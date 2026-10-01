"""品牌/车型统一目录对象与纯确定性解析器。"""

from __future__ import annotations

from bisect import bisect_left
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
ResolverSemantics = Literal["field_priority_v1", "brand_scoped_vehicle_v2"]
CURRENT_RESOLVER_SEMANTICS: ResolverSemantics = "brand_scoped_vehicle_v2"
SHORT_VEHICLE_CONTEXT_MAX_GAP = 12
_LOCAL_SEPARATORS = frozenset("。！？!?；;\n\r")
_BRAND_JOINERS = frozenset(
    ("", "和", "与", "及", "或", "或者", "、", ",", "，", "/", "&", "对比", "vs", "vs.")
)
_CatalogIdentity = tuple[int, FilterScope, tuple[UUID, ...], ResolverSemantics]


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
    # 缺字段的历史持久快照保持旧语义；生产新建目录由 Repository 显式冻结新语义。
    resolver_semantics: ResolverSemantics = "field_priority_v1"
    # 匹配只使用 active 车型；清理范围还包含冻结时所属的停用及合并源身份。
    automatic_evidence_vehicle_ids: tuple[UUID, ...] = ()


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
    vehicle_matchers_by_brand: dict[UUID, _AliasAutomaton]
    vehicle_aliases_by_brand: dict[UUID, dict[str, tuple[VehicleAliasRecord, ...]]]


@dataclass(frozen=True, slots=True)
class AliasOccurrence:
    """归一化文本内一次命中的半开区间；重复出现保留各自位置。"""

    normalized_alias: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _FieldContext:
    """匹配文本到原文字符位置的映射，避免空白归一化放宽局部间隔。"""

    raw: str
    normalized: str
    raw_positions: tuple[int, ...]

    def raw_span(self, start: int, end: int) -> tuple[int, int]:
        return self.raw_positions[start], self.raw_positions[end - 1] + 1


@dataclass(frozen=True, slots=True)
class _BrandGroup:
    """相邻并列品牌共同修饰后续车型，不凭最近品牌强行归属。"""

    start: int
    end: int
    brand_ids: frozenset[UUID]


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

        return tuple({item.normalized_alias for item in self.find_occurrences(text)})

    def find_occurrences(self, text: str) -> tuple[AliasOccurrence, ...]:
        """返回全部位置，用于单次命中归属、局部消歧和稳定代表证据。"""

        state = 0
        matched: list[AliasOccurrence] = []
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
                matched.append(AliasOccurrence(pattern, start, index + 1))
        return tuple(matched)


