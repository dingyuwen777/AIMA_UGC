"""Analysis Scheme 复制辅助、归档、恢复与条件删除的 Analysis Owner Repository。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.analysis.lifecycle_schema import register_analysis_lifecycle_schema
from aima_ugc.modules.analysis.scheme_tables import (
    analysis_scheme_versions_table,
    analysis_schemes_table,
)
from aima_ugc.modules.analysis.tables import analysis_content_runs_table

register_analysis_lifecycle_schema()


@dataclass(frozen=True, slots=True)
class ArchivedAnalysisSchemeRecord:
    """已归档 Analysis Scheme 的最小业务投影。"""

    id: UUID
    name: str
    archived_at: datetime


class PostgresAnalysisSchemeLifecycleRepository:
    """Analysis Scheme 聚合生命周期；历史 Run 只用于删除资格守卫。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_update(self, scheme_id: UUID) -> RowMapping | None:
        """锁定 Scheme 父事实。"""

        return (
            self._session.execute(
                select(analysis_schemes_table)
                .where(analysis_schemes_table.c.id == scheme_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )

    def latest_version_id(self, scheme_id: UUID) -> UUID | None:
        """返回最新版本 ID；复制由现有 Scheme Repository 读取并重新编译成新草稿。"""

        value = self._session.scalar(
            select(analysis_scheme_versions_table.c.id)
            .where(analysis_scheme_versions_table.c.scheme_id == scheme_id)
            .order_by(analysis_scheme_versions_table.c.version.desc())
            .limit(1)
        )
        return cast(UUID | None, value)

    def archive_blockers(self, scheme_id: UUID) -> tuple[str, ...]:
        """当前唯一 active Scheme 不能直接归档，避免让 AI 能力失去正式配置。"""

        row = self._session.execute(
            select(
                analysis_schemes_table.c.is_active,
                analysis_schemes_table.c.archived_at,
            ).where(analysis_schemes_table.c.id == scheme_id)
        ).mappings().one_or_none()
        if row is None:
            return ("资源不存在",)
        blockers: list[str] = []
        if row["archived_at"] is not None:
            blockers.append("分析方案已归档")
        if bool(row["is_active"]):
            blockers.append("当前生效的分析方案不能归档，请先发布或回滚到另一方案")
        return tuple(blockers)

    def archive(self, scheme_id: UUID, *, archived_at: datetime) -> bool:
        """归档非 active Scheme；不改写任何历史 Version。"""

        blockers = self.archive_blockers(scheme_id)
        if blockers:
            raise RuntimeError("；".join(blockers))
        archived = self._session.execute(
            update(analysis_schemes_table)
            .where(
                analysis_schemes_table.c.id == scheme_id,
                analysis_schemes_table.c.is_active.is_(False),
                analysis_schemes_table.c.archived_at.is_(None),
            )
            .values(archived_at=archived_at, updated_at=func.clock_timestamp())
            .returning(analysis_schemes_table.c.id)
        ).scalar_one_or_none()
        return archived == scheme_id

    def restore(self, scheme_id: UUID) -> bool:
        """恢复归档 Scheme；保持非 active，必须通过正式发布/回滚再生效。"""

        restored = self._session.execute(
            update(analysis_schemes_table)
            .where(
                analysis_schemes_table.c.id == scheme_id,
                analysis_schemes_table.c.archived_at.is_not(None),
            )
            .values(archived_at=None, is_active=False, updated_at=func.clock_timestamp())
            .returning(analysis_schemes_table.c.id)
        ).scalar_one_or_none()
        return restored == scheme_id

    def list_archived(self) -> tuple[ArchivedAnalysisSchemeRecord, ...]:
        rows = self._session.execute(
            select(
                analysis_schemes_table.c.id,
                analysis_schemes_table.c.name,
                analysis_schemes_table.c.archived_at,
            )
            .where(analysis_schemes_table.c.archived_at.is_not(None))
            .order_by(analysis_schemes_table.c.archived_at.desc(), analysis_schemes_table.c.id)
        ).mappings()
        return tuple(
            ArchivedAnalysisSchemeRecord(
                id=cast(UUID, row["id"]),
                name=cast(str, row["name"]),
                archived_at=cast(datetime, row["archived_at"]),
            )
            for row in rows
        )

    def delete_blockers(self, scheme_id: UUID) -> tuple[str, ...]:
        """只有从未发布、从未进入 Analysis Run 历史的归档 Scheme 才能硬删。"""

        row = self._session.execute(
            select(
                analysis_schemes_table.c.is_active,
                analysis_schemes_table.c.archived_at,
            ).where(analysis_schemes_table.c.id == scheme_id)
        ).mappings().one_or_none()
        if row is None:
            return ("资源不存在",)
        blockers: list[str] = []
        if row["archived_at"] is None:
            blockers.append("请先归档分析方案再执行永久删除")
        if bool(row["is_active"]):
            blockers.append("当前生效的分析方案不能永久删除")
        if self._session.scalar(
            select(analysis_scheme_versions_table.c.id)
            .where(
                analysis_scheme_versions_table.c.scheme_id == scheme_id,
                analysis_scheme_versions_table.c.published_at.is_not(None),
            )
            .limit(1)
        ) is not None:
            blockers.append("该分析方案已有发布历史，只允许归档")
        if self._session.scalar(
            select(analysis_content_runs_table.c.id)
            .join(
                analysis_scheme_versions_table,
                analysis_scheme_versions_table.c.id
                == analysis_content_runs_table.c.analysis_scheme_version_id,
            )
            .where(analysis_scheme_versions_table.c.scheme_id == scheme_id)
            .limit(1)
        ) is not None:
            blockers.append("AI 分析运行历史引用了该方案，只允许归档")
        return tuple(dict.fromkeys(blockers))

    def delete_archived(self, scheme_id: UUID) -> bool:
        """永久删除从未发布/使用的归档 Scheme 与其纯草稿历史。"""

        blockers = self.delete_blockers(scheme_id)
        if blockers:
            raise RuntimeError("；".join(blockers))
        self._session.execute(
            update(analysis_schemes_table)
            .where(analysis_schemes_table.c.id == scheme_id)
            .values(active_version_id=None)
        )
        self._session.execute(
            delete(analysis_scheme_versions_table).where(
                analysis_scheme_versions_table.c.scheme_id == scheme_id
            )
        )
        deleted = self._session.execute(
            delete(analysis_schemes_table)
            .where(
                analysis_schemes_table.c.id == scheme_id,
                analysis_schemes_table.c.archived_at.is_not(None),
            )
            .returning(analysis_schemes_table.c.id)
        ).scalar_one_or_none()
        return deleted == scheme_id


__all__ = [
    "ArchivedAnalysisSchemeRecord",
    "PostgresAnalysisSchemeLifecycleRepository",
]
