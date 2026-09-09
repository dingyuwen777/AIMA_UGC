"""Stage 2 BrandVehicleResolver 的确定性规则回归。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from aima_ugc.modules.vehicles.models import Brand, BrandAlias, CatalogSnapshot, VehicleAlias, VehicleModel
from aima_ugc.modules.vehicles.resolver import BrandVehicleResolver

NOW = datetime(2026, 9, 9, tzinfo=UTC)
BRAND_AIMA = UUID("00000000-0000-0000-0000-000000000001")
BRAND_OTHER = UUID("00000000-0000-0000-0000-000000000002")
VEHICLE_LUNA = UUID("00000000-0000-0000-0000-000000000101")
VEHICLE_M9_A = UUID("00000000-0000-0000-0000-000000000102")
VEHICLE_M9_B = UUID("00000000-0000-0000-0000-000000000103")


def _brand(brand_id: UUID, code: str, name: str) -> Brand:
    return Brand(
        id=brand_id,
        code=code,
        display_name=name,
        role="owned" if brand_id == BRAND_AIMA else "competitor",
        status="active",
        version=1,
        catalog_version=7,
        created_at=NOW,
        updated_at=NOW,
    )


def _vehicle(vehicle_id: UUID, code: str, brand_id: UUID) -> VehicleModel:
    return VehicleModel(
        id=vehicle_id,
        code=code,
        display_name=code,
        status="active",
        version=1,
        catalog_version=7,
        merged_into_id=None,
        created_at=NOW,
        updated_at=NOW,
        brand_id=brand_id,
    )


def _snapshot(*, ambiguous_m9: bool = False) -> CatalogSnapshot:
    vehicles = [_vehicle(VEHICLE_LUNA, "LUNA-AIR", BRAND_AIMA)]
    vehicle_aliases = [
        VehicleAlias(
            id=UUID("00000000-0000-0000-0000-000000001001"),
            vehicle_model_id=VEHICLE_LUNA,
            text="露娜Air",
            normalized_text="露娜air",
        )
    ]
    if ambiguous_m9:
        vehicles.extend(
            [
                _vehicle(VEHICLE_M9_A, "M9-A", BRAND_AIMA),
                _vehicle(VEHICLE_M9_B, "M9-B", BRAND_OTHER),
            ]
        )
        vehicle_aliases.extend(
            [
                VehicleAlias(
                    id=UUID("00000000-0000-0000-0000-000000001002"),
                    vehicle_model_id=VEHICLE_M9_A,
                    text="M9",
                    normalized_text="m9",
                ),
                VehicleAlias(
                    id=UUID("00000000-0000-0000-0000-000000001003"),
                    vehicle_model_id=VEHICLE_M9_B,
                    text="M9",
                    normalized_text="m9",
                ),
            ]
        )
    return CatalogSnapshot(
        catalog_version=7,
        brands=(
            _brand(BRAND_AIMA, "AIMA", "爱玛"),
            _brand(BRAND_OTHER, "OTHER", "竞品"),
        ),
        brand_aliases=(
            BrandAlias(
                id=UUID("00000000-0000-0000-0000-000000002001"),
                brand_id=BRAND_AIMA,
                text="爱玛",
                normalized_text="爱玛",
            ),
        ),
        vehicles=tuple(vehicles),
        vehicle_aliases=tuple(vehicle_aliases),
    )


def test_vehicle_alias_wins_and_derives_brand_without_duplicate_direct_brand() -> None:
    result = BrandVehicleResolver(_snapshot()).resolve(
        title="爱玛露娜Air新款",
        raw_text="爱玛通勤车",
        transcript_text=None,
    )

    assert [item.target_id for item in result.vehicle_evidence] == [VEHICLE_LUNA]
    assert len(result.brand_evidence) == 1
    assert result.brand_evidence[0].target_id == BRAND_AIMA
    assert result.brand_evidence[0].source == "vehicle_match"
    assert result.brand_evidence[0].derived_vehicle_model_id == VEHICLE_LUNA
    assert result.brand_evidence[0].source_field == "title"
    assert result.conflicts == ()


def test_field_priority_is_applied_independently_to_vehicle_and_brand_aliases() -> None:
    result = BrandVehicleResolver(_snapshot()).resolve(
        title="爱玛官方信息",
        raw_text="实际提到露娜Air",
        transcript_text="露娜Air",
    )

    assert result.vehicle_evidence[0].source_field == "raw_text"
    assert result.brand_evidence[0].source == "vehicle_match"
    assert result.brand_evidence[0].source_field == "raw_text"


def test_ambiguous_vehicle_alias_is_observable_and_not_guessed() -> None:
    result = BrandVehicleResolver(_snapshot(ambiguous_m9=True)).resolve(
        title="M9 到店体验",
        raw_text=None,
        transcript_text=None,
    )

    assert result.vehicle_evidence == ()
    vehicle_conflicts = [item for item in result.conflicts if item.kind == "vehicle"]
    assert len(vehicle_conflicts) == 1
    assert vehicle_conflicts[0].candidate_ids == (VEHICLE_M9_A, VEHICLE_M9_B)
    assert result.brand_evidence == ()
