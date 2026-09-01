"""词包与车型资源选择的统一 Discovery 展开规则。"""

from __future__ import annotations

from dataclasses import dataclass

from aima_ugc.contracts.platform import PlatformName
from aima_ugc.modules.vehicles.models import VehicleCatalogSnapshot

from .execution import CollectionScopeDefinition
from .scheduled_scopes import (
    ScheduledKeywordEntry,
    ScheduledKeywordPackSnapshot,
    build_scheduled_scope_snapshot,
)

_MAX_DISCOVERY_SCOPES = 500


@dataclass(frozen=True, slots=True)
class CollectionResourceSnapshot:
    """一次 Run 冻结的词包版本、车型目录版本和实际搜索 Scope。"""

    scopes: tuple[CollectionScopeDefinition, ...]
    keyword_packs: tuple[ScheduledKeywordPackSnapshot, ...]
    vehicles: VehicleCatalogSnapshot


def build_collection_resource_snapshot(
    *,
    plan_platforms: tuple[PlatformName, ...],
    keyword_entries: tuple[ScheduledKeywordEntry, ...],
    keyword_packs: tuple[ScheduledKeywordPackSnapshot, ...],
    vehicles: VehicleCatalogSnapshot,
) -> CollectionResourceSnapshot:
    """维度内 OR，词包与车型维度间 AND，并对实际搜索词稳定去重。"""

    keyword_snapshot = build_scheduled_scope_snapshot(
        plan_platforms=plan_platforms,
        entries=keyword_entries,
        keyword_packs=keyword_packs,
    )
    keyword_terms_by_platform: dict[PlatformName, list[str]] = {
        platform: [] for platform in plan_platforms
    }
    for scope in keyword_snapshot.scopes:
        keyword_terms_by_platform[scope.platform].append(scope.source_value)

    aliases = vehicles.resolved_aliases
    scopes: list[CollectionScopeDefinition] = []
    seen: set[tuple[PlatformName, str]] = set()
    for platform in plan_platforms:
        keyword_terms = tuple(dict.fromkeys(keyword_terms_by_platform[platform]))
        if keyword_terms and aliases:
            terms = tuple(f"{keyword} {alias}" for keyword in keyword_terms for alias in aliases)
        elif keyword_terms:
            terms = keyword_terms
        else:
            terms = aliases
        for term in terms:
            identity = (platform, term.casefold())
            if identity in seen:
                continue
            seen.add(identity)
            scopes.append(
                CollectionScopeDefinition(
                    platform=platform,
                    source_type="keyword_search",
                    source_value=term,
                    operation_group="content_discovery",
                )
            )
            if len(scopes) > _MAX_DISCOVERY_SCOPES:
                raise ValueError("词包与车型组合超过 500 个 Discovery Scope，请缩小选择范围")

    return CollectionResourceSnapshot(
        scopes=tuple(scopes),
        keyword_packs=keyword_snapshot.keyword_packs,
        vehicles=vehicles,
    )


__all__ = ["CollectionResourceSnapshot", "build_collection_resource_snapshot"]
