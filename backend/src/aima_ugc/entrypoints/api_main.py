"""FastAPI 进程入口。"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import cast

from fastapi import FastAPI

from aima_ugc.bootstrap.analysis_capability_http import (
    install_content_analysis_capability_route,
)
from aima_ugc.bootstrap.analysis_scheme_lifecycle_http import (
    install_analysis_scheme_lifecycle_routes,
)
from aima_ugc.bootstrap.api import HealthResponse, ReadinessChecks, ReadinessResponse
from aima_ugc.bootstrap.api import create_app as _create_app
from aima_ugc.bootstrap.brand_vehicle_http import install_brand_vehicle_routes
from aima_ugc.bootstrap.import_revocation_http import install_import_revocation_routes
from aima_ugc.bootstrap.provider_lifecycle_http import install_provider_lifecycle_routes
from aima_ugc.bootstrap.resource_lifecycle_http import install_resource_lifecycle_routes
from aima_ugc.modules.identity import DevelopmentIdentityResolver, IdentityResolver


def _with_product_extension_routes[**P](
    factory: Callable[P, FastAPI],
) -> Callable[P, FastAPI]:
    """在最终 API assembly 中安装安全的产品扩展路由。"""

    @wraps(factory)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> FastAPI:
        application = factory(*args, **kwargs)
        install_content_analysis_capability_route(application)
        raw_kwargs = cast(dict[str, object], kwargs)
        identity_resolver = cast(
            IdentityResolver | None,
            raw_kwargs.get("identity_resolver"),
        )
        resolved_identity = identity_resolver or DevelopmentIdentityResolver()
        install_import_revocation_routes(
            application,
            identity_resolver=resolved_identity,
        )
        install_resource_lifecycle_routes(
            application,
            identity_resolver=resolved_identity,
        )
        install_provider_lifecycle_routes(
            application,
            identity_resolver=resolved_identity,
        )
        install_analysis_scheme_lifecycle_routes(
            application,
            identity_resolver=resolved_identity,
        )
        install_brand_vehicle_routes(
            application,
            identity_resolver=resolved_identity,
        )
        return application

    return wrapped


create_app = _with_product_extension_routes(_create_app)

__all__ = [
    "HealthResponse",
    "ReadinessChecks",
    "ReadinessResponse",
    "app",
    "create_app",
]

app = create_app()