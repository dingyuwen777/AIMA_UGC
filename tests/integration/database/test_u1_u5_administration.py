"""U1—U5 车型合并、删除规则与配置审计 PostgreSQL 集成回归。"""

from __future__ import annotations

import pytest
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.administration import (
    VehicleModelCreateRequest,
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
            code=code,
            display_name=f"测试品牌 {code}",
            role="owned",
            aliases=(f"{code}品牌",),
        ),
        principal=principal,
        request_id=f"brand-{code}",
    )


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
        VehicleModelCreateRequest(
            code="Q7-OLD", display_name="旧 Q7", brand_id=brand.id, aliases=("旧Q7",)
        ),
        principal=principal,
        request_id="req-create-source",
    )
    target = service.create_vehicle_model(
        VehicleModelCreateRequest(
            code="Q7", display_name="爱玛 Q7", brand_id=brand.id, aliases=("Q7",)
        ),
        principal=principal,
        request_id="req-create-target",
    )
    final_target = service.create_vehicle_model(
        VehicleModelCreateRequest(
            code="Q7-CANONICAL",
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
            code="CLASS-Q7",
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
        VehicleModelCreateRequest(
            code="LUNA", display_name="爱玛露娜", brand_id=brand.id, aliases=("露娜",)
        ),
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
