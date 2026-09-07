"""Keyword Pack 编辑、复制、归档与条件删除的 System Owner Repository。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.tables import (
    collection_plan_keyword_packs_table,
    collection_runs_table,
)
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaigns_table
from aima_ugc.modules.system.lifecycle_schema import register_system_lifecycle_schema
from aima_ugc.modules.system.models import KeywordPack
from aima_ugc.modules.system.tables import (
    global_relevance_config_table,
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
)
from aima_ugc.modules.vehicles.tables import keyword_pack_vehicle_models_table
from aima_ugc.platform.jobs.tables import jobs_table

register_system_lifecycle_schema()


@dataclass(frozen=True, slots=True)
class ArchivedKeywordPackRecord:
    """已归档词包的最小业务投影。"""

    id: UUID
    name: str
    archived_at: datetime


class PostgresKeywordPackLifecycleRepository:
    """只写 System Owner 词包事实；跨 Owner 表仅用于引用守卫。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def update_metadata(
        self,
        pack_id: UUID,
        *,
        expected_version: int,
        name: str,
        description: str,
    ) -> KeywordPack | None:
        """按乐观版本更新词包元数据；归档资源拒绝原地编辑。"""

        row = (
            self._session.execute(
                update(keyword_packs_table)
                .where(
                    keyword_packs_table.c.id == pack_id,
                    keyword_packs_table.c.version == expected_version,
                    keyword_packs_table.c.archived_at.is_(None),
                )
                .values(
                    name=name,
                    description=description,
                    version=keyword_packs_table.c.version + 1,
                    updated_at=func.clock_timestamp(),
                )
                .returning(keyword_packs_table)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _pack(row)

    def remove_item(
        self,
        pack_id: UUID,
        keyword_id: UUID,
        *,
        platform_scope: str,
        expected_version: int,
    ) -> KeywordPack | None:
        """从已停用词包删除一个成员；共享 Keyword 只有完全无引用时才顺带清理。"""

        parent = (
            self._session.execute(
                select(keyword_packs_table)
                .where(keyword_packs_table.c.id == pack_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if parent is None:
            return None
        if parent["archived_at"] is not None:
            raise RuntimeError("已归档词包不能修改关键词")
        if parent["enabled"]:
            raise RuntimeError("请先停用词包，再删除已有关键词")
        if parent["version"] != expected_version:
            raise RuntimeError("词包版本已经变化，请刷新后重试")
        deleted = self._session.execute(
            delete(keyword_pack_items_table)
            .where(
                keyword_pack_items_table.c.pack_id == pack_id,
                keyword_pack_items_table.c.keyword_id == keyword_id,
                keyword_pack_items_table.c.platform_scope == platform_scope,
            )
            .returning(keyword_pack_items_table.c.keyword_id)
        ).scalar_one_or_none()
        if deleted is None:
            raise LookupError("词包中不存在该关键词")
        self._session.execute(
            update(keyword_packs_table)
            .where(keyword_packs_table.c.id == pack_id)
            .values(
                version=keyword_packs_table.c.version + 1,
                updated_at=func.clock_timestamp(),
            )
        )
        still_referenced = self._session.scalar(
            select(keyword_pack_items_table.c.keyword_id)
            .where(keyword_pack_items_table.c.keyword_id == keyword_id)
            .limit(1)
        )
        if still_referenced is None:
            self._session.execute(delete(keywords_table).where(keywords_table.c.id == keyword_id))
        updated = self._session.execute(
            select(keyword_packs_table).where(keyword_packs_table.c.id == pack_id)
        ).mappings().one()
        return _pack(updated)

    def copy_pack(self, pack_id: UUID, *, name: str) -> KeywordPack | None:
        """复制词包内容与车型关系；副本固定从停用、未归档状态开始。"""

        source = self._session.execute(
            select(keyword_packs_table).where(keyword_packs_table.c.id == pack_id)
        ).mappings().one_or_none()
        if source is None:
            return None
        new_id = uuid4()
        now = func.clock_timestamp()
        row = (
            self._session.execute(
                insert(keyword_packs_table)
                .values(
                    id=new_id,
                    name=name,
                    description=source["description"],
                    enabled=False,
                    version=1,
                    archived_at=None,
                    created_at=now,
                    updated_at=now,
                )
                .returning(keyword_packs_table)
            )
            .mappings()
            .one()
        )
        items = tuple(
            self._session.execute(
                select(keyword_pack_items_table).where(
                    keyword_pack_items_table.c.pack_id == pack_id
                )
            ).mappings()
        )
        if items:
            self._session.execute(
                insert(keyword_pack_items_table),
                [
                    {
                        "pack_id": new_id,
                        "keyword_id": item["keyword_id"],
                        "platform_scope": item["platform_scope"],
                        "priority": item["priority"],
                        "enabled": item["enabled"],
                        "note": item["note"],
                    }
                    for item in items
                ],
            )
        vehicle_ids = tuple(
            self._session.scalars(
                select(keyword_pack_vehicle_models_table.c.vehicle_model_id).where(
                    keyword_pack_vehicle_models_table.c.keyword_pack_id == pack_id
                )
            )
        )
        if vehicle_ids:
            self._session.execute(
                insert(keyword_pack_vehicle_models_table),
                [
                    {"keyword_pack_id": new_id, "vehicle_model_id": vehicle_id}
                    for vehicle_id in vehicle_ids
                ],
            )
        return _pack(row)

    def archive(self, pack_id: UUID, *, archived_at: datetime) -> KeywordPack | None:
        """归档词包并强制停用；业务引用冲突由 Application Service 先行守卫。"""

        row = (
            self._session.execute(
                update(keyword_packs_table)
                .where(
                    keyword_packs_table.c.id == pack_id,
                    keyword_packs_table.c.archived_at.is_(None),
                )
                .values(
                    enabled=False,
                    archived_at=archived_at,
                    version=keyword_packs_table.c.version + 1,
                    updated_at=func.clock_timestamp(),
                )
                .returning(keyword_packs_table)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _pack(row)

    def restore(self, pack_id: UUID) -> KeywordPack | None:
        """恢复归档词包；保持停用，必须由用户显式重新启用。"""

        row = (
            self._session.execute(
                update(keyword_packs_table)
                .where(
                    keyword_packs_table.c.id == pack_id,
                    keyword_packs_table.c.archived_at.is_not(None),
                )
                .values(
                    archived_at=None,
                    enabled=False,
                    version=keyword_packs_table.c.version + 1,
                    updated_at=func.clock_timestamp(),
                )
                .returning(keyword_packs_table)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _pack(row)

    def list_archived(self) -> tuple[ArchivedKeywordPackRecord, ...]:
        """按最近归档顺序返回已归档词包。"""

        rows = self._session.execute(
            select(
                keyword_packs_table.c.id,
                keyword_packs_table.c.name,
                keyword_packs_table.c.archived_at,
            )
            .where(keyword_packs_table.c.archived_at.is_not(None))
            .order_by(keyword_packs_table.c.archived_at.desc(), keyword_packs_table.c.id)
        ).mappings()
        return tuple(
            ArchivedKeywordPackRecord(
                id=cast(UUID, row["id"]),
                name=cast(str, row["name"]),
                archived_at=cast(datetime, row["archived_at"]),
            )
            for row in rows
        )

    def archive_blockers(self, pack_id: UUID) -> tuple[str, ...]:
        """返回会被立即破坏的活动业务引用。"""

        blockers: list[str] = []
        if self._session.scalar(
            select(global_relevance_config_table.c.keyword_pack_id).where(
                global_relevance_config_table.c.keyword_pack_id == pack_id
            )
        ) is not None:
            blockers.append("当前全局相关性正在使用该词包")
        from aima_ugc.modules.collection.tables import collection_plans_table

        if self._session.scalar(
            select(collection_plan_keyword_packs_table.c.plan_id)
            .join(
                collection_plans_table,
                collection_plans_table.c.id == collection_plan_keyword_packs_table.c.plan_id,
            )
            .where(
                collection_plan_keyword_packs_table.c.keyword_pack_id == pack_id,
                collection_plans_table.c.enabled.is_(True),
            )
            .limit(1)
        ) is not None:
            blockers.append("启用中的采集计划正在使用该词包")
        return tuple(blockers)

    def delete_blockers(self, pack_id: UUID) -> tuple[str, ...]:
        """保守检查当前关系与历史冻结快照；存在任何业务历史就只允许归档。"""

        blockers = list(self.archive_blockers(pack_id))
        pack = self._session.execute(
            select(keyword_packs_table.c.archived_at).where(keyword_packs_table.c.id == pack_id)
        ).scalar_one_or_none()
        if pack is None:
            return ("资源不存在",)
        if pack is None or not isinstance(pack, datetime):
            blockers.append("请先归档词包再执行永久删除")
        if self._session.scalar(
            select(collection_plan_keyword_packs_table.c.plan_id)
            .where(collection_plan_keyword_packs_table.c.keyword_pack_id == pack_id)
            .limit(1)
        ) is not None:
            blockers.append("采集计划历史引用了该词包")
        pack_marker = [{"id": str(pack_id)}]
        if self._session.scalar(
            select(historical_import_campaigns_table.c.id)
            .where(
                historical_import_campaigns_table.c.keyword_pack_snapshot["keyword_packs"].contains(
                    pack_marker
                )
            )
            .limit(1)
        ) is not None:
            blockers.append("数据导入历史引用了该词包")
        if self._session.scalar(
            select(jobs_table.c.id)
            .where(jobs_table.c.payload["keyword_selection"]["keyword_packs"].contains(pack_marker))
            .limit(1)
        ) is not None:
            blockers.append("导入任务历史引用了该词包")
        if self._session.scalar(
            select(collection_runs_table.c.id)
            .where(collection_runs_table.c.config_snapshot.cast(str).contains(str(pack_id)))
            .limit(1)
        ) is not None:
            blockers.append("采集运行历史引用了该词包")
        return tuple(dict.fromkeys(blockers))

    def delete_archived(self, pack_id: UUID) -> bool:
        """永久删除已通过引用守卫的归档词包；共享 Keyword 只清理孤儿。"""

        keyword_ids = tuple(
            self._session.scalars(
                select(keyword_pack_items_table.c.keyword_id).where(
                    keyword_pack_items_table.c.pack_id == pack_id
                )
            )
        )
        self._session.execute(
            delete(keyword_pack_vehicle_models_table).where(
                keyword_pack_vehicle_models_table.c.keyword_pack_id == pack_id
            )
        )
        self._session.execute(
            delete(keyword_pack_items_table).where(keyword_pack_items_table.c.pack_id == pack_id)
        )
        deleted = self._session.execute(
            delete(keyword_packs_table)
            .where(
                keyword_packs_table.c.id == pack_id,
                keyword_packs_table.c.archived_at.is_not(None),
            )
            .returning(keyword_packs_table.c.id)
        ).scalar_one_or_none()
        if deleted is None:
            return False
        for keyword_id in keyword_ids:
            still_used = self._session.scalar(
                select(keyword_pack_items_table.c.keyword_id)
                .where(keyword_pack_items_table.c.keyword_id == keyword_id)
                .limit(1)
            )
            if still_used is None:
                self._session.execute(
                    delete(keywords_table).where(keywords_table.c.id == keyword_id)
                )
        return True


def _pack(row) -> KeywordPack:
    """把词包表行映射为现有领域对象。"""

    return KeywordPack(
        id=cast(UUID, row["id"]),
        name=cast(str, row["name"]),
        description=cast(str, row["description"]),
        enabled=cast(bool, row["enabled"]),
        version=cast(int, row["version"]),
    )


__all__ = ["ArchivedKeywordPackRecord", "PostgresKeywordPackLifecycleRepository"]
