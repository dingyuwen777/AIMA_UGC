"""Analysis Scheme 复制辅助、归档、恢复与删除的 Analysis Owner Repository。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
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


@dataclass(frozen=True, slots=True)
class AnalysisSchemeDeletionResult:
    """记录管理视图删除采用的持久化模式。"""

    id: UUID
    mode: Literal["hard_deleted", "history_preserved"]


class PostgresAnalysisSchemeLifecycleRepository:
    """Analysis Scheme 聚合生命周期；删除管理资源时保留必要历史快照。"""

    def __init__(self, session: Session) -> None:
        """绑定调用方拥有的生命周期事务。"""

        self._session = session

    def get_for_update(self, scheme_id: UUID) -> RowMapping | None:
        """锁定仍可由管理员管理的 Scheme 父事实。"""

        return (
            self._session.execute(
                select(analysis_schemes_table)
                .where(
                    analysis_schemes_table.c.id == scheme_id,
                    analysis_schemes_table.c.deleted_at.is_(None),
                )
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
        """当前唯一 active Scheme 不能直接归档，已删除资源视为不存在。"""

        row = (
            self._session.execute(
                select(
                    analysis_schemes_table.c.is_active,
                    analysis_schemes_table.c.archived_at,
                ).where(
                    analysis_schemes_table.c.id == scheme_id,
                    analysis_schemes_table.c.deleted_at.is_(None),
                )
            )
            .mappings()
            .one_or_none()
        )
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
                analysis_schemes_table.c.deleted_at.is_(None),
            )
            .values(archived_at=archived_at, updated_at=func.clock_timestamp())
            .returning(analysis_schemes_table.c.id)
        ).scalar_one_or_none()
        return archived == scheme_id

    def restore(self, scheme_id: UUID) -> bool:
        """恢复未删除的归档 Scheme；保持非 active，必须通过正式发布/回滚再生效。"""

        restored = self._session.execute(
            update(analysis_schemes_table)
            .where(
                analysis_schemes_table.c.id == scheme_id,
                analysis_schemes_table.c.archived_at.is_not(None),
                analysis_schemes_table.c.deleted_at.is_(None),
            )
            .values(archived_at=None, is_active=False, updated_at=func.clock_timestamp())
            .returning(analysis_schemes_table.c.id)
        ).scalar_one_or_none()
        return restored == scheme_id

    def list_archived(self) -> tuple[ArchivedAnalysisSchemeRecord, ...]:
        """仅返回仍可恢复或删除的归档 Scheme。"""

        rows = self._session.execute(
            select(
                analysis_schemes_table.c.id,
                analysis_schemes_table.c.name,
                analysis_schemes_table.c.archived_at,
            )
            .where(
                analysis_schemes_table.c.archived_at.is_not(None),
                analysis_schemes_table.c.deleted_at.is_(None),
            )
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
        """归档且非 active 的可管理 Scheme 均允许从管理视图删除。"""

        row = (
            self._session.execute(
                select(
                    analysis_schemes_table.c.is_active,
                    analysis_schemes_table.c.archived_at,
                ).where(
                    analysis_schemes_table.c.id == scheme_id,
                    analysis_schemes_table.c.deleted_at.is_(None),
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return ("资源不存在",)
        blockers: list[str] = []
        if row["archived_at"] is None:
            blockers.append("请先归档分析方案再执行删除")
        if bool(row["is_active"]):
            blockers.append("当前生效的分析方案不能删除")
        return tuple(dict.fromkeys(blockers))

    def _has_published_history(self, scheme_id: UUID) -> bool:
        """判断 Scheme 是否曾经发布，用于决定是否必须保留版本快照。"""

        return (
            self._session.scalar(
                select(analysis_scheme_versions_table.c.id)
                .where(
                    analysis_scheme_versions_table.c.scheme_id == scheme_id,
                    analysis_scheme_versions_table.c.published_at.is_not(None),
                )
                .limit(1)
            )
            is not None
        )

    def _has_run_history(self, scheme_id: UUID) -> bool:
        """判断是否存在 Analysis Run 直接引用该 Scheme 的任一 Version。"""

        return (
            self._session.scalar(
                select(analysis_content_runs_table.c.id)
                .join(
                    analysis_scheme_versions_table,
                    analysis_scheme_versions_table.c.id
                    == analysis_content_runs_table.c.analysis_scheme_version_id,
                )
                .where(analysis_scheme_versions_table.c.scheme_id == scheme_id)
                .limit(1)
            )
            is not None
        )

    def delete_archived(self, scheme_id: UUID) -> AnalysisSchemeDeletionResult | None:
        """删除归档资源；纯草稿物理删除，历史规则仅从管理视图移除。"""

        archived = self._session.scalar(
            select(analysis_schemes_table.c.id)
            .where(
                analysis_schemes_table.c.id == scheme_id,
                analysis_schemes_table.c.archived_at.is_not(None),
                analysis_schemes_table.c.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if archived is None:
            return None

        blockers = self.delete_blockers(scheme_id)
        if blockers:
            raise RuntimeError("；".join(blockers))

        preserve_history = self._has_published_history(scheme_id) or self._has_run_history(scheme_id)
        if preserve_history:
            deleted_id = self._session.execute(
                update(analysis_schemes_table)
                .where(
                    analysis_schemes_table.c.id == scheme_id,
                    analysis_schemes_table.c.is_active.is_(False),
                    analysis_schemes_table.c.archived_at.is_not(None),
                    analysis_schemes_table.c.deleted_at.is_(None),
                )
                .values(
                    active_version_id=None,
                    deleted_at=func.clock_timestamp(),
                    updated_at=func.clock_timestamp(),
                )
                .returning(analysis_schemes_table.c.id)
            ).scalar_one_or_none()
            if deleted_id is None:
                return None
            return AnalysisSchemeDeletionResult(id=scheme_id, mode="history_preserved")

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
        deleted_id = self._session.execute(
            delete(analysis_schemes_table)
            .where(
                analysis_schemes_table.c.id == scheme_id,
                analysis_schemes_table.c.archived_at.is_not(None),
                analysis_schemes_table.c.deleted_at.is_(None),
            )
            .returning(analysis_schemes_table.c.id)
        ).scalar_one_or_none()
        if deleted_id is None:
            return None
        return AnalysisSchemeDeletionResult(id=scheme_id, mode="hard_deleted")


__all__ = [
    "AnalysisSchemeDeletionResult",
    "ArchivedAnalysisSchemeRecord",
    "PostgresAnalysisSchemeLifecycleRepository",
]
