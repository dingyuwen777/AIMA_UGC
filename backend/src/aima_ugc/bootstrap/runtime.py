"""四类进程共用的 Platform 装配。"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError

from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.platform.capacity import detect_resources, select_job_window
from aima_ugc.platform.config import PlatformSettings, load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.health import CheckStatus, ReadinessReport
from aima_ugc.platform.logging import (
    configure_service_logging,
    log_event,
    log_exception_event,
    shutdown_service_logging,
)
from aima_ugc.platform.security import SecretFileError


def _directory_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".aima-readiness-{uuid4().hex}"
        with probe.open("xb") as handle:
            handle.write(b"ok")
            handle.flush()
            os.fsync(handle.fileno())
        probe.unlink()
        return True
    except OSError:
        return False


@dataclass(slots=True)
class PlatformRuntime:
    """进程可复用的业务无关运行组件。"""

    service: str
    settings: PlatformSettings
    database: DatabaseRuntime
    artifact_store: LocalArtifactStore
    logger: logging.Logger
    _resource_closers: list[Callable[[], None]] = field(default_factory=list, repr=False)
    _last_job_windows: dict[str, int] = field(default_factory=dict, repr=False)

    def job_window(self, kind: str, *, ceiling: int) -> int:
        """每次投放前读取实际配额/内存压力，只在值变化时记录调节事件。"""

        resources = detect_resources()
        selected = select_job_window(resources, ceiling=ceiling)
        previous = self._last_job_windows.get(kind)
        if previous != selected:
            log_event(
                self.logger,
                logging.INFO,
                "capacity.job_window_selected",
                "Job 投放窗口调整",
                kind=kind,
                previous_jobs=previous,
                selected_jobs=selected,
                reason=("resource_pressure" if selected < ceiling else "resource_available"),
                cpu_cores=resources.cpu_cores,
                memory_available_mib=(
                    resources.memory_available_bytes // (1024 * 1024)
                    if resources.memory_available_bytes is not None
                    else None
                ),
            )
            self._last_job_windows[kind] = selected
        return selected

    def check_readiness(self) -> ReadinessReport:
        database_status: CheckStatus = "error"
        artifact_status: CheckStatus = "error"
        log_status: CheckStatus = "error"

        try:
            if self.database.ping():
                database_status = "ok"
        except OSError, SecretFileError, SQLAlchemyError:
            database_status = "error"

        try:
            self.artifact_store.ensure_ready()
            artifact_status = "ok"
        except OSError:
            artifact_status = "error"

        if _directory_writable(self.settings.log_dir):
            log_status = "ok"

        return ReadinessReport(
            database=database_status,
            artifact_store=artifact_status,
            log_directory=log_status,
        )

    def add_resource_closer(self, closer: Callable[[], None]) -> None:
        """注册进程级外部资源；Runtime.close() 统一释放。"""
        self._resource_closers.append(closer)

    def close(self) -> None:
        while self._resource_closers:
            closer = self._resource_closers.pop()
            try:
                closer()
            except Exception as exc:
                log_exception_event(
                    self.logger,
                    logging.ERROR,
                    "service.resource_close_failed",
                    "runtime resource close failed",
                    exc,
                )
        self.database.dispose()
        shutdown_service_logging(self.logger)


def create_platform_runtime(
    service: str,
    *,
    settings: PlatformSettings | None = None,
    log_instance: UUID | None = None,
) -> PlatformRuntime:
    """从同一配置装配 DB、Local Store 与日志。"""
    resolved_settings = load_settings() if settings is None else settings
    logger = configure_service_logging(
        service=service,
        settings=resolved_settings,
        log_instance=log_instance,
    )
    runtime = PlatformRuntime(
        service=service,
        settings=resolved_settings,
        database=DatabaseRuntime(resolved_settings),
        artifact_store=LocalArtifactStore(resolved_settings.artifact_dir),
        logger=logger,
    )
    log_event(
        logger,
        logging.INFO,
        "service.started",
        "Platform 运行基础已装配",
        timezone="Asia/Shanghai",
    )
    return runtime
