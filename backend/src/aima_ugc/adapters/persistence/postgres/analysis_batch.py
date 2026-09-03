"""高吞吐 Analysis Shard 的 PostgreSQL 批量结果持久化。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import bindparam, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.analysis import (
    AnalysisRequestNotFound,
    AnalysisRunConfigurationChanged,
    PostgresAnalysisRepository,
    _assert_same_analysis,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.contracts.analysis import ContentLabelAnalysisV3
from aima_ugc.modules.analysis.persistence import (
    AnalysisConfigurationIdentity,
    AnalysisContentResult,
    AnalysisWorkItem,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_label_pairs_table,
    analysis_content_request_items_table,
    analysis_content_requests_table,
    analysis_content_results_table,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.time import beijing_now


@dataclass(frozen=True, slots=True)
class AnalysisSuccessWrite:
    """一条已经完成本地 Validation 的成功 Analysis。"""

    work_item: AnalysisWorkItem
    analysis: ContentLabelAnalysisV3


@dataclass(frozen=True, slots=True)
class AnalysisFailureWrite:
    """一条需要把 pending Request Item 终结为 failed 的结果。"""

    work_item: AnalysisWorkItem
    error_code: str


@dataclass(frozen=True, slots=True)
class AnalysisBatchWriteSummary:
    """一次短事务批量写入后的终态计数。"""

    succeeded: int
    failed: int
    stale: int


class PostgresAnalysisBatchRepository:
    """Analysis 表的高吞吐写入口；一个批次只获取一次 Job Fence。"""

    def __init__(self, session: Session) -> None:
        """复用调用方拥有的短事务 Session。"""

        self._session = session

    def persist_batch(
        self,
        *,
        fence: JobExecutionFence,
        successes: Sequence[AnalysisSuccessWrite],
        failures: Sequence[AnalysisFailureWrite],
    ) -> AnalysisBatchWriteSummary:
        """在一个事务中提交一组已完成结果，同时保持 Fence、版本、配置和幂等约束。"""

        if not successes and not failures:
            return AnalysisBatchWriteSummary(succeeded=0, failed=0, stale=0)

        job = PostgresJobRepository(self._session).lock_current_execution(fence)
        work_items = tuple(item.work_item for item in successes) + tuple(
            item.work_item for item in failures
        )
        self._verify_request_jobs(work_items, job_id=job.id)

        current_versions = self._current_versions(
            tuple(item.work_item.content_id for item in successes)
        )
        succeeded_rows: list[dict[str, object]] = []
        stale_rows: list[dict[str, object]] = []
        label_rows: list[dict[str, object]] = []
        succeeded_count = 0
        stale_count = 0

        for item in successes:
            work_item = item.work_item
            if current_versions.get(work_item.content_id) != work_item.content_version:
                stale_rows.append(
                    {
                        "p_request_id": work_item.request_id,
                        "p_content_id": work_item.content_id,
                    }
                )
                stale_count += 1
                continue
            self._validate_configuration(work_item, item.analysis)
            persisted_id, created = self._persist_result(
                job_id=job.id,
                work_item=work_item,
                analysis=item.analysis,
            )
            succeeded_rows.append(
                {
                    "p_request_id": work_item.request_id,
                    "p_content_id": work_item.content_id,
                    "p_result_id": persisted_id,
                }
            )
            if created:
                result = AnalysisContentResult.from_analysis(
                    result_id=persisted_id,
                    content_id=work_item.content_id,
                    content_version=work_item.content_version,
                    analysis_run_id=work_item.analysis_run_id,
                    job_id=job.id,
                    generation_config_hash=work_item.generation_config_hash,
                    analysis=item.analysis,
                )
                label_rows.extend(
                    {
                        "analysis_result_id": persisted_id,
                        "ordinal": label.ordinal,
                        "primary_label": label.primary_label,
                        "secondary_label": label.secondary_label,
                    }
                    for label in result.labels
                )
            succeeded_count += 1

        if label_rows:
            self._session.execute(insert(analysis_content_label_pairs_table), label_rows)
        self._mark_succeeded(succeeded_rows)
        self._mark_stale(stale_rows)

        failed_rows = [
            {
                "p_request_id": item.work_item.request_id,
                "p_content_id": item.work_item.content_id,
                "p_error_code": item.error_code[:200],
            }
            for item in failures
        ]
        self._mark_failed(failed_rows)
        return AnalysisBatchWriteSummary(
            succeeded=succeeded_count,
            failed=len(failed_rows),
            stale=stale_count,
        )

    def stats(self, request_id: UUID) -> dict[str, int]:
        """由 PostgreSQL 直接按状态聚合一个 Shard，避免把全部 Item 拉回 Python 计数。"""

        counts = {"pending": 0, "succeeded": 0, "failed": 0, "stale": 0}
        rows = self._session.execute(
            select(
                analysis_content_request_items_table.c.status,
                func.count().label("count"),
            )
            .where(analysis_content_request_items_table.c.request_id == request_id)
            .group_by(analysis_content_request_items_table.c.status)
        )
        for status, count in rows:
            counts[cast(str, status)] = cast(int, count)
        return counts

    def _verify_request_jobs(
        self,
        work_items: Sequence[AnalysisWorkItem],
        *,
        job_id: UUID,
    ) -> None:
        """一次查询验证本批所有 Request 都属于当前 Fence 的 Job。"""

        request_ids = tuple(dict.fromkeys(item.request_id for item in work_items))
        rows = dict(
            self._session.execute(
                select(
                    analysis_content_requests_table.c.id,
                    analysis_content_requests_table.c.job_id,
                ).where(analysis_content_requests_table.c.id.in_(request_ids))
            )
        )
        if len(rows) != len(request_ids):
            raise AnalysisRequestNotFound
        if any(rows[request_id] != job_id for request_id in request_ids):
            raise ValueError("Analysis Request 与当前 Job 不匹配")

    def _current_versions(self, content_ids: Sequence[UUID]) -> dict[UUID, int]:
        """一次查询取得本批成功候选的 Current Version。"""

        if not content_ids:
            return {}
        unique_ids = tuple(dict.fromkeys(content_ids))
        return {
            cast(UUID, content_id): cast(int, current_version)
            for content_id, current_version in self._session.execute(
                select(contents_table.c.id, contents_table.c.current_version).where(
                    contents_table.c.id.in_(unique_ids)
                )
            )
        }

    @staticmethod
    def _validate_configuration(
        work_item: AnalysisWorkItem,
        analysis: ContentLabelAnalysisV3,
    ) -> None:
        """新 Run 在写入前再次验证模型结果属于冻结的 Prompt/Taxonomy/Provider/Model。"""

        if not work_item.configuration_enforced:
            return
        actual_identity = AnalysisConfigurationIdentity(
            prompt_version=analysis.prompt_version,
            prompt_sha256=analysis.prompt_sha256,
            taxonomy_sha256=analysis.taxonomy_sha256,
            model_provider=analysis.model_provider,
            model=analysis.model,
        )
        if actual_identity != work_item.configuration_identity:
            raise AnalysisRunConfigurationChanged

    def _persist_result(
        self,
        *,
        job_id: UUID,
        work_item: AnalysisWorkItem,
        analysis: ContentLabelAnalysisV3,
    ) -> tuple[UUID, bool]:
        """插入一条幂等 Result；冲突时复核已有结果语义并复用其 ID。"""

        result = AnalysisContentResult.from_analysis(
            result_id=uuid4(),
            content_id=work_item.content_id,
            content_version=work_item.content_version,
            analysis_run_id=work_item.analysis_run_id,
            job_id=job_id,
            generation_config_hash=work_item.generation_config_hash,
            analysis=analysis,
        )
        created_id = self._session.scalar(
            pg_insert(analysis_content_results_table)
            .values(
                id=result.id,
                content_id=result.content_id,
                content_version=result.content_version,
                analysis_run_id=result.analysis_run_id,
                job_id=result.job_id,
                schema_version=result.schema_version,
                relevance=result.relevance,
                voice_type=result.voice_type,
                sentiment=result.sentiment,
                prompt_version=result.prompt_version,
                prompt_sha256=result.prompt_sha256,
                taxonomy_sha256=result.taxonomy_sha256,
                model_provider=result.model_provider,
                model=result.model,
                input_hash=result.input_hash,
                generation_config_hash=result.generation_config_hash,
                analyzed_at=result.analyzed_at,
                created_at=beijing_now(),
            )
            .on_conflict_do_nothing(constraint="uq_analysis_content_results_identity")
            .returning(analysis_content_results_table.c.id)
        )
        if created_id is not None:
            return cast(UUID, created_id), True
        persisted_id = self._session.scalar(
            select(analysis_content_results_table.c.id).where(
                analysis_content_results_table.c.analysis_run_id == result.analysis_run_id,
                analysis_content_results_table.c.content_id == result.content_id,
                analysis_content_results_table.c.content_version == result.content_version,
            )
        )
        if persisted_id is None:
            raise RuntimeError("Analysis 幂等冲突后找不到已有 Result")
        actual_id = cast(UUID, persisted_id)
        _assert_same_analysis(self._session, actual_id, analysis)
        return actual_id, False

    def _mark_succeeded(self, rows: Sequence[dict[str, object]]) -> None:
        """用 DBAPI executemany 更新本批成功 Request Item。"""

        if not rows:
            return
        statement = (
            update(analysis_content_request_items_table)
            .where(
                analysis_content_request_items_table.c.request_id
                == bindparam("p_request_id"),
                analysis_content_request_items_table.c.content_id
                == bindparam("p_content_id"),
            )
            .values(
                status="succeeded",
                analysis_result_id=bindparam("p_result_id"),
                error_code=None,
            )
        )
        self._session.execute(statement, list(rows))

    def _mark_stale(self, rows: Sequence[dict[str, object]]) -> None:
        """用 DBAPI executemany 标记模型执行期间已经发生版本变化的成功候选。"""

        if not rows:
            return
        statement = (
            update(analysis_content_request_items_table)
            .where(
                analysis_content_request_items_table.c.request_id
                == bindparam("p_request_id"),
                analysis_content_request_items_table.c.content_id
                == bindparam("p_content_id"),
                analysis_content_request_items_table.c.status == "pending",
            )
            .values(status="stale", error_code="content_version_changed")
        )
        self._session.execute(statement, list(rows))

    def _mark_failed(self, rows: Sequence[dict[str, object]]) -> None:
        """用 DBAPI executemany 终结本批已隔离的 Validation/Transport 失败。"""

        if not rows:
            return
        statement = (
            update(analysis_content_request_items_table)
            .where(
                analysis_content_request_items_table.c.request_id
                == bindparam("p_request_id"),
                analysis_content_request_items_table.c.content_id
                == bindparam("p_content_id"),
                analysis_content_request_items_table.c.status == "pending",
            )
            .values(status="failed", error_code=bindparam("p_error_code"))
        )
        self._session.execute(statement, list(rows))


__all__ = [
    "AnalysisBatchWriteSummary",
    "AnalysisFailureWrite",
    "AnalysisSuccessWrite",
    "PostgresAnalysisBatchRepository",
]
