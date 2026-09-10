"""集成测试共用的 Stage 3 Brand Filter 目录准备。"""

from __future__ import annotations

from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.contracts.brand_vehicle import BrandCreateRequest
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot
from aima_ugc.platform.database import DatabaseRuntime


def stage3_filter_brand_id(runtime: PlatformRuntime, *, alias: str = "爱玛") -> str:
    """建立或复用当前测试 Runtime 的 Stage 3 品牌过滤事实。"""

    service = PostgresBrandVehicleHttpService(runtime)
    active = service.list_brands(
        search=None,
        status_value="active",
        role=None,
        offset=0,
        limit=200,
    )
    for brand in active.items:
        if brand.display_name == alias or any(item.text == alias for item in brand.aliases):
            return str(brand.id)
    brand = service.create_brand(
        BrandCreateRequest(
            code=f"STAGE3-INTEGRATION-{uuid4()}",
            display_name=f"Stage3 {alias}",
            role="owned",
            aliases=(alias,),
        ),
        principal=Principal(
            principal_id="stage3-integration",
            display_name="Stage3 集成测试管理员",
            role="administrator",
            source="development",
        ),
        request_id=f"stage3-brand-{uuid4()}",
    )
    return str(brand.id)


def stage4_collection_config_snapshot(
    runtime: PlatformRuntime | DatabaseRuntime,
    *,
    alias: str = "爱玛",
    **overrides: object,
) -> dict[str, object]:
    """构造当前 v2 Discovery 执行需要的真实冻结过滤快照。"""

    database = runtime.database if isinstance(runtime, PlatformRuntime) else runtime
    session = database.new_session()
    try:
        with session.begin():
            repository = PostgresBrandVehicleRepository(session)
            snapshot = repository.snapshot(brand_ids=None)
            if alias not in {item.text for item in snapshot.brand_aliases}:
                repository.create_brand(
                    code=f"STAGE4-INTEGRATION-{uuid4()}",
                    display_name=f"Stage4 {alias}",
                    role="owned",
                    aliases=(alias,),
                    actor_ref="stage4-integration",
                )
                snapshot = repository.snapshot(brand_ids=None)
            filter_snapshot = BrandVehicleFilterSnapshot(
                search_semantics="keyword_pack",
                catalog=snapshot,
            )
    finally:
        session.close()
    return {
        "schema_version": "collection-run-config.v2",
        "brand_vehicle_filter": filter_snapshot.model_dump(mode="json"),
        **overrides,
    }


__all__ = ["stage3_filter_brand_id", "stage4_collection_config_snapshot"]
