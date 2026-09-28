"""工作台聚合快照的后台刷新与启动预热。"""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.workbench_snapshots import (
    PostgresWorkbenchSnapshotRepository,
    WorkbenchSnapshotRefresh,
    snapshot_refresh_from_payload,
)
from aima_ugc.bootstrap.analysis_identity import active_analysis_configuration
from aima_ugc.contracts.workbench import WorkbenchQuery
from aima_ugc.modules.workbench.jobs import WorkbenchSnapshotJobPayload
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime
from .workbench_http import (
    PostgresWorkbenchHttpService,
    _enqueue_snapshot_job,
    _resolved_snapshot_query,
    _snapshot_query_hash,
)


class PostgresWorkbenchSnapshotJobExecutor:
    """使用正式聚合实现刷新一个精确 query snapshot。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def execute(
        self,
        *,
        payload: WorkbenchSnapshotJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        context.heartbeat(progress=5)
        service = PostgresWorkbenchHttpService(self._runtime, use_snapshot_cache=False)
        try:
            response = (
                service.get_mind(payload.query)
                if payload.module == "mind"
                else service.get_trend(payload.query)
            )
        except LeaseLostError:
            raise
        except SQLAlchemyError:
            return JobHandlerResult.retry("workbench_snapshot_database_error")
        except Exception:
            return JobHandlerResult.failed("workbench_snapshot_compute_error")

        if response.analysis_scheme_version_id != payload.analysis_scheme_version_id:
            return JobHandlerResult.succeeded({"superseded": True})
        context.heartbeat(progress=90)
        computed_at = beijing_now()
        stored = response.model_copy(
            update={
                "snapshot_status": "fresh",
                "computed_at": computed_at,
                "source_revision": payload.source_revision,
            }
        )
        refresh = WorkbenchSnapshotRefresh(
            module=payload.module,
            query_hash=payload.query_hash,
            source_revision=payload.source_revision,
            refresh_generation=payload.refresh_generation,
            analysis_scheme_version_id=payload.analysis_scheme_version_id,
        )
        session = self._runtime.database.new_session()
        try:
            try:
                with session.begin():
                    saved = PostgresWorkbenchSnapshotRepository(session).record_success(
                        refresh=refresh,
                        taxonomy_sha256=stored.taxonomy_sha256,
                        response=stored.model_dump(mode="json"),
                        computed_at=computed_at,
                        fence=fence,
                    )
            except LeaseLostError:
                raise
            except SQLAlchemyError:
                return JobHandlerResult.retry("workbench_snapshot_store_error")
        finally:
            session.close()
        return JobHandlerResult.succeeded(
            {
                "saved": saved,
                "module": payload.module,
                "query_hash": payload.query_hash,
                "source_revision": payload.source_revision,
            }
        )


def ensure_workbench_default_snapshot_jobs(runtime: PlatformRuntime) -> tuple[JobRecord, ...]:
    """Worker 启动时为默认近 30 天的 Mind/Trend 幂等安排预热。"""

    query = _resolved_snapshot_query(WorkbenchQuery())
    session = runtime.database.new_session()
    jobs: list[JobRecord] = []
    try:
        with session.begin():
            configuration = active_analysis_configuration(session, runtime.settings)
            snapshots = PostgresWorkbenchSnapshotRepository(session)
            revision = snapshots.current_data_revision()
            for module in ("mind", "trend"):
                query_hash = _snapshot_query_hash(module, query)
                row = snapshots.get(module=module, query_hash=query_hash)
                if (
                    row is not None
                    and row["status"] == "ready"
                    and row["source_revision"] == revision
                    and row["analysis_scheme_version_id"] == configuration.scheme.id
                ):
                    continue
                refresh = snapshots.request_refresh(
                    module=module,
                    query_hash=query_hash,
                    query=query.model_dump(mode="json"),
                    source_revision=revision,
                    analysis_scheme_version_id=configuration.scheme.id,
                )
                if refresh is not None:
                    jobs.append(_enqueue_snapshot_job(session, refresh=refresh, query=query))
        return tuple(jobs)
    finally:
        session.close()


def workbench_snapshot_job_terminal_callback(session: Session, job: JobRecord) -> None:
    """最终失败保留最近成功 response，只标记本刷新代次失败。"""

    if job.status != "failed":
        return
    refresh = snapshot_refresh_from_payload(job.payload)
    PostgresWorkbenchSnapshotRepository(session).record_failure(
        refresh=refresh,
        error_code=job.error_code or "workbench_snapshot_failed",
    )


__all__ = [
    "PostgresWorkbenchSnapshotJobExecutor",
    "ensure_workbench_default_snapshot_jobs",
    "workbench_snapshot_job_terminal_callback",
]
