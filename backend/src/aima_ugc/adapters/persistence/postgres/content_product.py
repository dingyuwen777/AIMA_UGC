"""Content Owner 的 Count 与第三方可用状态写入。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from aima_ugc.contracts.http import ContentFilterSnapshot
from aima_ugc.contracts.product import ContentAvailabilityObservationRequest
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity
from aima_ugc.modules.content.availability_tables import (
    content_availability_observations_table,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.time import beijing_now

from .content_queries import PostgresContentQueryRepository


class PostgresContentProductRepository:
    """内容产品能力继续走 Content Owner 表与查询链。"""

    def __init__(
        self,
        session: Session,
        *,
        analysis_identity: AnalysisConfigurationIdentity | None,
    ) -> None:
        """绑定 Content 查询事务与当前 Analysis 身份。"""

        self._session = session
        self._queries = PostgresContentQueryRepository(session, analysis_identity=analysis_identity)

    def exact_count(self, filters: ContentFilterSnapshot, *, limit: int) -> tuple[int, bool]:
        """扫描至上限加一，返回范围内数量和是否被截断。"""

        statement, _ = self._queries._base_statement(filters, targets_only=True)  # noqa: SLF001
        rows = tuple(self._session.scalars(select(statement.subquery().c.id).limit(limit + 1)))
        return min(len(rows), limit), len(rows) > limit

    def estimated_count(self, filters: ContentFilterSnapshot) -> int | None:
        """首版仅对无筛选全表返回 PostgreSQL 统计估算，避免伪造条件估算。"""

        if filters != ContentFilterSnapshot():
            return None
        value = self._session.scalar(
            text(
                "SELECT GREATEST(reltuples::bigint, 0) FROM pg_class WHERE oid='contents'::regclass"
            )
        )
        return None if value is None else max(int(value), 0)

    def append_availability(
        self,
        request: ContentAvailabilityObservationRequest,
    ) -> tuple[int, datetime]:
        """锁定当前内容并追加一条带内容版本的可用状态观察。"""

        current_version = self._session.scalar(
            select(contents_table.c.current_version)
            .where(contents_table.c.id == request.content_id)
            .with_for_update()
        )
        if current_version is None:
            raise LookupError(request.content_id)
        observed_at = beijing_now()
        self._session.execute(
            insert(content_availability_observations_table).values(
                id=uuid4(),
                content_id=request.content_id,
                content_version=int(current_version),
                status=request.status,
                reason_code=request.reason_code,
                evidence_kind=request.evidence_kind,
                provider_attempt_id=request.provider_attempt_id,
                raw_artifact_id=request.raw_artifact_id,
                safe_summary=request.safe_summary,
                observed_at=observed_at,
            )
        )
        return cast(int, current_version), observed_at


__all__ = ["PostgresContentProductRepository"]
