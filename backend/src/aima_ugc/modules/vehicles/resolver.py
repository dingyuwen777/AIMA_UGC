"""品牌 / 车型统一目录的纯确定性解析器。"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal
from uuid import UUID

from aima_ugc.contracts.canonical import CanonicalContentV1

from .models import (
    BrandVehicleResolution,
    CatalogSnapshot,
    ResolutionConflict,
    ResolutionEvidence,
    ResolutionSourceField,
    normalize_vehicle_text,
)

_FIELD_ORDER: tuple[ResolutionSourceField, ...] = ("title", "text")


class BrandVehicleResolver:
    """只使用冻结 CatalogSnapshot 做可复现别名匹配，不做模糊猜测。"""

    def __init__(self, snapshot: CatalogSnapshot) -> None:
        self._snapshot = snapshot
        active_brands = {item.id for item in snapshot.brands if item.status == "active"}
        self._vehicles = {
            item.id: item
            for item in snapshot.vehicles
            if item.status == "active" and item.brand_id in active_brands
        }
        self._brand_aliases: defaultdict[str, list[tuple[UUID, str]]] = defaultdict(list)
        self._vehicle_aliases: defaultdict[str, list[tuple[UUID, str]]] = defaultdict(list)
        for alias in snapshot.brand_aliases:
            if alias.brand_id in active_brands:
                self._brand_aliases[alias.normalized_text].append((alias.brand_id, alias.text))
        for alias in snapshot.vehicle_aliases:
            if alias.vehicle_model_id in self._vehicles:
                self._vehicle_aliases[alias.normalized_text].append(
                    (alias.vehicle_model_id, alias.text)
                )

    def resolve(self, content: CanonicalContentV1) -> BrandVehicleResolution:
        """解析 CanonicalContentV1；车型命中同时派生所属品牌。"""

        fields: dict[ResolutionSourceField, str | None] = {
            "title": content.title,
            "text": content.text,
        }
        vehicle_matches, vehicle_conflicts = self._resolve_aliases(
            fields,
            aliases=self._vehicle_aliases,
            kind="vehicle",
        )

        brand_matches: list[ResolutionEvidence] = []
        derived_brand_ids: set[UUID] = set()
        for evidence in vehicle_matches:
            vehicle = self._vehicles[evidence.target_id]
            if vehicle.brand_id is None or vehicle.brand_id in derived_brand_ids:
                continue
            derived_brand_ids.add(vehicle.brand_id)
            brand_matches.append(
                ResolutionEvidence(
                    kind="brand",
                    target_id=vehicle.brand_id,
                    source="vehicle_match",
                    matched_text=evidence.matched_text,
                    source_field=evidence.source_field,
                    derived_vehicle_model_id=vehicle.id,
                )
            )

        direct_brand_matches, brand_conflicts = self._resolve_aliases(
            fields,
            aliases=self._brand_aliases,
            kind="brand",
        )
        seen_brand_ids = set(derived_brand_ids)
        for evidence in direct_brand_matches:
            if evidence.target_id in seen_brand_ids:
                continue
            seen_brand_ids.add(evidence.target_id)
            brand_matches.append(evidence)

        effective_brand_ids = tuple(sorted(seen_brand_ids, key=str))
        effective_vehicle_model_ids = tuple(
            sorted((item.target_id for item in vehicle_matches), key=str)
        )
        return BrandVehicleResolution(
            catalog_version=self._snapshot.catalog_version,
            matched=bool(effective_brand_ids or effective_vehicle_model_ids),
            brand_matches=tuple(brand_matches),
            vehicle_matches=vehicle_matches,
            effective_brand_ids=effective_brand_ids,
            effective_vehicle_model_ids=effective_vehicle_model_ids,
            conflicts=vehicle_conflicts + brand_conflicts,
        )

    @staticmethod
    def _resolve_aliases(
        fields: dict[ResolutionSourceField, str | None],
        *,
        aliases: dict[str, list[tuple[UUID, str]]],
        kind: Literal["brand", "vehicle"],
    ) -> tuple[tuple[ResolutionEvidence, ...], tuple[ResolutionConflict, ...]]:
        evidence_by_id: dict[UUID, ResolutionEvidence] = {}
        conflicts: list[ResolutionConflict] = []
        ordered_aliases = tuple(sorted(aliases, key=lambda value: (-len(value), value)))

        for field in _FIELD_ORDER:
            raw_value = fields[field]
            if raw_value is None or not raw_value.strip():
                continue
            normalized_content = normalize_vehicle_text(raw_value)
            for normalized_alias in ordered_aliases:
                if normalized_alias not in normalized_content:
                    continue
                bindings = aliases[normalized_alias]
                candidates = tuple(sorted({target_id for target_id, _ in bindings}, key=str))
                if len(candidates) != 1:
                    conflicts.append(
                        ResolutionConflict(
                            kind=kind,
                            normalized_text=normalized_alias,
                            candidate_ids=candidates,
                            source_field=field,
                        )
                    )
                    continue
                target_id = candidates[0]
                matched_text = next(
                    text for candidate_id, text in bindings if candidate_id == target_id
                )
                evidence_by_id.setdefault(
                    target_id,
                    ResolutionEvidence(
                        kind=kind,
                        target_id=target_id,
                        source="alias_match",
                        matched_text=matched_text,
                        source_field=field,
                    ),
                )

        return tuple(evidence_by_id.values()), tuple(conflicts)


__all__ = ["BrandVehicleResolver"]
