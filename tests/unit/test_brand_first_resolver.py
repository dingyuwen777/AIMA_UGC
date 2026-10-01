"""数据库冻结目录的全字段品牌先行与局部车型消歧场景。"""

from dataclasses import replace
from uuid import UUID

import aima_ugc.modules.vehicles.brand_vehicle as resolver_module
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
    return replace(snapshot, vehicle_aliases=aliases, resolver_semantics="brand_scoped_vehicle_v2")


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


def test_transcript_adds_brands_and_field_priority_selects_one_evidence() -> None:
    snapshot = _catalog()
    result = BrandVehicleResolver(snapshot).resolve(
        snapshot, title="爱玛 O", raw_text="爱玛露娜Air", transcript_text="竞品B X"
    )
    assert result.effective_brand_ids == (BRAND_A, BRAND_B)
    assert result.effective_vehicle_model_ids == (VEHICLE_A, VEHICLE_B)
    assert [item.source_field for item in result.vehicle_evidence] == ["title", "transcript_text"]
    assert result.vehicle_evidence[0].matched_text == "O"


@pytest.mark.parametrize("separator", [" " * 13, "\n", ";", "。"])
def test_local_distance_uses_original_characters_and_fragment_boundaries(separator: str) -> None:
    assert _resolve("爱玛" + separator + "O").effective_vehicle_model_ids == ()


def test_ambiguous_brand_alias_does_not_discard_other_brand_hits() -> None:
    snapshot = replace(
        _snapshot(ambiguous_brand_alias=True), resolver_semantics="brand_scoped_vehicle_v2"
    )
    result = BrandVehicleResolver(snapshot).resolve(
        snapshot, title="爱玛 竞品B 竞速X", raw_text=None, transcript_text=None
    )
    assert result.effective_brand_ids == (BRAND_B,)
    assert result.effective_vehicle_model_ids == (VEHICLE_B,)
    assert "ambiguous_brand_alias:爱玛" in result.conflicts


def test_locked_empty_brand_suppresses_automatic_models() -> None:
    snapshot = _catalog()
    result = BrandVehicleResolver(snapshot).resolve(
        snapshot,
        title="爱玛 O 竞品B X",
        raw_text=None,
        transcript_text=None,
        manual_brand_ids=(),
    )
    assert result.effective_brand_ids == ()
    assert result.effective_vehicle_model_ids == ()


def test_both_manual_locks_preserve_independent_choices() -> None:
    snapshot = _catalog()
    result = BrandVehicleResolver(snapshot).resolve(
        snapshot,
        title="爱玛露娜Air",
        raw_text=None,
        transcript_text=None,
        manual_brand_ids=(BRAND_A,),
        manual_vehicle_ids=(VEHICLE_B,),
    )
    assert result.effective_brand_ids == (BRAND_A,)
    assert result.effective_vehicle_model_ids == (VEHICLE_B,)


def test_compilation_is_reused_across_contents_and_semantic_change_recompiles(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    original = resolver_module._compile_catalog
    compiled = []

    def compile_catalog(snapshot):  # type: ignore[no-untyped-def]
        compiled.append(snapshot.resolver_semantics)
        return original(snapshot)

    monkeypatch.setattr(resolver_module, "_compile_catalog", compile_catalog)
    snapshot = _catalog()
    resolver = BrandVehicleResolver(snapshot)
    for _ in range(100):
        resolver.resolve(snapshot, title="爱玛 O", raw_text=None, transcript_text=None)
    resolver.resolve(
        replace(snapshot, resolver_semantics="field_priority_v1"),
        title="O",
        raw_text=None,
        transcript_text=None,
    )
    assert compiled == ["brand_scoped_vehicle_v2", "field_priority_v1"]
