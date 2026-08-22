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


def _context(*, external_content_id: str) -> KuaishouMappingContext:
    return KuaishouMappingContext(
        provider_request_id="request-kuaishou-enrichment",
        provider_attempt_id="attempt-kuaishou-enrichment",
        raw_artifact_id=_RAW_ID,
        operation="fetch_one_video",
        source_type="content",
        source_value=external_content_id,
        observed_at=_OBSERVED_AT,
        external_content_id=external_content_id,
    )


def test_kuaishou_detail_preserves_requested_content_identity_and_records_provider_photo_id() -> (
    None
):
    mapped = map_content(
        {
            "photo_id": "provider-photo-id",
            "caption": "detail",
            "duration": 12000,
        },
        _context(external_content_id="excel-photo-id"),
        item_locator="data.photos[0]",
    )

    assert mapped.external_content_id == "excel-photo-id"
    assert mapped.alternate_ids["photo_id"] == "provider-photo-id"


def test_kuaishou_comment_prefers_content_context_over_provider_photo_id() -> None:
    mapped = map_comment(
        {
            "comment_id": "comment-1",
            "photo_id": "provider-photo-id",
            "content": "comment",
        },
        _context(external_content_id="excel-photo-id"),
        item_locator="data.rootComments[0]",
        is_root=True,
    )

    assert mapped.external_content_id == "excel-photo-id"
    assert mapped.external_comment_id == "comment-1"
