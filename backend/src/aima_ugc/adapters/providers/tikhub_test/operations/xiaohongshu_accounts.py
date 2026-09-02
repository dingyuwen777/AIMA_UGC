"""小红书指定账号人工采集：账号发现复用生产 TikHub Operation，内容处理复用现有调试主链。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

from aima_ugc.adapters.providers.tikhub import account_runtime
from aima_ugc.adapters.providers.tikhub import runtime as tikhub_runtime
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from aima_ugc.adapters.providers.tikhub_test.core.config import TikHubTestConfig
from aima_ugc.adapters.providers.tikhub_test.core.core import default_run_id
from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.contracts.collection import CollectionDecisionV1
from aima_ugc.contracts.export import UnifiedDataExcelCommentV1
from aima_ugc.contracts.provider import assert_secret_free
from aima_ugc.platform.time import beijing_now

from .runner import (
    _DEFAULT_OUTPUT_ROOT,
    _RunLimits,
    _TikHubDebugRunner,
    TikHubTestRunResult,
)

_BEIJING_TZ = ZoneInfo("Asia/Shanghai")
_ACCOUNT_CACHE_SCHEMA = "tikhub-test-account-cache.v1"
CommentMode = Literal["limited", "all"]
ResolutionReason = Literal["not_found", "ambiguous", "incomplete", "identity_mismatch"]


@dataclass(frozen=True, slots=True)
class XiaohongshuAccountTarget:
    """人工配置的小红书账号目标；稳定身份优先级为 user_id > red_id > nickname。"""

    nickname: str | None = None
    red_id: str | None = None
    user_id: str | None = None

    def __post_init__(self) -> None:
        """去除配置空白并拒绝完全没有定位信息的账号。"""
        object.__setattr__(self, "nickname", _normalized_optional(self.nickname))
        object.__setattr__(self, "red_id", _normalized_optional(self.red_id))
        object.__setattr__(self, "user_id", _normalized_optional(self.user_id))
        if self.nickname is None and self.red_id is None and self.user_id is None:
            raise ValueError("小红书账号至少提供 nickname、red_id 或 user_id 之一")


@dataclass(frozen=True, slots=True)
class ResolvedXiaohongshuAccount:
    """完成消歧后可安全用于付费用户笔记请求的稳定账号身份。"""

    user_id: str
    red_id: str | None
    nickname: str | None
    nickname_matches: bool | None


class XiaohongshuAccountResolutionError(ValueError):
    """账号无法安全解析时的失败；reason 用于决定是否允许备用搜索词。"""

    def __init__(self, message: str, *, reason: ResolutionReason) -> None:
        """保存稳定失败分类，供账号解析流程决定是否继续备用搜索。"""
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class _DateWindow:
    """把人类包含式日期区间转换为北京时间左闭右开窗口。"""

    start_date: date
    end_date: date
    start_at: datetime
    end_at_exclusive: datetime

    @classmethod
    def create(cls, *, start_date: date | str, end_date: date | str) -> _DateWindow:
        """解析 ISO 日期，并建立 `[start, end + 1 day)` 的北京时间窗口。"""
        start = _parse_date(start_date, "start_date")
        end = _parse_date(end_date, "end_date")
        if end < start:
            raise ValueError("end_date 不能早于 start_date")
        start_at = datetime.combine(start, time.min, tzinfo=_BEIJING_TZ)
        end_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=_BEIJING_TZ)
        return cls(start, end, start_at, end_at)

    def contains(self, published_at: datetime) -> bool:
        """按实际时区转换后判断发布时间是否位于目标区间。"""
        if published_at.tzinfo is None:
            return False
        observed = published_at.astimezone(_BEIJING_TZ)
        return self.start_at <= observed < self.end_at_exclusive


@dataclass(slots=True)
class _AccountResolutionCache:
    """只缓存稳定公开账号身份，避免重复付费搜索；不保存 Secret。"""

    path: Path
    entries: dict[str, dict[str, object]]

    @classmethod
    def load(cls, path: Path) -> _AccountResolutionCache:
        """读取账号解析缓存；损坏缓存 fail closed，避免静默抓错账号。"""
        if not path.exists():
            return cls(path=path, entries={})
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"小红书账号解析缓存无法读取：{path}") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != _ACCOUNT_CACHE_SCHEMA:
            raise ValueError("小红书账号解析缓存 schema_version 不受支持")
        entries = raw.get("entries")
        if not isinstance(entries, dict):
            raise ValueError("小红书账号解析缓存缺少 entries")
        normalized: dict[str, dict[str, object]] = {}
        for key, value in entries.items():
            if isinstance(key, str) and isinstance(value, dict):
                normalized[key] = dict(value)
        return cls(path=path, entries=normalized)

    def get(self, target: XiaohongshuAccountTarget) -> ResolvedXiaohongshuAccount | None:
        """仅按稳定 red_id/user_id 复用缓存；昵称单独不足以成为缓存身份。"""
        key = _cache_key(target)
        if key is None:
            return None
        entry = self.entries.get(key)
        if entry is None:
            return None
        user_id = _object_string(entry.get("user_id"))
        red_id = _object_string(entry.get("red_id"))
        nickname = _object_string(entry.get("nickname"))
        if user_id is None:
            return None
        if target.user_id is not None and user_id != target.user_id:
            return None
        if target.red_id is not None and red_id != target.red_id:
            return None
        return ResolvedXiaohongshuAccount(
            user_id=user_id,
            red_id=red_id,
            nickname=nickname,
            nickname_matches=_nickname_matches(target.nickname, nickname),
        )

    def remember(
        self,
        target: XiaohongshuAccountTarget,
        resolved: ResolvedXiaohongshuAccount,
    ) -> None:
        """记录稳定账号解析结果并立即原子保存，降低中途失败后的重复搜索费用。"""
        key = _cache_key(target)
        if key is None:
            return
        self.entries[key] = {
            "user_id": resolved.user_id,
            "red_id": resolved.red_id,
            "nickname": resolved.nickname,
            "resolved_at": beijing_now().isoformat(),
        }
        self.save()

    def save(self) -> Path:
        """以 Secret-free JSON 原子发布账号解析缓存。"""
        payload: dict[str, object] = {
            "schema_version": _ACCOUNT_CACHE_SCHEMA,
            "entries": self.entries,
        }
        assert_secret_free(payload, path="tikhub_test.resolved_accounts")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return self.path


def resolve_account_candidate(
    target: XiaohongshuAccountTarget,
    candidates: Sequence[dict[str, Any]],
) -> ResolvedXiaohongshuAccount:
    """按稳定身份消歧账号；red_id 精确匹配优先，昵称歧义时拒绝猜测。"""
    identities: dict[str, ResolvedXiaohongshuAccount] = {}
    for raw in candidates:
        candidate = _resolved_candidate(target, raw)
        if candidate is not None:
            identities[candidate.user_id] = candidate
    values = tuple(identities.values())

    if target.user_id is not None:
        matches = tuple(item for item in values if item.user_id == target.user_id)
        if len(matches) == 1:
            candidate = matches[0]
            if target.red_id is not None and candidate.red_id not in {None, target.red_id}:
                raise XiaohongshuAccountResolutionError(
                    f"user_id={target.user_id} 返回的 red_id 与配置不一致",
                    reason="identity_mismatch",
                )
            return candidate
        if len(matches) > 1:
            raise XiaohongshuAccountResolutionError(
                f"user_id={target.user_id} 候选不唯一",
                reason="ambiguous",
            )
        raise XiaohongshuAccountResolutionError(
            f"未找到 user_id={target.user_id} 的账号候选",
            reason="not_found",
        )

    if target.red_id is not None:
        matches = tuple(item for item in values if item.red_id == target.red_id)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise XiaohongshuAccountResolutionError(
                f"小红书号 {target.red_id} 候选不唯一",
                reason="ambiguous",
            )
        raise XiaohongshuAccountResolutionError(
            f"未找到小红书号 {target.red_id} 的精确账号候选",
            reason="not_found",
        )

    assert target.nickname is not None
    matches = tuple(item for item in values if item.nickname == target.nickname)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise XiaohongshuAccountResolutionError(
            f"昵称 {target.nickname} 候选不唯一，必须补充小红书号或 user_id",
            reason="ambiguous",
        )
    raise XiaohongshuAccountResolutionError(
        f"未找到昵称 {target.nickname} 的精确账号候选",
        reason="not_found",
    )


class _XiaohongshuAccountRunner(_TikHubDebugRunner):
    """把账号 Discovery 接到既有 Detail/Comment/Reply/Canonical/Excel 调试主链。"""

    def __init__(
        self,
        *,
        accounts: tuple[XiaohongshuAccountTarget, ...],
        date_window: _DateWindow,
        provider_config: TikHubTestConfig,
        output_root: Path,
        run_id: str,
        limits: _RunLimits,
        max_account_search_pages: int,
        max_note_pages_per_account: int,
        include_comments: bool,
        include_replies: bool,
        comment_mode: CommentMode,
        validate_user_info: bool,
    ) -> None:
        """初始化账号采集编排，并复用现有调试 Runner 的 Transport/输出/内容处理能力。"""
        if max_account_search_pages < 1:
            raise ValueError("max_account_search_pages 必须大于 0")
        if max_note_pages_per_account < 1:
            raise ValueError("max_note_pages_per_account 必须大于 0")
        if comment_mode not in {"limited", "all"}:
            raise ValueError("comment_mode 只允许 limited 或 all")

        self.date_window = date_window
        self.max_account_search_pages = max_account_search_pages
        self.max_note_pages_per_account = max_note_pages_per_account
        self.comment_mode = comment_mode
        self.validate_user_info = validate_user_info
        self._account_by_key = {
            f"account[{index}]": target for index, target in enumerate(accounts, start=1)
        }
        self._account_summaries = {
            key: _new_account_summary(target) for key, target in self._account_by_key.items()
        }
        self._current_account_key: str | None = None
        self._resolution_cache = _AccountResolutionCache.load(
            output_root / "xiaohongshu" / "resolved_accounts.json"
        )

        super().__init__(
            platform="xiaohongshu",
            keywords=tuple(self._account_by_key),
            search_config={},
            provider_config=provider_config,
            output_root=output_root,
            run_id=run_id,
            limits=limits,
            include_comments=include_comments,
            include_replies=include_replies,
            force_refresh=True,
            write_to_database=False,
            provider_config_id=None,
        )

    def _run_search(self, transport: TikHubHttpTransport, keyword: str) -> None:
        """把基类的“一个关键词 Discovery”槽位替换为“一个账号 Discovery”，并隔离账号失败。"""
        target = self._account_by_key[keyword]
        summary = self._account_summaries[keyword]
        summary["status"] = "running"
        self._current_account_key = keyword
        try:
            resolved, resolution_method = self._resolve_account(transport, keyword, target)
            summary.update(
                {
                    "resolution_method": resolution_method,
                    "resolved_user_id": resolved.user_id,
                    "resolved_red_id": resolved.red_id,
                    "resolved_nickname": resolved.nickname,
                    "nickname_matches": resolved.nickname_matches,
                }
            )
            self._run_account_notes(transport, keyword, resolved, summary)
            if summary["status"] == "running":
                summary["status"] = "completed"
        except Exception as exc:
            summary["status"] = "failed"
            summary["error_type"] = type(exc).__name__
            summary["error_summary"] = str(exc)
            self._search_stop_reasons[keyword] = "account_failed"
        finally:
            self._current_account_key = None

    def _resolve_account(
        self,
        transport: TikHubHttpTransport,
        account_key: str,
        target: XiaohongshuAccountTarget,
    ) -> tuple[ResolvedXiaohongshuAccount, str]:
        """按 cache → user_id → red_id/nickname 搜索解析稳定 user_id。"""
        cached = self._resolution_cache.get(target)
        if cached is not None:
            resolved = self._validate_account_info_if_requested(
                transport,
                account_key,
                target,
                cached,
            )
            return resolved, "cache"

        if target.user_id is not None:
            resolved = ResolvedXiaohongshuAccount(
                user_id=target.user_id,
                red_id=target.red_id,
                nickname=target.nickname,
                nickname_matches=True if target.nickname is not None else None,
            )
            resolved = self._validate_account_info_if_requested(
                transport,
                account_key,
                target,
                resolved,
            )
            self._resolution_cache.remember(target, resolved)
            return resolved, "configured_user_id"

        last_not_found: XiaohongshuAccountResolutionError | None = None
        for query in _resolution_queries(target):
            try:
                resolved = self._resolve_account_from_query(
                    transport,
                    account_key,
                    target,
                    query=query,
                )
            except XiaohongshuAccountResolutionError as exc:
                if exc.reason == "not_found":
                    last_not_found = exc
                    continue
                raise
            resolved = self._validate_account_info_if_requested(
                transport,
                account_key,
                target,
                resolved,
            )
            self._resolution_cache.remember(target, resolved)
            return resolved, f"search_users:{query}"

        if last_not_found is not None:
            raise last_not_found
        raise XiaohongshuAccountResolutionError(
            "账号缺少可执行的解析输入",
            reason="not_found",
        )

    def _resolve_account_from_query(
        self,
        transport: TikHubHttpTransport,
        account_key: str,
        target: XiaohongshuAccountTarget,
        *,
        query: str,
    ) -> ResolvedXiaohongshuAccount:
        """分页搜索单个解析关键词；稳定 red_id 命中可提前停止，昵称必须等 Provider 耗尽。"""
        pagination: dict[str, object] | None = None
        candidates: list[dict[str, Any]] = []
        for _ in range(self.max_account_search_pages):
            call = account_runtime.build_user_search_call(keyword=query, state=pagination)
            body, _ = self._send(transport, call, keyword=account_key)
            self._annotate_last_request(account_key, resolution_query=query)
            candidates.extend(account_runtime.extract_user_search_items(body))

            if target.red_id is not None:
                try:
                    return resolve_account_candidate(target, candidates)
                except XiaohongshuAccountResolutionError as exc:
                    if exc.reason != "not_found":
                        raise

            advance = account_runtime.advance_user_search(state=pagination, body=body)
            if not advance.should_continue:
                return resolve_account_candidate(target, candidates)
            pagination = cast(dict[str, object], advance.next_state)

        raise XiaohongshuAccountResolutionError(
            f"搜索 {query} 达到 {self.max_account_search_pages} 页上限，无法确认账号唯一性",
            reason="incomplete",
        )

    def _validate_account_info_if_requested(
        self,
        transport: TikHubHttpTransport,
        account_key: str,
        target: XiaohongshuAccountTarget,
        resolved: ResolvedXiaohongshuAccount,
    ) -> ResolvedXiaohongshuAccount:
        """按显式开关调用付费用户详情做身份复核；默认不增加该额外请求。"""
        if not self.validate_user_info:
            return resolved
        call = account_runtime.build_user_info_call(user_id=resolved.user_id)
        body, _ = self._send(transport, call, keyword=account_key)
        self._annotate_last_request(account_key)
        raw_user = account_runtime.extract_user_info_item(body)
        if raw_user is None:
            raise XiaohongshuAccountResolutionError(
                f"user_id={resolved.user_id} 用户详情缺少可验证身份",
                reason="identity_mismatch",
            )
        validation_target = XiaohongshuAccountTarget(
            nickname=target.nickname,
            red_id=target.red_id,
            user_id=resolved.user_id,
        )
        return resolve_account_candidate(validation_target, (raw_user,))

    def _run_account_notes(
        self,
        transport: TikHubHttpTransport,
        account_key: str,
        resolved: ResolvedXiaohongshuAccount,
        summary: dict[str, object],
    ) -> None:
        """遍历用户笔记 cursor；所有页都按 Provider 终止，不依据日期顺序做未验证的提前停止。"""
        pagination: dict[str, object] | None = None
        for page_no in range(1, self.max_note_pages_per_account + 1):
            call = account_runtime.build_user_notes_call(
                user_id=resolved.user_id,
                state=pagination,
            )
            body, raw_record = self._send(transport, call, keyword=account_key)
            self._annotate_last_request(account_key)
            summary["note_pages"] = page_no
            items = account_runtime.extract_user_note_items(body)
            for item_index, raw_item in enumerate(items):
                _increment(summary, "discovered_note_count")
                item_locator = f"user_notes.page[{page_no}].notes[{item_index}]"
                try:
                    content = tikhub_runtime.map_content(
                        platform="xiaohongshu",
                        raw=raw_item,
                        context=tikhub_runtime.mapping_context(
                            provider_request_id=raw_record.request_id,
                            provider_attempt_id=raw_record.attempt_id,
                            raw_artifact_id=raw_record.artifact_id,
                            operation=call.operation,
                            source_type="account",
                            source_value=resolved.user_id,
                            observed_at=raw_record.observed_at,
                        ),
                        item_locator=item_locator,
                    )
                except Exception as exc:
                    self._record_note_failure(summary, None, "map_user_note", exc)
                    continue

                if content.published_at is None:
                    _increment(summary, "missing_published_at_count")
                    self._record_note_failure(
                        summary,
                        content.external_content_id,
                        "date_filter",
                        ValueError("用户笔记列表未观察到 published_at，无法安全判断日期范围"),
                    )
                    continue
                if not self.date_window.contains(content.published_at):
                    _increment(summary, "out_of_range_note_count")
                    continue

                _increment(summary, "in_range_note_count")
                content_id = content.external_content_id
                if content_id in self._seen_contents:
                    _increment(summary, "duplicate_note_count")
                    continue
                self._seen_contents.add(content_id)
                self.store.append_canonical("contents", content)
                raw_locator = f"{self.store.relative_path(raw_record.path)}#{item_locator}"
                before_blocks = len(self._blocks)
                try:
                    self._process_content(
                        transport,
                        keyword=account_key,
                        search_content=content,
                        search_raw_locator=raw_locator,
                    )
                except Exception as exc:
                    self._record_note_failure(summary, content_id, "content_pipeline", exc)
                    continue
                _increment(summary, "processed_note_count")
                self._record_partial_comment_coverage(summary, before_blocks)
                if self._content_limit_reached():
                    summary["note_stop_reason"] = "content_target_reached"
                    self._search_stop_reasons[account_key] = "content_target_reached"
                    return

            advance = account_runtime.advance_user_notes(state=pagination, body=body)
            if not advance.should_continue:
                stop_reason = advance.stop_reason or "provider_exhausted"
                summary["note_stop_reason"] = stop_reason
                self._search_stop_reasons[account_key] = stop_reason
                if _account_has_partial_results(summary):
                    summary["status"] = "partial"
                return
            pagination = cast(dict[str, object], advance.next_state)

        summary["note_stop_reason"] = "max_note_pages_per_account_reached"
        summary["status"] = "partial"
        self._search_stop_reasons[account_key] = "max_note_pages_per_account_reached"

    def _decide(
        self,
        *,
        content: CanonicalContentV1,
        previous_exists: bool,
        previous_count: int | None,
        after_detail: bool,
    ) -> CollectionDecisionV1:
        """all 模式只把评论软目标提升为 Provider 已观察的真实评论总数。"""
        decision = super()._decide(
            content=content,
            previous_exists=previous_exists,
            previous_count=previous_count,
            after_detail=after_detail,
        )
        if self.comment_mode != "all" or not self.include_comments:
            return decision
        comment_count = content.metrics.comment_count
        if comment_count is None or comment_count < 1:
            return decision
        if decision.comment_action in {"skip", "defer_until_detail"}:
            return decision
        return decision.model_copy(update={"comment_target": comment_count})

    def _fetch_replies(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        content: CanonicalContentV1,
        root: CanonicalCommentV1,
    ) -> list[UnifiedDataExcelCommentV1]:
        """all 模式用真实 reply_count 替换回复软目标，仍保留现有硬页数和 Provider 终止条件。"""
        expected = root.metrics.reply_count
        if self.comment_mode != "all" or expected is None or expected < 1:
            return super()._fetch_replies(
                transport,
                keyword=keyword,
                content=content,
                root=root,
            )

        original_limits = self.limits
        self.limits = replace(
            original_limits,
            max_replies_per_root=max(original_limits.max_replies_per_root, expected),
        )
        try:
            rows = super()._fetch_replies(
                transport,
                keyword=keyword,
                content=content,
                root=root,
            )
        finally:
            self.limits = original_limits

        if len(rows) < expected:
            summary = self._current_account_summary()
            if summary is not None:
                cast(list[object], summary["warnings"]).append(
                    {
                        "stage": "replies",
                        "external_content_id": content.external_content_id,
                        "root_comment_id": root.external_comment_id,
                        "observed": len(rows),
                        "expected": expected,
                        "reason": "hard_page_limit_or_provider_shape",
                    }
                )
                summary["status"] = "partial"
        return rows

    def _annotate_last_request(
        self,
        account_key: str,
        *,
        resolution_query: str | None = None,
    ) -> None:
        """给脱敏请求摘要补账号定位上下文，不复制请求参数或鉴权信息。"""
        if not self._requests:
            return
        target = self._account_by_key[account_key]
        request = self._requests[-1]
        request["account_key"] = account_key
        request["configured_red_id"] = target.red_id
        request["configured_nickname"] = target.nickname
        if resolution_query is not None:
            request["resolution_query"] = resolution_query

    def _record_note_failure(
        self,
        summary: dict[str, object],
        content_id: str | None,
        stage: str,
        error: Exception,
    ) -> None:
        """记录单笔记失败并保持同账号其他笔记、其他账号继续执行。"""
        cast(list[object], summary["note_failures"]).append(
            {
                "external_content_id": content_id,
                "stage": stage,
                "error_type": type(error).__name__,
                "error_summary": str(error),
            }
        )
        summary["status"] = "partial"

    def _record_partial_comment_coverage(
        self,
        summary: dict[str, object],
        before_blocks: int,
    ) -> None:
        """all 模式若现有内容链明确返回 partial coverage，则把账号结果标记为部分完成。"""
        if self.comment_mode != "all" or len(self._blocks) <= before_blocks:
            return
        coverage = self._blocks[-1].content.coverage
        if isinstance(coverage, str) and coverage.startswith("partial"):
            _increment(summary, "partial_comment_count")
            summary["status"] = "partial"

    def _current_account_summary(self) -> dict[str, object] | None:
        """返回当前账号摘要，供回复分页等公共下游补充部分完成事实。"""
        if self._current_account_key is None:
            return None
        return self._account_summaries[self._current_account_key]

    def _run_summary(self, error: Exception | None) -> dict[str, object]:
        """把通用调试摘要投影为账号采集摘要，同时保留原始请求与内容失败证据。"""
        payload = super()._run_summary(error)
        account_summaries: list[dict[str, object]] = []
        for key in self._account_by_key:
            summary = self._account_summaries[key]
            if summary["status"] == "pending":
                reason = self._search_stop_reasons.get(key)
                summary["status"] = "skipped" if reason else "pending"
                if reason:
                    summary["note_stop_reason"] = reason
            account_summaries.append(dict(summary))

        statuses = {str(item.get("status")) for item in account_summaries}
        if error is not None or (account_summaries and statuses == {"failed"}):
            status = "failed"
        elif self._content_failures or statuses.intersection({"failed", "partial"}):
            status = "completed_with_errors"
        else:
            status = "completed"

        payload.pop("keyword", None)
        payload.pop("keywords", None)
        payload.pop("matched_keywords", None)
        payload.update(
            {
                "schema_version": "tikhub-test-account-run.v1",
                "operations": "xiaohongshu_accounts",
                "status": status,
                "comment_mode": self.comment_mode,
                "date_range": {
                    "start_date": self.date_window.start_date.isoformat(),
                    "end_date": self.date_window.end_date.isoformat(),
                    "timezone": "Asia/Shanghai",
                },
                "accounts": account_summaries,
            }
        )
        return payload


def run_xiaohongshu_accounts(
    *,
    accounts: Sequence[XiaohongshuAccountTarget],
    start_date: date | str,
    end_date: date | str,
    env_file: str | Path | None = None,
    output_root: str | Path | None = None,
    run_id: str | None = None,
    max_account_search_pages: int = 5,
    max_note_pages_per_account: int = 100,
    max_contents: int | None = None,
    max_comments_per_content: int = 100,
    max_comment_pages_per_content: int = 100,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int = 50,
    include_comments: bool = True,
    include_replies: bool = True,
    comment_mode: CommentMode = "all",
    validate_user_info: bool = False,
) -> TikHubTestRunResult:
    """按多个小红书账号和包含式日期区间执行人工文件采集，不写数据库。"""
    normalized_accounts = tuple(accounts)
    if not normalized_accounts:
        raise ValueError("accounts 至少包含一个账号")
    if not all(isinstance(item, XiaohongshuAccountTarget) for item in normalized_accounts):
        raise ValueError("accounts 只能包含 XiaohongshuAccountTarget")

    config = TikHubTestConfig.load(env_file)
    root = Path(output_root) if output_root is not None else _DEFAULT_OUTPUT_ROOT
    actual_run_id = run_id or default_run_id()
    return _XiaohongshuAccountRunner(
        accounts=normalized_accounts,
        date_window=_DateWindow.create(start_date=start_date, end_date=end_date),
        provider_config=config,
        output_root=root,
        run_id=actual_run_id,
        limits=_RunLimits(
            max_search_pages=max_account_search_pages,
            max_contents=max_contents,
            max_comments_per_content=max_comments_per_content,
            max_comment_pages_per_content=max_comment_pages_per_content,
            max_replies_per_root=max_replies_per_root,
            max_reply_pages_per_root=max_reply_pages_per_root,
        ),
        max_account_search_pages=max_account_search_pages,
        max_note_pages_per_account=max_note_pages_per_account,
        include_comments=include_comments,
        include_replies=include_replies,
        comment_mode=comment_mode,
        validate_user_info=validate_user_info,
    ).run()


def _resolved_candidate(
    target: XiaohongshuAccountTarget,
    raw: dict[str, Any],
) -> ResolvedXiaohongshuAccount | None:
    """把 Provider 用户候选规范化为稳定身份；缺 user_id 的候选不可用于后续付费请求。"""
    user = _unwrap_user(raw)
    user_id = _first_string(user, "user_id", "userid", "userId", "id")
    if user_id is None:
        return None
    red_id = _first_string(user, "red_id", "redId")
    nickname = _first_string(user, "nickname", "nick_name", "name")
    return ResolvedXiaohongshuAccount(
        user_id=user_id,
        red_id=red_id,
        nickname=nickname,
        nickname_matches=_nickname_matches(target.nickname, nickname),
    )


def _unwrap_user(raw: dict[str, Any]) -> dict[str, Any]:
    """兼容搜索候选和用户详情中的常见用户 wrapper。"""
    for key in ("user", "user_info", "userInfo", "profile"):
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return raw


def _resolution_queries(target: XiaohongshuAccountTarget) -> tuple[str, ...]:
    """优先用稳定小红书号搜索，未命中且有昵称时再做经过 red_id 复核的备用搜索。"""
    values: list[str] = []
    for value in (target.red_id, target.nickname):
        if value is not None and value not in values:
            values.append(value)
    return tuple(values)


def _cache_key(target: XiaohongshuAccountTarget) -> str | None:
    """缓存只使用稳定 red_id/user_id，拒绝把昵称单独当永久身份。"""
    if target.red_id is not None:
        return f"red_id:{target.red_id}"
    if target.user_id is not None:
        return f"user_id:{target.user_id}"
    return None


def _new_account_summary(target: XiaohongshuAccountTarget) -> dict[str, object]:
    """建立单账号运行摘要的稳定初始结构。"""
    return {
        "configured_nickname": target.nickname,
        "configured_red_id": target.red_id,
        "configured_user_id": target.user_id,
        "resolved_user_id": None,
        "resolved_red_id": None,
        "resolved_nickname": None,
        "nickname_matches": None,
        "resolution_method": None,
        "status": "pending",
        "note_pages": 0,
        "discovered_note_count": 0,
        "in_range_note_count": 0,
        "out_of_range_note_count": 0,
        "missing_published_at_count": 0,
        "duplicate_note_count": 0,
        "processed_note_count": 0,
        "partial_comment_count": 0,
        "note_stop_reason": None,
        "note_failures": [],
        "warnings": [],
        "error_type": None,
        "error_summary": None,
    }


def _account_has_partial_results(summary: dict[str, object]) -> bool:
    """判断账号是否存在会阻止“完整采集”结论的可观察缺口。"""
    missing = summary.get("missing_published_at_count")
    partial_comments = summary.get("partial_comment_count")
    failures = summary.get("note_failures")
    return bool(missing) or bool(partial_comments) or bool(failures)


def _increment(summary: dict[str, object], key: str) -> None:
    """安全递增账号摘要中的整型计数器。"""
    value = summary.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"账号摘要计数器 {key} 结构非法")
    summary[key] = value + 1


def _nickname_matches(configured: str | None, actual: str | None) -> bool | None:
    """昵称只做辅助核验；缺任一侧时返回未知，不覆盖稳定身份。"""
    if configured is None or actual is None:
        return None
    return configured == actual


def _first_string(raw: dict[str, Any], *keys: str) -> str | None:
    """从 Provider 用户对象中读取第一个非空字符串字段。"""
    for key in keys:
        if key in raw:
            value = _object_string(raw[key])
            if value is not None:
                return value
    return None


def _object_string(value: object) -> str | None:
    """把可序列化标量规范化为去空白字符串。"""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalized_optional(value: str | None) -> str | None:
    """把人工配置中的空字符串归一为 None。"""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _parse_date(value: date | str, field_name: str) -> date:
    """解析人工输入的 ISO 日期，不接受含时间的隐式截断。"""
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} 必须是 YYYY-MM-DD") from exc
    if type(value) is date:
        return value
    raise ValueError(f"{field_name} 必须是 date 或 YYYY-MM-DD 字符串")


__all__ = [
    "ResolvedXiaohongshuAccount",
    "XiaohongshuAccountResolutionError",
    "XiaohongshuAccountTarget",
    "resolve_account_candidate",
    "run_xiaohongshu_accounts",
]
