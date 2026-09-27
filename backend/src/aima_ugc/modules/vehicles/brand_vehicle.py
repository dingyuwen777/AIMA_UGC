"""品牌/车型统一目录对象与纯确定性解析器。"""

from __future__ import annotations

from collections import deque
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
_CatalogIdentity = tuple[int, FilterScope, tuple[UUID, ...]]


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


@dataclass(frozen=True, slots=True)
class _ResolverCatalogIndex:
    """冻结目录的批次级索引，避免每条内容重复重建相同映射。"""

    active_brands: dict[UUID, BrandRecord]
    active_vehicles: dict[UUID, VehicleRecord]
    brand_aliases_by_text: dict[str, tuple[BrandAliasRecord, ...]]
    vehicle_aliases_by_text: dict[str, tuple[VehicleAliasRecord, ...]]
    brand_alias_matcher: _AliasAutomaton
    vehicle_alias_matcher: _AliasAutomaton


@dataclass(frozen=True, slots=True)
class _AliasAutomaton:
    """冻结别名的 Aho-Corasick 自动机；一次扫描返回正文中的全部别名。"""

    transitions: tuple[dict[str, int], ...]
    failures: tuple[int, ...]
    outputs: tuple[tuple[str, ...], ...]

    @classmethod
    def compile(cls, patterns: tuple[str, ...]) -> _AliasAutomaton:
        """目录冻结时构建自动机，把逐内容复杂度从别名数中解耦。"""

        transitions: list[dict[str, int]] = [{}]
        failures = [0]
        outputs: list[list[str]] = [[]]
        for pattern in sorted(set(patterns)):
            if not pattern:
                continue
            state = 0
            for character in pattern:
                target = transitions[state].get(character)
                if target is None:
                    target = len(transitions)
                    transitions[state][character] = target
                    transitions.append({})
                    failures.append(0)
                    outputs.append([])
                state = target
            outputs[state].append(pattern)

        pending: deque[int] = deque(transitions[0].values())
        while pending:
            state = pending.popleft()
            for character, target in transitions[state].items():
                pending.append(target)
                fallback = failures[state]
                while fallback and character not in transitions[fallback]:
                    fallback = failures[fallback]
                failures[target] = transitions[fallback].get(character, 0)
                outputs[target].extend(outputs[failures[target]])

        return cls(
            transitions=tuple(transitions),
            failures=tuple(failures),
            outputs=tuple(tuple(items) for items in outputs),
        )

    def find(self, text: str) -> tuple[str, ...]:
        """按正文字符单次推进；英数字别名只匹配完整词，避免短车型误命中。"""

        state = 0
        matched: set[str] = set()
        for index, character in enumerate(text):
            while state and character not in self.transitions[state]:
                state = self.failures[state]
            state = self.transitions[state].get(character, 0)
            for pattern in self.outputs[state]:
                start = index - len(pattern) + 1
                if (start > 0 and _ascii_word(pattern[0]) and _ascii_word(text[start - 1])) or (
                    index + 1 < len(text)
                    and _ascii_word(pattern[-1])
                    and _ascii_word(text[index + 1])
                ):
                    continue
                matched.add(pattern)
        return tuple(matched)


