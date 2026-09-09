"""Stage 2 BrandVehicleResolver 的确定性规则回归。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.modules.vehicles.models import (
    Brand,
    BrandAlias,
    CatalogSnapshot,
    VehicleAlias,
    VehicleModel,
)
from aima_ugc.modules.vehicles.resolver import BrandVehicleResolver

NOW = datetime(2026, 9, 9, tzinfo=UTC)
BRAND_AIMA = UUID("00000000-0000-0000-0000-000000000001")
BRAND_NIU = UUID("00000000-0000-0000-0000-000000000002")
VEHICLE_LUNA = UUID("00000000-0000-0000-0000-000000000101")
VEHICLE_UQI = UUID("00000000-0000-0000-0000-000000000102")
VEHICLE_M9_A = UUID("00000000-0000-0000-0000-000000000103")
VEHICLE_M9_B = UUID("00000000-0000-0000-0000-000000000104")


def _content(*, title: str | None = None, text: str | None = None) -> CanonicalContentV1:
    return CanonicalContentV1.model_construct(title=title, text=text)


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


def _snapshot(
    *,
    ambiguous_m9: bool = False,
    selected_only: bool = False,
) -> CatalogSnapshot:
    brands = (
        _brand(BRAND_AIMA, "AIMA", "爱玛"),
        _brand(BRAND_NIU, "NIU", "小牛"),
    )
    vehicles = [
        _vehicle(VEHICLE_LUNA, "LUNA-AIR", BRAND_AIMA),
        _vehicle(VEHICLE_UQI, "UQI", BRAND_NIU),
    ]
    vehicle_aliases = [
        VehicleAlias(
            id=UUID("00000000-0000-0000-0000-000000001001"),
            vehicle_model_id=VEHICLE_LUNA,
            text="露娜Air",
            normalized_text="露娜air",
        ),
        VehicleAlias(
            id=UUID("00000000-0000-0000-0000-000000001002"),
            vehicle_model_id=VEHICLE_UQI,
            text="UQi",
            normalized_text="uqi",
        ),
    ]
    if ambiguous_m9:
        vehicles.extend(
            [
                _vehicle(VEHICLE_M9_A, "M9-A", BRAND_AIMA),
                _vehicle(VEHICLE_M9_B, "M9-B", BRAND_NIU),
            ]
        )
        vehicle_aliases.extend(
            [
                VehicleAlias(
                    id=UUID("00000000-0000-0000-0000-000000001003"),
                    vehicle_model_id=VEHICLE_M9_A,
                    text="M9",
                    normalized_text="m9",
                ),
                VehicleAlias(
                    id=UUID("00000000-0000-0000-0000-000000001004"),
                    vehicle_model_id=VEHICLE_M9_B,
                    text="M9",
                    normalized_text="m9",
                ),
            ]
        )
    brand_aliases = (
        BrandAlias(
            id=UUID("00000000-0000-0000-0000-000000002001"),
            brand_id=BRAND_AIMA,
            text="爱玛",
            normalized_text="爱玛",
        ),
        BrandAlias(
            id=UUID("00000000-0000-0000-0000-000000002002"),
            brand_id=BRAND_NIU,
            text="小牛",
            normalized_text="小牛",
        ),
    )
    if selected_only:
        return CatalogSnapshot(
            catalog_version=7,
            brands=(brands[0],),
            brand_aliases=(brand_aliases[0],),
            vehicles=(vehicles[0],),
            vehicle_aliases=(vehicle_aliases[0],),
            filter_mode="selected",
            selected_brand_ids=(BRAND_AIMA,),
        )
    return CatalogSnapshot(
        catalog_version=7,
        brands=brands,
        brand_aliases=brand_aliases,
        vehicles=tuple(vehicles),
        vehicle_aliases=tuple(vehicle_aliases),
    )


def test_vehicle_alias_derives_brand_and_exposes_required_result_fields() -> None:
    result = BrandVehicleResolver(_snapshot()).resolve(
        _content(title="爱玛露娜Air新款", text="城市通勤")
    )

    assert result.matched is True
    assert result.effective_vehicle_model_ids == (VEHICLE_LUNA,)
    assert result.effective_brand_ids == (BRAND_AIMA,)
    assert result.vehicle_matches[0].target_id == VEHICLE_LUNA
    assert result.brand_matches[0].target_id == BRAND_AIMA
    assert result.brand_matches[0].source == "vehicle_match"
    assert result.brand_matches[0].derived_vehicle_model_id == VEHICLE_LUNA
    assert result.brand_matches[0].source_field == "title"
    assert result.conflicts == ()


def test_distinct_unambiguous_aliases_can_return_multiple_brands_and_vehicles() -> None:
    result = BrandVehicleResolver(_snapshot()).resolve(
        _content(title="露娜Air 与 UQi 对比", text="爱玛和小牛日常体验")
    )

    assert result.matched is True
    assert set(result.effective_vehicle_model_ids) == {VEHICLE_LUNA, VEHICLE_UQI}
    assert set(result.effective_brand_ids) == {BRAND_AIMA, BRAND_NIU}
    assert {item.target_id for item in result.vehicle_matches} == {
        VEHICLE_LUNA,
        VEHICLE_UQI,
    }
    assert {item.target_id for item in result.brand_matches} == {BRAND_AIMA, BRAND_NIU}
    assert result.conflicts == ()


def test_same_alias_with_multiple_active_entities_is_observable_and_not_guessed() -> None:
    result = BrandVehicleResolver(_snapshot(ambiguous_m9=True)).resolve(
        _content(title="M9 到店体验")
    )

    assert result.matched is False
    assert result.vehicle_matches == ()
    assert result.brand_matches == ()
    assert result.effective_vehicle_model_ids == ()
    assert result.effective_brand_ids == ()
    vehicle_conflicts = [item for item in result.conflicts if item.kind == "vehicle"]
    assert len(vehicle_conflicts) == 1
    assert vehicle_conflicts[0].candidate_ids == (VEHICLE_M9_A, VEHICLE_M9_B)


def test_frozen_selected_scope_ignores_entities_outside_snapshot() -> None:
    result = BrandVehicleResolver(_snapshot(selected_only=True)).resolve(
        _content(title="小牛 UQi", text="小牛体验")
    )

    assert result.matched is False
    assert result.effective_brand_ids == ()
    assert result.effective_vehicle_model_ids == ()
    assert result.conflicts == ()


def test_unmatched_canonical_content_is_explicit() -> None:
    result = BrandVehicleResolver(_snapshot()).resolve(
        _content(title="今天骑车上班", text="没有提到品牌或车型")
    )

    assert result.matched is False
    assert result.brand_matches == ()
    assert result.vehicle_matches == ()
    assert result.effective_brand_ids == ()
    assert result.effective_vehicle_model_ids == ()
