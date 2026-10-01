"""复用生产 TikHub Runtime 的五平台人工调试执行器。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from aima_ugc.adapters.providers.tikhub import runtime as tikhub_runtime
from aima_ugc.adapters.providers.tikhub.capabilities import TIKHUB_PLATFORM_CAPABILITIES
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from aima_ugc.adapters.providers.tikhub_test.core.config import TikHubTestConfig
from aima_ugc.adapters.providers.tikhub_test.core.core import (
    DebugState,
    RawOutputRecord,
    RunOutputStore,
    default_run_id,
)
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
from aima_ugc.contracts.export import UnifiedDataExcelCommentV1, UnifiedDataExcelV1
from aima_ugc.modules.collection.decision import (
    CollectionDecisionService,
    known_comment_boundary_reached,
)
from aima_ugc.modules.collection.providers.transport import ProviderTransportFailure
from aima_ugc.platform.export import (
    export_comment_labeling_excel,
    export_unified_data_excel,
    project_canonical_comment,
    project_canonical_content,
)

if TYPE_CHECKING:
    from aima_ugc.bootstrap.tikhub_test_database import TikHubDebugDatabaseSession

_DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "output"
_CAPABILITIES = {item.platform: item for item in TIKHUB_PLATFORM_CAPABILITIES}
_BEIJING = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class TikHubTestRunResult:
    platform: tikhub_runtime.TikHubPlatform
    run_dir: Path
    workbook_path: Path
    run_summary_path: Path
    content_count: int
    root_comment_count: int
    reply_count: int
    request_count: int


@dataclass(frozen=True, slots=True)
class _RunLimits:
    max_search_pages: int
    max_contents: int | None
    max_comments_per_content: int
    max_comment_pages_per_content: int | None
    max_replies_per_root: int
    max_reply_pages_per_root: int | None

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
        invalid = [name for name, value in values.items() if isinstance(value, int) and value < 1]
        if invalid:
            raise ValueError(f"TikHub 调试上限必须大于 0: {', '.join(invalid)}")


class _TikHubHttpStatusError(RuntimeError):
    """保留已落盘 HTTP 失败的安全关联信息，供内容级决策使用。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        operation: str,
        external_request_id: str | None,
        raw_file: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.operation = operation
        self.external_request_id = external_request_id
        self.raw_file = raw_file
        self.retryable = retryable


