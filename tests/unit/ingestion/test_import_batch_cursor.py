from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from aima_ugc.modules.ingestion.import_batch_cursor import (
    ImportBatchCursorCodec,
    ImportBatchCursorPosition,
    InvalidImportCursor,
)

_SECRET = b"stage8c-cursor-signing-secret-32b"
_NOW = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)
_POSITION = ImportBatchCursorPosition(
    created_at=datetime(2026, 8, 20, 9, 30, tzinfo=UTC),
    batch_id=UUID("12345678-1234-5678-1234-567812345678"),
)


def _codec() -> ImportBatchCursorCodec:
    return ImportBatchCursorCodec(
        secret=_SECRET,
        lifetime=timedelta(minutes=30),
        now=lambda: _NOW,
    )


def test_signed_cursor_round_trips_for_the_same_query() -> None:
    cursor = _codec().encode(_POSITION, query_hash="query-a")

    assert _codec().decode(cursor, query_hash="query-a") == _POSITION


@pytest.mark.parametrize("failure", ("tampered", "another-query", "expired"))
def test_cursor_rejects_tampering_query_mismatch_and_expiry(failure: str) -> None:
    codec = _codec()
    cursor = codec.encode(_POSITION, query_hash="query-a")
    if failure == "tampered":
        cursor = f"{cursor[:-1]}{'A' if cursor[-1] != 'A' else 'B'}"
        query_hash = "query-a"
        verifier = codec
    elif failure == "another-query":
        query_hash = "query-b"
        verifier = codec
    else:
        query_hash = "query-a"
        verifier = ImportBatchCursorCodec(
            secret=_SECRET,
            lifetime=timedelta(minutes=30),
            now=lambda: _NOW + timedelta(minutes=31),
        )

    with pytest.raises(InvalidImportCursor):
        verifier.decode(cursor, query_hash=query_hash)


def test_cursor_signing_secret_requires_at_least_32_bytes() -> None:
    with pytest.raises(ValueError, match="32"):
        ImportBatchCursorCodec(secret=b"too-short")
