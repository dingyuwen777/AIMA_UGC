"""Stage 2 Brand/Vehicle 管理、快照、准备度与 Brand Review Lock PostgreSQL 回归。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.administration import VehicleModelCreateRequest, VehicleModelUpdateRequest
from aima_ugc.contracts.brand_vehicle import (
    BrandCreateRequest,
    BrandUpdateRequest,
    VehicleBrandAssignmentRequest,
)
from aima_ugc.modules.administration import AdministrationConflict
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.vehicles.brand_vehicle import ResolverEvidence
from aima_ugc.modules.vehicles.tables import (
    content_brand_evidence_table,
    content_brand_review_locks_table,
    content_vehicle_review_locks_table,
)
from aima_ugc.platform.config import load_settings
from sqlalchemy import func, select, text


@pytest.fixture
def runtime():  # type: ignore[no-untyped-def]
    value = create_worker_runtime(settings=load_settings())

    def cleanup() -> None:
        with value.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE audit_events, vehicle_brands, vehicle_models "
                "RESTART IDENTITY CASCADE"
            )

    cleanup()
    try:
        yield value
    finally:
        cleanup()
        value.close()


def _principal() -> Principal:
    return Principal(
        principal_id="stage2-admin",
        display_name="Stage2 管理员",
        role="administrator",
        source="development",
    )


def test_brand_vehicle_management_snapshot_and_readiness_use_one_catalog(runtime) -> None:  # type: ignore[no-untyped-def]
    """Brand/Vehicle 共享版本；新 active Vehicle 必须绑 active Brand；selected 自动带出车型。"""

    principal = _principal()
    brand_service = PostgresBrandVehicleHttpService(runtime)
    vehicle_service = PostgresAdministrationHttpService(runtime)

    with pytest.raises(AdministrationConflict):
        vehicle_service.create_vehicle_model(
            VehicleModelCreateRequest(code="NO-BRAND", display_name="无品牌车型"),
            principal=principal,
            request_id="stage2-no-brand",
        )

    owned = brand_service.create_brand(
        BrandCreateRequest(
            code="aima",
            display_name="爱玛",
            role="owned",
            aliases=("爱玛", "AIMA"),
        ),
        principal=principal,
        request_id="stage2-brand-owned",
    )
    competitor = brand_service.create_brand(
        BrandCreateRequest(
            code="competitor-b",
            display_name="竞品 B",
            role="competitor",
            aliases=("竞品B",),
        ),
        principal=principal,
        request_id="stage2-brand-competitor",
    )
    vehicle = vehicle_service.create_vehicle_model(
        VehicleModelCreateRequest(
            code="LUNA-AIR",
            display_name="露娜 Air",
            brand_id=owned.id,
            aliases=("露娜Air",),
        ),
        principal=principal,
        request_id="stage2-vehicle-create",
    )
    assert vehicle.brand_id == owned.id
    assert vehicle.catalog_version > competitor.catalog_version > owned.catalog_version

    moved = vehicle_service.update_vehicle_model(
        vehicle.id,
        VehicleModelUpdateRequest(brand_id=competitor.id),
        principal=principal,
        request_id="stage2-vehicle-brand-update",
    )
    assert moved.brand_id == competitor.id
    assert moved.version == vehicle.version + 1
    assert moved.catalog_version > vehicle.catalog_version

    with pytest.raises(AdministrationConflict):
        brand_service.update_brand(
            competitor.id,
            BrandUpdateRequest(status="deprecated"),
            principal=principal,
            request_id="stage2-brand-deactivate-blocked",
        )

    selected = brand_service.snapshot(scope="selected", brand_ids=(competitor.id,))
    assert selected.filter_scope == "selected"
    assert selected.selected_brand_ids == (competitor.id,)
    assert {item.id for item in selected.brands} == {competitor.id}
    assert {item.id for item in selected.vehicles} == {vehicle.id}
    assert {item.text for item in selected.brand_aliases} == {"竞品B"}
    assert {item.text for item in selected.vehicle_aliases} == {"露娜Air"}
    assert selected.catalog_version == moved.catalog_version

    # 模拟 Stage 1 遗留 active Vehicle：只用于证明 readiness 可发现且必须显式修复，不做猜测回填。
    session = runtime.database.new_session()
    try:
        with session.begin():
            legacy = PostgresVehicleCatalogRepository(session).create_model(
                code=f"LEGACY-{uuid4().hex[:8]}",
                display_name="历史未归属车型",
                aliases=("历史未归属车型",),
                actor_ref=principal.principal_id,
                brand_id=None,
            )
    finally:
        session.close()

    readiness = brand_service.readiness(principal=principal)
    assert readiness.ready is False
    assert legacy.id in readiness.unresolved_active_vehicle_ids

    fixed = brand_service.assign_vehicle_brand(
        legacy.id,
        VehicleBrandAssignmentRequest(brand_id=owned.id),
        principal=principal,
        request_id="stage2-explicit-fix",
    )
    assert fixed.brand_id == owned.id
    readiness = brand_service.readiness(principal=principal)
    assert readiness.ready is True
    assert readiness.unresolved_active_vehicle_ids == ()


def test_brand_manual_lock_blocks_automatic_overwrite_without_touching_vehicle_lock(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    """Brand Review Lock 与 Vehicle Review Lock 独立；锁后自动证据不能覆盖。"""

    principal = _principal()
    brand_service = PostgresBrandVehicleHttpService(runtime)
    brand = brand_service.create_brand(
        BrandCreateRequest(
            code="AIMA-LOCK",
            display_name="爱玛锁测试",
            role="owned",
            aliases=("爱玛锁测试",),
        ),
        principal=principal,
        request_id="stage2-lock-brand",
    )
    content_id = uuid4()

    session = runtime.database.new_session()
    try:
        with session.begin():
            # 这里只验证 Evidence/Lock Owner 语义；关闭 FK trigger，
            # 避免为该独立持久化测试构造无关 Content 聚合。
            session.execute(text("SET LOCAL session_replication_role = replica"))
            repository = PostgresBrandVehicleRepository(session)
            automatic = ResolverEvidence(
                entity_id=brand.id,
                source="alias_match",
                matched_text="爱玛锁测试",
                source_field="title",
            )
            assert (
                repository.replace_automatic_brand_evidence(
                    content_id=content_id,
                    content_version=3,
                    evidence=(automatic,),
                    catalog_version=repository.current_catalog_version(),
                )
                is True
            )
            repository.replace_manual_brand_evidence(
                content_id=content_id,
                content_version=3,
                brand_ids=(brand.id,),
                unlock_existing=False,
                actor_ref=principal.principal_id,
            )
            assert (
                repository.replace_automatic_brand_evidence(
                    content_id=content_id,
                    content_version=3,
                    evidence=(automatic,),
                    catalog_version=repository.current_catalog_version(),
                )
                is False
            )

            brand_lock = session.scalar(
                select(content_brand_review_locks_table.c.is_locked).where(
                    content_brand_review_locks_table.c.content_id == content_id,
                    content_brand_review_locks_table.c.content_version == 3,
                )
            )
            vehicle_lock_count = session.scalar(
                select(func.count())
                .select_from(content_vehicle_review_locks_table)
                .where(
                    content_vehicle_review_locks_table.c.content_id == content_id,
                    content_vehicle_review_locks_table.c.content_version == 3,
                )
            )
            active_brand_evidence = tuple(
                session.execute(
                    select(
                        content_brand_evidence_table.c.source,
                        content_brand_evidence_table.c.matched_text,
                        content_brand_evidence_table.c.source_field,
                        content_brand_evidence_table.c.is_manual_locked,
                    ).where(
                        content_brand_evidence_table.c.content_id == content_id,
                        content_brand_evidence_table.c.content_version == 3,
                        content_brand_evidence_table.c.is_active.is_(True),
                    )
                )
            )
            assert brand_lock is True
            assert vehicle_lock_count == 0
            assert active_brand_evidence == (("manual_review", None, None, True),)
    finally:
        session.close()
