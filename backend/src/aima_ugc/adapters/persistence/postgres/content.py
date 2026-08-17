"""Stage 6 Content Owner PostgreSQL Current/History 摄取。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalCommentV1,
    CanonicalContentV1,
)
from aima_ugc.modules.content.account_tables import account_external_ids_table
from aima_ugc.modules.content.tables import (
    accounts_table,
    comment_coverage_observations_table,
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
_CONTENT_BUSINESS_COLUMNS = (
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
_COMMENT_BUSINESS_COLUMNS = (
    "root_comment_id",
    "parent_comment_id",
    "text",
    "published_at",
    "source_updated_at",
    "status",
    "is_by_content_author",
    "author_account_id",
)
_COVERAGE_VALUES = {"complete", "partial", "not_requested", "unavailable"}


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
        author_id = self._upsert_author(observation)
        content_id = uuid4()
        state = _new_content_state(content_id, observation, author_id)
        created = self._session.execute(
            pg_insert(contents_table)
            .values(**state)
            .on_conflict_do_nothing(
                index_elements=[
                    contents_table.c.platform,
                    contents_table.c.external_content_id,
                ]
            )
            .returning(contents_table.c.id)
        ).scalar_one_or_none()
        if created is not None:
            self._append_content_version(
                content_id=content_id,
                version_no=1,
                state=state,
                observation=observation,
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

        current = dict(
            self._session.execute(
                select(contents_table)
                .where(
                    contents_table.c.platform == observation.platform,
                    contents_table.c.external_content_id == observation.external_content_id,
                )
                .with_for_update()
            )
            .mappings()
            .one()
        )
        content_id = cast(UUID, current["id"])
        metric_changed = _content_metric_changed(current, observation)
        stale = observation.observed_at < current["last_seen_at"]
        business_changed = False
        version_no = int(current["current_version"])
        updates: dict[str, Any] = {
            "first_seen_at": min(current["first_seen_at"], observation.observed_at),
            "last_seen_at": max(current["last_seen_at"], observation.observed_at),
            "updated_at": max(current["updated_at"], observation.observed_at),
        }
        merged = dict(current)

        if not stale:
            current_updates = _content_updates(observation, author_id)
            merged.update(current_updates)
            business_changed = _business_tuple(
                current, _CONTENT_BUSINESS_COLUMNS
            ) != _business_tuple(merged, _CONTENT_BUSINESS_COLUMNS)
            version_no += 1 if business_changed else 0
            updates.update(current_updates)
            updates["current_version"] = version_no

        merged.update(updates)
        self._session.execute(
            update(contents_table).where(contents_table.c.id == content_id).values(**updates)
        )
        if business_changed:
            self._append_content_version(
                content_id=content_id,
                version_no=version_no,
                state=merged,
                observation=observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )

        metric_recorded = False
        has_metric_fields = any(
            f"metrics.{name}" in observation.observed_fields for name in _CONTENT_METRICS
        )
        if has_metric_fields and not self._has_content_source_metric(
            content_id, attempt_id, raw_id
        ):
            day = observation.observed_at.astimezone(_BUSINESS_TZ).date()
            if metric_changed:
                reason = "changed"
            elif not self._has_content_metric_on_day(content_id, day):
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
                )
                metric_recorded = True
        return PostgresIngestionResult(
            content_id,
            version_no,
            business_changed,
            metric_recorded,
        )

    def ingest_comment(self, observation: CanonicalCommentV1) -> PostgresIngestionResult:
        attempt_id, raw_id = _source_ids(observation)
        content_id = self._session.execute(
            select(contents_table.c.id).where(
                contents_table.c.platform == observation.platform,
                contents_table.c.external_content_id == observation.external_content_id,
            )
        ).scalar_one()
        author_id = self._upsert_comment_author(observation)
        comment_id = uuid4()
        state = _new_comment_state(comment_id, content_id, observation, author_id)
        created = self._session.execute(
            pg_insert(comments_table)
            .values(**state)
            .on_conflict_do_nothing(
                index_elements=[
                    comments_table.c.content_id,
                    comments_table.c.external_comment_id,
                ]
            )
            .returning(comments_table.c.id)
        ).scalar_one_or_none()
        if created is not None:
            self._append_comment_version(
                comment_id=comment_id,
                version_no=1,
                state=state,
                observation=observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            self._append_comment_metric(
                comment_id=comment_id,
                observation=observation,
                reason="initial",
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            return PostgresIngestionResult(comment_id, 1, True, True)

        current = dict(
            self._session.execute(
                select(comments_table)
                .where(
                    comments_table.c.content_id == content_id,
                    comments_table.c.external_comment_id == observation.external_comment_id,
                )
                .with_for_update()
            )
            .mappings()
            .one()
        )
        comment_id = cast(UUID, current["id"])
        metric_changed = _comment_metric_changed(current, observation)
        stale = observation.observed_at < current["last_seen_at"]
        business_changed = False
        version_no = int(current["current_version"])
        updates: dict[str, Any] = {
            "first_seen_at": min(current["first_seen_at"], observation.observed_at),
            "last_seen_at": max(current["last_seen_at"], observation.observed_at),
            "updated_at": max(current["updated_at"], observation.observed_at),
        }
        merged = dict(current)

        if not stale:
            current_updates = _comment_updates(observation, author_id)
            merged.update(current_updates)
            business_changed = _business_tuple(
                current, _COMMENT_BUSINESS_COLUMNS
            ) != _business_tuple(merged, _COMMENT_BUSINESS_COLUMNS)
            version_no += 1 if business_changed else 0
            updates.update(current_updates)
            updates["current_version"] = version_no

        merged.update(updates)
        self._session.execute(
            update(comments_table).where(comments_table.c.id == comment_id).values(**updates)
        )
        if business_changed:
            self._append_comment_version(
                comment_id=comment_id,
                version_no=version_no,
                state=merged,
                observation=observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )

        metric_recorded = False
        has_metric_fields = (
            "metrics.like_count" in observation.observed_fields
            or "metrics.reply_count" in observation.observed_fields
        )
        if has_metric_fields and not self._has_comment_source_metric(
            comment_id, attempt_id, raw_id
        ):
            day = observation.observed_at.astimezone(_BUSINESS_TZ).date()
            if metric_changed:
                reason = "changed"
            elif not self._has_comment_metric_on_day(comment_id, day):
                reason = "daily_checkpoint"
            else:
                reason = None
            if reason is not None:
                self._append_comment_metric(
                    comment_id=comment_id,
                    observation=observation,
                    reason=reason,
                    attempt_id=attempt_id,
                    raw_id=raw_id,
                )
                metric_recorded = True
        return PostgresIngestionResult(
            comment_id,
            version_no,
            business_changed,
            metric_recorded,
        )

    def record_comment_coverage(
        self,
        *,
        content_id: UUID,
        provider_attempt_id: UUID,
        raw_artifact_id: UUID,
        coverage: str,
        reported_total: int | None,
        collected_count: int,
        sample_mode: str,
        sort_mode: str,
        target_count: int | None,
        stop_reason: str,
        observed_at: datetime,
    ) -> UUID:
        """按来源幂等保存一次评论 Coverage；0016 前历史行可保留空扩展字段。"""
        if coverage not in _COVERAGE_VALUES:
            raise ValueError("Comment Coverage 状态非法")
        if reported_total is not None and reported_total < 0:
            raise ValueError("Comment Coverage reported_total 不能为负数")
        if collected_count < 0:
            raise ValueError("Comment Coverage collected_count 不能为负数")
        if target_count is not None and target_count < 0:
            raise ValueError("Comment Coverage target_count 不能为负数")
        if observed_at.utcoffset() is None:
            raise ValueError("Comment Coverage observed_at 必须包含时区")
        if not sample_mode.strip() or not sort_mode.strip() or not stop_reason.strip():
            raise ValueError("Comment Coverage 可观测字段不能为空")
        if coverage in {"not_requested", "unavailable"} and collected_count != 0:
            raise ValueError("未请求/不可用 Coverage 不能包含已采集评论")
        if coverage == "complete" and reported_total is not None:
            if collected_count < reported_total:
                raise ValueError("complete Coverage 的采集数不能小于 Provider 报告总数")

        coverage_id = uuid4()
        values = {
            "id": coverage_id,
            "content_id": content_id,
            "provider_attempt_id": provider_attempt_id,
            "raw_artifact_id": raw_artifact_id,
            "coverage": coverage,
            "reported_total": reported_total,
            "collected_count": collected_count,
            "sample_mode": sample_mode.strip(),
            "sort_mode": sort_mode.strip(),
            "target_count": target_count,
            "stop_reason": stop_reason.strip(),
            "observed_at": observed_at,
        }
        row_id = self._session.execute(
            pg_insert(comment_coverage_observations_table)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[
                    comment_coverage_observations_table.c.content_id,
                    comment_coverage_observations_table.c.provider_attempt_id,
                    comment_coverage_observations_table.c.raw_artifact_id,
                ],
                set_={
                    "coverage": values["coverage"],
                    "reported_total": values["reported_total"],
                    "collected_count": values["collected_count"],
                    "sample_mode": values["sample_mode"],
                    "sort_mode": values["sort_mode"],
                    "target_count": values["target_count"],
                    "stop_reason": values["stop_reason"],
                    "observed_at": values["observed_at"],
                },
            )
            .returning(comment_coverage_observations_table.c.id)
        ).scalar_one()
        return cast(UUID, row_id)

    def _upsert_author(self, observation: CanonicalContentV1) -> UUID | None:
        return self._upsert_account(
            observation.platform,
            observation.author,
            observation.observed_fields,
            observation.observed_at,
        )

    def _upsert_comment_author(self, observation: CanonicalCommentV1) -> UUID | None:
        return self._upsert_account(
            observation.platform,
            observation.author,
            observation.observed_fields,
            observation.observed_at,
        )

    def _upsert_account(
        self,
        platform: str,
        author: CanonicalAuthorV1 | None,
        observed_fields: list[str],
        observed_at: datetime,
    ) -> UUID | None:
        if author is None or author.external_account_id is None:
            return None
        author_values = {
            "display_name": author.display_name,
            "handle": author.handle,
            "profile_url": str(author.profile_url) if author.profile_url else None,
            "avatar_url": str(author.avatar_url) if author.avatar_url else None,
            "bio": author.bio,
            "verified": author.verified,
            "verification_label": author.verification_label,
            "region": author.region,
            "follower_count": author.follower_count,
            "following_count": author.following_count,
            "content_count": author.content_count,
            "total_like_count": author.total_like_count,
        }
        column_names = {
            "display_name": "display_name",
            "handle": "handle",
            "profile_url": "profile_url",
            "avatar_url": "avatar_url",
            "bio": "bio",
            "verified": "verified",
            "verification_label": "verification_label",
            "region": "region",
            "follower_count": "current_follower_count",
            "following_count": "current_following_count",
            "content_count": "current_content_count",
            "total_like_count": "current_total_like_count",
        }
        observed_values = {
            column_names[field_name]: value
            for field_name, value in author_values.items()
            if f"author.{field_name}" in observed_fields
        }
        account_id = uuid4()
        created = self._session.execute(
            pg_insert(accounts_table)
            .values(
                id=account_id,
                platform=platform,
                external_account_id=author.external_account_id,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
                updated_at=observed_at,
                **observed_values,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    accounts_table.c.platform,
                    accounts_table.c.external_account_id,
                ]
            )
            .returning(accounts_table.c.id)
        ).scalar_one_or_none()
        if created is None:
            row = dict(
                self._session.execute(
                    select(accounts_table)
                    .where(
                        accounts_table.c.platform == platform,
                        accounts_table.c.external_account_id == author.external_account_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            account_id = cast(UUID, row["id"])
            values: dict[str, Any] = {
                "first_seen_at": min(row["first_seen_at"], observed_at),
                "last_seen_at": max(row["last_seen_at"], observed_at),
                "updated_at": max(row["updated_at"], observed_at),
            }
            if observed_at >= row["last_seen_at"]:
                values.update(observed_values)
            self._session.execute(
                update(accounts_table).where(accounts_table.c.id == account_id).values(**values)
            )
        if "author.alternate_ids" in observed_fields:
            self._upsert_account_external_ids(account_id, author.alternate_ids)
        return account_id

    def _upsert_account_external_ids(
        self,
        account_id: UUID,
        alternate_ids: dict[str, str],
    ) -> None:
        for id_type, external_id in sorted(alternate_ids.items()):
            row = (
                self._session.execute(
                    select(account_external_ids_table).where(
                        account_external_ids_table.c.account_id == account_id,
                        account_external_ids_table.c.id_type == id_type,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                self._session.execute(
                    insert(account_external_ids_table).values(
                        account_id=account_id,
                        id_type=id_type,
                        external_id=external_id,
                    )
                )
            elif row["external_id"] != external_id:
                self._session.execute(
                    update(account_external_ids_table)
                    .where(
                        account_external_ids_table.c.account_id == account_id,
                        account_external_ids_table.c.id_type == id_type,
                    )
                    .values(external_id=external_id)
                )

    def _append_content_version(
        self,
        *,
        content_id: UUID,
        version_no: int,
        state: dict[str, Any],
        observation: CanonicalContentV1,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> None:
        self._session.execute(
            insert(content_versions_table).values(
                id=uuid4(),
                content_id=content_id,
                version_no=version_no,
                content_type=state["content_type"],
                title=state.get("title"),
                text=state.get("text"),
                canonical_url=state.get("canonical_url"),
                share_url=state.get("share_url"),
                author_snapshot=(
                    observation.author.model_dump(mode="json")
                    if observation.author is not None
                    else None
                ),
                published_at=state.get("published_at"),
                source_updated_at=state.get("source_updated_at"),
                status=state.get("status"),
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
    ) -> None:
        metrics = {
            name: (
                getattr(observation.metrics, name)
                if f"metrics.{name}" in observation.observed_fields
                else None
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
        *,
        comment_id: UUID,
        version_no: int,
        state: dict[str, Any],
        observation: CanonicalCommentV1,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> None:
        self._session.execute(
            insert(comment_versions_table).values(
                id=uuid4(),
                comment_id=comment_id,
                version_no=version_no,
                root_comment_id=state.get("root_comment_id"),
                parent_comment_id=state.get("parent_comment_id"),
                text=state.get("text"),
                author_snapshot=(
                    observation.author.model_dump(mode="json")
                    if observation.author is not None
                    else None
                ),
                published_at=state.get("published_at"),
                source_updated_at=state.get("source_updated_at"),
                status=state.get("status"),
                is_by_content_author=state.get("is_by_content_author"),
                provider_attempt_id=attempt_id,
                raw_artifact_id=raw_id,
                observed_at=observation.observed_at,
            )
        )

    def _append_comment_metric(
        self,
        *,
        comment_id: UUID,
        observation: CanonicalCommentV1,
        reason: str,
        attempt_id: UUID,
        raw_id: UUID,
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
                like_count=(
                    observation.metrics.like_count
                    if "metrics.like_count" in observation.observed_fields
                    else None
                ),
                reply_count=(
                    observation.metrics.reply_count
                    if "metrics.reply_count" in observation.observed_fields
                    else None
                ),
                observed_at=observation.observed_at,
            )
        )

    def _has_content_source_metric(
        self,
        content_id: UUID,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> bool:
        return (
            self._session.execute(
                select(content_metric_observations_table.c.id).where(
                    content_metric_observations_table.c.content_id == content_id,
                    content_metric_observations_table.c.provider_attempt_id == attempt_id,
                    content_metric_observations_table.c.raw_artifact_id == raw_id,
                )
            ).first()
            is not None
        )

    def _has_comment_source_metric(
        self,
        comment_id: UUID,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> bool:
        return (
            self._session.execute(
                select(comment_metric_observations_table.c.id).where(
                    comment_metric_observations_table.c.comment_id == comment_id,
                    comment_metric_observations_table.c.provider_attempt_id == attempt_id,
                    comment_metric_observations_table.c.raw_artifact_id == raw_id,
                )
            ).first()
            is not None
        )

    def _has_content_metric_on_day(self, content_id: UUID, day: date) -> bool:
        return (
            self._session.execute(
                select(content_metric_observations_table.c.id).where(
                    content_metric_observations_table.c.content_id == content_id,
                    content_metric_observations_table.c.business_date == day,
                )
            ).first()
            is not None
        )

    def _has_comment_metric_on_day(self, comment_id: UUID, day: date) -> bool:
        return (
            self._session.execute(
                select(comment_metric_observations_table.c.id).where(
                    comment_metric_observations_table.c.comment_id == comment_id,
                    comment_metric_observations_table.c.business_date == day,
                )
            ).first()
            is not None
        )


def _source_ids(
    observation: CanonicalContentV1 | CanonicalCommentV1,
) -> tuple[UUID, UUID]:
    if observation.source.provider_attempt_id is None or observation.source.raw_artifact_id is None:
        raise ValueError("持久化 Canonical 必须包含 provider_attempt_id 与 raw_artifact_id")
    return UUID(observation.source.provider_attempt_id), observation.source.raw_artifact_id


def _new_content_state(
    content_id: UUID,
    observation: CanonicalContentV1,
    author_id: UUID | None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
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
    state.update(_content_updates(observation, author_id))
    return state


def _content_updates(
    observation: CanonicalContentV1,
    author_id: UUID | None,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if "content_type" in observation.observed_fields:
        updates["content_type"] = observation.content_type
    values = {
        "title": observation.title,
        "text": observation.text,
        "canonical_url": (str(observation.canonical_url) if observation.canonical_url else None),
        "share_url": str(observation.share_url) if observation.share_url else None,
        "published_at": observation.published_at,
        "source_updated_at": observation.source_updated_at,
        "status": observation.status,
    }
    for path, value in values.items():
        if path in observation.observed_fields:
            updates[path] = value
    if (
        observation.author is not None
        and author_id is not None
        and "author.external_account_id" in observation.observed_fields
    ):
        updates["author_account_id"] = author_id
    for name in _CONTENT_METRICS:
        if f"metrics.{name}" in observation.observed_fields:
            updates[f"current_{name}"] = getattr(observation.metrics, name)
    return updates


def _new_comment_state(
    comment_id: UUID,
    content_id: UUID,
    observation: CanonicalCommentV1,
    author_id: UUID | None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "id": comment_id,
        "content_id": content_id,
        "external_comment_id": observation.external_comment_id,
        "root_comment_id": observation.root_comment_id,
        "parent_comment_id": observation.parent_comment_id,
        "author_account_id": author_id,
        "first_seen_at": observation.observed_at,
        "last_seen_at": observation.observed_at,
        "current_version": 1,
        "updated_at": observation.observed_at,
    }
    state.update(_comment_updates(observation, author_id))
    return state


def _comment_updates(
    observation: CanonicalCommentV1,
    author_id: UUID | None,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    values = {
        "root_comment_id": observation.root_comment_id,
        "parent_comment_id": observation.parent_comment_id,
        "text": observation.text,
        "published_at": observation.published_at,
        "source_updated_at": observation.source_updated_at,
        "status": observation.status,
        "is_by_content_author": observation.is_by_content_author,
    }
    for path, value in values.items():
        if path in observation.observed_fields:
            updates[path] = value
    if (
        observation.author is not None
        and author_id is not None
        and "author.external_account_id" in observation.observed_fields
    ):
        updates["author_account_id"] = author_id
    if "metrics.like_count" in observation.observed_fields:
        updates["current_like_count"] = observation.metrics.like_count
    if "metrics.reply_count" in observation.observed_fields:
        updates["current_reply_count"] = observation.metrics.reply_count
    return updates


def _content_metric_changed(current: dict[str, Any], observation: CanonicalContentV1) -> bool:
    return any(
        f"metrics.{name}" in observation.observed_fields
        and current.get(f"current_{name}") != getattr(observation.metrics, name)
        for name in _CONTENT_METRICS
    )


def _comment_metric_changed(current: dict[str, Any], observation: CanonicalCommentV1) -> bool:
    return (
        "metrics.like_count" in observation.observed_fields
        and current.get("current_like_count") != observation.metrics.like_count
    ) or (
        "metrics.reply_count" in observation.observed_fields
        and current.get("current_reply_count") != observation.metrics.reply_count
    )


def _business_tuple(row: dict[str, Any], columns: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(row.get(name) for name in columns)


def _observation_key(
    observation: CanonicalContentV1 | CanonicalCommentV1,
    reason: str,
) -> str:
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
