"""Stage 2 品牌车型管理、冻结 Scope 与人工锁 PostgreSQL 集成回归。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import insert, select

from aima_ugc.adapters.persistence.postgres.brand_vehicle import (
    PostgresBrandVehicleCatalogRepository,
)
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.administration import VehicleModelCreateRequest
from aima_ugc.contracts.brand_vehicle import (
    BrandCreateRequest,
    BrandUpdateRequest,
    BrandVehicleCatalogSnapshotQuery,
    VehicleBrandAssignmentRequest,
)
from aima_ugc.modules.administration import AdministrationConflict
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.vehicles.models import ContentBrandEvidence, ContentVehicleEvidence
from aima_ugc.modules.vehicles.tables import (
    content_brand_evidence_table,
    vehicle_models_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.time import beijing_now


@pytest.fixture
def runtime():  # type: ignore[no-untyped-def]
    value = create_worker_runtime(settings=load_settings())

    def cleanup() -> None:
        with value.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE contents, vehicle_models, vehicle_brands RESTART IDENTITY CASCADE"
            )

    cleanup()
    try:
        yield value
    finally:
        cleanup()
        value.close()


def _admin() -> Principal:
    return Principal(
        principal_id="stage2-admin",
        display_name="管理员",
        role="administrator",
        source="development",
    )


def _brand(
    service: PostgresBrandVehicleHttpService,
    principal: Principal,
    *,
    code: str,
    name: str,
    role: str,
    aliases: tuple[str, ...],
):  # type: ignore[no-untyped-def]
    return service.create_brand(
        BrandCreateRequest(code=code, display_name=name, role=role, aliases=aliases),  # type: ignore[arg-type]
        principal=principal,
        request_id=f"stage2-brand-{code}",
    )


def _vehicle(
    service: PostgresAdministrationHttpService,
    principal: Principal,
    *,
    code: str,
    name: str,
    brand_id,
    aliases: tuple[str, ...],
):  # type: ignore[no-untyped-def]
    return service.create_vehicle_model(
        VehicleModelCreateRequest(
            code=code,
            display_name=name,
            brand_id=brand_id,
            aliases=aliases,
        ),
        principal=principal,
        request_id=f"stage2-vehicle-{code}",
    )


def test_brand_vehicle_admin_invariant_and_snapshot_scopes(runtime) -> None:  # type: ignore[no-untyped-def]
    brand_service = PostgresBrandVehicleHttpService(runtime)
    vehicle_service = PostgresAdministrationHttpService(runtime)
    principal = _admin()
    aima = _brand(
        brand_service,
        principal,
        code="AIMA",
        name="爱玛",
        role="owned",
        aliases=("爱玛", "AIMA"),
    )
    niu = _brand(
        brand_service,
        principal,
        code="NIU",
        name="小牛",
        role="competitor",
        aliases=("小牛", "NIU"),
    )
    spare = _brand(
        brand_service,
        principal,
        code="SPARE",
        name="停用品牌",
        role="other",
        aliases=("停用品牌",),
    )

    luna = _vehicle(
        vehicle_service,
        principal,
        code="LUNA-AIR",
        name="爱玛露娜 Air",
        brand_id=aima.id,
        aliases=("露娜Air",),
    )
    q5 = _vehicle(
        vehicle_service,
        principal,
        code="Q5",
        name="爱玛 Q5",
        brand_id=aima.id,
        aliases=("爱玛Q5",),
    )
    uqi = _vehicle(
        vehicle_service,
        principal,
        code="UQI",
        name="小牛 UQi",
        brand_id=niu.id,
        aliases=("UQi",),
    )

    assert vehicle_service.get_vehicle_model(luna.id).brand_id == aima.id
    assert brand_service.get_active_vehicle_brand_integrity().is_complete is True

    all_snapshot = brand_service.get_catalog_snapshot(BrandVehicleCatalogSnapshotQuery())
    assert all_snapshot.filter_mode == "all_active"
    assert all_snapshot.selected_brand_ids == ()
    assert {item.id for item in all_snapshot.brands} == {aima.id, niu.id, spare.id}
    assert {item.id for item in all_snapshot.vehicles} == {luna.id, q5.id, uqi.id}
    assert all_snapshot.catalog_version >= uqi.catalog_version

    selected = brand_service.get_catalog_snapshot(
        BrandVehicleCatalogSnapshotQuery(mode="selected", brand_ids=(aima.id,))
    )
    assert selected.filter_mode == "selected"
    assert selected.selected_brand_ids == (aima.id,)
    assert {item.id for item in selected.brands} == {aima.id}
    assert {item.id for item in selected.vehicles} == {luna.id, q5.id}
    assert {item.vehicle_model_id for item in selected.vehicle_aliases} == {luna.id, q5.id}
    assert {item.brand_id for item in selected.brand_aliases} == {aima.id}

    with pytest.raises(AdministrationConflict):
        brand_service.update_brand(
            aima.id,
            BrandUpdateRequest(status="deprecated"),
            principal=principal,
            request_id="stage2-deprecate-brand-with-active-vehicles",
        )
    with pytest.raises(AdministrationConflict):
        brand_service.assign_vehicle_brand(
            luna.id,
            VehicleBrandAssignmentRequest(brand_id=None),
            principal=principal,
            request_id="stage2-clear-active-brand",
        )

    deprecated = brand_service.update_brand(
        spare.id,
        BrandUpdateRequest(status="deprecated"),
        principal=principal,
        request_id="stage2-deprecate-unused-brand",
    )
    assert deprecated.status == "deprecated"
    with pytest.raises(AdministrationConflict):
        _vehicle(
            vehicle_service,
            principal,
            code="INVALID-BRAND",
            name="不能绑定停用品牌",
            brand_id=spare.id,
            aliases=("INVALID-BRAND",),
        )


def test_legacy_unassigned_active_vehicle_must_be_explicitly_repaired(runtime) -> None:  # type: ignore[no-untyped-def]
    service = PostgresBrandVehicleHttpService(runtime)
    principal = _admin()
    brand = _brand(
        service,
        principal,
        code="AIMA",
        name="爱玛",
        role="owned",
        aliases=("爱玛",),
    )
    vehicle_id = uuid4()
    now = beijing_now()
    session = runtime.database.new_session()
    try:
        with session.begin():
            catalog_version = PostgresVehicleCatalogRepository(session).current_catalog_version()
            session.execute(
                insert(vehicle_models_table).values(
                    id=vehicle_id,
                    code="LEGACY-UNASSIGNED",
                    display_name="历史未归属车型",
                    brand_id=None,
                    status="active",
                    version=1,
                    catalog_version=catalog_version,
                    created_at=now,
                    updated_at=now,
                )
            )
    finally:
        session.close()

    integrity = service.get_active_vehicle_brand_integrity()
    assert integrity.is_complete is False
    assert integrity.missing_brand_vehicle_model_ids == (vehicle_id,)
    with pytest.raises(AdministrationConflict):
        service.get_catalog_snapshot(BrandVehicleCatalogSnapshotQuery())

    repaired = service.assign_vehicle_brand(
        vehicle_id,
        VehicleBrandAssignmentRequest(brand_id=brand.id),
        principal=principal,
        request_id="stage2-explicit-legacy-repair",
    )
    assert repaired.brand_id == brand.id
    assert service.get_active_vehicle_brand_integrity().is_complete is True
    snapshot = service.get_catalog_snapshot(BrandVehicleCatalogSnapshotQuery())
    assert {item.id for item in snapshot.vehicles} == {vehicle_id}


def test_manual_brand_and_vehicle_locks_block_automatic_replacement(runtime) -> None:  # type: ignore[no-untyped-def]
    principal = _admin()
    service = PostgresBrandVehicleHttpService(runtime)
    brand = _brand(
        service,
        principal,
        code="AIMA",
        name="爱玛",
        role="owned",
        aliases=("爱玛",),
    )
    content_id = uuid4()
    now = beijing_now()
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(contents_table).values(
                id=content_id,
                platform="xiaohongshu",
                external_content_id=f"stage2-{content_id}",
                content_type="image",
                first_seen_at=now,
                last_seen_at=now,
                current_version=1,
                updated_at=now,
            )
        )
    session = runtime.database.new_session()
    try:
        with session.begin():
            vehicle_repo = PostgresVehicleCatalogRepository(session)
            vehicle = vehicle_repo.create_model(
                code="LUNA-LOCK",
                display_name="爱玛露娜",
                aliases=("露娜",),
                brand_id=brand.id,
                actor_ref=principal.principal_id,
            )
            repository = PostgresBrandVehicleCatalogRepository(session)
            catalog_version = repository.current_catalog_version()
            assert repository.replace_automatic_brand_evidence(
                content_id=content_id,
                content_version=1,
                evidence=(
                    ContentBrandEvidence(
                        id=uuid4(),
                        content_id=content_id,
                        content_version=1,
                        brand_id=brand.id,
                        source="alias_match",
                        matched_text="爱玛",
                        source_field="title",
                        derived_vehicle_model_id=None,
                        catalog_version=catalog_version,
                        confidence=1.0,
                        is_manual_locked=False,
                        is_active=True,
                        created_at=now,
                    ),
                ),
            )
            repository.replace_manual_brand_evidence(
                content_id=content_id,
                content_version=1,
                brand_ids=(brand.id,),
                unlock_existing=False,
                actor_ref=principal.principal_id,
            )
            assert (
                repository.replace_automatic_brand_evidence(
                    content_id=content_id,
                    content_version=1,
                    evidence=(),
                )
                is False
            )
            active_brand_rows = tuple(
                session.execute(
                    select(content_brand_evidence_table).where(
                        content_brand_evidence_table.c.content_id == content_id,
                        content_brand_evidence_table.c.content_version == 1,
                        content_brand_evidence_table.c.is_active.is_(True),
                    )
                ).mappings()
            )
            assert len(active_brand_rows) == 1
            assert active_brand_rows[0]["source"] == "manual_review"
            assert active_brand_rows[0]["is_manual_locked"] is True

            vehicle_repo.replace_manual_evidence(
                content_id=content_id,
                content_version=1,
                model_ids=(vehicle.id,),
                unlock_existing=False,
                actor_ref=principal.principal_id,
            )
            assert (
                repository.replace_automatic_vehicle_evidence(
                    content_id=content_id,
                    content_version=1,
                    evidence=(
                        ContentVehicleEvidence(
                            id=uuid4(),
                            content_id=content_id,
                            content_version=1,
                            vehicle_model_id=vehicle.id,
                            source="alias_match",
                            matched_text="露娜",
                            source_field="title",
                            catalog_version=repository.current_catalog_version(),
                            confidence=1.0,
                            is_manual_locked=False,
                            is_active=True,
                            created_at=now,
                        ),
                    ),
                )
                is False
            )
    finally:
        session.close()
