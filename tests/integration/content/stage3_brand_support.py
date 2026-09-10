"""Content 集成测试共用的 Stage 3 Brand Filter 目录准备。"""

from __future__ import annotations

from uuid import uuid4

from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.contracts.brand_vehicle import BrandCreateRequest
from aima_ugc.modules.identity import Principal


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
            code=f"STAGE3-CONTENT-{uuid4()}",
            display_name=f"Stage3 {alias}",
            role="owned",
            aliases=(alias,),
        ),
        principal=Principal(
            principal_id="stage3-content-integration",
            display_name="Stage3 Content 集成测试管理员",
            role="administrator",
            source="development",
        ),
        request_id=f"stage3-content-brand-{uuid4()}",
    )
    return str(brand.id)


__all__ = ["stage3_filter_brand_id"]
