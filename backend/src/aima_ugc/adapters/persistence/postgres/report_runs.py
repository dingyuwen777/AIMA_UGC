"""报告 Owner：冻结一致读数据、产物关联与独立恢复断点。"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.analysis_effective import load_effective_analysis
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.reporting import PostgresDataExportRepository
from aima_ugc.contracts.export import UnifiedDataExcelV1
from aima_ugc.modules.content.tables import accounts_table, contents_table
from aima_ugc.modules.reporting.report_tables import (
    report_artifacts_table,
    report_items_table,
    report_runs_table,
)
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage.tables import artifacts_table
from aima_ugc.platform.time import beijing_now


class ReportNotFound(LookupError):
    """报告不存在。"""


class PostgresReportRepository:
    """报告表唯一写入口；所有事务由调用方控制。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, values: dict[str, Any]) -> None:
        """与生成 Job 在同一 Unit of Work 中建立父事实。"""
        self._session.execute(insert(report_runs_table).values(**values))

    def get(self, report_id: UUID, *, lock: bool = False) -> RowMapping:
        """需要排他更新时锁定报告，防止重复生成和发布。"""
        statement = select(report_runs_table).where(report_runs_table.c.id == report_id)
        if lock:
            statement = statement.with_for_update()
        row = self._session.execute(statement).mappings().one_or_none()
        if row is None:
            raise ReportNotFound
        return row

    def list_recent(self, *, limit: int = 50) -> tuple[RowMapping, ...]:
        """返回有界历史，保留过期报告的审计身份。"""
        return tuple(
            self._session.execute(
                select(report_runs_table)
                .order_by(
                    report_runs_table.c.created_at.desc(),
                    report_runs_table.c.id.desc(),
                )
                .limit(limit)
            ).mappings()
        )

    def freeze(self, report_id: UUID, period: str, target: Any) -> dict[str, int]:
        """在调用方 REPEATABLE READ 事务中冻结正文、评论、指标及实际分析身份。"""
        selected = target.subquery("report_targets")
        projection = select(
            selected.c.content_id,
            selected.c.content_version,
            selected.c.target_ordinal.label("ordinal"),
        )
        counts = {"content_count": 0, "analyzed_count": 0, "real_user_count": 0, "comment_count": 0}
        after = -1
        reader = PostgresDataExportRepository(self._session)
        while page := reader.load_target_page(projection, after_ordinal=after, limit=200):
            identities = tuple(
                self._session.execute(
                    projection.where(
                        selected.c.target_ordinal > after,
                    )
                    .order_by(selected.c.target_ordinal)
                    .limit(200)
                ).mappings()
            )
            by_ordinal = {row["ordinal"]: row for row in identities}
            basis = self._analysis_basis(
                {row["content_id"]: row["content_version"] for row in identities}
            )
            followers = dict(
                self._session.execute(
                    select(contents_table.c.id, accounts_table.c.current_follower_count)
                    .join(accounts_table, accounts_table.c.id == contents_table.c.author_account_id)
                    .where(contents_table.c.id.in_(tuple(row["content_id"] for row in identities)))
                )
                .tuples()
                .all()
            )
            values = []
            for ordinal, record in page:
                identity = by_ordinal[ordinal]
                # 使用该版本已有的有效证据标准名称；不重扫正文，重复别名只计一个名称。
                content_updates: dict[str, Any] = {
                    "matched_keywords": tuple(
                        dict.fromkeys((*record.content.brands, *record.content.vehicles))
                    )
                }
                # 作者最新已知粉丝数属于指标；正文版本中的作者信息仍保持冻结版本。
                follower_count = followers.get(identity["content_id"])
                if follower_count is not None:
                    content_updates["author_follower_count"] = follower_count
                record = record.model_copy(
                    update={"content": record.content.model_copy(update=content_updates)}
                )
                values.append(
                    {
                        "report_run_id": report_id,
                        "period": period,
                        "ordinal": ordinal,
                        "content_id": identity["content_id"],
                        "content_version": identity["content_version"],
                        "data": record.model_dump(mode="json"),
                        "analysis_basis": basis.get(identity["content_id"], {}),
                    }
                )
                counts["content_count"] += 1
                counts["comment_count"] += len(record.comments)
                if record.content.analysis is not None:
                    counts["analyzed_count"] += 1
                    counts["real_user_count"] += (
                        record.content.analysis.voice_type == "真实用户发声"
                    )
            self._session.execute(insert(report_items_table), values)
            after = page[-1][0]
        expected = self._session.scalar(select(func.count()).select_from(selected))
        if counts["content_count"] != expected:
            raise ValueError("报告目标存在不可投影的数据，不能静默遗漏")
        return counts

    def load_records(self, report_id: UUID, period: str) -> tuple[UnifiedDataExcelV1, ...]:
        """仅消费冻结数据，重试不读取当前 Content、评论或模型结果。"""
        rows = self._session.scalars(
            select(report_items_table.c.data)
            .where(
                report_items_table.c.report_run_id == report_id,
                report_items_table.c.period == period,
            )
            .order_by(report_items_table.c.ordinal)
        )
        return tuple(UnifiedDataExcelV1.model_validate(row) for row in rows)

    def summarize_analysis_bases(self, report_id: UUID) -> list[dict[str, Any]]:
        """从冻结项目汇总历史分析依据，避免查询历史时重新解释当前配置。"""
        basis = report_items_table.c.analysis_basis
        columns = [report_items_table.c.period]
        for source, target in (
            ("analysis_scheme_version_id", "scheme_version_id"),
            ("prompt_version", "prompt_version"),
            ("prompt_sha256", "prompt_sha256"),
            ("taxonomy_sha256", "taxonomy_sha256"),
            ("model_provider", "provider"),
            ("model", "model"),
        ):
            columns.append(basis[source].astext.label(target))
        statement = (
            select(
                *columns,
                func.count().label("content_count"),
                func.count()
                # 缺键和冻结的 JSON null 都不代表人工操作；解锁对象仍是历史审核事实。
                .filter(func.jsonb_typeof(basis["manual_override"]) == "object")
                .label("manual_override_count"),
            )
            .where(report_items_table.c.report_run_id == report_id, basis != {})
            .group_by(*columns)
            .order_by(*columns)
        )
        return [dict(row) for row in self._session.execute(statement).mappings()]

    def artifacts(self, report_id: UUID) -> tuple[RowMapping, ...]:
        """读取所属文件及 Platform 元数据，保持单一字节事实源。"""
        return tuple(
            self._session.execute(
                select(
                    report_artifacts_table.c.artifact_type,
                    report_artifacts_table.c.filename,
                    artifacts_table,
                )
                .select_from(
                    report_artifacts_table.join(
                        artifacts_table,
                        artifacts_table.c.id == report_artifacts_table.c.artifact_id,
                    )
                )
                .where(report_artifacts_table.c.report_run_id == report_id)
                .order_by(report_artifacts_table.c.filename)
            ).mappings()
        )

    def update_job(self, report_id: UUID, *, kind: str, job_id: UUID) -> None:
        """HTTP 锁定报告后绑定新的恢复任务。"""
        column = "generation_job_id" if kind == "generation" else "publication_job_id"
        self._session.execute(
            update(report_runs_table)
            .where(
                report_runs_table.c.id == report_id,
            )
            .values(**{column: job_id})
        )

    def checkpoint(
        self, report_id: UUID, fence: JobExecutionFence, *, kind: str, values: dict[str, Any]
    ) -> None:
        """每个外部成功结果立即在当前 fence 下保存，跨重试复用。"""
        self.validate_execution(report_id, fence, kind)
        self._session.execute(
            update(report_runs_table)
            .where(
                report_runs_table.c.id == report_id,
            )
            .values(**{f"{kind}_checkpoint": values})
        )

    def complete(
        self,
        report_id: UUID,
        fence: JobExecutionFence,
        *,
        files: tuple[tuple[UUID, str, str], ...],
        result: dict[str, Any],
        retention_days: int,
    ) -> None:
        """完整文件集合与生成结果原子提交；失败产生的孤儿由原清理器回收。"""
        self.validate_execution(report_id, fence, "generation")
        if self.get(report_id)["completed_at"] is not None:
            return
        completed = beijing_now()
        expiry = completed + timedelta(days=retention_days)
        metadata = PostgresArtifactMetadataRepository(self._session)
        for artifact_id, artifact_type, filename in files:
            self._session.execute(
                insert(report_artifacts_table).values(
                    report_run_id=report_id,
                    artifact_id=artifact_id,
                    artifact_type=artifact_type,
                    filename=filename,
                )
            )
            metadata.mark_linked(artifact_id, linked_at=completed)
            metadata.set_report_expiry(artifact_id, expires_at=expiry)
        self._session.execute(
            update(report_runs_table)
            .where(
                report_runs_table.c.id == report_id,
            )
            .values(completed_at=completed, expires_at=expiry, generation_result=result)
        )

    def validate_execution(self, report_id: UUID, fence: JobExecutionFence, kind: str) -> None:
        """拒绝失效 Worker、已取消任务及与当前报告无关的 Job。"""
        row = self.get(report_id, lock=True)
        # HTTP 恢复/取消同样先锁报告再锁 Job，避免相反锁序造成死锁。
        PostgresJobRepository(self._session).lock_current_execution(fence)
        if row[f"{kind}_job_id"] != fence.job_id:
            raise ValueError("报告 Job 身份不匹配")

    def _analysis_basis(self, versions: dict[UUID, int]) -> dict[UUID, dict[str, Any]]:
        """记录冻结目标及真实来源，历史模型和人工操作不会冒充新执行。"""
        result_map = {}
        for content_id, row in load_effective_analysis(self._session, versions).items():
            result_map[content_id] = json.loads(json.dumps(dict(row), default=str))
        return result_map
