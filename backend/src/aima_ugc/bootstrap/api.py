"""API 进程装配与健康检查。"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response, status
from pydantic import BaseModel, ConfigDict

from aima_ugc.platform.health import ReadinessReport

from .runtime import PlatformRuntime, create_platform_runtime

ReadinessCheck = Callable[[], ReadinessReport]


class HealthResponse(BaseModel):
    """进程存活检查响应。"""

    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"]


class ReadinessChecks(BaseModel):
    """readiness 子检查，不包含异常详情。"""

    model_config = ConfigDict(extra="forbid")
    database: Literal["ok", "error"]
    artifact_store: Literal["ok", "error"]
    log_directory: Literal["ok", "error"]


class ReadinessResponse(BaseModel):
    """依赖就绪检查响应。"""

    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "error"]
    checks: ReadinessChecks


def create_app(*, readiness_check: ReadinessCheck | None = None) -> FastAPI:
    """创建 API 应用；默认 runtime 延迟到启动或第一次 readiness 检查。"""
    runtime: PlatformRuntime | None = None
    runtime_failed = False

    def get_runtime() -> PlatformRuntime | None:
        nonlocal runtime, runtime_failed
        if runtime is None and not runtime_failed:
            try:
                runtime = create_platform_runtime("api")
            except OSError, ValueError:
                runtime_failed = True
        return runtime

    def current_readiness() -> ReadinessReport:
        if readiness_check is not None:
            return readiness_check()
        resolved_runtime = get_runtime()
        if resolved_runtime is None:
            return ReadinessReport(
                database="error",
                artifact_store="error",
                log_directory="error",
            )
        return resolved_runtime.check_readiness()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if readiness_check is None:
            get_runtime()
        try:
            yield
        finally:
            if runtime is not None:
                runtime.close()

    application = FastAPI(title="AIMA_UGC API", version="0.1.0", lifespan=lifespan)

    @application.get(
        "/health/live",
        operation_id="healthLive",
        response_model=HealthResponse,
        tags=["health"],
    )
    def health_live() -> HealthResponse:
        """返回进程存活状态，不检查外部依赖。"""
        return HealthResponse(status="ok")

    @application.get(
        "/health/ready",
        operation_id="healthReady",
        response_model=ReadinessResponse,
        responses={503: {"model": ReadinessResponse}},
        tags=["health"],
    )
    def health_ready(response: Response) -> ReadinessResponse:
        """检查 PostgreSQL、Artifact 目录和日志目录，不泄露失败详情。"""
        report = current_readiness()
        response.status_code = (
            status.HTTP_200_OK if report.ready else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return ReadinessResponse(
            status="ok" if report.ready else "error",
            checks=ReadinessChecks(
                database=report.database,
                artifact_store=report.artifact_store,
                log_directory=report.log_directory,
            ),
        )

    return application