class BrandVehicleResolver:
    """只依赖冻结目录和输入文本的纯确定性 Brand/Vehicle Resolver。"""

    _FIELDS: tuple[ResolverField, ...] = ("title", "raw_text", "transcript_text")

    def __init__(self, snapshot: BrandVehicleCatalogSnapshot | None = None) -> None:
        """可选预编译冻结目录；单条兼容调用仍可在 resolve 时传入。"""

        self._cached_catalog = (
            (_catalog_identity(snapshot), _compile_catalog(snapshot))
            if snapshot is not None
            else None
        )

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
        """按任务冻结语义解析；v2 品牌先行，历史 v1 保留原优先级和反推。"""

        texts = {
            "title": title,
            "raw_text": raw_text,
            "transcript_text": transcript_text,
        }
        identity = _catalog_identity(snapshot)
        cached = self._cached_catalog
        if cached is None or cached[0] != identity:
            cached = (identity, _compile_catalog(snapshot))
            self._cached_catalog = cached
        index = cached[1]
        if snapshot.resolver_semantics == "brand_scoped_vehicle_v2":
            return self._resolve_brand_scoped(
                snapshot, index, texts, manual_brand_ids, manual_vehicle_ids
            )
        if snapshot.resolver_semantics != "field_priority_v1":
            raise ValueError(f"不支持的 Resolver 语义：{snapshot.resolver_semantics}")
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

    def _resolve_brand_scoped(
        self,
        snapshot: BrandVehicleCatalogSnapshot,
        index: _ResolverCatalogIndex,
        texts: dict[str, str | None],
        manual_brand_ids: tuple[UUID, ...] | None,
        manual_vehicle_ids: tuple[UUID, ...] | None,
    ) -> BrandVehicleResolution:
        """完整品牌集合限定车型候选；文本关联只用于高风险或共享车型别名。"""

        conflicts: list[str] = []
        contexts = {field: _field_context(texts[field]) for field in self._FIELDS}
        brand_evidence: dict[UUID, ResolverEvidence] = {}
        brand_ranks: dict[UUID, tuple[int, int, int, str, str]] = {}
        groups: dict[ResolverField, tuple[_BrandGroup, ...]] = {}
        for field_rank, field in enumerate(self._FIELDS):
            context = contexts[field]
            if context is None:
                groups[field] = ()
                continue
            hits: list[tuple[AliasOccurrence, UUID]] = []
            for occurrence in index.brand_alias_matcher.find_occurrences(context.normalized):
                alias_text = occurrence.normalized_alias
                aliases = index.brand_aliases_by_text[alias_text]
                candidates = {alias.brand_id for alias in aliases}
                if alias_text in snapshot.ambiguous_brand_aliases or len(candidates) != 1:
                    conflicts.append(f"ambiguous_brand_alias:{alias_text}")
                    continue
                brand_id = next(iter(candidates))
                hits.append((occurrence, brand_id))
                alias = min(aliases, key=lambda item: (item.text, str(item.id)))
                rank = (field_rank, -len(alias_text), occurrence.start, alias_text, str(alias.id))
                if brand_id not in brand_ranks or rank < brand_ranks[brand_id]:
                    brand_ranks[brand_id] = rank
                    brand_evidence[brand_id] = ResolverEvidence(
                        brand_id, "alias_match", alias.text, field
                    )
            groups[field] = _brand_groups(context, hits)

        if manual_brand_ids is not None:
            brand_ids = self._validated_manual_ids(
                manual_brand_ids,
                available=set(index.active_brands),
                entity="brand",
                conflicts=conflicts,
            )
            brand_evidence = {
                item: ResolverEvidence(item, "manual_review", None, None) for item in brand_ids
            }
        allowed_brands = set(brand_evidence)
        vehicle_evidence: dict[UUID, ResolverEvidence] = {}
        if manual_vehicle_ids is not None:
            vehicle_ids = self._validated_manual_ids(
                manual_vehicle_ids,
                available=set(index.active_vehicles),
                entity="vehicle",
                conflicts=conflicts,
            )
            vehicle_evidence = {
                item: ResolverEvidence(item, "manual_review", None, None) for item in vehicle_ids
            }
            if manual_brand_ids is None:
                for vehicle_id in vehicle_ids:
                    manual_vehicle_brand = index.active_vehicles[vehicle_id].brand_id
                    if (
                        manual_vehicle_brand is None
                        or manual_vehicle_brand not in index.active_brands
                    ):
                        conflicts.append(f"vehicle_brand_unresolved:{vehicle_id}")
                    elif manual_vehicle_brand not in brand_evidence:
                        brand_evidence[manual_vehicle_brand] = ResolverEvidence(
                            manual_vehicle_brand, "vehicle_match", None, None, vehicle_id
                        )
        else:
            vehicle_ranks: dict[UUID, tuple[int, int, int, str, str]] = {}
            for field_rank, field in enumerate(self._FIELDS):
                context = contexts[field]
                if context is None:
                    continue
                occurrences: dict[AliasOccurrence, list[VehicleAliasRecord]] = {}
                for brand_id in sorted(allowed_brands, key=str):
                    matcher = index.vehicle_matchers_by_brand.get(brand_id)
                    if matcher is not None:
                        for occurrence in matcher.find_occurrences(context.normalized):
                            occurrences.setdefault(occurrence, []).extend(
                                index.vehicle_aliases_by_brand[brand_id][
                                    occurrence.normalized_alias
                                ]
                            )
                for occurrence in sorted(
                    occurrences,
                    key=lambda item: (
                        item.start,
                        -len(item.normalized_alias),
                        item.normalized_alias,
                    ),
                ):
                    alias_text = occurrence.normalized_alias
                    vehicle_aliases = occurrences[occurrence]
                    candidates = {alias.vehicle_model_id for alias in vehicle_aliases}
                    if len(candidates) > 1:
                        owners = _local_brand_owners(context, occurrence, groups[field])
                        candidates = (
                            {
                                item
                                for item in candidates
                                if index.active_vehicles[item].brand_id in owners
                            }
                            if len(owners) == 1
                            else set()
                        )
                        if len(candidates) != 1:
                            conflicts.append(f"ambiguous_vehicle_alias:{alias_text}")
                            continue
                    if not candidates:
                        continue
                    vehicle_id = next(iter(candidates))
                    if len(alias_text) == 1 and _local_brand_owners(
                        context, occurrence, groups[field]
                    ) != frozenset((index.active_vehicles[vehicle_id].brand_id,)):
                        conflicts.append(f"unsafe_short_vehicle_alias:{alias_text}")
                        continue
                    vehicle_alias = min(
                        (item for item in vehicle_aliases if item.vehicle_model_id == vehicle_id),
                        key=lambda item: (item.text, str(item.id)),
                    )
                    rank = (
                        field_rank,
                        -len(alias_text),
                        occurrence.start,
                        alias_text,
                        str(vehicle_alias.id),
                    )
                    if vehicle_id not in vehicle_ranks or rank < vehicle_ranks[vehicle_id]:
                        vehicle_ranks[vehicle_id] = rank
                        vehicle_evidence[vehicle_id] = ResolverEvidence(
                            vehicle_id, "alias_match", vehicle_alias.text, field
                        )

        brand_ids = tuple(sorted(brand_evidence, key=str))
        vehicle_ids = tuple(sorted(vehicle_evidence, key=str))
        return BrandVehicleResolution(
            catalog_version=snapshot.catalog_version,
            matched=bool(brand_ids or vehicle_ids),
            brand_matches=brand_ids,
            vehicle_matches=vehicle_ids,
            effective_brand_ids=brand_ids,
            effective_vehicle_model_ids=vehicle_ids,
            vehicle_evidence=tuple(vehicle_evidence[item] for item in vehicle_ids),
            brand_evidence=tuple(brand_evidence[item] for item in brand_ids),
            conflicts=tuple(sorted(set(conflicts))),
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


def _field_context(value: str | None) -> _FieldContext | None:
    """保持目录的空白/大小写归一化，并保留原始距离及换行边界。"""

    if value is None or not value.strip():
        return None
    characters: list[str] = []
    positions: list[int] = []
    pending_space: int | None = None
    for position, character in enumerate(value):
        if character.isspace():
            if characters and pending_space is None:
                pending_space = position
            continue
        if pending_space is not None:
            characters.append(" ")
            positions.append(pending_space)
            pending_space = None
        folded = character.casefold()
        characters.extend(folded)
        positions.extend([position] * len(folded))
    return _FieldContext(value, "".join(characters), tuple(positions))


def _brand_groups(
    context: _FieldContext, hits: list[tuple[AliasOccurrence, UUID]]
) -> tuple[_BrandGroup, ...]:
    groups: list[_BrandGroup] = []
    for occurrence, brand_id in sorted(
        hits, key=lambda item: (item[0].start, -item[0].end, str(item[1]))
    ):
        start, end = context.raw_span(occurrence.start, occurrence.end)
        if groups:
            previous = groups[-1]
            bridge = context.raw[previous.end : start]
            if start < previous.end or (
                not any(character in _LOCAL_SEPARATORS for character in bridge)
                and bridge.strip().casefold() in _BRAND_JOINERS
            ):
                groups[-1] = _BrandGroup(
                    previous.start, max(previous.end, end), previous.brand_ids | {brand_id}
                )
                continue
        groups.append(_BrandGroup(start, end, frozenset((brand_id,))))
    return tuple(groups)


def _local_brand_owners(
    context: _FieldContext, occurrence: AliasOccurrence, groups: tuple[_BrandGroup, ...]
) -> frozenset[UUID]:
    """优先同片段前置品牌；并列品牌保留歧义，只有无前置关联时使用后置品牌。"""

    start, end = context.raw_span(occurrence.start, occurrence.end)
    next_index = bisect_left(groups, end, key=lambda group: group.start)
    before = groups[next_index - 1] if next_index else None
    after = groups[next_index] if next_index < len(groups) else None
    if before is not None and before.end > start:
        return before.brand_ids
    for group, bridge_start, bridge_end in (
        (before, before.end if before is not None else start, start),
        (after, end, after.start if after is not None else end),
    ):
        # 先检查数值距离，再截取局部文本，避免远距离重复命中复制整个正文。
        if group is not None and bridge_end - bridge_start <= SHORT_VEHICLE_CONTEXT_MAX_GAP:
            bridge = context.raw[bridge_start:bridge_end]
            if not any(character in _LOCAL_SEPARATORS for character in bridge):
                return group.brand_ids
    return frozenset()


def _catalog_identity(snapshot: BrandVehicleCatalogSnapshot) -> _CatalogIdentity:
    """返回冻结目录的稳定身份，避免反序列化后因对象地址变化而重复编译。"""

    return (
        snapshot.catalog_version,
        snapshot.filter_scope,
        tuple(sorted(set(snapshot.selected_brand_ids), key=str)),
        snapshot.resolver_semantics,
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
    by_brand: dict[UUID, dict[str, list[VehicleAliasRecord]]] = {}
    if snapshot.resolver_semantics == "brand_scoped_vehicle_v2":
        for aliases in vehicle_aliases.values():
            for alias in aliases:
                brand_id = active_vehicles[alias.vehicle_model_id].brand_id
                if brand_id is not None and brand_id in active_brands:
                    by_brand.setdefault(brand_id, {}).setdefault(alias.normalized_text, []).append(
                        alias
                    )
    return _ResolverCatalogIndex(
        active_brands=active_brands,
        active_vehicles=active_vehicles,
        brand_aliases_by_text={key: tuple(value) for key, value in brand_aliases.items()},
        vehicle_aliases_by_text={key: tuple(value) for key, value in vehicle_aliases.items()},
        brand_alias_matcher=_AliasAutomaton.compile(tuple(brand_aliases)),
        vehicle_alias_matcher=_AliasAutomaton.compile(
            tuple(vehicle_aliases) if snapshot.resolver_semantics == "field_priority_v1" else ()
        ),
        vehicle_matchers_by_brand={
            brand_id: _AliasAutomaton.compile(tuple(aliases))
            for brand_id, aliases in by_brand.items()
        },
        vehicle_aliases_by_brand={
            brand_id: {key: tuple(value) for key, value in aliases.items()}
            for brand_id, aliases in by_brand.items()
        },
    )


__all__ = [
    "AliasOccurrence",
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
    "ResolverSemantics",
    "SHORT_VEHICLE_CONTEXT_MAX_GAP",
    "VehicleAliasRecord",
    "VehicleRecord",
]
