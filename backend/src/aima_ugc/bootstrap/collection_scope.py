"""Stage 7 TikHub Collection Scope 的生产执行组合层。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.collection_actions import (
    CollectionContentActionRecord,
    PostgresCollectionContentActionRepository,
)
from aima_ugc.adapters.persistence.postgres.collection_content import (
    PostgresCollectionContentStateReader,
    PostgresFencedCollectionIngestionWriter,
)
from aima_ugc.adapters.persistence.postgres.collection_provider_execution import (
    CollectionScopeExecutionCounts,
    PostgresFencedProviderAttemptPreparer,
)
from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
    PostgresCollectionRunExecutionGateway,
)
from aima_ugc.adapters.persistence.postgres.provider_dispatch import (
    PostgresProviderDispatchPersistence,
    PostgresProviderRecoveryPersistence,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.tikhub.capabilities import TIKHUB_PLATFORM_CAPABILITIES
from aima_ugc.adapters.providers.tikhub.pricing import load_tikhub_pricing
from aima_ugc.adapters.providers.tikhub.runtime import (
    TikHubOperationCall,
    TikHubPlatform,
    advance_comments,
    advance_search,
    advance_sub_comments,
    build_comments_call,
    build_detail_call,
    build_search_call,
    build_sub_comments_call,
    extract_comment_items,
    extract_detail_items,
    extract_search_items,
    extract_sub_comment_items,
    map_comment,
    map_content,
    mapping_context,
)
from aima_ugc.contracts.analysis import RelevanceSnapshotV1
from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.contracts.collection import (
    CollectionDecisionPolicyV1,
    CollectionDecisionRequestV1,
    ContentObservationV1,
    PreviousContentStateV1,
    ProviderPlatformCapabilityV1,
    ReplyDecisionRequestV1,
)
from aima_ugc.contracts.provider import JsonObject, ProviderRequestV1
from aima_ugc.modules.analysis import RelevanceKeyword, RelevanceService
from aima_ugc.modules.collection.collection_run_executor import (
    CollectionScopeExecutionResult,
    CollectionScopeRetryableError,
    CollectionScopeTerminalStatus,
)
from aima_ugc.modules.collection.decision import (
    CollectionDecisionService,
    known_comment_boundary_reached,
)
from aima_ugc.modules.collection.execution import CollectionRunRecord, CollectionScopeRecord
from aima_ugc.modules.collection.execution_limits import (
    MAX_COMMENT_PAGES,
    MAX_SEARCH_PAGES,
    MAX_SUB_COMMENT_PAGES,
)
from aima_ugc.modules.collection.provider_dispatch import ProviderDispatchService
from aima_ugc.modules.collection.provider_persistence import PreparedProviderAttempt
from aima_ugc.modules.collection.provider_recovery import ProviderAttemptReconciler
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransport,
    RawArtifactService,
    raw_storage_key,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.storage import ArtifactRecord

_COMMENT_FETCH_ACTIONS = {
    "fetch_adaptive",
    "fetch_incremental",
    "refresh_controlled",
    "probe_first_page",
}
_REPLY_FETCH_ACTIONS = {"fetch_target", "probe_first_page"}
_RETRYABLE_HTTP_STATUSES = {408, 425, 429}
_UNAVAILABLE_COMMENT_REASONS = {
    "comments_operation_unavailable",
    "comments_unavailable",
}
_PROVIDER_TERMINAL_STOP_REASONS = {"provider_exhausted", "empty_page"}
_EXPECTED_PARTIAL_STOP_REASONS = {
    "known_comment_reached",
    "probe_first_page",
    "target_reached",
}
_TECHNICAL_PARTIAL_STOP_REASONS = {
    "page_limit",
    "pagination_not_advanced",
    "cursor_unavailable",
    "response_data_unavailable",
    "items_unavailable",
    "duplicate_page",
}


@dataclass(frozen=True, slots=True)
class _PlatformRuntimeConfig:
    provider_config_id: UUID
    config: dict[str, object]
    provider: str | None = None
    base_url: str | None = None
    secret_ref: str | None = None


@dataclass(frozen=True, slots=True)
class _ExecutedCall:
    request_id: UUID
    attempt_id: UUID
    raw_artifact_id: UUID
    observed_at: datetime
    body: dict[str, object]


@dataclass(frozen=True, slots=True)
class _DetailCandidate:
    content: CanonicalContentV1
    candidate_id: UUID


@dataclass(frozen=True, slots=True)
class _CommentFetchOutcome:
    completed: bool
    technical_partial: bool = False


@dataclass(frozen=True, slots=True)
class _ReplyFetchOutcome:
    reply_ids: frozenset[str]
    completed: bool
    technical_partial: bool = False


class _ProviderCallFailed(RuntimeError):
    """一次 Provider 调用已有持久化失败事实，交给 Scope 决定是否 Job retry。"""

    def __init__(self, *, error_code: str, retryable: bool) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.retryable = retryable


@dataclass(slots=True)
class _ScopeStats:
    requested_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    search_pages: int = 0
    search_items: int = 0
    detail_requests: int = 0
    comment_requests: int = 0
    sub_comment_requests: int = 0
    content_count: int = 0
    comment_count: int = 0
    technical_partial_results: int = 0
    filtered_content_count: int = 0

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> _ScopeStats:
        return cls(
            requested_count=_payload_int(payload, "requested_count"),
            succeeded_count=_payload_int(payload, "succeeded_count"),
            failed_count=_payload_int(payload, "failed_count"),
            search_pages=_payload_int(payload, "search_pages"),
            search_items=_payload_int(payload, "search_items"),
            detail_requests=_payload_int(payload, "detail_requests"),
            comment_requests=_payload_int(payload, "comment_requests"),
            sub_comment_requests=_payload_int(payload, "sub_comment_requests"),
            content_count=_payload_int(payload, "content_count"),
            comment_count=_payload_int(payload, "comment_count"),
            technical_partial_results=_payload_int(
                payload,
                "technical_partial_results",
            ),
            filtered_content_count=_payload_int(payload, "filtered_content_count"),
        )

    def sync_counts(self, counts: CollectionScopeExecutionCounts) -> None:
        self.requested_count = counts.requested_count
        self.succeeded_count = counts.succeeded_count
        self.failed_count = counts.failed_count
        self.content_count = counts.content_count
        self.comment_count = counts.comment_count

    def payload(self) -> dict[str, object]:
        return {
            "requested_count": self.requested_count,
            "succeeded_count": self.succeeded_count,
            "failed_count": self.failed_count,
            "content_count": self.content_count,
            "comment_count": self.comment_count,
            "search_pages": self.search_pages,
            "search_items": self.search_items,
            "detail_requests": self.detail_requests,
            "comment_requests": self.comment_requests,
            "sub_comment_requests": self.sub_comment_requests,
            "technical_partial_results": self.technical_partial_results,
            "filtered_content_count": self.filtered_content_count,
            "provider_requests": self.requested_count,
        }


class TikHubCollectionScopeExecutor:
    """复用既有 TikHub/Raw/Decision/Ingestion 实现执行一个关键词发现 Scope。"""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        raw_artifacts: RawArtifactService,
        transport_factory: Callable[[ProviderConfig], ProviderTransport],
        secret_resolver: Callable[[str], SecretStr],
        observed_at: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._raw_artifacts = raw_artifacts
        self._transport_factory = transport_factory
        self._secret_resolver = secret_resolver
        self._observed_at = observed_at or (lambda: datetime.now(UTC))
        self._pricing = load_tikhub_pricing()
        self._attempt_preparer = PostgresFencedProviderAttemptPreparer(session_factory)
        self._scope_gateway = PostgresCollectionRunExecutionGateway(session_factory)
        self._content_state = PostgresCollectionContentStateReader(session_factory)
        self._content_writer = PostgresFencedCollectionIngestionWriter(session_factory)
        self._content_actions = PostgresCollectionContentActionRepository(session_factory)
        self._decision_service = CollectionDecisionService()
        self._reconciler = ProviderAttemptReconciler(
            persistence=PostgresProviderRecoveryPersistence(session_factory),
            raw_artifacts=raw_artifacts,
        )

    def execute(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        context: JobExecutionContextProtocol,
    ) -> CollectionScopeExecutionResult:
        """执行当前正式 keyword_search/content_discovery Scope。"""
        if scope.source_type != "keyword_search" or scope.operation_group != "content_discovery":
            raise ValueError("TikHub Scope Runtime 当前只支持 keyword_search/content_discovery")

        self._reconciler.recover_inherited(context.fence)
        platform = _tikhub_platform(scope.platform)
        runtime_config = _platform_runtime_config(run, scope.platform)
        provider_config = self._provider_config_for_run(run, runtime_config)
        capability = _capability(platform)
        _validate_decision_policy(run)
        policy = _decision_policy(run)
        relevance = _relevance_service(run)

        stats = _ScopeStats.from_payload(scope.stats)
        self._refresh_counts(scope=scope, context=context, stats=stats)
        pagination_state = dict(scope.pagination_state)
        stop_reason: str | None = None
        first_page_no = max(1, scope.progress + 1)
        current_page_no = first_page_no

        try:
            for current_page_no in range(first_page_no, MAX_SEARCH_PAGES + 1):
                if context.cancel_requested():
                    self._refresh_counts(scope=scope, context=context, stats=stats)
                    return _result(
                        status="cancelled",
                        stop_reason="cancelled",
                        pagination_state=pagination_state,
                        stats=stats,
                    )

                call = build_search_call(
                    platform=platform,
                    keyword=scope.source_value,
                    config=runtime_config.config,
                    state=pagination_state,
                )
                executed = self._execute_call(
                    run=run,
                    scope=scope,
                    call=call,
                    provider_config=provider_config,
                    context=context,
                )
                stats.search_pages += 1

                items = extract_search_items(platform, executed.body)
                stats.search_items += len(items)
                for raw_item in items:
                    if context.cancel_requested():
                        self._refresh_counts(
                            scope=scope,
                            context=context,
                            stats=stats,
                        )
                        return _result(
                            status="cancelled",
                            stop_reason="cancelled",
                            pagination_state=pagination_state,
                            stats=stats,
                        )
                    item_locator = _stable_item_locator(
                        call.operation,
                        "content",
                        raw_item,
                    )
                    candidate_id = self._content_writer.discover_candidate(
                        provider_attempt_id=executed.attempt_id,
                        raw_artifact_id=executed.raw_artifact_id,
                        item_kind="content",
                        item_locator=item_locator,
                        discovered_at=executed.observed_at,
                        fence=context.fence,
                    )
                    try:
                        search_content = map_content(
                            platform=platform,
                            raw=raw_item,
                            context=mapping_context(
                                provider_request_id=str(executed.request_id),
                                provider_attempt_id=str(executed.attempt_id),
                                raw_artifact_id=executed.raw_artifact_id,
                                operation=call.operation,
                                source_type=scope.source_type,
                                source_value=scope.source_value,
                                observed_at=executed.observed_at,
                            ),
                            item_locator=item_locator,
                        )
                    except Exception as exc:
                        self._content_writer.record_candidate_failure(
                            candidate_id=candidate_id,
                            provider_attempt_id=executed.attempt_id,
                            fence=context.fence,
                            result="invalid",
                            error_code=type(exc).__name__,
                        )
                        raise
                    self._process_search_content(
                        run=run,
                        scope=scope,
                        content=search_content,
                        search_executed=executed,
                        search_candidate_id=candidate_id,
                        provider_config=provider_config,
                        capability=capability,
                        policy=policy,
                        context=context,
                        stats=stats,
                        relevance=relevance,
                    )

                advance = advance_search(
                    platform=platform,
                    state=pagination_state,
                    body=executed.body,
                )
                if not advance.should_continue:
                    stop_reason = advance.stop_reason or "provider_exhausted"
                    break
                assert advance.next_state is not None
                pagination_state = dict(advance.next_state)
                self._refresh_counts(scope=scope, context=context, stats=stats)
                self._scope_gateway.checkpoint_scope(
                    scope.id,
                    fence=context.fence,
                    pagination_state=pagination_state,
                    progress=min(99, current_page_no),
                    stats=stats.payload(),
                )
            else:
                stop_reason = "page_limit"
                stats.technical_partial_results += 1
        except LeaseLostError:
            raise
        except _ProviderCallFailed as exc:
            self._refresh_counts(scope=scope, context=context, stats=stats)
            if exc.retryable:
                raise CollectionScopeRetryableError(
                    error_code=exc.error_code,
                    pagination_state=pagination_state,
                    progress=max(
                        scope.progress,
                        min(99, current_page_no - 1),
                    ),
                    stats=stats.payload(),
                    requested_count=stats.requested_count,
                    succeeded_count=stats.succeeded_count,
                    failed_count=stats.failed_count,
                    content_count=stats.content_count,
                    comment_count=stats.comment_count,
                ) from exc
            return _result(
                status="failed",
                stop_reason=exc.error_code,
                pagination_state=pagination_state,
                stats=stats,
            )
        except Exception:
            self._refresh_counts(scope=scope, context=context, stats=stats)
            return _result(
                status="failed",
                stop_reason="scope_execution_failed",
                pagination_state=pagination_state,
                stats=stats,
            )

        self._refresh_counts(scope=scope, context=context, stats=stats)
        return _result(
            status=(
                "partial_success"
                if stop_reason == "page_limit" or stats.technical_partial_results > 0
                else "succeeded"
            ),
            stop_reason=stop_reason,
            pagination_state=pagination_state,
            stats=stats,
        )

    def _refresh_counts(
        self,
        *,
        scope: CollectionScopeRecord,
        context: JobExecutionContextProtocol,
        stats: _ScopeStats,
    ) -> None:
        stats.sync_counts(
            self._attempt_preparer.read_scope_counts(
                scope_id=scope.id,
                fence=context.fence,
            )
        )

    def _process_search_content(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        content: CanonicalContentV1,
        search_executed: _ExecutedCall,
        search_candidate_id: UUID,
        provider_config: ProviderConfig,
        capability: ProviderPlatformCapabilityV1,
        policy: CollectionDecisionPolicyV1,
        context: JobExecutionContextProtocol,
        stats: _ScopeStats,
        relevance: RelevanceService,
    ) -> None:
        search_content = content
        prefetched_details: tuple[_DetailCandidate, ...] = ()
        detail_prefetched = False
        if not relevance.evaluate(content).matched:
            details = self._fetch_detail_candidates(
                run=run,
                scope=scope,
                content=content,
                provider_config=provider_config,
                context=context,
                stats=stats,
            )
            detail = details[-1]
            if not relevance.evaluate(detail.content).matched:
                self._content_writer.record_candidate_filtered(
                    candidate_id=search_candidate_id,
                    canonical=content,
                    fence=context.fence,
                )
                for candidate in details:
                    self._content_writer.record_candidate_filtered(
                        candidate_id=candidate.candidate_id,
                        canonical=candidate.content,
                        fence=context.fence,
                    )
                stats.filtered_content_count += 1
                return
            content = detail.content
            prefetched_details = details
            detail_prefetched = True

        action = self._content_actions.get(
            scope_id=scope.id,
            external_content_id=content.external_content_id,
            fence=context.fence,
        )
        if action is None:
            prior = self._content_state.evaluate(content)
            search_comment_count = _observed_comment_count(content)
            decision = self._decision_service.decide(
                CollectionDecisionRequestV1(
                    current=ContentObservationV1(
                        comment_count=search_comment_count,
                        search_missing_required_fields=search_comment_count is None,
                        business_changed=(prior.business_changed if prior is not None else False),
                    ),
                    previous=prior.previous if prior is not None else None,
                    policy=policy,
                    capability=capability,
                )
            )
            action = self._content_actions.get_or_create(
                scope_id=scope.id,
                external_content_id=content.external_content_id,
                search_provider_attempt_id=search_executed.attempt_id,
                search_raw_artifact_id=search_executed.raw_artifact_id,
                search_observed_at=search_executed.observed_at,
                previous_exists=prior is not None,
                previous_comment_count=(
                    prior.previous.comment_count if prior is not None else None
                ),
                initial_business_changed=(prior.business_changed if prior is not None else False),
                decision=decision,
                resolved_comment_count=search_comment_count,
                fence=context.fence,
            )

        candidates = (
            (
                _DetailCandidate(search_content, search_candidate_id),
                *prefetched_details,
            )
            if detail_prefetched
            else (_DetailCandidate(content, search_candidate_id),)
        )
        content_id: UUID | None = None
        for candidate in candidates:
            ingestion = self._content_writer.ingest_content(
                canonical=candidate.content,
                fence=context.fence,
                candidate_id=candidate.candidate_id,
            )
            if content_id is not None and ingestion.target_id != content_id:
                raise RuntimeError("Search/Detail 摄取未收敛到同一 Content")
            content_id = ingestion.target_id
        if content_id is None:  # pragma: no cover - candidates 固定非空
            raise RuntimeError("Search/Detail 未产生 Content")
        if (
            detail_prefetched
            and action.decision.detail_action == "fetch"
            and not action.detail_completed
        ):
            post_detail = self._decision_service.decide(
                CollectionDecisionRequestV1(
                    current=ContentObservationV1(
                        comment_count=_observed_comment_count(content),
                        business_changed=False,
                    ),
                    previous=_previous_from_action(action),
                    policy=policy,
                    capability=capability,
                )
            )
            action = self._content_actions.complete_detail(
                action_id=action.id,
                decision=post_detail,
                resolved_comment_count=_observed_comment_count(content),
                fence=context.fence,
            )
        if action.comments_completed:
            return

        comment_source = content
        decision = action.decision
        if (
            action.decision.detail_action == "fetch"
            and not action.detail_completed
            and not detail_prefetched
            and not context.cancel_requested()
        ):
            comment_source = self._fetch_detail(
                run=run,
                scope=scope,
                content=content,
                content_id=content_id,
                provider_config=provider_config,
                context=context,
                stats=stats,
            )
            post_detail = self._decision_service.decide(
                CollectionDecisionRequestV1(
                    current=ContentObservationV1(
                        comment_count=_observed_comment_count(comment_source),
                        business_changed=False,
                    ),
                    previous=_previous_from_action(action),
                    policy=policy,
                    capability=capability,
                )
            )
            action = self._content_actions.complete_detail(
                action_id=action.id,
                decision=post_detail,
                resolved_comment_count=_observed_comment_count(comment_source),
                fence=context.fence,
            )
            decision = action.decision

        if context.cancel_requested():
            return

        if decision.comment_action in _COMMENT_FETCH_ACTIONS:
            outcome = self._fetch_comments(
                run=run,
                scope=scope,
                content=comment_source,
                content_id=content_id,
                provider_config=provider_config,
                capability=capability,
                policy=policy,
                context=context,
                stats=stats,
                comment_action=decision.comment_action,
                comment_target=decision.comment_target,
                reported_total_override=action.resolved_comment_count,
            )
            if outcome.technical_partial:
                stats.technical_partial_results += 1
            if outcome.completed:
                self._content_actions.complete_comments(
                    action_id=action.id,
                    fence=context.fence,
                )
            return

        self._record_non_fetch_coverage(
            content_id=content_id,
            content=comment_source,
            context=context,
            comment_reason=decision.comment_reason,
            comment_target=decision.comment_target,
        )
        self._content_actions.complete_comments(
            action_id=action.id,
            fence=context.fence,
        )

    def _fetch_detail(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        content: CanonicalContentV1,
        content_id: UUID,
        provider_config: ProviderConfig,
        context: JobExecutionContextProtocol,
        stats: _ScopeStats,
    ) -> CanonicalContentV1:
        details = self._fetch_detail_candidates(
            run=run,
            scope=scope,
            content=content,
            provider_config=provider_config,
            context=context,
            stats=stats,
        )
        latest_detail: CanonicalContentV1 | None = None
        for detail in details:
            detail_ingestion = self._content_writer.ingest_content(
                canonical=detail.content,
                fence=context.fence,
                candidate_id=detail.candidate_id,
            )
            if detail_ingestion.target_id != content_id:
                raise RuntimeError("Detail 与 Search 摄取未收敛到同一 Content")
            latest_detail = detail.content
        if latest_detail is None:  # pragma: no cover - 前置非空校验保证
            raise RuntimeError("TikHub Detail 未产生 Canonical Content")
        return latest_detail

    def _fetch_detail_candidates(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        content: CanonicalContentV1,
        provider_config: ProviderConfig,
        context: JobExecutionContextProtocol,
        stats: _ScopeStats,
    ) -> tuple[_DetailCandidate, ...]:
        """通过正式 Provider/Raw/Mapper 获取一次 Detail，但不提前写 Content。"""

        platform = _tikhub_platform(scope.platform)
        detail_call = build_detail_call(platform, content)
        executed = self._execute_call(
            run=run,
            scope=scope,
            call=detail_call,
            provider_config=provider_config,
            context=context,
        )
        stats.detail_requests += 1

        detail_items = extract_detail_items(platform, executed.body)
        if not detail_items:
            raise ValueError("TikHub Detail 响应未包含可映射内容")
        mapped: list[_DetailCandidate] = []
        for raw_item in detail_items:
            item_locator = _stable_item_locator(
                detail_call.operation,
                "content",
                raw_item,
            )
            candidate_id = self._content_writer.discover_candidate(
                provider_attempt_id=executed.attempt_id,
                raw_artifact_id=executed.raw_artifact_id,
                item_kind="content",
                item_locator=item_locator,
                discovered_at=executed.observed_at,
                fence=context.fence,
            )
            try:
                detail_content = map_content(
                    platform=platform,
                    raw=raw_item,
                    context=mapping_context(
                        provider_request_id=str(executed.request_id),
                        provider_attempt_id=str(executed.attempt_id),
                        raw_artifact_id=executed.raw_artifact_id,
                        operation=detail_call.operation,
                        source_type=scope.source_type,
                        source_value=scope.source_value,
                        observed_at=executed.observed_at,
                        external_content_id=content.external_content_id,
                    ),
                    item_locator=item_locator,
                )
            except Exception as exc:
                self._content_writer.record_candidate_failure(
                    candidate_id=candidate_id,
                    provider_attempt_id=executed.attempt_id,
                    fence=context.fence,
                    result="invalid",
                    error_code=type(exc).__name__,
                )
                raise
            if detail_content.external_content_id != content.external_content_id:
                self._content_writer.record_candidate_failure(
                    candidate_id=candidate_id,
                    provider_attempt_id=executed.attempt_id,
                    fence=context.fence,
                    result="invalid",
                    error_code="detail_content_identity_mismatch",
                )
                raise ValueError("TikHub Detail 与 Search Content 身份不一致")
            mapped.append(_DetailCandidate(content=detail_content, candidate_id=candidate_id))
        return tuple(mapped)

    def _fetch_comments(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        content: CanonicalContentV1,
        content_id: UUID,
        provider_config: ProviderConfig,
        capability: ProviderPlatformCapabilityV1,
        policy: CollectionDecisionPolicyV1,
        context: JobExecutionContextProtocol,
        stats: _ScopeStats,
        comment_action: str,
        comment_target: int | None,
        reported_total_override: int | None,
    ) -> _CommentFetchOutcome:
        platform = _tikhub_platform(scope.platform)
        pagination_state: dict[str, object] = {}
        seen_comment_ids: set[str] = set()
        reported_total = (
            reported_total_override
            if reported_total_override is not None
            else _observed_comment_count(content)
        )
        sample_mode = _comment_sample_mode(
            comment_action=comment_action,
            comment_target=comment_target,
            reported_total=reported_total,
        )
        sort_mode = _comment_sort_mode(platform)
        last_executed: _ExecutedCall | None = None
        known_comment_ids = (
            self._content_state.known_root_comment_ids(content_id)
            if comment_action == "fetch_incremental"
            else frozenset()
        )
        technical_partial = False

        for _page_no in range(1, MAX_COMMENT_PAGES + 1):
            if context.cancel_requested():
                if last_executed is not None:
                    self._record_comment_coverage(
                        content_id=content_id,
                        platform=platform,
                        executed=last_executed,
                        context=context,
                        coverage="partial",
                        reported_total=reported_total,
                        collected_count=len(seen_comment_ids),
                        sample_mode=sample_mode,
                        sort_mode=sort_mode,
                        target_count=comment_target,
                        stop_reason="cancelled",
                    )
                return _CommentFetchOutcome(
                    completed=False,
                    technical_partial=technical_partial,
                )
            call = build_comments_call(
                platform=platform,
                external_content_id=content.external_content_id,
                state=pagination_state,
            )
            executed = self._execute_call(
                run=run,
                scope=scope,
                call=call,
                provider_config=provider_config,
                context=context,
            )
            last_executed = executed
            stats.comment_requests += 1

            raw_items = extract_comment_items(platform, executed.body)
            page_comment_ids: list[str] = []
            for raw_item in raw_items:
                item_locator = _stable_item_locator(
                    call.operation,
                    "comment",
                    raw_item,
                )
                candidate_id = self._content_writer.discover_candidate(
                    provider_attempt_id=executed.attempt_id,
                    raw_artifact_id=executed.raw_artifact_id,
                    item_kind="comment",
                    item_locator=item_locator,
                    discovered_at=executed.observed_at,
                    fence=context.fence,
                )
                try:
                    comment = map_comment(
                        platform=platform,
                        raw=raw_item,
                        context=mapping_context(
                            provider_request_id=str(executed.request_id),
                            provider_attempt_id=str(executed.attempt_id),
                            raw_artifact_id=executed.raw_artifact_id,
                            operation=call.operation,
                            source_type=scope.source_type,
                            source_value=scope.source_value,
                            observed_at=executed.observed_at,
                            external_content_id=content.external_content_id,
                        ),
                        item_locator=item_locator,
                        is_root=True,
                    )
                except Exception as exc:
                    self._content_writer.record_candidate_failure(
                        candidate_id=candidate_id,
                        provider_attempt_id=executed.attempt_id,
                        fence=context.fence,
                        result="invalid",
                        error_code=type(exc).__name__,
                    )
                    raise
                if comment.external_content_id != content.external_content_id:
                    self._content_writer.record_candidate_failure(
                        candidate_id=candidate_id,
                        provider_attempt_id=executed.attempt_id,
                        fence=context.fence,
                        result="invalid",
                        error_code="comment_content_identity_mismatch",
                    )
                    raise ValueError("TikHub Comment 与 Content 身份不一致")
                page_comment_ids.append(comment.external_comment_id)
                self._content_writer.ingest_comment(
                    canonical=comment,
                    fence=context.fence,
                    candidate_id=candidate_id,
                )
                root_is_new = comment.external_comment_id not in seen_comment_ids
                seen_comment_ids.add(comment.external_comment_id)

                if not root_is_new:
                    continue
                reply_decision = self._decision_service.decide_reply(
                    ReplyDecisionRequestV1(
                        reply_count=_observed_reply_count(comment),
                        policy=policy,
                        capability=capability,
                    )
                )
                if reply_decision.action in _REPLY_FETCH_ACTIONS and not context.cancel_requested():
                    reply_outcome = self._fetch_sub_comments(
                        run=run,
                        scope=scope,
                        content_id=content_id,
                        root_comment=comment,
                        provider_config=provider_config,
                        context=context,
                        stats=stats,
                        reply_action=reply_decision.action,
                        reply_target=reply_decision.target,
                    )
                    technical_partial = technical_partial or reply_outcome.technical_partial
                    if not reply_outcome.completed:
                        return _CommentFetchOutcome(
                            completed=False,
                            technical_partial=technical_partial,
                        )
                else:
                    self._record_non_fetch_thread_coverage(
                        content_id=content_id,
                        root_comment=comment,
                        platform=platform,
                        context=context,
                        reason=reply_decision.reason,
                        target_count=reply_decision.target,
                    )

            advance = advance_comments(
                platform=platform,
                state=pagination_state,
                body=executed.body,
            )
            if not advance.should_continue:
                stop_reason = advance.stop_reason or "provider_exhausted"
                if stop_reason == "empty_page" and not seen_comment_ids:
                    # 第一页评论接口的显式空集合是比 Search/Detail 更晚的观察事实。
                    reported_total = 0
                    sample_mode = _comment_sample_mode(
                        comment_action=comment_action,
                        comment_target=comment_target,
                        reported_total=reported_total,
                    )
                coverage = _coverage_for_stop(
                    stop_reason,
                    reported_total,
                    len(seen_comment_ids),
                )
                technical_partial = technical_partial or _technical_partial_stop(stop_reason)
                self._record_comment_coverage(
                    content_id=content_id,
                    platform=platform,
                    executed=executed,
                    context=context,
                    coverage=coverage,
                    reported_total=reported_total,
                    collected_count=len(seen_comment_ids),
                    sample_mode=sample_mode,
                    sort_mode=sort_mode,
                    target_count=comment_target,
                    stop_reason=stop_reason,
                )
                return _CommentFetchOutcome(
                    completed=True,
                    technical_partial=technical_partial,
                )

            if comment_action == "fetch_incremental" and known_comment_boundary_reached(
                page_comment_ids,
                known_comment_ids,
            ):
                self._record_comment_coverage(
                    content_id=content_id,
                    platform=platform,
                    executed=executed,
                    context=context,
                    coverage="partial",
                    reported_total=reported_total,
                    collected_count=len(seen_comment_ids),
                    sample_mode=sample_mode,
                    sort_mode=sort_mode,
                    target_count=comment_target,
                    stop_reason="known_comment_reached",
                )
                return _CommentFetchOutcome(
                    completed=True,
                    technical_partial=technical_partial,
                )
            if comment_action == "probe_first_page":
                self._record_comment_coverage(
                    content_id=content_id,
                    platform=platform,
                    executed=executed,
                    context=context,
                    coverage="partial",
                    reported_total=reported_total,
                    collected_count=len(seen_comment_ids),
                    sample_mode=sample_mode,
                    sort_mode=sort_mode,
                    target_count=comment_target,
                    stop_reason="probe_first_page",
                )
                return _CommentFetchOutcome(
                    completed=True,
                    technical_partial=technical_partial,
                )
            if comment_target is not None and len(seen_comment_ids) >= comment_target:
                # 只有 Provider 仍声明可继续分页时才会走到这里；达到软目标不能证明全集完整。
                coverage = "partial"
                self._record_comment_coverage(
                    content_id=content_id,
                    platform=platform,
                    executed=executed,
                    context=context,
                    coverage=coverage,
                    reported_total=reported_total,
                    collected_count=len(seen_comment_ids),
                    sample_mode=sample_mode,
                    sort_mode=sort_mode,
                    target_count=comment_target,
                    stop_reason="target_reached",
                )
                return _CommentFetchOutcome(
                    completed=True,
                    technical_partial=technical_partial,
                )
            assert advance.next_state is not None
            pagination_state = dict(advance.next_state)

        if last_executed is None:  # pragma: no cover - 分页上限为正
            raise RuntimeError("TikHub Comments 未执行任何页面")
        self._record_comment_coverage(
            content_id=content_id,
            platform=platform,
            executed=last_executed,
            context=context,
            coverage="partial",
            reported_total=reported_total,
            collected_count=len(seen_comment_ids),
            sample_mode=sample_mode,
            sort_mode=sort_mode,
            target_count=comment_target,
            stop_reason="page_limit",
        )
        return _CommentFetchOutcome(
            completed=True,
            technical_partial=True,
        )

    def _record_non_fetch_coverage(
        self,
        *,
        content_id: UUID,
        content: CanonicalContentV1,
        context: JobExecutionContextProtocol,
        comment_reason: str,
        comment_target: int | None,
    ) -> None:
        attempt_id, raw_artifact_id = _canonical_source_ids(content)
        if comment_reason == "provider_reported_zero":
            coverage = "complete"
        elif comment_reason in _UNAVAILABLE_COMMENT_REASONS:
            coverage = "unavailable"
        else:
            coverage = "not_requested"
        self._content_writer.record_comment_coverage(
            content_id=content_id,
            provider_attempt_id=attempt_id,
            raw_artifact_id=raw_artifact_id,
            platform=content.platform,
            fence=context.fence,
            coverage=coverage,
            reported_total=_observed_comment_count(content),
            collected_count=0,
            sample_mode="not_requested",
            sort_mode="not_requested",
            target_count=comment_target,
            stop_reason=comment_reason,
            observed_at=content.observed_at,
        )

    def _record_non_fetch_thread_coverage(
        self,
        *,
        content_id: UUID,
        root_comment: CanonicalCommentV1,
        platform: TikHubPlatform,
        context: JobExecutionContextProtocol,
        reason: str,
        target_count: int | None,
    ) -> None:
        attempt_id, raw_artifact_id = _canonical_source_ids(root_comment)
        reported_total = _observed_reply_count(root_comment)
        if reason == "reply_count_zero":
            coverage = "complete"
        elif reason == "sub_comments_unavailable":
            coverage = "unavailable"
        else:
            coverage = "not_requested"
        self._content_writer.record_thread_coverage(
            content_id=content_id,
            root_comment_id=root_comment.external_comment_id,
            provider_attempt_id=attempt_id,
            raw_artifact_id=raw_artifact_id,
            platform=platform,
            fence=context.fence,
            coverage=coverage,
            reported_total=reported_total,
            captured_count=0,
            target_count=target_count,
            stop_reason=reason,
            observed_at=root_comment.observed_at,
        )

    def _record_comment_coverage(
        self,
        *,
        content_id: UUID,
        platform: TikHubPlatform,
        executed: _ExecutedCall,
        context: JobExecutionContextProtocol,
        coverage: str,
        reported_total: int | None,
        collected_count: int,
        sample_mode: str,
        sort_mode: str,
        target_count: int | None,
        stop_reason: str,
    ) -> None:
        self._content_writer.record_comment_coverage(
            content_id=content_id,
            provider_attempt_id=executed.attempt_id,
            raw_artifact_id=executed.raw_artifact_id,
            platform=platform,
            fence=context.fence,
            coverage=coverage,
            reported_total=reported_total,
            collected_count=collected_count,
            sample_mode=sample_mode,
            sort_mode=sort_mode,
            target_count=target_count,
            stop_reason=stop_reason,
            observed_at=executed.observed_at,
        )

    def _fetch_sub_comments(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        content_id: UUID,
        root_comment: CanonicalCommentV1,
        provider_config: ProviderConfig,
        context: JobExecutionContextProtocol,
        stats: _ScopeStats,
        reply_action: str,
        reply_target: int | None,
    ) -> _ReplyFetchOutcome:
        platform = _tikhub_platform(scope.platform)
        pagination_state: dict[str, object] = {}
        reply_ids: set[str] = set()
        last_executed: _ExecutedCall | None = None
        reported_total = _observed_reply_count(root_comment)
        technical_partial = False

        for _page_no in range(1, MAX_SUB_COMMENT_PAGES + 1):
            if context.cancel_requested():
                if last_executed is not None:
                    self._content_writer.record_thread_coverage(
                        content_id=content_id,
                        root_comment_id=root_comment.external_comment_id,
                        provider_attempt_id=last_executed.attempt_id,
                        raw_artifact_id=last_executed.raw_artifact_id,
                        platform=platform,
                        fence=context.fence,
                        coverage="partial",
                        reported_total=reported_total,
                        captured_count=len(reply_ids),
                        target_count=reply_target,
                        stop_reason="cancelled",
                        observed_at=last_executed.observed_at,
                    )
                return _ReplyFetchOutcome(
                    reply_ids=frozenset(reply_ids),
                    completed=False,
                    technical_partial=technical_partial,
                )

            call = build_sub_comments_call(
                platform=platform,
                external_content_id=root_comment.external_content_id,
                root_comment_id=root_comment.external_comment_id,
                state=pagination_state,
            )
            executed = self._execute_call(
                run=run,
                scope=scope,
                call=call,
                provider_config=provider_config,
                context=context,
            )
            last_executed = executed
            stats.sub_comment_requests += 1

            raw_items = extract_sub_comment_items(platform, executed.body)
            for raw_item in raw_items:
                item_locator = _stable_item_locator(
                    call.operation,
                    "comment",
                    raw_item,
                )
                candidate_id = self._content_writer.discover_candidate(
                    provider_attempt_id=executed.attempt_id,
                    raw_artifact_id=executed.raw_artifact_id,
                    item_kind="comment",
                    item_locator=item_locator,
                    discovered_at=executed.observed_at,
                    fence=context.fence,
                )
                try:
                    reply = map_comment(
                        platform=platform,
                        raw=raw_item,
                        context=mapping_context(
                            provider_request_id=str(executed.request_id),
                            provider_attempt_id=str(executed.attempt_id),
                            raw_artifact_id=executed.raw_artifact_id,
                            operation=call.operation,
                            source_type=scope.source_type,
                            source_value=scope.source_value,
                            observed_at=executed.observed_at,
                            external_content_id=root_comment.external_content_id,
                            root_comment_id=root_comment.external_comment_id,
                        ),
                        item_locator=item_locator,
                        is_root=False,
                    )
                except Exception as exc:
                    self._content_writer.record_candidate_failure(
                        candidate_id=candidate_id,
                        provider_attempt_id=executed.attempt_id,
                        fence=context.fence,
                        result="invalid",
                        error_code=type(exc).__name__,
                    )
                    raise
                if reply.external_content_id != root_comment.external_content_id:
                    self._content_writer.record_candidate_failure(
                        candidate_id=candidate_id,
                        provider_attempt_id=executed.attempt_id,
                        fence=context.fence,
                        result="invalid",
                        error_code="reply_content_identity_mismatch",
                    )
                    raise ValueError("TikHub Reply 与 Content 身份不一致")
                if reply.root_comment_id != root_comment.external_comment_id:
                    self._content_writer.record_candidate_failure(
                        candidate_id=candidate_id,
                        provider_attempt_id=executed.attempt_id,
                        fence=context.fence,
                        result="invalid",
                        error_code="reply_root_identity_mismatch",
                    )
                    raise ValueError("TikHub Reply 与 Root Comment 身份不一致")
                self._content_writer.ingest_comment(
                    canonical=reply,
                    fence=context.fence,
                    candidate_id=candidate_id,
                )
                reply_ids.add(reply.external_comment_id)

            advance = advance_sub_comments(
                platform=platform,
                state=pagination_state,
                body=executed.body,
            )
            if not advance.should_continue:
                stop_reason = advance.stop_reason or "provider_exhausted"
                if stop_reason == "empty_page" and not reply_ids:
                    reported_total = 0
                coverage = _coverage_for_stop(
                    stop_reason,
                    reported_total,
                    len(reply_ids),
                )
                technical_partial = technical_partial or _technical_partial_stop(stop_reason)
                self._content_writer.record_thread_coverage(
                    content_id=content_id,
                    root_comment_id=root_comment.external_comment_id,
                    provider_attempt_id=executed.attempt_id,
                    raw_artifact_id=executed.raw_artifact_id,
                    platform=platform,
                    fence=context.fence,
                    coverage=coverage,
                    reported_total=reported_total,
                    captured_count=len(reply_ids),
                    target_count=reply_target,
                    stop_reason=stop_reason,
                    observed_at=executed.observed_at,
                )
                return _ReplyFetchOutcome(
                    reply_ids=frozenset(reply_ids),
                    completed=True,
                    technical_partial=technical_partial,
                )

            if reply_action == "probe_first_page":
                self._content_writer.record_thread_coverage(
                    content_id=content_id,
                    root_comment_id=root_comment.external_comment_id,
                    provider_attempt_id=executed.attempt_id,
                    raw_artifact_id=executed.raw_artifact_id,
                    platform=platform,
                    fence=context.fence,
                    coverage="partial",
                    reported_total=reported_total,
                    captured_count=len(reply_ids),
                    target_count=reply_target,
                    stop_reason="probe_first_page",
                    observed_at=executed.observed_at,
                )
                return _ReplyFetchOutcome(
                    reply_ids=frozenset(reply_ids),
                    completed=True,
                    technical_partial=technical_partial,
                )

            if reply_target is not None and len(reply_ids) >= reply_target:
                coverage = "partial"
                self._content_writer.record_thread_coverage(
                    content_id=content_id,
                    root_comment_id=root_comment.external_comment_id,
                    provider_attempt_id=executed.attempt_id,
                    raw_artifact_id=executed.raw_artifact_id,
                    platform=platform,
                    fence=context.fence,
                    coverage=coverage,
                    reported_total=reported_total,
                    captured_count=len(reply_ids),
                    target_count=reply_target,
                    stop_reason="target_reached",
                    observed_at=executed.observed_at,
                )
                return _ReplyFetchOutcome(
                    reply_ids=frozenset(reply_ids),
                    completed=True,
                    technical_partial=technical_partial,
                )

            assert advance.next_state is not None
            pagination_state = dict(advance.next_state)

        if last_executed is None:  # pragma: no cover - 分页上限为正
            raise RuntimeError("TikHub SubComments 未执行任何页面")
        self._content_writer.record_thread_coverage(
            content_id=content_id,
            root_comment_id=root_comment.external_comment_id,
            provider_attempt_id=last_executed.attempt_id,
            raw_artifact_id=last_executed.raw_artifact_id,
            platform=platform,
            fence=context.fence,
            coverage="partial",
            reported_total=reported_total,
            captured_count=len(reply_ids),
            target_count=reply_target,
            stop_reason="page_limit",
            observed_at=last_executed.observed_at,
        )
        return _ReplyFetchOutcome(
            reply_ids=frozenset(reply_ids),
            completed=True,
            technical_partial=True,
        )

    def _execute_call(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        call: TikHubOperationCall,
        provider_config: ProviderConfig,
        context: JobExecutionContextProtocol,
    ) -> _ExecutedCall:
        request_params: JsonObject = {
            "method": call.method,
            "path": call.path,
            "params": dict(call.params),
        }
        if call.body is not None:
            request_params["body"] = dict(call.body)
        request = ProviderRequestV1.create(
            request_id=uuid4(),
            run_id=run.id,
            scope_id=scope.id,
            provider=provider_config.provider,
            platform=scope.platform,
            operation=call.operation,
            request_params=request_params,
            pagination_input=dict(call.pagination_input or {}),
        )
        prepared = self._attempt_preparer.resolve_or_prepare_billable_attempt(
            request=request,
            provider_config_id=provider_config.id,
            attempt_id=uuid4(),
            billing=self._pricing.billing_for_endpoint(call.path),
            fence=context.fence,
        )

        if prepared.attempt.dispatch_status == "completed":
            if prepared.attempt.error_code is not None or (
                prepared.attempt.http_status is not None and prepared.attempt.http_status >= 400
            ):
                status_code = prepared.attempt.http_status
                raise _ProviderCallFailed(
                    error_code=(
                        prepared.attempt.error_code
                        or (f"http_{status_code}" if status_code is not None else "provider_failed")
                    ),
                    retryable=(
                        _retryable_http_status(status_code) if status_code is not None else False
                    ),
                )
            return self._replay_completed_call(
                request=request,
                prepared=prepared,
            )
        if prepared.attempt.dispatch_status != "reserved":
            raise RuntimeError(
                f"Provider Attempt 未处于可发送状态: {prepared.attempt.dispatch_status}"
            )

        credential = self._secret_resolver(provider_config.secret_ref)
        outcome = ProviderDispatchService(
            persistence=PostgresProviderDispatchPersistence(self._session_factory),
            client=ProviderClient(transport=self._transport_factory(provider_config)),
            raw_artifacts=self._raw_artifacts,
        ).dispatch(
            attempt_id=prepared.attempt.id,
            fence=context.fence,
            transport_request=call.transport_request(credential),
        )
        if outcome.attempt.dispatch_status != "completed":
            raise _ProviderCallFailed(
                error_code=(outcome.attempt.error_code or outcome.attempt.dispatch_status),
                retryable=outcome.attempt.dispatch_status in {"not_sent", "unknown"},
            )
        if outcome.attempt.http_status is not None and outcome.attempt.http_status >= 400:
            raise _ProviderCallFailed(
                error_code=(outcome.attempt.error_code or f"http_{outcome.attempt.http_status}"),
                retryable=_retryable_http_status(outcome.attempt.http_status),
            )
        if outcome.artifact is None:
            raise RuntimeError("TikHub completed Attempt 缺少 Raw Artifact")

        envelope = self._raw_artifacts.replay(outcome.artifact)
        if envelope.response is None:
            raise RuntimeError("TikHub completed Attempt 的 Raw 缺少 response")
        body = _response_body(envelope.response.body)
        return _ExecutedCall(
            request_id=prepared.request.id,
            attempt_id=prepared.attempt.id,
            raw_artifact_id=outcome.artifact.id,
            observed_at=envelope.completed_at,
            body=body,
        )

    def _replay_completed_call(
        self,
        *,
        request: ProviderRequestV1,
        prepared: PreparedProviderAttempt,
    ) -> _ExecutedCall:
        attempt = prepared.attempt
        if attempt.raw_artifact_id is None or attempt.dispatch_started_at is None:
            raise RuntimeError("已完成 Provider Attempt 缺少可回放 Raw 来源")
        artifact = self._load_raw_artifact(
            request=request,
            attempt_id=attempt.id,
            dispatch_started_at=attempt.dispatch_started_at,
            expected_artifact_id=attempt.raw_artifact_id,
        )
        envelope = self._raw_artifacts.replay(artifact)
        if envelope.response is None:
            raise RuntimeError("已完成 Provider Attempt 的 Raw 缺少 response")
        if envelope.response.status_code is not None and envelope.response.status_code >= 400:
            raise RuntimeError("成功 Attempt 的 Raw 不应包含 HTTP 失败状态")
        return _ExecutedCall(
            request_id=prepared.request.id,
            attempt_id=attempt.id,
            raw_artifact_id=artifact.id,
            observed_at=envelope.completed_at,
            body=_response_body(envelope.response.body),
        )

    def _load_raw_artifact(
        self,
        *,
        request: ProviderRequestV1,
        attempt_id: UUID,
        dispatch_started_at: datetime,
        expected_artifact_id: UUID,
    ) -> ArtifactRecord:
        storage_key = raw_storage_key(
            request=request,
            dispatch_started_at=dispatch_started_at,
            attempt_id=attempt_id,
        )
        session = self._session_factory()
        try:
            with session.begin():
                artifact = PostgresArtifactMetadataRepository(session).get_by_storage_key(
                    storage_key
                )
        finally:
            session.close()
        if artifact is None or artifact.id != expected_artifact_id:
            raise RuntimeError("Provider Attempt 的 Raw Artifact 元数据不存在或来源不一致")
        return artifact

    def _provider_config_for_run(
        self,
        run: CollectionRunRecord,
        runtime_config: _PlatformRuntimeConfig,
    ) -> ProviderConfig:
        if (
            runtime_config.provider is not None
            and runtime_config.base_url is not None
            and runtime_config.secret_ref is not None
        ):
            if runtime_config.provider != "tikhub":
                raise ValueError("TikHub Scope Runtime 只接受 provider=tikhub")
            return ProviderConfig(
                id=runtime_config.provider_config_id,
                provider=runtime_config.provider,
                display_name=f"run-snapshot:{runtime_config.provider_config_id}",
                base_url=runtime_config.base_url,
                secret_ref=runtime_config.secret_ref,
                enabled=True,
            )

        return self._load_provider_config(
            runtime_config.provider_config_id,
        )

    def _load_provider_config(
        self,
        provider_config_id: UUID,
    ) -> ProviderConfig:
        session = self._session_factory()
        try:
            with session.begin():
                config = PostgresProviderConfigRepository(session).get(provider_config_id)
        finally:
            session.close()
        if config is None:
            raise LookupError(f"Provider Config 不存在: {provider_config_id}")
        if not config.enabled:
            raise ValueError("Provider Config 已禁用")
        if config.provider != "tikhub":
            raise ValueError("TikHub Scope Runtime 只接受 provider=tikhub")
        return config


def _previous_from_action(
    action: CollectionContentActionRecord,
) -> PreviousContentStateV1 | None:
    if not action.previous_exists:
        return None
    return PreviousContentStateV1(comment_count=action.previous_comment_count)


def _canonical_source_ids(
    observation: CanonicalContentV1 | CanonicalCommentV1,
) -> tuple[UUID, UUID]:
    attempt_id = observation.source.provider_attempt_id
    raw_artifact_id = observation.source.raw_artifact_id
    if attempt_id is None or raw_artifact_id is None:
        raise ValueError("Coverage 来源缺少 provider_attempt_id/raw_artifact_id")
    try:
        return UUID(attempt_id), raw_artifact_id
    except ValueError as exc:
        raise ValueError("Coverage provider_attempt_id 不是 UUID") from exc


def _observed_comment_count(
    content: CanonicalContentV1,
) -> int | None:
    if "metrics.comment_count" not in content.observed_fields:
        return None
    return content.metrics.comment_count


def _observed_reply_count(
    comment: CanonicalCommentV1,
) -> int | None:
    if "metrics.reply_count" not in comment.observed_fields:
        return None
    return comment.metrics.reply_count


def _comment_sample_mode(
    *,
    comment_action: str,
    comment_target: int | None,
    reported_total: int | None,
) -> str:
    if comment_action == "probe_first_page":
        return "probe"
    if (
        reported_total is not None
        and comment_target is not None
        and comment_target >= reported_total
    ):
        return "full"
    return "adaptive_sample"


def _comment_sort_mode(platform: TikHubPlatform) -> str:
    if platform in {"xhs", "weibo", "bilibili"}:
        return "latest"
    return "provider_default"


def _coverage_for_stop(
    stop_reason: str,
    reported_total: int | None,
    captured_count: int,
) -> str:
    if stop_reason not in _PROVIDER_TERMINAL_STOP_REASONS:
        return "partial"
    if reported_total is None or captured_count >= reported_total:
        return "complete"
    return "partial"


def _technical_partial_stop(stop_reason: str) -> bool:
    if stop_reason in _TECHNICAL_PARTIAL_STOP_REASONS:
        return True
    return (
        stop_reason not in _PROVIDER_TERMINAL_STOP_REASONS
        and stop_reason not in _EXPECTED_PARTIAL_STOP_REASONS
    )


def _stable_item_locator(
    operation: str,
    item_kind: str,
    raw_item: dict[str, object],
) -> str:
    encoded = json.dumps(
        raw_item,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"{operation}:{item_kind}:{digest}"


def _response_body(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("TikHub Raw 响应 body 必须为 JSON Object")
    return cast(dict[str, object], value)


def _retryable_http_status(status_code: int) -> bool:
    return status_code in _RETRYABLE_HTTP_STATUSES or status_code >= 500


def _payload_int(payload: dict[str, object], name: str) -> int:
    value = payload.get(name, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _platform_runtime_config(
    run: CollectionRunRecord,
    platform: str,
) -> _PlatformRuntimeConfig:
    snapshot = run.config_snapshot
    platforms = snapshot.get("platforms")
    if not isinstance(platforms, list):
        raise ValueError("Collection Run Snapshot 缺少 platforms")
    matches = [
        item for item in platforms if isinstance(item, dict) and item.get("platform") == platform
    ]
    if len(matches) != 1:
        raise ValueError("Collection Run Snapshot 必须为 Scope 平台提供唯一 Provider Config")
    item = matches[0]
    provider_config_id = item.get("provider_config_id")
    if not isinstance(provider_config_id, str):
        raise ValueError("Collection Run Snapshot provider_config_id 必须为 UUID 字符串")
    try:
        parsed_config_id = UUID(provider_config_id)
    except ValueError as exc:
        raise ValueError("Collection Run Snapshot provider_config_id 不是合法 UUID") from exc
    config = item.get("config", {})
    if not isinstance(config, dict):
        raise ValueError("Collection Run Snapshot platform config 必须为对象")
    provider = item.get("provider")
    base_url = item.get("base_url")
    secret_ref = item.get("secret_ref")
    return _PlatformRuntimeConfig(
        provider_config_id=parsed_config_id,
        config={str(key): value for key, value in config.items()},
        provider=provider if isinstance(provider, str) else None,
        base_url=base_url if isinstance(base_url, str) else None,
        secret_ref=(secret_ref if isinstance(secret_ref, str) else None),
    )


def _decision_policy(
    run: CollectionRunRecord,
) -> CollectionDecisionPolicyV1:
    payload = run.config_snapshot.get("decision_policy")
    if payload is None:
        return CollectionDecisionPolicyV1()
    if not isinstance(payload, dict):
        raise ValueError("Collection Run Snapshot decision_policy 必须为对象")
    return CollectionDecisionPolicyV1.model_validate(payload)


def _relevance_service(run: CollectionRunRecord) -> RelevanceService:
    payload = run.config_snapshot.get("relevance")
    snapshot = RelevanceSnapshotV1.model_validate(payload)
    return RelevanceService(
        tuple(
            RelevanceKeyword(text=text, priority=priority)
            for priority, text in enumerate(snapshot.effective_keywords)
        )
    )


def _validate_decision_policy(run: CollectionRunRecord) -> None:
    detail_policy = run.config_snapshot.get(
        "detail_policy",
        "on_change",
    )
    comment_policy = run.config_snapshot.get(
        "comment_policy",
        "adaptive",
    )
    if detail_policy != "on_change":
        raise ValueError("Collection Scope Runtime 当前只支持 detail_policy=on_change")
    if comment_policy != "adaptive":
        raise ValueError("Collection Scope Runtime 当前只支持 comment_policy=adaptive")


def _capability(
    platform: TikHubPlatform,
) -> ProviderPlatformCapabilityV1:
    match = next(
        (
            capability
            for capability in TIKHUB_PLATFORM_CAPABILITIES
            if capability.provider == "tikhub" and capability.platform == platform
        ),
        None,
    )
    if match is None:
        raise ValueError(f"TikHub 平台 Capability 不存在: {platform}")
    return match


def _tikhub_platform(value: str) -> TikHubPlatform:
    if value not in {
        "xhs",
        "douyin",
        "weibo",
        "bilibili",
        "kuaishou",
    }:
        raise ValueError(f"TikHub Scope Runtime 不支持平台: {value}")
    return cast(TikHubPlatform, value)


def _result(
    *,
    status: CollectionScopeTerminalStatus,
    stop_reason: str | None,
    pagination_state: dict[str, object],
    stats: _ScopeStats,
) -> CollectionScopeExecutionResult:
    return CollectionScopeExecutionResult(
        status=status,
        stop_reason=stop_reason,
        pagination_state=dict(pagination_state),
        stats=stats.payload(),
        requested_count=stats.requested_count,
        succeeded_count=stats.succeeded_count,
        failed_count=stats.failed_count,
        content_count=stats.content_count,
        comment_count=stats.comment_count,
    )


__all__ = ["TikHubCollectionScopeExecutor"]
