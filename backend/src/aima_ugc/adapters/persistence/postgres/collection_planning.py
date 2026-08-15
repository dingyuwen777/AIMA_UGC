"""PostgreSQL Collection Plan/Occurrence Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.planning import (
    CollectionOccurrenceStatus,
    CollectionPlanDefinition,
    CollectionPlanRecord,
    CollectionScheduleOccurrenceRecord,
    PlanPlatformDefinition,
)
from aima_ugc.modules.collection.tables import (
    collection_plan_keyword_packs_table,
    collection_plan_platforms_table,
    collection_plans_table,
    collection_schedule_occurrences_table,
)


class PostgresCollectionPlanningRepository:
    """Plan/Occurrence 表的唯一 Collection 写入口；事务由调用方持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_plan(self, definition: CollectionPlanDefinition) -> CollectionPlanRecord:
        """在当前事务创建 Plan 及其平台/词包关系。"""
        plan_id = uuid4()
        now = func.clock_timestamp()
        self._session.execute(
            insert(collection_plans_table).values(
                id=plan_id,
                name=definition.name,
                enabled=definition.enabled,
                schedule_expr=definition.schedule_expr,
                timezone=definition.timezone,
                schedule_version=definition.schedule_version,
                next_run_at=None,
                last_scheduled_at=None,
                misfire_policy=definition.misfire_policy,
                max_catch_up_runs=definition.max_catch_up_runs,
                detail_policy=definition.detail_policy,
                comment_policy=definition.comment_policy,
                request_budget=definition.request_budget,
                created_by=definition.created_by,
                created_at=now,
                updated_at=now,
            )
        )

        if definition.platforms:
            self._session.execute(
                insert(collection_plan_platforms_table).values(
                    [
                        {
                            "plan_id": plan_id,
                            "platform": platform.platform,
                            "provider_config_id": platform.provider_config_id,
                            "config": dict(platform.config),
                        }
                        for platform in definition.platforms
                    ]
                )
            )

        if definition.keyword_pack_ids:
            self._session.execute(
                insert(collection_plan_keyword_packs_table).values(
                    [
                        {"plan_id": plan_id, "keyword_pack_id": keyword_pack_id}
                        for keyword_pack_id in definition.keyword_pack_ids
                    ]
                )
            )

        created = self.get_plan(plan_id)
        if created is None:  # pragma: no cover - insert succeeded but lookup vanished
            raise RuntimeError("created collection plan is not readable in current transaction")
        return created

    def get_plan(self, plan_id: UUID) -> CollectionPlanRecord | None:
        """读取 Plan 聚合快照，不修改事务状态。"""
        row = (
            self._session.execute(
                select(collection_plans_table).where(collection_plans_table.c.id == plan_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None

        platform_rows = (
            self._session.execute(
                select(collection_plan_platforms_table)
                .where(collection_plan_platforms_table.c.plan_id == plan_id)
                .order_by(collection_plan_platforms_table.c.platform)
            )
            .mappings()
            .all()
        )
        keyword_pack_ids = tuple(
            cast(UUID, value)
            for value in self._session.execute(
                select(collection_plan_keyword_packs_table.c.keyword_pack_id)
                .where(collection_plan_keyword_packs_table.c.plan_id == plan_id)
                .order_by(collection_plan_keyword_packs_table.c.keyword_pack_id)
            ).scalars()
        )
        platforms = tuple(_row_to_platform(platform_row) for platform_row in platform_rows)
        return _row_to_plan(row, platforms=platforms, keyword_pack_ids=keyword_pack_ids)

    def create_occurrence(
        self,
        *,
        plan_id: UUID,
        schedule_version: int,
        scheduled_for: datetime,
        job_id: UUID | None,
        status: CollectionOccurrenceStatus,
        skip_reason: str | None,
    ) -> CollectionScheduleOccurrenceRecord:
        """插入调用方已经判定的 Occurrence；不解析调度表达式。"""
        row = (
            self._session.execute(
                insert(collection_schedule_occurrences_table)
                .values(
                    id=uuid4(),
                    plan_id=plan_id,
                    schedule_version=schedule_version,
                    scheduled_for=scheduled_for,
                    job_id=job_id,
                    status=status,
                    skip_reason=skip_reason,
                    created_at=func.clock_timestamp(),
                )
                .returning(*collection_schedule_occurrences_table.c)
            )
            .mappings()
            .one()
        )
        return _row_to_occurrence(row)


def _row_to_platform(row: RowMapping) -> PlanPlatformDefinition:
    return PlanPlatformDefinition(
        platform=cast(str, row["platform"]),
        provider_config_id=cast(UUID, row["provider_config_id"]),
        config=cast(dict[str, object], row["config"]),
    )


def _row_to_plan(
    row: RowMapping,
    *,
    platforms: tuple[PlanPlatformDefinition, ...],
    keyword_pack_ids: tuple[UUID, ...],
) -> CollectionPlanRecord:
    return CollectionPlanRecord(
        id=cast(UUID, row["id"]),
        name=cast(str, row["name"]),
        enabled=cast(bool, row["enabled"]),
        schedule_expr=cast(str | None, row["schedule_expr"]),
        timezone=cast(str, row["timezone"]),
        schedule_version=cast(int, row["schedule_version"]),
        next_run_at=row["next_run_at"],
        last_scheduled_at=row["last_scheduled_at"],
        misfire_policy=cast(str, row["misfire_policy"]),
        max_catch_up_runs=cast(int, row["max_catch_up_runs"]),
        detail_policy=cast(str, row["detail_policy"]),
        comment_policy=cast(str, row["comment_policy"]),
        request_budget=cast(int, row["request_budget"]),
        created_by=cast(UUID | None, row["created_by"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        platforms=platforms,
        keyword_pack_ids=keyword_pack_ids,
    )


def _row_to_occurrence(row: RowMapping) -> CollectionScheduleOccurrenceRecord:
    return CollectionScheduleOccurrenceRecord(
        id=cast(UUID, row["id"]),
        plan_id=cast(UUID, row["plan_id"]),
        schedule_version=cast(int, row["schedule_version"]),
        scheduled_for=row["scheduled_for"],
        job_id=cast(UUID | None, row["job_id"]),
        status=cast(CollectionOccurrenceStatus, row["status"]),
        skip_reason=cast(str | None, row["skip_reason"]),
        created_at=row["created_at"],
    )
