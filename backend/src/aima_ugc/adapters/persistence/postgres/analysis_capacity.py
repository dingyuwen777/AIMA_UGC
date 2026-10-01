"""Analysis Owner 的共享容量状态、墙钟观察窗与跨 Run 活动分片查询。"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta
from math import ceil
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.analysis.adaptive_capacity import (
    CONTROL_VERSION,
    SHARD_CONCURRENCY_CEILING,
    SUPPORTED_CAPACITY_MODES,
    WINDOW_SECONDS,
    CapacityObservation,
    CapacityState,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_requests_table as requests,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_runs_table as runs,
)
from aima_ugc.modules.analysis.tables import (
    analysis_llm_capacity_profiles_table as profiles,
)
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.tables import jobs_table as jobs

# 固定桶限制存储和线程聚合开销；P95 是桶上界估计，非原始完整样本。
LATENCY_BUCKETS = tuple(0.05 * 1.2**index for index in range(56))
_DECLARATION_UNSET = object()
_CONGESTION_FIELDS = (
    "rate_limited",
    "timeouts",
    "transport_errors",
    "concurrency_limited",
    "rate_only_limited",
)
COUNT_FIELDS = (
    "persisted",
    "failed",
    "validation_failed",
    "requests",
    "started",
    "rate_limited",
    "timeouts",
    "transport_errors",
    "cohort_requests",
    "concurrency_limited",
    "rate_only_limited",
)


def empty_window() -> dict[str, Any]:
    """有界窗口没有逐请求记录，不包含内容、Secret 或响应正文。"""

    return {
        **dict.fromkeys(COUNT_FIELDS, 0),
        "busy_seconds": 0.0,
        "timeout_lower_bound_seconds": 0.0,
        "latency": [0] * len(LATENCY_BUCKETS),
        "demand": False,
        "version": 2,
        "epoch": 0,
        "reservations": {},
        "local_limited": False,
        "control_errors": dict.fromkeys(_CONGESTION_FIELDS, 0),
    }


class PostgresAnalysisCapacityRepository:
    """一行锁串行推进控制器；学习反馈复用调用方短事务。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, provider_id: UUID, model: str, *, for_update: bool = False) -> RowMapping | None:
        statement = select(profiles).where(
            profiles.c.provider_config_id == provider_id, profiles.c.model == model
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.execute(statement).mappings().one_or_none()

    def ensure(
        self,
        provider_id: UUID,
        model: str,
        *,
        revision: int,
        prompt_sha256: str,
        declared_ceiling: int | None | object = _DECLARATION_UNSET,
    ) -> CapacityState:
        """新 Run 只在身份变更时保守重探，旧 Revision 不能倒写新学习状态。"""

        now = self._now()
        hint = (
            None if declared_ceiling is _DECLARATION_UNSET else cast(int | None, declared_ceiling)
        )
        initial = min(64, max(10, ceil((hint or 100) ** 0.5)))
        self._session.execute(
            insert(profiles)
            .values(
                provider_config_id=provider_id,
                model=model,
                revision=revision,
                prompt_sha256=prompt_sha256,
                state=asdict(
                    CapacityState(
                        current=initial,
                        declared_ceiling=hint,
                    )
                ),
                window=empty_window(),
                window_started_at=now,
                updated_at=now,
                last_adjusted_at=now,
            )
            .on_conflict_do_nothing()
        )
        row = self.get(provider_id, model, for_update=True)
        assert row is not None
        state = CapacityState(**row["state"])
        declaration_changed = (
            declared_ceiling is not _DECLARATION_UNSET
            and revision >= row["revision"]
            and state.declared_ceiling != hint
        )
        if declaration_changed:
            # None 表示当前端点明确没有声明，省略参数才表示保留当前提示。
            state = replace(state, declared_ceiling=hint)
            self._session.execute(
                update(profiles)
                .where(
                    profiles.c.provider_config_id == provider_id,
                    profiles.c.model == model,
                )
                .values(state=asdict(state))
            )
        if row["state"].get("control_version") != CONTROL_VERSION:
            # 旧算法的 unsafe/冷却依赖错误占用口径，不能迁成新容量证明。
            state = replace(
                state,
                current=min(state.declared_ceiling or 5000, max(initial, state.current))
                if row["state"].get("control_version") == 2
                else max(initial, min(64, state.current)),
                last_safe=0,
                safe_bound=0,
                last_safe_throughput=0,
                throughput_ewma=0,
                unsafe=None,
                cooldown_windows=0,
                cooldown_seconds=0,
                phase="exploring",
                control_version=CONTROL_VERSION,
                stable_windows=0,
                plateau_windows=0,
                reason="control_version_upgrade",
            ).clear_evidence()
            self._session.execute(
                update(profiles)
                .where(
                    profiles.c.provider_config_id == provider_id,
                    profiles.c.model == model,
                )
                .values(
                    state=asdict(state),
                    # 控制证据必须重探，旧 Fence 的未知占用仍须保留到归还或过期。
                    window={
                        **empty_window(),
                        "epoch": int(row["window"].get("epoch", 0)) + 1,
                        "reservations": row["window"].get("reservations", {}),
                    },
                    window_started_at=now,
                )
            )
        if (
            revision > row["revision"]
            or (revision == row["revision"] and prompt_sha256 != row["prompt_sha256"])
            or (declaration_changed and row["state"].get("control_version") == CONTROL_VERSION)
        ):
            state = state.warm_start()
            # 配置变化不能提前借出上一身份仍在 HTTP 等待的槽位。
            previous_window = row["window"]
            next_window = {
                **empty_window(),
                "epoch": int(previous_window.get("epoch", 0)) + 1,
                "reservations": previous_window.get("reservations", {}),
            }
            self._session.execute(
                update(profiles)
                .where(
                    profiles.c.provider_config_id == provider_id,
                    profiles.c.model == model,
                )
                .values(
                    revision=revision,
                    prompt_sha256=prompt_sha256,
                    state=asdict(state),
                    window=next_window,
                    window_started_at=now,
                    updated_at=now,
                    last_adjusted_at=now,
                )
            )
        return state

    def observe(
        self,
        provider_id: UUID,
        model: str,
        *,
        revision: int,
        prompt_sha256: str,
        delta: dict[str, Any],
        diagnostics: dict[str, Any] | None = None,
    ) -> RowMapping:
        """同一墙钟窗只推进一次；旧配置反馈不能覆盖当前状态。

        diagnostics 只在闭窗时提供安全聚合事实，调用方应在事务提交后记录，
        不将诊断数据写入 Profile 或用于另一次控制判断。
        """

        row = self.get(provider_id, model, for_update=True)
        if row is None:
            raise ValueError("缺少自适应容量 Profile")
        if row["revision"] != revision or row["prompt_sha256"] != prompt_sha256:
            return row
        if row["state"].get("control_version") != CONTROL_VERSION:
            # 升级后先运行历史 v1 分片，也必须退出旧统计口径和错误 unsafe。
            self.ensure(provider_id, model, revision=revision, prompt_sha256=prompt_sha256)
            row = self.get(provider_id, model, for_update=True)
            assert row is not None
        state = CapacityState(**row["state"])
        now = self._now()
        window = dict(row["window"])
        window_started = row["window_started_at"]
        if window.get("version") != 2:
            window = empty_window()
            window_started = now
        # 没有在途/待发活动的间隔不进入新的性能分母。
        if not window["started"] and not window["requests"] and not window["busy_seconds"]:
            idle_gap = (now - row["updated_at"]).total_seconds()
            if idle_gap > 3:
                window_started = now - timedelta(
                    seconds=min(float(delta.get("sample_seconds", 1)), idle_gap)
                )
        for key in COUNT_FIELDS:
            if key == "cohort_requests":
                continue
            window[key] = int(window[key]) + int(delta[key])
        # 原始错误保留用于排障；只有当前发送阶段的错误可以再次降低当前容量。
        # 无阶段聚合的旧调用按 delta.epoch 兼容，不把迟到反馈冒充新阶段拥塞。
        controls = window.setdefault("control_errors", dict.fromkeys(_CONGESTION_FIELDS, 0))
        cohorts = delta.get("cohorts")
        if cohorts is None:
            cohorts = {
                delta.get("epoch", 0): {
                    "requests": delta["cohort_requests"],
                    **{key: delta[key] for key in _CONGESTION_FIELDS},
                }
            }
        for epoch, counts in cohorts.items():
            if int(epoch) != window["epoch"]:
                continue
            window["cohort_requests"] += counts.get("requests", 0)
            for key in _CONGESTION_FIELDS:
                controls[key] += counts.get(key, 0)
        window["busy_seconds"] += delta["busy_seconds"]
        window["timeout_lower_bound_seconds"] = max(
            window["timeout_lower_bound_seconds"], delta["timeout_lower_bound_seconds"]
        )
        window["latency"] = [
            a + b for a, b in zip(window["latency"], delta["latency"], strict=True)
        ]
        window["demand"] = bool(window["demand"] or delta["demand"])
        window["local_limited"] = bool(window["local_limited"] or delta.get("local_limited"))
        elapsed = (now - window_started).total_seconds()
        adjusted_at = row["last_adjusted_at"]
        started_at = window_started
        # 首批请求尚未成熟时不提前判健康；429 仍按固定短窗快速响应。
        decision_seconds = WINDOW_SECONDS
        enough = (
            window["persisted"] >= min(8, max(2, ceil(state.current * 0.05)))
            or controls["rate_limited"]
            or controls["timeouts"] >= 3
            or controls["transport_errors"] >= 3
            or not window["demand"]
        )
        if elapsed >= decision_seconds and enough:
            count = sum(window["latency"])
            threshold = ceil(count * 0.95)
            cumulative = 0
            p95 = 0.0
            for upper, bucket_count in zip(LATENCY_BUCKETS, window["latency"], strict=True):
                cumulative += bucket_count
                if cumulative >= threshold and count:
                    p95 = upper
                    break
            observation = CapacityObservation(
                seconds=elapsed,
                p95_seconds=p95,
                # 升档首窗可只装满旧目标的一半；明显未装满的尾部不能学习模型边界。
                demand=bool(window["demand"])
                and window["busy_seconds"] / elapsed >= state.current * 0.5,
                mature=window["cohort_requests"] >= min(8, max(2, ceil(state.current * 0.05))),
                local_limited=bool(window["local_limited"]),
                available_concurrency=max(
                    state.current,
                    sum(
                        int(value["wanted"])
                        for value in window["reservations"].values()
                        if datetime.fromisoformat(value["expires_at"]) > now
                    ),
                ),
                timeout_lower_bound_seconds=window["timeout_lower_bound_seconds"],
                **{
                    key: int(controls[key] if key in _CONGESTION_FIELDS else window[key])
                    for key in COUNT_FIELDS
                },
            )
            next_state = state.observe(observation)
            if diagnostics is not None:
                # 只导出本次实际决策的聚合事实，不另算一套控制规则，也不持久化诊断数据。
                diagnostics.update(
                    window_seconds=round(elapsed, 3),
                    decision_seconds=round(decision_seconds, 3),
                    feedback_gap_seconds=round(
                        max(0.0, (now - row["updated_at"]).total_seconds()), 3
                    ),
                    **{key: int(window[key]) for key in COUNT_FIELDS},
                    **{f"control_{key}": int(controls[key]) for key in _CONGESTION_FIELDS},
                    p95_seconds=p95,
                    previous_p95_seconds=round(state.latency_p95, 3),
                    persisted_per_second=round(observation.persisted / elapsed, 3),
                    previous_throughput_ewma=round(state.throughput_ewma, 3),
                    in_flight_seconds=round(window["busy_seconds"], 3),
                    average_in_flight=round(window["busy_seconds"] / elapsed, 3),
                    mature_cohort=observation.mature,
                    local_limited=observation.local_limited,
                    available_concurrency=observation.available_concurrency,
                    reported_demand=bool(window["demand"]),
                    accepted_demand=observation.demand,
                    previous_concurrency=state.current,
                    global_concurrency=next_state.current,
                    previous_phase=state.phase,
                    phase=next_state.phase,
                    reason=next_state.reason,
                    previous_cooldown_windows=state.cooldown_windows,
                    cooldown_windows=next_state.cooldown_windows,
                    cooldown_seconds=next_state.cooldown_seconds,
                    stable_windows=next_state.stable_windows,
                    refinements=next_state.refinements,
                    previous_last_safe=state.last_safe,
                    previous_last_safe_throughput=round(state.last_safe_throughput, 3),
                    last_safe=next_state.last_safe,
                    control_version=next_state.control_version,
                    evidence_seconds=round(next_state.evidence_seconds, 3),
                    evidence_persisted=next_state.evidence_persisted,
                    evidence_validation_failed=next_state.evidence_validation_failed,
                    accepted_throughput=round(next_state.last_safe_throughput, 3),
                    safe_bound=next_state.safe_bound,
                    unsafe=next_state.unsafe,
                )
            if (
                next_state.current != state.current
                or next_state.rps != state.rps
                or next_state.phase != state.phase
            ):
                adjusted_at = now
                next_state = replace(next_state, last_adjustment_reason=next_state.reason)
            # RPS 收紧与 C 调整都改变发送策略；旧策略的迟到拒绝只能进入诊断。
            # 健康 RPS 恢复不清空并发成熟证据，避免长延迟请求永远赶不上观察阶段。
            send_policy_changed = next_state.current != state.current or (
                next_state.rps is not None and (state.rps is None or next_state.rps < state.rps)
            )
            if send_policy_changed:
                next_state = next_state.clear_evidence()
            state = next_state
            reservations = window["reservations"]
            epoch = int(window["epoch"]) + send_policy_changed
            window = {**empty_window(), "reservations": reservations, "epoch": epoch}
            started_at = now
        self._session.execute(
            update(profiles)
            .where(
                profiles.c.provider_config_id == provider_id,
                profiles.c.model == model,
            )
            .values(
                state=asdict(state),
                window=window,
                window_started_at=started_at,
                updated_at=now,
                last_adjusted_at=adjusted_at,
            )
        )
        result = self.get(provider_id, model)
        assert result is not None
        return result

    def reserve(
        self,
        provider_id: UUID,
        model: str,
        *,
        fence: JobExecutionFence,
        wanted: int,
        occupied: int,
        timeout_seconds: float,
    ) -> tuple[int, int]:
        """原子预留分片槽位；旧在途只排空，换 Fence 不提前释放未知请求。

        调用方须先锁当前 Job；每秒一次批量预留，HTTP 热路径只使用本地许可。
        同一 Profile JSON 保存有期限的派生预留，不新增任务或逐请求账本。
        """
        from .jobs import PostgresJobRepository

        PostgresJobRepository(self._session).lock_current_execution(fence)
        row = self.get(provider_id, model, for_update=True)
        if row is None:
            raise ValueError("缺少自适应容量 Profile")
        now = self._now()
        window = dict(row["window"])
        if window.get("version") != 2:
            window = empty_window()
        reservations = {
            key: value
            for key, value in window["reservations"].items()
            if datetime.fromisoformat(value["expires_at"]) > now
        }
        active = self.active_shards(provider_id, model)
        state = CapacityState(**row["state"])
        key = f"{fence.job_id}:{fence.lease_token}"
        capacity = state.current
        fair = capacity // max(1, len(active))
        own_share = fair + (
            fence.job_id in active and active.index(fence.job_id) < capacity % max(1, len(active))
        )
        spare = 0
        for index, job_id in enumerate(active):
            if job_id == fence.job_id:
                continue
            peers = [value for value in reservations.values() if value["job_id"] == str(job_id)]
            peer_share = fair + (index < capacity % max(1, len(active)))
            peer_wanted = max((int(value["wanted"]) for value in peers), default=peer_share)
            spare += max(0, peer_share - peer_wanted)
        others = sum(
            int(value["reserved"]) for identity, value in reservations.items() if identity != key
        )
        granted = min(
            max(0, wanted), own_share + spare, max(0, capacity - others), SHARD_CONCURRENCY_CEILING
        )
        reservations[key] = {
            "job_id": str(fence.job_id),
            "wanted": wanted,
            "reserved": max(granted, occupied),
            "rps": self._reserve_send_rate(
                reservations,
                key=key,
                active=active,
                capacity=capacity,
                granted=granted,
                global_rps=state.rps,
            ),
            "expires_at": (now + timedelta(seconds=max(30, timeout_seconds) + 15)).isoformat(),
        }
        window["reservations"] = reservations
        self._session.execute(
            update(profiles)
            .where(
                profiles.c.provider_config_id == provider_id,
                profiles.c.model == model,
            )
            .values(window=window)
        )
        return granted, int(window["epoch"])

    @staticmethod
    def _reserve_send_rate(
        reservations: dict[str, dict[str, object]],
        *,
        key: str,
        active: tuple[UUID, ...],
        capacity: int,
        granted: int,
        global_rps: float | None,
    ) -> float | None:
        """按可发送份额借出速率，并扣除其他已承诺速率，避免异步刷新重复借额。

        只按 target/C 会损失机器受限或尾部任务的可用 RPS；只归一化 target 总量
        又可能与 peer 的旧本地速率叠加。旧记录未带速率时保守保留完整保护，
        由下一次原子刷新归还；真实/未知 C 占用继续由 reserve 的原有规则保护。
        """
        if global_rps is None:
            return None
        if granted <= 0:
            return 0.0
        weights = granted
        for index, job_id in enumerate(active):
            if key.startswith(f"{job_id}:"):
                continue
            peers = [value for value in reservations.values() if value["job_id"] == str(job_id)]
            peer_share = capacity // max(1, len(active)) + (index < capacity % max(1, len(active)))
            weights += max(
                (min(cast(int, value["wanted"]), cast(int, value["reserved"])) for value in peers),
                default=peer_share,
            )
        others = 0.0
        for identity, value in reservations.items():
            if identity == key:
                continue
            rate = value.get("rps")
            if rate is None:
                rate = (
                    global_rps
                    if cast(int, value["reserved"]) > 0 and cast(int, value["wanted"]) > 0
                    else 0.0
                )
            others += cast(float, rate)
        return min(global_rps * granted / max(1, weights), max(0.0, global_rps - others))

    def reserved_rps(
        self, provider_id: UUID, model: str, *, fence: JobExecutionFence
    ) -> float | None:
        """读取同事务 C 预留已提交的本 Fence 速率，不在反馈层再造分配算法。"""
        row = self.get(provider_id, model)
        if row is None:
            raise ValueError("缺少自适应容量 Profile")
        value = row["window"].get("reservations", {}).get(f"{fence.job_id}:{fence.lease_token}", {})
        if "rps" not in value:
            return None if row["state"].get("rps") is None else 0.0
        return cast(float | None, value["rps"])

    def release(self, provider_id: UUID, model: str, fence: JobExecutionFence) -> None:
        """执行线程全部结束后只释放本 Fence 的预留，不删除接管者的状态。"""
        row = self.get(provider_id, model, for_update=True)
        if row is None:
            return
        window = dict(row["window"])
        reservations = dict(window.get("reservations", {}))
        reservations.pop(f"{fence.job_id}:{fence.lease_token}", None)
        window["reservations"] = reservations
        state = row["state"]
        if not reservations:
            # 最后一片退出时同时丢弃尾窗和未完成候选，已学安全档不受影响。
            window = {**empty_window(), "epoch": int(window.get("epoch", 0)) + 1}
            if state.get("control_version") == CONTROL_VERSION:
                state = asdict(CapacityState(**state).clear_evidence())
        self._session.execute(
            update(profiles)
            .where(
                profiles.c.provider_config_id == provider_id,
                profiles.c.model == model,
            )
            .values(
                state=state,
                window=window,
                window_started_at=self._now() if not reservations else row["window_started_at"],
            )
        )

    def active_shards(self, provider_id: UUID, model: str) -> tuple[UUID, ...]:
        """跨 Run 只计仍持有有效 Lease/Deadline 的运行分片，队列不稀释实际容量。"""

        statement = (
            self._matching_jobs(provider_id, model)
            .where(
                jobs.c.status == "running",
                jobs.c.lease_expires_at > func.clock_timestamp(),
                jobs.c.attempt_deadline_at > func.clock_timestamp(),
                jobs.c.cancel_requested_at.is_(None),
                runs.c.cancel_requested_at.is_(None),
            )
            .order_by(jobs.c.id)
        )
        return tuple(self._session.execute(statement).scalars())

    def provider_job_window(self, run: RowMapping, resource_window: int) -> int:
        """新投放受 Provider 需求和全局已投放量约束，不收回已经认领/发送的工作。"""

        snapshot = run["runtime_config_snapshot"]
        if snapshot.get("capacity_mode") not in SUPPORTED_CAPACITY_MODES:
            return resource_window
        provider_id = UUID(snapshot["provider_config_id"])
        if self.legacy_jobs(provider_id, run["model"]):
            return 0
        profile = self.get(provider_id, run["model"])
        state = CapacityState(**profile["state"]) if profile is not None else CapacityState()
        slots = min(
            int(snapshot["max_concurrency"]),
            int(run["shard_size"]),
            int(run["target_count"]),
            SHARD_CONCURRENCY_CEILING,
        )
        needed = max(1, ceil(state.current / max(1, slots)))
        # 预备一个衔接分片；慢尾部释放的共享许可可立即用于后续内容。
        # 这只增加有界 Job 窗口，HTTP 总许可仍由 reserve 原子限制。
        if int(run["shard_count"]) > needed:
            needed += 1
        other_jobs = self._matching_jobs(provider_id, run["model"]).where(
            jobs.c.status.in_(("queued", "running")),
            runs.c.id != run["id"],
            jobs.c.cancel_requested_at.is_(None),
            runs.c.cancel_requested_at.is_(None),
        )
        other_count = self._session.execute(
            select(func.count()).select_from(other_jobs.subquery())
        ).scalar_one()
        # 没有可继续领取的工作时保留一片。队列不发送 HTTP，也不增加 DB 连接；
        # 瞬时 DB 压力结束后仍有持久唤醒入口，不扩大已有积压。
        return max(0, min(max(1, resource_window), needed) - int(other_count))

    def legacy_jobs(self, provider_id: UUID, model: str) -> tuple[UUID, ...]:
        """旧快照保持固定参数，新 Run 等待它们排空，不把旧占用当空闲容量。"""

        statement = self._matching_jobs(provider_id, model).where(
            runs.c.runtime_config_snapshot["capacity_mode"].astext.is_(None),
            or_(
                jobs.c.status == "queued",
                (jobs.c.status == "running")
                & (jobs.c.lease_expires_at > func.clock_timestamp())
                & (jobs.c.attempt_deadline_at > func.clock_timestamp()),
            ),
        )
        return tuple(self._session.execute(statement).scalars())

    def waiting_runs(self, provider_id: UUID, model: str, *, excluding: UUID) -> tuple[UUID, ...]:
        """容量释放后唤醒已完成 Planner 的同 Provider Run，跳过其他事务持有的 Run。"""

        planner = jobs.alias("capacity_planner")
        statement = (
            select(runs.c.id)
            .join(planner, planner.c.id == runs.c.planner_job_id)
            .where(
                runs.c.runtime_config_snapshot["capacity_mode"].astext.in_(
                    SUPPORTED_CAPACITY_MODES
                ),
                runs.c.runtime_config_snapshot["provider_config_id"].astext == str(provider_id),
                runs.c.model == model,
                runs.c.id != excluding,
                runs.c.status.in_(("queued", "running")),
                runs.c.cancel_requested_at.is_(None),
                planner.c.status == "succeeded",
            )
            .order_by(runs.c.created_at, runs.c.id)
            .limit(20)
            .with_for_update(of=runs, skip_locked=True)
        )
        return tuple(self._session.execute(statement).scalars())

    def _matching_jobs(self, provider_id: UUID, model: str) -> Select[tuple[UUID]]:
        """Provider/Model 共享身份不由 Run 或进程本地实例决定。"""

        return (
            select(jobs.c.id)
            .select_from(
                jobs.join(requests, requests.c.job_id == jobs.c.id).join(
                    runs, runs.c.id == requests.c.run_id
                )
            )
            .where(
                or_(
                    runs.c.runtime_config_snapshot["provider_config_id"].astext == str(provider_id),
                    (runs.c.runtime_config_snapshot == {})
                    & (provider_id == UUID("00000000-0000-4000-8000-000000000001")),
                ),
                runs.c.model == model,
            )
        )

    def _now(self) -> datetime:
        return cast(datetime, self._session.execute(select(func.clock_timestamp())).scalar_one())
