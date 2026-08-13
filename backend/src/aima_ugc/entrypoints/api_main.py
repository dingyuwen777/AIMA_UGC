"""FastAPI 进程入口。"""

from aima_ugc.bootstrap.api import (
    HealthResponse,
    ReadinessChecks,
    ReadinessResponse,
    create_app,
)

__all__ = [
    "HealthResponse",
    "ReadinessChecks",
    "ReadinessResponse",
    "app",
    "create_app",
]

app = create_app()
