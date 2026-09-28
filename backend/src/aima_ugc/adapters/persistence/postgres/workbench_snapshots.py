"""工作台聚合快照的唯一 PostgreSQL 写入口。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.workbench.tables import workbench_snapshots_table
from aima_ugc.platform.jobs import JobExecutionFence

type WorkbenchSnapshotModule = Literal["mind", "trend"]


@dataclass(frozen=True, slots=True)
class WorkbenchSnapshotRefresh:
    module: WorkbenchSnapshotModule
    query_hash: str
    source_revision: int
    refresh_generation: int
    analysis_scheme_version_id: UUID


class PostgresWorkbenchSnapshotRepository:
    """维护可重建聚合的最近成功结果、目标 revision 和刷新代次。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def current_data_revision(self) -> int:
        """读取 statement trigger 推进的无锁单调修订序列。"""

        return int(
            self._session.scalar(text("SELECT last_value FROM workbench_data_revision_seq")) or 1
        )

    def get(self, *, module: WorkbenchSnapshotModule, query_hash: str) -> RowMapping | None:
        return (
            self._session.execute(
                select(workbench_snapshots_table).where(
                    workbench_snapshots_table.c.module == module,
                    workbench_snapshots_table.c.query_hash == query_hash,
                )
            )
            .mappings()
            .one_or_none()
        )

    def request_refresh(
        self,
        *,
        module: WorkbenchSnapshotModule,
        query_hash: str,
        query: dict[str, object],
        source_revision: int,
        analysis_scheme_version_id: UUID,
    ) -> WorkbenchSnapshotRefresh | None:
        """同一 query/revision/scheme 只创建一个刷新代次，失败后允许新代次重试。"""

        current = (
            self._session.execute(
                select(workbench_snapshots_table)
                .where(
                    workbench_snapshots_table.c.module == module,
                    workbench_snapshots_table.c.query_hash == query_hash,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if (
            current is not None
            and current["status"] == "refreshing"
            and current["target_analysis_scheme_version_id"] == analysis_scheme_version_id
        ):
            # 同一 Scheme 的连续数据写入合并到当前计算之后的一次补算，避免高吞吐导入时
            # 页面轮询不断废弃正在执行的千万级聚合。
            return None

        generation = 1 if current is None else int(current["refresh_generation"]) + 1
        values: dict[str, object] = {
            "module": module,
            "query_hash": query_hash,
            "query": query,
            "target_revision": source_revision,
            "target_analysis_scheme_version_id": analysis_scheme_version_id,
            "refresh_generation": generation,
            "status": "refreshing",
            "last_error_code": None,
            "updated_at": text("clock_timestamp()"),
        }
        self._session.execute(
            pg_insert(workbench_snapshots_table)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[
                    workbench_snapshots_table.c.module,
                    workbench_snapshots_table.c.query_hash,
                ],
                set_={
                    key: value
                    for key, value in values.items()
                    if key not in {"module", "query_hash"}
                },
            )
        )
        return WorkbenchSnapshotRefresh(
            module=module,
            query_hash=query_hash,
            source_revision=source_revision,
            refresh_generation=generation,
            analysis_scheme_version_id=analysis_scheme_version_id,
        )

    def record_success(
        self,
        *,
        refresh: WorkbenchSnapshotRefresh,
        taxonomy_sha256: str,
        response: dict[str, object],
        computed_at: datetime,
        fence: JobExecutionFence | None = None,
    ) -> bool:
        """只有当前刷新代次可提交业务可见结果；Worker 提交前同时锁定 Job Fence。"""

        if fence is not None:
            PostgresJobRepository(self._session).lock_current_execution(fence)
        result = self._session.execute(
            update(workbench_snapshots_table)
            .where(
                workbench_snapshots_table.c.module == refresh.module,
                workbench_snapshots_table.c.query_hash == refresh.query_hash,
                workbench_snapshots_table.c.refresh_generation == refresh.refresh_generation,
                workbench_snapshots_table.c.target_revision == refresh.source_revision,
                workbench_snapshots_table.c.target_analysis_scheme_version_id
                == refresh.analysis_scheme_version_id,
            )
            .values(
                analysis_scheme_version_id=refresh.analysis_scheme_version_id,
                taxonomy_sha256=taxonomy_sha256,
                source_revision=refresh.source_revision,
                status="ready",
                response=response,
                computed_at=computed_at,
                last_error_code=None,
                updated_at=text("clock_timestamp()"),
            )
        )
        return bool(getattr(result, "rowcount", 0))

    def record_failure(self, *, refresh: WorkbenchSnapshotRefresh, error_code: str) -> bool:
        result = self._session.execute(
            update(workbench_snapshots_table)
            .where(
                workbench_snapshots_table.c.module == refresh.module,
                workbench_snapshots_table.c.query_hash == refresh.query_hash,
                workbench_snapshots_table.c.refresh_generation == refresh.refresh_generation,
            )
            .values(
                status="failed",
                last_error_code=error_code[:200],
                updated_at=text("clock_timestamp()"),
            )
        )
        return bool(getattr(result, "rowcount", 0))


def snapshot_refresh_from_payload(payload: object) -> WorkbenchSnapshotRefresh:
    """终态回调只依赖稳定 Payload 字段，不加载业务响应。"""

    item = cast(dict[str, object], payload)
    return WorkbenchSnapshotRefresh(
        module=cast(WorkbenchSnapshotModule, item["module"]),
        query_hash=str(item["query_hash"]),
        source_revision=int(cast(int, item["source_revision"])),
        refresh_generation=int(cast(int, item["refresh_generation"])),
        analysis_scheme_version_id=UUID(str(item["analysis_scheme_version_id"])),
    )


__all__ = [
    "PostgresWorkbenchSnapshotRepository",
    "WorkbenchSnapshotModule",
    "WorkbenchSnapshotRefresh",
    "snapshot_refresh_from_payload",
]
