"""Stage 8A tikhub_test 可选 PostgreSQL 模式的正式来源链装配。"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import SecretStr

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
)
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_content import (
    PostgresFencedCollectionIngestionWriter,
)
from aima_ugc.adapters.persistence.postgres.collection_provider_execution import (
    PostgresFencedProviderAttemptPreparer,
)
from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
    PostgresCollectionRunExecutionGateway,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.provider_dispatch import (
    PostgresProviderDispatchPersistence,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.tikhub.pricing import load_tikhub_pricing
from aima_ugc.adapters.providers.tikhub.runtime import TikHubOperationCall, TikHubPlatform
from aima_ugc.bootstrap.manual_ingestion import require_stage8a_schema
from aima_ugc.bootstrap.runtime import PlatformRuntime, create_platform_runtime
from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.contracts.collection import CollectionDecisionPolicyV1
from aima_ugc.contracts.provider import ProviderRequestV1
from aima_ugc.modules.collection.candidates import CandidateKind
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionRunRecord,
    CollectionScopeDefinition,
    CollectionScopeRecord,
)
from aima_ugc.modules.collection.provider_dispatch import ProviderDispatchService
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransport,
    ProviderTransportRequest,
    ProviderTransportResponse,
    RawArtifactService,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.security import read_secret_file
from aima_ugc.platform.storage import ArtifactService

_DEBUG_JOB_PREFIX = "debug.tikhub.collection"


@dataclass(frozen=True, slots=True)
class TikHubDebugDatabaseDispatch:
    """一次真实 TikHub 调试请求在正式来源链中的稳定引用。"""

    provider_request_id: UUID
    provider_attempt_id: UUID
    raw_artifact_id: UUID
    observed_at: datetime
    response: ProviderTransportResponse


class _MirroringTransport:
    """真实 Transport 只发送一次；响应先镜像到调试文件，再交给正式 Raw 链。"""

    def __init__(
        self,
        *,
        inner: ProviderTransport,
        mirror_response: Callable[[ProviderTransportResponse], None],
    ) -> None:
        self._inner = inner
        self._mirror_response = mirror_response
        self.response: ProviderTransportResponse | None = None
        self.mirror_error: Exception | None = None

    def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
        response = self._inner.send(request)
        self.response = response
        try:
            self._mirror_response(response)
        except Exception as exc:
            # 让正式 Attempt/Raw 先收敛；之后再把调试文件失败报告给调用方。
            self.mirror_error = exc
        return response


class TikHubDebugDatabaseSession:
    """把 tikhub_test 的同一次网络调用接入正式 Collection/Provider/Raw/Ingestion。"""

    def __init__(
        self,
        *,
        runtime: PlatformRuntime,
        platform: TikHubPlatform,
        keywords: tuple[str, ...],
        run_id: str,
        provider_config: ProviderConfig,
        credential: SecretStr,
        search_config: dict[str, object],
        policy: CollectionDecisionPolicyV1,
        provider_timeout_seconds: float,
    ) -> None:
        self._runtime = runtime
        self._platform = platform
        self._provider_config = provider_config
        self._credential = credential
        self._pricing = load_tikhub_pricing()
        self._lease_seconds = max(600, int(provider_timeout_seconds * 2) + 60)
        self._attempt_preparer = PostgresFencedProviderAttemptPreparer(runtime.database.new_session)
        self._scope_gateway = PostgresCollectionRunExecutionGateway(runtime.database.new_session)
        self._content_writer = PostgresFencedCollectionIngestionWriter(runtime.database.new_session)
        artifact_service = ArtifactService(
            metadata=PostgresArtifactMetadataGateway(runtime.database.new_session),
            store=runtime.artifact_store,
        )
        self._raw_artifacts = RawArtifactService(
            artifacts=artifact_service,
            store=runtime.artifact_store,
        )
        self._run, self._scopes, self._fence = self._create_execution(
            keywords=keywords,
            run_id=run_id,
            search_config=search_config,
            policy=policy,
        )
        self._scope_by_keyword = {scope.source_value: scope for scope in self._scopes}
        self._closed = False

    def dispatch(
        self,
        *,
        keyword: str,
        call: TikHubOperationCall,
        transport: ProviderTransport,
        mirror_response: Callable[[ProviderTransportResponse], None],
    ) -> TikHubDebugDatabaseDispatch:
        """正式 Attempt 预留后执行唯一一次网络请求，并保存正式 Raw。"""
        self._require_open()
        self._heartbeat()
        scope = self._scope(keyword)
        request_params: dict[str, object] = {
            "method": call.method,
            "path": call.path,
            "params": dict(call.params),
        }
        if call.body is not None:
            request_params["body"] = dict(call.body)
        request = ProviderRequestV1.create(
            request_id=uuid4(),
            run_id=self._run.id,
            scope_id=scope.id,
            provider=self._provider_config.provider,
            platform=self._platform,
            operation=call.operation,
            request_params=request_params,
            pagination_input=dict(call.pagination_input or {}),
        )
        prepared = self._attempt_preparer.prepare_billable_attempt(
            request=request,
            provider_config_id=self._provider_config.id,
            attempt_id=uuid4(),
            billing=self._pricing.billing_for_endpoint(call.path),
            fence=self._fence,
        )
        mirrored = _MirroringTransport(
            inner=transport,
            mirror_response=mirror_response,
        )
        outcome = ProviderDispatchService(
            persistence=PostgresProviderDispatchPersistence(self._runtime.database.new_session),
            client=ProviderClient(transport=mirrored),
            raw_artifacts=self._raw_artifacts,
        ).dispatch(
            attempt_id=prepared.attempt.id,
            fence=self._fence,
            transport_request=call.transport_request(self._credential),
        )
        if mirrored.mirror_error is not None:
            raise mirrored.mirror_error
        response = mirrored.response
        if response is None:
            error = outcome.attempt.error_detail or outcome.attempt.dispatch_status
            raise RuntimeError(f"TikHub 数据库模式请求未取得确定响应: {error}")
        if outcome.artifact is None:
            raise RuntimeError("TikHub 数据库模式 completed Attempt 缺少 Raw Artifact")
        envelope = self._raw_artifacts.replay(outcome.artifact)
        if envelope.response is None:
            raise RuntimeError("TikHub 数据库模式 Raw 缺少响应体")
        return TikHubDebugDatabaseDispatch(
            provider_request_id=request.request_id,
            provider_attempt_id=outcome.attempt.id,
            raw_artifact_id=outcome.artifact.id,
            observed_at=envelope.completed_at,
            response=response,
        )

    def discover_candidate(
        self,
        *,
        provider_attempt_id: UUID,
        raw_artifact_id: UUID,
        item_kind: CandidateKind,
        item_locator: str,
        discovered_at: datetime,
    ) -> UUID:
        self._require_open()
        return self._content_writer.discover_candidate(
            provider_attempt_id=provider_attempt_id,
            raw_artifact_id=raw_artifact_id,
            item_kind=item_kind,
            item_locator=item_locator,
            discovered_at=discovered_at,
            fence=self._fence,
        )

    def record_candidate_failure(
        self,
        *,
        candidate_id: UUID,
        provider_attempt_id: UUID,
        error_code: str,
    ) -> None:
        self._content_writer.record_candidate_failure(
            candidate_id=candidate_id,
            provider_attempt_id=provider_attempt_id,
            fence=self._fence,
            result="invalid",
            error_code=error_code,
        )

    def ingest_content(self, canonical: CanonicalContentV1, *, candidate_id: UUID) -> None:
        self._content_writer.ingest_content(
            canonical=canonical,
            fence=self._fence,
            candidate_id=candidate_id,
        )

    def ingest_comment(self, canonical: CanonicalCommentV1, *, candidate_id: UUID) -> None:
        self._content_writer.ingest_comment(
            canonical=canonical,
            fence=self._fence,
            candidate_id=candidate_id,
        )

    def finish(
        self,
        *,
        error: Exception | None,
        stop_reasons: dict[str, str],
    ) -> None:
        """把 Scope/Run/Job 收敛到终态；不管理 Docker 或 Migration。"""
        if self._closed:
            return
        try:
            self._heartbeat()
            totals = {
                "requested_count": 0,
                "succeeded_count": 0,
                "failed_count": 0,
                "content_count": 0,
                "comment_count": 0,
            }
            scope_statuses: list[str] = []
            for scope in self._scopes:
                counts = self._attempt_preparer.read_scope_counts(
                    scope_id=scope.id,
                    fence=self._fence,
                )
                stats = {
                    "requested_count": counts.requested_count,
                    "succeeded_count": counts.succeeded_count,
                    "failed_count": counts.failed_count,
                    "content_count": counts.content_count,
                    "comment_count": counts.comment_count,
                }
                for name, value in stats.items():
                    totals[name] += value
                if error is not None:
                    scope_status = "failed"
                elif counts.failed_count == 0:
                    scope_status = "succeeded"
                elif counts.succeeded_count > 0:
                    scope_status = "partial_success"
                else:
                    scope_status = "failed"
                scope_statuses.append(scope_status)
                self._scope_gateway.finish_scope(
                    scope.id,
                    fence=self._fence,
                    status=scope_status,
                    stop_reason=(
                        type(error).__name__
                        if error is not None
                        else stop_reasons.get(scope.source_value)
                    ),
                    pagination_state={},
                    stats=stats,
                )

            if error is not None:
                run_status = "failed"
            elif all(status == "succeeded" for status in scope_statuses):
                run_status = "succeeded"
            elif any(status in {"succeeded", "partial_success"} for status in scope_statuses):
                run_status = "partial_success"
            else:
                run_status = "failed"

            self._scope_gateway.finish_run(
                self._run.id,
                fence=self._fence,
                status=run_status,
                requested_count=totals["requested_count"],
                succeeded_count=totals["succeeded_count"],
                failed_count=totals["failed_count"],
                content_count=totals["content_count"],
                comment_count=totals["comment_count"],
                error_summary=(
                    None if error is None else f"{type(error).__name__}: {str(error)[:1800]}"
                ),
            )
            session = self._runtime.database.new_session()
            try:
                with session.begin():
                    jobs = PostgresJobRepository(session)
                    if error is None:
                        jobs.succeed(
                            job_id=self._fence.job_id,
                            lease_token=self._fence.lease_token,
                            result={
                                "collection_run_id": str(self._run.id),
                                "status": run_status,
                            },
                        )
                    else:
                        jobs.fail_permanent(
                            job_id=self._fence.job_id,
                            lease_token=self._fence.lease_token,
                            error_code="tikhub_debug_database_failed",
                        )
            finally:
                session.close()
        finally:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._runtime.close()

    def _create_execution(
        self,
        *,
        keywords: tuple[str, ...],
        run_id: str,
        search_config: dict[str, object],
        policy: CollectionDecisionPolicyV1,
    ) -> tuple[CollectionRunRecord, tuple[CollectionScopeRecord, ...], JobExecutionFence]:
        session = self._runtime.database.new_session()
        debug_job_type = f"{_DEBUG_JOB_PREFIX}.{uuid4().hex}"
        try:
            with session.begin():
                jobs = PostgresJobRepository(session)
                job = jobs.enqueue(
                    job_type=debug_job_type,
                    payload_version="tikhub-debug-collection.v1",
                    payload={
                        "schema_version": "tikhub-debug-collection.v1",
                        "platform": self._platform,
                        "run_id": run_id,
                    },
                    internal_idempotency_key=f"{self._platform}:{run_id}",
                    request_id=None,
                    priority=100,
                    max_attempts=1,
                    timeout_seconds=86_400,
                )
                execution = CollectionExecutionService(
                    PostgresCollectionRepository(session)
                ).create_run(
                    job_id=job.id,
                    trigger_type="manual",
                    config_snapshot={
                        "schema_version": "collection-run-config.v1",
                        "detail_policy": "on_change",
                        "comment_policy": "adaptive",
                        "decision_policy": policy.model_dump(mode="json"),
                        "platforms": [
                            {
                                "platform": self._platform,
                                "provider_config_id": str(self._provider_config.id),
                                "provider": self._provider_config.provider,
                                "base_url": self._provider_config.base_url,
                                "secret_ref": self._provider_config.secret_ref,
                                "config": dict(search_config),
                            }
                        ],
                    },
                    scopes=tuple(
                        CollectionScopeDefinition(
                            platform=self._platform,
                            source_type="keyword_search",
                            source_value=keyword,
                            operation_group="content_discovery",
                        )
                        for keyword in keywords
                    ),
                )
            with session.begin():
                claimed = PostgresJobRepository(session).claim_next(
                    supported_job_types=(debug_job_type,),
                    worker_id="tikhub-test-db",
                    lease_seconds=self._lease_seconds,
                )
            if claimed is None or claimed.id != job.id or claimed.lease_token is None:
                raise RuntimeError("TikHub 调试数据库 Job 无法取得独立 Fencing Token")
        finally:
            session.close()
        fence = JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token)
        run = self._scope_gateway.start_run(execution.run.id, fence=fence)
        scopes = tuple(
            self._scope_gateway.start_scope(scope.id, fence=fence) for scope in execution.scopes
        )
        return run, scopes, fence

    def _scope(self, keyword: str) -> CollectionScopeRecord:
        scope = self._scope_by_keyword.get(keyword)
        if scope is None:
            raise RuntimeError(f"TikHub 调试数据库 Scope 不存在: {keyword}")
        return scope

    def _heartbeat(self) -> None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).heartbeat(
                    job_id=self._fence.job_id,
                    lease_token=self._fence.lease_token,
                    lease_seconds=self._lease_seconds,
                    progress=0,
                )
        finally:
            session.close()

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("TikHub 调试数据库 Session 已关闭")


def create_tikhub_debug_database_session(
    *,
    platform: TikHubPlatform,
    keywords: tuple[str, ...],
    run_id: str,
    provider_config_id: UUID,
    expected_base_url: str,
    expected_api_key: SecretStr,
    provider_timeout_seconds: float,
    search_config: dict[str, object],
    policy: CollectionDecisionPolicyV1,
) -> TikHubDebugDatabaseSession:
    """读取正式 DB/Secret 配置并建立同步调试所需的 Collection 执行父事实。"""
    runtime = create_platform_runtime("tikhub-test-db")
    try:
        require_stage8a_schema(runtime.database)
        session = runtime.database.new_session()
        try:
            with session.begin():
                provider_config = PostgresProviderConfigRepository(session).get(provider_config_id)
        finally:
            session.close()
        if provider_config is None:
            raise RuntimeError(f"Provider Config 不存在: {provider_config_id}")
        if not provider_config.enabled:
            raise RuntimeError(f"Provider Config 已禁用: {provider_config_id}")
        if provider_config.provider != "tikhub":
            raise RuntimeError("tikhub_test 数据库模式只接受 provider=tikhub")
        if provider_config.base_url != expected_base_url.rstrip("/"):
            raise RuntimeError("tikhub_test .env Base URL 与正式 Provider Config 不一致")
        credential = read_secret_file(
            runtime.settings.secret_dir / provider_config.secret_ref,
            root=runtime.settings.secret_dir,
        )
        if not hmac.compare_digest(
            credential.get_secret_value(),
            expected_api_key.get_secret_value(),
        ):
            raise RuntimeError("tikhub_test .env API Key 与正式 Provider Config Secret 不一致")
        return TikHubDebugDatabaseSession(
            runtime=runtime,
            platform=platform,
            keywords=keywords,
            run_id=run_id,
            provider_config=provider_config,
            credential=credential,
            search_config=search_config,
            policy=policy,
            provider_timeout_seconds=provider_timeout_seconds,
        )
    except Exception:
        runtime.close()
        raise


__all__ = [
    "TikHubDebugDatabaseDispatch",
    "TikHubDebugDatabaseSession",
    "create_tikhub_debug_database_session",
]
