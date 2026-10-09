"""Content Owner 的媒体播放状态与纯 URL 条件更新。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from aima_ugc.modules.content.media_observations import media_identity_token
from aima_ugc.modules.content.media_playback import ContentPlaybackSource, media_source_revision
from aima_ugc.modules.content.media_playback_tables import (
    content_media_playback_states_table as states,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.time import beijing_now


class PostgresContentPlaybackRepository:
    """所有写入持有 Content 锁；Worker 写入先验证并锁定 Job Fence。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _media(self, content_id: UUID, position: int, *, lock: bool) -> dict[str, Any] | None:
        from .content_media_playback import read_playback_media

        return read_playback_media(self._session, content_id, position, lock=lock)

    def get_source(
        self, content_id: UUID, position: int, *, lock: bool = False
    ) -> ContentPlaybackSource | None:
        """来源失效只使旧准备状态失效，不能把其 failure 传给新的正常补采 URL。"""
        row = self._media(content_id, position, lock=lock)
        if row is None:
            return None
        state = (
            self._session.execute(
                select(states).where(
                    states.c.content_id == content_id, states.c.position == position
                )
            )
            .mappings()
            .one_or_none()
        )
        token, revision = media_identity_token(row), media_source_revision(row)
        current = (
            state is not None
            and state["identity_token"] == token
            and state["source_revision"] == revision
        )
        effective = state if current and state is not None else {}
        return ContentPlaybackSource(
            content_id=content_id,
            position=position,
            note_id=str(row["note_id"]),
            identity_token=token,
            source_revision=revision,
            url=row["url"],
            generation=int(state["generation"]) if state else 0,
            job_id=effective.get("job_id"),
            run_id=effective.get("run_id"),
            state=effective.get("state", "ready"),
            failure_code=effective.get("failure_code"),
            failure_source_revision=effective.get("failure_source_revision"),
            cooldown_until=effective.get("cooldown_until"),
        )

    def begin_refresh(self, source: ContentPlaybackSource, *, job_id: UUID, run_id: UUID) -> None:
        """调用方在同一事务持 Content 锁并创建正式 Job/Run/Scope 后绑定代次。"""
        values = dict(
            content_id=source.content_id,
            position=source.position,
            identity_token=source.identity_token,
            source_revision=source.source_revision,
            generation=source.generation + 1,
            state="preparing",
            job_id=job_id,
            run_id=run_id,
            obtained_at=None,
            explicit_expires_at=None,
            failure_code=None,
            failure_source_revision=None,
            cooldown_until=None,
        )
        self._session.execute(
            pg_insert(states)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[states.c.content_id, states.c.position], set_=values
            )
        )

    def publish_refresh(
        self,
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
    ) -> bool:
        """同一事务委托既有 Content Owner 发布 URL，再更新本状态表。"""
        from .content import PostgresContentRepository

        revision = PostgresContentRepository(self._session).publish_media_refresh(
            fence=fence,
            content_id=content_id,
            position=position,
            identity_token=identity_token,
            expected_source_revision=expected_source_revision,
            generation=generation,
            url=url,
            attempt_id=attempt_id,
            raw_id=raw_id,
            observed_at=observed_at,
            observed_external_media_id=observed_external_media_id,
        )
        if revision is None:
            return False
        self._session.execute(
            update(states)
            .where(states.c.content_id == content_id, states.c.position == position)
            .values(
                state="ready",
                source_revision=revision,
                obtained_at=observed_at,
                failure_code=None,
                failure_source_revision=None,
                cooldown_until=beijing_now() + timedelta(minutes=5),
            )
        )
        return True

    def record_stream_failure(
        self, source: ContentPlaybackSource, *, code: str, now: datetime
    ) -> None:
        """旧连接失败不得污染已被正常补采或其他刷新替换的来源。"""
        current = self.get_source(source.content_id, source.position, lock=True)
        if (
            current is None
            or current.identity_token != source.identity_token
            or current.source_revision != source.source_revision
        ):
            return
        values = dict(
            content_id=source.content_id,
            position=source.position,
            identity_token=source.identity_token,
            source_revision=source.source_revision,
            generation=current.generation,
            state=current.state,
            job_id=current.job_id,
            run_id=current.run_id,
            failure_code=code,
            failure_source_revision=source.source_revision,
            cooldown_until=now + timedelta(seconds=30)
            if code == "cdn_rate_limited"
            else current.cooldown_until,
        )
        self._session.execute(
            pg_insert(states)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[states.c.content_id, states.c.position],
                set_={
                    key: values[key]
                    for key in ("failure_code", "failure_source_revision", "cooldown_until")
                },
            )
        )

    def settle_job(self, job_id: UUID, *, code: str, now: datetime) -> int:
        """终态回调与 API 恢复共用；只结束仍属于该 Job 的 preparing 状态。"""
        rows = self._session.execute(
            select(states.c.content_id, states.c.position).where(
                states.c.job_id == job_id, states.c.state == "preparing"
            )
        ).all()
        changed = 0
        for content_id, position in rows:
            self._session.execute(
                select(contents_table.c.id)
                .where(contents_table.c.id == content_id)
                .with_for_update()
            )
            result = self._session.execute(
                update(states)
                .where(
                    states.c.content_id == content_id,
                    states.c.position == position,
                    states.c.job_id == job_id,
                    states.c.state == "preparing",
                )
                .values(
                    state="unavailable",
                    failure_code=code,
                    failure_source_revision=states.c.source_revision,
                    cooldown_until=now + timedelta(minutes=5),
                )
                .returning(states.c.content_id)
            )
            changed += len(result.all())
        return changed
