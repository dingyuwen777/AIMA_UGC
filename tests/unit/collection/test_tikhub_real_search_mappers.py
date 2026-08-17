"""TikHub 四平台真实 Search Fixture → Canonical V1 回归测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from aima_ugc.adapters.providers.tikhub.mappers.bilibili import (
    BilibiliMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.bilibili import (
    map_content as map_bilibili_content,
)
from aima_ugc.adapters.providers.tikhub.mappers.douyin import (
    DouyinMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.douyin import (
    map_content as map_douyin_content,
)
from aima_ugc.adapters.providers.tikhub.mappers.kuaishou import (
    KuaishouMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.kuaishou import (
    map_content as map_kuaishou_content,
)
from aima_ugc.adapters.providers.tikhub.mappers.weibo import (
    WeiboMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.weibo import (
    map_content as map_weibo_content,
)

_FIXTURE_ROOT = Path("tests/fixtures/providers/tikhub")
_OBSERVED_AT = datetime(2026, 8, 15, 17, 0, tzinfo=UTC)
_RAW_ID = UUID("00000000-0000-0000-0000-000000000701")


def _fixture(platform: str) -> dict[str, object]:
    return json.loads(
        (_FIXTURE_ROOT / platform / "search_page1.sanitized.json").read_text(encoding="utf-8")
    )


def _context(context_type: type, operation: str):
    return context_type(
        provider_request_id="request-fixture-1",
        provider_attempt_id="attempt-fixture-1",
        raw_artifact_id=_RAW_ID,
        operation=operation,
        source_type="keyword",
        source_value="爱玛",
        observed_at=_OBSERVED_AT,
    )


def test_douyin_real_search_item_maps_to_canonical_content() -> None:
    raw = _fixture("douyin")["data"]["business_data"][0]
    mapped = map_douyin_content(
        raw,
        _context(DouyinMappingContext, "fetch_video_search_v2"),
        item_locator="data.business_data[0]",
    )

    assert mapped.platform == "douyin"
    assert mapped.external_content_id == "aweme-fixture-1"
    assert mapped.content_type == "video"
    assert mapped.title == "脱敏标题 A"
    assert mapped.text == "脱敏正文 A"
    assert mapped.author is not None
    assert mapped.author.external_account_id == "user-fixture-1"
    assert mapped.author.handle == "handle-fixture-1"
    assert mapped.metrics.like_count == 252
    assert mapped.metrics.comment_count == 30
    assert mapped.metrics.favorite_count == 66
    assert mapped.metrics.share_count == 37
    assert mapped.metrics.download_count == 4
    assert mapped.published_at == datetime.fromtimestamp(1720000000, tz=UTC)
    assert mapped.source.provider_name == "tikhub"


def test_weibo_real_search_card_maps_to_canonical_content() -> None:
    raw = _fixture("weibo")["data"]["data"]["cards"][0]
    mapped = map_weibo_content(
        raw,
        _context(WeiboMappingContext, "fetch_search"),
        item_locator="data.data.cards[0]",
    )

    assert mapped.platform == "weibo"
    assert mapped.external_content_id == "status-fixture-1"
    assert mapped.alternate_ids["bid"] == "bid-fixture-1"
    assert mapped.content_type == "image"
    assert mapped.text == "脱敏微博正文 A"
    assert mapped.author is not None
    assert mapped.author.external_account_id == "100001"
    assert mapped.author.display_name == "脱敏用户 A"
    assert mapped.author.verified is True
    assert mapped.metrics.like_count == 12
    assert mapped.metrics.comment_count == 3
    assert mapped.metrics.repost_count == 4
    assert mapped.metrics.favorite_count == 5
    assert mapped.published_at is not None


def test_bilibili_real_search_item_maps_to_canonical_content() -> None:
    raw = _fixture("bilibili")["data"]["data"]["items"][0]
    mapped = map_bilibili_content(
        raw,
        _context(BilibiliMappingContext, "fetch_search_by_type"),
        item_locator="data.data.items[0]",
    )

    assert mapped.platform == "bilibili"
    assert mapped.external_content_id == "av-fixture-1"
    assert mapped.content_type == "video"
    assert mapped.title == "脱敏标题 A"
    assert mapped.text == "脱敏正文 A"
    assert mapped.author is not None
    assert mapped.author.external_account_id == "user-fixture-1"
    assert mapped.author.display_name == "脱敏用户 A"
    assert mapped.metrics.play_count == 196954
    assert mapped.metrics.danmaku_count == 2452
    assert mapped.published_at == datetime.fromtimestamp(1720000000, tz=UTC)


def test_kuaishou_real_search_feed_maps_numeric_ids_to_canonical_strings() -> None:
    raw = _fixture("kuaishou")["data"]["mixFeeds"][0]
    mapped = map_kuaishou_content(
        raw,
        _context(KuaishouMappingContext, "search_video_v2"),
        item_locator="data.mixFeeds[0]",
    )

    assert mapped.platform == "kuaishou"
    assert mapped.external_content_id == "100001"
    assert mapped.alternate_ids["kwai_id"] == "kwai-fixture-1"
    assert mapped.content_type == "video"
    assert mapped.text == "脱敏正文 A"
    assert mapped.author is not None
    assert mapped.author.external_account_id == "100002"
    assert mapped.author.display_name == "脱敏用户 A"
    assert mapped.author.verified is False
    assert mapped.metrics.like_count == 15223
    assert mapped.metrics.comment_count == 686
    assert mapped.metrics.favorite_count == 1850
    assert mapped.metrics.share_count == 7016
    assert mapped.metrics.repost_count == 0
    assert mapped.metrics.view_count == 639011
    assert mapped.published_at == datetime.fromtimestamp(1720000000, tz=UTC)
