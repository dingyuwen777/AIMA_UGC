"""Stage 8D Analysis Request、Result 与有序标签 PostgreSQL Owner Adapter。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, TypeAdapter
from sqlalchemy import (
    BigInteger,
    Integer,
    Uuid,
    func,
    insert,
    literal,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.contracts.analysis import ContentLabelAnalysisV3
from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.contracts.platform import require_platform_name
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
    analysis_content_run_targets_table,
    analysis_content_runs_table,
)
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.query import ContentTarget
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.time import beijing_now

_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


class AnalysisRequestNotFound(LookupError):
    pass


class AnalysisRunStateConflict(RuntimeError):
    pass


class AnalysisRunConfigurationChanged(RuntimeError):
    pass


class PostgresAnalysisRepository:
    """Analysis 表唯一写入口；所有业务可见提交验证当前 Job Fence。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_run_by_client_key(self, client_idempotency_key: str) -> RowMapping | None:
        return (
            self._session.execute(
                select(analysis_content_runs_table).where(
                    analysis_content_runs_table.c.client_idempotency_key == client_idempotency_key
                )
            )
            .mappings()
            .one_or_none()
        )

    def count_targets(self, target_statement: Any) -> int:
        targets = target_statement.subquery("analysis_count_targets")
        return cast(int, self._session.scalar(select(func.count()).select_from(targets)) or 0)

    def create_run_header(
        self,
        *,
        run_id: UUID,
        client_idempotency_key: str,
        planner_job_id: UUID,
        run_intent: str,
        scope: str,
        filter_snapshot: dict[str, object],
        target_count: int,
        shard_count: int,
        shard_size: int,
        identity: AnalysisConfigurationIdentity,
        generation_config: dict[str, object],
        generation_config_hash: str,
        analysis_scheme_version_id: UUID | None = None,
        prompt_text_snapshot: str | None = None,
    ) -> RowMapping | None:
        return (
            self._session.execute(
                pg_insert(analysis_content_runs_table)
                .values(
                    id=run_id,
                    client_idempotency_key=client_idempotency_key,
                    planner_job_id=planner_job_id,
                    run_intent=run_intent,
                    scope=scope,
                    filter_snapshot=filter_snapshot,
                    status="queued",
                    target_count=target_count,
                    shard_count=shard_count,
                    shard_size=shard_size,
                    prompt_version=identity.prompt_version,
                    analysis_scheme_version_id=analysis_scheme_version_id,
                    prompt_text_snapshot=prompt_text_snapshot,
                    prompt_sha256=identity.prompt_sha256,
                    taxonomy_sha256=identity.taxonomy_sha256,
                    model_provider=identity.model_provider,
                    model=identity.model,
                    generation_config=generation_config,
                    generation_config_hash=generation_config_hash,
                    created_at=beijing_now(),
                )
                .on_conflict_do_nothing(
                    constraint="uq_analysis_content_runs_client_idempotency_key"
                )
                .returning(analysis_content_runs_table)
            )
            .mappings()
            .one_or_none()
        )

    def freeze_run_targets(
        self,
        *,
        run_id: UUID,
        target_statement: Any,
    ) -> int:
        """用一次 `INSERT ... SELECT` 冻结 Run 的全部 Content ID + Version。"""

        target = target_statement.subquery("analysis_run_targets")
        self._session.execute(
            insert(analysis_content_run_targets_table).from_select(
                ("run_id", "target_ordinal", "content_id", "content_version"),
                select(
                    literal(run_id, type_=Uuid()),
                    target.c.target_ordinal.cast(BigInteger),
                    target.c.content_id,
                    target.c.content_version,
                ),
            )
        )
        return cast(
            int,
            self._session.scalar(
                select(func.count()).where(analysis_content_run_targets_table.c.run_id == run_id)
            )
            or 0,
        )

    def frozen_target_count(self, run_id: UUID) -> int:
        """返回已由 Planner 原子冻结的目标数，供 Lease 重试判定幂等状态。"""

        return cast(
            int,
            self._session.scalar(
                select(func.count()).where(analysis_content_run_targets_table.c.run_id == run_id)
            )
            or 0,
        )

    def next_unscheduled_shards(self, run_id: UUID, *, limit: int) -> tuple[int, ...]:
        if limit <= 0:
            return ()
        run = analysis_content_runs_table
        target = analysis_content_run_targets_table
        request = analysis_content_requests_table
        shard_no = func.floor(target.c.target_ordinal / run.c.shard_size).cast(Integer)
        scheduled = select(request.c.id).where(
            request.c.run_id == run_id,
            request.c.shard_no == shard_no,
        )
        return tuple(
            value
            for value in self._session.execute(
                select(shard_no.label("shard_no"))
                .select_from(target.join(run, run.c.id == target.c.run_id))
                .where(
                    target.c.run_id == run_id,
                    ~scheduled.exists(),
                    run.c.cancel_requested_at.is_(None),
                )
                .distinct()
                .order_by(shard_no)
                .limit(limit)
            ).scalars()
        )

    def active_shard_count(self, run_id: UUID) -> int:
        return cast(
            int,
            self._session.scalar(
                select(func.count())
                .select_from(
                    analysis_content_requests_table.join(
                        jobs_table,
                        jobs_table.c.id == analysis_content_requests_table.c.job_id,
                    )
                )
                .where(
                    analysis_content_requests_table.c.run_id == run_id,
                    jobs_table.c.status.in_(("queued", "running")),
                )
            )
            or 0,
        )

    def create_run_shard(
        self,
        *,
        run_id: UUID,
        request_id: UUID,
        job_id: UUID,
        shard_no: int,
    ) -> int:
        """创建一个有界 Shard，并从冻结目标集合式填充其 Item。"""

        run = self.get_run(run_id, for_update=True)
        if run is None:
            raise AnalysisRequestNotFound
        shard_size = cast(int, run["shard_size"])
        start_ordinal = shard_no * shard_size
        end_ordinal = start_ordinal + shard_size
        target = analysis_content_run_targets_table
        target_count = cast(
            int,
            self._session.scalar(
                select(func.count()).where(
                    target.c.run_id == run_id,
                    target.c.target_ordinal >= start_ordinal,
                    target.c.target_ordinal < end_ordinal,
                )
            )
            or 0,
        )
        if target_count == 0:
            raise ValueError("Analysis Shard 没有冻结目标")
        self._session.execute(
            insert(analysis_content_requests_table).values(
                id=request_id,
                run_id=run_id,
                shard_no=shard_no,
                job_id=job_id,
                scope=run["scope"],
                filter_snapshot=run["filter_snapshot"],
                target_count=target_count,
                created_at=beijing_now(),
            )
        )
        self._session.execute(
            insert(analysis_content_request_items_table).from_select(
                (
                    "request_id",
                    "content_id",
                    "content_version",
                    "ordinal",
                    "status",
                ),
                select(
                    literal(request_id, type_=Uuid()),
                    target.c.content_id,
                    target.c.content_version,
                    (target.c.target_ordinal - start_ordinal).cast(Integer),
                    literal("pending"),
                ).where(
                    target.c.run_id == run_id,
                    target.c.target_ordinal >= start_ordinal,
                    target.c.target_ordinal < end_ordinal,
                ),
            )
        )
        return target_count

    def create_request(
        self,
        *,
        request_id: UUID,
        run_id: UUID,
        shard_no: int,
        job_id: UUID,
        scope: str,
        filter_snapshot: dict[str, object],
        targets: tuple[ContentTarget, ...],
    ) -> None:
        if not targets:
            raise ValueError("Analysis Request 至少需要一个目标")
        self._session.execute(
            insert(analysis_content_requests_table).values(
                id=request_id,
                run_id=run_id,
                shard_no=shard_no,
                job_id=job_id,
                scope=scope,
                filter_snapshot=filter_snapshot,
                target_count=len(targets),
                created_at=beijing_now(),
            )
        )
        self._session.execute(
            insert(analysis_content_request_items_table),
            [
                {
                    "request_id": request_id,
                    "content_id": target.content_id,
                    "content_version": target.content_version,
                    "ordinal": ordinal,
                    "status": "pending",
                }
                for ordinal, target in enumerate(targets)
            ],
        )

    def load_pending(self, request_id: UUID, *, limit: int) -> tuple[AnalysisWorkItem, ...]:
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        request = analysis_content_requests_table
        item = analysis_content_request_items_table
        content = contents_table
        version = content_versions_table
        attempt = provider_request_attempts_table
        provider_request = provider_requests_table
        rows = tuple(
            self._session.execute(
                select(
                    request.c.id.label("request_id"),
                    request.c.run_id.label("analysis_run_id"),
                    analysis_content_runs_table.c.client_idempotency_key,
                    analysis_content_runs_table.c.prompt_version,
                    analysis_content_runs_table.c.prompt_sha256,
                    analysis_content_runs_table.c.taxonomy_sha256,
                    analysis_content_runs_table.c.model_provider,
                    analysis_content_runs_table.c.model,
                    analysis_content_runs_table.c.generation_config_hash,
                    item.c.ordinal,
                    item.c.content_id,
                    item.c.content_version,
                    content.c.current_version,
                    content.c.platform,
                    content.c.external_content_id,
                    version.c.content_type,
                    version.c.title,
                    version.c.text,
                    version.c.canonical_url,
                    version.c.share_url,
                    version.c.author_snapshot,
                    version.c.published_at,
                    version.c.source_updated_at,
                    version.c.status.label("content_status"),
                    version.c.observed_at,
                    version.c.provider_attempt_id,
                    version.c.raw_artifact_id,
                    provider_request.c.provider,
                    provider_request.c.operation,
                    provider_request.c.id.label("provider_request_id"),
                )
                .select_from(
                    request.join(item, item.c.request_id == request.c.id)
                    .join(
                        analysis_content_runs_table,
                        analysis_content_runs_table.c.id == request.c.run_id,
                    )
                    .join(content, content.c.id == item.c.content_id)
                    .join(
                        version,
                        (version.c.content_id == item.c.content_id)
                        & (version.c.version_no == item.c.content_version),
                    )
                    .join(attempt, attempt.c.id == version.c.provider_attempt_id)
                    .join(
                        provider_request,
                        provider_request.c.id == attempt.c.provider_request_id,
                    )
                )
                .where(
                    request.c.id == request_id,
                    item.c.status == "pending",
                )
                .order_by(item.c.ordinal)
                .limit(limit)
            ).mappings()
        )
        if not rows:
            request_exists = self._session.scalar(
                select(request.c.id).where(request.c.id == request_id)
            )
            if request_exists is None:
                raise AnalysisRequestNotFound
            return ()

        work: list[AnalysisWorkItem] = []
        for row in rows:
            if row["current_version"] != row["content_version"]:
                self._session.execute(
                    update(item)
                    .where(
                        item.c.request_id == request_id,
                        item.c.content_id == row["content_id"],
                        item.c.status == "pending",
                    )
                    .values(status="stale", error_code="content_version_changed")
                )
                continue
            work.append(_row_to_work_item(row))
        return tuple(work)

    def persist_success(
        self,
        *,
        fence: JobExecutionFence,
        work_item: AnalysisWorkItem,
        analysis: ContentLabelAnalysisV3,
    ) -> AnalysisContentResult | None:
        job = PostgresJobRepository(self._session).lock_current_execution(fence)
        request_job_id = self._session.scalar(
            select(analysis_content_requests_table.c.job_id).where(
                analysis_content_requests_table.c.id == work_item.request_id
            )
        )
        if request_job_id is None:
            raise AnalysisRequestNotFound
        if request_job_id != job.id:
            raise ValueError("Analysis Request 与当前 Job 不匹配")
        current_version = self._session.scalar(
            select(contents_table.c.current_version).where(
                contents_table.c.id == work_item.content_id
            )
        )
        if current_version != work_item.content_version:
            self._session.execute(
                update(analysis_content_request_items_table)
                .where(
                    analysis_content_request_items_table.c.request_id == work_item.request_id,
                    analysis_content_request_items_table.c.content_id == work_item.content_id,
                    analysis_content_request_items_table.c.status == "pending",
                )
                .values(status="stale", error_code="content_version_changed")
            )
            return None

        if work_item.configuration_enforced:
            actual_identity = AnalysisConfigurationIdentity(
                prompt_version=analysis.prompt_version,
                prompt_sha256=analysis.prompt_sha256,
                taxonomy_sha256=analysis.taxonomy_sha256,
                model_provider=analysis.model_provider,
                model=analysis.model,
            )
            if actual_identity != work_item.configuration_identity:
                raise AnalysisRunConfigurationChanged

        result = AnalysisContentResult.from_analysis(
            result_id=uuid4(),
            content_id=work_item.content_id,
            content_version=work_item.content_version,
            analysis_run_id=work_item.analysis_run_id,
            job_id=job.id,
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
            if result.labels:
                self._session.execute(
                    insert(analysis_content_label_pairs_table),
                    [
                        {
                            "analysis_result_id": created_id,
                            "ordinal": label.ordinal,
                            "primary_label": label.primary_label,
                            "secondary_label": label.secondary_label,
                        }
                        for label in result.labels
                    ],
                )
            persisted_id = cast(UUID, created_id)
        else:
            persisted_id = cast(
                UUID,
                self._session.scalar(
                    select(analysis_content_results_table.c.id).where(
                        analysis_content_results_table.c.analysis_run_id == result.analysis_run_id,
                        analysis_content_results_table.c.content_id == result.content_id,
                        analysis_content_results_table.c.content_version == result.content_version,
                    )
                ),
            )
            _assert_same_analysis(self._session, persisted_id, analysis)

        self._session.execute(
            update(analysis_content_request_items_table)
            .where(
                analysis_content_request_items_table.c.request_id == work_item.request_id,
                analysis_content_request_items_table.c.content_id == work_item.content_id,
            )
            .values(
                status="succeeded",
                analysis_result_id=persisted_id,
                error_code=None,
            )
        )
        return AnalysisContentResult.from_analysis(
            result_id=persisted_id,
            content_id=work_item.content_id,
            content_version=work_item.content_version,
            analysis_run_id=work_item.analysis_run_id,
            job_id=job.id,
            generation_config_hash=work_item.generation_config_hash,
            analysis=analysis,
        )

    def mark_failed(
        self,
        *,
        fence: JobExecutionFence,
        request_id: UUID,
        content_id: UUID,
        error_code: str,
    ) -> None:
        PostgresJobRepository(self._session).lock_current_execution(fence)
        self._session.execute(
            update(analysis_content_request_items_table)
            .where(
                analysis_content_request_items_table.c.request_id == request_id,
                analysis_content_request_items_table.c.content_id == content_id,
                analysis_content_request_items_table.c.status == "pending",
            )
            .values(status="failed", error_code=error_code[:200])
        )

    def stats(self, request_id: UUID) -> dict[str, int]:
        statuses = self._session.execute(
            select(
                analysis_content_request_items_table.c.status,
                analysis_content_request_items_table.c.content_id,
            ).where(analysis_content_request_items_table.c.request_id == request_id)
        )
        counts = {"pending": 0, "succeeded": 0, "failed": 0, "stale": 0}
        for status, _ in statuses:
            counts[cast(str, status)] += 1
        return counts

    def get_run(self, run_id: UUID, *, for_update: bool = False) -> RowMapping | None:
        statement = select(analysis_content_runs_table).where(
            analysis_content_runs_table.c.id == run_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.execute(statement).mappings().one_or_none()

    def list_runs(self, *, limit: int = 50) -> tuple[RowMapping, ...]:
        return tuple(
            self._session.execute(
                select(analysis_content_runs_table)
                .order_by(analysis_content_runs_table.c.sequence_no.desc())
                .limit(limit)
            ).mappings()
        )

    def list_run_shards(self, run_id: UUID) -> tuple[RowMapping, ...]:
        request = analysis_content_requests_table
        job = jobs_table
        return tuple(
            self._session.execute(
                select(
                    request.c.id.label("request_id"),
                    request.c.shard_no,
                    request.c.target_count,
                    job.c.id.label("job_id"),
                    job.c.status,
                    job.c.progress,
                    job.c.error_code,
                )
                .select_from(request.join(job, job.c.id == request.c.job_id))
                .where(request.c.run_id == run_id)
                .order_by(request.c.shard_no)
            ).mappings()
        )

    def run_stats(self, run_id: UUID) -> dict[str, int]:
        counts = {status: 0 for status in ("pending", "succeeded", "failed", "stale", "cancelled")}
        rows = self._session.execute(
            select(
                analysis_content_request_items_table.c.status,
                func.count().label("count"),
            )
            .select_from(
                analysis_content_request_items_table.join(
                    analysis_content_requests_table,
                    analysis_content_requests_table.c.id
                    == analysis_content_request_items_table.c.request_id,
                )
            )
            .where(analysis_content_requests_table.c.run_id == run_id)
            .group_by(analysis_content_request_items_table.c.status)
        )
        for status, count in rows:
            counts[cast(str, status)] = cast(int, count)
        run = self.get_run(run_id)
        if run is None:
            raise AnalysisRequestNotFound
        scheduled_count = sum(counts.values())
        unscheduled_count = max(cast(int, run["target_count"]) - scheduled_count, 0)
        if run["status"] == "failed":
            counts["failed"] += unscheduled_count
        elif run["cancel_requested_at"] is not None or run["status"] == "cancelled":
            counts["cancelled"] += unscheduled_count
        else:
            counts["pending"] += unscheduled_count
        return counts

    def mark_run_running(self, run_id: UUID) -> None:
        self._session.execute(
            update(analysis_content_runs_table)
            .where(
                analysis_content_runs_table.c.id == run_id,
                analysis_content_runs_table.c.status == "queued",
            )
            .values(status="running", started_at=beijing_now())
        )

    def request_run_cancel(self, run_id: UUID) -> None:
        run = self.get_run(run_id, for_update=True)
        if run is None:
            raise AnalysisRequestNotFound
        if run["status"] not in {"queued", "running", "cancelling"}:
            raise AnalysisRunStateConflict("Analysis Run 当前状态不可取消")
        self._session.execute(
            update(analysis_content_runs_table)
            .where(analysis_content_runs_table.c.id == run_id)
            .values(status="cancelling", cancel_requested_at=beijing_now())
        )
        jobs = PostgresJobRepository(self._session)
        for request_id, job_id in self._session.execute(
            select(
                analysis_content_requests_table.c.id,
                analysis_content_requests_table.c.job_id,
            ).where(analysis_content_requests_table.c.run_id == run_id)
        ):
            job = jobs.request_cancel(cast(UUID, job_id))
            if job.status == "cancelled":
                self._session.execute(
                    update(analysis_content_request_items_table)
                    .where(
                        analysis_content_request_items_table.c.request_id == request_id,
                        analysis_content_request_items_table.c.status == "pending",
                    )
                    .values(status="cancelled", error_code="cancel_requested")
                )
        planner_job_id = cast(UUID, run["planner_job_id"])
        jobs.request_cancel(planner_job_id)
        self.refresh_run(run_id)

    def complete_request_terminal(
        self,
        *,
        request_id: UUID,
        job_status: str,
        error_code: str | None,
    ) -> UUID:
        run_id = self._session.scalar(
            select(analysis_content_requests_table.c.run_id).where(
                analysis_content_requests_table.c.id == request_id
            )
        )
        if run_id is None:
            raise AnalysisRequestNotFound
        if job_status in {"failed", "cancelled"}:
            terminal_status = "cancelled" if job_status == "cancelled" else "failed"
            self._session.execute(
                update(analysis_content_request_items_table)
                .where(
                    analysis_content_request_items_table.c.request_id == request_id,
                    analysis_content_request_items_table.c.status == "pending",
                )
                .values(
                    status=terminal_status,
                    error_code=(error_code or job_status)[:200],
                )
            )
        self.refresh_run(cast(UUID, run_id))
        return cast(UUID, run_id)

    def refresh_run(self, run_id: UUID) -> str:
        run = self.get_run(run_id, for_update=True)
        if run is None:
            raise AnalysisRequestNotFound
        counts = self.run_stats(run_id)
        if counts["pending"]:
            status = "cancelling" if run["cancel_requested_at"] is not None else "running"
            finished_at = None
        elif counts["failed"]:
            status = "partial_failed" if counts["succeeded"] else "failed"
            finished_at = beijing_now()
        elif counts["cancelled"]:
            status = "cancelled"
            finished_at = beijing_now()
        else:
            status = "succeeded"
            finished_at = beijing_now()
        self._session.execute(
            update(analysis_content_runs_table)
            .where(analysis_content_runs_table.c.id == run_id)
            .values(
                status=status,
                started_at=run["started_at"] or beijing_now(),
                finished_at=finished_at,
            )
        )
        return status

    def complete_plan_terminal(
        self,
        *,
        run_id: UUID,
        job_status: str,
        error_code: str | None,
    ) -> str:
        run = self.get_run(run_id, for_update=True)
        if run is None:
            raise AnalysisRequestNotFound
        if job_status == "succeeded":
            return self.refresh_run(run_id)
        status = "cancelled" if job_status == "cancelled" else "failed"
        now = beijing_now()
        self._session.execute(
            update(analysis_content_runs_table)
            .where(analysis_content_runs_table.c.id == run_id)
            .values(
                status=status,
                error_code=(error_code or job_status)[:200],
                started_at=run["started_at"] or now,
                finished_at=now,
                cancel_requested_at=(
                    run["cancel_requested_at"] or now if status == "cancelled" else None
                ),
            )
        )
        return status


def _row_to_work_item(row: RowMapping) -> AnalysisWorkItem:
    author_snapshot = row["author_snapshot"]
    display_name = _snapshot_text(author_snapshot, "display_name")
    bio = _snapshot_text(author_snapshot, "bio")
    verification_label = _snapshot_text(author_snapshot, "verification_label")
    observed_fields = ["content_type", "title", "text"]
    author = None
    if any(value is not None for value in (display_name, bio, verification_label)):
        author = CanonicalAuthorV1(
            display_name=display_name,
            bio=bio,
            verification_label=verification_label,
        )
        if display_name is not None:
            observed_fields.append("author.display_name")
        if bio is not None:
            observed_fields.append("author.bio")
        if verification_label is not None:
            observed_fields.append("author.verification_label")
    content = CanonicalContentV1(
        platform=require_platform_name(cast(str, row["platform"])),
        external_content_id=cast(str, row["external_content_id"]),
        content_type=cast(str, row["content_type"]),
        title=cast(str | None, row["title"]),
        text=cast(str | None, row["text"]),
        canonical_url=_http_url(row["canonical_url"]),
        share_url=_http_url(row["share_url"]),
        author=author,
        published_at=row["published_at"],
        source_updated_at=row["source_updated_at"],
        observed_at=cast(datetime, row["observed_at"]),
        observed_fields=observed_fields,
        metrics=CanonicalMetricsV1(),
        status=cast(str | None, row["content_status"]),
        source=CanonicalSourceV1(
            provider_name=cast(str, row["provider"]),
            operation=cast(str, row["operation"]),
            provider_request_id=str(row["provider_request_id"]),
            provider_attempt_id=str(row["provider_attempt_id"]),
            raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
            observed_at=cast(datetime, row["observed_at"]),
        ),
    )
    return AnalysisWorkItem(
        request_id=cast(UUID, row["request_id"]),
        analysis_run_id=cast(UUID, row["analysis_run_id"]),
        configuration_identity=AnalysisConfigurationIdentity(
            prompt_version=cast(str, row["prompt_version"]),
            prompt_sha256=cast(str, row["prompt_sha256"]),
            taxonomy_sha256=cast(str, row["taxonomy_sha256"]),
            model_provider=cast(str, row["model_provider"]),
            model=cast(str, row["model"]),
        ),
        # 0027 无法从旧 Request 还原 generation config；即使已有 Result 可推断
        # Prompt/模型身份，也不能把空配置哈希误当成当时真实配置并阻断未完成请求。
        configuration_enforced=not cast(str, row["client_idempotency_key"]).startswith(
            "legacy-request:"
        ),
        generation_config_hash=cast(str, row["generation_config_hash"]),
        ordinal=cast(int, row["ordinal"]),
        content_id=cast(UUID, row["content_id"]),
        content_version=cast(int, row["content_version"]),
        content=content,
    )


def _assert_same_analysis(
    session: Session,
    result_id: UUID,
    analysis: ContentLabelAnalysisV3,
) -> None:
    persisted_result = session.execute(
        select(
            analysis_content_results_table.c.schema_version,
            analysis_content_results_table.c.relevance,
            analysis_content_results_table.c.voice_type,
            analysis_content_results_table.c.sentiment,
        ).where(analysis_content_results_table.c.id == result_id)
    ).one()
    expected_result = (
        analysis.schema_version,
        analysis.relevance,
        analysis.voice_type,
        analysis.sentiment,
    )
    if tuple(persisted_result) != expected_result:
        raise ValueError("Analysis 幂等身份对应的相关性/发声类型/情感不一致")

    rows = session.execute(
        select(
            analysis_content_label_pairs_table.c.primary_label,
            analysis_content_label_pairs_table.c.secondary_label,
        )
        .where(analysis_content_label_pairs_table.c.analysis_result_id == result_id)
        .order_by(analysis_content_label_pairs_table.c.ordinal)
    )
    persisted = tuple((cast(str, row[0]), cast(str, row[1])) for row in rows)
    expected = tuple((item.primary_label, item.secondary_label) for item in analysis.labels)
    if persisted != expected:
        raise ValueError("Analysis 幂等身份对应的标签集合不一致")


def _snapshot_text(snapshot: object, key: str) -> str | None:
    if not isinstance(snapshot, dict) or snapshot.get(key) is None:
        return None
    return str(snapshot[key])


def _http_url(value: object) -> AnyHttpUrl | None:
    return _HTTP_URL_ADAPTER.validate_python(value) if value is not None else None


__all__ = [
    "AnalysisRequestNotFound",
    "AnalysisRunStateConflict",
    "PostgresAnalysisRepository",
]
