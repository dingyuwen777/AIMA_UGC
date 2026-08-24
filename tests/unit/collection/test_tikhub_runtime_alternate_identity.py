from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.collection_targets import _lookup_identity
from aima_ugc.adapters.providers.tikhub.runtime import (
    build_comments_call,
    build_detail_call,
    build_sub_comments_call,
)
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1


def _content(
    *,
    platform: str,
    external_content_id: str,
    alternate_ids: dict[str, str],
) -> CanonicalContentV1:
    observed_at = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
    return CanonicalContentV1(
        platform=platform,  # type: ignore[arg-type]
        external_content_id=external_content_id,
        alternate_ids=alternate_ids,
        content_type="unknown",
        observed_at=observed_at,
        source=CanonicalSourceV1(
            provider_name="imports",
            provider_request_id=str(uuid4()),
            provider_attempt_id=str(uuid4()),
            raw_artifact_id=uuid4(),
            source_type="aima-monitoring-excel.v1",
            source_value="source.xlsx",
            item_locator="sheet=文章;row=2",
            observed_at=observed_at,
        ),
        observed_fields=["alternate_ids"],
    )


def test_detail_uses_typed_lookup_even_when_stable_content_identity_differs() -> None:
    content = _content(
        platform="xiaohongshu",
        external_content_id="SOURCE-ARTICLE-001",
        alternate_ids={"note_id": "provider-note-001"},
    )

    call = build_detail_call("xiaohongshu", content)

    assert call.params["note_id"] == "provider-note-001"


def test_comments_and_replies_use_typed_lookup_without_changing_stable_content_identity() -> None:
    alternate_ids = {"aweme_id": "7675702103746898533"}

    comments = build_comments_call(
        platform="douyin",
        external_content_id="SOURCE-ARTICLE-002",
        alternate_ids=alternate_ids,
    )
    replies = build_sub_comments_call(
        platform="douyin",
        external_content_id="SOURCE-ARTICLE-002",
        alternate_ids=alternate_ids,
        root_comment_id="comment-001",
    )

    assert comments.params["aweme_id"] == "7675702103746898533"
    assert replies.params["item_id"] == "7675702103746898533"


def test_bilibili_comments_preserve_bv_locator_type() -> None:
    call = build_comments_call(
        platform="bilibili",
        external_content_id="SOURCE-ARTICLE-003",
        alternate_ids={"bv_id": "BV1xx411c7mD"},
    )

    assert call.params["bv_id"] == "BV1xx411c7mD"
    assert "av_id" not in call.params


def test_batch_target_accepts_verified_typed_lookup_different_from_stable_identity() -> None:
    lookup = _lookup_identity(
        platform="xiaohongshu",
        external_content_id="SOURCE-ARTICLE-004",
        alternate_ids={"note_id": "provider-note-004"},
        has_tikhub_source=False,
    )

    assert lookup == ("note_id", "provider-note-004")
