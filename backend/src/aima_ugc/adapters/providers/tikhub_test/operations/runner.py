"""复用生产 TikHub Runtime 的五平台人工调试执行器。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import UUID

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
from aima_ugc.platform.export import (
    export_unified_data_excel,
    project_canonical_comment,
    project_canonical_content,
)

if TYPE_CHECKING:
    from aima_ugc.bootstrap.tikhub_test_database import TikHubDebugDatabaseSession

_DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "output"
_CAPABILITIES = {item.platform: item for item in TIKHUB_PLATFORM_CAPABILITIES}


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
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.operation = operation
        self.external_request_id = external_request_id
        self.raw_file = raw_file


class _TikHubDebugRunner:
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
            workbook_path = export_unified_data_excel(
                self._blocks_with_keywords(),
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
            except _TikHubHttpStatusError as exc:
                if (
                    self.platform == "douyin"
                    and detail_call.operation == "fetch_one_video_v3"
                    and exc.status_code == 400
                ):
                    self._content_failures.append(
                        {
                            "external_content_id": content_id,
                            "stage": "detail",
                            "operation": exc.operation,
                            "status_code": exc.status_code,
                            "external_request_id": exc.external_request_id,
                            "raw_file": exc.raw_file,
                        }
                    )
                    self._blocks.append(
                        UnifiedDataExcelV1(
                            content=project_canonical_content(
                                search_content,
                                coverage="unavailable",
                                raw_locator=search_raw_locator,
                            ),
                            comments=(),
                        )
                    )
                    return
                raise
            detail_items = tikhub_runtime.extract_detail_items(self.platform, detail_body)
            mapped_details: list[tuple[CanonicalContentV1, str]] = []
            for index, detail_item in enumerate(detail_items):
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
                target=decision.comment_target or self.limits.max_comments_per_content,
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
        keyword: str,
        content: CanonicalContentV1,
        action: str,
        target: int | None,
    ) -> tuple[list[UnifiedDataExcelCommentV1], str]:
        content_id = content.external_content_id
        pagination: dict[str, object] | None = None
        mapped_rows: list[UnifiedDataExcelCommentV1] = []
        root_total = 0
        provider_exhausted = False
        known_comment_ids = (
            self.state.known_comment_ids(self.platform, content_id)
            if action == "fetch_incremental"
            else frozenset()
        )
        for page_no in range(1, self.limits.max_comment_pages_per_content + 1):
            call = tikhub_runtime.build_comments_call(
                platform=self.platform,
                external_content_id=content_id,
                state=pagination,
            )
            body, raw_record = self._send(transport, call, keyword=keyword)
            items = tikhub_runtime.extract_comment_items(self.platform, body)
            mapped_roots: list[CanonicalCommentV1] = []
            page_comment_ids: list[str] = []
            for item_index, raw_item in enumerate(items):
                item_locator = f"comments.page[{page_no}].items[{item_index}]"
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
                    raise
                page_comment_ids.append(comment.external_comment_id)
                key = (content_id, comment.external_comment_id)
                is_new = key not in self._seen_comments
                if is_new:
                    self._seen_comments.add(key)
                    self.store.append_canonical("comments", comment)
                self._ingest_comment(comment, candidate_id=candidate_id)
                if not is_new:
                    continue
                self.state.remember_comment(
                    self.platform,
                    content_id,
                    comment.external_comment_id,
                )
                locator = f"{self.store.relative_path(raw_record.path)}#{item_locator}"
                mapped_rows.append(
                    project_canonical_comment(comment, level="一级", raw_locator=locator)
                )
                mapped_roots.append(comment)
                root_total += 1
                self._root_comment_count += 1

            if self.include_replies:
                for root in mapped_roots:
                    mapped_rows.extend(
                        self._fetch_replies(
                            transport,
                            keyword=keyword,
                            content=content,
                            root=root,
                        )
                    )

            advance = tikhub_runtime.advance_comments(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            if not advance.should_continue:
                provider_exhausted = True
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
        *,
        keyword: str,
        content: CanonicalContentV1,
        root: CanonicalCommentV1,
        fetch_all: bool = False,
    ) -> list[UnifiedDataExcelCommentV1]:
        reply_decision = self.decision_service.decide_reply(
            ReplyDecisionRequestV1(
                reply_count=root.metrics.reply_count,
                policy=self._policy(),
                capability=self.capability,
            )
        )
        if reply_decision.action == "skip":
            return []
        target = (
            None
            if fetch_all
            else (reply_decision.target or self.limits.max_replies_per_root)
        )
        pagination: dict[str, object] | None = None
        mapped_rows: list[UnifiedDataExcelCommentV1] = []
        mapped_count = 0
        for page_no in range(1, self.limits.max_reply_pages_per_root + 1):
            call = tikhub_runtime.build_sub_comments_call(
                platform=self.platform,
                external_content_id=content.external_content_id,
                root_comment_id=root.external_comment_id,
                state=pagination,
            )
            body, raw_record = self._send(transport, call, keyword=keyword)
            items = tikhub_runtime.extract_sub_comment_items(self.platform, body)
            for item_index, raw_item in enumerate(items):
                item_locator = f"replies.page[{page_no}].items[{item_index}]"
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
                    raise
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
                self._reply_count += 1

            advance = tikhub_runtime.advance_sub_comments(
                platform=self.platform,
                state=pagination,
                body=body,
            )
            if not advance.should_continue or (
                target is not None and mapped_count >= target
            ):
                break
            pagination = cast(dict[str, object], advance.next_state)
        return mapped_rows

    def _send(
        self,
        transport: TikHubHttpTransport,
        call: tikhub_runtime.TikHubOperationCall,
        *,
        keyword: str,
    ) -> tuple[dict[str, Any], RawOutputRecord]:
        self._request_no += 1
        if self._database is None:
            response = transport.send(call.transport_request(self.provider_config.api_key))
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
            if (
                call.platform == "douyin"
                and call.operation == "fetch_one_video_v3"
                and status_code == 400
            ):
                raise _TikHubHttpStatusError(
                    message,
                    status_code=status_code,
                    operation=call.operation,
                    external_request_id=response.external_request_id,
                    raw_file=raw_file,
                )
            raise RuntimeError(message)
        if not isinstance(response.body, dict):
            raise RuntimeError(f"TikHub {self.platform} {call.operation} 返回 JSON 顶层不是对象")
        return cast(dict[str, Any], response.body), raw_record

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
        return {
            "schema_version": "tikhub-test-run.v1",
            "operations": self.platform,
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
    max_comment_pages_per_content: int = 20,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int = 10,
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
