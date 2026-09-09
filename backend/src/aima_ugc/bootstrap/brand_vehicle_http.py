"""Stage 2 Brand/Vehicle 管理、目录准备度与冻结快照 HTTP 接线。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError

from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.contracts.brand_vehicle import (
    BrandAliasCreateRequest,
    BrandAliasResponse,
    BrandFilterScope,
    BrandListResponse,
    BrandResponse,
    BrandRole,
    BrandStatus,
    BrandUpdateRequest,
    BrandVehicleCatalogReadinessResponse,
    BrandVehicleCatalogSnapshotResponse,
    BrandCreateRequest,
    CatalogBrandAliasSnapshotItem,
    CatalogBrandSnapshotItem,
    CatalogVehicleAliasSnapshotItem,
    CatalogVehicleSnapshotItem,
    VehicleBrandAssignmentRequest,
    VehicleBrandAssignmentResponse,
)
from aima_ugc.modules.administration.http import (
    AdministrationConflict,
    AdministrationResourceNotFound,
)
from aima_ugc.modules.identity import DevelopmentIdentityResolver, IdentityResolver, Principal
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.modules.vehicles.brand_vehicle import BrandRecord, BrandVehicleCatalogSnapshot
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime, create_platform_runtime


class PostgresBrandVehicleHttpService:
    """Brand/Vehicle Stage 2 管理写与 audit_events 在同一事务提交。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def create_brand(
        self,
        body: BrandCreateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> BrandResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleRepository(session)
                brand = repository.create_brand(
                    code=body.code,
                    display_name=body.display_name,
                    role=body.role,
                    aliases=body.aliases,
                    actor_ref=principal.principal_id,
                )
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="vehicle_brand_created",
                    object_type="vehicle_brand",
                    object_id=str(brand.id),
                    detail={
                        "code": brand.code,
                        "role": brand.role,
                        "catalog_version": brand.catalog_version,
                    },
                )
                return _brand_response(repository, brand)
        except IntegrityError as exc:
            raise AdministrationConflict from exc
        finally:
            session.close()

    def list_brands(
        self,
        *,
        search: str | None,
        status_value: BrandStatus | None,
        role: BrandRole | None,
        offset: int,
        limit: int,
    ) -> BrandListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleRepository(session)
                brands, total = repository.list_brands(
                    search=search,
                    status=status_value,
                    role=role,
                    offset=offset,
                    limit=limit,
                )
                return BrandListResponse(
                    items=tuple(_brand_response(repository, brand) for brand in brands),
                    total=total,
                    catalog_version=repository.current_catalog_version(),
                    offset=offset,
                    limit=limit,
                )
        finally:
            session.close()

    def get_brand(self, brand_id: UUID) -> BrandResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleRepository(session)
                brand = repository.get_brand(brand_id)
                if brand is None:
                    raise AdministrationResourceNotFound
                return _brand_response(repository, brand)
        finally:
            session.close()

    def update_brand(
        self,
        brand_id: UUID,
        body: BrandUpdateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> BrandResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleRepository(session)
                try:
                    brand = repository.update_brand(
                        brand_id,
                        display_name=body.display_name,
                        role=body.role,
                        status=body.status,
                        actor_ref=principal.principal_id,
                    )
                except LookupError as exc:
                    raise AdministrationResourceNotFound from exc
                except RuntimeError as exc:
                    raise AdministrationConflict(str(exc)) from exc
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="vehicle_brand_updated",
                    object_type="vehicle_brand",
                    object_id=str(brand.id),
                    detail={
                        "version": brand.version,
                        "status": brand.status,
                        "role": brand.role,
                        "catalog_version": brand.catalog_version,
                    },
                )
                return _brand_response(repository, brand)
        except IntegrityError as exc:
            raise AdministrationConflict from exc
        finally:
            session.close()

    def delete_brand(
        self,
        brand_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleRepository(session)
                try:
                    deleted = repository.delete_unreferenced_brand(
                        brand_id, actor_ref=principal.principal_id
                    )
                except RuntimeError as exc:
                    raise AdministrationConflict(str(exc)) from exc
                if not deleted:
                    raise AdministrationResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="vehicle_brand_deleted",
                    object_type="vehicle_brand",
                    object_id=str(brand_id),
                    detail={},
                )
        finally:
            session.close()

    def add_alias(
        self,
        brand_id: UUID,
        body: BrandAliasCreateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> BrandResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleRepository(session)
                try:
                    alias = repository.add_brand_alias(
                        brand_id, text=body.text, actor_ref=principal.principal_id
                    )
                except LookupError as exc:
                    raise AdministrationResourceNotFound from exc
                except RuntimeError as exc:
                    raise AdministrationConflict(str(exc)) from exc
                brand = repository.get_brand(brand_id)
                if brand is None:
                    raise AdministrationResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="vehicle_brand_alias_added",
                    object_type="vehicle_brand",
                    object_id=str(brand_id),
                    detail={"alias_id": str(alias.id), "catalog_version": brand.catalog_version},
                )
                return _brand_response(repository, brand)
        except IntegrityError as exc:
            raise AdministrationConflict from exc
        finally:
            session.close()

    def delete_alias(
        self,
        brand_id: UUID,
        alias_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> BrandResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleRepository(session)
                try:
                    deleted = repository.delete_brand_alias(
                        brand_id, alias_id, actor_ref=principal.principal_id
                    )
                except LookupError as exc:
                    raise AdministrationResourceNotFound from exc
                if not deleted:
                    raise AdministrationResourceNotFound
                brand = repository.get_brand(brand_id)
                if brand is None:
                    raise AdministrationResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="vehicle_brand_alias_deleted",
                    object_type="vehicle_brand",
                    object_id=str(brand_id),
                    detail={"alias_id": str(alias_id), "catalog_version": brand.catalog_version},
                )
                return _brand_response(repository, brand)
        finally:
            session.close()

    def assign_vehicle_brand(
        self,
        vehicle_model_id: UUID,
        body: VehicleBrandAssignmentRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> VehicleBrandAssignmentResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleRepository(session)
                try:
                    vehicle = repository.assign_vehicle_brand(
                        vehicle_model_id,
                        body.brand_id,
                        actor_ref=principal.principal_id,
                    )
                except LookupError as exc:
                    raise AdministrationResourceNotFound from exc
                except RuntimeError as exc:
                    raise AdministrationConflict(str(exc)) from exc
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="vehicle_model_brand_updated",
                    object_type="vehicle_model",
                    object_id=str(vehicle_model_id),
                    detail={
                        "brand_id": None if body.brand_id is None else str(body.brand_id),
                        "version": vehicle.version,
                        "catalog_version": vehicle.catalog_version,
                    },
                )
                return VehicleBrandAssignmentResponse(
                    vehicle_model_id=vehicle.id,
                    brand_id=vehicle.brand_id,
                    version=vehicle.version,
                    catalog_version=vehicle.catalog_version,
                )
        finally:
            session.close()

    def readiness(self, *, principal: Principal) -> BrandVehicleCatalogReadinessResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleRepository(session)
                unresolved = repository.unresolved_active_vehicle_ids()
                return BrandVehicleCatalogReadinessResponse(
                    ready=not unresolved,
                    catalog_version=repository.current_catalog_version(),
                    unresolved_active_vehicle_ids=unresolved,
                )
        finally:
            session.close()

    def snapshot(
        self,
        *,
        scope: BrandFilterScope,
        brand_ids: tuple[UUID, ...],
    ) -> BrandVehicleCatalogSnapshotResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleRepository(session)
                if scope == "all_active":
                    if brand_ids:
                        raise AdministrationConflict("all_active 不接受 brand_id")
                    snapshot = repository.snapshot(brand_ids=None)
                else:
                    if not brand_ids:
                        raise AdministrationConflict("selected 必须至少指定一个 brand_id")
                    try:
                        snapshot = repository.snapshot(brand_ids=brand_ids)
                    except (LookupError, ValueError) as exc:
                        raise AdministrationConflict(str(exc)) from exc
                return _snapshot_response(snapshot)
        finally:
            session.close()


