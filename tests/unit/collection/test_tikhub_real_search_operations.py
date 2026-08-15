"""TikHub 真实 Search Fixture 的 item 提取与分页回归测试。"""

from __future__ import annotations

import json
from pathlib import Path

from aima_ugc.adapters.providers.tikhub.operations.bilibili import (
    extract_search_items as extract_bilibili_items,
)
from aima_ugc.adapters.providers.tikhub.operations.kuaishou import (
    KuaishouSearchPagination,
    extract_search_items as extract_kuaishou_items,
)
from aima_ugc.adapters.providers.tikhub.operations.weibo import (
    extract_search_items as extract_weibo_items,
)

_FIXTURE_ROOT = Path("tests/fixtures/providers/tikhub")


def _fixture(platform: str) -> dict[str, object]:
    return json.loads(
        (_FIXTURE_ROOT / platform / "search_page1.sanitized.json").read_text(encoding="utf-8")
    )


def test_weibo_real_search_extracts_only_mblog_cards() -> None:
    items = extract_weibo_items(_fixture("weibo"))
    assert len(items) == 1
    assert items[0]["mblog"]["id"] == "status-fixture-1"


def test_bilibili_real_search_extracts_video_items() -> None:
    items = extract_bilibili_items(_fixture("bilibili"))
    assert len(items) == 1
    assert items[0]["param"] == "av-fixture-1"
    assert items[0]["av"]["mid"] == "user-fixture-1"


def test_kuaishou_real_search_extracts_mixfeeds_and_provider_pcursor() -> None:
    body = _fixture("kuaishou")
    items = extract_kuaishou_items(body)
    pagination = KuaishouSearchPagination.from_response(previous_cursor="", body=body)

    assert len(items) == 1
    assert items[0]["feed"]["photo_id"] == 100001
    assert pagination.next_cursor == "1"
    assert pagination.should_continue is True


def test_kuaishou_search_stops_when_pcursor_does_not_advance() -> None:
    pagination = KuaishouSearchPagination.from_response(
        previous_cursor="1",
        body={"data": {"mixFeeds": [{"feed": {"photo_id": 1}}], "pcursor": "1"}},
    )
    assert pagination.should_continue is False
    assert pagination.stop_reason == "pagination_not_advanced"
