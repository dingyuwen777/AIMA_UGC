"""Worker 进程 Platform 与持久化 Job Runtime 装配。"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import SecretStr

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
)
from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
    PostgresCollectionRunExecutionGateway,
)
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from aima_ugc.modules.collection.collection_run_executor import CollectionRunExecutor
from aima_ugc.modules.collection.collection_run_job import (
    CollectionRunJobHandler,
    register_collection_run_job,
)
from aima_ugc.modules.collection.providers import (
    ProviderTransport,
    ProviderTransportRequest,
    ProviderTransportResponse,
    RawArtifactService,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.jobs import JobReaper, JobRegistry, JobWorker
from aima_ugc.platform.security import read_secret_file, validate_secret_ref
from aima_ugc.platform.storage import ArtifactService

from .collection_scope import TikHubCollectionScopeExecutor
from .runtime import PlatformRuntime, create_platform_runtime


class _TikHubOneShotTransport:
    """每次发送都关闭自持 HTTP Client，避免 Worker 默认装配泄漏连接资源。"""

    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url

    def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
        with TikHubHttpTransport(base_url=self._base_url) as transport:
            return transport.send(request)


def _default_transport_factory(provider_config: ProviderConfig) -> ProviderTransport:
    return _TikHubOneShotTransport(base_url=provider_config.base_url)


def _default_secret_resolver(runtime: PlatformRuntime) -> Callable[[str], SecretStr]:
    def resolve(secret_ref: str) -> SecretStr:
        validated_ref = validate_secret_ref(secret_ref)
        return read_secret_file(runtime.settings.secret_dir / validated_ref)

    return resolve


def create_worker_runtime(*, settings: PlatformSettings | None = None) -> PlatformRuntime:
    """创建 Worker 所需的业务无关 Platform runtime。"""
    return create_platform_runtime("worker", settings=settings)


def create_collection_job_registry(
    *,
    runtime: PlatformRuntime,
    transport_factory: Callable[[ProviderConfig], ProviderTransport] | None = None,
    secret_resolver: Callable[[str], SecretStr] | None = None,
) -> JobRegistry:
    """用既有 Collection/Provider/Raw 组件组装正式 collection.run.v1 Registry。"""
    artifact_service = ArtifactService(
        metadata=PostgresArtifactMetadataGateway(runtime.database.new_session),
        store=runtime.artifact_store,
    )
    raw_artifacts = RawArtifactService(
        artifacts=artifact_service,
        store=runtime.artifact_store,
    )
    scope_executor = TikHubCollectionScopeExecutor(
        session_factory=runtime.database.new_session,
        raw_artifacts=raw_artifacts,
        transport_factory=transport_factory or _default_transport_factory,
        secret_resolver=secret_resolver or _default_secret_resolver(runtime),
    )
    executor = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(runtime.database.new_session),
        scope_executor=scope_executor,
    )
    registry = JobRegistry()
    register_collection_run_job(registry, CollectionRunJobHandler(executor))
    return registry


def create_job_worker(
    *,
    runtime: PlatformRuntime,
    registry: JobRegistry,
    worker_id: str,
    lease_seconds: int,
    retry_delay_seconds: int,
) -> JobWorker:
    """用正式 DatabaseRuntime 组装一个 Job Worker。"""
    return JobWorker(
        session_factory=runtime.database.new_session,
        registry=registry,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        retry_delay_seconds=retry_delay_seconds,
    )


def create_job_reaper(
    *,
    runtime: PlatformRuntime,
    registry: JobRegistry,
    retry_delay_seconds: int,
) -> JobReaper:
    """用正式 DatabaseRuntime 组装 Platform Reaper。"""
    return JobReaper(
        session_factory=runtime.database.new_session,
        registry=registry,
        retry_delay_seconds=retry_delay_seconds,
    )
