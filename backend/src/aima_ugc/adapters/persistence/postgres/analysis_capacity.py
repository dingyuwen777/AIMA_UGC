"""Analysis Owner 的共享容量状态、墙钟观察窗与跨 Run 活动分片查询。"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from math import ceil
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.analysis.adaptive_capacity import (
    CAPACITY_MODE,
    SHARD_CONCURRENCY_CEILING,
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
from aima_ugc.platform.jobs.tables import jobs_table as jobs

# 固定桶限制存储和线程聚合开销；P95 是桶上界估计，非原始完整样本。
LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0)
COUNT_FIELDS = (
    "persisted",
    "failed",
    "validation_failed",
    "requests",
    "started",
    "rate_limited",
    "timeouts",
    "transport_errors",
)


def empty_window() -> dict[str, Any]:
    """有界窗口没有逐请求记录，不包含内容、Secret 或响应正文。"""

    return {
        **dict.fromkeys(COUNT_FIELDS, 0),
        "busy_seconds": 0.0,
        "timeout_lower_bound_seconds": 0.0,
        "latency": [0] * len(LATENCY_BUCKETS),
        "demand": False,
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
        self, provider_id: UUID, model: str, *, revision: int, prompt_sha256: str
    ) -> CapacityState:
        """新 Run 只在身份变更时保守重探，旧 Revision 不能倒写新学习状态。"""

        now = self._now()
        self._session.execute(
            insert(profiles)
            .values(
                provider_config_id=provider_id,
                model=model,
                revision=revision,
                prompt_sha256=prompt_sha256,
                state=asdict(CapacityState()),
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
        if revision > row["revision"] or (
            revision == row["revision"] and prompt_sha256 != row["prompt_sha256"]
        ):
            state = state.warm_start()
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
                    window=empty_window(),
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
    ) -> RowMapping:
        """同一墙钟窗只推进一次；旧配置反馈不能覆盖当前状态。"""

        row = self.get(provider_id, model, for_update=True)
        if row is None:
            raise ValueError("缺少自适应容量 Profile")
        if row["revision"] != revision or row["prompt_sha256"] != prompt_sha256:
            return row
        state = CapacityState(**row["state"])
        now = self._now()
        window = dict(row["window"])
        for key in COUNT_FIELDS:
            window[key] = int(window[key]) + int(delta[key])
        window["busy_seconds"] += delta["busy_seconds"]
        window["timeout_lower_bound_seconds"] = max(
            window["timeout_lower_bound_seconds"], delta["timeout_lower_bound_seconds"]
        )
        window["latency"] = [
            a + b for a, b in zip(window["latency"], delta["latency"], strict=True)
        ]
        window["demand"] = bool(window["demand"] or delta["demand"])
        elapsed = (now - row["window_started_at"]).total_seconds()
        adjusted_at = row["last_adjusted_at"]
        started_at = row["window_started_at"]
        # 首批请求尚未成熟时不提前判健康；429 仍按固定短窗快速响应。
        decision_seconds = (
            WINDOW_SECONDS
            if window["rate_limited"]
            else max(WINDOW_SECONDS, min(30.0, state.latency_p95 * 1.5))
        )
        if elapsed >= decision_seconds:
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
                demand=bool(
                    window["demand"] and window["busy_seconds"] / elapsed >= state.current * 0.9
                ),
                timeout_lower_bound_seconds=window["timeout_lower_bound_seconds"],
                **{key: int(window[key]) for key in COUNT_FIELDS},
            )
            next_state = state.observe(observation)
            if (
                next_state.current != state.current
                or next_state.rps != state.rps
                or next_state.phase != state.phase
            ):
                adjusted_at = now
                next_state = replace(next_state, last_adjustment_reason=next_state.reason)
            state = next_state
            window = empty_window()
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
        if snapshot.get("capacity_mode") != CAPACITY_MODE:
            return resource_window
        provider_id = UUID(snapshot["provider_config_id"])
        if self.legacy_jobs(provider_id, run["model"]):
            return 0
        profile = self.get(provider_id, run["model"])
        state = CapacityState(**profile["state"]) if profile is not None else CapacityState()
        needed = max(1, ceil(state.current / SHARD_CONCURRENCY_CEILING))
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
                runs.c.runtime_config_snapshot["capacity_mode"].astext == CAPACITY_MODE,
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
