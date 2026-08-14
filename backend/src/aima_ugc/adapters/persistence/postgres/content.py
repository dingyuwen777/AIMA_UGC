"""Stage 6 Content Owner PostgreSQL Current/History 摄取。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.modules.content.tables import (
    accounts_table,
    comment_metric_observations_table,
    comment_versions_table,
    comments_table,
    content_metric_observations_table,
    content_versions_table,
    contents_table,
)

_BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
_CONTENT_METRICS = (
    "like_count",
    "comment_count",
    "share_count",
    "repost_count",
    "favorite_count",
    "view_count",
    "play_count",
    "danmaku_count",
    "coin_count",
    "download_count",
)


@dataclass(frozen=True, slots=True)
class PostgresIngestionResult:
    target_id: UUID
    version_no: int
    version_created: bool
    metric_recorded: bool


class PostgresContentRepository:
    """Content 模块唯一业务表写入口；事务由调用方持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ingest_content(self, observation: CanonicalContentV1) -> PostgresIngestionResult:
        attempt_id, raw_id = _source_ids(observation)
        row = (
            self._session.execute(
                select(contents_table)
                .where(
                    contents_table.c.platform == observation.platform,
                    contents_table.c.external_content_id == observation.external_content_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        author_id = self._upsert_author(observation)
        if row is None:
            content_id = uuid4()
            values = _new_content_values(content_id, observation, author_id)
            self._session.execute(insert(contents_table).values(**values))
            self._append_content_version(
                content_id=content_id,
                version_no=1,
                observation=observation,
                author_id=author_id,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            self._append_content_metric(
                content_id=content_id,
                observation=observation,
                reason="initial",
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            return PostgresIngestionResult(content_id, 1, True, True)

        content_id = row["id"]
        updates = _content_updates(dict(row), observation, author_id)
        business_changed = _content_business_tuple(dict(row)) != _content_business_tuple(
            {**dict(row), **updates}
        )
        version_no = int(row["current_version"]) + (1 if business_changed else 0)
        updates["current_version"] = version_no
        updates["last_seen_at"] = max(row["last_seen_at"], observation.observed_at)
        updates["updated_at"] = observation.observed_at
        self._session.execute(
            update(contents_table).where(contents_table.c.id == content_id).values(**updates)
        )
        if business_changed:
            self._append_content_version(
                content_id=content_id,
                version_no=version_no,
                observation=_merge_content_for_version(dict(row), updates, observation),
                author_id=updates.get("author_account_id", row["author_account_id"]),
                attempt_id=attempt_id,
                raw_id=raw_id,
            )

        metric_changed = any(
            f"metrics.{name}" in observation.observed_fields
            and updates.get(f"current_{name}", row[f"current_{name}"]) != row[f"current_{name}"]
            for name in _CONTENT_METRICS
        )
        metric_recorded = False
        if any(f"metrics.{name}" in observation.observed_fields for name in _CONTENT_METRICS):
            day = observation.observed_at.astimezone(_BUSINESS_TZ).date()
            if metric_changed:
                reason = "changed"
            elif not self._has_content_checkpoint(content_id, day):
                reason = "daily_checkpoint"
            else:
                reason = None
            if reason is not None:
                self._append_content_metric(
                    content_id=content_id,
                    observation=observation,
                    reason=reason,
                    attempt_id=attempt_id,
                    raw_id=raw_id,
                    current={**dict(row), **updates},
                )
                metric_recorded = True
        return PostgresIngestionResult(content_id, version_no, business_changed, metric_recorded)

    def ingest_comment(self, observation: CanonicalCommentV1) -> PostgresIngestionResult:
        attempt_id, raw_id = _source_ids(observation)
        content_id = self._session.execute(
            select(contents_table.c.id).where(
                contents_table.c.platform == observation.platform,
                contents_table.c.external_content_id == observation.external_content_id,
            )
        ).scalar_one()
        row = (
            self._session.execute(
                select(comments_table)
                .where(
                    comments_table.c.content_id == content_id,
                    comments_table.c.external_comment_id == observation.external_comment_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        author_id = self._upsert_comment_author(observation)
        like_count = (
            observation.metrics.like_count
            if "metrics.like_count" in observation.observed_fields
            else None
        )
        reply_count = (
            observation.metrics.reply_count
            if "metrics.reply_count" in observation.observed_fields
            else None
        )
        if row is None:
            comment_id = uuid4()
            self._session.execute(
                insert(comments_table).values(
                    id=comment_id,
                    content_id=content_id,
                    external_comment_id=observation.external_comment_id,
                    root_comment_id=observation.root_comment_id,
                    parent_comment_id=observation.parent_comment_id,
                    author_account_id=author_id,
                    text=observation.text if "text" in observation.observed_fields else None,
                    published_at=(
                        observation.published_at
                        if "published_at" in observation.observed_fields
                        else None
                    ),
                    source_updated_at=(
                        observation.source_updated_at
                        if "source_updated_at" in observation.observed_fields
                        else None
                    ),
                    status=observation.status if "status" in observation.observed_fields else None,
                    is_by_content_author=(
                        observation.is_by_content_author
                        if "is_by_content_author" in observation.observed_fields
                        else None
                    ),
                    first_seen_at=observation.observed_at,
                    last_seen_at=observation.observed_at,
                    current_like_count=like_count,
                    current_reply_count=reply_count,
                    current_version=1,
                    updated_at=observation.observed_at,
                )
            )
            self._append_comment_version(
                comment_id,
                1,
                observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            self._append_comment_metric(
                comment_id,
                observation,
                reason="initial",
                attempt_id=attempt_id,
                raw_id=raw_id,
                like_count=like_count,
                reply_count=reply_count,
            )
            return PostgresIngestionResult(comment_id, 1, True, True)

        comment_id = row["id"]
        updates: dict[str, Any] = {"last_seen_at": max(row["last_seen_at"], observation.observed_at)}
        field_map = {
            "root_comment_id": "root_comment_id",
            "parent_comment_id": "parent_comment_id",
            "text": "text",
            "published_at": "published_at",
            "source_updated_at": "source_updated_at",
            "status": "status",
            "is_by_content_author": "is_by_content_author",
        }
        for path, column in field_map.items():
            if path in observation.observed_fields:
                updates[column] = getattr(observation, path)
        if observation.author is not None and author_id is not None:
            updates["author_account_id"] = author_id
        if "metrics.like_count" in observation.observed_fields:
            updates["current_like_count"] = observation.metrics.like_count
        if "metrics.reply_count" in observation.observed_fields:
            updates["current_reply_count"] = observation.metrics.reply_count
        business_columns = (
            "root_comment_id",
            "parent_comment_id",
            "text",
            "published_at",
            "source_updated_at",
            "status",
            "is_by_content_author",
            "author_account_id",
        )
        business_changed = any(updates.get(name, row[name]) != row[name] for name in business_columns)
        version_no = int(row["current_version"]) + (1 if business_changed else 0)
        updates["current_version"] = version_no
        updates["updated_at"] = observation.observed_at
        self._session.execute(
            update(comments_table).where(comments_table.c.id == comment_id).values(**updates)
        )
        if business_changed:
            self._append_comment_version(
                comment_id,
                version_no,
                observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
                current={**dict(row), **updates},
            )
        metric_changed = (
            ("metrics.like_count" in observation.observed_fields and like_count != row["current_like_count"])
            or (
                "metrics.reply_count" in observation.observed_fields
                and reply_count != row["current_reply_count"]
            )
        )
        metric_recorded = False
        if "metrics.like_count" in observation.observed_fields or "metrics.reply_count" in observation.observed_fields:
            day = observation.observed_at.astimezone(_BUSINESS_TZ).date()
            if metric_changed:
                reason = "changed"
            elif not self._has_comment_checkpoint(comment_id, day):
                reason = "daily_checkpoint"
            else:
                reason = None
            if reason:
                self._append_comment_metric(
                    comment_id,
                    observation,
                    reason=reason,
                    attempt_id=attempt_id,
                    raw_id=raw_id,
                    like_count=updates.get("current_like_count", row["current_like_count"]),
                    reply_count=updates.get("current_reply_count", row["current_reply_count"]),
                )
                metric_recorded = True
        return PostgresIngestionResult(comment_id, version_no, business_changed, metric_recorded)

    def _upsert_author(self, observation: CanonicalContentV1) -> UUID | None:
        return self._upsert_account(observation.platform, observation.author, observation.observed_at)

    def _upsert_comment_author(self, observation: CanonicalCommentV1) -> UUID | None:
        return self._upsert_account(observation.platform, observation.author, observation.observed_at)

    def _upsert_account(self, platform: str, author: Any, observed_at: Any) -> UUID | None:
        if author is None or author.external_account_id is None:
            return None
        row = self._session.execute(
            select(accounts_table).where(
                accounts_table.c.platform == platform,
                accounts_table.c.external_account_id == author.external_account_id,
            )
        ).mappings().one_or_none()
        values = {
            "display_name": author.display_name,
            "handle": author.handle,
            "profile_url": str(author.profile_url) if author.profile_url else None,
            "avatar_url": str(author.avatar_url) if author.avatar_url else None,
            "bio": author.bio,
            "verified": author.verified,
            "verification_label": author.verification_label,
            "region": author.region,
            "current_follower_count": author.follower_count,
            "current_following_count": author.following_count,
            "current_content_count": author.content_count,
            "current_total_like_count": author.total_like_count,
            "last_seen_at": observed_at,
            "updated_at": observed_at,
        }
        if row is not None:
            self._session.execute(update(accounts_table).where(accounts_table.c.id == row["id"]).values(**values))
            return row["id"]
        account_id = uuid4()
        self._session.execute(
            insert(accounts_table).values(
                id=account_id,
                platform=platform,
                external_account_id=author.external_account_id,
                first_seen_at=observed_at,
                **values,
            )
        )
        return account_id

    def _append_content_version(
        self,
        *,
        content_id: UUID,
        version_no: int,
        observation: CanonicalContentV1,
        author_id: UUID | None,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> None:
        del author_id
        self._session.execute(
            insert(content_versions_table).values(
                id=uuid4(),
                content_id=content_id,
                version_no=version_no,
                content_type=observation.content_type,
                title=observation.title,
                text=observation.text,
                canonical_url=str(observation.canonical_url) if observation.canonical_url else None,
                share_url=str(observation.share_url) if observation.share_url else None,
                author_snapshot=(observation.author.model_dump(mode="json") if observation.author else None),
                published_at=observation.published_at,
                source_updated_at=observation.source_updated_at,
                status=observation.status,
                provider_attempt_id=attempt_id,
                raw_artifact_id=raw_id,
                observed_at=observation.observed_at,
            )
        )

    def _append_content_metric(
        self,
        *,
        content_id: UUID,
        observation: CanonicalContentV1,
        reason: str,
        attempt_id: UUID,
        raw_id: UUID,
        current: dict[str, Any] | None = None,
    ) -> None:
        values = current or {}
        metrics = {
            name: (
                getattr(observation.metrics, name)
                if f"metrics.{name}" in observation.observed_fields
                else values.get(f"current_{name}")
            )
            for name in _CONTENT_METRICS
        }
        self._session.execute(
            insert(content_metric_observations_table).values(
                id=uuid4(),
                content_id=content_id,
                provider_attempt_id=attempt_id,
                raw_artifact_id=raw_id,
                reason=reason,
                business_date=observation.observed_at.astimezone(_BUSINESS_TZ).date(),
                observation_key=_observation_key(observation, reason),
                observed_at=observation.observed_at,
                **metrics,
            )
        )

    def _append_comment_version(
        self,
        comment_id: UUID,
        version_no: int,
        observation: CanonicalCommentV1,
        *,
        attempt_id: UUID,
        raw_id: UUID,
        current: dict[str, Any] | None = None,
    ) -> None:
        state = current or {}
        self._session.execute(
            insert(comment_versions_table).values(
                id=uuid4(),
                comment_id=comment_id,
                version_no=version_no,
                root_comment_id=state.get("root_comment_id", observation.root_comment_id),
                parent_comment_id=state.get("parent_comment_id", observation.parent_comment_id),
                text=state.get("text", observation.text),
                author_snapshot=(observation.author.model_dump(mode="json") if observation.author else None),
                published_at=state.get("published_at", observation.published_at),
                source_updated_at=state.get("source_updated_at", observation.source_updated_at),
                status=state.get("status", observation.status),
                is_by_content_author=state.get(
                    "is_by_content_author", observation.is_by_content_author
                ),
                provider_attempt_id=attempt_id,
                raw_artifact_id=raw_id,
                observed_at=observation.observed_at,
            )
        )

    def _append_comment_metric(
        self,
        comment_id: UUID,
        observation: CanonicalCommentV1,
        *,
        reason: str,
        attempt_id: UUID,
        raw_id: UUID,
        like_count: int | None,
        reply_count: int | None,
    ) -> None:
        self._session.execute(
            insert(comment_metric_observations_table).values(
                id=uuid4(),
                comment_id=comment_id,
                provider_attempt_id=attempt_id,
                raw_artifact_id=raw_id,
                reason=reason,
                business_date=observation.observed_at.astimezone(_BUSINESS_TZ).date(),
                observation_key=_observation_key(observation, reason),
                like_count=like_count,
                reply_count=reply_count,
                observed_at=observation.observed_at,
            )
        )

    def _has_content_checkpoint(self, content_id: UUID, day: date) -> bool:
        return self._session.execute(
            select(content_metric_observations_table.c.id).where(
                content_metric_observations_table.c.content_id == content_id,
                content_metric_observations_table.c.business_date == day,
                content_metric_observations_table.c.reason == "daily_checkpoint",
            )
        ).first() is not None

    def _has_comment_checkpoint(self, comment_id: UUID, day: date) -> bool:
        return self._session.execute(
            select(comment_metric_observations_table.c.id).where(
                comment_metric_observations_table.c.comment_id == comment_id,
                comment_metric_observations_table.c.business_date == day,
                comment_metric_observations_table.c.reason == "daily_checkpoint",
            )
        ).first() is not None


def _source_ids(observation: CanonicalContentV1 | CanonicalCommentV1) -> tuple[UUID, UUID]:
    if observation.source.provider_attempt_id is None or observation.source.raw_artifact_id is None:
        raise ValueError("持久化 Canonical 必须包含 provider_attempt_id 与 raw_artifact_id")
    return UUID(observation.source.provider_attempt_id), observation.source.raw_artifact_id


def _new_content_values(
    content_id: UUID, observation: CanonicalContentV1, author_id: UUID | None
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "id": content_id,
        "platform": observation.platform,
        "external_content_id": observation.external_content_id,
        "content_type": observation.content_type,
        "author_account_id": author_id,
        "first_seen_at": observation.observed_at,
        "last_seen_at": observation.observed_at,
        "current_version": 1,
        "updated_at": observation.observed_at,
    }
    return _content_updates(values, observation, author_id)


def _content_updates(
    current: dict[str, Any], observation: CanonicalContentV1, author_id: UUID | None
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    simple = {
        "content_type": observation.content_type,
        "title": observation.title,
        "text": observation.text,
        "canonical_url": str(observation.canonical_url) if observation.canonical_url else None,
        "share_url": str(observation.share_url) if observation.share_url else None,
        "published_at": observation.published_at,
        "source_updated_at": observation.source_updated_at,
        "status": observation.status,
    }
    for path, value in simple.items():
        if path == "content_type" or path in observation.observed_fields:
            updates[path] = value
    if observation.author is not None and author_id is not None:
        updates["author_account_id"] = author_id
    for name in _CONTENT_METRICS:
        if f"metrics.{name}" in observation.observed_fields:
            updates[f"current_{name}"] = getattr(observation.metrics, name)
    for key, value in current.items():
        updates.setdefault(key, value)
    return updates


def _content_business_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        row.get(name)
        for name in (
            "content_type",
            "title",
            "text",
            "canonical_url",
            "share_url",
            "author_account_id",
            "published_at",
            "source_updated_at",
            "status",
        )
    )


def _merge_content_for_version(
    previous: dict[str, Any], updates: dict[str, Any], observation: CanonicalContentV1
) -> CanonicalContentV1:
    values = {**previous, **updates}
    return observation.model_copy(
        update={
            "content_type": values["content_type"],
            "title": values.get("title"),
            "text": values.get("text"),
            "published_at": values.get("published_at"),
            "source_updated_at": values.get("source_updated_at"),
            "status": values.get("status"),
        }
    )


def _observation_key(observation: CanonicalContentV1 | CanonicalCommentV1, reason: str) -> str:
    payload = {
        "attempt": observation.source.provider_attempt_id,
        "raw": str(observation.source.raw_artifact_id),
        "locator": observation.source.item_locator,
        "observed_at": observation.observed_at.isoformat(),
        "reason": reason,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
