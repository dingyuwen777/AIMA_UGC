"""Worker 进程 Platform 与持久化 Job Runtime 装配。"""

from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.jobs import JobReaper, JobRegistry, JobWorker

from .runtime import PlatformRuntime, create_platform_runtime


def create_worker_runtime(*, settings: PlatformSettings | None = None) -> PlatformRuntime:
    """创建 Worker 所需的业务无关 Platform runtime。"""
    return create_platform_runtime("worker", settings=settings)


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
