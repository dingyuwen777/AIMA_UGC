"""声音广场签名 Cursor 的查询绑定与失效边界。"""

import base64
import hashlib
import hmac
import json
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
def test_content_cursor_preserves_missing_dates_and_follower_count(
    follower_count: int | None,
) -> None:
    """日期缺失与粉丝数零值都要保留，不能在分页时改为另一种排序值。"""
    now = datetime(2026, 9, 8, tzinfo=UTC)
    codec = ContentCursorCodec(secret=b"cursor-test-key-with-at-least-32-bytes", now=lambda: now)
    position = ContentCursorPosition(
        sort_at=None,
        content_id=uuid4(),
        follower_count=follower_count,
    )
    assert (
        codec.decode(codec.encode(position, query_hash="fans-desc"), query_hash="fans-desc")
        == position
    )


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


def test_content_query_hash_preserves_pre_plural_cursor_identity() -> None:
    """新增 plural 字段不能让部署前仍有效的旧查询 Cursor 失效。"""
    from aima_ugc.bootstrap.content_http import _query_hash
    from aima_ugc.contracts.http import ContentFilterSnapshot

    def legacy_query_hash(
        *,
        primary_label: str | None = None,
        secondary_label: str | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "platforms": [],
            "content_types": [],
            "brand_ids": [],
            "vehicle_model_ids": [],
            "competition_scopes": [],
            "list_sort": {"by": "published_at", "direction": "desc"},
        }
        if primary_label is not None:
            payload["primary_label"] = primary_label
        if secondary_label is not None:
            payload["secondary_label"] = secondary_label
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    now = datetime(2026, 9, 8, tzinfo=UTC)
    secret = b"legacy-filter-hash-regression-key-32-bytes"
    codec = ContentCursorCodec(secret=secret, now=lambda: now)

    for legacy_primary, legacy_secondary in (
        (None, None),
        ("产品体验", None),
        (None, "续航表现"),
        ("产品体验", "续航表现"),
    ):
        old_hash = legacy_query_hash(
            primary_label=legacy_primary,
            secondary_label=legacy_secondary,
        )
        current = ContentFilterSnapshot(
            primary_label=legacy_primary,
            secondary_label=legacy_secondary,
        )
        current_hash = _query_hash(
            current,
            sort_by="published_at",
            sort_direction="desc",
        )
        assert current_hash == old_hash
        assert current_hash == _query_hash(
            ContentFilterSnapshot(
                primary_labels=(legacy_primary,) if legacy_primary else (),
                secondary_labels=(legacy_secondary,) if legacy_secondary else (),
            ),
            sort_by="published_at",
            sort_direction="desc",
        )

        position = ContentCursorPosition(sort_at=now, content_id=uuid4())
        raw = json.dumps(
            {
                "version": 1,
                "content_id": str(position.content_id),
                "sort_at": now.isoformat(),
                "query_hash": old_hash,
                "expires_at": int((now + timedelta(minutes=5)).timestamp()),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        signature = hmac.new(secret, raw, hashlib.sha256).digest()
        cursor = ".".join(
            base64.urlsafe_b64encode(value).rstrip(b"=").decode()
            for value in (raw, signature)
        )
        assert codec.decode(cursor, query_hash=current_hash) == position

        different_hash = _query_hash(
            ContentFilterSnapshot(search="不同查询"),
            sort_by="published_at",
            sort_direction="desc",
        )
        with pytest.raises(InvalidContentCursor):
            codec.decode(cursor, query_hash=different_hash)

    multi_value_hash = _query_hash(
        ContentFilterSnapshot(primary_labels=("产品体验", "服务体验")),
        sort_by="published_at",
        sort_direction="desc",
    )
    assert multi_value_hash != legacy_query_hash(primary_label="产品体验")


def test_content_cursor_accepts_an_unexpired_v1_payload() -> None:
    """部署前签出的旧 Cursor 在原有效期内继续可用。"""
    now = datetime(2026, 9, 8, tzinfo=UTC)
    secret = b"legacy-cursor-regression-test-key-32-bytes"
    content_id = uuid4()
    raw = json.dumps(
        {
            "version": 1,
            "content_id": str(content_id),
            "sort_at": now.isoformat(),
            "query_hash": "legacy-query",
            "expires_at": int((now + timedelta(minutes=5)).timestamp()),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    signature = hmac.new(secret, raw, hashlib.sha256).digest()
    cursor = ".".join(
        base64.urlsafe_b64encode(value).rstrip(b"=").decode() for value in (raw, signature)
    )
    codec = ContentCursorCodec(secret=secret, now=lambda: now)
    assert codec.decode(cursor, query_hash="legacy-query") == ContentCursorPosition(
        sort_at=now, content_id=content_id
    )
