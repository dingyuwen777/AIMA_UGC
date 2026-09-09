"""品牌 / 车型统一目录的纯确定性解析器。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Literal
from uuid import UUID

from .models import (
    BrandVehicleResolution,
    CatalogSnapshot,
    ResolutionConflict,
    ResolutionEvidence,
    normalize_vehicle_text,
)

SourceField = Literal["title", "raw_text", "transcript_text"]
_FIELD_ORDER: tuple[SourceField, ...] = ("title", "raw_text", "transcript_text")


class BrandVehicleResolver:
    """只使用冻结 CatalogSnapshot 做可复现的别名匹配，不做模糊猜测。"""

    def __init__(self, snapshot: CatalogSnapshot) -> None:
        self._snapshot = snapshot
        active_brands = {item.id for item in snapshot.brands if item.status == "active"}
        active_vehicles = {item.id: item for item in snapshot.vehicles if item.status == "active"}
        self._vehicles = active_vehicles
        self._brand_aliases: defaultdict[str, list[tuple[UUID, str]]] = defaultdict(list)
        self._vehicle_aliases: defaultdict[str, list[tuple[UUID, str]]] = defaultdict(list)
        for alias in snapshot.brand_aliases:
            if alias.brand_id in active_brands:
                self._brand_aliases[alias.normalized_text].append((alias.brand_id, alias.text))
        for alias in snapshot.vehicle_aliases:
            if alias.vehicle_model_id in active_vehicles:
                self._vehicle_aliases[alias.normalized_text].append(
                    (alias.vehicle_model_id, alias.text)
                )

    def resolve(
        self,
        *,
        title: str | None,
        raw_text: str | None,
        transcript_text: str | None,
    ) -> BrandVehicleResolution:
        """车型别名先解析并派生品牌；品牌别名只补充尚未派生出的品牌。"""

        fields: dict[SourceField, str | None] = {
            "title": title,
            "raw_text": raw_text,
            "transcript_text": transcript_text,
        }
        vehicle_evidence, vehicle_conflicts = self._resolve_aliases(
            fields, aliases=self._vehicle_aliases, kind="vehicle"
        )
        brand_evidence: list[ResolutionEvidence] = []
        derived_brand_ids: set[UUID] = set()
        for evidence in vehicle_evidence:
            vehicle = self._vehicles[evidence.target_id]
            if vehicle.brand_id is None or vehicle.brand_id in derived_brand_ids:
                continue
            derived_brand_ids.add(vehicle.brand_id)
            brand_evidence.append(
                ResolutionEvidence(
                    kind="brand",
                    target_id=vehicle.brand_id,
                    source="vehicle_match",
                    matched_text=evidence.matched_text,
                    source_field=evidence.source_field,
                    derived_vehicle_model_id=vehicle.id,
                )
            )

        direct_brand_evidence, brand_conflicts = self._resolve_aliases(
            fields, aliases=self._brand_aliases, kind="brand"
        )
        seen_brand_ids = set(derived_brand_ids)
        for evidence in direct_brand_evidence:
            if evidence.target_id in seen_brand_ids:
                continue
            seen_brand_ids.add(evidence.target_id)
            brand_evidence.append(evidence)

        return BrandVehicleResolution(
            catalog_version=self._snapshot.catalog_version,
            brand_evidence=tuple(brand_evidence),
            vehicle_evidence=vehicle_evidence,
            conflicts=vehicle_conflicts + brand_conflicts,
        )

    @staticmethod
    def _resolve_aliases(
        fields: dict[SourceField, str | None],
        *,
        aliases: dict[str, list[tuple[UUID, str]]],
        kind: Literal["brand", "vehicle"],
    ) -> tuple[tuple[ResolutionEvidence, ...], tuple[ResolutionConflict, ...]]:
        for field in _FIELD_ORDER:
            raw_value = fields[field]
            if raw_value is None or not raw_value.strip():
                continue
            normalized = normalize_vehicle_text(raw_value)
            matches = tuple(
                (normalized_alias, bindings)
                for normalized_alias, bindings in aliases.items()
                if normalized_alias in normalized
            )
            if not matches:
                continue
            return BrandVehicleResolver._evidence_for_field(
                matches, kind=kind, source_field=field
            )
        return (), ()

    @staticmethod
    def _evidence_for_field(
        matches: Iterable[tuple[str, list[tuple[UUID, str]]]],
        *,
        kind: Literal["brand", "vehicle"],
        source_field: SourceField,
    ) -> tuple[tuple[ResolutionEvidence, ...], tuple[ResolutionConflict, ...]]:
        evidence_by_id: dict[UUID, ResolutionEvidence] = {}
        conflicts: list[ResolutionConflict] = []
        for normalized_alias, bindings in matches:
            candidates = tuple(sorted({target_id for target_id, _ in bindings}, key=str))
            if len(candidates) != 1:
                conflicts.append(
                    ResolutionConflict(
                        kind=kind,
                        normalized_text=normalized_alias,
                        candidate_ids=candidates,
                        source_field=source_field,
                    )
                )
                continue
            target_id = candidates[0]
            matched_text = next(text for candidate_id, text in bindings if candidate_id == target_id)
            evidence_by_id.setdefault(
                target_id,
                ResolutionEvidence(
                    kind=kind,
                    target_id=target_id,
                    source="alias_match",
                    matched_text=matched_text,
                    source_field=source_field,
                ),
            )
        if len(evidence_by_id) > 1:
            candidate_ids = tuple(sorted(evidence_by_id, key=str))
            conflicts.append(
                ResolutionConflict(
                    kind=kind,
                    normalized_text="<multiple-aliases>",
                    candidate_ids=candidate_ids,
                    source_field=source_field,
                )
            )
            return (), tuple(conflicts)
        return tuple(evidence_by_id.values()), tuple(conflicts)


__all__ = ["BrandVehicleResolver"]
