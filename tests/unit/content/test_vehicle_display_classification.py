"""管理员车型分组字段的兼容、清除与空白校验。"""

import pytest
from aima_ugc.contracts.administration import (
    VehicleModelCreateRequest,
    VehicleModelUpdateRequest,
)
from pydantic import ValidationError


def test_vehicle_classification_is_optional_and_trimmed() -> None:
    """旧请求无须补数据，显式分组去除首尾空白。"""
    old = VehicleModelCreateRequest(code="Q7", display_name="爱玛 Q7")
    assert old.series_name is None and old.category_name is None
    model = VehicleModelCreateRequest(
        code="Q7", display_name="爱玛 Q7", series_name=" Q 系列 ", category_name=" 电动两轮车 "
    )
    assert model.series_name == "Q 系列"
    assert model.category_name == "电动两轮车"


def test_vehicle_classification_can_be_cleared_without_changing_other_fields() -> None:
    """显式 null 是清除，未传字段不能覆盖已有分类。"""
    body = VehicleModelUpdateRequest(series_name=None)
    assert body.model_dump(exclude_unset=True) == {"series_name": None}
    with pytest.raises(ValidationError):
        VehicleModelUpdateRequest()
    with pytest.raises(ValidationError):
        VehicleModelUpdateRequest(category_name="  ")
