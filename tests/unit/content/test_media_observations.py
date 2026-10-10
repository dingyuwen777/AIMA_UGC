"""完整/部分媒体观察与来源撤销共享的纯规则回归。"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalMediaV1, CanonicalSourceV1
from aima_ugc.modules.content.media_observations import merge_media_rows, rollback_media_rows

NOW = datetime(2026, 10, 9, tzinfo=UTC)
CONTENT_ID = UUID(int=100)


def test_first_external_identity_completes_existing_video_without_losing_cover() -> None:
    cover = _merge(
        (),
        [
            CanonicalMediaV1(
                media_type="video",
                preview_url="https://a.invalid/cover",
                observed_fields=["media_type", "preview_url"],
            )
        ],
    )
    ready = _merge(
        cover,
        [
            CanonicalMediaV1(
                media_type="video",
                external_media_id="first",
                url="https://a.invalid/video",
                observed_fields=["media_type", "external_media_id", "url"],
            )
        ],
        step=1,
    )
    assert ready[0]["preview_url"] == cover[0]["preview_url"]
    assert (
        ready[0]["observation_metadata"]["identity_token"]
        == cover[0]["observation_metadata"]["identity_token"]
    )


def test_revoke_replacement_clears_owned_video_attributes_but_preserves_later_cover() -> None:
    image = _merge(
        (),
        [
            CanonicalMediaV1(
                media_type="image", external_media_id="image", url="https://a.invalid/image"
            )
        ],
    )
    video = _merge(
        image,
        [
            CanonicalMediaV1(
                media_type="video",
                external_media_id="video",
                url="https://a.invalid/video",
                observed_fields=["media_type", "external_media_id", "url"],
            )
        ],
        step=1,
    )
    later = _merge(
        video,
        [
            CanonicalMediaV1(
                media_type="video",
                preview_url="https://a.invalid/later",
                observed_fields=["media_type", "preview_url"],
            )
        ],
        step=2,
    )
    restored = rollback_media_rows(later, before=image, after=video)
    assert restored[0]["media_type"] == "video"
    assert restored[0]["url"] is None
    assert restored[0]["external_media_id"] is None
    assert restored[0]["preview_url"] == later[0]["preview_url"]
    assert (
        restored[0]["observation_metadata"]["identity_token"]
        == later[0]["observation_metadata"]["identity_token"]
    )


def _observation(media: list[CanonicalMediaV1], *, complete: bool = False, step: int = 0):
    """只构造正式 Canonical 输入；来源随步骤变化以证明属性归属。"""
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="note",
        content_type="video",
        media=media,
        media_collection_mode="complete" if complete else "partial",
        observed_fields=["media"],
        observed_at=NOW + timedelta(seconds=step),
        source=CanonicalSourceV1(
            provider_name="tikhub",
            operation="get_video_note_detail",
            source_type="content",
            source_value="note",
            provider_request_id=str(UUID(int=step + 1)),
            provider_attempt_id=str(UUID(int=step + 2)),
            raw_artifact_id=UUID(int=step + 3),
            item_locator="note:note",
            observed_at=NOW + timedelta(seconds=step),
        ),
    )


def _merge(existing, media, *, complete=False, step=0):
    observation = _observation(media, complete=complete, step=step)
    return merge_media_rows(
        existing,
        observation,
        content_id=CONTENT_ID,
        attempt_id=UUID(observation.source.provider_attempt_id),
        raw_id=observation.source.raw_artifact_id,
    )


def test_sparse_cover_preserves_url_and_partial_retains_other_positions() -> None:
    original = _merge(
        (),
        [
            CanonicalMediaV1(
                media_type="video",
                external_media_id="v1",
                url="https://sns-v11.rednotecdn.com/video.mp4",
                width=720,
                height=1280,
            )
        ],
    )
    sparse = _merge(
        original,
        [
            CanonicalMediaV1(
                media_type="video",
                preview_url="https://sns-i11.rednotecdn.com/cover.webp",
                observed_fields=["media_type", "preview_url"],
            )
        ],
        step=1,
    )
    assert sparse[0]["url"] == original[0]["url"]
    assert sparse[0]["external_media_id"] == "v1"
    assert sparse[0]["width"] == 720
    assert sparse[0]["preview_url"].endswith("cover.webp")
    assert _merge(sparse, [], step=2) == sparse
    assert _merge(sparse, [], complete=True, step=2) == ()


def test_media_type_or_external_identity_replacement_clears_old_url() -> None:
    original = _merge(
        (),
        [
            CanonicalMediaV1(
                media_type="image",
                external_media_id="image",
                url="https://sns-i11.rednotecdn.com/image.webp",
            )
        ],
    )
    video = _merge(
        original, [CanonicalMediaV1(media_type="video", observed_fields=["media_type"])], step=1
    )
    assert video[0]["url"] is None
    ready = _merge(
        video,
        [
            CanonicalMediaV1(
                media_type="video",
                external_media_id="first",
                url="https://sns-v11.rednotecdn.com/first.mp4",
            )
        ],
        step=2,
    )
    replaced = _merge(
        ready,
        [
            CanonicalMediaV1(
                media_type="video",
                external_media_id="second",
                observed_fields=["media_type", "external_media_id"],
            )
        ],
        step=3,
    )
    assert replaced[0]["url"] is None


def test_explicit_null_clears_only_observed_property_and_legacy_is_complete_row() -> None:
    original = _merge(
        (),
        [
            CanonicalMediaV1(
                media_type="video", url="https://a.invalid/v", preview_url="https://a.invalid/p"
            )
        ],
    )
    cleared = _merge(
        original, [CanonicalMediaV1(media_type="video", url=None, observed_fields=["url"])], step=1
    )
    assert cleared[0]["url"] is None
    assert cleared[0]["preview_url"] == original[0]["preview_url"]
    legacy = _merge(original, [CanonicalMediaV1(media_type="video")], step=1)
    assert legacy[0]["url"] is None
    assert legacy[0]["preview_url"] is None


def test_property_rollback_preserves_later_source_on_same_identity() -> None:
    before = _merge(
        (),
        [CanonicalMediaV1(media_type="video", external_media_id="v1", url="https://a.invalid/old")],
    )
    after = _merge(
        before,
        [
            CanonicalMediaV1(
                media_type="video",
                url="https://a.invalid/new",
                preview_url="https://a.invalid/first-cover",
                observed_fields=["url", "preview_url"],
            )
        ],
        step=1,
    )
    later = _merge(
        after,
        [
            CanonicalMediaV1(
                media_type="video",
                preview_url="https://a.invalid/later",
                observed_fields=["preview_url"],
            )
        ],
        step=2,
    )
    restored = rollback_media_rows(later, before=before, after=after)
    assert restored[0]["url"] == before[0]["url"]
    assert restored[0]["preview_url"] == later[0]["preview_url"]
    assert restored[0]["raw_artifact_id"] == later[0]["raw_artifact_id"]
