"""Keyword Pack Search Terms 的统一 Discovery 展开规则。"""

from __future__ import annotations

from dataclasses import dataclass

from aima_ugc.contracts.platform import PlatformName

from .execution import CollectionScopeDefinition
from .scheduled_scopes import (
    ScheduledKeywordEntry,
    ScheduledKeywordPackSnapshot,
    build_scheduled_scope_snapshot,
)

_MAX_DISCOVERY_SCOPES = 500


@dataclass(frozen=True, slots=True)
class CollectionResourceSnapshot:
    """一次 Run 冻结的词包版本和实际搜索 Scope。"""

    scopes: tuple[CollectionScopeDefinition, ...]
    keyword_packs: tuple[ScheduledKeywordPackSnapshot, ...]


def build_collection_resource_snapshot(
    *,
    plan_platforms: tuple[PlatformName, ...],
    keyword_entries: tuple[ScheduledKeywordEntry, ...],
    keyword_packs: tuple[ScheduledKeywordPackSnapshot, ...],
) -> CollectionResourceSnapshot:
    """按 `platform × keyword` 冻结 Search Scope，不引入车型 Alias。"""

    keyword_snapshot = build_scheduled_scope_snapshot(
        plan_platforms=plan_platforms,
        entries=keyword_entries,
        keyword_packs=keyword_packs,
    )
    if len(keyword_snapshot.scopes) > _MAX_DISCOVERY_SCOPES:
        raise ValueError("Keyword Pack 超过 500 个 Discovery Scope，请缩小选择范围")

    return CollectionResourceSnapshot(
        scopes=keyword_snapshot.scopes,
        keyword_packs=keyword_snapshot.keyword_packs,
    )


__all__ = ["CollectionResourceSnapshot", "build_collection_resource_snapshot"]
