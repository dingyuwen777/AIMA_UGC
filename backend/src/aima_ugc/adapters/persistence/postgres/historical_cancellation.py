"""Data Import Campaign 取消的 PostgreSQL 并发收敛。"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.jobs.tables import jobs_table

from .historical_import import (
    HistoricalCampaignConflict,
    HistoricalCampaignNotFound,
    PostgresHistoricalImportRepository,
    merge_stats,
)
from .jobs import PostgresJobRepository

_CANCELLABLE_STATUSES = frozenset(
    {"discovering", "snapshotting", "ready", "queued", "running", "cancelling"}
)
_NONTERMINAL_ITEM_STATUSES = ("discovered", "snapshotting", "ready", "queued", "running")
_ACTIVE_JOB_ITEM_STATUSES = ("snapshotting", "queued", "running")
_ACTIVE_JOB_STATUSES = ("queued", "running")


def lock_historical_campaign_cancel_gate(
    session: Session,
    campaign_id: UUID,
    *,
    shared: bool,
) -> None:
    """用事务级 advisory 读写门线性化取消与业务写入，同时允许 Worker 共享并发。"""

    key = campaign_id.int & ((1 << 64) - 1)
    if key >= 1 << 63:
        key -= 1 << 64
    lock = func.pg_advisory_xact_lock_shared(key) if shared else func.pg_advisory_xact_lock(key)
    session.execute(select(lock))


class PostgresHistoricalCancellationRepository(PostgresHistoricalImportRepository):
    """按取消门 → Campaign、Job、Item 的短事务收敛，避免反向持锁。"""

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def begin_cancel(self, campaign_id: UUID) -> None:
        """独占取消门后冻结 Campaign 与尚未调度的 Item；本阶段绝不申请 Job 锁。"""

        lock_historical_campaign_cancel_gate(self._session, campaign_id, shared=False)
        campaign = self.get_campaign(campaign_id, for_update=True)
        if campaign is None:
            raise HistoricalCampaignNotFound
        status = cast(str, campaign["status"])
        if status == "uploading":
            if campaign["source_kind"] != "local_upload":
                raise HistoricalCampaignConflict("Campaign 当前状态不可取消")
            self._session.execute(
                update(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.status.in_(_NONTERMINAL_ITEM_STATUSES),
                )
                .values(status="cancelled", finished_at=func.clock_timestamp())
            )
            self._session.execute(
                update(historical_import_campaigns_table)
                .where(historical_import_campaigns_table.c.id == campaign_id)
                .values(status="cancelled", finished_at=func.clock_timestamp())
            )
            return
        if status not in _CANCELLABLE_STATUSES:
            raise HistoricalCampaignConflict("Campaign 当前状态不可取消")

        self._session.execute(
            update(historical_import_campaigns_table)
            .where(historical_import_campaigns_table.c.id == campaign_id)
            .values(status="cancelling", finished_at=None)
        )
        # 先终止尚未绑定执行 Job 的工作，Campaign 进入 cancelling 后不会再允许用户启动。
        # Worker 即使刚好完成当前事务，后续调度也找不到这些 ready/discovered Item。
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.campaign_id == campaign_id,
                historical_import_campaign_items_table.c.status.in_(("discovered", "ready")),
            )
            .values(status="cancelled", finished_at=func.clock_timestamp())
        )

    def request_job_cancellations(self, campaign_id: UUID) -> None:
        """只按仍活动的 Job 行加锁；Item 上遗留的历史终态 Job 不参与取消。"""

        item = historical_import_campaign_items_table
        item_rows = tuple(
            self._session.execute(
                select(item.c.id, item.c.job_id)
                .join(jobs_table, jobs_table.c.id == item.c.job_id)
                .where(
                    item.c.campaign_id == campaign_id,
                    item.c.job_id.is_not(None),
                    item.c.status.in_(_ACTIVE_JOB_ITEM_STATUSES),
                    jobs_table.c.status.in_(_ACTIVE_JOB_STATUSES),
                )
            )
        )
        job_items: dict[UUID, list[UUID]] = {}
        for item_id, raw_job_id in item_rows:
            job_id = cast(UUID, raw_job_id)
            job_items.setdefault(job_id, []).append(cast(UUID, item_id))

        discovery_job_id = self._session.scalar(
            select(jobs_table.c.id).where(
                jobs_table.c.internal_idempotency_key == f"historical-discover:{campaign_id}",
                jobs_table.c.status.in_(_ACTIVE_JOB_STATUSES),
            )
        )
        job_ids = set(job_items)
        if discovery_job_id is not None:
            job_ids.add(cast(UUID, discovery_job_id))

        jobs = PostgresJobRepository(self._session)
        for job_id in sorted(job_ids, key=str):
            job = jobs.request_cancel(job_id)
            if job.status != "cancelled":
                continue
            item_ids = job_items.get(job_id)
            if not item_ids:
                continue
            self._session.execute(
                update(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.id.in_(tuple(item_ids)),
                    historical_import_campaign_items_table.c.status.in_(_NONTERMINAL_ITEM_STATUSES),
                )
                .values(status="cancelled", finished_at=func.clock_timestamp())
            )

    def settle_cancel(self, campaign_id: UUID) -> bool:
        """只在相关 Job 全部终态后，把 Item、Batch 与 Campaign 收敛为 cancelled。"""

        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            raise HistoricalCampaignNotFound
        status = cast(str, campaign["status"])
        if status == "cancelled":
            return True
        if status != "cancelling":
            return False

        item_job_ids = select(historical_import_campaign_items_table.c.job_id).where(
            historical_import_campaign_items_table.c.campaign_id == campaign_id,
            historical_import_campaign_items_table.c.job_id.is_not(None),
        )
        active_jobs = cast(
            int,
            self._session.scalar(
                select(func.count())
                .select_from(jobs_table)
                .where(
                    jobs_table.c.status.in_(_ACTIVE_JOB_STATUSES),
                    or_(
                        jobs_table.c.id.in_(item_job_ids),
                        jobs_table.c.internal_idempotency_key
                        == f"historical-discover:{campaign_id}",
                    ),
                )
            )
            or 0,
        )
        if active_jobs:
            return False

        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.campaign_id == campaign_id,
                historical_import_campaign_items_table.c.status.in_(_NONTERMINAL_ITEM_STATUSES),
            )
            .values(status="cancelled", finished_at=func.clock_timestamp())
        )

        processing_batches = tuple(
            self._session.execute(
                select(
                    processing_import_batches_table.c.id,
                    processing_import_batches_table.c.historical_campaign_item_id,
                    processing_import_batches_table.c.stats,
                ).where(
                    processing_import_batches_table.c.historical_campaign_item_id.in_(
                        select(historical_import_campaign_items_table.c.id).where(
                            historical_import_campaign_items_table.c.campaign_id == campaign_id,
                            historical_import_campaign_items_table.c.item_kind == "source_file",
                        )
                    ),
                    processing_import_batches_table.c.status == "processing",
                )
            ).mappings()
        )
        for batch in processing_batches:
            source_item_id = cast(UUID, batch["historical_campaign_item_id"])
            batch_counts = self._batch_accounting_counts(cast(UUID, batch["id"]), source_item_id)
            self._session.execute(
                update(processing_import_batches_table)
                .where(processing_import_batches_table.c.id == batch["id"])
                .values(
                    status="failed",
                    stats=merge_stats(
                        cast(dict[str, object], batch["stats"] or {}),
                        batch_counts.items(),
                    ),
                    error_summary="historical_campaign_cancelled",
                    finished_at=func.clock_timestamp(),
                )
            )

        campaign_stats = self._campaign_accounting_counts(campaign_id)
        self._session.execute(
            update(historical_import_campaigns_table)
            .where(historical_import_campaigns_table.c.id == campaign_id)
            .values(
                status="cancelled",
                stats=campaign_stats,
                finished_at=func.coalesce(
                    historical_import_campaigns_table.c.finished_at,
                    func.clock_timestamp(),
                ),
            )
        )
        return True


__all__ = [
    "PostgresHistoricalCancellationRepository",
    "lock_historical_campaign_cancel_gate",
]
