"""一个 Analysis 执行身份的本地反馈聚合与共享容量刷新。"""

from __future__ import annotations

import logging
from threading import Lock
from time import monotonic
from uuid import UUID

from aima_ugc.adapters.llm.request_audit import LLMHTTPRequestAudit
from aima_ugc.adapters.persistence.postgres.analysis_capacity import (
    COUNT_FIELDS,
    LATENCY_BUCKETS,
    PostgresAnalysisCapacityRepository,
    empty_window,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.analysis.adaptive_capacity import CapacityState, shard_capacity
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.logging import log_event

from .runtime import PlatformRuntime


class AnalysisCapacityFeedback:
    """HTTP 线程只更新有界内存计数；调度线程每秒在带 Fence 的短事务反馈。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        provider: ProviderConfig,
        prompt_sha256: str,
        run_id: UUID,
    ) -> None:
        self._runtime = runtime
        self._provider = provider
        self._prompt_sha256 = prompt_sha256
        self._run_id = run_id
        self._lock = Lock()
        self._delta = empty_window()
        self._last_refresh = 0.0
        self.target = 0
        self.rps: float | None = None

    def started(self) -> None:
        """统计物理发送次数，Retry 也独立计数。"""

        with self._lock:
            self._delta["started"] += 1

    def audit(self, audit: LLMHTTPRequestAudit) -> None:
        """统计 Attempt 的真实拥塞和延迟，不在 HTTP 热路径连接数据库。"""

        seconds = max(0.0, (audit.completed_at - audit.started_at).total_seconds())
        bucket = next(
            (index for index, upper in enumerate(LATENCY_BUCKETS) if seconds <= upper),
            len(LATENCY_BUCKETS) - 1,
        )
        with self._lock:
            self._delta["requests"] += 1
            self._delta["rate_limited"] += audit.status_code == 429
            self._delta["timeouts"] += audit.error_code == "timeout"
            self._delta["transport_errors"] += audit.error_code == "network_error" or (
                audit.status_code is not None
                and (audit.status_code == 408 or 500 <= audit.status_code < 600)
            )
            self._delta["latency"][bucket] += 1
            self._delta["busy_seconds"] += seconds
            if audit.error_code == "timeout":
                self._delta["timeout_lower_bound_seconds"] = max(
                    self._delta["timeout_lower_bound_seconds"], seconds
                )

    def persisted(self, *, succeeded: int, failed: int, validation_failed: int) -> None:
        """仅在结果事务提交成功后调用，stale 与取消没有成功贡献。"""

        with self._lock:
            self._delta["persisted"] += succeeded
            self._delta["failed"] += failed
            self._delta["validation_failed"] += validation_failed

    def refresh(self, fence: JobExecutionFence, *, demand: bool, force: bool = False) -> None:
        """刷新跨 Run 份额并在当前 Shard 尚未完成时有界扩展现有 Job 窗口。"""

        now = monotonic()
        if not force and now - self._last_refresh < 1.0:
            return
        with self._lock:
            delta = self._delta
            delta["demand"] = demand
            self._delta = empty_window()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                repository = PostgresAnalysisCapacityRepository(session)
                profile = repository.observe(
                    self._provider.id,
                    self._provider.model or "",
                    revision=self._provider.revision,
                    prompt_sha256=self._prompt_sha256,
                    delta=delta,
                )
                active = repository.active_shards(self._provider.id, self._provider.model or "")
                state = CapacityState(**profile["state"])
                legacy_occupied = bool(
                    repository.legacy_jobs(self._provider.id, self._provider.model or "")
                )
                target = (
                    shard_capacity(state.current, len(active), active.index(fence.job_id))
                    if fence.job_id in active and not legacy_occupied
                    else 0
                )
                rate = state.rps / len(active) if state.rps is not None and active else None
                # 在取 Profile 锁之后取 Run 锁；其他调度入口只读 Profile，避免反向等待。
                from .analysis_high_throughput_planner import (
                    schedule_high_throughput_analysis_run_shards,
                )

                schedule_high_throughput_analysis_run_shards(
                    session,
                    run_id=self._run_id,
                    max_in_flight=self._runtime.job_window(
                        "analysis", ceiling=self._runtime.settings.analysis_run_max_in_flight_jobs
                    ),
                    request_id=None,
                )
            if target != self.target or rate != self.rps:
                log_event(
                    self._runtime.logger,
                    logging.INFO,
                    "analysis.capacity_adjusted",
                    "LLM 共享容量目标调整。",
                    provider_config_id=str(self._provider.id),
                    model=self._provider.model,
                    run_id=str(self._run_id),
                    global_concurrency=state.current,
                    shard_concurrency=target,
                    active_shards=len(active),
                    rps=state.rps,
                    phase=state.phase,
                    reason=state.reason,
                )
            self.target = target
            self.rps = rate if target > 0 else 0.0
            self._last_refresh = now
        except BaseException:
            with self._lock:
                for key in COUNT_FIELDS:
                    self._delta[key] += delta[key]
                self._delta["busy_seconds"] += delta["busy_seconds"]
                self._delta["timeout_lower_bound_seconds"] = max(
                    self._delta["timeout_lower_bound_seconds"], delta["timeout_lower_bound_seconds"]
                )
                self._delta["latency"] = [
                    a + b for a, b in zip(self._delta["latency"], delta["latency"], strict=True)
                ]
            raise
        finally:
            session.close()
