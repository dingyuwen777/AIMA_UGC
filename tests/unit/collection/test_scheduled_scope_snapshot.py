"""Scheduled Run 关键词 Scope 冻结与展开领域测试。"""

from uuid import UUID

from aima_ugc.contracts.platform import PlatformScope
from aima_ugc.modules.collection.scheduled_scopes import (
    ScheduledKeywordEntry,
    build_scheduled_scope_snapshot,
)

_PACK_A = UUID("00000000-0000-0000-0000-000000000a01")
_PACK_B = UUID("00000000-0000-0000-0000-000000000a02")
_KEYWORD_AIMA = UUID("00000000-0000-0000-0000-000000000b01")
_KEYWORD_EV = UUID("00000000-0000-0000-0000-000000000b02")
_KEYWORD_DISABLED = UUID("00000000-0000-0000-0000-000000000b03")


def _entry(
    *,
    pack_id: UUID,
    pack_version: int,
    pack_enabled: bool = True,
    keyword_id: UUID,
    text: str,
    normalized_text: str,
    keyword_enabled: bool = True,
    item_platform_scope: PlatformScope = "all",
    priority: int = 100,
    item_enabled: bool = True,
) -> ScheduledKeywordEntry:
    return ScheduledKeywordEntry(
        pack_id=pack_id,
        pack_version=pack_version,
        pack_enabled=pack_enabled,
        keyword_id=keyword_id,
        keyword_text=text,
        keyword_normalized_text=normalized_text,
        keyword_enabled=keyword_enabled,
        item_platform_scope=item_platform_scope,
        priority=priority,
        item_enabled=item_enabled,
    )


def test_all_platform_keyword_expands_to_explicit_plan_platform_scopes() -> None:
    snapshot = build_scheduled_scope_snapshot(
        plan_platforms=("xiaohongshu", "douyin"),
        entries=(
            _entry(
                pack_id=_PACK_A,
                pack_version=3,
                keyword_id=_KEYWORD_AIMA,
                text="爱玛",
                normalized_text="爱玛",
                item_platform_scope="all",
                priority=10,
            ),
            _entry(
                pack_id=_PACK_A,
                pack_version=3,
                keyword_id=_KEYWORD_EV,
                text="电动车",
                normalized_text="电动车",
                item_platform_scope="xiaohongshu",
                priority=20,
            ),
        ),
    )

    assert [scope.identity for scope in snapshot.scopes] == [
        ("xiaohongshu", "keyword_search", "爱玛", "content_discovery"),
        ("douyin", "keyword_search", "爱玛", "content_discovery"),
        ("xiaohongshu", "keyword_search", "电动车", "content_discovery"),
    ]
    assert [(pack.pack_id, pack.version, pack.enabled) for pack in snapshot.keyword_packs] == [
        (_PACK_A, 3, True)
    ]


def test_duplicate_keyword_from_multiple_packs_produces_one_scope_per_platform() -> None:
    snapshot = build_scheduled_scope_snapshot(
        plan_platforms=("xiaohongshu",),
        entries=(
            _entry(
                pack_id=_PACK_A,
                pack_version=1,
                keyword_id=_KEYWORD_AIMA,
                text="爱玛",
                normalized_text="爱玛",
                item_platform_scope="all",
                priority=20,
            ),
            _entry(
                pack_id=_PACK_B,
                pack_version=7,
                keyword_id=_KEYWORD_AIMA,
                text="爱玛",
                normalized_text="爱玛",
                item_platform_scope="xiaohongshu",
                priority=5,
            ),
        ),
    )

    assert [scope.identity for scope in snapshot.scopes] == [
        ("xiaohongshu", "keyword_search", "爱玛", "content_discovery")
    ]
    assert [(pack.pack_id, pack.version) for pack in snapshot.keyword_packs] == [
        (_PACK_A, 1),
        (_PACK_B, 7),
    ]


def test_disabled_or_non_plan_entries_do_not_create_scopes_but_pack_versions_stay_auditable() -> (
    None
):
    snapshot = build_scheduled_scope_snapshot(
        plan_platforms=("xiaohongshu", "douyin"),
        entries=(
            _entry(
                pack_id=_PACK_A,
                pack_version=4,
                keyword_id=_KEYWORD_DISABLED,
                text="停用词",
                normalized_text="停用词",
                keyword_enabled=False,
            ),
            _entry(
                pack_id=_PACK_A,
                pack_version=4,
                keyword_id=_KEYWORD_EV,
                text="B站词",
                normalized_text="B站词",
                item_platform_scope="bilibili",
            ),
            _entry(
                pack_id=_PACK_B,
                pack_version=9,
                pack_enabled=False,
                keyword_id=_KEYWORD_AIMA,
                text="爱玛",
                normalized_text="爱玛",
            ),
        ),
    )

    assert snapshot.scopes == ()
    assert [(pack.pack_id, pack.version, pack.enabled) for pack in snapshot.keyword_packs] == [
        (_PACK_A, 4, True),
        (_PACK_B, 9, False),
    ]


def test_scope_order_is_deterministic_by_priority_then_keyword_and_plan_platform_order() -> None:
    snapshot = build_scheduled_scope_snapshot(
        plan_platforms=("weibo", "xiaohongshu"),
        entries=(
            _entry(
                pack_id=_PACK_A,
                pack_version=1,
                keyword_id=_KEYWORD_EV,
                text="电动车",
                normalized_text="电动车",
                priority=20,
            ),
            _entry(
                pack_id=_PACK_A,
                pack_version=1,
                keyword_id=_KEYWORD_AIMA,
                text="爱玛",
                normalized_text="爱玛",
                priority=10,
            ),
        ),
    )

    assert [scope.identity for scope in snapshot.scopes] == [
        ("weibo", "keyword_search", "爱玛", "content_discovery"),
        ("xiaohongshu", "keyword_search", "爱玛", "content_discovery"),
        ("weibo", "keyword_search", "电动车", "content_discovery"),
        ("xiaohongshu", "keyword_search", "电动车", "content_discovery"),
    ]
