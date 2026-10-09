"""播放来源代次与短期会话不依赖 CDN TTL。"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from aima_ugc.modules.content.content_cursor import InvalidContentCursor
from aima_ugc.modules.content.media_playback import (
    ContentPlaybackSessionCodec,
    media_source_revision,
)


def test_cover_only_update_does_not_change_url_revision_but_new_url_source_does() -> None:
    attempt, raw = uuid4(), uuid4()
    row = {
        "content_id": uuid4(),
        "position": 0,
        "media_type": "video",
        "url": "https://sns-v11.rednotecdn.com/synthetic",
        "provider_attempt_id": attempt,
        "raw_artifact_id": raw,
        "observed_at": datetime(2026, 10, 9, tzinfo=UTC),
        "observation_metadata": {},
    }
    revision = media_source_revision(row)
    covered = {
        **row,
        "preview_url": "https://example.test/cover",
        "provider_attempt_id": uuid4(),
        "observation_metadata": {
            "fields": {
                "url": {
                    "provider_attempt_id": str(attempt),
                    "raw_artifact_id": str(raw),
                    "observed_at": "2026-10-09T08:00:00+08:00",
                }
            }
        },
    }
    assert media_source_revision(covered) == revision
    assert media_source_revision({**row, "provider_attempt_id": uuid4()}) != revision
    assert media_source_revision({**row, "url": "https://sns-v27.rednotecdn.com/new"}) != revision


def test_session_binds_principal_content_position_identity_and_url_source() -> None:
    now = datetime(2026, 10, 9, tzinfo=UTC)
    codec = ContentPlaybackSessionCodec(secret=b"a" * 48, now=lambda: now)
    binding = dict(
        principal_id="viewer",
        content_id=uuid4(),
        position=0,
        identity_token="a" * 64,
        source_revision="b" * 64,
    )
    session = codec.issue(**binding)
    codec.verify(session, **binding)
    for field, replacement in (
        ("principal_id", "other"),
        ("content_id", uuid4()),
        ("position", 1),
        ("identity_token", "c" * 64),
        ("source_revision", "d" * 64),
    ):
        with pytest.raises(InvalidContentCursor):
            codec.verify(session, **{**binding, field: replacement})
    expired = ContentPlaybackSessionCodec(secret=b"a" * 48, now=lambda: now + timedelta(minutes=16))
    with pytest.raises(InvalidContentCursor):
        expired.verify(session, **binding)
