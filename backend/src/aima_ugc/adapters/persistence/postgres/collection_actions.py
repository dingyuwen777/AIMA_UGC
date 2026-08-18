"""Collection 内容级后续动作的 fenced durable checkpoint。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.contracts.collection import CollectionDecisionV1
from aima_ugc.modules.collection.corrective_tables import collection_content_actions_table
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError

from .jobs import PostgresJobRepository


@dataclass(frozen=True, slots=True)
class CollectionContentActionRecord:
    id: UUID
    scope_id: UUID
    external_content_id: str
    search_provider_attempt_id: UUID
    search_raw_artifact_id: UUID
    search_observed_at: datetime
    decision: CollectionDecisionV1
    resolved_comment_count: int | None
    detail_completed: bool
    comments_completed: bool


class PostgresCollectionContentActionRepository:
    """每个 Scope/Content 只冻结一次动作；重试只恢复未完成阶段。"""

    def __init__(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        self._session_factory = session_factory

    def get(
        self,
        *,
        scope_id: UUID,
        external_content_id: str,
        fence: JobExecutionFence,
    ) -> CollectionContentActionRecord | None:
        session = self._session_factory()
        try:
            with session.begin():
                _lock_scope(session, scope_id=scope_id, fence=fence)
                row = (
                    session.execute(
                        select(collection_content_actions_table).where(
                            collection_content_actions_table.c.scope_id == scope_id,
                            collection_content_actions_table.c.external_content_id
                            == external_content_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                return None if row is None else _row_to_action(row)
        finally:
            session.close()

    def get_or_create(
        self,
        *,
        scope_id: UUID,
        external_content_id: str,
        search_provider_attempt_id: UUID,
        search_raw_artifact_id: UUID,
        search_observed_at: datetime,
        decision: CollectionDecisionV1,
        resolved_comment_count: int | None,
        fence: JobExecutionFence,
    ) -> CollectionContentActionRecord:
        if search_observed_at.utcoffset() is None:
            raise ValueError("Content action search_observed_at 必须包含时区")
        session = self._session_factory()
        try:
            with session.begin():
                _lock_scope(session, scope_id=scope_id, fence=fence)
                _require_attempt_source(
                    session,
                    scope_id=scope_id,
                    attempt_id=search_provider_attempt_id,
                    raw_artifact_id=search_raw_artifact_id,
                )
                values = {
                    "id": uuid4(),
                    "scope_id": scope_id,
                    "external_content_id": external_content_id,
                    "search_provider_attempt_id": search_provider_attempt_id,
                    "search_raw_artifact_id": search_raw_artifact_id,
                    "search_observed_at": search_observed_at,
                    "detail_action": decision.detail_action,
                    "detail_reason": decision.detail_reason,
                    "comment_action": decision.comment_action,
                    "comment_reason": decision.comment_reason,
                    "comment_target": decision.comment_target,
                    "reply_target_per_root": decision.reply_target_per_root,
                    "resolved_comment_count": resolved_comment_count,
                    "detail_completed": decision.detail_action == "skip",
                    "comments_completed": False,
                    "created_at": func.clock_timestamp(),
                    "updated_at": func.clock_timestamp(),
                }
                session.execute(
                    pg_insert(collection_content_actions_table)
                    .values(**values)
                    .on_conflict_do_nothing(
                        index_elements=[
                            collection_content_actions_table.c.scope_id,
                            collection_content_actions_table.c.external_content_id,
                        ]
                    )
                )
                row = (
                    session.execute(
                        select(collection_content_actions_table)
                        .where(
                            collection_content_actions_table.c.scope_id == scope_id,
                            collection_content_actions_table.c.external_content_id
                            == external_content_id,
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one()
                )
                return _row_to_action(row)
        finally:
            session.close()

    def complete_detail(
        self,
        *,
        action_id: UUID,
        decision: CollectionDecisionV1,
        resolved_comment_count: int | None,
        fence: JobExecutionFence,
    ) -> CollectionContentActionRecord:
        session = self._session_factory()
        try:
            with session.begin():
                row = _lock_action(session, action_id=action_id, fence=fence)
                if row["detail_completed"]:
                    return _row_to_action(row)
                session.execute(
                    update(collection_content_actions_table)
                    .where(collection_content_actions_table.c.id == action_id)
                    .values(
                        detail_completed=True,
                        comment_action=decision.comment_action,
                        comment_reason=decision.comment_reason,
                        comment_target=decision.comment_target,
                        reply_target_per_root=decision.reply_target_per_root,
                        resolved_comment_count=resolved_comment_count,
                        updated_at=func.clock_timestamp(),
                    )
                )
                updated = (
                    session.execute(
                        select(collection_content_actions_table).where(
                            collection_content_actions_table.c.id == action_id
                        )
                    )
                    .mappings()
                    .one()
                )
                return _row_to_action(updated)
        finally:
            session.close()

    def complete_comments(
        self,
        *,
        action_id: UUID,
        fence: JobExecutionFence,
    ) -> CollectionContentActionRecord:
        session = self._session_factory()
        try:
            with session.begin():
                row = _lock_action(session, action_id=action_id, fence=fence)
                if not row["detail_completed"] and row["detail_action"] != "skip":
                    raise ValueError("Detail 未完成前不能完成 Comments action")
                if not row["comments_completed"]:
                    session.execute(
                        update(collection_content_actions_table)
                        .where(collection_content_actions_table.c.id == action_id)
                        .values(comments_completed=True, updated_at=func.clock_timestamp())
                    )
                updated = (
                    session.execute(
                        select(collection_content_actions_table).where(
                            collection_content_actions_table.c.id == action_id
                        )
                    )
                    .mappings()
                    .one()
                )
                return _row_to_action(updated)
        finally:
            session.close()


def _lock_scope(session: Session, *, scope_id: UUID, fence: JobExecutionFence) -> None:
    PostgresJobRepository(session).lock_current_execution(fence)
    owner = session.scalar(
        select(collection_runs_table.c.job_id)
        .select_from(
            collection_scopes_table.join(
                collection_runs_table,
                collection_scopes_table.c.run_id == collection_runs_table.c.id,
            )
        )
        .where(collection_scopes_table.c.id == scope_id)
    )
    if owner != fence.job_id:
        raise LeaseLostError("Collection action Scope 不属于当前 Job Fence")


def _lock_action(
    session: Session,
    *,
    action_id: UUID,
    fence: JobExecutionFence,
) -> RowMapping:
    PostgresJobRepository(session).lock_current_execution(fence)
    row = (
        session.execute(
            select(collection_content_actions_table)
            .where(collection_content_actions_table.c.id == action_id)
            .with_for_update()
        )
        .mappings()
        .one()
    )
    _lock_scope(session, scope_id=cast(UUID, row["scope_id"]), fence=fence)
    return row


def _require_attempt_source(
    session: Session,
    *,
    scope_id: UUID,
    attempt_id: UUID,
    raw_artifact_id: UUID,
) -> None:
    row = session.execute(
        select(
            provider_requests_table.c.scope_id,
            provider_request_attempts_table.c.raw_artifact_id,
        )
        .select_from(
            provider_request_attempts_table.join(
                provider_requests_table,
                provider_request_attempts_table.c.provider_request_id
                == provider_requests_table.c.id,
            )
        )
        .where(provider_request_attempts_table.c.id == attempt_id)
    ).one_or_none()
    if row is None or row.scope_id != scope_id or row.raw_artifact_id != raw_artifact_id:
        raise ValueError("Collection action Search Attempt/Raw/Scope 来源不一致")


def _row_to_action(row: RowMapping) -> CollectionContentActionRecord:
    decision = CollectionDecisionV1(
        detail_action=cast(str, row["detail_action"]),
        detail_reason=cast(str, row["detail_reason"]),
        comment_action=cast(str, row["comment_action"]),
        comment_reason=cast(str, row["comment_reason"]),
        comment_target=cast(int | None, row["comment_target"]),
        reply_target_per_root=cast(int | None, row["reply_target_per_root"]),
    )
    return CollectionContentActionRecord(
        id=cast(UUID, row["id"]),
        scope_id=cast(UUID, row["scope_id"]),
        external_content_id=cast(str, row["external_content_id"]),
        search_provider_attempt_id=cast(UUID, row["search_provider_attempt_id"]),
        search_raw_artifact_id=cast(UUID, row["search_raw_artifact_id"]),
        search_observed_at=row["search_observed_at"],
        decision=decision,
        resolved_comment_count=cast(int | None, row["resolved_comment_count"]),
        detail_completed=cast(bool, row["detail_completed"]),
        comments_completed=cast(bool, row["comments_completed"]),
    )


__all__ = [
    "CollectionContentActionRecord",
    "PostgresCollectionContentActionRepository",
]
