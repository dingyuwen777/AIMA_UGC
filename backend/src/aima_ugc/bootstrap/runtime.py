"""四类进程共用的 Platform 装配。"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.platform.config import PlatformSettings, load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.health import ReadinessReport
from aima_ugc.platform.logging import (
    configure_service_logging,
    log_event,
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

    def check_readiness(self) -> ReadinessReport:
        database_status = "error"
        artifact_status = "error"
        log_status = "error"

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

    def close(self) -> None:
        self.database.dispose()
        shutdown_service_logging(self.logger)


def create_platform_runtime(
    service: str,
    *,
    settings: PlatformSettings | None = None,
) -> PlatformRuntime:
    """从同一配置装配 DB、Local Store 与日志。"""
    resolved_settings = load_settings() if settings is None else settings
    logger = configure_service_logging(service=service, settings=resolved_settings)
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
