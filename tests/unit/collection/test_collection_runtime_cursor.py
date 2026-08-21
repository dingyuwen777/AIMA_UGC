from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from aima_ugc.modules.collection.runtime_cursor import (
    CollectionRuntimeCursorCodec,
    CollectionRuntimeCursorPosition,
    InvalidCollectionRuntimeCursor,
)


def test_collection_runtime_cursor_round_trip_and_query_binding() -> None:
    now = datetime(2026, 8, 21, 8, 0, tzinfo=UTC)
    codec = CollectionRuntimeCursorCodec(secret=b"c" * 32, now=lambda: now)
    position = CollectionRuntimeCursorPosition(
        created_at=now - timedelta(minutes=5),
        record_id=UUID("11111111-1111-4111-8111-111111111111"),
        record_type="tikhub_discovery",
    )

    cursor = codec.encode(position, query_hash="query-a")

    assert codec.decode(cursor, query_hash="query-a") == position
    with pytest.raises(InvalidCollectionRuntimeCursor):
        codec.decode(cursor, query_hash="query-b")


def test_collection_runtime_cursor_rejects_tamper_and_expiry() -> None:
    now = datetime(2026, 8, 21, 8, 0, tzinfo=UTC)
    codec = CollectionRuntimeCursorCodec(
        secret=b"c" * 32,
        lifetime=timedelta(minutes=1),
        now=lambda: now,
    )
    cursor = codec.encode(
        CollectionRuntimeCursorPosition(
            created_at=now,
            record_id=UUID("11111111-1111-4111-8111-111111111111"),
            record_type="excel_import",
        ),
        query_hash="query",
    )

    with pytest.raises(InvalidCollectionRuntimeCursor):
        codec.decode(f"{cursor}x", query_hash="query")

    expired = CollectionRuntimeCursorCodec(
        secret=b"c" * 32,
        now=lambda: now + timedelta(minutes=2),
    )
    with pytest.raises(InvalidCollectionRuntimeCursor):
        expired.decode(cursor, query_hash="query")
