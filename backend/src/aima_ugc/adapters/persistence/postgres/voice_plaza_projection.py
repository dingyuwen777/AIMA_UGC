"""声音广场派生投影的可恢复分块回填 Repository。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import Uuid, bindparam, func, select, text, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.content.read_model_tables import voice_plaza_projection_state_table
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.time import beijing_now


@dataclass(frozen=True, slots=True)
class VoicePlazaProjectionState:
    """单例回填游标与安全进度快照。"""

    status: Literal["pending", "running", "ready", "failed"]
    generation: int
    last_content_id: UUID | None
    projected_count: int
    total_content_count: int | None


class PostgresVoicePlazaProjectionRepository:
    """以 Job Fence 和 UUID Keyset 推进派生投影，不持有长事务。"""

    def __init__(self, session: Session) -> None:
        """绑定一个由调用方持有的短事务。"""

        self._session = session

    def get_state(self, *, for_update: bool = False) -> VoicePlazaProjectionState:
        """读取单例状态；Worker 启动与批次推进可选择行锁。"""

        statement = select(voice_plaza_projection_state_table).where(
            voice_plaza_projection_state_table.c.singleton.is_(True)
        )
        if for_update:
            statement = statement.with_for_update()
        row = self._session.execute(statement).mappings().one()
        return _state(row)

    def restart_generation(self, state: VoicePlazaProjectionState) -> VoicePlazaProjectionState:
        """终态 Job 未完成投影时创建新的幂等代次，保留已提交游标。"""

        row = (
            self._session.execute(
                update(voice_plaza_projection_state_table)
                .where(voice_plaza_projection_state_table.c.singleton.is_(True))
                .values(
                    generation=state.generation + 1,
                    status="pending",
                    last_error_code=None,
                    updated_at=beijing_now(),
                )
                .returning(*voice_plaza_projection_state_table.c)
            )
            .mappings()
            .one()
        )
        return _state(row)

    def project_next_batch(
        self,
        *,
        fence: JobExecutionFence,
        batch_size: int,
        expected_generation: int,
    ) -> tuple[VoicePlazaProjectionState, int]:
        """在一个短事务内刷新一批 Content 并提交同一检查点。"""

        if not 1 <= batch_size <= 1000:
            raise ValueError("声音广场投影 batch_size 必须在 1..1000")
        PostgresJobRepository(self._session).lock_current_execution(fence)
        state = self.get_state(for_update=True)
        if state.generation != expected_generation:
            return state, 0
        if state.status == "ready":
            return state, 0

        total = state.total_content_count
        if total is None:
            total = cast(
                int,
                self._session.scalar(select(func.count()).select_from(contents_table)),
            )
        statement = select(contents_table.c.id)
        if state.last_content_id is not None:
            statement = statement.where(contents_table.c.id > state.last_content_id)
        content_ids = tuple(
            self._session.scalars(statement.order_by(contents_table.c.id).limit(batch_size))
        )
        now = beijing_now()
        if not content_ids:
            row = (
                self._session.execute(
                    update(voice_plaza_projection_state_table)
                    .where(voice_plaza_projection_state_table.c.singleton.is_(True))
                    .values(
                        status="ready",
                        total_content_count=total,
                        finished_at=now,
                        last_error_code=None,
                        updated_at=now,
                    )
                    .returning(*voice_plaza_projection_state_table.c)
                )
                .mappings()
                .one()
            )
            return _state(row), 0

        refresh_batch = text(
            "SELECT refresh_voice_plaza_content_projection_batch(:content_ids)"
        ).bindparams(bindparam("content_ids", type_=ARRAY(Uuid())))
        self._session.execute(refresh_batch, {"content_ids": list(content_ids)}).all()
        row = (
            self._session.execute(
                update(voice_plaza_projection_state_table)
                .where(voice_plaza_projection_state_table.c.singleton.is_(True))
                .values(
                    status="running",
                    last_content_id=content_ids[-1],
                    projected_count=state.projected_count + len(content_ids),
                    total_content_count=total,
                    started_at=func.coalesce(
                        voice_plaza_projection_state_table.c.started_at,
                        now,
                    ),
                    finished_at=None,
                    last_error_code=None,
                    updated_at=now,
                )
                .returning(*voice_plaza_projection_state_table.c)
            )
            .mappings()
            .one()
        )
        return _state(row), len(content_ids)


def _state(row) -> VoicePlazaProjectionState:  # type: ignore[no-untyped-def]
    """把状态表 RowMapping 收敛为不可变执行快照。"""

    return VoicePlazaProjectionState(
        status=cast(Literal["pending", "running", "ready", "failed"], row["status"]),
        generation=cast(int, row["generation"]),
        last_content_id=cast(UUID | None, row["last_content_id"]),
        projected_count=cast(int, row["projected_count"]),
        total_content_count=cast(int | None, row["total_content_count"]),
    )


__all__ = [
    "PostgresVoicePlazaProjectionRepository",
    "VoicePlazaProjectionState",
]
