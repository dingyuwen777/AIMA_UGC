"""FastAPI 进程入口。"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, cast

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
from aima_ugc.bootstrap.content_media_http import install_content_media_routes
from aima_ugc.bootstrap.feishu_auth_http import build_feishu_identity, install_feishu_auth_routes
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
        # ⚠️ `identity_resolver` 必须**在调用底层工厂之前**解析出来，再显式传下去：
        # 底层 `create_app` 的签名是关键字参数，而这里原本是靠 `kwargs.get(...)` 事后读取。
        # 飞书 Resolver 需要注入真实 Session 工厂，无法在 `create_app()` 之后再补。
        raw_kwargs = cast("dict[str, object]", kwargs)
        if "identity_resolver" not in raw_kwargs:
            # 未显式注入时按配置装配：配了飞书 → 飞书 Resolver；没配 → 开发身份（现状不变）。
            resolved_identity, feishu_routes = build_feishu_identity()
            raw_kwargs["identity_resolver"] = resolved_identity
        else:
            feishu_routes = None

        application = factory(*args, **cast("Any", raw_kwargs))
        install_content_analysis_capability_route(application)
        install_content_media_routes(application)
        resolved_identity = (
            cast(
                IdentityResolver,
                raw_kwargs.get("identity_resolver"),
            )
            or DevelopmentIdentityResolver()
        )
        if feishu_routes is not None:
            # 登录路由只在"自己装配 Resolver"时挂载，避免注入 Resolver 的测试被额外路由影响。
            install_feishu_auth_routes(application, auth_routes=feishu_routes)
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
