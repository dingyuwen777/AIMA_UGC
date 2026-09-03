"""千万级 Analysis Run 的高吞吐 PostgreSQL 调度与统计实现。"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, select

from aima_ugc.adapters.persistence.postgres.analysis import (
    AnalysisRequestNotFound,
    PostgresAnalysisRepository,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_request_items_table,
    analysis_content_requests_table,
    analysis_content_run_targets_table,
)
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
        if run["cancel_requested_at"] is not None:
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
        counts = {
            status: 0
            for status in ("pending", "succeeded", "failed", "stale", "cancelled")
        }
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
                succeeded = _result_count(result, "succeeded")
                failed = _result_count(result, "failed")
                stale = _result_count(result, "stale")
                if succeeded + failed + stale == target_count:
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
                .where(
                    analysis_content_request_items_table.c.request_id.in_(
                        item_scan_request_ids
                    )
                )
                .group_by(analysis_content_request_items_table.c.status)
            )
            for status, count in rows:
                counts[cast(str, status)] += cast(int, count)

        unscheduled_count = max(cast(int, run["target_count"]) - scheduled_count, 0)
        if run["status"] == "failed":
            counts["failed"] += unscheduled_count
        elif run["cancel_requested_at"] is not None or run["status"] == "cancelled":
            counts["cancelled"] += unscheduled_count
        else:
            counts["pending"] += unscheduled_count
        return counts


def _result_count(result: dict[object, object], key: str) -> int:
    """只接受非布尔、非负整数 Job Result 计数；损坏结果回退到 Item 扫描。"""

    value = result.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return -1_000_000_000
    return value


__all__ = ["PostgresHighThroughputAnalysisRepository"]
