"""管理员 LLM/TikHub Provider Configuration HTTP 路由。"""

from __future__ import annotations

import weakref
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Query, Request, status

from aima_ugc.contracts.administration import (
    ProviderConfigCreateRequest,
    ProviderConfigListResponse,
    ProviderConfigResponse,
    ProviderConfigUpdateRequest,
    ProviderKind,
)
from aima_ugc.contracts.http import HttpErrorResponse
from aima_ugc.modules.administration.http import AdministrationHttpService
from aima_ugc.modules.identity import (
    DevelopmentIdentityResolver,
    IdentityResolver,
    Principal,
)

from .runtime import PlatformRuntime, create_platform_runtime


class _ProviderConfigurationRouteContext:
    """为独立安装路由提供惰性 Service；OpenAPI 生成不会触发运行时依赖。"""

    def __init__(
        self,
        *,
        administration_service: AdministrationHttpService | None,
        identity_resolver: IdentityResolver | None,
    ) -> None:
        self._injected_service = administration_service
        self._identity_resolver = identity_resolver or DevelopmentIdentityResolver()
        self._runtime: PlatformRuntime | None = None
        self._service: AdministrationHttpService | None = administration_service

    def service(self) -> AdministrationHttpService:
        if self._service is not None:
            return self._service
        runtime = create_platform_runtime("api")
        from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService

        self._runtime = runtime
        self._service = PostgresAdministrationHttpService(runtime)
        return self._service

    def principal(self, request: Request) -> Principal:
        return self._identity_resolver.resolve(request)

    def close(self) -> None:
        if self._runtime is not None:
            self._runtime.close()
            self._runtime = None


def install_provider_configuration_routes(
    application: FastAPI,
    *,
    administration_service: AdministrationHttpService | None = None,
    identity_resolver: IdentityResolver | None = None,
) -> None:
    """安装 Provider Configuration 管理路由，不在 Contract 构建期创建数据库运行时。"""

    context = _ProviderConfigurationRouteContext(
        administration_service=administration_service,
        identity_resolver=identity_resolver,
    )
    weakref.finalize(application, context.close)

    @application.get(
        "/api/v1/provider-configs",
        operation_id="listProviderConfigs",
        response_model=ProviderConfigListResponse,
        responses={
            403: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["administration", "provider-configs"],
    )
    def list_provider_configs(
        request: Request,
        provider_kind: Annotated[ProviderKind | None, Query()] = None,
    ) -> ProviderConfigListResponse:
        """管理员读取 Provider 安全投影；响应不含 Secret 值或 secret_ref。"""

        context.principal(request).require_administrator()
        return context.service().list_provider_configs(provider_kind=provider_kind)

    @application.post(
        "/api/v1/provider-configs",
        operation_id="createProviderConfig",
        response_model=ProviderConfigResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["administration", "provider-configs"],
    )
    def create_provider_config(
        body: ProviderConfigCreateRequest,
        request: Request,
    ) -> ProviderConfigResponse:
        """管理员创建 Provider；API Key 仅进入后端 Secret Store 写入边界。"""

        return context.service().create_provider_config(
            body,
            principal=context.principal(request),
            request_id=_request_id(request),
        )

    @application.put(
        "/api/v1/provider-configs/{provider_config_id}",
        operation_id="updateProviderConfig",
        response_model=ProviderConfigResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["administration", "provider-configs"],
    )
    def update_provider_config(
        provider_config_id: UUID,
        body: ProviderConfigUpdateRequest,
        request: Request,
    ) -> ProviderConfigResponse:
        """管理员更新 Provider；省略 API Key 时沿用旧 Secret 引用。"""

        return context.service().update_provider_config(
            provider_config_id,
            body,
            principal=context.principal(request),
            request_id=_request_id(request),
        )


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else "provider-config-request"


__all__ = ["install_provider_configuration_routes"]