"""Stage 2 Brand/Vehicle 统一目录与品牌证据 PostgreSQL Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.vehicles.models import (
    Brand,
    BrandAlias,
    BrandRole,
    BrandStatus,
    CatalogFilterMode,
    CatalogSnapshot,
    ContentBrandEvidence,
    ContentVehicleEvidence,
    VehicleAlias,
    VehicleModel,
    VehicleStatus,
    normalize_vehicle_text,
)
from aima_ugc.modules.vehicles.tables import (
    content_brand_evidence_table,
    content_brand_review_locks_table,
    content_vehicle_evidence_table,
    content_vehicle_review_locks_table,
    vehicle_brand_aliases_table,
    vehicle_brands_table,
    vehicle_model_aliases_table,
    vehicle_models_table,
)
from aima_ugc.platform.time import beijing_now

from .vehicles import PostgresVehicleCatalogRepository


def _brand_from_row(row: RowMapping) -> Brand:
    return Brand(
        id=cast(UUID, row["id"]),
        code=cast(str, row["code"]),
        display_name=cast(str, row["display_name"]),
        role=cast(BrandRole, row["role"]),
        status=cast(BrandStatus, row["status"]),
        version=cast(int, row["version"]),
        catalog_version=cast(int, row["catalog_version"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _vehicle_from_row(row: RowMapping) -> VehicleModel:
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
        series_name=cast(str | None, row["series_name"]),
        category_name=cast(str | None, row["category_name"]),
        brand_id=cast(UUID | None, row["brand_id"]),
    )


class PostgresBrandVehicleCatalogRepository:
    """Stage 2 Brand 管理、统一快照、车型品牌归属和证据写入 Owner。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._vehicle_catalog = PostgresVehicleCatalogRepository(session)

    def current_catalog_version(self) -> int:
        return self._vehicle_catalog.current_catalog_version()

    def create_brand(
        self,
        *,
        code: str,
        display_name: str,
        role: BrandRole,
        aliases: tuple[str, ...],
        actor_ref: str,
    ) -> Brand:
        catalog_version = self._vehicle_catalog.next_catalog_version(
            reason="brand_created", actor_ref=actor_ref
        )
        brand_id = uuid4()
        now = beijing_now()
        row = (
            self._session.execute(
                insert(vehicle_brands_table)
                .values(
                    id=brand_id,
                    code=code,
                    display_name=display_name,
                    role=role,
                    status="active",
                    version=1,
                    catalog_version=catalog_version,
                    created_at=now,
                    updated_at=now,
                )
                .returning(vehicle_brands_table)
            )
            .mappings()
            .one()
        )
        self._replace_brand_aliases(brand_id, aliases, created_at=now)
        return _brand_from_row(row)

    def get_brand(self, brand_id: UUID, *, for_update: bool = False) -> Brand | None:
        statement = select(vehicle_brands_table).where(vehicle_brands_table.c.id == brand_id)
        if for_update:
            statement = statement.with_for_update()
        row = self._session.execute(statement).mappings().one_or_none()
        return None if row is None else _brand_from_row(row)

    def list_brands(
        self,
        *,
        search: str | None,
        role: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[tuple[Brand, ...], int]:
        conditions = []
        if search is not None:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            alias_match = select(vehicle_brand_aliases_table.c.id).where(
                vehicle_brand_aliases_table.c.brand_id == vehicle_brands_table.c.id,
                vehicle_brand_aliases_table.c.text.ilike(pattern, escape="\\"),
            )
            from sqlalchemy import or_

            conditions.append(
                or_(
                    vehicle_brands_table.c.code.ilike(pattern, escape="\\"),
                    vehicle_brands_table.c.display_name.ilike(pattern, escape="\\"),
                    alias_match.exists(),
                )
            )
        if role is not None:
            conditions.append(vehicle_brands_table.c.role == role)
        if status is not None:
            conditions.append(vehicle_brands_table.c.status == status)
        statement = select(vehicle_brands_table)
        count_statement = select(func.count()).select_from(vehicle_brands_table)
        if conditions:
            statement = statement.where(*conditions)
            count_statement = count_statement.where(*conditions)
        rows = self._session.execute(
            statement.order_by(vehicle_brands_table.c.code, vehicle_brands_table.c.id)
            .offset(offset)
            .limit(limit)
        ).mappings()
        return tuple(_brand_from_row(row) for row in rows), int(
            self._session.scalar(count_statement) or 0
        )

    def list_brand_aliases(self, brand_id: UUID) -> tuple[BrandAlias, ...]:
        rows = self._session.execute(
            select(vehicle_brand_aliases_table)
            .where(vehicle_brand_aliases_table.c.brand_id == brand_id)
            .order_by(vehicle_brand_aliases_table.c.normalized_text)
        ).mappings()
        return tuple(
            BrandAlias(
                id=cast(UUID, row["id"]),
                brand_id=cast(UUID, row["brand_id"]),
                text=cast(str, row["text"]),
                normalized_text=cast(str, row["normalized_text"]),
            )
            for row in rows
        )

    def update_brand(
        self,
        brand_id: UUID,
        *,
        display_name: str | None,
        role: BrandRole | None,
        status: BrandStatus | None,
        aliases: tuple[str, ...] | None,
        actor_ref: str,
    ) -> Brand:
        current = self.get_brand(brand_id, for_update=True)
        if current is None:
            raise LookupError(brand_id)
        if status == "deprecated" and self._has_active_vehicle(brand_id):
            raise RuntimeError("仍有 active 车型的品牌不能停用")
        catalog_version = self._vehicle_catalog.next_catalog_version(
            reason="brand_updated", actor_ref=actor_ref
        )
        values: dict[str, object] = {
            "version": current.version + 1,
            "catalog_version": catalog_version,
            "updated_at": beijing_now(),
        }
        if display_name is not None:
            values["display_name"] = display_name
        if role is not None:
            values["role"] = role
        if status is not None:
            values["status"] = status
        row = (
            self._session.execute(
                update(vehicle_brands_table)
                .where(vehicle_brands_table.c.id == brand_id)
                .values(**values)
                .returning(vehicle_brands_table)
            )
            .mappings()
            .one()
        )
        if aliases is not None:
            self._replace_brand_aliases(brand_id, aliases, created_at=beijing_now())
        return _brand_from_row(row)

    def is_brand_referenced(self, brand_id: UUID) -> bool:
        return (
            self._session.scalar(
                select(vehicle_models_table.c.id)
                .where(vehicle_models_table.c.brand_id == brand_id)
                .limit(1)
            )
            is not None
            or self._session.scalar(
                select(content_brand_evidence_table.c.id)
                .where(content_brand_evidence_table.c.brand_id == brand_id)
                .limit(1)
            )
            is not None
        )

    def delete_unreferenced_brand(self, brand_id: UUID, *, actor_ref: str) -> bool:
        current = self.get_brand(brand_id, for_update=True)
        if current is None:
            return False
        if self.is_brand_referenced(brand_id):
            raise RuntimeError("已被车型或内容证据引用的品牌不能物理删除")
        self._vehicle_catalog.next_catalog_version(reason="brand_deleted", actor_ref=actor_ref)
        self._session.execute(
            delete(vehicle_brand_aliases_table).where(
                vehicle_brand_aliases_table.c.brand_id == brand_id
            )
        )
        self._session.execute(
            delete(vehicle_brands_table).where(vehicle_brands_table.c.id == brand_id)
        )
        return True

    def get_vehicle_model(self, vehicle_model_id: UUID) -> VehicleModel | None:
        return self._vehicle_catalog.get_model(vehicle_model_id)

    def assign_vehicle_brand(
        self,
        vehicle_model_id: UUID,
        brand_id: UUID | None,
        *,
        actor_ref: str,
    ) -> VehicleModel:
        """委托 Vehicle Catalog 唯一写 Owner 修改品牌归属。"""

        return self._vehicle_catalog.assign_brand(
            vehicle_model_id,
            brand_id,
            actor_ref=actor_ref,
        )

    def active_vehicle_ids_missing_brand(self) -> tuple[UUID, ...]:
        """返回品牌为空或所属 Brand 非 active 的 active Vehicle。"""

        joined = vehicle_models_table.outerjoin(
            vehicle_brands_table,
            vehicle_brands_table.c.id == vehicle_models_table.c.brand_id,
        )
        return tuple(
            self._session.scalars(
                select(vehicle_models_table.c.id)
                .select_from(joined)
                .where(
                    vehicle_models_table.c.status == "active",
                    or_(
                        vehicle_models_table.c.brand_id.is_(None),
                        vehicle_brands_table.c.id.is_(None),
                        vehicle_brands_table.c.status != "active",
                    ),
                )
                .order_by(vehicle_models_table.c.id)
            )
        )

    def catalog_snapshot(
        self,
        *,
        filter_mode: CatalogFilterMode = "all_active",
        selected_brand_ids: tuple[UUID, ...] = (),
    ) -> CatalogSnapshot:
        """冻结 Brand/Vehicle/Alias scope；同一事务期间阻止目录版本写穿透。"""

        if filter_mode == "selected":
            if not selected_brand_ids:
                raise ValueError("selected 模式必须至少选择一个品牌")
            if len(selected_brand_ids) != len(set(selected_brand_ids)):
                raise ValueError("selected_brand_ids 不能重复")
        elif selected_brand_ids:
            raise ValueError("all_active 模式不能同时传 selected_brand_ids")

        catalog_version = self._vehicle_catalog.lock_catalog_version()
        if filter_mode == "all_active" and self.active_vehicle_ids_missing_brand():
            raise RuntimeError(
                "仍有 active 车型缺少有效 active Brand，不能冻结 all_active Snapshot"
            )

        brand_statement = select(vehicle_brands_table).where(
            vehicle_brands_table.c.status == "active"
        )
        if filter_mode == "selected":
            brand_statement = brand_statement.where(
                vehicle_brands_table.c.id.in_(selected_brand_ids)
            )
        brands = tuple(
            _brand_from_row(row)
            for row in self._session.execute(
                brand_statement.order_by(vehicle_brands_table.c.code, vehicle_brands_table.c.id)
            ).mappings()
        )
        brand_ids = {item.id for item in brands}
        if filter_mode == "selected" and brand_ids != set(selected_brand_ids):
            raise LookupError("所选品牌不存在或已停用")

        brand_aliases = (
            tuple(
                BrandAlias(
                    id=cast(UUID, row["id"]),
                    brand_id=cast(UUID, row["brand_id"]),
                    text=cast(str, row["text"]),
                    normalized_text=cast(str, row["normalized_text"]),
                )
                for row in self._session.execute(
                    select(vehicle_brand_aliases_table)
                    .where(vehicle_brand_aliases_table.c.brand_id.in_(brand_ids))
                    .order_by(
                        vehicle_brand_aliases_table.c.brand_id,
                        vehicle_brand_aliases_table.c.normalized_text,
                    )
                ).mappings()
            )
            if brand_ids
            else ()
        )
        vehicles = (
            tuple(
                _vehicle_from_row(row)
                for row in self._session.execute(
                    select(vehicle_models_table)
                    .where(
                        vehicle_models_table.c.status == "active",
                        vehicle_models_table.c.brand_id.in_(brand_ids),
                    )
                    .order_by(vehicle_models_table.c.code, vehicle_models_table.c.id)
                ).mappings()
            )
            if brand_ids
            else ()
        )
        vehicle_ids = {item.id for item in vehicles}
        vehicle_aliases = (
            tuple(
                VehicleAlias(
                    id=cast(UUID, row["id"]),
                    vehicle_model_id=cast(UUID, row["vehicle_model_id"]),
                    text=cast(str, row["text"]),
                    normalized_text=cast(str, row["normalized_text"]),
                )
                for row in self._session.execute(
                    select(vehicle_model_aliases_table)
                    .where(vehicle_model_aliases_table.c.vehicle_model_id.in_(vehicle_ids))
                    .order_by(
                        vehicle_model_aliases_table.c.vehicle_model_id,
                        vehicle_model_aliases_table.c.normalized_text,
                    )
                ).mappings()
            )
            if vehicle_ids
            else ()
        )
        return CatalogSnapshot(
            catalog_version=catalog_version,
            brands=brands,
            brand_aliases=brand_aliases,
            vehicles=vehicles,
            vehicle_aliases=vehicle_aliases,
            filter_mode=filter_mode,
            selected_brand_ids=(
                tuple(sorted(selected_brand_ids, key=str)) if filter_mode == "selected" else ()
            ),
        )

    def replace_automatic_brand_evidence(
        self,
        *,
        content_id: UUID,
        content_version: int,
        evidence: tuple[ContentBrandEvidence, ...],
    ) -> bool:
        if self._is_locked(content_brand_review_locks_table, content_id, content_version):
            return False
        self._session.execute(
            update(content_brand_evidence_table)
            .where(
                content_brand_evidence_table.c.content_id == content_id,
                content_brand_evidence_table.c.content_version == content_version,
                content_brand_evidence_table.c.is_manual_locked.is_(False),
                content_brand_evidence_table.c.is_active.is_(True),
            )
            .values(is_active=False)
        )
        for item in evidence:
            if item.is_manual_locked or item.source == "manual_review":
                raise ValueError("自动品牌证据不能伪装成人工锁定证据")
            statement = pg_insert(content_brand_evidence_table).values(
                id=item.id,
                content_id=item.content_id,
                content_version=item.content_version,
                brand_id=item.brand_id,
                source=item.source,
                matched_text=item.matched_text,
                source_field=item.source_field,
                derived_vehicle_model_id=item.derived_vehicle_model_id,
                catalog_version=item.catalog_version,
                confidence=item.confidence,
                is_manual_locked=False,
                is_active=True,
                created_at=item.created_at,
            )
            if item.derived_vehicle_model_id is None:
                statement = statement.on_conflict_do_update(
                    index_elements=[
                        content_brand_evidence_table.c.content_id,
                        content_brand_evidence_table.c.content_version,
                        content_brand_evidence_table.c.brand_id,
                        content_brand_evidence_table.c.source,
                        content_brand_evidence_table.c.catalog_version,
                    ],
                    index_where=content_brand_evidence_table.c.derived_vehicle_model_id.is_(None),
                    set_={"is_active": True, "created_at": item.created_at},
                )
            else:
                statement = statement.on_conflict_do_update(
                    index_elements=[
                        content_brand_evidence_table.c.content_id,
                        content_brand_evidence_table.c.content_version,
                        content_brand_evidence_table.c.brand_id,
                        content_brand_evidence_table.c.source,
                        content_brand_evidence_table.c.derived_vehicle_model_id,
                        content_brand_evidence_table.c.catalog_version,
                    ],
                    index_where=content_brand_evidence_table.c.derived_vehicle_model_id.is_not(
                        None
                    ),
                    set_={"is_active": True, "created_at": item.created_at},
                )
            self._session.execute(statement)
        return True

    def replace_automatic_vehicle_evidence(
        self,
        *,
        content_id: UUID,
        content_version: int,
        evidence: tuple[ContentVehicleEvidence, ...],
    ) -> bool:
        if self._is_locked(content_vehicle_review_locks_table, content_id, content_version):
            return False
        self._session.execute(
            update(content_vehicle_evidence_table)
            .where(
                content_vehicle_evidence_table.c.content_id == content_id,
                content_vehicle_evidence_table.c.content_version == content_version,
                content_vehicle_evidence_table.c.is_manual_locked.is_(False),
                content_vehicle_evidence_table.c.is_active.is_(True),
            )
            .values(is_active=False)
        )
        for item in evidence:
            if item.is_manual_locked or item.source == "manual_review":
                raise ValueError("自动车型证据不能伪装成人工锁定证据")
            statement = (
                pg_insert(content_vehicle_evidence_table)
                .values(
                    id=item.id,
                    content_id=item.content_id,
                    content_version=item.content_version,
                    vehicle_model_id=item.vehicle_model_id,
                    source=item.source,
                    matched_text=item.matched_text,
                    source_field=item.source_field,
                    catalog_version=item.catalog_version,
                    confidence=item.confidence,
                    is_manual_locked=False,
                    is_active=True,
                    created_at=item.created_at,
                )
                .on_conflict_do_update(
                    constraint="uq_content_vehicle_evidence_identity",
                    set_={"is_active": True, "created_at": item.created_at},
                )
            )
            self._session.execute(statement)
        return True

    def replace_manual_brand_evidence(
        self,
        *,
        content_id: UUID,
        content_version: int,
        brand_ids: tuple[UUID, ...],
        unlock_existing: bool,
        actor_ref: str,
    ) -> None:
        locked = self._session.scalar(
            select(content_brand_review_locks_table.c.is_locked)
            .where(
                content_brand_review_locks_table.c.content_id == content_id,
                content_brand_review_locks_table.c.content_version == content_version,
            )
            .with_for_update()
        )
        if locked is True and not unlock_existing:
            raise RuntimeError("已有人工锁定品牌，必须显式解锁后才能修改")
        active_brands = set(
            self._session.scalars(
                select(vehicle_brands_table.c.id).where(
                    vehicle_brands_table.c.id.in_(brand_ids),
                    vehicle_brands_table.c.status == "active",
                )
            )
        )
        if active_brands != set(brand_ids):
            raise LookupError("品牌不存在或不可用")
        self._session.execute(
            update(content_brand_evidence_table)
            .where(
                content_brand_evidence_table.c.content_id == content_id,
                content_brand_evidence_table.c.content_version == content_version,
                content_brand_evidence_table.c.is_active.is_(True),
            )
            .values(is_active=False)
        )
        should_lock = not (unlock_existing and not brand_ids)
        self._session.execute(
            pg_insert(content_brand_review_locks_table)
            .values(
                content_id=content_id,
                content_version=content_version,
                is_locked=should_lock,
                actor_ref=actor_ref,
                updated_at=beijing_now(),
            )
            .on_conflict_do_update(
                index_elements=[
                    content_brand_review_locks_table.c.content_id,
                    content_brand_review_locks_table.c.content_version,
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
        now = beijing_now()
        for brand_id in brand_ids:
            statement = (
                pg_insert(content_brand_evidence_table)
                .values(
                    id=uuid4(),
                    content_id=content_id,
                    content_version=content_version,
                    brand_id=brand_id,
                    source="manual_review",
                    matched_text=None,
                    source_field=None,
                    derived_vehicle_model_id=None,
                    catalog_version=catalog_version,
                    confidence=1.0,
                    is_manual_locked=True,
                    is_active=True,
                    created_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[
                        content_brand_evidence_table.c.content_id,
                        content_brand_evidence_table.c.content_version,
                        content_brand_evidence_table.c.brand_id,
                        content_brand_evidence_table.c.source,
                        content_brand_evidence_table.c.catalog_version,
                    ],
                    index_where=content_brand_evidence_table.c.derived_vehicle_model_id.is_(None),
                    set_={"is_active": True, "is_manual_locked": True, "created_at": now},
                )
            )
            self._session.execute(statement)

    def _has_active_vehicle(self, brand_id: UUID) -> bool:
        return (
            self._session.scalar(
                select(vehicle_models_table.c.id)
                .where(
                    vehicle_models_table.c.brand_id == brand_id,
                    vehicle_models_table.c.status == "active",
                )
                .limit(1)
            )
            is not None
        )

    @staticmethod
    def _lock_conditions(table: Any, content_id: UUID, content_version: int) -> tuple[Any, Any]:
        return table.c.content_id == content_id, table.c.content_version == content_version

    def _is_locked(self, table: Any, content_id: UUID, content_version: int) -> bool:
        value = self._session.scalar(
            select(table.c.is_locked).where(
                *self._lock_conditions(table, content_id, content_version)
            )
        )
        return value is True

    def _replace_brand_aliases(
        self,
        brand_id: UUID,
        aliases: tuple[str, ...],
        *,
        created_at: datetime,
    ) -> None:
        self._session.execute(
            delete(vehicle_brand_aliases_table).where(
                vehicle_brand_aliases_table.c.brand_id == brand_id
            )
        )
        if aliases:
            self._session.execute(
                insert(vehicle_brand_aliases_table),
                [
                    {
                        "id": uuid4(),
                        "brand_id": brand_id,
                        "text": alias,
                        "normalized_text": normalize_vehicle_text(alias),
                        "created_at": created_at,
                    }
                    for alias in aliases
                ],
            )


__all__ = ["PostgresBrandVehicleCatalogRepository"]
