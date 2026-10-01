"""一个 Analysis 执行身份的本地反馈聚合与共享容量刷新。"""

from __future__ import annotations

import logging
from math import ceil
from threading import Condition, Event, Lock, get_ident
from time import monotonic
from uuid import UUID

from aima_ugc.adapters.llm.rate_limited import RateLimitedContentLabelingLLM
from aima_ugc.adapters.llm.request_audit import LLMHTTPRequestAudit
from aima_ugc.adapters.persistence.postgres.analysis_capacity import (
    COUNT_FIELDS,
    LATENCY_BUCKETS,
    PostgresAnalysisCapacityRepository,
    empty_window,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.analysis.adaptive_capacity import GLOBAL_CONCURRENCY_CEILING, CapacityState
from aima_ugc.modules.analysis.capacity_telemetry import InFlightMeter
from aima_ugc.modules.analysis.content_labeling import ensure_labeling_running
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.capacity import CpuPressureSampler, analysis_http_slots, detect_resources
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
        work_ceiling: int = 1_024,
        timeout_seconds: float = 120,
    ) -> None:
        self._runtime = runtime
        self._provider = provider
        self._prompt_sha256 = prompt_sha256
        self._run_id = run_id
        self._lock = Lock()
        self._condition = Condition(self._lock)
        self._meter = InFlightMeter()
        self._completed: dict[int, tuple[float, int]] = {}
        self._epoch = 0
        self._cohorts: dict[int, dict[str, int]] = {}
        self._reserving = False
        self._work_ceiling = work_ceiling
        self._cpu = CpuPressureSampler()
        self._local_limit = work_ceiling
        self._database_limit = GLOBAL_CONCURRENCY_CEILING
        self._http_seconds = 0.0
        self._http_count = 0
        self.request_timeout = timeout_seconds
        self._delta = empty_window()
        self._last_refresh = 0.0
        self._sample_at = monotonic()
        self.target = 0
        self.rps: float | None = None
        self.rate_limiter: RateLimitedContentLabelingLLM | None = None
        self.control_seconds = 0.0

    def started(self) -> None:
        """统计物理发送次数，Retry 也独立计数。"""

        with self._lock:
            self._meter.start(get_ident(), self._epoch)
            self._delta["started"] += 1

    def admit(self, stop_event: Event | None) -> None:
        """每次物理发送取得本地预留许可，重试同样受限且等待可取消。"""
        with self._condition:
            while True:
                ensure_labeling_running(stop_event)
                if self._reserving or self._meter.active >= self.target:
                    self._condition.wait(timeout=0.1)
                    continue
                delay = self.rate_limiter.try_acquire_slot() if self.rate_limiter is not None else 0
                if delay > 0:
                    before = monotonic()
                    self._condition.wait(timeout=min(delay, 0.1))
                    assert self.rate_limiter is not None
                    self.rate_limiter.record_wait(monotonic() - before)
                    continue
                # C 与 RPS 都允许立即发送才开始在途积分，不计本地许可等待。
                self._meter.start(get_ident(), self._epoch)
                self._delta["started"] += 1
                return

    def finished(self) -> None:
        """物理 HTTP 结束立即归还本地槽位，解析不伪装成在途等待。"""
        with self._condition:
            result = self._meter.finish(get_ident())
            if result is not None:
                self._completed[get_ident()] = result
            self._condition.notify_all()

    def audit(self, audit: LLMHTTPRequestAudit) -> None:
        """统计 Attempt 的真实拥塞和延迟，不在 HTTP 热路径连接数据库。"""

        seconds = max(0.0, (audit.completed_at - audit.started_at).total_seconds())
        bucket = next(
            (index for index, upper in enumerate(LATENCY_BUCKETS) if seconds <= upper),
            len(LATENCY_BUCKETS) - 1,
        )
        with self._lock:
            completed = self._completed.pop(get_ident(), None)
            if completed is None:
                completed = self._meter.finish(get_ident())
            epoch = self._epoch
            if completed is not None:
                seconds, epoch = completed
                self._delta["cohort_requests"] += epoch == self._epoch
                bucket = next(
                    (index for index, upper in enumerate(LATENCY_BUCKETS) if seconds <= upper),
                    len(LATENCY_BUCKETS) - 1,
                )
            self._delta["requests"] += 1
            self._delta["rate_limited"] += audit.status_code == 429
            self._delta["timeouts"] += (
                audit.error_code == "timeout" and audit.timeout_phase not in {"pool", "connect"}
            )
            self._delta["local_limited"] |= audit.timeout_phase == "pool"
            self._delta["transport_errors"] += audit.error_code == "network_error" or (
                audit.status_code is not None
                and (audit.status_code == 408 or 500 <= audit.status_code < 600)
            )
            if audit.status_code is not None and 200 <= audit.status_code < 300:
                self._delta["latency"][bucket] += 1
                self._http_seconds += seconds
                self._http_count += 1
            if audit.status_code == 429:
                self._delta["concurrency_limited"] += audit.rate_limit_kind == "concurrency"
                self._delta["rate_only_limited"] += audit.rate_limit_kind in {
                    "request_rate",
                    "token_rate",
                }
            if audit.error_code == "timeout" and audit.timeout_phase not in {"pool", "connect"}:
                self._delta["timeout_lower_bound_seconds"] = max(
                    self._delta["timeout_lower_bound_seconds"], seconds
                )
            # 错误属于实际发送阶段；刷新事务期间返回的旧请求也不能混入新阶段。
            cohort = self._cohorts.setdefault(epoch, {})
            values = {
                "requests": 1,
                "rate_limited": int(audit.status_code == 429),
                "timeouts": int(
                    audit.error_code == "timeout" and audit.timeout_phase not in {"pool", "connect"}
                ),
                "transport_errors": int(
                    audit.error_code == "network_error"
                    or (
                        audit.status_code is not None
                        and (audit.status_code == 408 or 500 <= audit.status_code < 600)
                    )
                ),
                "concurrency_limited": int(
                    audit.status_code == 429 and audit.rate_limit_kind == "concurrency"
                ),
                "rate_only_limited": int(
                    audit.status_code == 429
                    and audit.rate_limit_kind in {"request_rate", "token_rate"}
                ),
            }
            for key, count in values.items():
                cohort[key] = cohort.get(key, 0) + count

    def persisted(
        self, *, succeeded: int, failed: int, validation_failed: int, seconds: float = 0
    ) -> None:
        """仅在结果事务提交成功后调用，stale 与取消没有成功贡献。"""

        with self._lock:
            self._delta["persisted"] += succeeded
            self._delta["failed"] += failed
            self._delta["validation_failed"] += validation_failed
            if seconds >= 0.25 and succeeded + failed >= 8:
                latency = self._http_seconds / max(1, self._http_count) or 5
                self._database_limit = max(1, int((succeeded + failed) / seconds * latency * 0.8))
            elif seconds > 0:
                self._database_limit = min(
                    GLOBAL_CONCURRENCY_CEILING,
                    max(self._database_limit + 1, int(self._database_limit * 1.25)),
                )

    def refresh(
        self,
        fence: JobExecutionFence,
        *,
        demand: bool,
        force: bool = False,
        pending_items: int | None = None,
        release: bool = False,
    ) -> None:
        """刷新跨 Run 份额并在当前 Shard 尚未完成时有界扩展现有 Job 窗口。

        pending_items 只记录当前执行器已取出的未完成工作项，不等同 Run 的数据库
        pending 总数；它表示希望继续处理的工作量，不能当作已发送 HTTP 占用。
        控制耗时包含此入口的事务、调度及日志。
        """

        now = monotonic()
        if not force and now - self._last_refresh < 1.0:
            return
        with self._lock:
            delta = self._delta
            delta["epoch"] = self._epoch
            delta["cohorts"], self._cohorts = self._cohorts, {}
            delta["sample_seconds"] = max(0.0, now - self._sample_at)
            self._sample_at = now
            delta["busy_seconds"] += self._meter.take_busy_seconds()
            delta["demand"] = demand
            self._delta = empty_window()
        session = self._runtime.database.new_session()
        diagnostics: dict[str, object] = {}
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
                    diagnostics=diagnostics,
                )
                active = repository.active_shards(self._provider.id, self._provider.model or "")
                state = CapacityState(**profile["state"])
                machine_limit = analysis_http_slots(detect_resources(), shard_count=len(active))
                cpu = self._cpu.sample()
                if cpu is not None and cpu > 0.9:
                    machine_limit = min(machine_limit, max(1, int(self._local_limit * 0.75)))
                self._local_limit = min(machine_limit, self._database_limit, self._work_ceiling)
                legacy_occupied = bool(
                    repository.legacy_jobs(self._provider.id, self._provider.model or "")
                )
                wanted = (
                    self._local_limit
                    if demand
                    else min(self._local_limit, max(0, pending_items or 0))
                )
                if release:
                    repository.release(self._provider.id, self._provider.model or "", fence)
                    target, epoch = 0, int(profile["window"].get("epoch", 0))
                else:
                    # 暂停本地新发送再采样，避免短事务期间从旧目标继续填充而借出真实占用。
                    # 已在途请求可以正常返回；等待 Future 不保留共享槽位。
                    with self._condition:
                        self._reserving = True
                        occupied = self._meter.active
                    target, epoch = repository.reserve(
                        self._provider.id,
                        self._provider.model or "",
                        fence=fence,
                        wanted=wanted if fence.job_id in active and not legacy_occupied else 0,
                        occupied=occupied,
                        timeout_seconds=self.request_timeout,
                    )
                rate = (
                    repository.reserved_rps(
                        self._provider.id, self._provider.model or "", fence=fence
                    )
                    if not release
                    else None
                )
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
            # 同一共享窗口只由真正关闭它的事务记录；提交失败不能写成有效决策。
            if diagnostics:
                log_event(
                    self._runtime.logger,
                    logging.INFO,
                    "analysis.capacity_window",
                    "LLM 容量观察窗判断完成。",
                    provider_config_id=str(self._provider.id),
                    model=self._provider.model,
                    run_id=str(self._run_id),
                    job_id=str(fence.job_id),
                    connection_revision=self._provider.revision,
                    prompt_sha256=self._prompt_sha256,
                    active_shards=len(active),
                    shard_concurrency=target,
                    rps=state.rps,
                    shard_rps=rate if target > 0 else 0.0,
                    pending_items=pending_items,
                    physical_active=self._meter.active,
                    local_slot_limit=self._local_limit,
                    database_slot_limit=self._database_limit,
                    cpu_pressure=cpu,
                    cpu_pressure_source=self._cpu.source,
                    request_timeout_seconds=self.request_timeout,
                    control_ms=round((monotonic() - now) * 1000),
                    **diagnostics,
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
                    shard_rps=rate if target > 0 else 0.0,
                    phase=state.phase,
                    reason=state.reason,
                    local_slot_limit=self._local_limit,
                    physical_active=self._meter.active,
                    declared_ceiling=state.declared_ceiling,
                )
            with self._condition:
                self.target = target
                self._epoch = epoch
                self.request_timeout = min(
                    180,
                    max(
                        self.request_timeout,
                        state.latency_p95 * 3 + 5,
                        state.timeout_lower_bound_seconds * 1.5 + 5,
                    ),
                )
                self._delta["local_limited"] = self._local_limit < min(
                    ceil(state.current / max(1, len(active))), self._work_ceiling
                )
                self.rps = rate if target > 0 else 0.0
                self._condition.notify_all()
            self._last_refresh = now
        except BaseException:
            with self._lock:
                # 失败事务没有关闭采样窗，下一次反馈仍应包含这段墙钟时间。
                self._sample_at -= delta["sample_seconds"]
                for key in COUNT_FIELDS:
                    self._delta[key] += delta[key]
                self._delta["local_limited"] |= delta["local_limited"]
                self._delta["busy_seconds"] += delta["busy_seconds"]
                self._delta["timeout_lower_bound_seconds"] = max(
                    self._delta["timeout_lower_bound_seconds"], delta["timeout_lower_bound_seconds"]
                )
                self._delta["latency"] = [
                    a + b for a, b in zip(self._delta["latency"], delta["latency"], strict=True)
                ]
                for epoch, counts in delta["cohorts"].items():
                    cohort = self._cohorts.setdefault(epoch, {})
                    for key, count in counts.items():
                        cohort[key] = cohort.get(key, 0) + count
                self.target = 0
            raise
        finally:
            with self._condition:
                self._reserving = False
                self._condition.notify_all()
            session.close()
            self.control_seconds += monotonic() - now

    def release(self, fence: JobExecutionFence) -> None:
        """线程全部退出后释放自身派生许可；失权者也不能删除新 Fence 的许可。"""
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresAnalysisCapacityRepository(session).release(
                    self._provider.id, self._provider.model or "", fence
                )
        finally:
            session.close()
