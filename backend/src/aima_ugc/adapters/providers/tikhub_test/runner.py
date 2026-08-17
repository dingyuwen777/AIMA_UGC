"""复用生产 TikHub Runtime 的五平台无数据库调试执行器。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

from aima_ugc.adapters.providers.tikhub import runtime as tikhub_runtime
from aima_ugc.adapters.providers.tikhub.capabilities import TIKHUB_PLATFORM_CAPABILITIES
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.contracts.collection import (
    CollectionDecisionContextV1,
    CollectionDecisionPolicyV1,
    CollectionDecisionRequestV1,
    CollectionDecisionV1,
    ContentObservationV1,
    PreviousContentStateV1,
    ReplyDecisionRequestV1,
)
from aima_ugc.modules.collection.decision import CollectionDecisionService

from .config import TikHubTestConfig
from .core import DebugState, RawOutputRecord, RunOutputStore, default_run_id
from .excel import ReviewBlock, ReviewCommentRow, ReviewContent, write_review_workbook

_DEFAULT_OUTPUT_ROOT = Path(__file__).with_name("output")
_BEIJING = ZoneInfo("Asia/Shanghai")
_CAPABILITIES = {item.platform: item for item in TIKHUB_PLATFORM_CAPABILITIES}


@dataclass(frozen=True, slots=True)
class TikHubTestRunResult:
    platform: tikhub_runtime.TikHubPlatform
    run_dir: Path
    workbook_path: Path
    manifest_path: Path
    content_count: int
    root_comment_count: int
    reply_count: int
    request_count: int


@dataclass(frozen=True, slots=True)
class _RunLimits:
    max_search_pages: int
    max_contents: int | None
    max_comments_per_content: int
    max_comment_pages_per_content: int
    max_replies_per_root: int
    max_reply_pages_per_root: int

    def validate(self) -> None:
        values = {
            "max_search_pages": self.max_search_pages,
            "max_comments_per_content": self.max_comments_per_content,
            "max_comment_pages_per_content": self.max_comment_pages_per_content,
            "max_replies_per_root": self.max_replies_per_root,
            "max_reply_pages_per_root": self.max_reply_pages_per_root,
        }
        if self.max_contents is not None:
            values["max_contents"] = self.max_contents
        invalid = [name for name, value in values.items() if value < 1]
        if invalid:
            raise ValueError(f"TikHub 调试上限必须大于 0: {', '.join(invalid)}")


class _TikHubDebugRunner:
    def __init__(
        self,
        *,
        platform: tikhub_runtime.TikHubPlatform,
        keyword: str,
        search_config: dict[str, object],
        provider_config: TikHubTestConfig,
        output_root: Path,
        run_id: str,
        limits: _RunLimits,
        include_comments: bool,
        include_replies: bool,
        force_refresh: bool,
    ) -> None:
        if not keyword.strip():
            raise ValueError("keyword 不能为空")
        limits.validate()
        self.platform = platform
        self.keyword = keyword.strip()
        self.search_config = search_config
        self.provider_config = provider_config
        self.limits = limits
        self.include_comments = include_comments
        self.include_replies = include_replies
        self.force_refresh = force_refresh
        self.capability = _CAPABILITIES[platform]
        self.decision_service = CollectionDecisionService()
        self.store = RunOutputStore.create(
            output_root=output_root,
            platform=platform,
            run_id=run_id,
        )
        self.state = DebugState.load(output_root / platform / "state.json")
        self._request_no = 0
        self._requests: list[dict[str, object]] = []
        self._blocks: list[ReviewBlock] = []
        self._seen_contents: set[str] = set()
        self._seen_comments: set[tuple[str, str]] = set()
        self._root_comment_count = 0
        self._reply_count = 0
        self._search_stop_reason: str | None = None

    def run(self) -> TikHubTestRunResult:
        error: Exception | None = None
        try:
            with TikHubHttpTransport(
                base_url=self.provider_config.base_url,
                timeout_seconds=self.provider_config.timeout_seconds,
            ) as transport:
                self._run_search(transport)
        except Exception as exc:
            error = exc
        finally:
            self.state.save()
            workbook_path = write_review_workbook(
                tuple(self._blocks),
                self.store.review_dir / f"{self.platform}_review.xlsx",
            )
            manifest_path = self.store.write_manifest(self._manifest(error))

        if error is not None:
            raise error
        return TikHubTestRunResult(
            platform=self.platform,
            run_dir=self.store.run_dir,
            workbook_path=workbook_path,
            manifest_path=manifest_path,
            content_count=len(self._blocks),
            root_comment_count=self._root_comment_count,
            reply_count=self._reply_count,
            request_count=self._request_no,
        )

    def _run_search(self, transport: TikHubHttpTransport) -> None:
        pagination: dict[str, object] | None = None
        for page_no in range(1, self.limits.max_search_pages + 1):
            call = tikhub_runtime.build_search_call(
                platform=self.platform,
                keyword=self.keyword,
                config=self.search_config,
                state=pagination,
            )
            body, raw_record = self._send(transport, call)
            items = tikhub_runtime.extract_search_items(self.platform, body)
            for item_index, raw_item in enumerate(items):
                content = tikhub_runtime.map_content(
                    platform=self.platform,
                    raw=raw_item,
                    context=tikhub_runtime.mapping_context(
                        provider_request_id=raw_record.request_id,
                        provider_attempt_id=raw_record.attempt_id,
                        raw_artifact_id=raw_record.artifact_id,
                        operation=call.operation,
                        source_type="keyword",
                        source_value=self.keyword,
                        observed_at=raw_record.observed_at,
                    ),
                    item_locator=f"search.page[{page_no}].items[{item_index}]",
                )
                content_id = content.external_content_id
                if content_id in self._seen_contents:
                    continue
                self._seen_contents.add(content_id)
                self.store.append_canonical("contents", content)
                self._process_content(
                    transport,
                    search_content=content,
                    search_raw_locator=(
                        f"{self.store.relative_path(raw_record.path)}"
                        f"#search.page[{page_no}].items[{item_index}]"
                    ),
                )
                if self._content_limit_reached():
                    self._search_stop_reason = "content_target_reached"
                    return

            advance = tikhub_runtime.advance_search(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            if not advance.should_continue:
                self._search_stop_reason = advance.stop_reason or "provider_exhausted"
                return
            pagination = cast(dict[str, object], advance.next_state)
        self._search_stop_reason = "max_search_pages_reached"

    def _process_content(
        self,
        transport: TikHubHttpTransport,
        *,
        search_content: CanonicalContentV1,
        search_raw_locator: str,
    ) -> None:
        content_id = search_content.external_content_id
        previous_exists = self.state.has_content(self.platform, content_id)
        previous_count = self.state.previous_comment_count(self.platform, content_id)
        decision = self._decide(
            content=search_content,
            previous_exists=previous_exists,
            previous_count=previous_count,
            after_detail=False,
        )
        content = search_content
        content_raw_locator = search_raw_locator

        if decision.detail_action == "fetch":
            detail_call = tikhub_runtime.build_detail_call(self.platform, search_content)
            detail_body, detail_raw = self._send(transport, detail_call)
            detail_items = tikhub_runtime.extract_detail_items(self.platform, detail_body)
            mapped_details: list[tuple[CanonicalContentV1, str]] = []
            for index, detail_item in enumerate(detail_items):
                mapped = tikhub_runtime.map_content(
                    platform=self.platform,
                    raw=detail_item,
                    context=tikhub_runtime.mapping_context(
                        provider_request_id=detail_raw.request_id,
                        provider_attempt_id=detail_raw.attempt_id,
                        raw_artifact_id=detail_raw.artifact_id,
                        operation=detail_call.operation,
                        source_type="content",
                        source_value=content_id,
                        observed_at=detail_raw.observed_at,
                    ),
                    item_locator=f"detail.items[{index}]",
                )
                self.store.append_canonical("contents", mapped)
                mapped_details.append(
                    (
                        mapped,
                        f"{self.store.relative_path(detail_raw.path)}#detail.items[{index}]",
                    )
                )
            matching = next(
                (item for item in mapped_details if item[0].external_content_id == content_id),
                None,
            )
            if matching is None:
                raise RuntimeError(
                    f"TikHub {self.platform} Detail 未返回目标内容 {content_id} 的可映射数据"
                )
            content, content_raw_locator = matching
            decision = self._decide(
                content=content,
                previous_exists=previous_exists,
                previous_count=previous_count,
                after_detail=True,
            )

        comments: list[ReviewCommentRow] = []
        coverage = self._coverage_for_skipped_comments(
            decision.comment_action, decision.comment_reason
        )
        if decision.comment_action not in {"skip", "defer_until_detail"}:
            comments, coverage = self._fetch_comments(
                transport,
                content=content,
                target=decision.comment_target or self.limits.max_comments_per_content,
            )

        self.state.remember_content(
            self.platform,
            content_id,
            comment_count=content.metrics.comment_count,
        )
        self._blocks.append(
            ReviewBlock(
                content=_review_content(content, coverage, content_raw_locator),
                comments=tuple(comments),
            )
        )

    def _decide(
        self,
        *,
        content: CanonicalContentV1,
        previous_exists: bool,
        previous_count: int | None,
        after_detail: bool,
    ) -> CollectionDecisionV1:
        current_count = content.metrics.comment_count
        previous = PreviousContentStateV1(comment_count=previous_count) if previous_exists else None
        context = CollectionDecisionContextV1(
            scheduled_refresh_checkpoint=self.force_refresh and not after_detail,
        )
        if after_detail and previous is None:
            # Detail 已执行后，以“已有但评论计数未知”的最小快照进入第二次纯决策，
            # 让 Decision Service 决定 known count 的目标或 unknown count 的首屏 Probe。
            previous = PreviousContentStateV1(comment_count=None)
        return self.decision_service.decide(
            CollectionDecisionRequestV1(
                current=ContentObservationV1(
                    comment_count=current_count,
                    comments_available=None,
                    search_missing_required_fields=(not after_detail and current_count is None),
                    business_changed=(
                        not after_detail and previous_exists and previous_count != current_count
                    ),
                ),
                previous=previous,
                context=context,
                policy=self._policy(),
                capability=self.capability,
            )
        )

    def _policy(self) -> CollectionDecisionPolicyV1:
        return CollectionDecisionPolicyV1(
            comments_enabled=self.include_comments,
            full_fetch_threshold=self.limits.max_comments_per_content,
            sample_target=self.limits.max_comments_per_content,
            reply_target_per_root=self.limits.max_replies_per_root,
            comment_refresh_when_count_unchanged=self.force_refresh,
        )

    def _fetch_comments(
        self,
        transport: TikHubHttpTransport,
        *,
        content: CanonicalContentV1,
        target: int,
    ) -> tuple[list[ReviewCommentRow], str]:
        content_id = content.external_content_id
        pagination: dict[str, object] | None = None
        mapped_rows: list[ReviewCommentRow] = []
        root_total = 0
        provider_exhausted = False
        for page_no in range(1, self.limits.max_comment_pages_per_content + 1):
            call = tikhub_runtime.build_comments_call(
                platform=self.platform,
                external_content_id=content_id,
                state=pagination,
            )
            body, raw_record = self._send(transport, call)
            items = tikhub_runtime.extract_comment_items(self.platform, body)
            mapped_roots: list[CanonicalCommentV1] = []
            for item_index, raw_item in enumerate(items):
                comment = tikhub_runtime.map_comment(
                    platform=self.platform,
                    raw=raw_item,
                    context=tikhub_runtime.mapping_context(
                        provider_request_id=raw_record.request_id,
                        provider_attempt_id=raw_record.attempt_id,
                        raw_artifact_id=raw_record.artifact_id,
                        operation=call.operation,
                        source_type="content",
                        source_value=content_id,
                        observed_at=raw_record.observed_at,
                        external_content_id=content_id,
                    ),
                    item_locator=f"comments.page[{page_no}].items[{item_index}]",
                    is_root=True,
                )
                key = (content_id, comment.external_comment_id)
                if key in self._seen_comments:
                    continue
                self._seen_comments.add(key)
                self.store.append_canonical("comments", comment)
                self.state.remember_comment(
                    self.platform,
                    content_id,
                    comment.external_comment_id,
                )
                locator = (
                    f"{self.store.relative_path(raw_record.path)}"
                    f"#comments.page[{page_no}].items[{item_index}]"
                )
                mapped_rows.append(_review_comment(comment, "一级", locator))
                mapped_roots.append(comment)
                root_total += 1
                self._root_comment_count += 1

            if self.include_replies:
                for root in mapped_roots:
                    mapped_rows.extend(self._fetch_replies(transport, content, root))

            advance = tikhub_runtime.advance_comments(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            if not advance.should_continue:
                provider_exhausted = True
                break
            if root_total >= target:
                break
            pagination = cast(dict[str, object], advance.next_state)

        observed = root_total
        provider_count = content.metrics.comment_count
        if provider_exhausted and provider_count is not None and observed >= provider_count:
            return mapped_rows, f"complete {observed}/{provider_count}"
        if provider_exhausted and provider_count is None:
            return mapped_rows, f"complete {observed}/unknown"
        expected = str(provider_count) if provider_count is not None else "unknown"
        return mapped_rows, f"partial {observed}/{expected}"

    def _fetch_replies(
        self,
        transport: TikHubHttpTransport,
        content: CanonicalContentV1,
        root: CanonicalCommentV1,
    ) -> list[ReviewCommentRow]:
        reply_decision = self.decision_service.decide_reply(
            ReplyDecisionRequestV1(
                reply_count=root.metrics.reply_count,
                policy=self._policy(),
                capability=self.capability,
            )
        )
        if reply_decision.action == "skip":
            return []
        target = reply_decision.target or self.limits.max_replies_per_root
        pagination: dict[str, object] | None = None
        mapped_rows: list[ReviewCommentRow] = []
        mapped_count = 0
        for page_no in range(1, self.limits.max_reply_pages_per_root + 1):
            call = tikhub_runtime.build_sub_comments_call(
                platform=self.platform,
                external_content_id=content.external_content_id,
                root_comment_id=root.external_comment_id,
                state=pagination,
            )
            body, raw_record = self._send(transport, call)
            items = tikhub_runtime.extract_sub_comment_items(self.platform, body)
            for item_index, raw_item in enumerate(items):
                comment = tikhub_runtime.map_comment(
                    platform=self.platform,
                    raw=raw_item,
                    context=tikhub_runtime.mapping_context(
                        provider_request_id=raw_record.request_id,
                        provider_attempt_id=raw_record.attempt_id,
                        raw_artifact_id=raw_record.artifact_id,
                        operation=call.operation,
                        source_type="comment",
                        source_value=root.external_comment_id,
                        observed_at=raw_record.observed_at,
                        external_content_id=content.external_content_id,
                        root_comment_id=root.external_comment_id,
                    ),
                    item_locator=f"replies.page[{page_no}].items[{item_index}]",
                    is_root=False,
                )
                key = (content.external_content_id, comment.external_comment_id)
                if key in self._seen_comments:
                    continue
                self._seen_comments.add(key)
                self.store.append_canonical("comments", comment)
                self.state.remember_comment(
                    self.platform,
                    content.external_content_id,
                    comment.external_comment_id,
                )
                locator = (
                    f"{self.store.relative_path(raw_record.path)}"
                    f"#replies.page[{page_no}].items[{item_index}]"
                )
                mapped_rows.append(_review_comment(comment, "二级", locator))
                mapped_count += 1
                self._reply_count += 1

            advance = tikhub_runtime.advance_sub_comments(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            if not advance.should_continue or mapped_count >= target:
                break
            pagination = cast(dict[str, object], advance.next_state)
        return mapped_rows

    def _send(
        self,
        transport: TikHubHttpTransport,
        call: tikhub_runtime.TikHubOperationCall,
    ) -> tuple[dict[str, Any], RawOutputRecord]:
        self._request_no += 1
        response = transport.send(call.transport_request(self.provider_config.api_key))
        raw_record = self.store.save_raw(
            operation=call.operation,
            body=response.body,
            request_no=self._request_no,
            status_code=response.status_code,
            external_request_id=response.external_request_id,
        )
        self._requests.append(
            {
                "request_no": self._request_no,
                "business_operation": call.business_operation,
                "operation": call.operation,
                "method": call.method,
                "path": call.path,
                "status_code": response.status_code,
                "external_request_id": response.external_request_id,
                "raw_file": self.store.relative_path(raw_record.path),
            }
        )
        status_code = response.status_code
        if status_code is not None and status_code >= 400:
            raise RuntimeError(f"TikHub {self.platform} {call.operation} 返回 HTTP {status_code}")
        if not isinstance(response.body, dict):
            raise RuntimeError(f"TikHub {self.platform} {call.operation} 返回 JSON 顶层不是对象")
        return cast(dict[str, Any], response.body), raw_record

    def _content_limit_reached(self) -> bool:
        return (
            self.limits.max_contents is not None and len(self._blocks) >= self.limits.max_contents
        )

    def _coverage_for_skipped_comments(self, action: str, reason: str) -> str:
        if not self.include_comments or reason == "comments_disabled":
            return "not_requested"
        if reason in {"comments_operation_unavailable", "comments_unavailable"}:
            return "unavailable"
        if reason == "provider_reported_zero":
            return "complete 0/0"
        if action == "skip":
            return f"not_requested ({reason})"
        return f"partial 0/unknown ({reason})"

    def _manifest(self, error: Exception | None) -> dict[str, object]:
        return {
            "schema_version": "tikhub-test-run.v1",
            "platform": self.platform,
            "keyword": self.keyword,
            "status": "failed" if error is not None else "completed",
            "request_count": self._request_no,
            "content_count": len(self._blocks),
            "root_comment_count": self._root_comment_count,
            "reply_count": self._reply_count,
            "search_stop_reason": self._search_stop_reason,
            "requests": self._requests,
            "error_type": type(error).__name__ if error is not None else None,
            "error_summary": str(error) if error is not None else None,
        }


def run_platform(
    *,
    platform: tikhub_runtime.TikHubPlatform,
    keyword: str,
    search_config: dict[str, object] | None = None,
    env_file: str | Path | None = None,
    output_root: str | Path | None = None,
    run_id: str | None = None,
    max_search_pages: int = 20,
    max_contents: int | None = None,
    max_comments_per_content: int = 100,
    max_comment_pages_per_content: int = 20,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int = 10,
    include_comments: bool = True,
    include_replies: bool = True,
    force_refresh: bool = False,
) -> TikHubTestRunResult:
    """执行一个平台的独立真实调试；所有 Provider 私有逻辑由生产 Runtime 负责。"""
    config = TikHubTestConfig.load(env_file)
    root = Path(output_root) if output_root is not None else _DEFAULT_OUTPUT_ROOT
    return _TikHubDebugRunner(
        platform=platform,
        keyword=keyword,
        search_config=search_config or {},
        provider_config=config,
        output_root=root,
        run_id=run_id or default_run_id(),
        limits=_RunLimits(
            max_search_pages=max_search_pages,
            max_contents=max_contents,
            max_comments_per_content=max_comments_per_content,
            max_comment_pages_per_content=max_comment_pages_per_content,
            max_replies_per_root=max_replies_per_root,
            max_reply_pages_per_root=max_reply_pages_per_root,
        ),
        include_comments=include_comments,
        include_replies=include_replies,
        force_refresh=force_refresh,
    ).run()


def _review_content(
    content: CanonicalContentV1,
    coverage: str,
    raw_locator: str,
) -> ReviewContent:
    author = content.author
    author_label = None
    if author is not None:
        author_label = author.display_name or author.handle or author.external_account_id
    content_url = content.canonical_url or content.share_url
    return ReviewContent(
        platform=content.platform,
        external_content_id=content.external_content_id,
        content_type=content.content_type,
        title=content.title,
        text=content.text,
        author=author_label,
        published_at=_human_time(content.published_at),
        content_url=str(content_url) if content_url is not None else None,
        like_count=content.metrics.like_count,
        comment_count=content.metrics.comment_count,
        favorite_count=content.metrics.favorite_count,
        share_count=content.metrics.share_count,
        coverage=coverage,
        raw_locator=raw_locator,
    )


def _review_comment(
    comment: CanonicalCommentV1,
    level: str,
    raw_locator: str,
) -> ReviewCommentRow:
    author = comment.author
    author_label = None
    if author is not None:
        author_label = author.display_name or author.handle or author.external_account_id
    return ReviewCommentRow(
        level=level,
        comment_id=comment.external_comment_id,
        root_comment_id=comment.root_comment_id,
        parent_comment_id=comment.parent_comment_id,
        author=author_label,
        text=comment.text,
        published_at=_human_time(comment.published_at),
        like_count=comment.metrics.like_count,
        reply_count=comment.metrics.reply_count,
        raw_locator=raw_locator,
    )


def _human_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    converted = value.astimezone(_BEIJING)
    return converted.strftime("%Y-%m-%d %H:%M:%S")


__all__ = ["TikHubTestRunResult", "run_platform"]
