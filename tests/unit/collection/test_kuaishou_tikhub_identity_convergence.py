from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from aima_ugc.adapters.providers.tikhub.mappers.kuaishou import (
    KuaishouMappingContext,
    map_comment,
    map_content,
)

_OBSERVED_AT = datetime(2026, 8, 23, 1, 0, tzinfo=UTC)
_RAW_ID = UUID("00000000-0000-0000-0000-000000000799")


def _context(*, external_content_id: str | None = None) -> KuaishouMappingContext:
    return KuaishouMappingContext(
        provider_request_id="request-kuaishou-enrichment",
        provider_attempt_id="attempt-kuaishou-enrichment",
        raw_artifact_id=_RAW_ID,
        operation="fetch_one_video",
        source_type="content",
        source_value=external_content_id or "爱玛",
        observed_at=_OBSERVED_AT,
        external_content_id=external_content_id,
    )


def test_kuaishou_search_uses_public_share_photo_id_as_stable_identity() -> None:
    mapped = map_content(
        {
            "photo_id": "5211790853775999431",
            "share_info": "photoId=3x3ce49jvsw7uri&shareMethod=TOKEN",
            "caption": "search",
            "duration": 12000,
        },
        _context(),
        item_locator="data.mixFeeds[0]",
    )

    assert mapped.external_content_id == "3x3ce49jvsw7uri"
    assert mapped.alternate_ids["photo_id"] == "3x3ce49jvsw7uri"
    assert mapped.alternate_ids["provider_photo_id"] == "5211790853775999431"


def test_kuaishou_detail_preserves_requested_public_identity_and_records_provider_photo_id() -> (
    None
):
    mapped = map_content(
        {
            "photo_id": "5211790853775999431",
            "caption": "detail",
            "duration": 12000,
        },
        _context(external_content_id="3x3ce49jvsw7uri"),
        item_locator="data.photos[0]",
    )

    assert mapped.external_content_id == "3x3ce49jvsw7uri"
    assert mapped.alternate_ids["photo_id"] == "3x3ce49jvsw7uri"
    assert mapped.alternate_ids["provider_photo_id"] == "5211790853775999431"


def test_kuaishou_search_without_share_identity_keeps_numeric_provider_id_compatible() -> None:
    mapped = map_content(
        {
            "photo_id": "5211790853775999431",
            "caption": "legacy-search",
            "duration": 12000,
        },
        _context(),
        item_locator="data.mixFeeds[0]",
    )

    assert mapped.external_content_id == "5211790853775999431"
    assert mapped.alternate_ids["photo_id"] == "5211790853775999431"
    assert "provider_photo_id" not in mapped.alternate_ids


def test_kuaishou_comment_prefers_content_context_over_provider_photo_id() -> None:
    mapped = map_comment(
        {
            "comment_id": "comment-1",
            "photo_id": "5211790853775999431",
            "content": "comment",
        },
        _context(external_content_id="3x3ce49jvsw7uri"),
        item_locator="data.rootComments[0]",
        is_root=True,
    )

    assert mapped.external_content_id == "3x3ce49jvsw7uri"
    assert mapped.external_comment_id == "comment-1"
