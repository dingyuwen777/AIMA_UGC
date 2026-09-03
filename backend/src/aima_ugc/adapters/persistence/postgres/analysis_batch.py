"""高吞吐 Analysis Shard 的 PostgreSQL 批量结果持久化。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import bindparam, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.analysis import (
    AnalysisRequestNotFound,
    AnalysisRunConfigurationChanged,
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

_ResultIdentity = tuple[UUID, UUID, int]


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


@dataclass(frozen=True, slots=True)
class _PreparedSuccess:
    """已经通过版本/配置检查并预分配 Result ID 的成功写入项。"""

    work_item: AnalysisWorkItem
    analysis: ContentLabelAnalysisV3
    result: AnalysisContentResult


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
        prepared: list[_PreparedSuccess] = []
        stale_rows: list[dict[str, object]] = []
        for item in successes:
            work_item = item.work_item
            if current_versions.get(work_item.content_id) != work_item.content_version:
                stale_rows.append(
                    {
                        "p_request_id": work_item.request_id,
                        "p_content_id": work_item.content_id,
                    }
                )
                continue
            self._validate_configuration(work_item, item.analysis)
            prepared.append(
                _PreparedSuccess(
                    work_item=work_item,
                    analysis=item.analysis,
                    result=AnalysisContentResult.from_analysis(
                        result_id=uuid4(),
                        content_id=work_item.content_id,
                        content_version=work_item.content_version,
                        analysis_run_id=work_item.analysis_run_id,
                        job_id=job.id,
                        generation_config_hash=work_item.generation_config_hash,
                        analysis=item.analysis,
                    ),
                )
            )

        persisted_ids, created_identities = self._persist_results(prepared)
        self._persist_created_labels(
            prepared,
            persisted_ids=persisted_ids,
            created_identities=created_identities,
        )
        self._verify_conflicted_results(
            prepared,
            persisted_ids=persisted_ids,
            created_identities=created_identities,
        )

        succeeded_rows = [
            {
                "p_request_id": item.work_item.request_id,
                "p_content_id": item.work_item.content_id,
                "p_result_id": persisted_ids[_result_identity(item.work_item)],
            }
            for item in prepared
        ]
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
            succeeded=len(prepared),
            failed=len(failed_rows),
            stale=len(stale_rows),
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

    def _persist_results(
        self,
        prepared: Sequence[_PreparedSuccess],
    ) -> tuple[dict[_ResultIdentity, UUID], set[_ResultIdentity]]:
        """一次多行 INSERT 提交成功 Result，并一次查询补齐幂等冲突对应的已有 ID。"""

        if not prepared:
            return {}, set()
        created_at = beijing_now()
        result_rows = [
            {
                "id": item.result.id,
                "content_id": item.result.content_id,
                "content_version": item.result.content_version,
                "analysis_run_id": item.result.analysis_run_id,
                "job_id": item.result.job_id,
                "schema_version": item.result.schema_version,
                "relevance": item.result.relevance,
                "voice_type": item.result.voice_type,
                "sentiment": item.result.sentiment,
                "prompt_version": item.result.prompt_version,
                "prompt_sha256": item.result.prompt_sha256,
                "taxonomy_sha256": item.result.taxonomy_sha256,
                "model_provider": item.result.model_provider,
                "model": item.result.model,
                "input_hash": item.result.input_hash,
                "generation_config_hash": item.result.generation_config_hash,
                "analyzed_at": item.result.analyzed_at,
                "created_at": created_at,
            }
            for item in prepared
        ]
        created_rows = tuple(
            self._session.execute(
                pg_insert(analysis_content_results_table)
                .values(result_rows)
                .on_conflict_do_nothing(constraint="uq_analysis_content_results_identity")
                .returning(
                    analysis_content_results_table.c.id,
                    analysis_content_results_table.c.analysis_run_id,
                    analysis_content_results_table.c.content_id,
                    analysis_content_results_table.c.content_version,
                )
            ).mappings()
        )
        persisted_ids = {
            _row_identity(row): cast(UUID, row["id"])
            for row in created_rows
        }
        created_identities = set(persisted_ids)

        missing = {
            _result_identity(item.work_item)
            for item in prepared
            if _result_identity(item.work_item) not in persisted_ids
        }
        if missing:
            run_ids = tuple({identity[0] for identity in missing})
            content_ids = tuple({identity[1] for identity in missing})
            versions = tuple({identity[2] for identity in missing})
            existing_rows = self._session.execute(
                select(
                    analysis_content_results_table.c.id,
                    analysis_content_results_table.c.analysis_run_id,
                    analysis_content_results_table.c.content_id,
                    analysis_content_results_table.c.content_version,
                ).where(
                    analysis_content_results_table.c.analysis_run_id.in_(run_ids),
                    analysis_content_results_table.c.content_id.in_(content_ids),
                    analysis_content_results_table.c.content_version.in_(versions),
                )
            ).mappings()
            for row in existing_rows:
                identity = _row_identity(row)
                if identity in missing:
                    persisted_ids[identity] = cast(UUID, row["id"])
        unresolved = missing.difference(persisted_ids)
        if unresolved:
            raise RuntimeError("Analysis 批量幂等冲突后找不到已有 Result")
        return persisted_ids, created_identities

    def _persist_created_labels(
        self,
        prepared: Sequence[_PreparedSuccess],
        *,
        persisted_ids: dict[_ResultIdentity, UUID],
        created_identities: set[_ResultIdentity],
    ) -> None:
        """仅为本事务新建 Result 批量插入标签，幂等冲突不重复写 Label Pair。"""

        label_rows: list[dict[str, object]] = []
        for item in prepared:
            identity = _result_identity(item.work_item)
            if identity not in created_identities:
                continue
            result_id = persisted_ids[identity]
            label_rows.extend(
                {
                    "analysis_result_id": result_id,
                    "ordinal": label.ordinal,
                    "primary_label": label.primary_label,
                    "secondary_label": label.secondary_label,
                }
                for label in item.result.labels
            )
        if label_rows:
            self._session.execute(insert(analysis_content_label_pairs_table), label_rows)

    def _verify_conflicted_results(
        self,
        prepared: Sequence[_PreparedSuccess],
        *,
        persisted_ids: dict[_ResultIdentity, UUID],
        created_identities: set[_ResultIdentity],
    ) -> None:
        """批量复核冲突 Result 的业务值和标签，保持原有幂等冲突 fail-closed 语义。"""

        conflicted = [
            item
            for item in prepared
            if _result_identity(item.work_item) not in created_identities
        ]
        if not conflicted:
            return
        result_ids = tuple(
            persisted_ids[_result_identity(item.work_item)] for item in conflicted
        )
        result_rows = {
            cast(UUID, row["id"]): row
            for row in self._session.execute(
                select(
                    analysis_content_results_table.c.id,
                    analysis_content_results_table.c.schema_version,
                    analysis_content_results_table.c.relevance,
                    analysis_content_results_table.c.voice_type,
                    analysis_content_results_table.c.sentiment,
                ).where(analysis_content_results_table.c.id.in_(result_ids))
            ).mappings()
        }
        labels_by_result: dict[UUID, list[tuple[str, str]]] = {result_id: [] for result_id in result_ids}
        for result_id, primary_label, secondary_label in self._session.execute(
            select(
                analysis_content_label_pairs_table.c.analysis_result_id,
                analysis_content_label_pairs_table.c.primary_label,
                analysis_content_label_pairs_table.c.secondary_label,
            )
            .where(analysis_content_label_pairs_table.c.analysis_result_id.in_(result_ids))
            .order_by(
                analysis_content_label_pairs_table.c.analysis_result_id,
                analysis_content_label_pairs_table.c.ordinal,
            )
        ):
            labels_by_result[cast(UUID, result_id)].append(
                (cast(str, primary_label), cast(str, secondary_label))
            )

        for item in conflicted:
            result_id = persisted_ids[_result_identity(item.work_item)]
            row = result_rows.get(result_id)
            if row is None:
                raise RuntimeError("Analysis 幂等 Result 复核时记录不存在")
            actual = (
                row["schema_version"],
                row["relevance"],
                row["voice_type"],
                row["sentiment"],
            )
            expected = (
                item.analysis.schema_version,
                item.analysis.relevance,
                item.analysis.voice_type,
                item.analysis.sentiment,
            )
            if actual != expected:
                raise ValueError("Analysis 幂等身份对应的相关性/发声类型/情感不一致")
            expected_labels = [
                (label.primary_label, label.secondary_label) for label in item.analysis.labels
            ]
            if labels_by_result[result_id] != expected_labels:
                raise ValueError("Analysis 幂等身份对应的标签集合不一致")

    def _mark_succeeded(self, rows: Sequence[dict[str, object]]) -> None:
        """用 DBAPI executemany 更新本批成功 Request Item。"""

        if not rows:
            return
        statement = (
            update(analysis_content_request_items_table)
            .where(
                analysis_content_request_items_table.c.request_id == bindparam("p_request_id"),
                analysis_content_request_items_table.c.content_id == bindparam("p_content_id"),
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
                analysis_content_request_items_table.c.request_id == bindparam("p_request_id"),
                analysis_content_request_items_table.c.content_id == bindparam("p_content_id"),
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
                analysis_content_request_items_table.c.request_id == bindparam("p_request_id"),
                analysis_content_request_items_table.c.content_id == bindparam("p_content_id"),
                analysis_content_request_items_table.c.status == "pending",
            )
            .values(status="failed", error_code=bindparam("p_error_code"))
        )
        self._session.execute(statement, list(rows))


def _result_identity(work_item: AnalysisWorkItem) -> _ResultIdentity:
    """返回 Analysis Result 的数据库幂等身份。"""

    return (
        work_item.analysis_run_id,
        work_item.content_id,
        work_item.content_version,
    )


def _row_identity(row: RowMapping) -> _ResultIdentity:
    """从 PostgreSQL Result 行恢复幂等身份。"""

    return (
        cast(UUID, row["analysis_run_id"]),
        cast(UUID, row["content_id"]),
        cast(int, row["content_version"]),
    )


__all__ = [
    "AnalysisBatchWriteSummary",
    "AnalysisFailureWrite",
    "AnalysisSuccessWrite",
    "PostgresAnalysisBatchRepository",
]
