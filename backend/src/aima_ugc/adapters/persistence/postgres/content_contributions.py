"""Content Owner 来源贡献 before/after Delta 捕获。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from itertools import batched
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import insert, or_, select, tuple_
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

_MULTI_VALUES_INSERT_ROWS = 500


class _UnspecifiedAuthorSnapshot:
    """区分“沿用 Canonical Author”与“显式保存 NULL/历史裁剪快照”。"""


_UNSPECIFIED_AUTHOR_SNAPSHOT = _UnspecifiedAuthorSnapshot()

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
    *,
    before_snapshot: ContentContributionSnapshot | None = None,
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
        before=(
            before_snapshot
            if before_snapshot is not None
            else _capture_snapshot(session, observation)
        ),
    )


def prepare_content_contributions_batch(
    session: Session,
    observations: tuple[CanonicalContentV1, ...],
    *,
    before_snapshots: tuple[ContentContributionSnapshot, ...] | None = None,
) -> tuple[ContentContributionDraft, ...]:
    """集合冻结多个来源写入前的投影，避免既有内容逐行回读。"""

    if not observations:
        return ()
    if before_snapshots is not None and len(before_snapshots) != len(observations):
        raise ValueError("批量来源贡献 before 投影数量与观察不一致")
    source_keys = tuple(content_source_item_key(item) for item in observations)
    if len(set(source_keys)) != len(source_keys):
        raise ValueError("批量来源贡献不接受重复来源身份")
    existing_keys = set(
        session.execute(
            select(content_source_contributions_table.c.source_item_key).where(
                content_source_contributions_table.c.source_item_key.in_(source_keys)
            )
        ).scalars()
    )
    pending = tuple(
        (index, observation)
        for index, (source_key, observation) in enumerate(
            zip(source_keys, observations, strict=True)
        )
        if source_key not in existing_keys
    )
    if before_snapshots is None:
        before = capture_content_contribution_snapshots_batch(
            session,
            tuple((observation, None) for _, observation in pending),
        )
        pending_before = {
            index: snapshot for (index, _), snapshot in zip(pending, before, strict=True)
        }
    else:
        pending_before = {index: before_snapshots[index] for index, _ in pending}
    return tuple(
        ContentContributionDraft(
            source_item_key=source_key,
            already_recorded=source_key in existing_keys,
            before=pending_before.get(index),
        )
        for index, source_key in enumerate(source_keys)
    )


def commit_content_contribution(
    session: Session,
    *,
    draft: ContentContributionDraft,
    observation: CanonicalContentV1,
    content_id: UUID,
) -> ContentContributionSnapshot | None:
    """在完整 Content + Extension 写入后追加不可变 Delta；与业务写处于同一事务。"""

    if draft.already_recorded:
        return None
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
    return after


def commit_content_contributions_batch(
    session: Session,
    *,
    entries: tuple[
        tuple[ContentContributionDraft, CanonicalContentV1, UUID],
        ...,
    ],
) -> tuple[ContentContributionSnapshot, ...]:
    """集合捕获 after 并追加既有 Content 的不可变来源贡献。"""

    if not entries:
        return ()
    after_snapshots = capture_content_contribution_snapshots_batch(
        session,
        tuple((observation, content_id) for _, observation, content_id in entries),
    )
    pending = tuple(
        (index, entry) for index, entry in enumerate(entries) if not entry[0].already_recorded
    )
    if not pending:
        return after_snapshots
    now = beijing_now()
    values: list[dict[str, object]] = []
    expected: dict[str, tuple[UUID, UUID, UUID]] = {}
    for index, (draft, observation, content_id) in pending:
        after = after_snapshots[index]
        if after.content_id != content_id or after.version_no is None:
            raise RuntimeError("Content 来源贡献写入后无法读取 Current 投影")
        attempt_id, raw_artifact_id = _source_ids(observation)
        expected[draft.source_item_key] = (content_id, attempt_id, raw_artifact_id)
        values.append(
            {
                "id": uuid4(),
                "source_item_key": draft.source_item_key,
                "content_id": content_id,
                "provider_attempt_id": attempt_id,
                "raw_artifact_id": raw_artifact_id,
                "version_before": (draft.before.version_no if draft.before is not None else None),
                "version_after": after.version_no,
                "delta": _build_delta(observation, draft.before, after),
                "observed_at": observation.observed_at,
                "created_at": now,
            }
        )
    inserted_keys: set[str] = set()
    for chunk in batched(values, _MULTI_VALUES_INSERT_ROWS, strict=False):
        inserted_keys.update(
            session.execute(
                pg_insert(content_source_contributions_table)
                .values(list(chunk))
                .on_conflict_do_nothing(
                    index_elements=[content_source_contributions_table.c.source_item_key]
                )
                .returning(content_source_contributions_table.c.source_item_key)
            ).scalars()
        )
    conflicted_keys = tuple(set(expected).difference(inserted_keys))
    if not conflicted_keys:
        return after_snapshots
    persisted = {
        str(row["source_item_key"]): row
        for row in session.execute(
            select(content_source_contributions_table).where(
                content_source_contributions_table.c.source_item_key.in_(conflicted_keys)
            )
        ).mappings()
    }
    for source_key in conflicted_keys:
        row = persisted.get(source_key)
        identity = expected[source_key]
        if (
            row is None
            or (
                row["content_id"],
                row["provider_attempt_id"],
                row["raw_artifact_id"],
            )
            != identity
        ):
            raise RuntimeError("Content 来源贡献幂等键发生身份冲突")
    return after_snapshots


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


def capture_content_contribution_snapshot(
    session: Session,
    observation: CanonicalContentV1,
    *,
    content_id: UUID | None = None,
) -> ContentContributionSnapshot:
    """为一次独立业务操作冻结 Current 投影，不复用来源幂等账本。"""

    snapshot = _capture_snapshot(session, observation, content_id=content_id)
    if snapshot is None:
        raise RuntimeError("Content Current 投影不可读")
    return snapshot


def build_content_contribution_delta(
    observation: CanonicalContentV1,
    before: ContentContributionSnapshot | None,
    after: ContentContributionSnapshot,
) -> dict[str, object]:
    """生成与 Data Import 撤销相同语义的 before/after Delta。"""

    return _build_delta(observation, before, after)


def new_content_contribution_snapshot(
    observation: CanonicalContentV1,
    *,
    content_id: UUID,
    state: dict[str, Any],
    collections: dict[str, tuple[dict[str, object], ...]],
    author_snapshot: dict[str, Any] | None | _UnspecifiedAuthorSnapshot = (
        _UNSPECIFIED_AUTHOR_SNAPSHOT
    ),
) -> ContentContributionSnapshot:
    """从同事务刚写入的确定值构造新 Content 投影，避免逐行回读。"""

    raw_freshness = state.get("field_observed_at") or {}
    if not isinstance(raw_freshness, dict):
        raise ValueError("Content field_observed_at 必须是对象")
    return ContentContributionSnapshot(
        content_id=content_id,
        version_no=1,
        content_fields={
            path: state.get(column)
            for path, column in _CONTENT_FIELD_COLUMNS.items()
            if path in observation.observed_fields
        },
        field_observed_at={str(key): str(value) for key, value in raw_freshness.items()},
        author_snapshot=(
            observation.author.model_dump(mode="json")
            if isinstance(author_snapshot, _UnspecifiedAuthorSnapshot)
            and observation.author is not None
            else None
            if isinstance(author_snapshot, _UnspecifiedAuthorSnapshot)
            else author_snapshot
        ),
        collections=collections,
        account_id=None,
        account_fields={},
        account_field_observed_at={},
    )


def commit_new_content_contributions_batch(
    session: Session,
    entries: tuple[tuple[CanonicalContentV1, ContentContributionSnapshot], ...],
) -> None:
    """集合追加当前事务新建 Content 的不可变来源贡献。"""

    if not entries:
        return
    now = beijing_now()
    values: list[dict[str, object]] = []
    source_keys: set[str] = set()
    for observation, after in entries:
        if after.content_id is None or after.version_no != 1:
            raise ValueError("新 Content 来源贡献要求已确定的首版本投影")
        source_item_key = content_source_item_key(observation)
        if source_item_key in source_keys:
            raise ValueError("新 Content 来源贡献不接受重复来源身份")
        source_keys.add(source_item_key)
        attempt_id, raw_id = _source_ids(observation)
        values.append(
            {
                "id": uuid4(),
                "source_item_key": source_item_key,
                "content_id": after.content_id,
                "provider_attempt_id": attempt_id,
                "raw_artifact_id": raw_id,
                "version_before": None,
                "version_after": 1,
                "delta": _build_delta(observation, None, after),
                "observed_at": observation.observed_at,
                "created_at": now,
            }
        )
    # 新 Content 在本事务前不可见，来源贡献冲突代表调用方破坏了批次前提；
    # 直接失败并整体回滚，不能静默把不相干的既有贡献当成本批结果。
    for chunk in batched(values, _MULTI_VALUES_INSERT_ROWS, strict=False):
        session.execute(insert(content_source_contributions_table), list(chunk))


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


def capture_content_contribution_snapshots_batch(
    session: Session,
    entries: tuple[tuple[CanonicalContentV1, UUID | None], ...],
) -> tuple[ContentContributionSnapshot, ...]:
    """按身份集合读取 Current、Version、Collection 与 Account 投影。"""

    if not entries:
        return ()
    explicit_ids = tuple({content_id for _, content_id in entries if content_id is not None})
    identities = tuple(
        {
            (observation.platform, observation.external_content_id)
            for observation, content_id in entries
            if content_id is None
        }
    )
    conditions = []
    if explicit_ids:
        conditions.append(contents_table.c.id.in_(explicit_ids))
    if identities:
        conditions.append(
            tuple_(contents_table.c.platform, contents_table.c.external_content_id).in_(identities)
        )
    content_rows = tuple(session.execute(select(contents_table).where(or_(*conditions))).mappings())
    contents_by_id = {cast(UUID, row["id"]): row for row in content_rows}
    contents_by_identity = {
        (cast(str, row["platform"]), cast(str, row["external_content_id"])): row
        for row in content_rows
    }
    version_pairs = tuple(
        (cast(UUID, row["id"]), cast(int, row["current_version"])) for row in content_rows
    )
    versions = (
        {
            (cast(UUID, row["content_id"]), cast(int, row["version_no"])): row
            for row in session.execute(
                select(content_versions_table).where(
                    tuple_(
                        content_versions_table.c.content_id,
                        content_versions_table.c.version_no,
                    ).in_(version_pairs)
                )
            ).mappings()
        }
        if version_pairs
        else {}
    )

    account_keys = tuple(
        {
            (observation.platform, observation.author.external_account_id)
            for observation, _ in entries
            if observation.author is not None and observation.author.external_account_id is not None
        }
    )
    accounts = (
        {
            (cast(str, row["platform"]), cast(str, row["external_account_id"])): row
            for row in session.execute(
                select(accounts_table).where(
                    tuple_(accounts_table.c.platform, accounts_table.c.external_account_id).in_(
                        account_keys
                    )
                )
            ).mappings()
        }
        if account_keys
        else {}
    )

    content_ids = tuple(contents_by_id)
    observed_collections = {
        field_name
        for observation, _ in entries
        for field_name in _observed_collections(observation)
    }
    collections: dict[str, dict[UUID, tuple[dict[str, object], ...]]] = {}
    for field_name in observed_collections:
        table = _COLLECTION_TABLES[field_name]
        order_columns = (table.c.id_type,) if field_name == "alternate_ids" else (table.c.position,)
        grouped: dict[UUID, list[dict[str, object]]] = {}
        if content_ids:
            rows = session.execute(
                select(table)
                .where(table.c.content_id.in_(content_ids))
                .order_by(table.c.content_id, *order_columns)
            ).mappings()
            for row in rows:
                grouped.setdefault(cast(UUID, row["content_id"]), []).append(
                    {str(key): value for key, value in row.items() if key != "content_id"}
                )
        collections[field_name] = {
            content_id: tuple(values) for content_id, values in grouped.items()
        }

    snapshots: list[ContentContributionSnapshot] = []
    for observation, explicit_id in entries:
        content_row = (
            contents_by_id.get(explicit_id)
            if explicit_id is not None
            else contents_by_identity.get((observation.platform, observation.external_content_id))
        )
        author = observation.author
        account = (
            accounts.get((observation.platform, author.external_account_id))
            if author is not None and author.external_account_id is not None
            else None
        )
        account_freshness = account["field_observed_at"] if account is not None else {}
        if not isinstance(account_freshness, dict):
            raise ValueError("Account field_observed_at 必须是对象")
        account_fields = (
            {
                path: account[column]
                for path, column in _ACCOUNT_FIELD_COLUMNS.items()
                if path in observation.observed_fields
            }
            if account is not None
            else {}
        )
        if content_row is None:
            snapshots.append(
                ContentContributionSnapshot(
                    content_id=None,
                    version_no=None,
                    content_fields={},
                    field_observed_at={},
                    author_snapshot=None,
                    collections={
                        field_name: () for field_name in _observed_collections(observation)
                    },
                    account_id=(cast(UUID, account["id"]) if account is not None else None),
                    account_fields=account_fields,
                    account_field_observed_at={
                        str(key): str(value) for key, value in account_freshness.items()
                    },
                )
            )
            continue
        content_id = cast(UUID, content_row["id"])
        version_no = cast(int, content_row["current_version"])
        version = versions.get((content_id, version_no))
        raw_freshness = content_row["field_observed_at"] or {}
        if not isinstance(raw_freshness, dict):
            raise ValueError("Content field_observed_at 必须是对象")
        snapshots.append(
            ContentContributionSnapshot(
                content_id=content_id,
                version_no=version_no,
                content_fields={
                    path: content_row[column]
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
                    field_name: collections[field_name].get(content_id, ())
                    for field_name in _observed_collections(observation)
                },
                account_id=(cast(UUID, account["id"]) if account is not None else None),
                account_fields=account_fields,
                account_field_observed_at={
                    str(key): str(value) for key, value in account_freshness.items()
                },
            )
        )
    return tuple(snapshots)


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
    "build_content_contribution_delta",
    "capture_content_contribution_snapshots_batch",
    "capture_content_contribution_snapshot",
    "commit_new_content_contributions_batch",
    "ContentContributionDraft",
    "ContentContributionSnapshot",
    "commit_content_contribution",
    "commit_content_contributions_batch",
    "content_source_item_key",
    "decode_contribution_value",
    "new_content_contribution_snapshot",
    "prepare_content_contribution",
    "prepare_content_contributions_batch",
]
