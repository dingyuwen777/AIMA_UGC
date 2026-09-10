"""Stage 5 Brand/Vehicle 查询、Cursor 与导出公共 Contract。"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.content_http import _query_hash
from aima_ugc.contracts.http import (
    ContentBrandEvidenceResponse,
    ContentBrandReferenceResponse,
    ContentBrandResponse,
    ContentFilterSnapshot,
    ContentListItemResponse,
    ContentMetricsResponse,
    ContentSourceResponse,
    ContentVehicleEvidenceResponse,
    ContentVehicleResponse,
    DataExportSubmitRequest,
)
from aima_ugc.modules.content.content_cursor import (
    ContentCursorCodec,
    ContentCursorPosition,
    InvalidContentCursor,
)
from aima_ugc.modules.reporting.column_catalog import (
    EXPORT_COLUMN_CATALOG_VERSION,
    EXPORT_COLUMNS,
    export_column_headers,
)
from pydantic import ValidationError


def test_content_filter_accepts_brand_and_competition_sets_and_rejects_duplicates() -> None:
    """新增筛选是稳定 ID/枚举集合，同维度不允许重复。"""

    first, second = uuid4(), uuid4()
    snapshot = ContentFilterSnapshot(
        brand_ids=(first, second),
        competition_scopes=("owned_only", "mixed"),
    )

    assert snapshot.brand_ids == (first, second)
    assert snapshot.competition_scopes == ("owned_only", "mixed")

    with pytest.raises(ValidationError, match="brand_ids 不能重复"):
        ContentFilterSnapshot(brand_ids=(first, first))
    with pytest.raises(ValidationError, match="competition_scopes 不能重复"):
        ContentFilterSnapshot(competition_scopes=("mixed", "mixed"))


def test_content_read_model_keeps_brand_evidence_and_vehicle_brand_consistent() -> None:
    """品牌、车型所属品牌与派生竞品范围形成可审计响应。"""

    now = datetime(2026, 9, 10, tzinfo=UTC)
    brand_id = uuid4()
    vehicle_id = uuid4()
    brand = ContentBrandResponse(
        id=brand_id,
        code="AIMA",
        display_name="爱玛",
        role="owned",
        evidences=(
            ContentBrandEvidenceResponse(
                source="vehicle_match",
                matched_text="露娜 Air",
                source_field="title",
                derived_vehicle_model_id=vehicle_id,
                catalog_version=3,
                confidence=1.0,
            ),
        ),
    )
    item = ContentListItemResponse(
        id=uuid4(),
        content_version=1,
        platform="xiaohongshu",
        external_content_id="stage5-contract",
        content_type="note",
        last_seen_at=now,
        metrics=ContentMetricsResponse(),
        analysis={"status": "pending"},
        source=ContentSourceResponse(provider_name="file-import"),
        brands=(brand,),
        vehicles=(
            ContentVehicleResponse(
                vehicle_model_id=vehicle_id,
                code="LUNA-AIR",
                display_name="露娜 Air",
                brand=ContentBrandReferenceResponse(
                    id=brand_id,
                    code="AIMA",
                    display_name="爱玛",
                    role="owned",
                ),
                evidences=(
                    ContentVehicleEvidenceResponse(
                        source="alias_match",
                        matched_text="露娜 Air",
                        source_field="title",
                        catalog_version=3,
                    ),
                ),
            ),
        ),
        competition_scope="owned_only",
    )

    assert item.brands[0].evidences[0].derived_vehicle_model_id == vehicle_id
    assert item.vehicles[0].brand is not None
    assert item.vehicles[0].brand.id == brand_id
    assert item.competition_scope == "owned_only"

    with pytest.raises(ValidationError, match="competition_scope 必须由 brands 的 role 派生"):
        item.model_copy(update={"competition_scope": "competitor_only"}, deep=True).model_validate(
            {
                **item.model_dump(),
                "competition_scope": "competitor_only",
            }
        )


def test_cursor_query_hash_binds_brand_and_competition_filters() -> None:
    """新增过滤条件改变时，旧 Cursor 不得跨查询复用。"""

    now = datetime(2026, 9, 10, tzinfo=UTC)
    brand_id = uuid4()
    owned = ContentFilterSnapshot(
        brand_ids=(brand_id,),
        competition_scopes=("owned_only",),
    )
    mixed = ContentFilterSnapshot(
        brand_ids=(brand_id,),
        competition_scopes=("mixed",),
    )
    codec = ContentCursorCodec(secret=b"stage5-cursor-secret-is-at-least-32-bytes", now=lambda: now)
    cursor = codec.encode(
        ContentCursorPosition(sort_at=now, content_id=uuid4()),
        query_hash=_query_hash(owned),
    )

    assert _query_hash(owned) != _query_hash(mixed)
    with pytest.raises(InvalidContentCursor):
        codec.decode(cursor, query_hash=_query_hash(mixed))


def test_export_catalog_exposes_distinct_brand_role_competition_and_vehicle_columns() -> None:
    """导出列各自有稳定 key，不借用 matched_keywords。"""

    keys = tuple(item.key for item in EXPORT_COLUMNS)
    request = DataExportSubmitRequest(
        targets={"scope": "selected", "content_ids": [uuid4()]},
        columns=("matched_keywords", "brands", "brand_roles", "competition_scope", "vehicles"),
    )

    assert EXPORT_COLUMN_CATALOG_VERSION == 2
    assert {"brands", "brand_roles", "competition_scope", "vehicles"}.issubset(keys)
    assert request.columns == (
        "matched_keywords",
        "brands",
        "brand_roles",
        "competition_scope",
        "vehicles",
    )
    assert export_column_headers(request.columns) == (
        "命中关键词",
        "品牌",
        "品牌角色",
        "竞品范围",
        "车型",
    )
