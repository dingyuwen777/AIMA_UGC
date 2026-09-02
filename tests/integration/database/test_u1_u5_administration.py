"""U1—U5 车型合并、删除规则与配置审计 PostgreSQL 集成回归。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.administration import (
    KeywordPackVehicleLinkRequest,
    VehicleModelCreateRequest,
    VehicleModelMergeRequest,
)
from aima_ugc.modules.administration import (
    AdministrationConflict,
    AdministrationResourceNotFound,
)
from aima_ugc.modules.collection.tables import (
    collection_plan_vehicle_models_table,
    collection_plans_table,
)
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.system.tables import keyword_packs_table
from aima_ugc.modules.vehicles.tables import keyword_pack_vehicle_models_table
from aima_ugc.platform.config import load_settings
from sqlalchemy import func, insert, select


@pytest.fixture
def runtime():  # type: ignore[no-untyped-def]
    value = create_worker_runtime(settings=load_settings())

    def cleanup() -> None:
        with value.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE audit_events, collection_plans, keyword_packs, "
                "vehicle_models RESTART IDENTITY CASCADE"
            )

    cleanup()
    try:
        yield value
    finally:
        cleanup()
        value.close()


def test_vehicle_merge_redirects_future_references_and_audits_mutations(runtime) -> None:  # type: ignore[no-untyped-def]
    """合并迁移 Plan/Pack 引用但保留源车型身份，所有配置写入均可审计。"""

    service = PostgresAdministrationHttpService(runtime)
    principal = Principal(
        principal_id="admin-1",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    source = service.create_vehicle_model(
        VehicleModelCreateRequest(code="Q7-OLD", display_name="旧 Q7", aliases=("旧Q7",)),
        principal=principal,
        request_id="req-create-source",
    )
    target = service.create_vehicle_model(
        VehicleModelCreateRequest(code="Q7", display_name="爱玛 Q7", aliases=("Q7",)),
        principal=principal,
        request_id="req-create-target",
    )
    final_target = service.create_vehicle_model(
        VehicleModelCreateRequest(
            code="Q7-CANONICAL",
            display_name="爱玛 Q7 标准车型",
            aliases=("爱玛Q7标准车型",),
        ),
        principal=principal,
        request_id="req-create-final-target",
    )
    pack_id = uuid4()
    plan_id = uuid4()
    now = datetime.now(UTC)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(keyword_packs_table).values(
                id=pack_id,
                name=f"u1-pack-{uuid4()}",
                description="",
                enabled=True,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(collection_plans_table).values(
                id=plan_id,
                name=f"u1-plan-{uuid4()}",
                enabled=False,
                schedule_expr="0 9 * * *",
                timezone="Asia/Shanghai",
                schedule_version=1,
                misfire_policy="latest_only",
                max_catch_up_runs=0,
                detail_policy="on_change",
                comment_policy="adaptive",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(collection_plan_vehicle_models_table).values(
                plan_id=plan_id,
                vehicle_model_id=source.id,
            )
        )
    service.replace_keyword_pack_vehicles(
        pack_id,
        KeywordPackVehicleLinkRequest(vehicle_model_ids=(source.id,)),
        principal=principal,
        request_id="req-link",
    )

    merged = service.merge_vehicle_model(
        source.id,
        VehicleModelMergeRequest(target_vehicle_model_id=target.id),
        principal=principal,
        request_id="req-merge",
    )

    assert merged.status == "merged"
    assert merged.merged_into_id == target.id

    service.merge_vehicle_model(
        target.id,
        VehicleModelMergeRequest(target_vehicle_model_id=final_target.id),
        principal=principal,
        request_id="req-merge-chain",
    )
    assert service.get_vehicle_model(source.id).merged_into_id == final_target.id
    assert service.get_vehicle_model(target.id).merged_into_id == final_target.id
    with runtime.database.engine.begin() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(keyword_pack_vehicle_models_table)
                .where(keyword_pack_vehicle_models_table.c.vehicle_model_id == source.id)
            )
            == 0
        )
        assert (
            connection.scalar(
                select(func.count())
                .select_from(keyword_pack_vehicle_models_table)
                .where(keyword_pack_vehicle_models_table.c.vehicle_model_id == final_target.id)
            )
            == 1
        )
        assert (
            connection.scalar(
                select(func.count())
                .select_from(collection_plan_vehicle_models_table)
                .where(collection_plan_vehicle_models_table.c.vehicle_model_id == source.id)
            )
            == 0
        )
        assert (
            connection.scalar(
                select(func.count())
                .select_from(collection_plan_vehicle_models_table)
                .where(collection_plan_vehicle_models_table.c.vehicle_model_id == final_target.id)
            )
            == 1
        )

    session = runtime.database.new_session()
    try:
        with session.begin():
            events = PostgresAuditRepository(session).list_recent(limit=20)
    finally:
        session.close()
    assert {event.event_type for event in events} >= {
        "vehicle_model_created",
        "keyword_pack_vehicle_links_updated",
        "vehicle_model_merged",
    }
    assert all(event.actor_ref == "admin-1" for event in events)
    assert "req-merge" in {event.request_id for event in events}

    with pytest.raises(AdministrationConflict):
        service.delete_vehicle_model(
            final_target.id,
            principal=principal,
            request_id="req-delete-referenced",
        )


def test_unreferenced_vehicle_can_be_physically_deleted(runtime) -> None:  # type: ignore[no-untyped-def]
    service = PostgresAdministrationHttpService(runtime)
    principal = Principal(
        principal_id="admin-1",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    created = service.create_vehicle_model(
        VehicleModelCreateRequest(code="LUNA", display_name="爱玛露娜", aliases=("露娜",)),
        principal=principal,
        request_id="req-create",
    )

    service.delete_vehicle_model(
        created.id,
        principal=principal,
        request_id="req-delete",
    )

    with pytest.raises(AdministrationResourceNotFound):
        service.get_vehicle_model(created.id)
