"""U1—U5 新公共 Contract 的最小语义回归。"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.contracts.administration import (
    AnalysisSchemeDefinitionRequest,
    CurrentPrincipalResponse,
    VehicleModelCreateRequest,
)
from aima_ugc.contracts.http import (
    CollectionPlanCreateRequest,
    ContentFilterSnapshot,
    DataExportSubmitRequest,
)
from aima_ugc.contracts.product import (
    ContentAvailabilityObservationRequest,
    ContentCountQuery,
    ContentCountResponse,
    NotificationMarkReadRequest,
)
from aima_ugc.modules.reporting.column_catalog import (
    EXPORT_COLUMNS,
    export_column_headers,
)
from pydantic import ValidationError


def test_vehicle_only_collection_plan_is_additive_and_valid() -> None:
    """新 Plan 可只选车型，旧 keyword_pack_ids 字段继续存在。"""

    vehicle_id = uuid4()
    request = CollectionPlanCreateRequest(
        name="Q7 监测",
        schedule_expr="0 8 * * *",
        platforms=[
            {
                "platform": "douyin",
                "provider_config_id": uuid4(),
                "search_config": {},
            }
        ],
        vehicle_model_ids=[vehicle_id],
    )

    assert request.keyword_pack_ids == ()
    assert request.vehicle_model_ids == (vehicle_id,)


def test_vehicle_model_contract_normalizes_aliases_and_rejects_duplicates() -> None:
    """车型别名以规范化身份去重，不能在同车型下重复。"""

    model = VehicleModelCreateRequest(
        code=" q7 ",
        display_name=" 爱玛 Q7 ",
        aliases=["Q7", "爱玛Q7"],
    )
    assert model.code == "Q7"
    assert model.display_name == "爱玛 Q7"

    with pytest.raises(ValidationError):
        VehicleModelCreateRequest(
            code="Q7",
            display_name="爱玛 Q7",
            aliases=["Q7", " q7 "],
        )


def test_content_filter_accepts_multiple_vehicle_models() -> None:
    """声音广场车型筛选使用稳定 ID 并允许同维度 OR。"""

    first, second = uuid4(), uuid4()
    snapshot = ContentFilterSnapshot(vehicle_model_ids=[first, second])
    assert snapshot.vehicle_model_ids == (first, second)

    with pytest.raises(ValidationError):
        ContentFilterSnapshot(vehicle_model_ids=[first, first])


def test_analysis_scheme_requires_explicit_unknown_values() -> None:
    """Scheme 必须显式表达无法判断，不能把未知静默映射为中性。"""

    valid = AnalysisSchemeDefinitionRequest(
        prompt_template="规则\n{{AIMA_TAXONOMY_JSON}}\n结束",
        sentiments=["正面", "中性", "负面", "无法判断"],
        voice_types=["真实用户发声", "无法判断"],
        labels={"产品体验": ["动力", "续航"], "无法分类": ["无法判断"]},
    )
    assert valid.sentiments[-1] == "无法判断"

    with pytest.raises(ValidationError):
        AnalysisSchemeDefinitionRequest(
            prompt_template="{{AIMA_TAXONOMY_JSON}}",
            sentiments=["正面", "中性", "负面"],
            voice_types=["真实用户发声", "无法判断"],
            labels={"产品体验": ["动力"], "无法分类": ["无法判断"]},
        )


def test_identity_roles_are_only_administrator_and_user() -> None:
    """第一版角色面严格限制为管理员和普通用户。"""

    principal = CurrentPrincipalResponse(
        principal_id="local-admin",
        display_name="本地管理员",
        role="administrator",
        source="development",
    )
    assert principal.is_administrator is True

    with pytest.raises(ValidationError):
        CurrentPrincipalResponse(
            principal_id="reviewer",
            display_name="审核员",
            role="publisher",
            source="development",
        )


def test_count_export_and_notification_contracts_fail_closed() -> None:
    """Count、导出列和通知请求都拒绝模糊或重复输入。"""

    assert ContentCountQuery(count_mode="none").count_mode == "none"
    with pytest.raises(ValidationError):
        ContentCountQuery(count_mode="estimated", exact_limit=10)

    with pytest.raises(ValidationError):
        DataExportSubmitRequest(
            targets={"scope": "selected", "content_ids": [uuid4()]},
            columns=["title", "title"],
        )

    item_id = uuid4()
    request = NotificationMarkReadRequest(item_ids=[item_id])
    assert request.item_ids == (item_id,)


def test_export_catalog_keys_and_excel_headers_share_the_public_contract() -> None:
    """页面目录中的每个默认列都必须可提交并能映射到真实 Excel 表头。"""

    catalog_keys = {item.key for item in EXPORT_COLUMNS}
    request = DataExportSubmitRequest(
        targets={"scope": "selected", "content_ids": [uuid4()]},
        columns=tuple(item.key for item in EXPORT_COLUMNS),  # type: ignore[arg-type]
    )

    assert set(request.columns) == catalog_keys
    assert export_column_headers(tuple(item.key for item in EXPORT_COLUMNS))
    assert export_column_headers(("voice_type",)) == ("发声类型",)


def test_confirmed_unavailable_requires_explicit_provider_evidence() -> None:
    """人工判断不能伪装 Provider 已明确下架，技术失败也不能证明可用。"""

    with pytest.raises(ValidationError):
        ContentAvailabilityObservationRequest(
            content_id=uuid4(),
            status="unavailable_confirmed",
            reason_code="manual_guess",
            evidence_kind="manual_review",
        )

    with pytest.raises(ValidationError):
        ContentAvailabilityObservationRequest(
            content_id=uuid4(),
            status="unavailable_confirmed",
            reason_code="unsupported_provider_claim",
            evidence_kind="provider_explicit",
        )

    explicit = ContentAvailabilityObservationRequest(
        content_id=uuid4(),
        status="unavailable_confirmed",
        reason_code="provider_deleted",
        evidence_kind="provider_explicit",
        raw_artifact_id=uuid4(),
    )
    assert explicit.raw_artifact_id is not None

    with pytest.raises(ValidationError):
        ContentAvailabilityObservationRequest(
            content_id=uuid4(),
            status="available",
            reason_code="request_failed",
            evidence_kind="technical_failure",
        )


def test_truncated_exact_count_does_not_claim_an_exact_total() -> None:
    """有界扫描超限时只表达无可靠总数，不能把扫描上限叫作精确值。"""

    response = ContentCountResponse(
        count_mode="exact",
        count=None,
        count_kind="none",
        truncated=True,
        as_of=datetime.now(UTC),
    )
    assert response.count is None

    with pytest.raises(ValidationError):
        ContentCountResponse(
            count_mode="exact",
            count=100_000,
            count_kind="exact",
            truncated=True,
            as_of=datetime.now(UTC),
        )
