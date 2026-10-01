"""千万级 Analysis Run 的高吞吐 PostgreSQL 调度与统计实现。"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update

from aima_ugc.adapters.persistence.postgres.analysis import (
    AnalysisRequestNotFound,
    PostgresAnalysisRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.analysis.recovery import RECOVERY_MODE
from aima_ugc.modules.analysis.tables import (
    analysis_content_request_items_table,
    analysis_content_requests_table,
    analysis_content_run_targets_table,
)
from aima_ugc.platform.jobs import JobRecord
from aima_ugc.platform.jobs.tables import jobs_table


class PostgresHighThroughputAnalysisRepository(PostgresAnalysisRepository):
    """在不改变 Schema 的前提下替换大 Run 的重复全量扫描热路径。"""

    def next_frozen_target_ordinal(self, run_id: UUID) -> int:
        """用连续 ordinal 的最大值推导下一位置，避免 Planner 每批执行 COUNT(*)。"""

        last_ordinal = self._session.scalar(
            select(func.max(analysis_content_run_targets_table.c.target_ordinal)).where(
                analysis_content_run_targets_table.c.run_id == run_id
            )
        )
        return 0 if last_ordinal is None else int(last_ordinal) + 1

    def next_unscheduled_shards(self, run_id: UUID, *, limit: int) -> tuple[int, ...]:
        """从 Run `shard_count` 和连续 Request 序号推导下一批，不扫描海量 Run Target。"""

        if limit <= 0:
            return ()
        run = self.get_run(run_id)
        if run is None:
            raise AnalysisRequestNotFound
        if run["cancel_requested_at"] is not None or run["status"] not in {"queued", "running"}:
            return ()
        scheduled_count = cast(
            int,
            self._session.scalar(
                select(func.count()).where(analysis_content_requests_table.c.run_id == run_id)
            )
            or 0,
        )
        max_shard_no = self._session.scalar(
            select(func.max(analysis_content_requests_table.c.shard_no)).where(
                analysis_content_requests_table.c.run_id == run_id
            )
        )
        if scheduled_count == 0:
            start = 0
        else:
            if max_shard_no is None or int(max_shard_no) + 1 != scheduled_count:
                raise RuntimeError("Analysis Run 已调度 Shard 序号不连续")
            start = scheduled_count
        shard_count = cast(int, run["shard_count"])
        end = min(start + limit, shard_count)
        return tuple(range(start, end))

    def run_stats(self, run_id: UUID) -> dict[str, int]:
        """优先聚合已完成 Job 的持久结果，只扫描少量非成功 Shard 的 Item。"""

        run = self.get_run(run_id)
        if run is None:
            raise AnalysisRequestNotFound
        counts = {status: 0 for status in ("pending", "succeeded", "failed", "stale", "cancelled")}
        request_rows = tuple(
            self._session.execute(
                select(
                    analysis_content_requests_table.c.id,
                    analysis_content_requests_table.c.target_count,
                    jobs_table.c.status,
                    jobs_table.c.result,
                )
                .select_from(
                    analysis_content_requests_table.join(
                        jobs_table,
                        jobs_table.c.id == analysis_content_requests_table.c.job_id,
                    )
                )
                .where(analysis_content_requests_table.c.run_id == run_id)
            ).mappings()
        )
        scheduled_count = 0
        item_scan_request_ids: list[UUID] = []
        for row in request_rows:
            target_count = cast(int, row["target_count"])
            scheduled_count += target_count
            result = row["result"]
            if row["status"] == "succeeded" and isinstance(result, dict):
                succeeded = _optional_result_count(result, "succeeded")
                failed = _optional_result_count(result, "failed")
                stale = _optional_result_count(result, "stale")
                if (
                    succeeded is not None
                    and failed is not None
                    and stale is not None
                    and succeeded + failed + stale == target_count
                ):
                    counts["succeeded"] += succeeded
                    counts["failed"] += failed
                    counts["stale"] += stale
                    continue
            item_scan_request_ids.append(cast(UUID, row["id"]))

        if item_scan_request_ids:
            rows = self._session.execute(
                select(
                    analysis_content_request_items_table.c.status,
                    func.count().label("count"),
                )
                .where(analysis_content_request_items_table.c.request_id.in_(item_scan_request_ids))
                .group_by(analysis_content_request_items_table.c.status)
            )
            for status, count in rows:
                counts[cast(str, status)] += cast(int, count)

        unscheduled_count = max(cast(int, run["target_count"]) - scheduled_count, 0)
        if run["status"] == "failed":
            counts["failed"] += unscheduled_count + counts["pending"]
            counts["pending"] = 0
        elif run["cancel_requested_at"] is not None or run["status"] == "cancelled":
            counts["cancelled"] += unscheduled_count
        else:
            counts["pending"] += unscheduled_count
        return counts

    def is_current_request_job(self, request_id: UUID, job_id: UUID) -> bool:
        """旧执行周期的迟到回调不能终结已经交给后继 Job 的 Request。"""
        return (
            self._session.scalar(
                select(analysis_content_requests_table.c.job_id).where(
                    analysis_content_requests_table.c.id == request_id
                )
            )
            == job_id
        )

    def continue_timed_out_request(self, *, request_id: UUID, job: JobRecord) -> UUID | None:
        """v2 的未完成内容在有限执行周期耗尽后持久续接，不延长 Deadline 或重置失败审计。

        调用方持有旧 Job 终态事务，依次锁 Run、创建标准 Job、切换同一 Request。
        新 Job 和断点身份同事务提交，旧 Fence 永久失权；取消/真实系统故障不续接。
        """
        if job.status != "failed" or job.error_code != "attempt_timeout":
            return None
        run_id = self._session.scalar(
            select(analysis_content_requests_table.c.run_id).where(
                analysis_content_requests_table.c.id == request_id
            )
        )
        if run_id is None:
            raise AnalysisRequestNotFound
        run = self.get_run(run_id, for_update=True)
        if (
            run is None
            or run["status"] not in {"queued", "running"}
            or run["cancel_requested_at"] is not None
            or run["runtime_config_snapshot"].get("recovery_mode") != RECOVERY_MODE
            or not self.is_current_request_job(request_id, job.id)
        ):
            return None
        if (
            self._session.scalar(
                select(analysis_content_request_items_table.c.content_id)
                .where(
                    analysis_content_request_items_table.c.request_id == request_id,
                    analysis_content_request_items_table.c.status == "pending",
                )
                .limit(1)
            )
            is None
        ):
            return None
        successor = PostgresJobRepository(self._session).enqueue(
            job_type=job.job_type,
            payload_version=job.payload_version,
            payload=job.payload,
            internal_idempotency_key=f"content-analysis-continuation:{request_id}:{job.id}",
            request_id=job.request_id,
            priority=job.priority,
            max_attempts=job.max_attempts,
            timeout_seconds=job.timeout_seconds,
        )
        self._session.execute(
            update(analysis_content_requests_table)
            .where(
                analysis_content_requests_table.c.id == request_id,
                analysis_content_requests_table.c.job_id == job.id,
            )
            .values(job_id=successor.id)
        )
        self.refresh_run(run_id)
        return successor.id


def _optional_result_count(result: dict[object, object], key: str) -> int | None:
    """读取非负 Job Result 计数；损坏或缺失值返回 None 触发精确 Item 回退扫描。"""

    value = result.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


__all__ = ["PostgresHighThroughputAnalysisRepository"]
