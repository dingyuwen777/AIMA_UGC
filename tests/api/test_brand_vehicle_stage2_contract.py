"""Stage 2 Brand/Vehicle HTTP 路由与 OpenAPI Contract 回归。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aima_ugc.contracts.administration import VehicleModelCreateRequest
from aima_ugc.contracts.brand_vehicle import BrandCreateRequest
from aima_ugc.entrypoints.api_main import create_app


def test_brand_vehicle_stage2_routes_are_installed_on_formal_api() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]

    assert paths["/api/v1/vehicle-brands"]["post"]["operationId"] == "createVehicleBrand"
    assert paths["/api/v1/vehicle-brands"]["get"]["operationId"] == "listVehicleBrands"
    assert (
        paths["/api/v1/vehicle-models/{vehicle_model_id}/brand"]["put"]["operationId"]
        == "assignVehicleModelBrand"
    )
    assert (
        paths["/api/v1/vehicle-catalog/readiness"]["get"]["operationId"]
        == "getVehicleCatalogReadiness"
    )
    assert (
        paths["/api/v1/vehicle-catalog/snapshot"]["get"]["operationId"]
        == "getBrandVehicleCatalogSnapshot"
    )


def test_create_contracts_hide_internal_code_but_responses_keep_it() -> None:
    """创建请求不暴露机器 code，管理响应继续返回持久化 code。"""

    components = create_app().openapi()["components"]["schemas"]
    brand_create = components["BrandCreateRequest"]
    brand_response = components["BrandResponse"]
    vehicle_create = components["VehicleModelCreateRequest"]
    vehicle_response = components["VehicleModelResponse"]

    assert "code" not in brand_create["properties"]
    assert "code" not in brand_create.get("required", [])
    assert "code" in brand_response["properties"]
    assert "code" in brand_response["required"]
    assert "code" not in vehicle_create["properties"]
    assert "code" not in vehicle_create.get("required", [])
    assert "code" in vehicle_response["properties"]
    assert "code" in vehicle_response["required"]


def test_create_contracts_reject_client_supplied_internal_code() -> None:
    """旧客户端继续提交 code 时必须明确失败，不能静默吞掉机器身份输入。"""

    with pytest.raises(ValidationError):
        BrandCreateRequest.model_validate(
            {
                "code": "CLIENT_BRAND",
                "display_name": "测试品牌",
                "role": "competitor",
            }
        )
    with pytest.raises(ValidationError):
        VehicleModelCreateRequest.model_validate(
            {
                "code": "CLIENT_VEHICLE",
                "display_name": "测试车型",
            }
        )


def test_vehicle_contract_exposes_brand_id_and_snapshot_has_stage2_scope() -> None:
    schema = create_app().openapi()
    components = schema["components"]["schemas"]

    vehicle_create = components["VehicleModelCreateRequest"]
    vehicle_response = components["VehicleModelResponse"]
    snapshot = components["BrandVehicleCatalogSnapshotResponse"]

    assert "brand_id" in vehicle_create["properties"]
    assert "brand_id" in vehicle_response["properties"]
    assert {
        "catalog_version",
        "filter_scope",
        "selected_brand_ids",
        "brands",
        "brand_aliases",
        "vehicles",
        "vehicle_aliases",
        "ambiguous_brand_aliases",
        "ambiguous_vehicle_aliases",
        "unresolved_active_vehicle_ids",
    } <= set(snapshot["properties"])
