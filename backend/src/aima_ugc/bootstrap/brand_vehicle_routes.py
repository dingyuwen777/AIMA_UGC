"""Stage 2 Brand/Vehicle 管理扩展路由安装器。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Query, Request, Response, status

from aima_ugc.contracts.brand_vehicle import (
    ActiveVehicleBrandIntegrityResponse,
    BrandCreateRequest,
    BrandListResponse,
    BrandResponse,
    BrandRole,
    BrandStatus,
    BrandUpdateRequest,
    BrandVehicleCatalogSnapshotQuery,
    BrandVehicleCatalogSnapshotResponse,
    VehicleBrandAssignmentRequest,
    VehicleBrandAssignmentResponse,
)
from aima_ugc.contracts.http import HttpErrorResponse
from aima_ugc.modules.identity import DevelopmentIdentityResolver, IdentityResolver, Principal

from .brand_vehicle_http import PostgresBrandVehicleHttpService
from .runtime import PlatformRuntime, create_platform_runtime


def install_brand_vehicle_routes(
    application: FastAPI,
    *,
    identity_resolver: IdentityResolver | None = None,
) -> None:
    """安装 Brand CRUD、车型品牌归属、完整性与统一 Snapshot 管理路由。"""

    resolver = identity_resolver or DevelopmentIdentityResolver()
    runtime: PlatformRuntime | None = None

    def service() -> PostgresBrandVehicleHttpService:
        nonlocal runtime
        if runtime is None:
            runtime = create_platform_runtime("api")
        return PostgresBrandVehicleHttpService(runtime)

    router = cast(Any, application.router)
    original_lifespan = router.lifespan_context

    @asynccontextmanager
    async def brand_vehicle_lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with original_lifespan(app):
            try:
                yield
            finally:
                if runtime is not None:
                    runtime.close()

    router.lifespan_context = brand_vehicle_lifespan

    def principal(request: Request) -> Principal:
        return resolver.resolve(request)

    @application.get(
        "/api/v1/vehicle-brands",
        operation_id="listVehicleBrands",
        response_model=BrandListResponse,
        responses={500: {"model": HttpErrorResponse}},
        tags=["administration"],
    )
    def list_vehicle_brands(
        search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
        role: Annotated[BrandRole | None, Query()] = None,
        brand_status: Annotated[BrandStatus | None, Query(alias="status")] = None,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> BrandListResponse:
        return service().list_brands(
            search=search,
            role=role,
            status=brand_status,
            offset=offset,
            limit=limit,
        )

    @application.post(
        "/api/v1/vehicle-brands",
        operation_id="createVehicleBrand",
        response_model=BrandResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
        },
        tags=["administration"],
    )
    def create_vehicle_brand(body: BrandCreateRequest, request: Request) -> BrandResponse:
        return service().create_brand(
            body,
            principal=principal(request),
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/vehicle-brands/{brand_id}",
        operation_id="getVehicleBrand",
        response_model=BrandResponse,
        responses={404: {"model": HttpErrorResponse}},
        tags=["administration"],
    )
    def get_vehicle_brand(brand_id: UUID) -> BrandResponse:
        return service().get_brand(brand_id)

    @application.patch(
        "/api/v1/vehicle-brands/{brand_id}",
        operation_id="updateVehicleBrand",
        response_model=BrandResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
        },
        tags=["administration"],
    )
    def update_vehicle_brand(
        brand_id: UUID,
        body: BrandUpdateRequest,
        request: Request,
    ) -> BrandResponse:
        return service().update_brand(
            brand_id,
            body,
            principal=principal(request),
            request_id=_request_id(request),
        )

    @application.delete(
        "/api/v1/vehicle-brands/{brand_id}",
        operation_id="deleteVehicleBrand",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
        },
        tags=["administration"],
    )
    def delete_vehicle_brand(brand_id: UUID, request: Request) -> Response:
        service().delete_brand(
            brand_id,
            principal=principal(request),
            request_id=_request_id(request),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.put(
        "/api/v1/vehicle-models/{vehicle_model_id}/brand",
        operation_id="assignVehicleModelBrand",
        response_model=VehicleBrandAssignmentResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
        },
        tags=["administration"],
    )
    def assign_vehicle_model_brand(
        vehicle_model_id: UUID,
        body: VehicleBrandAssignmentRequest,
        request: Request,
    ) -> VehicleBrandAssignmentResponse:
        return service().assign_vehicle_brand(
            vehicle_model_id,
            body,
            principal=principal(request),
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/brand-vehicle-catalog/integrity",
        operation_id="getBrandVehicleCatalogIntegrity",
        response_model=ActiveVehicleBrandIntegrityResponse,
        responses={403: {"model": HttpErrorResponse}},
        tags=["administration"],
    )
    def get_brand_vehicle_catalog_integrity(
        request: Request,
    ) -> ActiveVehicleBrandIntegrityResponse:
        principal(request).require_administrator()
        return service().get_active_vehicle_brand_integrity()

    @application.get(
        "/api/v1/brand-vehicle-catalog/snapshot",
        operation_id="getBrandVehicleCatalogSnapshot",
        response_model=BrandVehicleCatalogSnapshotResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["administration"],
    )
    def get_brand_vehicle_catalog_snapshot(
        query: Annotated[BrandVehicleCatalogSnapshotQuery, Query()],
    ) -> BrandVehicleCatalogSnapshotResponse:
        return service().get_catalog_snapshot(query)


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else str(uuid4())


__all__ = ["install_brand_vehicle_routes"]