class BrandVehicleResolver:
    """只依赖冻结目录和输入文本的纯确定性 Brand/Vehicle Resolver。"""

    _FIELDS: tuple[ResolverField, ...] = ("title", "raw_text", "transcript_text")

    def __init__(self, snapshot: BrandVehicleCatalogSnapshot | None = None) -> None:
        """可选预编译冻结目录；单条兼容调用仍可在 resolve 时传入。"""

        self._snapshot_identity = _catalog_identity(snapshot) if snapshot is not None else None
        self._compiled = _compile_catalog(snapshot) if snapshot is not None else None

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
        """自动解析先品牌再其车型；无品牌别名时用车型回推品牌，人工锁优先。"""

        texts = {
            "title": title,
            "raw_text": raw_text,
            "transcript_text": transcript_text,
        }
        index = (
            self._compiled
            if (
                self._snapshot_identity == _catalog_identity(snapshot)
                and self._compiled is not None
            )
            else _compile_catalog(snapshot)
        )
        active_brands = index.active_brands
        active_vehicles = index.active_vehicles
        conflicts: list[str] = []

        anchor_brands: tuple[UUID, ...] = ()
        anchor_evidence: tuple[ResolverEvidence, ...] = ()
        if manual_brand_ids is None and manual_vehicle_ids is None:
            anchor_brands, anchor_evidence = self._resolve_brands(
                snapshot,
                vehicle_ids=(),
                vehicle_evidence=(),
                texts=texts,
                active_brands=active_brands,
                active_vehicles=active_vehicles,
                aliases_by_text=index.brand_aliases_by_text,
                alias_matcher=index.brand_alias_matcher,
                conflicts=conflicts,
            )

        if manual_vehicle_ids is None:
            vehicle_ids, vehicle_evidence = self._resolve_vehicle_aliases(
                snapshot,
                texts=texts,
                active_vehicles=active_vehicles,
                aliases_by_text=index.vehicle_aliases_by_text,
                alias_matcher=index.vehicle_alias_matcher,
                allowed_brand_ids=set(anchor_brands) if anchor_brands else None,
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
            if anchor_brands:
                brand_ids, brand_evidence = anchor_brands, anchor_evidence
            else:
                brand_ids, brand_evidence = self._resolve_brands(
                    snapshot,
                    vehicle_ids=vehicle_ids,
                    vehicle_evidence=vehicle_evidence,
                    texts=texts if manual_vehicle_ids is not None else dict.fromkeys(texts),
                    active_brands=active_brands,
                    active_vehicles=active_vehicles,
                    aliases_by_text=index.brand_aliases_by_text,
                    alias_matcher=index.brand_alias_matcher,
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
        aliases_by_text: dict[str, tuple[VehicleAliasRecord, ...]],
        alias_matcher: _AliasAutomaton,
        allowed_brand_ids: set[UUID] | None,
        conflicts: list[str],
    ) -> tuple[tuple[UUID, ...], tuple[ResolverEvidence, ...]]:
        for field in self._FIELDS:
            normalized = _normalize_optional(texts[field])
            if normalized is None:
                continue
            matched = alias_matcher.find(normalized)
            if not matched:
                continue
            evidence: list[ResolverEvidence] = []
            resolved: set[UUID] = set()
            for normalized_alias in sorted(matched, key=lambda item: (-len(item), item)):
                if (
                    allowed_brand_ids is None
                    and normalized_alias in snapshot.ambiguous_vehicle_aliases
                ):
                    conflicts.append(f"ambiguous_vehicle_alias:{normalized_alias}")
                    continue
                aliases = aliases_by_text[normalized_alias]
                candidates = {
                    item.vehicle_model_id
                    for item in aliases
                    if allowed_brand_ids is None
                    or active_vehicles[item.vehicle_model_id].brand_id in allowed_brand_ids
                }
                if not candidates:
                    continue
                if len(candidates) != 1:
                    conflicts.append(f"ambiguous_vehicle_alias:{normalized_alias}")
                    continue
                vehicle_id = next(iter(candidates))
                # 同一车型只留最长别名的首个命中；数据库唯一键不包含 matched_text。
                if vehicle_id in resolved:
                    continue
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
        aliases_by_text: dict[str, tuple[BrandAliasRecord, ...]],
        alias_matcher: _AliasAutomaton,
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

        for field in self._FIELDS:
            normalized = _normalize_optional(texts[field])
            if normalized is None:
                continue
            matched = alias_matcher.find(normalized)
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


def _ascii_word(character: str) -> bool:
    """中文相邻允许车型命中；英文字母、数字和下划线构成同一个词。"""

    return character.isascii() and (character.isalnum() or character == "_")


def _catalog_identity(snapshot: BrandVehicleCatalogSnapshot) -> _CatalogIdentity:
    """返回冻结目录的稳定身份，避免反序列化后因对象地址变化而重复编译。"""

    return (
        snapshot.catalog_version,
        snapshot.filter_scope,
        tuple(sorted(set(snapshot.selected_brand_ids), key=str)),
    )


def _compile_catalog(snapshot: BrandVehicleCatalogSnapshot) -> _ResolverCatalogIndex:
    """把稳定目录投影编译为只读批次索引；解析过程不再重复分组别名。"""

    active_brands = {item.id: item for item in snapshot.brands if item.status == "active"}
    active_vehicles = {item.id: item for item in snapshot.vehicles if item.status == "active"}
    brand_aliases: dict[str, list[BrandAliasRecord]] = {}
    for brand_alias in snapshot.brand_aliases:
        if brand_alias.brand_id in active_brands:
            brand_aliases.setdefault(brand_alias.normalized_text, []).append(brand_alias)
    vehicle_aliases: dict[str, list[VehicleAliasRecord]] = {}
    for vehicle_alias in snapshot.vehicle_aliases:
        if vehicle_alias.vehicle_model_id in active_vehicles:
            vehicle_aliases.setdefault(vehicle_alias.normalized_text, []).append(vehicle_alias)
    return _ResolverCatalogIndex(
        active_brands=active_brands,
        active_vehicles=active_vehicles,
        brand_aliases_by_text={key: tuple(value) for key, value in brand_aliases.items()},
        vehicle_aliases_by_text={key: tuple(value) for key, value in vehicle_aliases.items()},
        brand_alias_matcher=_AliasAutomaton.compile(tuple(brand_aliases)),
        vehicle_alias_matcher=_AliasAutomaton.compile(tuple(vehicle_aliases)),
    )


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
