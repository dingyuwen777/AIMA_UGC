"""Collection Plan 编辑、归档与条件删除的 Collection Owner Repository。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.corrective_tables import (
    collection_plan_decision_policies_table,
)
from aima_ugc.modules.collection.lifecycle_schema import register_collection_lifecycle_schema
from aima_ugc.modules.collection.planning import PlanPlatformDefinition
from aima_ugc.modules.collection.tables import (
    collection_plan_keyword_packs_table,
    collection_plan_platforms_table,
    collection_plan_vehicle_models_table,
    collection_plans_table,
    collection_runs_table,
    collection_schedule_occurrences_table,
)

register_collection_lifecycle_schema()


@dataclass(frozen=True, slots=True)
class ArchivedCollectionPlanRecord:
    """已归档采集计划的最小业务投影。"""

    id: UUID
    name: str
    archived_at: datetime


class PostgresCollectionPlanLifecycleRepository:
    """只修改 Collection Plan 聚合；历史 Occurrence/Run 保持不变。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def update_plan(
        self,
        plan_id: UUID,
        *,
        expected_schedule_version: int,
        name: str,
        schedule_expr: str,
        enabled: bool,
        platforms: tuple[PlanPlatformDefinition, ...],
        keyword_pack_ids: tuple[UUID, ...],
        vehicle_model_ids: tuple[UUID, ...],
    ) -> bool:
        """完整替换下一版本执行面；版本漂移或已归档时 fail closed。"""

        row = (
            self._session.execute(
                select(collection_plans_table)
                .where(collection_plans_table.c.id == plan_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError("采集计划不存在")
        if row["archived_at"] is not None:
            raise RuntimeError("已归档采集计划不能直接编辑，请先恢复")
        if row["schedule_version"] != expected_schedule_version:
            raise RuntimeError("采集计划版本已经变化，请刷新后重试")
        updated = self._session.execute(
            update(collection_plans_table)
            .where(
                collection_plans_table.c.id == plan_id,
                collection_plans_table.c.schedule_version == expected_schedule_version,
            )
            .values(
                name=name,
                schedule_expr=schedule_expr,
                enabled=enabled,
                schedule_version=collection_plans_table.c.schedule_version + 1,
                next_run_at=None,
                updated_at=func.clock_timestamp(),
            )
            .returning(collection_plans_table.c.id)
        ).scalar_one_or_none()
        if updated != plan_id:
            raise RuntimeError("采集计划版本已经变化，请刷新后重试")

        self._session.execute(
            delete(collection_plan_platforms_table).where(
                collection_plan_platforms_table.c.plan_id == plan_id
            )
        )
        self._session.execute(
            delete(collection_plan_keyword_packs_table).where(
                collection_plan_keyword_packs_table.c.plan_id == plan_id
            )
        )
        self._session.execute(
            delete(collection_plan_vehicle_models_table).where(
                collection_plan_vehicle_models_table.c.plan_id == plan_id
            )
        )
        self._session.execute(
            insert(collection_plan_platforms_table),
            [
                {
                    "plan_id": plan_id,
                    "platform": item.platform,
                    "provider_config_id": item.provider_config_id,
                    "config": item.config,
                }
                for item in platforms
            ],
        )
        if keyword_pack_ids:
            self._session.execute(
                insert(collection_plan_keyword_packs_table),
                [{"plan_id": plan_id, "keyword_pack_id": pack_id} for pack_id in keyword_pack_ids],
            )
        if vehicle_model_ids:
            self._session.execute(
                insert(collection_plan_vehicle_models_table),
                [
                    {"plan_id": plan_id, "vehicle_model_id": model_id}
                    for model_id in vehicle_model_ids
                ],
            )
        return True

    def archive(self, plan_id: UUID, *, archived_at: datetime) -> bool:
        """归档后停止未来调度，但不取消已经创建的 Run/Job。"""

        updated = self._session.execute(
            update(collection_plans_table)
            .where(
                collection_plans_table.c.id == plan_id,
                collection_plans_table.c.archived_at.is_(None),
            )
            .values(
                enabled=False,
                archived_at=archived_at,
                schedule_version=collection_plans_table.c.schedule_version + 1,
                next_run_at=None,
                updated_at=func.clock_timestamp(),
            )
            .returning(collection_plans_table.c.id)
        ).scalar_one_or_none()
        return updated == plan_id

    def restore(self, plan_id: UUID) -> bool:
        """恢复归档计划；保持停用，避免恢复动作本身触发采集。"""

        updated = self._session.execute(
            update(collection_plans_table)
            .where(
                collection_plans_table.c.id == plan_id,
                collection_plans_table.c.archived_at.is_not(None),
            )
            .values(
                archived_at=None,
                enabled=False,
                schedule_version=collection_plans_table.c.schedule_version + 1,
                next_run_at=None,
                updated_at=func.clock_timestamp(),
            )
            .returning(collection_plans_table.c.id)
        ).scalar_one_or_none()
        return updated == plan_id

    def list_archived(self) -> tuple[ArchivedCollectionPlanRecord, ...]:
        """按最近归档顺序读取计划。"""

        rows = self._session.execute(
            select(
                collection_plans_table.c.id,
                collection_plans_table.c.name,
                collection_plans_table.c.archived_at,
            )
            .where(collection_plans_table.c.archived_at.is_not(None))
            .order_by(collection_plans_table.c.archived_at.desc(), collection_plans_table.c.id)
        ).mappings()
        return tuple(
            ArchivedCollectionPlanRecord(
                id=cast(UUID, row["id"]),
                name=cast(str, row["name"]),
                archived_at=cast(datetime, row["archived_at"]),
            )
            for row in rows
        )

    def delete_blockers(self, plan_id: UUID) -> tuple[str, ...]:
        """只有已归档且从未形成 Occurrence/Run 的计划允许物理删除。"""

        row = (
            self._session.execute(
                select(collection_plans_table.c.id, collection_plans_table.c.archived_at).where(
                    collection_plans_table.c.id == plan_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return ("资源不存在",)
        blockers: list[str] = []
        if row["archived_at"] is None:
            blockers.append("请先归档采集计划再执行永久删除")
        if (
            self._session.scalar(
                select(collection_schedule_occurrences_table.c.id)
                .where(collection_schedule_occurrences_table.c.plan_id == plan_id)
                .limit(1)
            )
            is not None
        ):
            blockers.append("该计划已经产生调度历史")
        if (
            self._session.scalar(
                select(collection_runs_table.c.id)
                .where(collection_runs_table.c.manual_plan_id == plan_id)
                .limit(1)
            )
            is not None
        ):
            blockers.append("该计划已经产生采集运行历史")
        return tuple(blockers)

    def delete_archived(self, plan_id: UUID) -> bool:
        """永久删除从未运行过的归档计划及其当前配置关系。"""

        self._session.execute(
            delete(collection_plan_platforms_table).where(
                collection_plan_platforms_table.c.plan_id == plan_id
            )
        )
        self._session.execute(
            delete(collection_plan_keyword_packs_table).where(
                collection_plan_keyword_packs_table.c.plan_id == plan_id
            )
        )
        self._session.execute(
            delete(collection_plan_vehicle_models_table).where(
                collection_plan_vehicle_models_table.c.plan_id == plan_id
            )
        )
        self._session.execute(
            delete(collection_plan_decision_policies_table).where(
                collection_plan_decision_policies_table.c.plan_id == plan_id
            )
        )
        deleted = self._session.execute(
            delete(collection_plans_table)
            .where(
                collection_plans_table.c.id == plan_id,
                collection_plans_table.c.archived_at.is_not(None),
            )
            .returning(collection_plans_table.c.id)
        ).scalar_one_or_none()
        return deleted == plan_id


__all__ = [
    "ArchivedCollectionPlanRecord",
    "PostgresCollectionPlanLifecycleRepository",
]