class _TikHubDebugRunner:
    _continue_after_item_http_error = False
    comment_mode: Literal["limited", "all"] = "limited"

    def __init__(
        self,
        *,
        platform: tikhub_runtime.TikHubPlatform,
        keywords: tuple[str, ...],
        search_config: dict[str, object],
        provider_config: TikHubTestConfig,
        output_root: Path,
        run_id: str,
        limits: _RunLimits,
        include_comments: bool,
        include_replies: bool,
        force_refresh: bool,
        write_to_database: bool,
        provider_config_id: UUID | None,
    ) -> None:
        limits.validate()
        self.platform = platform
        self.keywords = keywords
        self.search_config = search_config
        self.provider_config = provider_config
        self.run_id = run_id
        self.limits = limits
        self.include_comments = include_comments
        self.include_replies = include_replies
        self.force_refresh = force_refresh
        self.write_to_database = write_to_database
        self.provider_config_id = provider_config_id
        self.account_mode = False
        self.start_date: date | None = None
        self.end_date: date | None = None
        self.account_feed_config: dict[str, object] = {}
        self.capability = _CAPABILITIES[platform]
        self.decision_service = CollectionDecisionService()
        self.store = RunOutputStore.create(
            output_root=output_root,
            platform=platform,
            run_id=run_id,
        )
        self.state = DebugState.load(output_root / platform / "state.json")
        self._database: TikHubDebugDatabaseSession | None = None
        self._request_no = 0
        self._requests: list[dict[str, object]] = []
        self._content_failures: list[dict[str, object]] = []
        self._blocks: list[UnifiedDataExcelV1] = []
        self._matched_keywords: dict[str, list[str]] = {}
        self._seen_contents: set[str] = set()
        self._seen_comments: set[tuple[str, str]] = set()
        self._root_comment_count = 0
        self._reply_count = 0
        self._search_stop_reasons: dict[str, str] = {}
        self._account_results: list[dict[str, object]] = []
        self._partial_content_ids: set[str] = set()
        self._comment_page_counts: dict[str, int] = {}
        self._reply_page_counts: dict[tuple[str, str], int] = {}
        self._reply_expansion_counts: dict[tuple[str, str], int | None] = {}
        self._reply_ids_by_root: dict[tuple[str, str], set[str]] = {}
        self._comment_coverage_failures: list[dict[str, object]] = []
        self._comment_count_discrepancies: list[dict[str, object]] = []

    def run(self) -> TikHubTestRunResult:
        error: Exception | None = None
        try:
            if self.write_to_database:
                if self.provider_config_id is None:
                    raise ValueError("write_to_database=True 时必须显式提供 provider_config_id")
                from aima_ugc.bootstrap.tikhub_test_database import (
                    create_tikhub_debug_database_session,
                )

                self._database = create_tikhub_debug_database_session(
                    platform=self.platform,
                    keywords=self.keywords,
                    run_id=self.run_id,
                    provider_config_id=self.provider_config_id,
                    expected_base_url=self.provider_config.base_url,
                    expected_api_key=self.provider_config.api_key,
                    provider_timeout_seconds=self.provider_config.timeout_seconds,
                    search_config=self.search_config,
                    policy=self._policy(),
                )

            with TikHubHttpTransport(
                base_url=self.provider_config.base_url,
                timeout_seconds=self.provider_config.timeout_seconds,
            ) as transport:
                for keyword in self.keywords:
                    if self._content_limit_reached():
                        self._search_stop_reasons[keyword] = "not_started_content_target_reached"
                        continue
                    self._run_search(transport, keyword)
        except Exception as exc:
            error = exc
        finally:
            if self._database is not None:
                try:
                    self._database.finish(
                        error=error,
                        stop_reasons=self._search_stop_reasons,
                    )
                except Exception as finish_exc:
                    if error is None:
                        error = finish_exc
                finally:
                    self._database = None
            self.state.save()
            records = self._blocks_with_keywords()
            if self.platform in {"douyin", "kuaishou", "weibo", "bilibili"} and self.account_mode:
                workbook_path = export_comment_labeling_excel(
                    records,
                    self.store.raw_data_dir / f"{self.platform}_comments_for_labeling.xlsx",
                ).output_path
            else:
                workbook_path = export_unified_data_excel(
                    records,
                    self.store.raw_data_dir / f"{self.platform}_raw_data.xlsx",
                    include_analysis=False,
                ).output_path
            run_summary_path = self.store.write_run_summary(self._run_summary(error))

        if error is not None:
            raise error
        return TikHubTestRunResult(
            platform=self.platform,
            run_dir=self.store.run_dir,
            workbook_path=workbook_path,
            run_summary_path=run_summary_path,
            content_count=len(self._blocks),
            root_comment_count=self._root_comment_count,
            reply_count=self._reply_count,
            request_count=self._request_no,
        )

    def _run_search(self, transport: TikHubHttpTransport, keyword: str) -> None:
        pagination: dict[str, object] | None = None
        for page_no in range(1, self.limits.max_search_pages + 1):
            call = tikhub_runtime.build_search_call(
                platform=self.platform,
                keyword=keyword,
                config=self.search_config,
                state=pagination,
            )
            body, raw_record = self._send(transport, call, keyword=keyword)
            self._requests[-1]["keyword"] = keyword
            items = tikhub_runtime.extract_search_items(self.platform, body)
            for item_index, raw_item in enumerate(items):
                item_locator = f"search.page[{page_no}].items[{item_index}]"
                candidate_id = self._discover_candidate(
                    raw_record=raw_record,
                    item_kind="content",
                    item_locator=item_locator,
                )
                try:
                    content = tikhub_runtime.map_content(
                        platform=self.platform,
                        raw=raw_item,
                        context=tikhub_runtime.mapping_context(
                            provider_request_id=raw_record.request_id,
                            provider_attempt_id=raw_record.attempt_id,
                            raw_artifact_id=raw_record.artifact_id,
                            operation=call.operation,
                            source_type="keyword",
                            source_value=keyword,
                            observed_at=raw_record.observed_at,
                        ),
                        item_locator=item_locator,
                    )
                except Exception as exc:
                    self._record_candidate_failure(
                        candidate_id=candidate_id,
                        raw_record=raw_record,
                        error=exc,
                    )
                    raise
                content_id = content.external_content_id
                self._remember_keyword(content_id, keyword)
                is_new = content_id not in self._seen_contents
                if is_new:
                    self._seen_contents.add(content_id)
                    self.store.append_canonical("contents", content)
                self._ingest_content(content, candidate_id=candidate_id)
                if not is_new:
                    continue
                self._process_content(
                    transport,
                    keyword=keyword,
                    search_content=content,
                    search_raw_locator=(
                        f"{self.store.relative_path(raw_record.path)}#{item_locator}"
                    ),
                )
                if self._content_limit_reached():
                    self._search_stop_reasons[keyword] = "content_target_reached"
                    return

            advance = tikhub_runtime.advance_search(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            if not advance.should_continue:
                self._search_stop_reasons[keyword] = advance.stop_reason or "provider_exhausted"
                return
            pagination = cast(dict[str, object], advance.next_state)
        self._search_stop_reasons[keyword] = "max_search_pages_reached"

    def _process_content(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
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
        decision = self._apply_comment_mode(decision)
        content = search_content
        content_raw_locator = search_raw_locator

        if decision.detail_action == "fetch":
            detail_call = tikhub_runtime.build_detail_call(self.platform, search_content)
            try:
                detail_body, detail_raw = self._send(
                    transport,
                    detail_call,
                    keyword=keyword,
                )
            except (_TikHubHttpStatusError, ProviderTransportFailure) as exc:
                can_collect_from_account_item = (
                    self._continue_after_item_http_error or self.platform == "douyin"
                )
                if can_collect_from_account_item:
                    self._record_content_http_failure(
                        content_id=content_id,
                        stage="detail",
                        error=exc,
                    )
                    fallback_comments: list[UnifiedDataExcelCommentV1] = []
                    fallback_coverage = "unavailable"
                    fallback_decision = self._apply_comment_mode(decision)
                    if self.account_mode and fallback_decision.comment_action not in {
                        "skip",
                        "defer_until_detail",
                    }:
                        fallback_comments, fallback_coverage = self._fetch_comments(
                            transport,
                            keyword=keyword,
                            content=search_content,
                            action=fallback_decision.comment_action,
                            target=(
                                None
                                if self.account_mode and self.comment_mode == "all"
                                else fallback_decision.comment_target
                                or self.limits.max_comments_per_content
                            ),
                        )
                    self._blocks.append(
                        UnifiedDataExcelV1(
                            content=project_canonical_content(
                                search_content,
                                coverage=fallback_coverage,
                                raw_locator=search_raw_locator,
                            ),
                            comments=tuple(fallback_comments),
                        )
                    )
                    return
                raise
            detail_items = tikhub_runtime.extract_detail_items(self.platform, detail_body)
            mapped_details: list[tuple[CanonicalContentV1, str]] = []
            for index, detail_item in enumerate(detail_items):
                if self.platform == "kuaishou":
                    native_id = detail_item.get("photo_id", detail_item.get("photoId"))
                    expected_native = search_content.alternate_ids.get(
                        "provider_photo_id", content_id
                    )
                    if str(native_id) != expected_native:
                        continue
                item_locator = f"detail.items[{index}]"
                candidate_id = self._discover_candidate(
                    raw_record=detail_raw,
                    item_kind="content",
                    item_locator=item_locator,
                )
                try:
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
                            external_content_id=content_id if self.platform == "kuaishou" else None,
                        ),
                        item_locator=item_locator,
                    )
                except Exception as exc:
                    self._record_candidate_failure(
                        candidate_id=candidate_id,
                        raw_record=detail_raw,
                        error=exc,
                    )
                    raise
                if mapped.external_content_id != content_id:
                    # Detail 可能包含其他作品；这些数据不能进入当前作品的输出或写入链。
                    continue
                if self.account_mode or self._strict_full_comment_mode():
                    expected_author = search_content.author
                    actual_author = mapped.author
                    if (
                        expected_author is None
                        or actual_author is None
                        or not expected_author.external_account_id
                        or actual_author.external_account_id != expected_author.external_account_id
                    ):
                        error = ValueError("账号作品 Detail 作者身份不一致或缺失")
                        self._record_candidate_failure(
                            candidate_id=candidate_id, raw_record=detail_raw, error=error
                        )
                        raise error
                self.store.append_canonical("contents", mapped)
                self._ingest_content(mapped, candidate_id=candidate_id)
                mapped_details.append(
                    (
                        mapped,
                        f"{self.store.relative_path(detail_raw.path)}#{item_locator}",
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
            decision = self._apply_comment_mode(decision)

        comments: list[UnifiedDataExcelCommentV1] = []
        coverage = self._coverage_for_skipped_comments(
            decision.comment_action, decision.comment_reason
        )
        if decision.comment_action not in {"skip", "defer_until_detail"}:
            comments, coverage = self._fetch_comments(
                transport,
                keyword=keyword,
                content=content,
                action=decision.comment_action,
                target=(
                    None
                    if self.account_mode and self.comment_mode == "all"
                    else decision.comment_target or self.limits.max_comments_per_content
                ),
            )

        self.state.remember_content(
            self.platform,
            content_id,
            comment_count=content.metrics.comment_count,
        )
        self._blocks.append(
            UnifiedDataExcelV1(
                content=project_canonical_content(
                    content,
                    coverage=coverage,
                    raw_locator=content_raw_locator,
                ),
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
            scheduled_refresh_checkpoint=(self._full_refresh_requested() and not after_detail),
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

    def _apply_comment_mode(self, decision: CollectionDecisionV1) -> CollectionDecisionV1:
        if not self.account_mode or self.comment_mode != "all":
            return decision
        if decision.comment_action == "skip":
            if (
                self._strict_kuaishou_comment_mode()
                and self.include_comments
                and decision.comment_reason == "provider_reported_zero"
            ):
                # 快手全量账号模式会对每条范围内作品同时探测 App/Web；不因作品
                # 列表或详情中的瞬时 0 计数跳过真实评论分页。
                return decision.model_copy(
                    update={
                        "comment_action": "fetch_adaptive",
                        "comment_target": None,
                        "reply_target_per_root": None,
                    }
                )
            # 保留 Provider 明确零值与不可用语义，避免强制请求造成虚假失败。
            return decision
        if not self.include_comments:
            return decision.model_copy(
                update={
                    "comment_action": "skip",
                    "comment_reason": "comments_disabled",
                    "comment_target": None,
                    "reply_target_per_root": None,
                }
            )
        return decision.model_copy(
            update={
                "comment_action": "fetch_adaptive",
                "comment_target": None,
                "reply_target_per_root": None,
            }
        )

    def _policy(self) -> CollectionDecisionPolicyV1:
        return CollectionDecisionPolicyV1(
            comments_enabled=self.include_comments,
            full_fetch_threshold=self.limits.max_comments_per_content,
            sample_target=self.limits.max_comments_per_content,
            reply_target_per_root=self.limits.max_replies_per_root,
            comment_refresh_when_count_unchanged=self._full_refresh_requested(),
        )

    def _full_refresh_requested(self) -> bool:
        # “全部评论”描述的是本次导出，而不是历史增量。即使 state.json 已有
        # 相同作品和评论计数，也必须重新抓详情、一级评论和全部二级回复；否则
        # 新一轮 Excel 只会得到内容块和表头，无法包含历史运行中的评论。
        return self.force_refresh or self._strict_full_comment_mode()

    def _strict_full_comment_mode(self) -> bool:
        return self.account_mode and self.comment_mode == "all"

    def _strict_douyin_comment_mode(self) -> bool:
        return self.platform == "douyin" and self.account_mode and self.comment_mode == "all"

    def _strict_kuaishou_comment_mode(self) -> bool:
        return self.platform == "kuaishou" and self.account_mode and self.comment_mode == "all"

    def _strict_weibo_comment_mode(self) -> bool:
        return self.platform == "weibo" and self.account_mode and self.comment_mode == "all"

    def _strict_bilibili_comment_mode(self) -> bool:
        return self.platform == "bilibili" and self.account_mode and self.comment_mode == "all"

    def _map_root_comment_items(
        self,
        *,
        content_id: str,
        call: tikhub_runtime.TikHubOperationCall,
        raw_record: RawOutputRecord,
        items: tuple[dict[str, Any], ...],
        page_no: int,
        locator_group: str,
    ) -> tuple[
        list[UnifiedDataExcelCommentV1],
        list[CanonicalCommentV1],
        list[str],
    ]:
        rows: list[UnifiedDataExcelCommentV1] = []
        roots: list[CanonicalCommentV1] = []
        page_comment_ids: list[str] = []
        for item_index, raw_item in enumerate(items):
            item_locator = f"{locator_group}.page[{page_no}].items[{item_index}]"
            candidate_id = self._discover_candidate(
                raw_record=raw_record,
                item_kind="comment",
                item_locator=item_locator,
            )
            try:
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
                    item_locator=item_locator,
                    is_root=True,
                )
            except Exception as exc:
                self._record_candidate_failure(
                    candidate_id=candidate_id,
                    raw_record=raw_record,
                    error=exc,
                )
                if self.account_mode and isinstance(exc, (ValueError, TypeError, KeyError)):
                    self._record_account_row_failure(
                        content_id=content_id,
                        raw_record=raw_record,
                        item_locator=item_locator,
                        error=exc,
                    )
                    continue
                raise
            page_comment_ids.append(comment.external_comment_id)
            key = (content_id, comment.external_comment_id)
            is_new = key not in self._seen_comments
            if is_new:
                self._seen_comments.add(key)
                self.store.append_canonical("comments", comment)
            self._ingest_comment(comment, candidate_id=candidate_id)
            if not is_new:
                if self._strict_kuaishou_comment_mode():
                    roots.append(comment)
                continue
            self.state.remember_comment(
                self.platform,
                content_id,
                comment.external_comment_id,
            )
            locator = f"{self.store.relative_path(raw_record.path)}#{item_locator}"
            rows.append(project_canonical_comment(comment, level="一级", raw_locator=locator))
            roots.append(comment)
            self._root_comment_count += 1
        return rows, roots, page_comment_ids

    def _fetch_comments(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        content: CanonicalContentV1,
        action: str,
        target: int | None,
    ) -> tuple[list[UnifiedDataExcelCommentV1], str]:
        content_id = content.external_content_id
        pagination: dict[str, object] | None = None
        mapped_rows: list[UnifiedDataExcelCommentV1] = []
        root_total = 0
        reply_total = 0
        reported_comment_count: int | None = None
        reported_comment_count_l1: int | None = None
        reported_comment_count_requires_fix = False
        provider_exhausted = False
        attempted_cursors: set[int] = {0}
        progressless_pages = 0
        known_comment_ids = (
            self.state.known_comment_ids(self.platform, content_id)
            if action == "fetch_incremental"
            else frozenset()
        )
        page_no = 0
        while (
            self.limits.max_comment_pages_per_content is None
            or self._comment_page_counts.get(content.external_content_id, 0)
            < self.limits.max_comment_pages_per_content
        ):
            page_no += 1
            self._comment_page_counts[content.external_content_id] = (
                self._comment_page_counts.get(content.external_content_id, 0) + 1
            )
            if pagination is not None:
                current_cursor = pagination.get("cursor")
                if isinstance(current_cursor, int) and not isinstance(current_cursor, bool):
                    attempted_cursors.add(current_cursor)
            call = tikhub_runtime.build_comments_call(
                platform=self.platform,
                external_content_id=content_id,
                alternate_ids=content.alternate_ids,
                state=pagination,
            )
            try:
                body, raw_record = self._send(transport, call, keyword=keyword)
            except (_TikHubHttpStatusError, ProviderTransportFailure) as exc:
                if self._continue_after_item_http_error:
                    self._record_content_http_failure(
                        content_id=content_id,
                        stage="comments",
                        error=exc,
                    )
                    expected = (
                        str(content.metrics.comment_count)
                        if content.metrics.comment_count is not None
                        else "unknown"
                    )
                    failure_code = (
                        f"http_{exc.status_code}"
                        if isinstance(exc, _TikHubHttpStatusError)
                        else exc.code
                    )
                    return mapped_rows, f"partial {root_total}/{expected} ({failure_code})"
                if not self._strict_full_comment_mode():
                    raise
                # 严格全量模式会继续使用 Web 接口补采；同时保留此前已映射的
                # App 评论，不能因为后续某一页失败而丢掉整个作品的数据。
                provider_exhausted = False
                break
            items = tikhub_runtime.extract_comment_items(self.platform, body)
            page_comment_count, page_comment_count_l1 = tikhub_runtime.extract_comment_counts(
                self.platform,
                body,
            )
            if _douyin_comment_total_requires_fix(body):
                reported_comment_count_requires_fix = True
            if items:
                reported_comment_count = _maximum_known_count(
                    reported_comment_count,
                    page_comment_count,
                )
                reported_comment_count_l1 = _maximum_known_count(
                    reported_comment_count_l1,
                    page_comment_count_l1,
                )
            page_rows, mapped_roots, page_comment_ids = self._map_root_comment_items(
                content_id=content_id,
                call=call,
                raw_record=raw_record,
                items=items,
                page_no=page_no,
                locator_group=("comments.app_v3" if self.platform == "douyin" else "comments.app"),
            )
            mapped_rows.extend(page_rows)
            root_total += len(page_rows)
            if page_rows:
                progressless_pages = 0
            else:
                progressless_pages += 1

            if self.include_replies:
                for root in mapped_roots:
                    reply_rows = self._fetch_replies(
                        transport,
                        keyword=keyword,
                        content=content,
                        root=root,
                    )
                    mapped_rows.extend(reply_rows)
                    reply_total += len(reply_rows)

            advance = tikhub_runtime.advance_comments(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            expected_comment_count = _maximum_known_count(
                content.metrics.comment_count,
                reported_comment_count,
            )
            if not advance.should_continue:
                stalled = self._strict_douyin_comment_mode() and progressless_pages >= 2
                resume_state = None
                if (
                    self.platform == "douyin"
                    and not self._strict_full_comment_mode()
                    and not stalled
                ):
                    resume_state = _resume_douyin_comment_state(
                        advance,
                        observed_count=root_total + reply_total,
                        expected_count=(
                            expected_comment_count
                            if self._strict_douyin_comment_mode()
                            else reported_comment_count or content.metrics.comment_count
                        ),
                        attempted_cursors=attempted_cursors,
                    )
                if resume_state is not None:
                    pagination = resume_state
                    provider_exhausted = False
                    continue
                provider_exhausted = not stalled and (
                    not self._strict_full_comment_mode()
                    or advance.stop_reason in {"provider_exhausted", "empty_page"}
                )
                break
            if self._strict_douyin_comment_mode() and progressless_pages >= 2:
                provider_exhausted = False
                break
            if action == "fetch_incremental" and known_comment_boundary_reached(
                page_comment_ids, known_comment_ids
            ):
                expected = (
                    str(content.metrics.comment_count)
                    if content.metrics.comment_count is not None
                    else "unknown"
                )
                return mapped_rows, f"partial {root_total}/{expected} (known_comment_reached)"
            if target is not None and root_total >= target:
                break
            pagination = cast(dict[str, object], advance.next_state)

        if self._strict_kuaishou_comment_mode():
            (
                web_rows,
                web_root_total,
                web_reply_total,
                web_reported_comment_count,
                web_exhausted,
            ) = self._fetch_kuaishou_web_comments(
                transport,
                keyword=keyword,
                content=content,
            )
            mapped_rows.extend(web_rows)
            root_total += web_root_total
            reply_total += web_reply_total
            reported_comment_count = _maximum_known_count(
                reported_comment_count,
                web_reported_comment_count,
            )
            expected_comment_count = _maximum_known_count(
                content.metrics.comment_count,
                reported_comment_count,
            )
            sources_exhausted = provider_exhausted and web_exhausted
            observed_comment_count = root_total + reply_total
            comments_complete = sources_exhausted and (
                expected_comment_count is None or observed_comment_count >= expected_comment_count
            )
            if not comments_complete:
                self._partial_content_ids.add(content_id)
                self._comment_coverage_failures.append(
                    {
                        "content_id": content_id,
                        "kind": "comments",
                        "expected": expected_comment_count,
                        "collected": observed_comment_count,
                        "root_collected": root_total,
                        "reply_collected": reply_total,
                        "sources": ["app", "web"],
                        "app_exhausted": provider_exhausted,
                        "web_exhausted": web_exhausted,
                    }
                )
            status = "complete" if content_id not in self._partial_content_ids else "partial"
            expected_text = (
                str(expected_comment_count) if expected_comment_count is not None else "unknown"
            )
            return (
                mapped_rows,
                f"{status} {observed_comment_count}/{expected_text} "
                f"(一级 {root_total}，二级 {reply_total}，App/Web 已合并)",
            )

        if self._strict_douyin_comment_mode():
            expected_comment_count = _maximum_known_count(
                content.metrics.comment_count,
                reported_comment_count,
            )
            observed_comment_count = root_total + reply_total
            comments_complete = provider_exhausted and (
                expected_comment_count is None or observed_comment_count >= expected_comment_count
            )
            provider_count_discrepancy = (
                not comments_complete
                and provider_exhausted
                and expected_comment_count is not None
                and reported_comment_count_requires_fix
            )
            if provider_count_discrepancy:
                # 抖音 App 会用 need_fix_total=true 明确标记 total 不可靠。
                # App、Web 与重叠窗口都已耗尽且每个根评论的回复数均已对齐时，
                # 少于该陈旧 total 的差额不应被误报为采集器失败。
                self._comment_count_discrepancies.append(
                    {
                        "content_id": content_id,
                        "reported_total": expected_comment_count,
                        "accessible_collected": observed_comment_count,
                        "root_collected": root_total,
                        "reply_collected": reply_total,
                        "reason": "provider_total_marked_need_fix",
                        "sources_exhausted": ["app_v3", "web", "web_overlap"],
                    }
                )
                comments_complete = True
            if not comments_complete:
                self._partial_content_ids.add(content_id)
                self._comment_coverage_failures.append(
                    {
                        "content_id": content_id,
                        "kind": "comments",
                        "expected": expected_comment_count,
                        "collected": observed_comment_count,
                        "root_collected": root_total,
                        "reply_collected": reply_total,
                        "sources": ["app_v3", "web"],
                    }
                )
            status = "complete" if content_id not in self._partial_content_ids else "partial"
            expected_text = (
                str(expected_comment_count) if expected_comment_count is not None else "unknown"
            )
            return (
                mapped_rows,
                f"{status} {observed_comment_count}/{expected_text} "
                f"(一级 {root_total}，二级 {reply_total}"
                f"{'，Provider 总数标记需修正' if provider_count_discrepancy else ''})",
            )

        if self._strict_bilibili_comment_mode():
            observed_comment_count = root_total + reply_total
            expected_comment_count = _maximum_known_count(
                content.metrics.comment_count,
                reported_comment_count,
            )
            comments_complete = provider_exhausted and (
                expected_comment_count is None or observed_comment_count >= expected_comment_count
            )
            if not comments_complete and provider_exhausted and expected_comment_count is not None:
                # B站详情的 stat.reply 会包含删除、审核或权限不可见的评论；当
                # 当前评论接口明确 is_end=true 时，已无合法游标可继续请求。保留
                # 差额审计，但将“接口可访问的全部评论”视为完整采集。
                self._comment_count_discrepancies.append(
                    {
                        "content_id": content_id,
                        "reported_total": expected_comment_count,
                        "accessible_collected": observed_comment_count,
                        "root_collected": root_total,
                        "reply_collected": reply_total,
                        "reason": "provider_reported_total_exceeds_accessible_completed_pagination",
                        "sources_exhausted": ["app"],
                    }
                )
                comments_complete = True
            if not comments_complete:
                self._partial_content_ids.add(content_id)
                self._comment_coverage_failures.append(
                    {
                        "content_id": content_id,
                        "kind": "comments",
                        "expected": expected_comment_count,
                        "collected": observed_comment_count,
                        "root_collected": root_total,
                        "reply_collected": reply_total,
                        "sources": ["app"],
                        "app_exhausted": provider_exhausted,
                    }
                )
            status = "complete" if comments_complete else "partial"
            expected_text = (
                str(expected_comment_count) if expected_comment_count is not None else "unknown"
            )
            return (
                mapped_rows,
                f"{status} {observed_comment_count}/{expected_text} "
                f"(一级 {root_total}，二级 {reply_total}，App 已分页结束)",
            )

        observed = root_total + reply_total
        provider_count = (
            reported_comment_count
            if reported_comment_count is not None
            else content.metrics.comment_count
        )
        provider_root_count = reported_comment_count_l1
        if provider_exhausted and provider_count is not None and observed >= provider_count:
            root_coverage = (
                f"一级 {root_total}/{provider_root_count}"
                if provider_root_count is not None
                else f"一级 {root_total}/unknown"
            )
            return mapped_rows, f"complete {observed}/{provider_count} ({root_coverage})"
        if provider_exhausted and provider_count is None:
            root_coverage = (
                f"一级 {root_total}/{provider_root_count}"
                if provider_root_count is not None
                else f"一级 {root_total}/unknown"
            )
            return mapped_rows, f"complete {observed}/unknown ({root_coverage})"
        expected = str(provider_count) if provider_count is not None else "unknown"
        root_expected = str(provider_root_count) if provider_root_count is not None else "unknown"
        return mapped_rows, f"partial {observed}/{expected} (一级 {root_total}/{root_expected})"

    def _fetch_kuaishou_web_comments(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        content: CanonicalContentV1,
    ) -> tuple[list[UnifiedDataExcelCommentV1], int, int, int | None, bool]:
        """遍历快手 Web 一级评论，并与 App 结果按稳定评论 ID 合并。"""

        pagination: dict[str, object] | None = None
        mapped_rows: list[UnifiedDataExcelCommentV1] = []
        root_total = 0
        reply_total = 0
        reported_comment_count: int | None = None
        provider_exhausted = False
        page_no = 0
        while (
            self.limits.max_comment_pages_per_content is None
            or self._comment_page_counts.get(content.external_content_id, 0)
            < self.limits.max_comment_pages_per_content
        ):
            page_no += 1
            self._comment_page_counts[content.external_content_id] = (
                self._comment_page_counts.get(content.external_content_id, 0) + 1
            )
            call = tikhub_runtime.build_kuaishou_web_comments_call(
                external_content_id=content.external_content_id,
                alternate_ids=content.alternate_ids,
                state=pagination,
            )
            try:
                body, raw_record = self._send(transport, call, keyword=keyword)
            except (_TikHubHttpStatusError, ProviderTransportFailure) as exc:
                self._record_content_http_failure(
                    content_id=content.external_content_id, stage="comments", error=exc
                )
                return mapped_rows, root_total, reply_total, reported_comment_count, False
            items = tikhub_runtime.extract_comment_items("kuaishou", body)
            page_reported_count, _ = tikhub_runtime.extract_comment_counts(
                "kuaishou",
                body,
            )
            if items:
                reported_comment_count = _maximum_known_count(
                    reported_comment_count,
                    page_reported_count,
                )
            page_rows, mapped_roots, _ = self._map_root_comment_items(
                content_id=content.external_content_id,
                call=call,
                raw_record=raw_record,
                items=items,
                page_no=page_no,
                locator_group="comments.web",
            )
            mapped_rows.extend(page_rows)
            root_total += len(page_rows)
            if self.include_replies:
                for root in mapped_roots:
                    reply_rows = self._fetch_replies(
                        transport,
                        keyword=keyword,
                        content=content,
                        root=root,
                    )
                    mapped_rows.extend(reply_rows)
                    reply_total += len(reply_rows)

            advance = tikhub_runtime.advance_comments(
                platform="kuaishou",
                state=pagination,
                body=body,
            )
            if not advance.should_continue:
                provider_exhausted = (
                    not self._strict_full_comment_mode()
                    or advance.stop_reason in {"provider_exhausted", "empty_page"}
                )
                break
            pagination = cast(dict[str, object], advance.next_state)
        return (
            mapped_rows,
            root_total,
            reply_total,
            reported_comment_count,
            provider_exhausted,
        )

    def _fetch_replies(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        content: CanonicalContentV1,
        root: CanonicalCommentV1,
        fetch_all: bool = False,
    ) -> list[UnifiedDataExcelCommentV1]:
        strict_douyin = self._strict_douyin_comment_mode()
        strict_kuaishou = self._strict_kuaishou_comment_mode()
        strict_full = self._strict_full_comment_mode()
        page_key = (content.external_content_id, root.external_comment_id)
        if strict_kuaishou and page_key in self._reply_expansion_counts:
            previous_count = self._reply_expansion_counts[page_key]
            incoming_count = root.metrics.reply_count
            if incoming_count is None and (previous_count is None or previous_count > 0):
                return []
            if (
                incoming_count is not None
                and previous_count is not None
                and incoming_count <= previous_count
            ):
                return []
        if strict_kuaishou:
            self._reply_expansion_counts[page_key] = root.metrics.reply_count
        full_fetch_requested = strict_full or fetch_all
        if full_fetch_requested:
            if not self.include_replies or not self.capability.operation("sub_comments"):
                return []
            if root.metrics.reply_count == 0:
                return []
            target: int | None = None
        else:
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

        app_rows, app_count, app_reported, app_exhausted = self._fetch_reply_pages(
            transport,
            keyword=keyword,
            content=content,
            root=root,
            target=target,
            use_web=False,
            already_collected=0,
        )
        mapped_rows = list(app_rows)
        mapped_count = app_count
        expected_replies = _maximum_known_count(root.metrics.reply_count, app_reported)
        provider_exhausted = app_exhausted

        should_fetch_web = strict_kuaishou
        if should_fetch_web:
            web_rows, web_count, web_reported, web_exhausted = self._fetch_reply_pages(
                transport,
                keyword=keyword,
                content=content,
                root=root,
                target=None,
                use_web=True,
                already_collected=mapped_count,
            )
            mapped_rows.extend(web_rows)
            mapped_count += web_count
            expected_replies = _maximum_known_count(expected_replies, web_reported)
            provider_exhausted = app_exhausted and web_exhausted

        observed_count = len(self._reply_ids_by_root.get(page_key, set()))
        if strict_kuaishou:
            self._reply_expansion_counts[page_key] = (
                max(expected_replies or 0, observed_count)
                if expected_replies is not None or observed_count
                else None
            )
        replies_complete = provider_exhausted and (
            expected_replies is None or observed_count >= expected_replies
        )
        if strict_full and not replies_complete:
            self._partial_content_ids.add(content.external_content_id)
            self._comment_coverage_failures.append(
                {
                    "content_id": content.external_content_id,
                    "kind": "replies",
                    "root_comment_id": root.external_comment_id,
                    "expected": expected_replies,
                    "collected": observed_count,
                    "sources": (
                        ["app_v3"]
                        if strict_douyin
                        else ["app", "web"]
                        if strict_kuaishou
                        else ["app"]
                    ),
                    "app_exhausted": app_exhausted,
                    "web_exhausted": (web_exhausted if should_fetch_web else None),
                }
            )
        return mapped_rows

    def _fetch_reply_pages(
        self,
        transport: TikHubHttpTransport,
        *,
        keyword: str,
        content: CanonicalContentV1,
        root: CanonicalCommentV1,
        target: int | None,
        use_web: bool,
        already_collected: int,
    ) -> tuple[list[UnifiedDataExcelCommentV1], int, int | None, bool]:
        pagination: dict[str, object] | None = None
        mapped_rows: list[UnifiedDataExcelCommentV1] = []
        mapped_count = 0
        reported_count: int | None = None
        provider_exhausted = False
        attempted_cursors: set[int] = {0}
        progressless_pages = 0
        page_no = 0
        while (
            self.limits.max_reply_pages_per_root is None
            or self._reply_page_counts.get(
                (content.external_content_id, root.external_comment_id), 0
            )
            < self.limits.max_reply_pages_per_root
        ):
            page_no += 1
            page_key = (content.external_content_id, root.external_comment_id)
            self._reply_page_counts[page_key] = self._reply_page_counts.get(page_key, 0) + 1
            if pagination is not None:
                current_cursor = pagination.get("cursor")
                if isinstance(current_cursor, int) and not isinstance(current_cursor, bool):
                    attempted_cursors.add(current_cursor)
            if use_web:
                call = tikhub_runtime.build_kuaishou_web_sub_comments_call(
                    external_content_id=content.external_content_id,
                    root_comment_id=root.external_comment_id,
                    alternate_ids=content.alternate_ids,
                    state=pagination,
                )
                locator_group = "replies.web"
            else:
                call = tikhub_runtime.build_sub_comments_call(
                    platform=self.platform,
                    external_content_id=content.external_content_id,
                    root_comment_id=root.external_comment_id,
                    alternate_ids=content.alternate_ids,
                    state=pagination,
                )
                locator_group = "replies.app_v3" if self.platform == "douyin" else "replies.app"
            try:
                body, raw_record = self._send(transport, call, keyword=keyword)
            except (_TikHubHttpStatusError, ProviderTransportFailure) as exc:
                if self._continue_after_item_http_error:
                    self._record_content_http_failure(
                        content_id=content.external_content_id,
                        stage="replies",
                        error=exc,
                    )
                    return mapped_rows, mapped_count, reported_count, False
                if not self._strict_full_comment_mode():
                    raise
                # 保留此前已采回复；快手显式双源由调用方分别执行。
                return mapped_rows, mapped_count, reported_count, False
            items = tikhub_runtime.extract_sub_comment_items(self.platform, body)
            if self.platform in {"douyin", "kuaishou"} and items:
                page_reported_count, _ = tikhub_runtime.extract_comment_counts(
                    self.platform,
                    body,
                )
                reported_count = _maximum_known_count(reported_count, page_reported_count)
            page_new_count = 0
            for item_index, raw_item in enumerate(items):
                item_locator = f"{locator_group}.page[{page_no}].items[{item_index}]"
                candidate_id = self._discover_candidate(
                    raw_record=raw_record,
                    item_kind="comment",
                    item_locator=item_locator,
                )
                try:
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
                        item_locator=item_locator,
                        is_root=False,
                    )
                except Exception as exc:
                    self._record_candidate_failure(
                        candidate_id=candidate_id,
                        raw_record=raw_record,
                        error=exc,
                    )
                    if self.account_mode and isinstance(exc, (ValueError, TypeError, KeyError)):
                        self._record_account_row_failure(
                            content_id=content.external_content_id,
                            raw_record=raw_record,
                            item_locator=item_locator,
                            error=exc,
                        )
                        continue
                    raise
                self._reply_ids_by_root.setdefault(
                    (content.external_content_id, root.external_comment_id), set()
                ).add(comment.external_comment_id)
                key = (content.external_content_id, comment.external_comment_id)
                is_new = key not in self._seen_comments
                if is_new:
                    self._seen_comments.add(key)
                    self.store.append_canonical("comments", comment)
                self._ingest_comment(comment, candidate_id=candidate_id)
                if not is_new:
                    continue
                self.state.remember_comment(
                    self.platform,
                    content.external_content_id,
                    comment.external_comment_id,
                )
                locator = f"{self.store.relative_path(raw_record.path)}#{item_locator}"
                mapped_rows.append(
                    project_canonical_comment(comment, level="二级", raw_locator=locator)
                )
                mapped_count += 1
                page_new_count += 1
                self._reply_count += 1
            if page_new_count:
                progressless_pages = 0
            else:
                progressless_pages += 1

            advance = tikhub_runtime.advance_sub_comments(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            if not advance.should_continue:
                resume_state = None
                stalled = self.platform == "douyin" and progressless_pages >= 2
                if (
                    self.platform == "douyin"
                    and not self._strict_full_comment_mode()
                    and not use_web
                    and not stalled
                ):
                    resume_state = _resume_douyin_comment_state(
                        advance,
                        observed_count=already_collected + mapped_count,
                        expected_count=_maximum_known_count(
                            root.metrics.reply_count,
                            reported_count,
                        ),
                        attempted_cursors=attempted_cursors,
                    )
                if resume_state is not None:
                    pagination = resume_state
                    provider_exhausted = False
                    continue
                provider_exhausted = not stalled and (
                    not self._strict_full_comment_mode()
                    or advance.stop_reason in {"provider_exhausted", "empty_page"}
                )
                break
            if self.platform == "douyin" and progressless_pages >= 2:
                provider_exhausted = False
                break
            if target is not None and mapped_count >= target:
                break
            pagination = cast(dict[str, object], advance.next_state)
        return mapped_rows, mapped_count, reported_count, provider_exhausted

    def _send(
        self,
        transport: TikHubHttpTransport,
        call: tikhub_runtime.TikHubOperationCall,
        *,
        keyword: str,
    ) -> tuple[dict[str, Any], RawOutputRecord]:
        self._request_no += 1
        if self._database is None:
            try:
                response = transport.send(call.transport_request(self.provider_config.api_key))
            except ProviderTransportFailure as exc:
                self._requests.append(
                    {
                        "request_no": self._request_no,
                        "business_operation": call.business_operation,
                        "operation": call.operation,
                        "method": call.method,
                        "path": call.path,
                        "delivery": exc.delivery,
                        "error_code": exc.code,
                        "billing_status": exc.billing.status,
                    }
                )
                raise
            raw_record = self.store.save_raw(
                operation=call.operation,
                body=response.body,
                request_no=self._request_no,
                status_code=response.status_code,
                external_request_id=response.external_request_id,
            )
        else:
            mirrored_record: RawOutputRecord | None = None

            def mirror_response(response: object) -> None:
                nonlocal mirrored_record
                status_code = getattr(response, "status_code", None)
                external_request_id = getattr(response, "external_request_id", None)
                body = getattr(response, "body", None)
                mirrored_record = self.store.save_raw(
                    operation=call.operation,
                    body=body,
                    request_no=self._request_no,
                    status_code=status_code if isinstance(status_code, int) else None,
                    external_request_id=(
                        external_request_id if isinstance(external_request_id, str) else None
                    ),
                )

            dispatch = self._database.dispatch(
                keyword=keyword,
                call=call,
                transport=transport,
                mirror_response=mirror_response,
            )
            response = dispatch.response
            if mirrored_record is None:
                raise RuntimeError("TikHub 数据库模式没有生成本地 Raw 镜像")
            raw_record = RawOutputRecord(
                artifact_id=dispatch.raw_artifact_id,
                request_id=str(dispatch.provider_request_id),
                attempt_id=str(dispatch.provider_attempt_id),
                operation=call.operation,
                request_no=self._request_no,
                path=mirrored_record.path,
                observed_at=dispatch.observed_at,
                status_code=response.status_code,
                external_request_id=response.external_request_id,
            )

        raw_file = self.store.relative_path(raw_record.path)
        self._requests.append(
            {
                "request_no": self._request_no,
                "business_operation": call.business_operation,
                "operation": call.operation,
                "method": call.method,
                "path": call.path,
                "status_code": response.status_code,
                "external_request_id": response.external_request_id,
                "raw_file": raw_file,
            }
        )
        status_code = response.status_code
        if status_code is not None and status_code >= 400:
            message = f"TikHub {self.platform} {call.operation} 返回 HTTP {status_code}"
            raise _TikHubHttpStatusError(
                message,
                status_code=status_code,
                operation=call.operation,
                external_request_id=response.external_request_id,
                raw_file=raw_file,
            )
        if not isinstance(response.body, dict):
            raise RuntimeError(f"TikHub {self.platform} {call.operation} 返回 JSON 顶层不是对象")
        return cast(dict[str, Any], response.body), raw_record

    def _record_content_http_failure(
        self,
        *,
        content_id: str,
        stage: Literal["detail", "comments", "replies"],
        error: _TikHubHttpStatusError | ProviderTransportFailure,
    ) -> None:
        """记录已落盘的内容级 HTTP 失败，供容错运行保留安全诊断信息。"""
        if self.account_mode:
            self._partial_content_ids.add(content_id)
        if isinstance(error, ProviderTransportFailure):
            self._content_failures.append(
                {
                    "external_content_id": content_id,
                    "stage": stage,
                    "error_type": type(error).__name__,
                    "delivery": error.delivery,
                    "code": error.code,
                    "billing_status": error.billing.status,
                }
            )
        else:
            self._content_failures.append(
                {
                    "external_content_id": content_id,
                    "stage": stage,
                    "operation": error.operation,
                    "status_code": error.status_code,
                    "external_request_id": error.external_request_id,
                    "raw_file": error.raw_file,
                }
            )

    def _record_account_row_failure(
        self,
        *,
        content_id: str,
        raw_record: RawOutputRecord,
        item_locator: str,
        error: Exception,
    ) -> None:
        """保留单行映射错误与原始来源，其他可映射评论继续进入文件。"""
        self._partial_content_ids.add(content_id)
        self._comment_coverage_failures.append(
            {
                "content_id": content_id,
                "kind": "mapping",
                "item_locator": item_locator,
                "error_type": type(error).__name__,
                "raw_file": self.store.relative_path(raw_record.path),
            }
        )

    def _discover_candidate(
        self,
        *,
        raw_record: RawOutputRecord,
        item_kind: Literal["content", "comment"],
        item_locator: str,
    ) -> UUID | None:
        if self._database is None:
            return None
        try:
            attempt_id = UUID(raw_record.attempt_id)
        except ValueError as exc:
            raise RuntimeError("TikHub 数据库模式 Attempt ID 不是 UUID") from exc
        return self._database.discover_candidate(
            provider_attempt_id=attempt_id,
            raw_artifact_id=raw_record.artifact_id,
            item_kind=item_kind,
            item_locator=item_locator,
            discovered_at=raw_record.observed_at,
        )

    def _record_candidate_failure(
        self,
        *,
        candidate_id: UUID | None,
        raw_record: RawOutputRecord,
        error: Exception,
    ) -> None:
        if self._database is None or candidate_id is None:
            return
        try:
            attempt_id = UUID(raw_record.attempt_id)
        except ValueError as exc:
            raise RuntimeError("TikHub 数据库模式 Attempt ID 不是 UUID") from exc
        self._database.record_candidate_failure(
            candidate_id=candidate_id,
            provider_attempt_id=attempt_id,
            error_code=type(error).__name__,
        )

    def _ingest_content(
        self,
        content: CanonicalContentV1,
        *,
        candidate_id: UUID | None,
    ) -> None:
        if self._database is None:
            return
        if candidate_id is None:
            raise RuntimeError("TikHub 数据库模式 Content 缺少 Candidate")
        self._database.ingest_content(content, candidate_id=candidate_id)

    def _ingest_comment(
        self,
        comment: CanonicalCommentV1,
        *,
        candidate_id: UUID | None,
    ) -> None:
        if self._database is None:
            return
        if candidate_id is None:
            raise RuntimeError("TikHub 数据库模式 Comment 缺少 Candidate")
        self._database.ingest_comment(comment, candidate_id=candidate_id)

    def _remember_keyword(self, content_id: str, keyword: str) -> None:
        matched = self._matched_keywords.setdefault(content_id, [])
        if keyword not in matched:
            matched.append(keyword)

    def _blocks_with_keywords(self) -> tuple[UnifiedDataExcelV1, ...]:
        return tuple(
            block.model_copy(
                update={
                    "content": block.content.model_copy(
                        update={
                            "matched_keywords": tuple(
                                self._matched_keywords.get(
                                    block.content.external_content_id,
                                    (),
                                )
                            )
                        }
                    )
                }
            )
            for block in self._blocks
        )

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

    def _run_summary(self, error: Exception | None) -> dict[str, object]:
        status = "failed" if error is not None else "completed"
        if error is None and self._content_failures:
            status = "completed_with_errors"
        account_failures = sum(
            result.get("status") != "completed" for result in self._account_results
        )
        if error is None and self.account_mode and account_failures:
            status = (
                "partial_success"
                if self._blocks
                or any(result.get("status") == "partial" for result in self._account_results)
                else "failed"
            )
        if self.account_mode:
            self._partial_content_ids.update(
                block.content.external_content_id
                for block in self._blocks
                if block.content.coverage
                and block.content.coverage.startswith(("partial", "unavailable"))
            )
        if error is None and self._partial_content_ids and status != "failed":
            status = "partial_success"
        return {
            "schema_version": "tikhub-test-run.v1",
            "operations": self.platform,
            "mode": (f"{self.platform}_accounts" if self.account_mode else "keyword_search"),
            "keyword": self.keywords[0] if len(self.keywords) == 1 else None,
            "keywords": list(self.keywords),
            "matched_keywords": self._matched_keywords,
            "write_to_database": self.write_to_database,
            "provider_config_id": (
                str(self.provider_config_id) if self.provider_config_id is not None else None
            ),
            "status": status,
            "request_count": self._request_no,
            "content_count": len(self._blocks),
            "root_comment_count": self._root_comment_count,
            "reply_count": self._reply_count,
            "search_stop_reasons": self._search_stop_reasons,
            "requests": self._requests,
            "content_failures": self._content_failures,
            "comment_coverage_failures": self._comment_coverage_failures,
            "comment_count_discrepancies": self._comment_count_discrepancies,
            "partial_content_count": len(self._partial_content_ids),
            "comment_mode": self.comment_mode,
            "account_date_range": (
                {
                    "start": self.start_date.isoformat(),
                    "end": self.end_date.isoformat(),
                    "timezone": "Asia/Shanghai",
                    "inclusive": True,
                }
                if self.account_mode and self.start_date is not None and self.end_date is not None
                else None
            ),
            "accounts_total": len(self._account_results) if self.account_mode else None,
            "accounts_success": (
                sum(result.get("status") == "completed" for result in self._account_results)
                if self.account_mode
                else None
            ),
            "accounts_failed": account_failures if self.account_mode else None,
            "accounts": self._account_results if self.account_mode else [],
            "error_type": type(error).__name__ if error is not None else None,
            "error_summary": str(error) if error is not None else None,
        }


def run_platform(
    *,
    platform: tikhub_runtime.TikHubPlatform,
    keyword: str | None = None,
    keywords: str | Sequence[str] | None = None,
    search_config: dict[str, object] | None = None,
    env_file: str | Path | None = None,
    output_root: str | Path | None = None,
    run_id: str | None = None,
    max_search_pages: int = 20,
    max_contents: int | None = None,
    max_comments_per_content: int = 100,
    max_comment_pages_per_content: int | None = None,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int | None = None,
    include_comments: bool = True,
    include_replies: bool = True,
    force_refresh: bool = False,
    write_to_database: bool = False,
    provider_config_id: UUID | None = None,
) -> TikHubTestRunResult:
    """执行一个平台的人工调试；数据库写入必须显式 opt-in。"""
    normalized_keywords = _normalize_keywords(keyword=keyword, keywords=keywords)
    config = TikHubTestConfig.load(env_file)
    root = Path(output_root) if output_root is not None else _DEFAULT_OUTPUT_ROOT
    actual_run_id = run_id or default_run_id()
    actual_search_config = search_config or {}
    return _TikHubDebugRunner(
        platform=platform,
        keywords=normalized_keywords,
        search_config=actual_search_config,
        provider_config=config,
        output_root=root,
        run_id=actual_run_id,
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
        write_to_database=write_to_database,
        provider_config_id=provider_config_id,
    ).run()


def _resume_douyin_comment_state(
    advance: tikhub_runtime.TikHubPageAdvance,
    *,
    observed_count: int,
    expected_count: int | None,
    attempted_cursors: set[int],
) -> dict[str, object] | None:
    """在 TikHub 提前宣称结束但评论总数未对齐时恢复下一页探测。"""

    if expected_count is None or observed_count >= expected_count:
        return None
    resume_state = advance.resume_state
    if resume_state is None:
        return None
    candidate = resume_state.get("cursor")
    if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate < 0:
        return None
    if candidate in attempted_cursors:
        return None
    attempted_cursors.add(candidate)
    return dict(resume_state)


def _maximum_known_count(*values: int | None) -> int | None:
    known = [value for value in values if value is not None]
    return max(known) if known else None


def _douyin_comment_total_requires_fix(body: object) -> bool:
    """识别抖音响应明确声明当前评论 total 需要修正的标志。"""
    if not isinstance(body, Mapping):
        return False
    data = body.get("data")
    if not isinstance(data, Mapping):
        return False
    value = data.get("need_fix_total")
    return value is True or value == 1 or value == "1" or value == "true"


def _normalize_keywords(
    *,
    keyword: str | None,
    keywords: str | Sequence[str] | None,
) -> tuple[str, ...]:
    if keyword is not None and keywords is not None:
        raise ValueError("keyword 与 keywords 不能同时传入")
    if keyword is not None:
        raw_values: tuple[str, ...] = (keyword,)
    elif keywords is None:
        raw_values = ("爱玛",)
    elif isinstance(keywords, str):
        raw_values = (keywords,)
    else:
        raw_values = tuple(keywords)

    normalized: list[str] = []
    for value in raw_values:
        if not isinstance(value, str):
            raise ValueError("keywords 只能包含字符串")
        stripped = value.strip()
        if not stripped:
            raise ValueError("keywords 不能包含空字符串")
        if stripped not in normalized:
            normalized.append(stripped)
    if not normalized:
        raise ValueError("keywords 至少包含一个关键词")
    return tuple(normalized)


__all__ = ["TikHubTestRunResult", "run_platform"]
