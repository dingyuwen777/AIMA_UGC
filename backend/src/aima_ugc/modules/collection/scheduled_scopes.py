"""Scheduled Run 关键词 Scope 的不可变展开事实。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from .execution import CollectionScopeDefinition


@dataclass(frozen=True, slots=True)
class ScheduledKeywordEntry:
    """一次数据库快照中读取到的词包/关键词/平台关联事实。"""

    pack_id: UUID
    pack_version: int
    pack_enabled: bool
    keyword_id: UUID
    keyword_text: str
    keyword_normalized_text: str
    keyword_enabled: bool
    item_platform: str
    priority: int
    item_enabled: bool


@dataclass(frozen=True, slots=True)
class ScheduledKeywordPackSnapshot:
    """Run 创建时冻结的词包版本身份。"""

    pack_id: UUID
    version: int
    enabled: bool


@dataclass(frozen=True, slots=True)
class ScheduledScopeSnapshot:
    """由当前 Plan 平台和词包事实一次性展开的 Run Scope 快照。"""

    scopes: tuple[CollectionScopeDefinition, ...]
    keyword_packs: tuple[ScheduledKeywordPackSnapshot, ...]


def build_scheduled_scope_snapshot(
    *,
    plan_platforms: tuple[str, ...],
    entries: tuple[ScheduledKeywordEntry, ...],
    keyword_packs: tuple[ScheduledKeywordPackSnapshot, ...] = (),
) -> ScheduledScopeSnapshot:
    """展开 `operations=all` 并按稳定关键词身份去重，不读取外部状态。"""
    normalized_platforms = tuple(
        platform.strip() for platform in plan_platforms if platform.strip()
    )
    if len(normalized_platforms) != len(set(normalized_platforms)):
        raise ValueError("scheduled scope plan_platforms 不得重复")
    platform_set = set(normalized_platforms)

    packs_by_id = {item.pack_id: item for item in keyword_packs}
    for entry in entries:
        current = packs_by_id.get(entry.pack_id)
        inferred = ScheduledKeywordPackSnapshot(
            pack_id=entry.pack_id,
            version=entry.pack_version,
            enabled=entry.pack_enabled,
        )
        if current is not None and current != inferred:
            raise ValueError(f"同一词包出现冲突版本快照: {entry.pack_id}")
        packs_by_id[entry.pack_id] = inferred

    ordered_entries = sorted(
        entries,
        key=lambda item: (
            item.priority,
            item.keyword_normalized_text,
            str(item.keyword_id),
            str(item.pack_id),
            item.item_platform,
        ),
    )
    seen: set[tuple[str, UUID]] = set()
    scopes: list[CollectionScopeDefinition] = []
    for entry in ordered_entries:
        if not (entry.pack_enabled and entry.keyword_enabled and entry.item_enabled):
            continue
        if not entry.keyword_text.strip() or not entry.keyword_normalized_text.strip():
            raise ValueError("scheduled keyword entry 文本不得为空")

        if entry.item_platform == "all":
            target_platforms = normalized_platforms
        elif entry.item_platform in platform_set:
            target_platforms = (entry.item_platform,)
        else:
            target_platforms = ()

        for platform in target_platforms:
            identity = (platform, entry.keyword_id)
            if identity in seen:
                continue
            seen.add(identity)
            scopes.append(
                CollectionScopeDefinition(
                    platform=platform,
                    source_type="keyword_search",
                    source_value=entry.keyword_text,
                    operation_group="content_discovery",
                )
            )

    return ScheduledScopeSnapshot(
        scopes=tuple(scopes),
        keyword_packs=tuple(sorted(packs_by_id.values(), key=lambda item: str(item.pack_id))),
    )


__all__ = [
    "ScheduledKeywordEntry",
    "ScheduledKeywordPackSnapshot",
    "ScheduledScopeSnapshot",
    "build_scheduled_scope_snapshot",
]
