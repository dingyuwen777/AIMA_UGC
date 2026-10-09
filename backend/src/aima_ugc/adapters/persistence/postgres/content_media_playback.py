"""既有 Content Repository 的播放 URL 条件更新实现，不另建媒体写 Repository。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from aima_ugc.adapters.providers.video_stream import normalize_video_url
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.extended_tables import content_media_table
from aima_ugc.modules.content.media_observations import MEDIA_FIELDS, media_identity_token
from aima_ugc.modules.content.media_playback import media_source_revision
from aima_ugc.modules.content.media_playback_tables import (
    content_media_playback_states_table as states,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.jobs import JobExecutionFence

from .content_queries import PostgresContentQueryRepository
from .jobs import PostgresJobRepository


def read_playback_media(
    session: Session, content_id: UUID, position: int, *, lock: bool
) -> dict[str, Any] | None:
    content_statement = select(contents_table).where(contents_table.c.id == content_id)
    if lock:
        content_statement = content_statement.with_for_update()
    content = session.execute(content_statement).mappings().one_or_none()
    if (
        content is None
        or content["platform"] != "xiaohongshu"
        or not PostgresContentQueryRepository(session, analysis_identity=None).content_exists(
            content_id
        )
    ):
        return None
    row = (
        session.execute(
            select(content_media_table).where(
                content_media_table.c.content_id == content_id,
                content_media_table.c.position == position,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["media_type"] != "video":
        return None
    return {**row, "note_id": content["external_content_id"]}


def publish_media_refresh(
    session: Session,
    *,
    fence: JobExecutionFence,
    content_id: UUID,
    position: int,
    identity_token: str,
    expected_source_revision: str,
    generation: int,
    url: str,
    attempt_id: UUID,
    raw_id: UUID,
    observed_at: datetime,
    observed_external_media_id: str | None = None,
) -> str | None:
    """在 Job→Content→state 锁序及成功 Attempt/Raw 证明下只发布当前 URL。"""
    PostgresJobRepository(session).lock_current_execution(fence)
    row = read_playback_media(session, content_id, position, lock=True)
    state = (
        session.execute(
            select(states)
            .where(states.c.content_id == content_id, states.c.position == position)
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    url_marker = ((row or {}).get("observation_metadata") or {}).get("fields", {}).get("url", {})
    already_published = (
        row is not None
        and state is not None
        and state["job_id"] == fence.job_id
        and state["generation"] == generation
        and state["state"] == "ready"
        and state["identity_token"] == identity_token
        and media_identity_token(row) == identity_token
        and state["source_revision"] == media_source_revision(row)
        and row["url"] == normalize_video_url(url)
        and url_marker.get("provider_attempt_id") == str(attempt_id)
        and url_marker.get("raw_artifact_id") == str(raw_id)
    )
    if not already_published and (
        row is None
        or state is None
        or state["job_id"] != fence.job_id
        or state["generation"] != generation
        or state["state"] != "preparing"
        or state["identity_token"] != identity_token
        or media_identity_token(row) != identity_token
        or state["source_revision"] != expected_source_revision
        or media_source_revision(row) != expected_source_revision
    ):
        return None
    assert row is not None and state is not None
    if (
        row["external_media_id"] is not None
        and observed_external_media_id is not None
        and row["external_media_id"] != observed_external_media_id
    ):
        return None
    proof = session.execute(
        select(provider_request_attempts_table.c.id)
        .join(
            provider_requests_table,
            provider_requests_table.c.id == provider_request_attempts_table.c.provider_request_id,
        )
        .join(
            collection_scopes_table,
            collection_scopes_table.c.id == provider_requests_table.c.scope_id,
        )
        .join(collection_runs_table, collection_runs_table.c.id == collection_scopes_table.c.run_id)
        .where(
            provider_request_attempts_table.c.id == attempt_id,
            provider_request_attempts_table.c.raw_artifact_id == raw_id,
            provider_request_attempts_table.c.dispatch_status == "completed",
            provider_request_attempts_table.c.http_status == 200,
            provider_request_attempts_table.c.error_code.is_(None),
            provider_request_attempts_table.c.completed_at == observed_at,
            collection_scopes_table.c.run_id == state["run_id"],
            collection_runs_table.c.job_id == fence.job_id,
            collection_scopes_table.c.platform == "xiaohongshu",
            collection_scopes_table.c.source_type == "content",
            collection_scopes_table.c.source_value == str(content_id),
            collection_scopes_table.c.operation_group == "media_refresh",
            provider_requests_table.c.operation == "get_video_note_detail",
            provider_requests_table.c.request_params["params"]["note_id"].astext == row["note_id"],
        )
    ).scalar_one_or_none()
    if proof is None:
        raise ValueError("播放 URL 缺少当前 Run 的成功 Attempt/Raw 证明")
    if already_published:
        # URL 已提交但 Scope 尚未提交时，接管 Worker 复用同一成功 Raw；不能再收费或误判来源变化。
        assert state is not None
        return str(state["source_revision"])
    metadata = deepcopy(row.get("observation_metadata") or {})
    old_marker = {
        key: str(row[key]) if key != "observed_at" else row[key].isoformat()
        for key in ("provider_attempt_id", "raw_artifact_id", "observed_at")
    }
    markers = metadata.setdefault("fields", {})
    for field in MEDIA_FIELDS:
        markers.setdefault(field, dict(old_marker))
    # 旧行第一次改 URL 前冻结旧身份，避免 fallback token 随 URL 改变。
    metadata["identity_token"] = identity_token
    markers["url"] = {
        "provider_attempt_id": str(attempt_id),
        "raw_artifact_id": str(raw_id),
        "observed_at": observed_at.isoformat(),
    }
    refreshed = {
        **row,
        "url": normalize_video_url(url),
        "observation_metadata": metadata,
        "provider_attempt_id": attempt_id,
        "raw_artifact_id": raw_id,
        "observed_at": observed_at,
    }
    session.execute(
        update(content_media_table)
        .where(
            content_media_table.c.content_id == content_id,
            content_media_table.c.position == position,
        )
        .values(
            url=refreshed["url"],
            observation_metadata=metadata,
            provider_attempt_id=attempt_id,
            raw_artifact_id=raw_id,
            observed_at=observed_at,
        )
    )
    return media_source_revision(refreshed)
