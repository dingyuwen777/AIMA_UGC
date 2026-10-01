"""数据库冻结目录的全字段品牌先行与局部车型消歧场景。"""

from dataclasses import replace
from uuid import UUID

import pytest
from aima_ugc.modules.vehicles.brand_vehicle import (
    BrandVehicleCatalogSnapshot,
    BrandVehicleResolver,
    VehicleAliasRecord,
)

from tests.unit.test_brand_vehicle_resolver import (
    BRAND_A,
    BRAND_B,
    NOW,
    VEHICLE_A,
    VEHICLE_B,
    _snapshot,
)


def _catalog(*, shared: bool = False) -> BrandVehicleCatalogSnapshot:
    snapshot = _snapshot()
    aliases = (
        *snapshot.vehicle_aliases,
        VehicleAliasRecord(UUID(int=201), VEHICLE_A, "O", "o", NOW),
        VehicleAliasRecord(UUID(int=202), VEHICLE_B, "X", "x", NOW),
    )
    if shared:
        aliases += (VehicleAliasRecord(UUID(int=203), VEHICLE_B, "O", "o", NOW),)
    return replace(snapshot, vehicle_aliases=aliases)


def _resolve(title: str, text: str | None = None, *, shared: bool = False):  # type: ignore[no-untyped-def]
    snapshot = _catalog(shared=shared)
    return BrandVehicleResolver(snapshot).resolve(
        snapshot, title=title, raw_text=text, transcript_text=None
    )


def test_all_brands_and_vehicles_across_fields_are_kept() -> None:
    result = _resolve("爱玛 O", "竞品B X")
    assert result.effective_brand_ids == (BRAND_A, BRAND_B)
    assert result.effective_vehicle_model_ids == (VEHICLE_A, VEHICLE_B)
    assert [item.source_field for item in result.brand_evidence] == ["title", "raw_text"]


def test_all_vehicles_in_the_same_field_are_kept() -> None:
    result = _resolve("爱玛 O 对比竞品B X")
    assert result.effective_brand_ids == (BRAND_A, BRAND_B)
    assert result.effective_vehicle_model_ids == (VEHICLE_A, VEHICLE_B)


@pytest.mark.parametrize("title", ["露娜Air", "O 型测试", "只是竞速X"])
def test_no_brand_does_not_infer_automatic_vehicle_or_brand(title: str) -> None:
    result = _resolve(title)
    assert not result.matched
    assert result.vehicle_evidence == ()
    assert result.brand_evidence == ()


@pytest.mark.parametrize(
    ("title", "text"),
    [
        ("爱玛今天体验", "O 型测试"),
        ("爱玛。O 型测试", None),
        ("爱玛" + "好" * 13 + " O", None),
        ("爱玛竞品B O", None),
        ("爱玛 SO GOOD", None),
    ],
)
def test_single_letter_requires_its_local_brand_context(title: str, text: str | None) -> None:
    result = _resolve(title, text)
    assert result.effective_vehicle_model_ids == ()


@pytest.mark.parametrize("title", ["爱玛 O", "O 爱玛", "爱玛" + "好" * 11 + " O"])
def test_single_letter_with_unique_local_brand_is_accepted(title: str) -> None:
    assert _resolve(title).effective_vehicle_model_ids == (VEHICLE_A,)


def test_normal_alias_can_use_brand_from_another_field() -> None:
    result = _resolve("爱玛新车", "露娜Air 骑起来很好")
    assert result.effective_vehicle_model_ids == (VEHICLE_A,)


def test_shared_alias_is_assigned_once_when_local_owner_is_unique() -> None:
    result = _resolve("爱玛 O 对比竞品B X", shared=True)
    assert result.effective_vehicle_model_ids == (VEHICLE_A, VEHICLE_B)


def test_shared_alias_after_two_brands_is_ambiguous() -> None:
    result = _resolve("爱玛和竞品B，O到底哪个好", shared=True)
    assert result.effective_brand_ids == (BRAND_A, BRAND_B)
    assert result.effective_vehicle_model_ids == ()
    assert "ambiguous_vehicle_alias:o" in result.conflicts


def test_manual_brand_limits_automatic_vehicle_scope() -> None:
    snapshot = _catalog()
    result = BrandVehicleResolver(snapshot).resolve(
        snapshot,
        title="爱玛露娜Air 竞品B竞速X",
        raw_text=None,
        transcript_text=None,
        manual_brand_ids=(BRAND_A,),
    )
    assert result.effective_brand_ids == (BRAND_A,)
    assert result.effective_vehicle_model_ids == (VEHICLE_A,)


def test_manual_vehicle_is_preserved_without_brand_in_text() -> None:
    snapshot = _catalog()
    result = BrandVehicleResolver(snapshot).resolve(
        snapshot,
        title="体验很好",
        raw_text=None,
        transcript_text=None,
        manual_vehicle_ids=(VEHICLE_B,),
    )
    assert result.effective_vehicle_model_ids == (VEHICLE_B,)
    assert result.effective_brand_ids == (BRAND_B,)
    assert result.vehicle_evidence[0].source == "manual_review"
