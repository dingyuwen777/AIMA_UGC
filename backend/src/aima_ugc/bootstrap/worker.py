"""Worker 进程 Platform 与持久化 Job Runtime 装配。"""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock

from pydantic import SecretStr

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
)
from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
    PostgresCollectionRunExecutionGateway,
)
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from aima_ugc.modules.analysis.content_analysis_job import (
    ContentAnalysisJobHandler,
    ContentAnalysisPlanJobHandler,
    register_content_analysis_job,
)
from aima_ugc.modules.collection.collection_run_executor import CollectionRunExecutor
from aima_ugc.modules.collection.collection_run_job import (
    CollectionRunJobHandler,
    register_collection_run_job,
)
from aima_ugc.modules.collection.providers import ProviderTransport, RawArtifactService
from aima_ugc.modules.ingestion import ImportJobHandler, register_import_job
from aima_ugc.modules.ingestion.historical_jobs import register_historical_jobs
from aima_ugc.modules.reporting.data_export_job import (
    DataExportJobHandler,
    register_data_export_job,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.jobs import JobReaper, JobRegistry, JobWorker
from aima_ugc.platform.security import read_secret_file, validate_secret_ref
from aima_ugc.platform.storage import ArtifactService

from .analysis_worker import (
    PostgresContentAnalysisJobExecutor,
    PostgresContentAnalysisPlanJobExecutor,
    create_analysis_job_terminal_callback,
)
from .collection_scope import TikHubCollectionScopeExecutor
from .export_worker import PostgresDataExportJobExecutor, export_job_terminal_callback
from .historical_import_worker import (
    PostgresHistoricalImportJobExecutor,
    historical_job_terminal_callback,
)
from .import_worker import PostgresImportJobExecutor, import_job_terminal_callback
from .runtime import PlatformRuntime, create_platform_runtime


class _TikHubTransportPool:
    """按已验证 Base URL 复用进程级 httpx Client，并由 PlatformRuntime 统一关闭。"""

    def __init__(self) -> None:
        self._transports: dict[str, TikHubHttpTransport] = {}
        self._lock = Lock()

    def __call__(self, provider_config: ProviderConfig) -> ProviderTransport:
        with self._lock:
            transport = self._transports.get(provider_config.base_url)
            if transport is None:
                transport = TikHubHttpTransport(base_url=provider_config.base_url)
                self._transports[provider_config.base_url] = transport
            return transport

    def close(self) -> None:
        with self._lock:
            transports = tuple(self._transports.values())
            self._transports.clear()
        for transport in transports:
            transport.close()


def _default_secret_resolver(runtime: PlatformRuntime) -> Callable[[str], SecretStr]:
    def resolve(secret_ref: str) -> SecretStr:
        validated_ref = validate_secret_ref(secret_ref)
        secret_root = runtime.settings.external_secret_root
        return read_secret_file(
            secret_root / validated_ref,
            root=secret_root,
        )

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
    resolved_transport_factory = transport_factory
    if resolved_transport_factory is None:
        pool = _TikHubTransportPool()
        runtime.add_resource_closer(pool.close)
        resolved_transport_factory = pool
    scope_executor = TikHubCollectionScopeExecutor(
        session_factory=runtime.database.new_session,
        raw_artifacts=raw_artifacts,
        transport_factory=resolved_transport_factory,
        secret_resolver=secret_resolver or _default_secret_resolver(runtime),
    )
    executor = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(runtime.database.new_session),
        scope_executor=scope_executor,
    )
    registry = JobRegistry()
    register_collection_run_job(registry, CollectionRunJobHandler(executor))
    register_import_job(
        registry,
        ImportJobHandler(PostgresImportJobExecutor(runtime)),
        terminal_callback=import_job_terminal_callback,
    )
    register_historical_jobs(
        registry,
        PostgresHistoricalImportJobExecutor(runtime),
        terminal_callback=historical_job_terminal_callback,
    )
    register_content_analysis_job(
        registry,
        ContentAnalysisJobHandler(PostgresContentAnalysisJobExecutor(runtime)),
        terminal_callback=create_analysis_job_terminal_callback(runtime),
        planner_handler=ContentAnalysisPlanJobHandler(
            PostgresContentAnalysisPlanJobExecutor(runtime)
        ),
        planner_terminal_callback=create_analysis_job_terminal_callback(runtime),
    )
    register_data_export_job(
        registry,
        DataExportJobHandler(PostgresDataExportJobExecutor(runtime)),
        terminal_callback=export_job_terminal_callback,
    )
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
