"""Stage 3 API 覆盖层：只替换 Excel/Historical 创建 Contract，其余路由复用稳定基线。"""

from __future__ import annotations

import inspect
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError

from aima_ugc.contracts.stage3_import import (
    HistoricalCampaignCreateRequest,
    LocalDataImportCampaignCreateRequest,
)

from . import _api_base as _base
from ._api_base import *  # noqa: F403

_REPLACED_CREATE_ROUTES = {
    ("/api/v1/import-batches", "POST"),
    ("/api/v1/data-import-campaigns/server", "POST"),
    ("/api/v1/historical-import-campaigns", "POST"),
    ("/api/v1/data-import-campaigns/local", "POST"),
}


def create_app(
    *,
    readiness_check: _base.ReadinessCheck | None = None,
    import_service: _base.ImportHttpService | None = None,
    content_service: _base.ContentHttpService | None = None,
    reporting_service: _base.ReportingHttpService | None = None,
    collection_service: _base.CollectionHttpService | None = None,
    strategy_service: _base.CollectionStrategyHttpService | None = None,
    historical_import_service: _base.HistoricalImportHttpService | None = None,
    administration_service: _base.AdministrationHttpService | None = None,
    product_service: _base.ProductHttpService | None = None,
    identity_resolver: _base.IdentityResolver | None = None,
    analysis_taxonomy_loader: _base.PromptTaxonomyLoader | None = None,
) -> _base.FastAPI:
    """构建原应用后原位替换三个 Stage 3 创建能力；Stage 6 完成前保持此迁移边界集中可删。"""

    application = _base.create_app(
        readiness_check=readiness_check,
        import_service=import_service,
        content_service=content_service,
        reporting_service=reporting_service,
        collection_service=collection_service,
        strategy_service=strategy_service,
        historical_import_service=historical_import_service,
        administration_service=administration_service,
        product_service=product_service,
        identity_resolver=identity_resolver,
        analysis_taxonomy_loader=analysis_taxonomy_loader,
    )
    current_import_service = cast(
        Any,
        _route_nonlocal(
            application,
            path="/api/v1/import-batches",
            method="POST",
            name="current_import_service",
        ),
    )
    current_historical_import_service = cast(
        Any,
        _route_nonlocal(
            application,
            path="/api/v1/historical-import-campaigns",
            method="POST",
            name="current_historical_import_service",
        ),
    )
    application.router.routes[:] = [
        route
        for route in application.router.routes
        if not any(
            getattr(route, "path", None) == path and method in getattr(route, "methods", set())
            for path, method in _REPLACED_CREATE_ROUTES
        )
    ]
    router = APIRouter()

    @router.post(
        "/api/v1/import-batches",
        operation_id="createImportBatch",
        response_model=_base.ImportBatchCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            409: {"model": _base.HttpErrorResponse},
            413: {"model": _base.HttpErrorResponse},
            422: {"model": _base.HttpErrorResponse},
            500: {"model": _base.HttpErrorResponse},
        },
        tags=["imports"],
    )
    async def create_import_batch(
        request: Request,
        file: Annotated[UploadFile, File()],
        brand_ids: Annotated[tuple[UUID, ...], Form()] = (),
    ) -> _base.ImportBatchCreatedResponse:
        """Excel Search 不适用；空 Brand Scope 表示冻结全部 active Brand。"""

        form = await request.form()
        items = list(form.multi_items())
        allowed = {"file", "brand_ids"}
        file_items = [value for key, value in items if key == "file"]
        brand_items = [value for key, value in items if key == "brand_ids"]
        if (
            any(key not in allowed for key, _ in items)
            or len(file_items) != 1
            or file_items[0] is not file
            or len(brand_items) != len(brand_ids)
            or len(brand_ids) > 100
            or len(brand_ids) != len(set(brand_ids))
        ):
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("body", "brand_ids"),
                        "msg": "multipart 只允许一个 file 与不重复的 brand_ids",
                        "input": None,
                        "ctx": {"error": ValueError("非法 Excel Brand Filter")},
                    }
                ]
            )
        try:
            return await _base.run_in_threadpool(
                current_import_service().create_import,
                filename=file.filename or "",
                content_type=file.content_type,
                source=file.file,
                brand_ids=tuple(brand_ids),
                request_id=_base._request_id(request),
            )
        finally:
            await file.close()

    @router.post(
        "/api/v1/data-import-campaigns/server",
        operation_id="createServerDataImportCampaign",
        response_model=_base.HistoricalCampaignCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            400: {"model": _base.HttpErrorResponse},
            409: {"model": _base.HttpErrorResponse},
            422: {"model": _base.HttpErrorResponse},
            500: {"model": _base.HttpErrorResponse},
        },
        tags=["imports"],
    )
    @router.post(
        "/api/v1/historical-import-campaigns",
        operation_id="createHistoricalImportCampaign",
        response_model=_base.HistoricalCampaignCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            400: {"model": _base.HttpErrorResponse},
            409: {"model": _base.HttpErrorResponse},
            422: {"model": _base.HttpErrorResponse},
            500: {"model": _base.HttpErrorResponse},
        },
        tags=["imports"],
    )
    def create_historical_import_campaign(
        body: HistoricalCampaignCreateRequest,
        request: Request,
    ) -> _base.HistoricalCampaignCreatedResponse:
        """创建服务端 Historical Campaign，并由 Service 冻结 Brand/Vehicle Snapshot。"""

        return current_historical_import_service().create_campaign(
            body,
            request_id=_base._request_id(request),
        )

    @router.post(
        "/api/v1/data-import-campaigns/local",
        operation_id="createLocalDataImportCampaign",
        response_model=_base.LocalDataImportCampaignCreatedResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": _base.HttpErrorResponse},
            409: {"model": _base.HttpErrorResponse},
            422: {"model": _base.HttpErrorResponse},
            500: {"model": _base.HttpErrorResponse},
        },
        tags=["imports"],
    )
    def create_local_data_import_campaign(
        body: LocalDataImportCampaignCreateRequest,
        request: Request,
    ) -> _base.LocalDataImportCampaignCreatedResponse:
        """创建本地上传 Campaign；不接受 Keyword Pack/Vehicle Model 过滤字段。"""

        return current_historical_import_service().create_local_campaign(
            body,
            request_id=_base._request_id(request),
        )

    application.include_router(router)
    application.openapi_schema = None
    return application


def _route_nonlocal(
    application: _base.FastAPI,
    *,
    path: str,
    method: str,
    name: str,
) -> object:
    """迁移期从原端点闭包取得同一 Service Resolver，避免复制 Runtime/异常处理装配。"""

    for route in application.routes:
        if getattr(route, "path", None) != path or method not in getattr(route, "methods", set()):
            continue
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            break
        value = inspect.getclosurevars(endpoint).nonlocals.get(name)
        if value is not None:
            return value
        break
    raise RuntimeError(f"Stage 3 API 无法恢复 {path} 的 {name}")


__all__ = [*getattr(_base, "__all__", ()), "create_app"]
