"""历史目录保持原编码，新目录把算法语义纳入持久身份。"""

import hashlib
from dataclasses import replace
from uuid import UUID

import pytest
from aima_ugc.adapters.persistence.postgres.canonical_replay import _selection_digest
from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot
from aima_ugc.modules.ingestion.canonical_replay import dump_filter_snapshot, load_filter_snapshot
from aima_ugc.modules.vehicles.content_reclassification import (
    dump_catalog_snapshot,
    load_catalog_snapshot,
)
from pydantic import ValidationError

from tests.unit.test_brand_vehicle_resolver import _snapshot


def test_legacy_catalog_roundtrip_preserves_missing_semantics_field() -> None:
    encoded = dump_catalog_snapshot(_snapshot())
    encoded.pop("resolver_semantics", None)
    restored = load_catalog_snapshot(encoded)
    assert restored.resolver_semantics == "field_priority_v1"
    assert dump_catalog_snapshot(restored) == encoded


def test_new_semantics_survives_both_persistent_snapshot_codecs() -> None:
    catalog = replace(
        _snapshot(),
        resolver_semantics="brand_scoped_vehicle_v2",
        automatic_evidence_vehicle_ids=(UUID(int=111), UUID(int=222)),
    )
    encoded = dump_catalog_snapshot(catalog)
    assert encoded["resolver_semantics"] == "brand_scoped_vehicle_v2"
    assert load_catalog_snapshot(encoded) == catalog
    frozen_filter = BrandVehicleFilterSnapshot(catalog=catalog)
    assert load_filter_snapshot(dump_filter_snapshot(frozen_filter)) == frozen_filter


def test_legacy_filter_roundtrip_preserves_original_identity() -> None:
    encoded = dump_filter_snapshot(BrandVehicleFilterSnapshot(catalog=_snapshot()))
    encoded["catalog"].pop("resolver_semantics", None)  # type: ignore[union-attr]
    restored = load_filter_snapshot(encoded)
    assert restored.catalog.resolver_semantics == "field_priority_v1"
    assert dump_filter_snapshot(restored) == encoded


def test_unknown_semantics_is_rejected_when_loading_persistent_catalog() -> None:
    encoded = dump_catalog_snapshot(_snapshot())
    encoded["resolver_semantics"] = "unknown_v9"
    with pytest.raises(ValidationError):
        load_catalog_snapshot(encoded)


def test_selection_digest_separates_semantics_without_changing_legacy_bytes() -> None:
    artifact_id = UUID(int=42)
    candidates = ((artifact_id, "excel_import_v2"),)
    legacy = hashlib.sha256(artifact_id.bytes + b"\0excel_import_v2\n").hexdigest()
    assert _selection_digest(candidates) == legacy
    assert _selection_digest(candidates, resolver_semantics="field_priority_v1") == legacy
    assert _selection_digest(candidates, resolver_semantics="brand_scoped_vehicle_v2") != legacy
