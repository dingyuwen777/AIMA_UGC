"""PostgreSQL Collection Plan/Occurrence Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.contracts.collection import CollectionDecisionPolicyV1
from aima_ugc.modules.collection.corrective_tables import collection_plan_decision_policies_table
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


class StaleCollectionPlanError(RuntimeError):
    """Scheduler 锁定后发现 Plan 版本已变化或已消失。"""


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
                created_by=definition.created_by,
                created_at=now,
                updated_at=now,
            )
        )
        self._session.execute(
            insert(collection_plan_decision_policies_table).values(
                plan_id=plan_id,
                policy=definition.decision_policy.model_dump(mode="json"),
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
        return self._get_plan(plan_id, for_update=False)

    def list_schedulable_plan_ids(self, *, now: datetime, limit: int = 100) -> tuple[UUID, ...]:
        """短事务预扫需要初始化或已经到期的 Plan ID，不在此处抢锁。"""
        if now.utcoffset() is None:
            raise ValueError("Scheduler scan now 必须包含时区")
        if limit < 1:
            raise ValueError("Scheduler scan limit 必须大于等于 1")
        values = self._session.execute(
            select(collection_plans_table.c.id)
            .where(
                collection_plans_table.c.enabled.is_(True),
                collection_plans_table.c.schedule_expr.is_not(None),
                or_(
                    collection_plans_table.c.next_run_at.is_(None),
                    collection_plans_table.c.next_run_at <= now,
                ),
            )
            .order_by(
                collection_plans_table.c.next_run_at.asc().nullsfirst(),
                collection_plans_table.c.id,
            )
            .limit(limit)
        ).scalars()
        return tuple(cast(UUID, value) for value in values)

    def get_plan_for_update(self, plan_id: UUID) -> CollectionPlanRecord | None:
        """在当前事务锁定一个 Plan，并重新读取最新调度事实。"""
        return self._get_plan(plan_id, for_update=True)

    def update_schedule_cursor(
        self,
        *,
        plan_id: UUID,
        schedule_version: int,
        next_run_at: datetime,
        last_scheduled_at: datetime | None,
    ) -> None:
        """推进当前 Plan 版本的 Scheduler cursor；版本漂移时 fail closed。"""
        if next_run_at.utcoffset() is None:
            raise ValueError("next_run_at 必须包含时区")
        updated_plan_id = self._session.execute(
            update(collection_plans_table)
            .where(
                collection_plans_table.c.id == plan_id,
                collection_plans_table.c.schedule_version == schedule_version,
            )
            .values(
                next_run_at=next_run_at,
                last_scheduled_at=last_scheduled_at,
                updated_at=func.clock_timestamp(),
            )
            .returning(collection_plans_table.c.id)
        ).scalar_one_or_none()
        if updated_plan_id != plan_id:
            raise StaleCollectionPlanError("Scheduler cursor 更新时 Plan 版本已变化")

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

    def _get_plan(self, plan_id: UUID, *, for_update: bool) -> CollectionPlanRecord | None:
        statement = select(collection_plans_table).where(collection_plans_table.c.id == plan_id)
        if for_update:
            statement = statement.with_for_update()
        row = self._session.execute(statement).mappings().one_or_none()
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
        policy_payload = self._session.scalar(
            select(collection_plan_decision_policies_table.c.policy).where(
                collection_plan_decision_policies_table.c.plan_id == plan_id
            )
        )
        if policy_payload is None:
            raise RuntimeError(f"Collection Plan 缺少 Decision Policy: {plan_id}")
        decision_policy = CollectionDecisionPolicyV1.model_validate(policy_payload)
        platforms = tuple(_row_to_platform(platform_row) for platform_row in platform_rows)
        return _row_to_plan(
            row,
            platforms=platforms,
            keyword_pack_ids=keyword_pack_ids,
            decision_policy=decision_policy,
        )


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
    decision_policy: CollectionDecisionPolicyV1,
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
        created_by=cast(UUID | None, row["created_by"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        platforms=platforms,
        keyword_pack_ids=keyword_pack_ids,
        decision_policy=decision_policy,
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
