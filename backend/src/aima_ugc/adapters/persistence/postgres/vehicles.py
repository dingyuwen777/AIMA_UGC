"""Vehicle Catalog、词包引用、任务快照和内容证据 PostgreSQL Repository。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult, RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.tables import collection_plan_vehicle_models_table
from aima_ugc.modules.vehicles.models import (
    ContentVehicleEvidence,
    VehicleAlias,
    VehicleCatalogSnapshot,
    VehicleModel,
    VehicleStatus,
    normalize_vehicle_text,
)
from aima_ugc.modules.vehicles.tables import (
    content_vehicle_evidence_table,
    content_vehicle_review_locks_table,
    keyword_pack_vehicle_models_table,
    vehicle_catalog_versions_table,
    vehicle_model_aliases_table,
    vehicle_models_table,
)
from aima_ugc.platform.time import beijing_now


def _vehicle_from_row(row: RowMapping) -> VehicleModel:
    """把数据库行投影为稳定车型领域对象。"""

    return VehicleModel(
        id=cast(UUID, row["id"]),
        code=cast(str, row["code"]),
        display_name=cast(str, row["display_name"]),
        status=cast(VehicleStatus, row["status"]),
        version=cast(int, row["version"]),
        catalog_version=cast(int, row["catalog_version"]),
        merged_into_id=cast(UUID | None, row["merged_into_id"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


class PostgresVehicleCatalogRepository:
    """车型目录唯一写 Owner；调用方拥有事务。"""

    def __init__(self, session: Session) -> None:
        """绑定调用方拥有的车型目录事务。"""

        self._session = session

    def current_catalog_version(self) -> int:
        """返回当前目录版本；Migration 始终播种 version=1。"""

        value = self._session.scalar(select(func.max(vehicle_catalog_versions_table.c.version)))
        if value is None:
            raise RuntimeError("Vehicle Catalog 尚未初始化")
        return int(value)

    def next_catalog_version(self, *, reason: str, actor_ref: str) -> int:
        """锁定永久 seed 行后读取最大版本，串行化并发目录写入。"""

        seed = self._session.scalar(
            select(vehicle_catalog_versions_table.c.version)
            .where(vehicle_catalog_versions_table.c.version == 1)
            .with_for_update()
        )
        if seed is None:
            raise RuntimeError("Vehicle Catalog 尚未初始化")
        current = self._session.scalar(select(func.max(vehicle_catalog_versions_table.c.version)))
        next_version = int(current or 1) + 1
        self._session.execute(
            insert(vehicle_catalog_versions_table).values(
                version=next_version,
                reason=reason,
                actor_ref=actor_ref,
                created_at=beijing_now(),
            )
        )
        return next_version

    def create_model(
        self,
        *,
        code: str,
        display_name: str,
        aliases: tuple[str, ...],
        actor_ref: str,
    ) -> VehicleModel:
        """创建车型并在同一事务追加目录版本和别名。"""

        catalog_version = self.next_catalog_version(reason="vehicle_created", actor_ref=actor_ref)
        model_id = uuid4()
        now = beijing_now()
        row = (
            self._session.execute(
                insert(vehicle_models_table)
                .values(
                    id=model_id,
                    code=code,
                    display_name=display_name,
                    status="active",
                    version=1,
                    catalog_version=catalog_version,
                    created_at=now,
                    updated_at=now,
                )
                .returning(vehicle_models_table)
            )
            .mappings()
            .one()
        )
        self._replace_aliases(model_id, aliases, created_at=now)
        return _vehicle_from_row(row)

    def get_model(self, model_id: UUID, *, for_update: bool = False) -> VehicleModel | None:
        """按稳定 ID 读取车型，可选择行锁。"""

        statement = select(vehicle_models_table).where(vehicle_models_table.c.id == model_id)
        if for_update:
            statement = statement.with_for_update()
        row = self._session.execute(statement).mappings().one_or_none()
        return None if row is None else _vehicle_from_row(row)

    def list_models(
        self,
        *,
        search: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[tuple[VehicleModel, ...], int]:
        """返回管理目录页和同条件总数。"""

        conditions = []
        if search is not None:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            alias_match = select(vehicle_model_aliases_table.c.id).where(
                vehicle_model_aliases_table.c.vehicle_model_id == vehicle_models_table.c.id,
                vehicle_model_aliases_table.c.text.ilike(pattern, escape="\\"),
            )
            conditions.append(
                or_(
                    vehicle_models_table.c.code.ilike(pattern, escape="\\"),
                    vehicle_models_table.c.display_name.ilike(pattern, escape="\\"),
                    alias_match.exists(),
                )
            )
        if status is not None:
            conditions.append(vehicle_models_table.c.status == status)
        base = select(vehicle_models_table)
        count_statement = select(func.count()).select_from(vehicle_models_table)
        if conditions:
            base = base.where(*conditions)
            count_statement = count_statement.where(*conditions)
        rows = self._session.execute(
            base.order_by(vehicle_models_table.c.code, vehicle_models_table.c.id)
            .offset(offset)
            .limit(limit)
        ).mappings()
        return tuple(_vehicle_from_row(row) for row in rows), int(
            self._session.scalar(count_statement) or 0
        )

    def list_aliases(self, model_id: UUID) -> tuple[VehicleAlias, ...]:
        """按规范化身份返回车型别名。"""

        rows = self._session.execute(
            select(vehicle_model_aliases_table)
            .where(vehicle_model_aliases_table.c.vehicle_model_id == model_id)
            .order_by(vehicle_model_aliases_table.c.normalized_text)
        ).mappings()
        return tuple(
            VehicleAlias(
                id=cast(UUID, row["id"]),
                vehicle_model_id=cast(UUID, row["vehicle_model_id"]),
                text=cast(str, row["text"]),
                normalized_text=cast(str, row["normalized_text"]),
            )
            for row in rows
        )

    def update_model(
        self,
        model_id: UUID,
        *,
        display_name: str | None,
        aliases: tuple[str, ...] | None,
        status: str | None,
        actor_ref: str,
    ) -> VehicleModel:
        """更新车型并递增车型版本和全局目录版本。"""

        current = self.get_model(model_id, for_update=True)
        if current is None:
            raise LookupError(model_id)
        if current.status == "merged":
            raise RuntimeError("已合并车型不能直接编辑")
        catalog_version = self.next_catalog_version(reason="vehicle_updated", actor_ref=actor_ref)
        values: dict[str, object] = {
            "version": current.version + 1,
            "catalog_version": catalog_version,
            "updated_at": beijing_now(),
        }
        if display_name is not None:
            values["display_name"] = display_name
        if status is not None:
            values["status"] = status
        row = (
            self._session.execute(
                update(vehicle_models_table)
                .where(vehicle_models_table.c.id == model_id)
                .values(**values)
                .returning(vehicle_models_table)
            )
            .mappings()
            .one()
        )
        if aliases is not None:
            self._replace_aliases(model_id, aliases, created_at=beijing_now())
        return _vehicle_from_row(row)

    def merge_model(self, source_id: UUID, target_id: UUID, *, actor_ref: str) -> VehicleModel:
        """把源车型重定向到目标；历史证据继续保留源身份。"""

        if source_id == target_id:
            raise RuntimeError("车型不能合并到自身")
        source = self.get_model(source_id, for_update=True)
        target = self.get_model(target_id, for_update=True)
        if source is None or target is None:
            raise LookupError(source_id if source is None else target_id)
        if source.status == "merged" or target.status != "active":
            raise RuntimeError("合并源必须未合并且目标必须为 active")
        catalog_version = self.next_catalog_version(reason="vehicle_merged", actor_ref=actor_ref)
        self._session.execute(
            pg_insert(keyword_pack_vehicle_models_table)
            .from_select(
                ["pack_id", "vehicle_model_id", "enabled", "created_at"],
                select(
                    keyword_pack_vehicle_models_table.c.pack_id,
                    literal(target_id),
                    keyword_pack_vehicle_models_table.c.enabled,
                    keyword_pack_vehicle_models_table.c.created_at,
                ).where(keyword_pack_vehicle_models_table.c.vehicle_model_id == source_id),
            )
            .on_conflict_do_nothing()
        )
        self._session.execute(
            delete(keyword_pack_vehicle_models_table).where(
                keyword_pack_vehicle_models_table.c.vehicle_model_id == source_id
            )
        )
        self._session.execute(
            pg_insert(collection_plan_vehicle_models_table)
            .from_select(
                ["plan_id", "vehicle_model_id"],
                select(
                    collection_plan_vehicle_models_table.c.plan_id,
                    literal(target_id),
                ).where(collection_plan_vehicle_models_table.c.vehicle_model_id == source_id),
            )
            .on_conflict_do_nothing()
        )
        self._session.execute(
            delete(collection_plan_vehicle_models_table).where(
                collection_plan_vehicle_models_table.c.vehicle_model_id == source_id
            )
        )
        self._session.execute(
            update(vehicle_models_table)
            .where(vehicle_models_table.c.merged_into_id == source_id)
            .values(
                merged_into_id=target_id,
                version=vehicle_models_table.c.version + 1,
                catalog_version=catalog_version,
                updated_at=beijing_now(),
            )
        )
        row = (
            self._session.execute(
                update(vehicle_models_table)
                .where(vehicle_models_table.c.id == source_id)
                .values(
                    status="merged",
                    merged_into_id=target_id,
                    version=source.version + 1,
                    catalog_version=catalog_version,
                    updated_at=beijing_now(),
                )
                .returning(vehicle_models_table)
            )
            .mappings()
            .one()
        )
        return _vehicle_from_row(row)

    def delete_unreferenced_model(self, model_id: UUID, *, actor_ref: str) -> bool:
        """仅物理删除从未被业务对象引用的车型。"""

        current = self.get_model(model_id, for_update=True)
        if current is None:
            return False
        if self.is_referenced(model_id):
            raise RuntimeError("已引用车型不能物理删除")
        self.next_catalog_version(reason="vehicle_deleted", actor_ref=actor_ref)
        self._session.execute(
            delete(vehicle_model_aliases_table).where(
                vehicle_model_aliases_table.c.vehicle_model_id == model_id
            )
        )
        self._session.execute(
            delete(vehicle_models_table).where(vehicle_models_table.c.id == model_id)
        )
        return True

    def is_referenced(self, model_id: UUID) -> bool:
        """检查词包、计划、内容证据或合并重定向引用。"""

        checks = (
            select(keyword_pack_vehicle_models_table.c.pack_id).where(
                keyword_pack_vehicle_models_table.c.vehicle_model_id == model_id
            ),
            select(collection_plan_vehicle_models_table.c.plan_id).where(
                collection_plan_vehicle_models_table.c.vehicle_model_id == model_id
            ),
            select(content_vehicle_evidence_table.c.id).where(
                content_vehicle_evidence_table.c.vehicle_model_id == model_id
            ),
            select(vehicle_models_table.c.id).where(
                vehicle_models_table.c.merged_into_id == model_id
            ),
        )
        return any(self._session.scalar(statement.limit(1)) is not None for statement in checks)

    def list_keyword_pack_ids(self, model_id: UUID) -> tuple[UUID, ...]:
        """返回当前引用车型的词包。"""

        return tuple(
            self._session.scalars(
                select(keyword_pack_vehicle_models_table.c.pack_id)
                .where(
                    keyword_pack_vehicle_models_table.c.vehicle_model_id == model_id,
                    keyword_pack_vehicle_models_table.c.enabled.is_(True),
                )
                .order_by(keyword_pack_vehicle_models_table.c.pack_id)
            )
        )

    def replace_keyword_pack_models(
        self,
        pack_id: UUID,
        model_ids: tuple[UUID, ...],
        *,
        actor_ref: str,
    ) -> tuple[UUID, ...]:
        """原子替换 Pack↔车型引用并递增目录版本。"""

        existing_models = tuple(
            self._session.scalars(
                select(vehicle_models_table.c.id).where(
                    vehicle_models_table.c.id.in_(model_ids),
                    vehicle_models_table.c.status == "active",
                )
            )
        )
        if len(existing_models) != len(model_ids):
            raise LookupError("车型不存在或已停用")
        self.next_catalog_version(reason="keyword_pack_vehicle_links_updated", actor_ref=actor_ref)
        self._session.execute(
            delete(keyword_pack_vehicle_models_table).where(
                keyword_pack_vehicle_models_table.c.pack_id == pack_id
            )
        )
        if model_ids:
            now = beijing_now()
            self._session.execute(
                insert(keyword_pack_vehicle_models_table),
                [
                    {
                        "pack_id": pack_id,
                        "vehicle_model_id": model_id,
                        "enabled": True,
                        "created_at": now,
                    }
                    for model_id in model_ids
                ],
            )
        return tuple(sorted(model_ids, key=str))

    def snapshot(self, model_ids: tuple[UUID, ...]) -> VehicleCatalogSnapshot:
        """冻结所选 active 车型及其别名；歧义仍由执行匹配器处理。"""

        if not model_ids:
            return VehicleCatalogSnapshot(
                catalog_version=self.current_catalog_version(),
                vehicle_model_ids=(),
                resolved_aliases=(),
            )
        rows = tuple(
            self._session.execute(
                select(
                    vehicle_models_table.c.id,
                    vehicle_models_table.c.version,
                    vehicle_model_aliases_table.c.text,
                    vehicle_model_aliases_table.c.normalized_text,
                )
                .join(
                    vehicle_model_aliases_table,
                    vehicle_model_aliases_table.c.vehicle_model_id == vehicle_models_table.c.id,
                )
                .where(
                    vehicle_models_table.c.id.in_(model_ids),
                    vehicle_models_table.c.status == "active",
                )
                .order_by(vehicle_models_table.c.id, vehicle_model_aliases_table.c.normalized_text)
            ).mappings()
        )
        found = {cast(UUID, row["id"]) for row in rows}
        if found != set(model_ids):
            raise LookupError("车型不存在、停用或没有有效别名")
        selected_normalized = {cast(str, row["normalized_text"]) for row in rows}
        global_alias_rows = self._session.execute(
            select(
                vehicle_model_aliases_table.c.normalized_text,
                vehicle_model_aliases_table.c.vehicle_model_id,
            )
            .join(
                vehicle_models_table,
                vehicle_models_table.c.id == vehicle_model_aliases_table.c.vehicle_model_id,
            )
            .where(
                vehicle_models_table.c.status == "active",
                vehicle_model_aliases_table.c.normalized_text.in_(selected_normalized),
            )
        ).mappings()
        candidates_by_alias: defaultdict[str, set[UUID]] = defaultdict(set)
        for alias_row in global_alias_rows:
            candidates_by_alias[cast(str, alias_row["normalized_text"])].add(
                cast(UUID, alias_row["vehicle_model_id"])
            )
        unambiguous_rows = tuple(
            row for row in rows if len(candidates_by_alias[cast(str, row["normalized_text"])]) == 1
        )
        if not unambiguous_rows:
            raise LookupError("所选车型没有可自动解析的非歧义别名")
        return VehicleCatalogSnapshot(
            catalog_version=self.current_catalog_version(),
            vehicle_model_ids=tuple(model_ids),
            resolved_aliases=tuple(
                dict.fromkeys(cast(str, row["text"]) for row in unambiguous_rows)
            ),
            vehicle_versions=tuple(
                dict.fromkeys((cast(UUID, row["id"]), cast(int, row["version"])) for row in rows)
            ),
            alias_bindings=tuple(
                (cast(UUID, row["id"]), cast(str, row["text"])) for row in unambiguous_rows
            ),
        )

    def resolve_alias_candidates(self, text: str) -> dict[str, tuple[UUID, ...]]:
        """返回命中的规范化别名及候选车型；多个候选保持歧义。"""

        normalized_content = normalize_vehicle_text(text)
        rows = self._session.execute(
            select(
                vehicle_model_aliases_table.c.normalized_text,
                vehicle_models_table.c.id,
                vehicle_models_table.c.merged_into_id,
            )
            .join(
                vehicle_models_table,
                vehicle_models_table.c.id == vehicle_model_aliases_table.c.vehicle_model_id,
            )
            .where(vehicle_models_table.c.status.in_(("active", "merged")))
        ).mappings()
        candidates: defaultdict[str, set[UUID]] = defaultdict(set)
        for row in rows:
            alias = cast(str, row["normalized_text"])
            if alias in normalized_content:
                candidates[alias].add(cast(UUID, row["merged_into_id"] or row["id"]))
        return {alias: tuple(sorted(model_ids, key=str)) for alias, model_ids in candidates.items()}

    def append_evidence(self, evidence: ContentVehicleEvidence) -> bool:
        """幂等追加内容车型证据；人工锁定不会被自动证据更新。"""

        if not evidence.is_manual_locked:
            locked = self._session.scalar(
                select(content_vehicle_review_locks_table.c.is_locked).where(
                    content_vehicle_review_locks_table.c.content_id == evidence.content_id,
                    content_vehicle_review_locks_table.c.content_version
                    == evidence.content_version,
                )
            )
            if locked is True:
                return False

        statement = pg_insert(content_vehicle_evidence_table).values(
            id=evidence.id,
            content_id=evidence.content_id,
            content_version=evidence.content_version,
            vehicle_model_id=evidence.vehicle_model_id,
            source=evidence.source,
            matched_text=evidence.matched_text,
            source_field=evidence.source_field,
            catalog_version=evidence.catalog_version,
            confidence=evidence.confidence,
            is_manual_locked=evidence.is_manual_locked,
            is_active=evidence.is_active,
            created_at=evidence.created_at,
        )
        if evidence.is_manual_locked:
            statement = statement.on_conflict_do_update(
                constraint="uq_content_vehicle_evidence_identity",
                set_={
                    "is_active": True,
                    "is_manual_locked": True,
                    "confidence": evidence.confidence,
                    "created_at": evidence.created_at,
                },
            )
        else:
            statement = statement.on_conflict_do_nothing(
                constraint="uq_content_vehicle_evidence_identity"
            )
        result = cast(CursorResult[Any], self._session.execute(statement))
        return bool(result.rowcount)

    def replace_manual_evidence(
        self,
        *,
        content_id: UUID,
        content_version: int,
        model_ids: tuple[UUID, ...],
        unlock_existing: bool,
        actor_ref: str,
    ) -> None:
        """写入人工车型结论；空集合也能被锁定，显式空解锁恢复自动证据。"""

        locked = self._session.scalar(
            select(content_vehicle_review_locks_table.c.is_locked)
            .where(
                content_vehicle_review_locks_table.c.content_id == content_id,
                content_vehicle_review_locks_table.c.content_version == content_version,
            )
            .with_for_update()
        )
        if locked is True and not unlock_existing:
            raise RuntimeError("已有人工锁定车型，必须显式解锁后才能修改")
        active_models = set(
            self._session.scalars(
                select(vehicle_models_table.c.id).where(
                    vehicle_models_table.c.id.in_(model_ids),
                    vehicle_models_table.c.status == "active",
                )
            )
        )
        if active_models != set(model_ids):
            raise LookupError("车型不存在或不可用")
        self._session.execute(
            update(content_vehicle_evidence_table)
            .where(
                content_vehicle_evidence_table.c.content_id == content_id,
                content_vehicle_evidence_table.c.content_version == content_version,
                content_vehicle_evidence_table.c.is_active.is_(True),
            )
            .values(is_active=False)
        )
        should_lock = not (unlock_existing and not model_ids)
        self._session.execute(
            pg_insert(content_vehicle_review_locks_table)
            .values(
                content_id=content_id,
                content_version=content_version,
                is_locked=should_lock,
                actor_ref=actor_ref,
                updated_at=beijing_now(),
            )
            .on_conflict_do_update(
                index_elements=[
                    content_vehicle_review_locks_table.c.content_id,
                    content_vehicle_review_locks_table.c.content_version,
                ],
                set_={
                    "is_locked": should_lock,
                    "actor_ref": actor_ref,
                    "updated_at": beijing_now(),
                },
            )
        )
        if not should_lock:
            return
        catalog_version = self.current_catalog_version()
        for model_id in model_ids:
            self.append_evidence(
                ContentVehicleEvidence(
                    id=uuid4(),
                    content_id=content_id,
                    content_version=content_version,
                    vehicle_model_id=model_id,
                    source="manual_review",
                    matched_text=None,
                    source_field=None,
                    catalog_version=catalog_version,
                    confidence=1.0,
                    is_manual_locked=True,
                    is_active=True,
                    created_at=beijing_now(),
                )
            )

    def _replace_aliases(
        self,
        model_id: UUID,
        aliases: tuple[str, ...],
        *,
        created_at: datetime,
    ) -> None:
        """替换单车型别名；跨车型同名保留为待消歧候选。"""

        self._session.execute(
            delete(vehicle_model_aliases_table).where(
                vehicle_model_aliases_table.c.vehicle_model_id == model_id
            )
        )
        if aliases:
            self._session.execute(
                insert(vehicle_model_aliases_table),
                [
                    {
                        "id": uuid4(),
                        "vehicle_model_id": model_id,
                        "text": alias,
                        "normalized_text": normalize_vehicle_text(alias),
                        "created_at": created_at,
                    }
                    for alias in aliases
                ],
            )


__all__ = ["PostgresVehicleCatalogRepository"]
