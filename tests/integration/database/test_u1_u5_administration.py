"""U1—U5 车型合并、删除规则与配置审计 PostgreSQL 集成回归。"""

from __future__ import annotations

from uuid import uuid4

import aima_ugc.bootstrap.administration_http as administration_http
import pytest
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.administration import (
    VehicleModelCreateRequest,
    VehicleModelListQuery,
    VehicleModelMergeRequest,
    VehicleModelUpdateRequest,
)
from aima_ugc.contracts.brand_vehicle import BrandCreateRequest
from aima_ugc.modules.administration import (
    AdministrationConflict,
    AdministrationResourceNotFound,
)
from aima_ugc.modules.identity import Principal
from aima_ugc.platform.config import load_settings
from sqlalchemy import event


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


def _create_owned_brand(runtime, principal: Principal, *, code: str):  # type: ignore[no-untyped-def]
    return PostgresBrandVehicleHttpService(runtime).create_brand(
        BrandCreateRequest(
            display_name=f"测试品牌 {code}",
            role="owned",
            aliases=(f"{code}品牌",),
        ),
        principal=principal,
        request_id=f"brand-{code}",
    )


def test_catalog_list_query_count_does_not_grow_with_page_size(runtime) -> None:  # type: ignore[no-untyped-def]
    """目录关联投影必须按页批量读取，不能为每个品牌或车型追加 SQL。"""

    principal = Principal(
        principal_id="catalog-query-admin",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    brand_service = PostgresBrandVehicleHttpService(runtime)
    vehicle_service = PostgresAdministrationHttpService(runtime)
    vehicle_ids = []
    for index in range(4):
        brand = _create_owned_brand(runtime, principal, code=f"QUERY-{index}")
        created = vehicle_service.create_vehicle_model(
            VehicleModelCreateRequest(
                display_name=f"查询车型 {index}",
                brand_id=brand.id,
                aliases=(f"查询别名 {index}",),
            ),
            principal=principal,
            request_id=f"query-vehicle-{index}",
        )
        vehicle_ids.append(created.id)
    vehicle_service.merge_vehicle_model(
        vehicle_ids[3],
        VehicleModelMergeRequest(target_vehicle_model_id=vehicle_ids[0]),
        principal=principal,
        request_id="query-vehicle-merge",
    )

    statements: list[str] = []

    def capture_statement(*args: object, **_kwargs: object) -> None:
        """记录 SQL 文本，只比较同一运行时下不同页大小的查询数量。"""

        statements.append(str(args[2]))

    event.listen(runtime.database.engine, "before_cursor_execute", capture_statement)
    try:
        vehicle_service.list_vehicle_models(VehicleModelListQuery(limit=1))
        vehicle_one_count = len(statements)
        statements.clear()
        vehicle_page = vehicle_service.list_vehicle_models(VehicleModelListQuery(limit=4))
        vehicle_four_count = len(statements)
        statements.clear()
        brand_service.list_brands(
            search=None,
            status_value=None,
            role=None,
            offset=0,
            limit=1,
        )
        brand_one_count = len(statements)
        statements.clear()
        brand_page = brand_service.list_brands(
            search=None,
            status_value=None,
            role=None,
            offset=0,
            limit=4,
        )
        brand_four_count = len(statements)
    finally:
        event.remove(runtime.database.engine, "before_cursor_execute", capture_statement)

    assert vehicle_four_count == vehicle_one_count == 6
    assert brand_four_count == brand_one_count == 4
    assert next(item for item in vehicle_page.items if item.id == vehicle_ids[0]).referenced is True
    assert {alias.text for item in vehicle_page.items for alias in item.aliases} == {
        f"查询别名 {index}" for index in range(4)
    }
    assert {alias.text for item in brand_page.items for alias in item.aliases} == {
        f"QUERY-{index}品牌" for index in range(4)
    }


def test_vehicle_display_name_update_uses_bounded_queries(runtime) -> None:  # type: ignore[no-untyped-def]
    """单字段编辑复用已锁定车型，并用单次查询返回引用状态。"""

    principal = Principal(
        principal_id="vehicle-update-query-admin",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    brand = _create_owned_brand(runtime, principal, code="UPDATE-QUERY")
    service = PostgresAdministrationHttpService(runtime)
    created = service.create_vehicle_model(
        VehicleModelCreateRequest(
            display_name="查询前车型",
            brand_id=brand.id,
            aliases=("保留别名",),
        ),
        principal=principal,
        request_id="vehicle-update-query-create",
    )
    statements: list[str] = []

    def capture_statement(*args: object, **_kwargs: object) -> None:
        """记录一次正式更新服务调用产生的数据库往返。"""

        statements.append(str(args[2]))

    event.listen(runtime.database.engine, "before_cursor_execute", capture_statement)
    try:
        updated = service.update_vehicle_model(
            created.id,
            VehicleModelUpdateRequest(display_name="查询后车型"),
            principal=principal,
            request_id="vehicle-update-query-update",
        )
    finally:
        event.remove(runtime.database.engine, "before_cursor_execute", capture_statement)

    assert len(statements) == 9
    assert updated.display_name == "查询后车型"
    assert tuple(alias.text for alias in updated.aliases) == ("保留别名",)


def test_vehicle_update_slow_log_records_stages_without_business_text(
    runtime, monkeypatch, caplog
) -> None:  # type: ignore[no-untyped-def]
    """慢成功与慢失败记录安全阶段字段，正常快速保存不产生告警。"""

    principal = Principal(
        principal_id="vehicle-timing-admin",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    brand = _create_owned_brand(runtime, principal, code="TIMING")
    service = PostgresAdministrationHttpService(runtime)
    created = service.create_vehicle_model(
        VehicleModelCreateRequest(display_name="初始车型", brand_id=brand.id),
        principal=principal,
        request_id="vehicle-timing-create",
    )
    runtime.logger.addHandler(caplog.handler)
    try:
        monkeypatch.setattr(administration_http, "SLOW_VEHICLE_UPDATE_MS", 10**9)
        service.update_vehicle_model(
            created.id,
            VehicleModelUpdateRequest(display_name="快速且敏感的车型名"),
            principal=principal,
            request_id="vehicle-timing-fast",
        )
        assert not any(
            getattr(record, "event", None) == "administration.vehicle_model_update_slow"
            for record in caplog.records
        )

        monkeypatch.setattr(administration_http, "SLOW_VEHICLE_UPDATE_MS", 0)
        service.update_vehicle_model(
            created.id,
            VehicleModelUpdateRequest(display_name="慢速且敏感的车型名", aliases=("敏感别名",)),
            principal=principal,
            request_id="vehicle-timing-slow",
        )
        with pytest.raises(AdministrationConflict):
            service.update_vehicle_model(
                created.id,
                VehicleModelUpdateRequest(display_name="失败且敏感的车型名", brand_id=uuid4()),
                principal=principal,
                request_id="vehicle-timing-failed",
            )
    finally:
        runtime.logger.removeHandler(caplog.handler)

    events = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "administration.vehicle_model_update_slow"
    ]
    assert [(record.request_id, record.outcome) for record in events] == [
        ("vehicle-timing-slow", "success"),
        ("vehicle-timing-failed", "failed"),
    ]
    stages = events[0].stage_ms
    assert set(stages) == {
        "session_create",
        "db_checkout",
        "vehicle_lock",
        "brand_check",
        "catalog_version",
        "model_update",
        "alias_replace",
        "audit",
        "response_projection",
        "commit",
    }
    assert events[0].vehicle_model_id == str(created.id)
    assert events[0].changed_fields == ["aliases", "display_name"]
    assert events[1].changed_fields == ["brand_id", "display_name"]
    assert set(events[1].stage_ms) == {
        "session_create",
        "db_checkout",
        "vehicle_lock",
        "brand_check",
    }
    assert "敏感" not in caplog.text


def test_vehicle_merge_redirects_identity_and_audits_mutations(runtime) -> None:  # type: ignore[no-untyped-def]
    """合并保留源车型身份并折叠链路，所有管理写入均可审计。"""

    service = PostgresAdministrationHttpService(runtime)
    principal = Principal(
        principal_id="admin-1",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    brand = _create_owned_brand(runtime, principal, code="U1-MERGE")
    source = service.create_vehicle_model(
        VehicleModelCreateRequest(display_name="旧 Q7", brand_id=brand.id, aliases=("旧Q7",)),
        principal=principal,
        request_id="req-create-source",
    )
    target = service.create_vehicle_model(
        VehicleModelCreateRequest(display_name="爱玛 Q7", brand_id=brand.id, aliases=("Q7",)),
        principal=principal,
        request_id="req-create-target",
    )
    final_target = service.create_vehicle_model(
        VehicleModelCreateRequest(
            display_name="爱玛 Q7 标准车型",
            brand_id=brand.id,
            aliases=("爱玛Q7标准车型",),
        ),
        principal=principal,
        request_id="req-create-final-target",
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
    session = runtime.database.new_session()
    try:
        with session.begin():
            events = PostgresAuditRepository(session).list_recent(limit=20)
    finally:
        session.close()
    assert {event.event_type for event in events} >= {
        "vehicle_model_created",
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


def test_vehicle_display_classification_persists_and_can_be_cleared(runtime) -> None:  # type: ignore[no-untyped-def]
    """系列与类别复用车型 Owner；省略保持原值，显式 null 清空并推进目录版本。"""
    service = PostgresAdministrationHttpService(runtime)
    principal = Principal(
        principal_id="classification-admin",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    brand = _create_owned_brand(runtime, principal, code="U1-CLASS")
    created = service.create_vehicle_model(
        VehicleModelCreateRequest(
            display_name="爱玛 Q7",
            brand_id=brand.id,
            series_name=" Q 系列 ",
            category_name="电动两轮车",
        ),
        principal=principal,
        request_id="classification-create",
    )
    stored = service.get_vehicle_model(created.id)
    assert stored.series_name == "Q 系列"
    assert stored.category_name == "电动两轮车"
    renamed = service.update_vehicle_model(
        created.id,
        VehicleModelUpdateRequest(display_name="爱玛 Q7 新名称"),
        principal=principal,
        request_id="classification-rename",
    )
    assert renamed.series_name == "Q 系列"
    assert renamed.category_name == "电动两轮车"
    cleared = service.update_vehicle_model(
        created.id,
        VehicleModelUpdateRequest(series_name=None),
        principal=principal,
        request_id="classification-clear",
    )
    assert cleared.series_name is None
    assert cleared.category_name == "电动两轮车"
    assert cleared.catalog_version > renamed.catalog_version > created.catalog_version
    assert service.get_vehicle_model(created.id).series_name is None


def test_unreferenced_vehicle_can_be_physically_deleted(runtime) -> None:  # type: ignore[no-untyped-def]
    service = PostgresAdministrationHttpService(runtime)
    principal = Principal(
        principal_id="admin-1",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    brand = _create_owned_brand(runtime, principal, code="U1-DELETE")
    created = service.create_vehicle_model(
        VehicleModelCreateRequest(display_name="爱玛露娜", brand_id=brand.id, aliases=("露娜",)),
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
