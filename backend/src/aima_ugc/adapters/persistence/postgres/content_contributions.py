"""Content Owner 来源贡献 before/after Delta 捕获。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.modules.content.contribution_tables import content_source_contributions_table
from aima_ugc.modules.content.extended_tables import (
    content_external_ids_table,
    content_locations_table,
    content_media_table,
    content_mentions_table,
    content_topics_table,
)
from aima_ugc.modules.content.tables import accounts_table, content_versions_table, contents_table
from aima_ugc.platform.time import beijing_now

_CONTENT_FIELD_COLUMNS = {
    "content_type": "content_type",
    "title": "title",
    "text": "text",
    "canonical_url": "canonical_url",
    "share_url": "share_url",
    "published_at": "published_at",
    "source_updated_at": "source_updated_at",
    "status": "status",
    "author.external_account_id": "author_account_id",
    "metrics.like_count": "current_like_count",
    "metrics.comment_count": "current_comment_count",
    "metrics.share_count": "current_share_count",
    "metrics.repost_count": "current_repost_count",
    "metrics.favorite_count": "current_favorite_count",
    "metrics.view_count": "current_view_count",
    "metrics.play_count": "current_play_count",
    "metrics.danmaku_count": "current_danmaku_count",
    "metrics.coin_count": "current_coin_count",
    "metrics.download_count": "current_download_count",
}
_ACCOUNT_FIELD_COLUMNS = {
    "author.display_name": "display_name",
    "author.handle": "handle",
    "author.profile_url": "profile_url",
    "author.avatar_url": "avatar_url",
    "author.bio": "bio",
    "author.verified": "verified",
    "author.verification_label": "verification_label",
    "author.region": "region",
    "author.follower_count": "current_follower_count",
    "author.following_count": "current_following_count",
    "author.content_count": "current_content_count",
    "author.total_like_count": "current_total_like_count",
}
_COLLECTION_TABLES = {
    "alternate_ids": content_external_ids_table,
    "media": content_media_table,
    "topics": content_topics_table,
    "mentions": content_mentions_table,
    "locations": content_locations_table,
}


@dataclass(frozen=True, slots=True)
class ContentContributionSnapshot:
    """一次来源写入前/后的最小可逆 Current 投影。"""

    content_id: UUID | None
    version_no: int | None
    content_fields: dict[str, object]
    field_observed_at: dict[str, str]
    author_snapshot: dict[str, Any] | None
    collections: dict[str, tuple[dict[str, object], ...]]
    account_id: UUID | None
    account_fields: dict[str, object]
    account_field_observed_at: dict[str, str]


@dataclass(frozen=True, slots=True)
class ContentContributionDraft:
    """在真正写 Content 前冻结的来源身份和 before 投影。"""

    source_item_key: str
    already_recorded: bool
    before: ContentContributionSnapshot | None


def prepare_content_contribution(
    session: Session,
    observation: CanonicalContentV1,
) -> ContentContributionDraft:
    """在 Content 写入前冻结 before；同一来源重放时复用原贡献事实。"""

    source_item_key = content_source_item_key(observation)
    existing = session.scalar(
        select(content_source_contributions_table.c.id).where(
            content_source_contributions_table.c.source_item_key == source_item_key
        )
    )
    if existing is not None:
        return ContentContributionDraft(
            source_item_key=source_item_key,
            already_recorded=True,
            before=None,
        )
    return ContentContributionDraft(
        source_item_key=source_item_key,
        already_recorded=False,
        before=_capture_snapshot(session, observation),
    )


def commit_content_contribution(
    session: Session,
    *,
    draft: ContentContributionDraft,
    observation: CanonicalContentV1,
    content_id: UUID,
) -> None:
    """在完整 Content + Extension 写入后追加不可变 Delta；与业务写处于同一事务。"""

    if draft.already_recorded:
        return
    attempt_raw = _source_ids(observation)
    after = _capture_snapshot(session, observation, content_id=content_id)
    if after is None or after.content_id != content_id or after.version_no is None:
        raise RuntimeError("Content 来源贡献写入后无法读取 Current 投影")
    delta = _build_delta(observation, draft.before, after)
    values = {
        "id": uuid4(),
        "source_item_key": draft.source_item_key,
        "content_id": content_id,
        "provider_attempt_id": attempt_raw[0],
        "raw_artifact_id": attempt_raw[1],
        "version_before": draft.before.version_no if draft.before is not None else None,
        "version_after": after.version_no,
        "delta": delta,
        "observed_at": observation.observed_at,
        "created_at": beijing_now(),
    }
    created = session.scalar(
        pg_insert(content_source_contributions_table)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=[content_source_contributions_table.c.source_item_key]
        )
        .returning(content_source_contributions_table.c.id)
    )
    if created is None:
        persisted = (
            session.execute(
                select(content_source_contributions_table).where(
                    content_source_contributions_table.c.source_item_key == draft.source_item_key
                )
            )
            .mappings()
            .one()
        )
        if (
            persisted["content_id"] != content_id
            or persisted["provider_attempt_id"] != attempt_raw[0]
            or persisted["raw_artifact_id"] != attempt_raw[1]
        ):
            raise RuntimeError("Content 来源贡献幂等键发生身份冲突")


def content_source_item_key(observation: CanonicalContentV1) -> str:
    """使用真实来源 + Content 身份形成稳定贡献幂等键。"""

    attempt_id, raw_id = _source_ids(observation)
    payload = [
        str(attempt_id),
        str(raw_id),
        observation.source.item_locator or "",
        observation.platform,
        observation.external_content_id,
    ]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _capture_snapshot(
    session: Session,
    observation: CanonicalContentV1,
    *,
    content_id: UUID | None = None,
) -> ContentContributionSnapshot | None:
    """读取当前 Content、当前 Version、相关 Collection 与 Account；不加第二个写 Owner。"""

    statement = select(contents_table)
    if content_id is None:
        statement = statement.where(
            contents_table.c.platform == observation.platform,
            contents_table.c.external_content_id == observation.external_content_id,
        )
    else:
        statement = statement.where(contents_table.c.id == content_id)
    row = session.execute(statement).mappings().one_or_none()
    account = _capture_account(session, observation)
    if row is None:
        return ContentContributionSnapshot(
            content_id=None,
            version_no=None,
            content_fields={},
            field_observed_at={},
            author_snapshot=None,
            collections={field: () for field in _observed_collections(observation)},
            account_id=account[0],
            account_fields=account[1],
            account_field_observed_at=account[2],
        )

    resolved_id = cast(UUID, row["id"])
    version_no = cast(int, row["current_version"])
    version = (
        session.execute(
            select(content_versions_table).where(
                content_versions_table.c.content_id == resolved_id,
                content_versions_table.c.version_no == version_no,
            )
        )
        .mappings()
        .one_or_none()
    )
    raw_freshness = row["field_observed_at"] or {}
    if not isinstance(raw_freshness, dict):
        raise ValueError("Content field_observed_at 必须是对象")
    return ContentContributionSnapshot(
        content_id=resolved_id,
        version_no=version_no,
        content_fields={
            path: row[column]
            for path, column in _CONTENT_FIELD_COLUMNS.items()
            if path in observation.observed_fields
        },
        field_observed_at={str(key): str(value) for key, value in raw_freshness.items()},
        author_snapshot=(
            dict(cast(dict[str, Any], version["author_snapshot"]))
            if version is not None and isinstance(version["author_snapshot"], dict)
            else None
        ),
        collections={
            field: _collection_rows(session, resolved_id, field)
            for field in _observed_collections(observation)
        },
        account_id=account[0],
        account_fields=account[1],
        account_field_observed_at=account[2],
    )


def _capture_account(
    session: Session,
    observation: CanonicalContentV1,
) -> tuple[UUID | None, dict[str, object], dict[str, str]]:
    """只在 Canonical 有稳定账号身份时记录 Account Current Delta。"""

    author = observation.author
    if author is None or author.external_account_id is None:
        return None, {}, {}
    row = (
        session.execute(
            select(accounts_table).where(
                accounts_table.c.platform == observation.platform,
                accounts_table.c.external_account_id == author.external_account_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None, {}, {}
    raw_freshness = row["field_observed_at"] or {}
    if not isinstance(raw_freshness, dict):
        raise ValueError("Account field_observed_at 必须是对象")
    return (
        cast(UUID, row["id"]),
        {
            path: row[column]
            for path, column in _ACCOUNT_FIELD_COLUMNS.items()
            if path in observation.observed_fields
        },
        {str(key): str(value) for key, value in raw_freshness.items()},
    )


def _observed_collections(observation: CanonicalContentV1) -> tuple[str, ...]:
    return tuple(field for field in _COLLECTION_TABLES if field in observation.observed_fields)


def _collection_rows(
    session: Session,
    content_id: UUID,
    field_name: str,
) -> tuple[dict[str, object], ...]:
    table = _COLLECTION_TABLES[field_name]
    if field_name == "alternate_ids":
        order_columns = (table.c.id_type,)
    else:
        order_columns = (table.c.position,)
    rows = session.execute(
        select(table).where(table.c.content_id == content_id).order_by(*order_columns)
    ).mappings()
    return tuple(
        {str(key): value for key, value in row.items() if key != "content_id"} for row in rows
    )


def _build_delta(
    observation: CanonicalContentV1,
    before: ContentContributionSnapshot | None,
    after: ContentContributionSnapshot,
) -> dict[str, object]:
    """只记录当前来源实际改变的值/新鲜度，避免把无变化观察伪装成撤销副作用。"""

    previous = before or ContentContributionSnapshot(
        content_id=None,
        version_no=None,
        content_fields={},
        field_observed_at={},
        author_snapshot=None,
        collections={},
        account_id=None,
        account_fields={},
        account_field_observed_at={},
    )
    content_fields: dict[str, object] = {}
    for path in _CONTENT_FIELD_COLUMNS:
        if path not in observation.observed_fields:
            continue
        before_value = previous.content_fields.get(path)
        after_value = after.content_fields.get(path)
        before_freshness = previous.field_observed_at.get(path)
        after_freshness = after.field_observed_at.get(path)
        if before_value != after_value or before_freshness != after_freshness:
            content_fields[path] = {
                "before": _encode(before_value),
                "after": _encode(after_value),
                "before_freshness": before_freshness,
                "after_freshness": after_freshness,
            }

    author_observed = any(field.startswith("author.") for field in observation.observed_fields)
    author_snapshot: object | None = None
    if author_observed and previous.author_snapshot != after.author_snapshot:
        author_snapshot = {
            "before": _encode(previous.author_snapshot),
            "after": _encode(after.author_snapshot),
        }

    collections: dict[str, object] = {}
    for field in _observed_collections(observation):
        before_rows = previous.collections.get(field, ())
        after_rows = after.collections.get(field, ())
        before_freshness = previous.field_observed_at.get(field)
        after_freshness = after.field_observed_at.get(field)
        if before_rows != after_rows or before_freshness != after_freshness:
            collections[field] = {
                "before": _encode(before_rows),
                "after": _encode(after_rows),
                "before_freshness": before_freshness,
                "after_freshness": after_freshness,
            }

    account_fields: dict[str, object] = {}
    for path in _ACCOUNT_FIELD_COLUMNS:
        if path not in observation.observed_fields:
            continue
        before_value = previous.account_fields.get(path)
        after_value = after.account_fields.get(path)
        before_freshness = previous.account_field_observed_at.get(path)
        after_freshness = after.account_field_observed_at.get(path)
        if before_value != after_value or before_freshness != after_freshness:
            account_fields[path] = {
                "before": _encode(before_value),
                "after": _encode(after_value),
                "before_freshness": before_freshness,
                "after_freshness": after_freshness,
            }

    return {
        "schema_version": "content-source-contribution.v1",
        "created_content": previous.content_id is None,
        "content_fields": content_fields,
        "author_snapshot": author_snapshot,
        "collections": collections,
        "account": (
            {
                "account_id": str(after.account_id or previous.account_id),
                "fields": account_fields,
            }
            if (after.account_id or previous.account_id) is not None and account_fields
            else None
        ),
    }


def decode_contribution_value(value: object) -> object:
    """把 Delta 中的显式类型包装还原为数据库可写 Python 值。"""

    if isinstance(value, list):
        return [decode_contribution_value(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"__aima_type__", "value"}:
            kind = value["__aima_type__"]
            raw = value["value"]
            if kind == "datetime":
                parsed = datetime.fromisoformat(str(raw))
                if parsed.utcoffset() is None:
                    raise ValueError("Contribution datetime 必须包含时区")
                return parsed
            if kind == "date":
                return date.fromisoformat(str(raw))
            if kind == "uuid":
                return UUID(str(raw))
        return {str(key): decode_contribution_value(child) for key, child in value.items()}
    return value


def _encode(value: object) -> object:
    if isinstance(value, datetime):
        return {"__aima_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__aima_type__": "date", "value": value.isoformat()}
    if isinstance(value, UUID):
        return {"__aima_type__": "uuid", "value": str(value)}
    if isinstance(value, tuple | list):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _encode(child) for key, child in value.items()}
    return value


def _source_ids(observation: CanonicalContentV1) -> tuple[UUID, UUID]:
    attempt = observation.source.provider_attempt_id
    raw_id = observation.source.raw_artifact_id
    if attempt is None or raw_id is None:
        raise ValueError("Content 来源贡献要求 provider_attempt_id 与 raw_artifact_id")
    return UUID(attempt), raw_id


__all__ = [
    "ContentContributionDraft",
    "ContentContributionSnapshot",
    "commit_content_contribution",
    "content_source_item_key",
    "decode_contribution_value",
    "prepare_content_contribution",
]
