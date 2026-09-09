"""Stage 2 品牌车型管理、统一快照与人工锁 PostgreSQL 集成回归。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.brand_vehicle import (
    PostgresBrandVehicleCatalogRepository,
)
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.brand_vehicle import BrandCreateRequest, VehicleBrandAssignmentRequest
from aima_ugc.modules.administration import AdministrationConflict
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.vehicles.models import ContentBrandEvidence, ContentVehicleEvidence
from aima_ugc.modules.vehicles.tables import content_brand_evidence_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.time import beijing_now
from sqlalchemy import insert, select


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


def test_brand_crud_vehicle_assignment_integrity_and_snapshot(runtime) -> None:  # type: ignore[no-untyped-def]
    service = PostgresBrandVehicleHttpService(runtime)
    principal = _admin()
    brand = service.create_brand(
        BrandCreateRequest(
            code="aima",
            display_name="爱玛",
            role="owned",
            aliases=("爱玛", "AIMA"),
        ),
        principal=principal,
        request_id="stage2-brand-create",
    )
    session = runtime.database.new_session()
    try:
        with session.begin():
            vehicle = PostgresVehicleCatalogRepository(session).create_model(
                code="LUNA-AIR",
                display_name="爱玛露娜 Air",
                aliases=("露娜Air",),
                actor_ref=principal.principal_id,
            )
    finally:
        session.close()

    before = service.get_active_vehicle_brand_integrity()
    assert before.is_complete is False
    assert before.missing_brand_vehicle_model_ids == (vehicle.id,)

    assigned = service.assign_vehicle_brand(
        vehicle.id,
        VehicleBrandAssignmentRequest(brand_id=brand.id),
        principal=principal,
        request_id="stage2-assign-brand",
    )
    assert assigned.brand_id == brand.id
    assert assigned.vehicle_version == vehicle.version + 1

    after = service.get_active_vehicle_brand_integrity()
    assert after.is_complete is True
    assert after.missing_brand_vehicle_model_ids == ()
    snapshot = service.get_catalog_snapshot()
    assert snapshot.catalog_version == after.catalog_version
    assert [(item.code, item.role) for item in snapshot.brands] == [("AIMA", "owned")]
    assert snapshot.vehicles[0].brand_id == brand.id
    assert {item.text for item in snapshot.brand_aliases} == {"爱玛", "AIMA"}
    assert [item.text for item in snapshot.vehicle_aliases] == ["露娜Air"]

    with pytest.raises(AdministrationConflict):
        service.delete_brand(
            brand.id,
            principal=principal,
            request_id="stage2-delete-referenced-brand",
        )


def test_manual_brand_and_vehicle_locks_block_automatic_replacement(runtime) -> None:  # type: ignore[no-untyped-def]
    principal = _admin()
    service = PostgresBrandVehicleHttpService(runtime)
    brand = service.create_brand(
        BrandCreateRequest(code="AIMA", display_name="爱玛", role="owned", aliases=("爱玛",)),
        principal=principal,
        request_id="stage2-brand-create-lock",
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
                actor_ref=principal.principal_id,
            )
            repository = PostgresBrandVehicleCatalogRepository(session)
            vehicle = repository.assign_vehicle_brand(
                vehicle.id, brand.id, actor_ref=principal.principal_id
            )
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
