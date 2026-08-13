"""FastAPI 进程入口。"""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """进程存活检查响应。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


def create_app() -> FastAPI:
    """创建 API 应用。"""
    application = FastAPI(title="AIMA_UGC API", version="0.1.0")

    @application.get(
        "/health/live",
        operation_id="healthLive",
        response_model=HealthResponse,
        tags=["health"],
    )
    def health_live() -> HealthResponse:
        """返回进程存活状态，不检查外部依赖。"""
        return HealthResponse(status="ok")

    return application


app = create_app()
