"""TikHub 五平台真实 Detail Fixture → CanonicalContentV1 回归测试。"""

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
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    XiaohongshuMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    map_content as map_xiaohongshu_content,
)
from aima_ugc.adapters.providers.tikhub.operations import (
    bilibili,
    douyin,
    kuaishou,
    weibo,
    xiaohongshu,
)

_ROOT = Path("tests/fixtures/providers/tikhub")
_OBSERVED_AT = datetime(2026, 8, 15, 19, 0, tzinfo=UTC)
_RAW_ID = UUID("00000000-0000-0000-0000-000000000703")


def _fixture(platform: str, name: str = "detail.sanitized.json") -> dict[str, object]:
    return json.loads((_ROOT / platform / name).read_text(encoding="utf-8"))


def _common_context(context_type: type, operation: str):
    return context_type(
        provider_request_id="request-detail-fixture-1",
        provider_attempt_id="attempt-detail-fixture-1",
        raw_artifact_id=_RAW_ID,
        operation=operation,
        source_type="content",
        source_value="fixture",
        observed_at=_OBSERVED_AT,
    )


def test_xiaohongshu_image_and_video_detail_normalize_media_topics_location_and_metrics() -> None:
    image_items = xiaohongshu.extract_detail_items(
        _fixture("xiaohongshu", "image_detail.sanitized.json")
    )
    assert len(image_items) == 1
    image_raw = image_items[0]
    image_external_id = str(image_raw["id"])
    image_topic_id = str(image_raw["topics"][0]["id"])
    image = map_xiaohongshu_content(
        image_raw,
        XiaohongshuMappingContext(
            provider_request_id="request-detail-fixture-1",
            provider_attempt_id="attempt-detail-fixture-1",
            raw_artifact_id=_RAW_ID,
            operation="get_image_note_detail",
            source_type="content",
            source_value=image_external_id,
            observed_at=_OBSERVED_AT,
        ),
        item_locator="data.data[0].note_list[0]",
    )
    assert image.external_content_id == image_external_id
    assert image.metrics.view_count == 1000
    assert image.source_updated_at == datetime.fromtimestamp(1720000100, tz=UTC)
    assert len(image.media) == 1
    assert image.media[0].media_type == "image"
    assert image.media[0].width == 2250
    assert image.media[0].height == 3000
    assert image.topics[0].external_topic_id == image_topic_id
    assert image.locations[0].location_type == "ip_region"
    assert image.locations[0].label == "上海"

    video_items = xiaohongshu.extract_detail_items(
        _fixture("xiaohongshu", "video_detail.sanitized.json")
    )
    video_raw = video_items[0]
    video_external_id = str(video_raw["id"])
    video = map_xiaohongshu_content(
        video_raw,
        XiaohongshuMappingContext(
            provider_request_id="request-detail-fixture-1",
            provider_attempt_id="attempt-detail-fixture-1",
            raw_artifact_id=_RAW_ID,
            operation="get_video_note_detail",
            source_type="content",
            source_value=video_external_id,
            observed_at=_OBSERVED_AT,
        ),
        item_locator="data.data[0]",
    )
    assert video.external_content_id == video_external_id
    assert video.content_type == "video"
    assert video.media[0].media_type == "video"
    assert video.media[0].duration_ms == 85000
    assert video.media[0].width == 1080
    assert video.media[0].height == 1920


def test_douyin_detail_uses_same_content_mapper_and_full_metrics() -> None:
    item = douyin.extract_detail_item(_fixture("douyin"))
    mapped = map_douyin_content(
        item,
        _common_context(DouyinMappingContext, "fetch_one_video_v3"),
        item_locator="data.aweme_detail",
    )
    assert mapped.external_content_id == "douyin-aweme-detail-1"
    assert mapped.metrics.play_count == 1000
    assert mapped.metrics.download_count == 2
    assert mapped.metrics.repost_count == 3
    assert mapped.media[0].media_type == "video"
    assert mapped.media[0].duration_ms == 12000


def test_weibo_detail_uses_idstr_and_preserves_edit_time_and_region() -> None:
    item = weibo.extract_detail_item(_fixture("weibo"))
    mapped = map_weibo_content(
        item,
        _common_context(WeiboMappingContext, "fetch_status_detail"),
        item_locator="data.detailInfo.status",
    )
    assert mapped.external_content_id == "weibo-status-detail-1"
    assert mapped.alternate_ids["mid"] == "weibo-mid-detail-1"
    assert mapped.source_updated_at is not None
    assert mapped.locations[0].label == "发布于 上海"
    assert mapped.metrics.comment_count == 20


def test_bilibili_detail_normalizes_aid_bvid_metrics_cover_and_duration() -> None:
    item = bilibili.extract_detail_item(_fixture("bilibili"))
    mapped = map_bilibili_content(
        item,
        _common_context(BilibiliMappingContext, "fetch_one_video"),
        item_locator="data.data",
    )
    assert mapped.external_content_id == "100001"
    assert mapped.alternate_ids["bvid"] == "BV-fixture-detail-1"
    assert mapped.author is not None
    assert mapped.author.external_account_id == "100002"
    assert mapped.metrics.view_count == 2628
    assert mapped.metrics.comment_count == 7
    assert mapped.metrics.favorite_count == 42
    assert mapped.metrics.coin_count == 4
    assert mapped.media[0].media_type == "cover"
    assert mapped.media[0].duration_ms == 180000


def test_kuaishou_detail_normalizes_numeric_ids_and_video_media() -> None:
    item = kuaishou.extract_detail_item(_fixture("kuaishou"))
    mapped = map_kuaishou_content(
        item,
        _common_context(KuaishouMappingContext, "fetch_one_video"),
        item_locator="data.photos[0]",
    )
    assert mapped.external_content_id == "100001"
    assert mapped.author is not None
    assert mapped.author.external_account_id == "100002"
    assert mapped.metrics.view_count == 1000
    assert mapped.metrics.download_count == 2
    assert {media.media_type for media in mapped.media} == {"video", "cover"}
    assert any(media.duration_ms == 11500 for media in mapped.media)
