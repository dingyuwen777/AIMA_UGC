"""Stage 7 TikHub Collection Scope 的生产执行组合层。"""

from __future__ import annotations

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
from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.contracts.collection import (
    CollectionDecisionPolicyV1,
    CollectionDecisionRequestV1,
    ContentObservationV1,
    ProviderPlatformCapabilityV1,
    ReplyDecisionRequestV1,
)
from aima_ugc.contracts.provider import JsonObject, ProviderRequestV1
from aima_ugc.modules.collection.collection_run_executor import (
    CollectionScopeExecutionResult,
    CollectionScopeRetryableError,
    CollectionScopeTerminalStatus,
)
from aima_ugc.modules.collection.decision import CollectionDecisionService
from aima_ugc.modules.collection.execution import CollectionRunRecord, CollectionScopeRecord
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

_MAX_SEARCH_PAGES = 100
_MAX_COMMENT_PAGES = 100
_MAX_SUB_COMMENT_PAGES = 100
_COMMENT_FETCH_ACTIONS = {
    "fetch_adaptive",
    "fetch_incremental",
    "refresh_controlled",
    "probe_first_page",
}
_REPLY_FETCH_ACTIONS = {"fetch_target", "probe_first_page"}
_RETRYABLE_HTTP_STATUSES = {408, 425, 429}


@dataclass(frozen=True, slots=True)
class _PlatformRuntimeConfig:
    provider_config_id: UUID
    config: dict[str, object]


