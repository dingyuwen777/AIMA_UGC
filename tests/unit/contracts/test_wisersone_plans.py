"""同一计划入口按类型保留真实配置，不给网站导入伪造 TikHub 搜索面。"""

import pytest
from aima_ugc.contracts.http import CollectionPlanCreateRequest
from aima_ugc.contracts.resource_lifecycle import CollectionPlanUpdateRequest
from pydantic import ValidationError


def test_wisersone_create_and_update_need_only_common_plan_configuration() -> None:
    body = {"plan_type": "wisersone", "name": "网站每日导入", "schedule_expr": "0 0 * * *"}
    created = CollectionPlanCreateRequest.model_validate(body)
    assert created.platforms == () and created.keyword_pack_ids == ()
    assert created.comment_policy is None
    edited = CollectionPlanUpdateRequest.model_validate(
        {**body, "enabled": True, "expected_version": 1}
    )
    assert edited.plan_type == "wisersone"


@pytest.mark.parametrize(
    "extra",
    [{"comment_policy": "full"}, {"keyword_pack_ids": ["10000000-0000-0000-0000-000000000001"]}],
)
def test_wisersone_rejects_tikhub_only_configuration(extra) -> None:
    with pytest.raises(ValidationError):
        CollectionPlanCreateRequest.model_validate(
            {"plan_type": "wisersone", "name": "网站", "schedule_expr": "0 0 * * *", **extra}
        )


def test_tikhub_still_requires_search_surface() -> None:
    with pytest.raises(ValidationError):
        CollectionPlanCreateRequest(name="旧计划", schedule_expr="0 * * * *")
