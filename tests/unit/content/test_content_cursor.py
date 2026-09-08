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


@pytest.mark.parametrize("follower_count", [None, 0, 120_000])
def test_content_cursor_preserves_missing_dates_and_follower_count(follower_count: int | None) -> None:
    """日期缺失与粉丝数零值都要保留，不能在分页时改为另一种排序值。"""
    now = datetime(2026, 9, 8, tzinfo=UTC)
    codec = ContentCursorCodec(secret=b"cursor-test-key-with-at-least-32-bytes", now=lambda: now)
    position = ContentCursorPosition(
        sort_at=None, content_id=uuid4(), follower_count=follower_count,
    )
    assert codec.decode(codec.encode(position, query_hash="fans-desc"), query_hash="fans-desc") == position


def test_content_sort_identity_does_not_change_filters_or_legacy_query_hash() -> None:
    """列表排序不进入分析/导出的筛选快照，但必须隔离不同排序的 Cursor。"""
    from aima_ugc.bootstrap.content_http import _filters, _query_hash
    from aima_ugc.contracts.http import ContentListQuery

    old = _filters(ContentListQuery(search="爱玛"))
    query = ContentListQuery(search="爱玛", sort_by="follower_count", sort_direction="asc")
    assert _filters(query) == old
    assert _query_hash(old) == _query_hash(old, sort_by=None, sort_direction="desc")
    ascending = _query_hash(old, sort_by="follower_count", sort_direction="asc")
    descending = _query_hash(old, sort_by="follower_count", sort_direction="desc")
    published = _query_hash(old, sort_by="published_at", sort_direction="asc")
    assert len({ascending, descending, published, _query_hash(old)}) == 4
