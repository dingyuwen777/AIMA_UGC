"""品牌与车型内部 code 的 HTTP Contract 回归。"""

import pytest
from aima_ugc.contracts.administration import VehicleModelCreateRequest
from aima_ugc.contracts.brand_vehicle import BrandCreateRequest
from aima_ugc.entrypoints.api_main import create_app
from pydantic import ValidationError


def test_catalog_create_requests_do_not_expose_internal_code() -> None:
    """创建请求不接收 code，但响应仍保留内部稳定身份。"""

    schemas = create_app().openapi()["components"]["schemas"]
    for name in ("BrandCreateRequest", "VehicleModelCreateRequest"):
        schema = schemas[name]
        assert "code" not in schema.get("properties", {})
        assert "code" not in schema.get("required", [])

    for name in ("BrandResponse", "VehicleModelResponse"):
        assert "code" in schemas[name]["properties"]


def test_catalog_create_requests_reject_client_controlled_code() -> None:
    """extra=forbid 防止客户端继续注入内部 code。"""

    with pytest.raises(ValidationError):
        BrandCreateRequest.model_validate({"code": "AIMA", "display_name": "爱玛", "role": "owned"})
    with pytest.raises(ValidationError):
        VehicleModelCreateRequest.model_validate({"code": "AIMA-PONY", "display_name": "Pony"})


def test_catalog_create_requests_accept_human_fields_without_code() -> None:
    """管理员只提供人类可理解的业务字段即可创建请求。"""

    brand = BrandCreateRequest(display_name=" 爱玛 ", role="owned", aliases=("AIMA",))
    vehicle = VehicleModelCreateRequest(display_name=" Pony ", aliases=("小爱",))
    assert brand.display_name == "爱玛"
    assert vehicle.display_name == "Pony"