def install_brand_vehicle_routes(
    application: FastAPI,
    *,
    identity_resolver: IdentityResolver | None = None,
) -> None:
    """安装 Stage 2 管理/快照路由，并复用正式 Platform Runtime 生命周期。"""

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

    @application.post(
        "/api/v1/vehicle-brands",
        operation_id="createVehicleBrand",
        response_model=BrandResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["vehicle-catalog"],
    )
    def create_brand(body: BrandCreateRequest, request: Request) -> BrandResponse:
        return service().create_brand(
            body, principal=principal(request), request_id=_request_id(request)
        )

    @application.get(
        "/api/v1/vehicle-brands",
        operation_id="listVehicleBrands",
        response_model=BrandListResponse,
        tags=["vehicle-catalog"],
    )
    def list_brands(
        search: str | None = Query(default=None, min_length=1, max_length=200),
        status_value: BrandStatus | None = Query(default=None, alias="status"),
        role: BrandRole | None = None,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> BrandListResponse:
        return service().list_brands(
            search=search,
            status_value=status_value,
            role=role,
            offset=offset,
            limit=limit,
        )

    @application.get(
        "/api/v1/vehicle-brands/{brand_id}",
        operation_id="getVehicleBrand",
        response_model=BrandResponse,
        tags=["vehicle-catalog"],
    )
    def get_brand(brand_id: UUID) -> BrandResponse:
        return service().get_brand(brand_id)

    @application.put(
        "/api/v1/vehicle-brands/{brand_id}",
        operation_id="updateVehicleBrand",
        response_model=BrandResponse,
        tags=["vehicle-catalog"],
    )
    def update_brand(brand_id: UUID, body: BrandUpdateRequest, request: Request) -> BrandResponse:
        return service().update_brand(
            brand_id, body, principal=principal(request), request_id=_request_id(request)
        )

    @application.delete(
        "/api/v1/vehicle-brands/{brand_id}",
        operation_id="deleteVehicleBrand",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["vehicle-catalog"],
    )
    def delete_brand(brand_id: UUID, request: Request) -> Response:
        service().delete_brand(
            brand_id, principal=principal(request), request_id=_request_id(request)
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.post(
        "/api/v1/vehicle-brands/{brand_id}/aliases",
        operation_id="addVehicleBrandAlias",
        response_model=BrandResponse,
        tags=["vehicle-catalog"],
    )
    def add_alias(
        brand_id: UUID, body: BrandAliasCreateRequest, request: Request
    ) -> BrandResponse:
        return service().add_alias(
            brand_id, body, principal=principal(request), request_id=_request_id(request)
        )

    @application.delete(
        "/api/v1/vehicle-brands/{brand_id}/aliases/{alias_id}",
        operation_id="deleteVehicleBrandAlias",
        response_model=BrandResponse,
        tags=["vehicle-catalog"],
    )
    def delete_alias(brand_id: UUID, alias_id: UUID, request: Request) -> BrandResponse:
        return service().delete_alias(
            brand_id, alias_id, principal=principal(request), request_id=_request_id(request)
        )

    @application.put(
        "/api/v1/vehicle-models/{vehicle_model_id}/brand",
        operation_id="assignVehicleModelBrand",
        response_model=VehicleBrandAssignmentResponse,
        tags=["vehicle-catalog"],
    )
    def assign_vehicle_brand(
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
        "/api/v1/vehicle-catalog/readiness",
        operation_id="getVehicleCatalogReadiness",
        response_model=BrandVehicleCatalogReadinessResponse,
        tags=["vehicle-catalog"],
    )
    def readiness(request: Request) -> BrandVehicleCatalogReadinessResponse:
        return service().readiness(principal=principal(request))

    @application.get(
        "/api/v1/vehicle-catalog/snapshot",
        operation_id="getBrandVehicleCatalogSnapshot",
        response_model=BrandVehicleCatalogSnapshotResponse,
        tags=["vehicle-catalog"],
    )
    def snapshot(
        scope: BrandFilterScope = "all_active",
        brand_id: list[UUID] | None = Query(default=None),
    ) -> BrandVehicleCatalogSnapshotResponse:
        return service().snapshot(scope=scope, brand_ids=tuple(brand_id or ()))


def _brand_response(
    repository: PostgresBrandVehicleRepository,
    brand: BrandRecord,
) -> BrandResponse:
    return BrandResponse(
        id=brand.id,
        code=brand.code,
        display_name=brand.display_name,
        role=brand.role,
        status=brand.status,
        version=brand.version,
        catalog_version=brand.catalog_version,
        aliases=tuple(
            BrandAliasResponse(
                id=alias.id,
                brand_id=alias.brand_id,
                text=alias.text,
                normalized_text=alias.normalized_text,
                created_at=alias.created_at,
            )
            for alias in repository.list_brand_aliases(brand.id)
        ),
        created_at=brand.created_at,
        updated_at=brand.updated_at,
    )


def _snapshot_response(snapshot: BrandVehicleCatalogSnapshot) -> BrandVehicleCatalogSnapshotResponse:
    return BrandVehicleCatalogSnapshotResponse(
        catalog_version=snapshot.catalog_version,
        filter_scope=snapshot.filter_scope,
        selected_brand_ids=snapshot.selected_brand_ids,
        brands=tuple(
            CatalogBrandSnapshotItem(
                id=item.id,
                code=item.code,
                display_name=item.display_name,
                role=item.role,
                version=item.version,
                catalog_version=item.catalog_version,
            )
            for item in snapshot.brands
        ),
        brand_aliases=tuple(
            CatalogBrandAliasSnapshotItem(
                id=item.id,
                brand_id=item.brand_id,
                text=item.text,
                normalized_text=item.normalized_text,
            )
            for item in snapshot.brand_aliases
        ),
        vehicles=tuple(
            CatalogVehicleSnapshotItem(
                id=item.id,
                code=item.code,
                display_name=item.display_name,
                brand_id=cast(UUID, item.brand_id),
                status=item.status,
                version=item.version,
                catalog_version=item.catalog_version,
            )
            for item in snapshot.vehicles
        ),
        vehicle_aliases=tuple(
            CatalogVehicleAliasSnapshotItem(
                id=item.id,
                vehicle_model_id=item.vehicle_model_id,
                text=item.text,
                normalized_text=item.normalized_text,
            )
            for item in snapshot.vehicle_aliases
        ),
        unresolved_active_vehicle_ids=snapshot.unresolved_active_vehicle_ids,
    )


def _audit(
    session: Any,
    *,
    principal: Principal,
    request_id: str,
    event_type: str,
    object_type: str,
    object_id: str,
    detail: dict[str, object],
) -> None:
    PostgresAuditRepository(session).append(
        AuditEvent(
            id=uuid4(),
            actor_kind="principal",
            actor_ref=principal.principal_id,
            event_type=event_type,
            object_type=object_type,
            object_id=object_id,
            request_id=request_id,
            safe_detail=cast(Any, detail),
            created_at=beijing_now(),
        )
    )


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else str(uuid4())


__all__ = ["PostgresBrandVehicleHttpService", "install_brand_vehicle_routes"]
