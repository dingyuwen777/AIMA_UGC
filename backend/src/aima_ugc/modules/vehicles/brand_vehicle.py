"""品牌/车型统一目录对象与纯确定性解析器。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from aima_ugc.modules.vehicles.models import normalize_vehicle_text

BrandRole = Literal["owned", "competitor", "other"]
BrandStatus = Literal["active", "deprecated"]
FilterScope = Literal["all_active", "selected"]
ResolverSource = Literal["manual_review", "vehicle_match", "alias_match"]
ResolverField = Literal["title", "raw_text", "transcript_text"]


@dataclass(frozen=True, slots=True)
class BrandRecord:
    """统一目录中的稳定品牌。"""

    id: UUID
    code: str
    display_name: str
    role: BrandRole
    status: BrandStatus
    version: int
    catalog_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class BrandAliasRecord:
    """品牌当前有效别名。"""

    id: UUID
    brand_id: UUID
    text: str
    normalized_text: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class VehicleRecord:
    """Resolver 所需的最小车型目录投影。"""

    id: UUID
    code: str
    display_name: str
    brand_id: UUID | None
    status: Literal["active", "deprecated", "merged"]
    version: int
    catalog_version: int


@dataclass(frozen=True, slots=True)
class VehicleAliasRecord:
    """车型当前有效别名。"""

    id: UUID
    vehicle_model_id: UUID
    text: str
    normalized_text: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BrandVehicleCatalogSnapshot:
    """同一 catalog version 下供确定性过滤/解析消费的 Brand/Vehicle 快照。"""

    catalog_version: int
    filter_scope: FilterScope
    selected_brand_ids: tuple[UUID, ...]
    brands: tuple[BrandRecord, ...]
    brand_aliases: tuple[BrandAliasRecord, ...]
    vehicles: tuple[VehicleRecord, ...]
    vehicle_aliases: tuple[VehicleAliasRecord, ...]
    ambiguous_brand_aliases: tuple[str, ...] = ()
    ambiguous_vehicle_aliases: tuple[str, ...] = ()
    unresolved_active_vehicle_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolverEvidence:
    """一次 Resolver 命中的可追溯证据。"""

    entity_id: UUID
    source: ResolverSource
    matched_text: str | None
    source_field: ResolverField | None
    derived_vehicle_model_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class BrandVehicleResolution:
    """Resolver 的稳定输出；冲突可观察但不会被猜成唯一答案。"""

    catalog_version: int
    matched: bool
    brand_matches: tuple[UUID, ...]
    vehicle_matches: tuple[UUID, ...]
    effective_brand_ids: tuple[UUID, ...]
    effective_vehicle_model_ids: tuple[UUID, ...]
    vehicle_evidence: tuple[ResolverEvidence, ...]
    brand_evidence: tuple[ResolverEvidence, ...]
    conflicts: tuple[str, ...]


class BrandVehicleResolver:
    """只依赖冻结目录和输入文本的纯确定性 Brand/Vehicle Resolver。"""

    _FIELDS: tuple[ResolverField, ...] = ("title", "raw_text", "transcript_text")

    def resolve(
        self,
        snapshot: BrandVehicleCatalogSnapshot,
        *,
        title: str | None,
        raw_text: str | None,
        transcript_text: str | None,
        manual_brand_ids: tuple[UUID, ...] | None = None,
        manual_vehicle_ids: tuple[UUID, ...] | None = None,
    ) -> BrandVehicleResolution:
        """按人工锁 > 车型派生品牌 > 品牌别名，且 title > raw > transcript 解析。"""

        texts = {
            "title": title,
            "raw_text": raw_text,
            "transcript_text": transcript_text,
        }
        active_brands = {item.id: item for item in snapshot.brands if item.status == "active"}
        active_vehicles = {item.id: item for item in snapshot.vehicles if item.status == "active"}
        conflicts: list[str] = []

        if manual_vehicle_ids is None:
            vehicle_ids, vehicle_evidence = self._resolve_vehicle_aliases(
                snapshot,
                texts=texts,
                active_vehicles=active_vehicles,
                conflicts=conflicts,
            )
        else:
            vehicle_ids = self._validated_manual_ids(
                manual_vehicle_ids,
                available=set(active_vehicles),
                entity="vehicle",
                conflicts=conflicts,
            )
            vehicle_evidence = tuple(
                ResolverEvidence(
                    entity_id=item,
                    source="manual_review",
                    matched_text=None,
                    source_field=None,
                )
                for item in vehicle_ids
            )

        if manual_brand_ids is None:
            brand_ids, brand_evidence = self._resolve_brands(
                snapshot,
                vehicle_ids=vehicle_ids,
                vehicle_evidence=vehicle_evidence,
                texts=texts,
                active_brands=active_brands,
                active_vehicles=active_vehicles,
                conflicts=conflicts,
            )
        else:
            brand_ids = self._validated_manual_ids(
                manual_brand_ids,
                available=set(active_brands),
                entity="brand",
                conflicts=conflicts,
            )
            brand_evidence = tuple(
                ResolverEvidence(
                    entity_id=item,
                    source="manual_review",
                    matched_text=None,
                    source_field=None,
                )
                for item in brand_ids
            )

        return BrandVehicleResolution(
            catalog_version=snapshot.catalog_version,
            matched=bool(brand_ids or vehicle_ids),
            brand_matches=brand_ids,
            vehicle_matches=vehicle_ids,
            effective_brand_ids=brand_ids,
            effective_vehicle_model_ids=vehicle_ids,
            vehicle_evidence=vehicle_evidence,
            brand_evidence=brand_evidence,
            conflicts=tuple(dict.fromkeys(conflicts)),
        )

    def _resolve_vehicle_aliases(
        self,
        snapshot: BrandVehicleCatalogSnapshot,
        *,
        texts: dict[str, str | None],
        active_vehicles: dict[UUID, VehicleRecord],
        conflicts: list[str],
    ) -> tuple[tuple[UUID, ...], tuple[ResolverEvidence, ...]]:
        aliases_by_text: dict[str, list[VehicleAliasRecord]] = {}
        for alias in snapshot.vehicle_aliases:
            if alias.vehicle_model_id in active_vehicles:
                aliases_by_text.setdefault(alias.normalized_text, []).append(alias)
        for field in self._FIELDS:
            normalized = _normalize_optional(texts[field])
            if normalized is None:
                continue
            matched = [key for key in aliases_by_text if key in normalized]
            if not matched:
                continue
            evidence: list[ResolverEvidence] = []
            resolved: set[UUID] = set()
            for normalized_alias in sorted(matched, key=lambda item: (-len(item), item)):
                if normalized_alias in snapshot.ambiguous_vehicle_aliases:
                    conflicts.append(f"ambiguous_vehicle_alias:{normalized_alias}")
                    continue
                aliases = aliases_by_text[normalized_alias]
                candidates = {item.vehicle_model_id for item in aliases}
                if len(candidates) != 1:
                    conflicts.append(f"ambiguous_vehicle_alias:{normalized_alias}")
                    continue
                vehicle_id = next(iter(candidates))
                resolved.add(vehicle_id)
                representative = sorted(aliases, key=lambda item: (item.text, str(item.id)))[0]
                evidence.append(
                    ResolverEvidence(
                        entity_id=vehicle_id,
                        source="alias_match",
                        matched_text=representative.text,
                        source_field=field,
                    )
                )
            return tuple(sorted(resolved, key=str)), tuple(evidence)
        return (), ()

    def _resolve_brands(
        self,
        snapshot: BrandVehicleCatalogSnapshot,
        *,
        vehicle_ids: tuple[UUID, ...],
        vehicle_evidence: tuple[ResolverEvidence, ...],
        texts: dict[str, str | None],
        active_brands: dict[UUID, BrandRecord],
        active_vehicles: dict[UUID, VehicleRecord],
        conflicts: list[str],
    ) -> tuple[tuple[UUID, ...], tuple[ResolverEvidence, ...]]:
        resolved: set[UUID] = set()
        evidence: list[ResolverEvidence] = []
        for vehicle_id in vehicle_ids:
            vehicle = active_vehicles[vehicle_id]
            if vehicle.brand_id is None or vehicle.brand_id not in active_brands:
                conflicts.append(f"vehicle_brand_unresolved:{vehicle_id}")
                continue
            resolved.add(vehicle.brand_id)
            provenance = next(
                (item for item in vehicle_evidence if item.entity_id == vehicle_id),
                None,
            )
            evidence.append(
                ResolverEvidence(
                    entity_id=vehicle.brand_id,
                    source="vehicle_match",
                    matched_text=None if provenance is None else provenance.matched_text,
                    source_field=None if provenance is None else provenance.source_field,
                    derived_vehicle_model_id=vehicle_id,
                )
            )

        aliases_by_text: dict[str, list[BrandAliasRecord]] = {}
        for alias in snapshot.brand_aliases:
            if alias.brand_id in active_brands:
                aliases_by_text.setdefault(alias.normalized_text, []).append(alias)
        for field in self._FIELDS:
            normalized = _normalize_optional(texts[field])
            if normalized is None:
                continue
            matched = [key for key in aliases_by_text if key in normalized]
            if not matched:
                continue
            for normalized_alias in sorted(matched, key=lambda item: (-len(item), item)):
                if normalized_alias in snapshot.ambiguous_brand_aliases:
                    conflicts.append(f"ambiguous_brand_alias:{normalized_alias}")
                    continue
                aliases = aliases_by_text[normalized_alias]
                candidates = {item.brand_id for item in aliases}
                if len(candidates) != 1:
                    conflicts.append(f"ambiguous_brand_alias:{normalized_alias}")
                    continue
                brand_id = next(iter(candidates))
                if brand_id in resolved:
                    continue
                resolved.add(brand_id)
                representative = sorted(aliases, key=lambda item: (item.text, str(item.id)))[0]
                evidence.append(
                    ResolverEvidence(
                        entity_id=brand_id,
                        source="alias_match",
                        matched_text=representative.text,
                        source_field=field,
                    )
                )
            break
        return tuple(sorted(resolved, key=str)), tuple(evidence)

    @staticmethod
    def _validated_manual_ids(
        ids: tuple[UUID, ...],
        *,
        available: set[UUID],
        entity: str,
        conflicts: list[str],
    ) -> tuple[UUID, ...]:
        valid = tuple(sorted((item for item in set(ids) if item in available), key=str))
        for item in sorted(set(ids) - available, key=str):
            conflicts.append(f"manual_{entity}_unavailable:{item}")
        return valid


def _normalize_optional(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return normalize_vehicle_text(value)


__all__ = [
    "BrandAliasRecord",
    "BrandRecord",
    "BrandRole",
    "BrandStatus",
    "BrandVehicleCatalogSnapshot",
    "BrandVehicleResolution",
    "BrandVehicleResolver",
    "FilterScope",
    "ResolverEvidence",
    "ResolverField",
    "ResolverSource",
    "VehicleAliasRecord",
    "VehicleRecord",
]
