"""Stage 7 TikHub Collection Scope 的生产执行组合层。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.collection_content import (
    PostgresCollectionContentStateReader,
    PostgresFencedCollectionIngestionWriter,
)
from aima_ugc.adapters.persistence.postgres.collection_provider_execution import (
    PostgresFencedProviderAttemptPreparer,
)
from aima_ugc.adapters.persistence.postgres.provider_dispatch import (
    PostgresProviderDispatchPersistence,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.tikhub.capabilities import TIKHUB_PLATFORM_CAPABILITIES
from aima_ugc.adapters.providers.tikhub.pricing import TikHubPricing, load_tikhub_pricing
from aima_ugc.adapters.providers.tikhub.runtime import (
    TikHubOperationCall,
    TikHubPlatform,
    advance_search,
    build_detail_call,
    build_search_call,
    extract_detail_items,
    extract_search_items,
    map_content,
    mapping_context,
)
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.contracts.collection import (
    CollectionDecisionPolicyV1,
    CollectionDecisionRequestV1,
    ContentObservationV1,
    ProviderPlatformCapabilityV1,
)
from aima_ugc.contracts.provider import ProviderRequestV1
from aima_ugc.modules.collection.collection_run_executor import CollectionScopeExecutionResult
from aima_ugc.modules.collection.decision import CollectionDecisionService
from aima_ugc.modules.collection.execution import CollectionRunRecord, CollectionScopeRecord
from aima_ugc.modules.collection.provider_dispatch import ProviderDispatchService
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransport,
    RawArtifactService,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

_MAX_SEARCH_PAGES = 100


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


@dataclass(slots=True)
class _ScopeStats:
    requested_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    search_pages: int = 0
    search_items: int = 0
    detail_requests: int = 0
    content_identities: set[tuple[str, str]] | None = None

    def __post_init__(self) -> None:
        if self.content_identities is None:
            self.content_identities = set()

    def record_content(self, content: CanonicalContentV1) -> None:
        assert self.content_identities is not None
        self.content_identities.add((content.platform, content.external_content_id))

    def payload(self) -> dict[str, object]:
        return {
            "search_pages": self.search_pages,
            "search_items": self.search_items,
            "detail_requests": self.detail_requests,
            "provider_requests": self.requested_count,
        }

    @property
    def content_count(self) -> int:
        assert self.content_identities is not None
        return len(self.content_identities)


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
        self._content_state = PostgresCollectionContentStateReader(session_factory)
        self._content_writer = PostgresFencedCollectionIngestionWriter(session_factory)
        self._decision_service = CollectionDecisionService()

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

        platform = _tikhub_platform(scope.platform)
        runtime_config = _platform_runtime_config(run, scope.platform)
        provider_config = self._load_provider_config(runtime_config.provider_config_id)
        capability = _capability(platform)
        _validate_decision_policy(run)

        stats = _ScopeStats()
        pagination_state = dict(scope.pagination_state)
        stop_reason: str | None = None

        for page_no in range(1, _MAX_SEARCH_PAGES + 1):
            if context.cancel_requested():
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
            stats.requested_count += 1
            stats.succeeded_count += 1
            stats.search_pages += 1

            items = extract_search_items(platform, executed.body)
            stats.search_items += len(items)
            for index, raw_item in enumerate(items):
                if context.cancel_requested():
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
            context.heartbeat(progress=min(99, page_no))
        else:
            stop_reason = "page_limit"

        return _result(
            status="partial_success" if stop_reason == "page_limit" else "succeeded",
            stop_reason=stop_reason,
            pagination_state=pagination_state,
            stats=stats,
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
        stats.record_content(content)

        if decision.detail_action != "fetch":
            return
        if context.cancel_requested():
            return

        detail_call = build_detail_call(_tikhub_platform(scope.platform), content)
        executed = self._execute_call(
            run=run,
            scope=scope,
            call=detail_call,
            provider_config=provider_config,
            context=context,
        )
        stats.requested_count += 1
        stats.succeeded_count += 1
        stats.detail_requests += 1

        detail_items = extract_detail_items(_tikhub_platform(scope.platform), executed.body)
        if not detail_items:
            raise ValueError("TikHub Detail 响应未包含可映射内容")
        for index, raw_item in enumerate(detail_items):
            detail_content = map_content(
                platform=_tikhub_platform(scope.platform),
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
            stats.record_content(detail_content)

    def _execute_call(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        call: TikHubOperationCall,
        provider_config: ProviderConfig,
        context: JobExecutionContextProtocol,
    ) -> _ExecutedCall:
        request_params: dict[str, object] = {
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
            raise RuntimeError(
                f"TikHub Provider Attempt 未完成: {outcome.attempt.dispatch_status}"
            )
        if outcome.attempt.http_status is not None and outcome.attempt.http_status >= 400:
            raise RuntimeError(f"TikHub Provider 返回 HTTP {outcome.attempt.http_status}")
        if outcome.artifact is None:
            raise RuntimeError("TikHub completed Attempt 缺少 Raw Artifact")

        envelope = self._raw_artifacts.replay(outcome.artifact)
        if envelope.response is None or not isinstance(envelope.response.body, dict):
            raise ValueError("TikHub Raw 响应 body 必须为 JSON Object")
        return _ExecutedCall(
            request_id=prepared.request.id,
            attempt_id=prepared.attempt.id,
            raw_artifact_id=outcome.artifact.id,
            body=cast(dict[str, object], envelope.response.body),
        )

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


def _platform_runtime_config(run: CollectionRunRecord, platform: str) -> _PlatformRuntimeConfig:
    snapshot = run.config_snapshot
    platforms = snapshot.get("platforms")
    if not isinstance(platforms, list):
        raise ValueError("Collection Run Snapshot 缺少 platforms")
    matches = [
        item
        for item in platforms
        if isinstance(item, dict) and item.get("platform") == platform
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
    status: str,
    stop_reason: str | None,
    pagination_state: dict[str, object],
    stats: _ScopeStats,
) -> CollectionScopeExecutionResult:
    return CollectionScopeExecutionResult(
        status=cast(object, status),
        stop_reason=stop_reason,
        pagination_state=dict(pagination_state),
        stats=stats.payload(),
        requested_count=stats.requested_count,
        succeeded_count=stats.succeeded_count,
        failed_count=stats.failed_count,
        content_count=stats.content_count,
        comment_count=0,
    )


__all__ = ["TikHubCollectionScopeExecutor"]
