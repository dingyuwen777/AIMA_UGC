"""Stage 2 BrandVehicleResolver 确定性优先级与歧义回归。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.ingestion.brand_vehicle_filter import (
    BrandVehicleFilterSnapshot,
    filter_canonical_content_by_brand_vehicle_jsonl,
)
from aima_ugc.modules.vehicles.brand_vehicle import (
    BrandAliasRecord,
    BrandRecord,
    BrandVehicleCatalogSnapshot,
    BrandVehicleResolver,
    VehicleAliasRecord,
    VehicleRecord,
)

NOW = datetime(2026, 9, 9, tzinfo=UTC)
BRAND_A = UUID("00000000-0000-0000-0000-000000000001")
BRAND_B = UUID("00000000-0000-0000-0000-000000000002")
VEHICLE_A = UUID("00000000-0000-0000-0000-000000000101")


def _snapshot(*, ambiguous_brand_alias: bool = False) -> BrandVehicleCatalogSnapshot:
    brand_aliases = [
        BrandAliasRecord(
            id=UUID("00000000-0000-0000-0000-000000000011"),
            brand_id=BRAND_A,
            text="爱玛",
            normalized_text="爱玛",
            created_at=NOW,
        ),
        BrandAliasRecord(
            id=UUID("00000000-0000-0000-0000-000000000012"),
            brand_id=BRAND_B,
            text="竞品B",
            normalized_text="竞品b",
            created_at=NOW,
        ),
    ]
    if ambiguous_brand_alias:
        brand_aliases.append(
            BrandAliasRecord(
                id=UUID("00000000-0000-0000-0000-000000000013"),
                brand_id=BRAND_B,
                text="爱玛",
                normalized_text="爱玛",
                created_at=NOW,
            )
        )
    return BrandVehicleCatalogSnapshot(
        catalog_version=8,
        filter_scope="all_active",
        selected_brand_ids=(BRAND_A, BRAND_B),
        brands=(
            BrandRecord(
                id=BRAND_A,
                code="AIMA",
                display_name="爱玛",
                role="owned",
                status="active",
                version=2,
                catalog_version=8,
                created_at=NOW,
                updated_at=NOW,
            ),
            BrandRecord(
                id=BRAND_B,
                code="COMP-B",
                display_name="竞品 B",
                role="competitor",
                status="active",
                version=1,
                catalog_version=7,
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
        brand_aliases=tuple(brand_aliases),
        vehicles=(
            VehicleRecord(
                id=VEHICLE_A,
                code="LUNA-AIR",
                display_name="露娜 Air",
                brand_id=BRAND_A,
                status="active",
                version=3,
                catalog_version=8,
            ),
        ),
        vehicle_aliases=(
            VehicleAliasRecord(
                id=UUID("00000000-0000-0000-0000-000000000111"),
                vehicle_model_id=VEHICLE_A,
                text="露娜Air",
                normalized_text="露娜air",
                created_at=NOW,
            ),
        ),
    )


def _content(*, external_content_id: str, title: str) -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=external_content_id,
        content_type="note",
        title=title,
        text=None,
        observed_at=NOW,
        observed_fields=("title",),
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            source_type="aima-monitoring-excel.v1",
            source_value="input.xlsx",
            observed_at=NOW,
        ),
    )


def test_vehicle_alias_resolves_vehicle_and_derives_its_brand() -> None:
    resolution = BrandVehicleResolver().resolve(
        _snapshot(),
        title="刚提爱玛露娜Air",
        raw_text="正文不重要",
        transcript_text=None,
    )

    assert resolution.matched is True
    assert resolution.vehicle_matches == (VEHICLE_A,)
    assert resolution.brand_matches == (BRAND_A,)
    assert resolution.effective_vehicle_model_ids == (VEHICLE_A,)
    assert resolution.effective_brand_ids == (BRAND_A,)
    assert [item.source for item in resolution.vehicle_evidence] == ["alias_match"]
    assert [item.source for item in resolution.brand_evidence] == ["vehicle_match"]
    assert resolution.conflicts == ()


def test_brand_alias_supplements_vehicle_derived_brand_and_supports_multiple_brands() -> None:
    resolution = BrandVehicleResolver().resolve(
        _snapshot(),
        title="露娜Air 对比竞品B",
        raw_text=None,
        transcript_text=None,
    )

    assert resolution.vehicle_matches == (VEHICLE_A,)
    assert set(resolution.brand_matches) == {BRAND_A, BRAND_B}
    assert {item.source for item in resolution.brand_evidence} == {"vehicle_match", "alias_match"}


def test_ambiguous_brand_alias_is_observable_and_never_guessed() -> None:
    resolution = BrandVehicleResolver().resolve(
        _snapshot(ambiguous_brand_alias=True),
        title="爱玛新品",
        raw_text=None,
        transcript_text=None,
    )

    assert resolution.matched is False
    assert resolution.brand_matches == ()
    assert resolution.vehicle_matches == ()
    assert resolution.conflicts == ("ambiguous_brand_alias:爱玛",)


def test_title_has_priority_over_lower_fields() -> None:
    resolution = BrandVehicleResolver().resolve(
        _snapshot(),
        title="竞品B新品",
        raw_text="露娜Air",
        transcript_text="爱玛",
    )

    assert resolution.vehicle_matches == (VEHICLE_A,)
    assert set(resolution.brand_matches) == {BRAND_A, BRAND_B}
    vehicle_evidence = resolution.vehicle_evidence[0]
    assert vehicle_evidence.source_field == "raw_text"
    brand_alias_evidence = next(
        item for item in resolution.brand_evidence if item.source == "alias_match"
    )
    assert brand_alias_evidence.entity_id == BRAND_B
    assert brand_alias_evidence.source_field == "title"


def test_selected_scope_does_not_hide_global_brand_alias_ambiguity() -> None:
    snapshot = _snapshot()
    snapshot = BrandVehicleCatalogSnapshot(
        catalog_version=snapshot.catalog_version,
        filter_scope="selected",
        selected_brand_ids=(BRAND_A,),
        brands=(snapshot.brands[0],),
        brand_aliases=(snapshot.brand_aliases[0],),
        vehicles=snapshot.vehicles,
        vehicle_aliases=snapshot.vehicle_aliases,
        ambiguous_brand_aliases=("爱玛",),
    )

    resolution = BrandVehicleResolver().resolve(
        snapshot,
        title="爱玛新品",
        raw_text=None,
        transcript_text=None,
    )

    assert resolution.matched is False
    assert resolution.brand_matches == ()
    assert resolution.conflicts == ("ambiguous_brand_alias:爱玛",)


def test_manual_brand_lock_is_independent_from_vehicle_resolution() -> None:
    resolution = BrandVehicleResolver().resolve(
        _snapshot(),
        title="露娜Air 竞品B",
        raw_text=None,
        transcript_text=None,
        manual_brand_ids=(BRAND_B,),
    )

    assert resolution.vehicle_matches == (VEHICLE_A,)
    assert resolution.brand_matches == (BRAND_B,)
    assert resolution.brand_evidence[0].source == "manual_review"
    assert resolution.vehicle_evidence[0].source == "alias_match"


def test_stage3_filter_snapshot_round_trip_preserves_frozen_catalog() -> None:
    snapshot = BrandVehicleFilterSnapshot(catalog=_snapshot())

    restored = BrandVehicleFilterSnapshot.model_validate_json(snapshot.model_dump_json())

    assert restored == snapshot
    assert restored.search_semantics == "not_applicable"
    assert restored.catalog.filter_scope == "all_active"


def test_stage4_filter_snapshot_marks_keyword_pack_search_semantics() -> None:
    """TikHub Discovery 快照显式记录 Search Terms 来源，不与 Excel 语义混淆。"""

    snapshot = BrandVehicleFilterSnapshot(
        search_semantics="keyword_pack",
        catalog=_snapshot(),
    )

    restored = BrandVehicleFilterSnapshot.model_validate_json(snapshot.model_dump_json())
    assert restored.search_semantics == "keyword_pack"


def test_stage3_jsonl_filter_uses_resolver_and_writes_only_matches(tmp_path: Path) -> None:
    source = tmp_path / "canonical.jsonl"
    output = tmp_path / "filtered.jsonl"
    source.write_text(
        "".join(
            f"{content.model_dump_json()}\n"
            for content in (
                _content(external_content_id="matched", title="爱玛露娜Air 新品"),
                _content(external_content_id="unmatched", title="普通行业资讯"),
            )
        ),
        encoding="utf-8",
    )

    summary = filter_canonical_content_by_brand_vehicle_jsonl(
        input_path=source,
        output_path=output,
        snapshot=BrandVehicleFilterSnapshot(catalog=_snapshot()),
    )
    records = tuple(
        UnifiedContentRecordV1.model_validate_json(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    )

    assert summary.rows_seen == 2
    assert summary.rows_written == 1
    assert summary.rows_filtered_out == 1
    assert [record.content.external_content_id for record in records] == ["matched"]