@dataclass(frozen=True, slots=True)
class _ExecutedCall:
    request_id: UUID
    attempt_id: UUID
    raw_artifact_id: UUID
    body: dict[str, object]


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
        provider_config = self._load_provider_config(runtime_config.provider_config_id)
        capability = _capability(platform)
        _validate_decision_policy(run)

        stats = _ScopeStats.from_payload(scope.stats)
        self._refresh_counts(scope=scope, context=context, stats=stats)
        pagination_state = dict(scope.pagination_state)
        stop_reason: str | None = None
        first_page_no = max(1, scope.progress + 1)
        current_page_no = first_page_no

        try:
            for current_page_no in range(first_page_no, _MAX_SEARCH_PAGES + 1):
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
                for index, raw_item in enumerate(items):
                    if context.cancel_requested():
                        self._refresh_counts(scope=scope, context=context, stats=stats)
                        return _result(
                            status="cancelled",
                            stop_reason="cancelled",
                            pagination_state=pagination_state,
                            stats=stats,
                        )
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
                            observed_at=self._observed_at(),
                        ),
                        item_locator=f"search.items[{index}]",
                    )
                    self._process_search_content(
                        run=run,
                        scope=scope,
                        content=search_content,
                        provider_config=provider_config,
                        capability=capability,
                        context=context,
                        stats=stats,
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
        except LeaseLostError:
            raise
        except _ProviderCallFailed as exc:
            self._refresh_counts(scope=scope, context=context, stats=stats)
            if exc.retryable:
                raise CollectionScopeRetryableError(
                    error_code=exc.error_code,
                    pagination_state=pagination_state,
                    progress=max(scope.progress, min(99, current_page_no - 1)),
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
            status="partial_success" if stop_reason == "page_limit" else "succeeded",
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
            self._attempt_preparer.read_scope_counts(scope_id=scope.id, fence=context.fence)
        )

    def _process_search_content(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        content: CanonicalContentV1,
        provider_config: ProviderConfig,
        capability: ProviderPlatformCapabilityV1,
        context: JobExecutionContextProtocol,
        stats: _ScopeStats,
    ) -> None:
        prior = self._content_state.evaluate(content)
        decision = self._decision_service.decide(
            CollectionDecisionRequestV1(
                current=ContentObservationV1(
                    comment_count=content.metrics.comment_count,
                    business_changed=prior.business_changed if prior is not None else False,
                ),
                previous=prior.previous if prior is not None else None,
                policy=CollectionDecisionPolicyV1(),
                capability=capability,
            )
        )

        self._content_writer.ingest_content(canonical=content, fence=context.fence)

        if decision.detail_action == "fetch" and not context.cancel_requested():
            self._fetch_detail(
                run=run,
                scope=scope,
                content=content,
                provider_config=provider_config,
                context=context,
                stats=stats,
            )

        if decision.comment_action in _COMMENT_FETCH_ACTIONS and not context.cancel_requested():
            self._fetch_comments(
                run=run,
                scope=scope,
                content=content,
                provider_config=provider_config,
                capability=capability,
                context=context,
                stats=stats,
                comment_action=decision.comment_action,
                comment_target=decision.comment_target,
            )

    def _fetch_detail(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        content: CanonicalContentV1,
        provider_config: ProviderConfig,
        context: JobExecutionContextProtocol,
        stats: _ScopeStats,
    ) -> None:
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
        for index, raw_item in enumerate(detail_items):
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
                    observed_at=self._observed_at(),
                    external_content_id=content.external_content_id,
                ),
                item_locator=f"detail.items[{index}]",
            )
            if detail_content.external_content_id != content.external_content_id:
                raise ValueError("TikHub Detail 与 Search Content 身份不一致")
            self._content_writer.ingest_content(canonical=detail_content, fence=context.fence)

    def _fetch_comments(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        content: CanonicalContentV1,
        provider_config: ProviderConfig,
        capability: ProviderPlatformCapabilityV1,
        context: JobExecutionContextProtocol,
        stats: _ScopeStats,
        comment_action: str,
        comment_target: int | None,
    ) -> None:
        platform = _tikhub_platform(scope.platform)
        pagination_state: dict[str, object] = {}
        fetched = 0

        for _page_no in range(1, _MAX_COMMENT_PAGES + 1):
            if context.cancel_requested():
                return
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
            stats.comment_requests += 1

            raw_items = extract_comment_items(platform, executed.body)
            for index, raw_item in enumerate(raw_items):
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
                        observed_at=self._observed_at(),
                        external_content_id=content.external_content_id,
                    ),
                    item_locator=f"comments.items[{index}]",
                    is_root=True,
                )
                if comment.external_content_id != content.external_content_id:
                    raise ValueError("TikHub Comment 与 Content 身份不一致")
                self._content_writer.ingest_comment(canonical=comment, fence=context.fence)
                fetched += 1

                reply_decision = self._decision_service.decide_reply(
                    ReplyDecisionRequestV1(
                        reply_count=comment.metrics.reply_count,
                        policy=CollectionDecisionPolicyV1(),
                        capability=capability,
                    )
                )
                if reply_decision.action in _REPLY_FETCH_ACTIONS and not context.cancel_requested():
                    self._fetch_sub_comments(
                        run=run,
                        scope=scope,
                        root_comment=comment,
                        provider_config=provider_config,
                        context=context,
                        stats=stats,
                        reply_action=reply_decision.action,
                        reply_target=reply_decision.target,
                    )

            # target 是“是否继续请求下一页”的软目标；已付费返回的整页必须全部保留。
            if comment_target is not None and fetched >= comment_target:
                return
            if comment_action == "probe_first_page":
                return
            advance = advance_comments(
                platform=platform,
                state=pagination_state,
                body=executed.body,
            )
            if not advance.should_continue:
                return
            assert advance.next_state is not None
            pagination_state = dict(advance.next_state)

        raise RuntimeError("TikHub Comments 达到技术分页上限")

    def _fetch_sub_comments(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        root_comment: CanonicalCommentV1,
        provider_config: ProviderConfig,
        context: JobExecutionContextProtocol,
        stats: _ScopeStats,
        reply_action: str,
        reply_target: int | None,
    ) -> None:
        platform = _tikhub_platform(scope.platform)
        pagination_state: dict[str, object] = {}
        fetched = 0

        for _page_no in range(1, _MAX_SUB_COMMENT_PAGES + 1):
            if context.cancel_requested():
                return
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
            stats.sub_comment_requests += 1

            raw_items = extract_sub_comment_items(platform, executed.body)
            for index, raw_item in enumerate(raw_items):
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
                        observed_at=self._observed_at(),
                        external_content_id=root_comment.external_content_id,
                        root_comment_id=root_comment.external_comment_id,
                    ),
                    item_locator=f"sub_comments.items[{index}]",
                    is_root=False,
                )
                if reply.external_content_id != root_comment.external_content_id:
                    raise ValueError("TikHub Reply 与 Content 身份不一致")
                if reply.root_comment_id != root_comment.external_comment_id:
                    raise ValueError("TikHub Reply 与 Root Comment 身份不一致")
                self._content_writer.ingest_comment(canonical=reply, fence=context.fence)
                fetched += 1

            # target 是“是否继续请求下一页”的软目标；当前响应整页不能在本地截断。
            if reply_target is not None and fetched >= reply_target:
                return
            if reply_action == "probe_first_page":
                return
            advance = advance_sub_comments(
                platform=platform,
                state=pagination_state,
                body=executed.body,
            )
            if not advance.should_continue:
                return
            assert advance.next_state is not None
            pagination_state = dict(advance.next_state)

        raise RuntimeError("TikHub SubComments 达到技术分页上限")

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
            return self._replay_completed_call(request=request, prepared=prepared)
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
                error_code=outcome.attempt.error_code or outcome.attempt.dispatch_status,
                retryable=outcome.attempt.dispatch_status in {"not_sent", "unknown"},
            )
        if outcome.attempt.http_status is not None and outcome.attempt.http_status >= 400:
            raise _ProviderCallFailed(
                error_code=outcome.attempt.error_code or f"http_{outcome.attempt.http_status}",
                retryable=_retryable_http_status(outcome.attempt.http_status),
            )
        if outcome.artifact is None:
            raise RuntimeError("TikHub completed Attempt 缺少 Raw Artifact")

        envelope = self._raw_artifacts.replay(outcome.artifact)
        body = _response_body(envelope.response.body if envelope.response is not None else None)
        return _ExecutedCall(
            request_id=prepared.request.id,
            attempt_id=prepared.attempt.id,
            raw_artifact_id=outcome.artifact.id,
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
                artifact = PostgresArtifactMetadataRepository(session).get_by_storage_key(storage_key)
        finally:
            session.close()
        if artifact is None or artifact.id != expected_artifact_id:
            raise RuntimeError("Provider Attempt 的 Raw Artifact 元数据不存在或来源不一致")
        return artifact

    def _load_provider_config(self, provider_config_id: UUID) -> ProviderConfig:
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


def _platform_runtime_config(run: CollectionRunRecord, platform: str) -> _PlatformRuntimeConfig:
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
    return _PlatformRuntimeConfig(
        provider_config_id=parsed_config_id,
        config={str(key): value for key, value in config.items()},
    )


def _validate_decision_policy(run: CollectionRunRecord) -> None:
    detail_policy = run.config_snapshot.get("detail_policy", "on_change")
    comment_policy = run.config_snapshot.get("comment_policy", "adaptive")
    if detail_policy != "on_change":
        raise ValueError("Collection Scope Runtime 当前只支持 detail_policy=on_change")
    if comment_policy != "adaptive":
        raise ValueError("Collection Scope Runtime 当前只支持 comment_policy=adaptive")


def _capability(platform: TikHubPlatform) -> ProviderPlatformCapabilityV1:
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
    if value not in {"xhs", "douyin", "weibo", "bilibili", "kuaishou"}:
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
