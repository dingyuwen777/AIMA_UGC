"""FastAPI 进程入口。"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import FastAPI

from aima_ugc.bootstrap.analysis_capability_http import (
    install_content_analysis_capability_route,
)
from aima_ugc.bootstrap.api import HealthResponse, ReadinessChecks, ReadinessResponse
from aima_ugc.bootstrap.api import create_app as _create_app
from aima_ugc.bootstrap.provider_configuration_http import (
    install_provider_configuration_routes,
)


def _with_final_routes[**P](
    factory: Callable[P, FastAPI],
) -> Callable[P, FastAPI]:
    """在最终 API assembly 中增加独立 Capability 与 Provider 管理路由。"""

    @wraps(factory)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> FastAPI:
        application = factory(*args, **kwargs)
        install_content_analysis_capability_route(application)
        typed_kwargs = dict(kwargs)
        install_provider_configuration_routes(
            application,
            administration_service=typed_kwargs.get("administration_service"),
            identity_resolver=typed_kwargs.get("identity_resolver"),
        )
        return application

    return wrapped


create_app = _with_final_routes(_create_app)

__all__ = [
    "HealthResponse",
    "ReadinessChecks",
    "ReadinessResponse",
    "app",
    "create_app",
]

app = create_app()