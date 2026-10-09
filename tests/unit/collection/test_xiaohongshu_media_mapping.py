"""真实脱敏详情证明类型、流属性与稀疏封面的媒体语义。"""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    XiaohongshuMappingContext,
    map_content,
)

FIXTURES = Path(__file__).parents[2] / "fixtures/providers/tikhub/xiaohongshu"


def _map(raw: dict[str, object], operation: str = "get_video_note_detail"):
    """调用正式 Mapper，不复刻第三方字段解析。"""
    return map_content(
        raw,
        XiaohongshuMappingContext(
            provider_request_id="request-media",
            provider_attempt_id="attempt-media",
            raw_artifact_id=UUID(int=1),
            operation=operation,
            source_type="content",
            source_value="a00000000000000000000001",
            observed_at=datetime(2026, 10, 9, tzinfo=UTC),
        ),
        item_locator="note:a00000000000000000000001",
    )


@pytest.mark.parametrize("note_type", [None, "", "future_type", "unknown", 0])
def test_unproven_type_is_unknown_instead_of_image(note_type: object) -> None:
    result = _map({"id": "a00000000000000000000001", "type": note_type}, "search_notes")
    assert result.content_type == "unknown"
    assert "content_type" not in result.observed_fields


def test_real_video_detail_selects_h264_and_its_own_dimensions_and_milliseconds() -> None:
    raw = json.loads((FIXTURES / "video_detail_20261009.sanitized.json").read_text("utf-8"))
    result = _map(raw["data"]["data"][0])
    assert result.content_type == "video"
    assert result.media_collection_mode == "complete"
    assert len(result.media) == 1
    media = result.media[0]
    assert media.media_type == "video"
    assert str(media.url) == "http://sns-v11.rednotecdn.com/fixture-13.mp4"
    assert str(media.preview_url) == "https://sns-i11.rednotecdn.com/fixture-6.webp"
    assert (media.width, media.height, media.duration_ms) == (720, 1280, 17800)
    assert media.mime_type == "video/mp4"
    assert media.external_media_id == "id-0006"
    assert set(media.observed_fields or ()) >= {"url", "preview_url", "duration_ms"}


def test_image_endpoint_video_cover_remains_sparse_video_without_playback_url() -> None:
    raw = json.loads((FIXTURES / "video_cover_detail_20261009.sanitized.json").read_text("utf-8"))
    result = _map(raw["data"]["data"][0], "get_image_note_detail")
    assert result.content_type == "video"
    assert len(result.media) == 1
    media = result.media[0]
    assert media.media_type == "video"
    assert media.url is None
    assert str(media.preview_url) == "https://sns-i11.rednotecdn.com/fixture-26.webp"
    assert "url" not in (media.observed_fields or ())
    assert "external_media_id" not in (media.observed_fields or ())
    assert result.media_collection_mode == "partial"


def test_explicit_empty_image_detail_observes_complete_deletion() -> None:
    result = _map(
        {"id": "a00000000000000000000001", "type": "normal", "images_list": []},
        "get_image_note_detail",
    )
    assert result.media == []
    assert "media" in result.observed_fields
    assert result.media_collection_mode == "complete"


def test_unknown_type_image_list_cannot_prove_gallery_instead_of_video_cover() -> None:
    result = _map(
        {
            "id": "a00000000000000000000001",
            "images_list": [{"url": "https://a.invalid/cover"}],
        },
        "search_notes",
    )
    assert result.content_type == "unknown"
    assert "media" not in result.observed_fields


@pytest.mark.parametrize(
    "invalid", [{"unrecognized_provider_error": "temporarily_unavailable"}, {}, None]
)
def test_unrecognized_image_entry_cannot_prove_destructive_complete_collection(
    invalid: object,
) -> None:
    result = _map(
        {
            "id": "a00000000000000000000001",
            "type": "normal",
            "images_list": [{"url": "https://a.invalid/valid"}, invalid],
        },
        "get_image_note_detail",
    )
    assert result.media_collection_mode == "partial"
    assert [item.position for item in result.media] == [0]


def test_recognized_partial_image_attributes_can_still_prove_complete_positions() -> None:
    result = _map(
        {"id": "a00000000000000000000001", "type": "normal", "images_list": [{"width": 1080}]},
        "get_image_note_detail",
    )
    assert result.media_collection_mode == "complete"
    assert result.media[0].width == 1080
