"""声音广场签名 Cursor 的查询绑定与失效边界。"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from aima_ugc.modules.content.content_cursor import (
    ContentCursorCodec,
    ContentCursorPosition,
    InvalidContentCursor,
)


def test_content_cursor_rejects_tampering_query_reuse_and_expiry() -> None:
    now = datetime(2026, 8, 21, tzinfo=UTC)
    codec = ContentCursorCodec(
        secret=b"stage8d-unit-content-cursor-key-32-bytes-minimum",
        lifetime=timedelta(minutes=5),
        now=lambda: now,
    )
    position = ContentCursorPosition(sort_at=now, content_id=uuid4())
    cursor = codec.encode(position, query_hash="query-a")

    assert codec.decode(cursor, query_hash="query-a") == position
    encoded_payload, encoded_signature = cursor.split(".", 1)
    tampered_signature = ("A" if encoded_signature[0] != "A" else "B") + encoded_signature[1:]
    with pytest.raises(InvalidContentCursor):
        codec.decode(f"{encoded_payload}.{tampered_signature}", query_hash="query-a")
    with pytest.raises(InvalidContentCursor):
        codec.decode(cursor, query_hash="query-b")

    expired = ContentCursorCodec(
        secret=b"stage8d-unit-content-cursor-key-32-bytes-minimum",
        now=lambda: now + timedelta(minutes=5),
    )
    with pytest.raises(InvalidContentCursor):
        expired.decode(cursor, query_hash="query-a")
