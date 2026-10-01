"""Analysis 现有 Run/Request Item 的待重试及健康窗口写入口。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.analysis.persistence import AnalysisWorkItem
from aima_ugc.modules.analysis.recovery import (
    RECOVERY_MODE,
    TRANSPORT_UNAVAILABLE,
    UNHEALTHY_SECONDS,
    VALIDATION_UNHEALTHY,
    retry_delay_seconds,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_request_items_table as items,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_requests_table as requests,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_runs_table as runs,
)
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.tables import jobs_table


@dataclass(frozen=True, slots=True)
class AnalysisRetryWrite:
    """一次可恢复失败；状态仍为 pending，成功内容不进入此路径。"""

    work_item: AnalysisWorkItem
    kind: str
    error_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TransportObservation:
    """有限聚合的物理 HTTP 事实，时间用于合并跨 Shard 的迟到反馈。"""

    success_at: datetime | None = None
    failure_started_at: datetime | None = None
    last_failure_at: datetime | None = None
    failure_spans: tuple[tuple[datetime, datetime], ...] = ()


class PostgresAnalysisRecoveryRepository:
    """在调用方短事务中维护恢复事实，不新增任务或外部发送。"""

    def __init__(self, session: Session) -> None:
        """复用现有 Analysis Unit of Work。"""

        self._session = session

    def refresh(
        self,
        *,
        fence: JobExecutionFence,
        run_id: UUID,
        observation: TransportObservation | None = None,
        stop_error: str | None = None,
    ) -> tuple[str | None, bool]:
        """验证 Fence 后锁 Run，合并两种计时，返回系统停止或探活状态。"""

        PostgresJobRepository(self._session).lock_current_execution(fence)
        observation = observation or TransportObservation()
        run = (
            self._session.execute(select(runs).where(runs.c.id == run_id).with_for_update())
            .mappings()
            .one()
        )
        if run["status"] == "failed":
            return run["error_code"] or "llm_run_stopped", False
        now = self._now()
        success_at = run["last_transport_success_at"]
        failure_at = run["transport_failure_started_at"]
        if observation.success_at is not None and (
            success_at is None or observation.success_at > success_at
        ):
            success_at = observation.success_at
        # 正常窗保存精确失败时刻，跨 Shard 成功落在中间时仍可找到其后的首错。
        # 固定内存上限触发区间压缩时保守截到成功时刻，不能推迟五分钟停止。
        incoming = observation.failure_spans or tuple(
            (at, at)
            for at in (observation.failure_started_at, observation.last_failure_at)
            if at is not None
        )
        stored = tuple(
            (datetime.fromisoformat(first), datetime.fromisoformat(last))
            for first, last in run["transport_failure_spans"]
        )
        # 跨事务保存有界失败事实；迟到成功只清除其之前的错误，不能丢失之后的首错。
        # 兼容迁移前已记录的首错；正常新协议始终具有完整的持久区间。
        if not stored and failure_at is not None:
            stored = ((failure_at, failure_at),)
        spans = sorted(
            set(
                (max(first, success_at + timedelta(microseconds=1)), last)
                if success_at is not None
                else (first, last)
                for first, last in (*stored, *incoming)
                if success_at is None or last > success_at
            )
        )
        while len(spans) > 4096:
            compressed = (spans[0][0], max(last for _, last in spans[:2048]))
            spans[:2048] = [compressed]
        failure_at = spans[0][0] if spans else None
        values = dict(
            last_transport_success_at=success_at,
            transport_failure_started_at=failure_at,
            transport_failure_spans=[
                [first.isoformat(), last.isoformat()] for first, last in spans
            ],
        )
        if failure_at is None:
            values.update(probe_job_id=None, probe_not_before=None)
        self._session.execute(update(runs).where(runs.c.id == run_id).values(**values))
        legacy = run["runtime_config_snapshot"].get("recovery_mode") != RECOVERY_MODE
        expired_validation = (
            self._session.scalar(
                select(items.c.content_id)
                .join(
                    requests,
                    requests.c.id == items.c.request_id,
                )
                .where(
                    requests.c.run_id == run_id,
                    items.c.status == "pending",
                    items.c.validation_failure_started_at
                    <= now - timedelta(seconds=UNHEALTHY_SECONDS),
                )
                .limit(1)
            )
            if legacy
            else None
        )
        if stop_error is None:
            # v2 必须有持续失败的真实物理反馈；一次错误后在本地等待不能证明网络故障。
            failure_end = now if legacy else max((last for _, last in spans), default=now)
            if failure_at is not None and failure_end - failure_at >= timedelta(
                seconds=UNHEALTHY_SECONDS
            ):
                stop_error = TRANSPORT_UNAVAILABLE
            elif expired_validation is not None:
                stop_error = VALIDATION_UNHEALTHY
        if stop_error is not None:
            # 不反向锁其他 Job；各执行身份从 Run 停止事实收敛并收割已发请求。
            self._session.execute(
                update(runs)
                .where(runs.c.id == run_id)
                .values(
                    status="failed",
                    error_code=stop_error[:200],
                    finished_at=now,
                )
            )
        return stop_error, failure_at is not None

    def defer(self, *, fence: JobExecutionFence, retries: Sequence[AnalysisRetryWrite]) -> None:
        """仅对当前 Job 尚未终态的 Item 持久退避，连续 Validation 窗口不重置。"""

        if not retries:
            return
        PostgresJobRepository(self._session).lock_current_execution(fence)
        now = self._now()
        for retry in retries:
            work = retry.work_item
            request_job = self._session.scalar(
                select(requests.c.job_id).where(requests.c.id == work.request_id)
            )
            if request_job != fence.job_id:
                raise ValueError("待重试 Item 与当前 Job 不匹配")
            count = work.retry_count + 1
            values: dict[str, object] = {
                "retry_kind": retry.kind,
                "retry_count": count,
                "retry_not_before": now + timedelta(seconds=retry_delay_seconds(count)),
                "last_retry_at": now,
            }
            if retry.kind == "validation":
                values["validation_failure_started_at"] = func.coalesce(
                    items.c.validation_failure_started_at, now
                )
                values["validation_error_codes"] = list(retry.error_codes)
            self._session.execute(
                update(items)
                .where(
                    items.c.request_id == work.request_id,
                    items.c.content_id == work.content_id,
                    items.c.status == "pending",
                )
                .values(**values)
            )

    def claim_probe(self, *, fence: JobExecutionFence, run_id: UUID) -> tuple[bool, bool]:
        """同一 Run 至多认领一个逻辑探活，沿用持有 Job 的 Lease/Deadline 判断失效。"""

        PostgresJobRepository(self._session).lock_current_execution(fence)
        run = (
            self._session.execute(select(runs).where(runs.c.id == run_id).with_for_update())
            .mappings()
            .one()
        )
        now = self._now()
        if run["status"] not in {"queued", "running"}:
            return False, False
        if run["transport_failure_started_at"] is None:
            return True, False
        if run["probe_not_before"] is not None and run["probe_not_before"] > now:
            return False, True
        owner = run["probe_job_id"]
        if owner is not None and owner != fence.job_id:
            live = self._session.scalar(
                select(jobs_table.c.id).where(
                    jobs_table.c.id == owner,
                    jobs_table.c.status == "running",
                    jobs_table.c.lease_expires_at > now,
                    jobs_table.c.attempt_deadline_at > now,
                    jobs_table.c.cancel_requested_at.is_(None),
                )
            )
            if live is not None:
                return False, True
        self._session.execute(
            update(runs).where(runs.c.id == run_id).values(probe_job_id=fence.job_id)
        )
        return True, True

    def release_probe(self, *, fence: JobExecutionFence, run_id: UUID, delay: float = 0) -> None:
        """逻辑探活收尾后释放占用；成功恢复已清理占用，迟到失败不能重建它。"""

        PostgresJobRepository(self._session).lock_current_execution(fence)
        self._session.execute(
            update(runs)
            .where(
                runs.c.id == run_id,
                runs.c.probe_job_id == fence.job_id,
            )
            .values(probe_job_id=None, probe_not_before=self._now() + timedelta(seconds=delay))
        )

    def _now(self) -> datetime:
        """恢复与五分钟窗口使用同一 PostgreSQL 时钟，接管不依赖进程计时。"""

        return cast(datetime, self._session.scalar(select(func.clock_timestamp())))
