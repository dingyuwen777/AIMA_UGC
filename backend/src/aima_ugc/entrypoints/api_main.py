"""FastAPI 进程入口。"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from fastapi import FastAPI

from aima_ugc.bootstrap.analysis_capability_http import (
    install_content_analysis_capability_route,
)
from aima_ugc.bootstrap.api import HealthResponse, ReadinessChecks, ReadinessResponse
from aima_ugc.bootstrap.api import create_app as _create_app


def _with_content_analysis_capability[**_P](
    factory: Callable[_P, FastAPI],
) -> Callable[_P, FastAPI]:
    """在最终 API assembly 中增加不泄露 Secret 的 Analysis Capability。"""

    @wraps(factory)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> FastAPI:
        application = factory(*args, **kwargs)
        install_content_analysis_capability_route(application)
        return application

    return wrapped


create_app = _with_content_analysis_capability(_create_app)

__all__ = [
    "HealthResponse",
    "ReadinessChecks",
    "ReadinessResponse",
    "app",
    "create_app",
]

app = create_app()
