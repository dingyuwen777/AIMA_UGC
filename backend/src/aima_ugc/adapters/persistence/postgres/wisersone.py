"""Ingestion Owner 的 WisersOne 来源事实与续跑 Job。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.contracts.http import WisersOneDownloadCreateRequest
from aima_ugc.modules.collection.tables import (
    collection_plans_table,
    collection_schedule_occurrences_table,
)
from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot
from aima_ugc.modules.ingestion.historical_jobs import HISTORICAL_JOB_PRIORITY
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaigns_table
from aima_ugc.modules.ingestion.wisersone_jobs import WISERSONE_JOB_TYPE, WisersOneJobPayload
from aima_ugc.modules.ingestion.wisersone_tables import wisersone_downloads_table as table
from aima_ugc.platform.jobs.models import JobExecutionFence
from aima_ugc.platform.time import beijing_now

from .jobs import PostgresJobRepository


class WisersOneConflict(RuntimeError):
    """相同幂等身份必须对应同一下载输入。"""


class PostgresWisersOneRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, download_id: UUID, *, lock: bool = False) -> RowMapping | None:
        query = self._view().where(table.c.id == download_id)
        if lock:
            query = query.with_for_update(of=table)
        return self.session.execute(query).mappings().one_or_none()

    def list(self) -> tuple[RowMapping, ...]:
        return tuple(
            self.session.execute(self._view().order_by(table.c.created_at.desc()).limit(100))
            .mappings()
            .all()
        )

    def for_campaign(self, campaign_id: UUID) -> RowMapping | None:
        """恢复与原文件删除共用下载行锁；必须先于 Campaign 行锁取得。"""
        return (
            self.session.execute(
                select(table).where(table.c.campaign_id == campaign_id).with_for_update()
            )
            .mappings()
            .one_or_none()
        )

    def lock_input_admission(self, *, wait: bool = True) -> bool:
        """短事务串行化文件消费者准入与删除认领；清理不阻塞正在恢复的请求。"""
        key = func.hashtextextended("wisersone-managed-input-admission", 0)
        if wait:
            self.session.execute(select(func.pg_advisory_xact_lock(key)))
            return True
        return bool(self.session.scalar(select(func.pg_try_advisory_xact_lock(key))))

    def undeleted_inputs(self) -> tuple[RowMapping, ...]:
        return tuple(
            self.session.execute(select(table).where(table.c.file_deleted_at.is_(None)))
            .mappings()
            .all()
        )

    def retained_server_consumers(self, cutoff: datetime) -> tuple[RowMapping, ...]:
        """冻结目录选择是持久消费范围；所有消费者终态满七天才释放原文件。"""
        campaigns = historical_import_campaigns_table
        return tuple(
            self.session.execute(
                select(
                    campaigns.c.profile_snapshot,
                    campaigns.c.root_relative_path,
                    campaigns.c.recursive,
                ).where(
                    campaigns.c.source_kind == "server_path",
                    or_(campaigns.c.finished_at.is_(None), campaigns.c.finished_at > cutoff),
                )
            )
            .mappings()
            .all()
        )

    @staticmethod
    def _view() -> Select[Any]:
        """展示当前关联计划名称；冻结过滤范围仍以下载事实为准。"""
        occurrence = collection_schedule_occurrences_table
        plan = collection_plans_table
        return select(
            table, plan.c.id.label("plan_id"), plan.c.name.label("plan_name")
        ).select_from(
            table.outerjoin(occurrence, table.c.occurrence_id == occurrence.c.id).outerjoin(
                plan, occurrence.c.plan_id == plan.c.id
            )
        )

    def create(
        self,
        request: WisersOneDownloadCreateRequest,
        request_id: str | None,
        *,
        filter_snapshot: BrandVehicleFilterSnapshot,
    ) -> RowMapping:
        now = beijing_now()
        download_id = uuid4()
        row = (
            self.session.execute(
                insert(table)
                .values(
                    id=download_id,
                    client_idempotency_key=request.client_idempotency_key,
                    request=request.model_dump(mode="json"),
                    filter_snapshot=filter_snapshot.model_dump(mode="json"),
                    status="queued",
                    send_state="not_sent",
                    step=0,
                    percent=0,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=[table.c.client_idempotency_key])
                .returning(table)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            row = (
                self.session.execute(
                    select(table).where(
                        table.c.client_idempotency_key == request.client_idempotency_key
                    )
                )
                .mappings()
                .one()
            )
            if row["request"] != request.model_dump(mode="json"):
                raise WisersOneConflict("幂等键已用于不同 WisersOne 下载请求。")
            return row
        self.enqueue(download_id, step=0, request_id=request_id)
        return self.get(download_id) or row

    def enqueue(
        self,
        download_id: UUID,
        *,
        step: int,
        request_id: str | None,
        delay: int = 0,
        operation: Literal["observe", "cancel"] = "observe",
    ) -> UUID:
        payload = WisersOneJobPayload(download_id=download_id, step=step, operation=operation)
        job = PostgresJobRepository(self.session).enqueue(
            job_type=WISERSONE_JOB_TYPE,
            payload_version=WISERSONE_JOB_TYPE,
            payload=payload.model_dump(mode="json"),
            internal_idempotency_key=f"wisersone:{download_id}:{step}",
            request_id=request_id,
            priority=HISTORICAL_JOB_PRIORITY,
            max_attempts=5,
            timeout_seconds=900,
            available_at=beijing_now() + timedelta(seconds=delay),
        )
        self.update(download_id, step=step, job_id=job.id)
        return job.id

    def update(self, download_id: UUID, **values: object) -> None:
        self.session.execute(
            update(table)
            .where(table.c.id == download_id)
            .values(**values, updated_at=beijing_now())
        )

    def fenced(self, download_id: UUID, fence: JobExecutionFence) -> RowMapping:
        # 锁顺序保持 Job → 来源事实，与 Worker Runtime 一致。
        PostgresJobRepository(self.session).lock_current_execution(fence)
        row = self.get(download_id, lock=True)
        if row is None or row["job_id"] != fence.job_id:
            raise WisersOneConflict("WisersOne 阶段已被新的执行代替。")
        return row
