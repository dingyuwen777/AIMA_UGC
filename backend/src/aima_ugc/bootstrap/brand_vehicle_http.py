"""Stage 2 Brand/Vehicle 管理 PostgreSQL Application Service。"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from aima_ugc.adapters.persistence.postgres.brand_vehicle import (
    PostgresBrandVehicleCatalogRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.contracts.brand_vehicle import (
    ActiveVehicleBrandIntegrityResponse,
    BrandAliasResponse,
    BrandCreateRequest,
    BrandListResponse,
    BrandResponse,
    BrandRole,
    BrandStatus,
    BrandUpdateRequest,
    BrandVehicleCatalogSnapshotQuery,
    BrandVehicleCatalogSnapshotResponse,
    CatalogBrandAliasResponse,
    CatalogVehicleAliasResponse,
    CatalogVehicleResponse,
    VehicleBrandAssignmentRequest,
    VehicleBrandAssignmentResponse,
)
from aima_ugc.modules.administration.http import (
    AdministrationConflict,
    AdministrationResourceNotFound,
)
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.modules.vehicles.models import Brand
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime


class PostgresBrandVehicleHttpService:
    """品牌 / 车型管理写入与审计在同一 PostgreSQL 事务提交。"""

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
                repository = PostgresBrandVehicleCatalogRepository(session)
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
                    detail={"code": brand.code, "role": brand.role},
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
        role: BrandRole | None,
        status: BrandStatus | None,
        offset: int,
        limit: int,
    ) -> BrandListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleCatalogRepository(session)
                brands, total = repository.list_brands(
                    search=search,
                    role=role,
                    status=status,
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
                repository = PostgresBrandVehicleCatalogRepository(session)
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
                repository = PostgresBrandVehicleCatalogRepository(session)
                try:
                    brand = repository.update_brand(
                        brand_id,
                        display_name=body.display_name,
                        role=body.role,
                        status=body.status,
                        aliases=body.aliases,
                        actor_ref=principal.principal_id,
                    )
                except LookupError as exc:
                    raise AdministrationResourceNotFound from exc
                except RuntimeError as exc:
                    raise AdministrationConflict from exc
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="vehicle_brand_updated",
                    object_type="vehicle_brand",
                    object_id=str(brand.id),
                    detail={
                        "version": brand.version,
                        "catalog_version": brand.catalog_version,
                        "role": brand.role,
                        "status": brand.status,
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
                repository = PostgresBrandVehicleCatalogRepository(session)
                try:
                    deleted = repository.delete_unreferenced_brand(
                        brand_id,
                        actor_ref=principal.principal_id,
                    )
                except RuntimeError as exc:
                    raise AdministrationConflict from exc
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
                repository = PostgresBrandVehicleCatalogRepository(session)
                before = repository.get_vehicle_model(vehicle_model_id)
                if before is None:
                    raise AdministrationResourceNotFound
                try:
                    vehicle = repository.assign_vehicle_brand(
                        vehicle_model_id,
                        body.brand_id,
                        actor_ref=principal.principal_id,
                    )
                except LookupError as exc:
                    raise AdministrationResourceNotFound from exc
                except RuntimeError as exc:
                    raise AdministrationConflict from exc
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="vehicle_model_brand_assigned",
                    object_type="vehicle_model",
                    object_id=str(vehicle_model_id),
                    detail={
                        "previous_brand_id": (
                            None if before.brand_id is None else str(before.brand_id)
                        ),
                        "brand_id": None if body.brand_id is None else str(body.brand_id),
                        "catalog_version": vehicle.catalog_version,
                    },
                )
                return VehicleBrandAssignmentResponse(
                    vehicle_model_id=vehicle.id,
                    brand_id=vehicle.brand_id,
                    vehicle_status=vehicle.status,
                    vehicle_version=vehicle.version,
                    catalog_version=vehicle.catalog_version,
                )
        finally:
            session.close()

    def get_active_vehicle_brand_integrity(self) -> ActiveVehicleBrandIntegrityResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleCatalogRepository(session)
                missing = repository.active_vehicle_ids_missing_brand()
                return ActiveVehicleBrandIntegrityResponse(
                    is_complete=not missing,
                    missing_brand_vehicle_model_ids=missing,
                    catalog_version=repository.current_catalog_version(),
                )
        finally:
            session.close()

    def get_catalog_snapshot(
        self,
        query: BrandVehicleCatalogSnapshotQuery,
    ) -> BrandVehicleCatalogSnapshotResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresBrandVehicleCatalogRepository(session)
                try:
                    snapshot = repository.catalog_snapshot(
                        filter_mode=query.mode,
                        selected_brand_ids=query.brand_ids,
                    )
                except LookupError as exc:
                    raise AdministrationResourceNotFound from exc
                except RuntimeError as exc:
                    raise AdministrationConflict from exc
                aliases_by_brand: dict[UUID, list[BrandAliasResponse]] = {}
                for alias in snapshot.brand_aliases:
                    aliases_by_brand.setdefault(alias.brand_id, []).append(
                        BrandAliasResponse(
                            id=alias.id,
                            text=alias.text,
                            normalized_text=alias.normalized_text,
                        )
                    )
                return BrandVehicleCatalogSnapshotResponse(
                    catalog_version=snapshot.catalog_version,
                    filter_mode=snapshot.filter_mode,
                    selected_brand_ids=snapshot.selected_brand_ids,
                    brands=tuple(
                        BrandResponse(
                            id=brand.id,
                            code=brand.code,
                            display_name=brand.display_name,
                            role=brand.role,
                            status=brand.status,
                            version=brand.version,
                            catalog_version=brand.catalog_version,
                            aliases=tuple(aliases_by_brand.get(brand.id, ())),
                            referenced=repository.is_brand_referenced(brand.id),
                            created_at=brand.created_at,
                            updated_at=brand.updated_at,
                        )
                        for brand in snapshot.brands
                    ),
                    brand_aliases=tuple(
                        CatalogBrandAliasResponse(
                            brand_id=alias.brand_id,
                            text=alias.text,
                            normalized_text=alias.normalized_text,
                        )
                        for alias in snapshot.brand_aliases
                    ),
                    vehicles=tuple(
                        CatalogVehicleResponse(
                            id=vehicle.id,
                            code=vehicle.code,
                            display_name=vehicle.display_name,
                            brand_id=vehicle.brand_id,
                            status=vehicle.status,
                            version=vehicle.version,
                        )
                        for vehicle in snapshot.vehicles
                    ),
                    vehicle_aliases=tuple(
                        CatalogVehicleAliasResponse(
                            vehicle_model_id=alias.vehicle_model_id,
                            text=alias.text,
                            normalized_text=alias.normalized_text,
                        )
                        for alias in snapshot.vehicle_aliases
                    ),
                )
        finally:
            session.close()


def _brand_response(
    repository: PostgresBrandVehicleCatalogRepository,
    brand: Brand,
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
                text=alias.text,
                normalized_text=alias.normalized_text,
            )
            for alias in repository.list_brand_aliases(brand.id)
        ),
        referenced=repository.is_brand_referenced(brand.id),
        created_at=brand.created_at,
        updated_at=brand.updated_at,
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


__all__ = ["PostgresBrandVehicleHttpService"]
