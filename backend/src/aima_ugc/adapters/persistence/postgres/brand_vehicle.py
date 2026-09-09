"""Brand/Vehicle 统一目录、过滤快照与品牌证据 PostgreSQL Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import delete, insert, or_, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.modules.vehicles.brand_vehicle import (
    BrandAliasRecord,
    BrandRecord,
    BrandRole,
    BrandStatus,
    BrandVehicleCatalogSnapshot,
    FilterScope,
    ResolverEvidence,
    VehicleAliasRecord,
    VehicleRecord,
)
from aima_ugc.modules.vehicles.models import normalize_vehicle_text
from aima_ugc.modules.vehicles.tables import (
    content_brand_evidence_table,
    content_brand_review_locks_table,
    vehicle_brand_aliases_table,
    vehicle_brands_table,
    vehicle_model_aliases_table,
    vehicle_models_table,
)
from aima_ugc.platform.time import beijing_now


def _brand_from_row(row: RowMapping) -> BrandRecord:
    return BrandRecord(
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


def _brand_alias_from_row(row: RowMapping) -> BrandAliasRecord:
    return BrandAliasRecord(
        id=cast(UUID, row["id"]),
        brand_id=cast(UUID, row["brand_id"]),
        text=cast(str, row["text"]),
        normalized_text=cast(str, row["normalized_text"]),
        created_at=cast(datetime, row["created_at"]),
    )


def _vehicle_from_row(row: RowMapping) -> VehicleRecord:
    return VehicleRecord(
        id=cast(UUID, row["id"]),
        code=cast(str, row["code"]),
        display_name=cast(str, row["display_name"]),
        brand_id=cast(UUID | None, row["brand_id"]),
        status=cast(str, row["status"]),  # type: ignore[arg-type]
        version=cast(int, row["version"]),
        catalog_version=cast(int, row["catalog_version"]),
    )


def _vehicle_alias_from_row(row: RowMapping) -> VehicleAliasRecord:
    return VehicleAliasRecord(
        id=cast(UUID, row["id"]),
        vehicle_model_id=cast(UUID, row["vehicle_model_id"]),
        text=cast(str, row["text"]),
        normalized_text=cast(str, row["normalized_text"]),
        created_at=cast(datetime, row["created_at"]),
    )


class PostgresBrandVehicleRepository:
    """Stage 2 Brand/Vehicle 统一目录唯一写边界；调用方拥有事务。"""

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
    ) -> BrandRecord:
        """创建 active Brand，并与 Alias 在同一 Catalog Version 事务内落库。"""

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
        self._insert_brand_aliases(brand_id, aliases, created_at=now)
        return _brand_from_row(row)

    def get_brand(self, brand_id: UUID, *, for_update: bool = False) -> BrandRecord | None:
        statement = select(vehicle_brands_table).where(vehicle_brands_table.c.id == brand_id)
        if for_update:
            statement = statement.with_for_update()
        row = self._session.execute(statement).mappings().one_or_none()
        return None if row is None else _brand_from_row(row)

    def list_brands(
        self,
        *,
        search: str | None,
        status: BrandStatus | None,
        role: BrandRole | None,
        offset: int,
        limit: int,
    ) -> tuple[tuple[BrandRecord, ...], int]:
        conditions = []
        if search is not None:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            alias_match = select(vehicle_brand_aliases_table.c.id).where(
                vehicle_brand_aliases_table.c.brand_id == vehicle_brands_table.c.id,
                vehicle_brand_aliases_table.c.text.ilike(pattern, escape="\\"),
            )
            conditions.append(
                or_(
                    vehicle_brands_table.c.code.ilike(pattern, escape="\\"),
                    vehicle_brands_table.c.display_name.ilike(pattern, escape="\\"),
                    alias_match.exists(),
                )
            )
        if status is not None:
            conditions.append(vehicle_brands_table.c.status == status)
        if role is not None:
            conditions.append(vehicle_brands_table.c.role == role)
        statement = select(vehicle_brands_table)
        count_statement = select(vehicle_brands_table.c.id)
        if conditions:
            statement = statement.where(*conditions)
            count_statement = count_statement.where(*conditions)
        rows = self._session.execute(
            statement.order_by(vehicle_brands_table.c.code, vehicle_brands_table.c.id)
            .offset(offset)
            .limit(limit)
        ).mappings()
        return (
            tuple(_brand_from_row(row) for row in rows),
            len(tuple(self._session.scalars(count_statement))),
        )

    def list_brand_aliases(self, brand_id: UUID) -> tuple[BrandAliasRecord, ...]:
        rows = self._session.execute(
            select(vehicle_brand_aliases_table)
            .where(vehicle_brand_aliases_table.c.brand_id == brand_id)
            .order_by(
                vehicle_brand_aliases_table.c.normalized_text, vehicle_brand_aliases_table.c.id
            )
        ).mappings()
        return tuple(_brand_alias_from_row(row) for row in rows)

    def update_brand(
        self,
        brand_id: UUID,
        *,
        display_name: str | None,
        role: BrandRole | None,
        status: BrandStatus | None,
        actor_ref: str,
    ) -> BrandRecord:
        """更新 Brand；仍有 active Vehicle 时禁止停用，避免悬空语义。"""

        current = self.get_brand(brand_id, for_update=True)
        if current is None:
            raise LookupError(brand_id)
        if status == "deprecated" and current.status != "deprecated":
            active_vehicle = self._session.scalar(
                select(vehicle_models_table.c.id)
                .where(
                    vehicle_models_table.c.brand_id == brand_id,
                    vehicle_models_table.c.status == "active",
                )
                .limit(1)
            )
            if active_vehicle is not None:
                raise RuntimeError("品牌仍有 active 车型，必须先停用或迁移车型")
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
        return _brand_from_row(row)

    def delete_unreferenced_brand(self, brand_id: UUID, *, actor_ref: str) -> bool:
        current = self.get_brand(brand_id, for_update=True)
        if current is None:
            return False
        referenced = self._session.scalar(
            select(vehicle_models_table.c.id)
            .where(vehicle_models_table.c.brand_id == brand_id)
            .limit(1)
        )
        evidence = self._session.scalar(
            select(content_brand_evidence_table.c.id)
            .where(content_brand_evidence_table.c.brand_id == brand_id)
            .limit(1)
        )
        if referenced is not None or evidence is not None:
            raise RuntimeError("已引用品牌不能物理删除")
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

    def add_brand_alias(
        self,
        brand_id: UUID,
        *,
        text: str,
        actor_ref: str,
    ) -> BrandAliasRecord:
        brand = self.get_brand(brand_id, for_update=True)
        if brand is None:
            raise LookupError(brand_id)
        if brand.status != "active":
            raise RuntimeError("已停用品牌不能新增识别词")
        catalog_version = self._vehicle_catalog.next_catalog_version(
            reason="brand_alias_added", actor_ref=actor_ref
        )
        now = beijing_now()
        row = (
            self._session.execute(
                insert(vehicle_brand_aliases_table)
                .values(
                    id=uuid4(),
                    brand_id=brand_id,
                    text=text,
                    normalized_text=normalize_vehicle_text(text),
                    created_at=now,
                )
                .returning(vehicle_brand_aliases_table)
            )
            .mappings()
            .one()
        )
        self._touch_brand(brand, catalog_version=catalog_version, updated_at=now)
        return _brand_alias_from_row(row)

    def delete_brand_alias(self, brand_id: UUID, alias_id: UUID, *, actor_ref: str) -> bool:
        brand = self.get_brand(brand_id, for_update=True)
        if brand is None:
            raise LookupError(brand_id)
        alias = (
            self._session.execute(
                select(vehicle_brand_aliases_table).where(
                    vehicle_brand_aliases_table.c.id == alias_id,
                    vehicle_brand_aliases_table.c.brand_id == brand_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if alias is None:
            return False
        catalog_version = self._vehicle_catalog.next_catalog_version(
            reason="brand_alias_deleted", actor_ref=actor_ref
        )
        self._session.execute(
            delete(vehicle_brand_aliases_table).where(vehicle_brand_aliases_table.c.id == alias_id)
        )
        self._touch_brand(brand, catalog_version=catalog_version, updated_at=beijing_now())
        return True

    def require_active_brand(self, brand_id: UUID) -> BrandRecord:
        # 与 Brand 停用/删除串行化，避免并发产生 active Vehicle -> deprecated Brand。
        brand = self.get_brand(brand_id, for_update=True)
        if brand is None:
            raise LookupError(brand_id)
        if brand.status != "active":
            raise RuntimeError("车型只能绑定 active 品牌")
        return brand

    def assign_vehicle_brand(
        self,
        vehicle_model_id: UUID,
        brand_id: UUID | None,
        *,
        actor_ref: str,
    ) -> VehicleRecord:
        """显式修改 Vehicle 品牌归属；active Vehicle 不允许清空或指向停用 Brand。"""

        row = (
            self._session.execute(
                select(vehicle_models_table)
                .where(vehicle_models_table.c.id == vehicle_model_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError(vehicle_model_id)
        status = cast(str, row["status"])
        if status == "merged":
            raise RuntimeError("已合并车型不能修改品牌归属")
        if brand_id is None:
            if status == "active":
                raise RuntimeError("active 车型必须绑定 active 品牌")
        else:
            self.require_active_brand(brand_id)
        catalog_version = self._vehicle_catalog.next_catalog_version(
            reason="vehicle_brand_updated", actor_ref=actor_ref
        )
        updated = (
            self._session.execute(
                update(vehicle_models_table)
                .where(vehicle_models_table.c.id == vehicle_model_id)
                .values(
                    brand_id=brand_id,
                    version=vehicle_models_table.c.version + 1,
                    catalog_version=catalog_version,
                    updated_at=beijing_now(),
                )
                .returning(vehicle_models_table)
            )
            .mappings()
            .one()
        )
        return _vehicle_from_row(updated)

    def unresolved_active_vehicle_ids(self) -> tuple[UUID, ...]:
        rows = self._session.scalars(
            select(vehicle_models_table.c.id)
            .outerjoin(
                vehicle_brands_table,
                vehicle_brands_table.c.id == vehicle_models_table.c.brand_id,
            )
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
        return tuple(rows)

    def snapshot(self, *, brand_ids: tuple[UUID, ...] | None) -> BrandVehicleCatalogSnapshot:
        """冻结 all_active 或 selected Brand，并自动包含其全部 active Vehicle/Alias。"""

        scope: FilterScope = "all_active" if brand_ids is None else "selected"
        if brand_ids is None:
            selected_brands = tuple(
                self._session.execute(
                    select(vehicle_brands_table)
                    .where(vehicle_brands_table.c.status == "active")
                    .order_by(vehicle_brands_table.c.id)
                ).mappings()
            )
        else:
            unique_ids = tuple(dict.fromkeys(brand_ids))
            if not unique_ids:
                raise ValueError("selected scope 至少需要一个 brand_id")
            selected_brands = tuple(
                self._session.execute(
                    select(vehicle_brands_table)
                    .where(
                        vehicle_brands_table.c.id.in_(unique_ids),
                        vehicle_brands_table.c.status == "active",
                    )
                    .order_by(vehicle_brands_table.c.id)
                ).mappings()
            )
            if {cast(UUID, row["id"]) for row in selected_brands} != set(unique_ids):
                raise LookupError("所选品牌不存在或已停用")
        selected_ids = tuple(cast(UUID, row["id"]) for row in selected_brands)
        if selected_ids:
            vehicle_rows = tuple(
                self._session.execute(
                    select(vehicle_models_table)
                    .where(
                        vehicle_models_table.c.status == "active",
                        vehicle_models_table.c.brand_id.in_(selected_ids),
                    )
                    .order_by(vehicle_models_table.c.id)
                ).mappings()
            )
            brand_alias_rows = tuple(
                self._session.execute(
                    select(vehicle_brand_aliases_table)
                    .where(vehicle_brand_aliases_table.c.brand_id.in_(selected_ids))
                    .order_by(
                        vehicle_brand_aliases_table.c.brand_id,
                        vehicle_brand_aliases_table.c.normalized_text,
                        vehicle_brand_aliases_table.c.id,
                    )
                ).mappings()
            )
        else:
            vehicle_rows = ()
            brand_alias_rows = ()
        vehicle_ids = tuple(cast(UUID, row["id"]) for row in vehicle_rows)
        if vehicle_ids:
            vehicle_alias_rows = tuple(
                self._session.execute(
                    select(vehicle_model_aliases_table)
                    .where(vehicle_model_aliases_table.c.vehicle_model_id.in_(vehicle_ids))
                    .order_by(
                        vehicle_model_aliases_table.c.vehicle_model_id,
                        vehicle_model_aliases_table.c.normalized_text,
                        vehicle_model_aliases_table.c.id,
                    )
                ).mappings()
            )
        else:
            vehicle_alias_rows = ()
        ambiguous_brand_aliases = self._ambiguous_active_brand_aliases()
        ambiguous_vehicle_aliases = self._ambiguous_active_vehicle_aliases()
        return BrandVehicleCatalogSnapshot(
            catalog_version=self.current_catalog_version(),
            filter_scope=scope,
            selected_brand_ids=selected_ids,
            brands=tuple(_brand_from_row(row) for row in selected_brands),
            brand_aliases=tuple(_brand_alias_from_row(row) for row in brand_alias_rows),
            vehicles=tuple(_vehicle_from_row(row) for row in vehicle_rows),
            vehicle_aliases=tuple(_vehicle_alias_from_row(row) for row in vehicle_alias_rows),
            ambiguous_brand_aliases=ambiguous_brand_aliases,
            ambiguous_vehicle_aliases=ambiguous_vehicle_aliases,
            unresolved_active_vehicle_ids=self.unresolved_active_vehicle_ids(),
        )

    def _ambiguous_active_brand_aliases(self) -> tuple[str, ...]:
        rows = self._session.execute(
            select(
                vehicle_brand_aliases_table.c.normalized_text,
                vehicle_brand_aliases_table.c.brand_id,
            )
            .join(
                vehicle_brands_table,
                vehicle_brands_table.c.id == vehicle_brand_aliases_table.c.brand_id,
            )
            .where(vehicle_brands_table.c.status == "active")
        )
        candidates: dict[str, set[UUID]] = {}
        for normalized_text, brand_id in rows:
            candidates.setdefault(cast(str, normalized_text), set()).add(cast(UUID, brand_id))
        return tuple(sorted(alias for alias, ids in candidates.items() if len(ids) > 1))

    def _ambiguous_active_vehicle_aliases(self) -> tuple[str, ...]:
        rows = self._session.execute(
            select(
                vehicle_model_aliases_table.c.normalized_text,
                vehicle_model_aliases_table.c.vehicle_model_id,
            )
            .join(
                vehicle_models_table,
                vehicle_models_table.c.id == vehicle_model_aliases_table.c.vehicle_model_id,
            )
            .where(vehicle_models_table.c.status == "active")
        )
        candidates: dict[str, set[UUID]] = {}
        for normalized_text, vehicle_model_id in rows:
            candidates.setdefault(cast(str, normalized_text), set()).add(
                cast(UUID, vehicle_model_id)
            )
        return tuple(sorted(alias for alias, ids in candidates.items() if len(ids) > 1))

    def replace_automatic_brand_evidence(
        self,
        *,
        content_id: UUID,
        content_version: int,
        evidence: tuple[ResolverEvidence, ...],
        catalog_version: int,
    ) -> bool:
        """替换当前 Content Version 的自动 Brand 证据；人工锁存在时完全不写。"""

        locked = self._session.scalar(
            select(content_brand_review_locks_table.c.is_locked).where(
                content_brand_review_locks_table.c.content_id == content_id,
                content_brand_review_locks_table.c.content_version == content_version,
            )
        )
        if locked is True:
            return False
        self._session.execute(
            update(content_brand_evidence_table)
            .where(
                content_brand_evidence_table.c.content_id == content_id,
                content_brand_evidence_table.c.content_version == content_version,
                content_brand_evidence_table.c.is_active.is_(True),
                content_brand_evidence_table.c.is_manual_locked.is_(False),
            )
            .values(is_active=False)
        )
        for item in evidence:
            if item.source not in ("alias_match", "vehicle_match"):
                raise ValueError("自动 Brand Evidence 只接受 alias_match/vehicle_match")
            self._validate_brand_evidence(item)
            self._upsert_brand_evidence(
                content_id=content_id,
                content_version=content_version,
                item=item,
                catalog_version=catalog_version,
                confidence=1.0,
                is_manual_locked=False,
            )
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
        """独立锁定 Brand 结论；不会改变 Vehicle Review Lock 或 Vehicle Evidence。"""

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
        unique_ids = tuple(dict.fromkeys(brand_ids))
        active_ids = set(
            self._session.scalars(
                select(vehicle_brands_table.c.id).where(
                    vehicle_brands_table.c.id.in_(unique_ids),
                    vehicle_brands_table.c.status == "active",
                )
            )
        )
        if active_ids != set(unique_ids):
            raise LookupError("品牌不存在或已停用")
        self._session.execute(
            update(content_brand_evidence_table)
            .where(
                content_brand_evidence_table.c.content_id == content_id,
                content_brand_evidence_table.c.content_version == content_version,
                content_brand_evidence_table.c.is_active.is_(True),
            )
            .values(is_active=False)
        )
        should_lock = not (unlock_existing and not unique_ids)
        existing_lock = (
            self._session.execute(
                select(content_brand_review_locks_table).where(
                    content_brand_review_locks_table.c.content_id == content_id,
                    content_brand_review_locks_table.c.content_version == content_version,
                )
            )
            .mappings()
            .one_or_none()
        )
        lock_values = {
            "is_locked": should_lock,
            "actor_ref": actor_ref,
            "updated_at": beijing_now(),
        }
        if existing_lock is None:
            self._session.execute(
                insert(content_brand_review_locks_table).values(
                    content_id=content_id,
                    content_version=content_version,
                    **lock_values,
                )
            )
        else:
            self._session.execute(
                update(content_brand_review_locks_table)
                .where(
                    content_brand_review_locks_table.c.content_id == content_id,
                    content_brand_review_locks_table.c.content_version == content_version,
                )
                .values(**lock_values)
            )
        if not should_lock:
            return
        catalog_version = self.current_catalog_version()
        for brand_id in unique_ids:
            self._upsert_brand_evidence(
                content_id=content_id,
                content_version=content_version,
                item=ResolverEvidence(
                    entity_id=brand_id,
                    source="manual_review",
                    matched_text=None,
                    source_field=None,
                ),
                catalog_version=catalog_version,
                confidence=1.0,
                is_manual_locked=True,
            )

    def _validate_brand_evidence(self, item: ResolverEvidence) -> None:
        self.require_active_brand(item.entity_id)
        if item.source == "vehicle_match":
            if item.derived_vehicle_model_id is None:
                raise ValueError("vehicle_match 必须携带 derived_vehicle_model_id")
            vehicle_brand = self._session.scalar(
                select(vehicle_models_table.c.brand_id).where(
                    vehicle_models_table.c.id == item.derived_vehicle_model_id,
                    vehicle_models_table.c.status == "active",
                )
            )
            if vehicle_brand != item.entity_id:
                raise ValueError("derived Vehicle 与 Brand 归属不一致")
        elif item.derived_vehicle_model_id is not None:
            raise ValueError("非 vehicle_match 不能携带 derived_vehicle_model_id")

    def _upsert_brand_evidence(
        self,
        *,
        content_id: UUID,
        content_version: int,
        item: ResolverEvidence,
        catalog_version: int,
        confidence: float,
        is_manual_locked: bool,
    ) -> None:
        conditions = [
            content_brand_evidence_table.c.content_id == content_id,
            content_brand_evidence_table.c.content_version == content_version,
            content_brand_evidence_table.c.brand_id == item.entity_id,
            content_brand_evidence_table.c.source == item.source,
            content_brand_evidence_table.c.catalog_version == catalog_version,
        ]
        if item.derived_vehicle_model_id is None:
            conditions.append(content_brand_evidence_table.c.derived_vehicle_model_id.is_(None))
        else:
            conditions.append(
                content_brand_evidence_table.c.derived_vehicle_model_id
                == item.derived_vehicle_model_id
            )
        existing_id = self._session.scalar(
            select(content_brand_evidence_table.c.id).where(*conditions).limit(1)
        )
        values = {
            "matched_text": item.matched_text,
            "source_field": item.source_field,
            "confidence": confidence,
            "is_manual_locked": is_manual_locked,
            "is_active": True,
            "created_at": beijing_now(),
        }
        if existing_id is None:
            self._session.execute(
                insert(content_brand_evidence_table).values(
                    id=uuid4(),
                    content_id=content_id,
                    content_version=content_version,
                    brand_id=item.entity_id,
                    source=item.source,
                    derived_vehicle_model_id=item.derived_vehicle_model_id,
                    catalog_version=catalog_version,
                    **values,
                )
            )
        else:
            self._session.execute(
                update(content_brand_evidence_table)
                .where(content_brand_evidence_table.c.id == existing_id)
                .values(**values)
            )

    def _insert_brand_aliases(
        self,
        brand_id: UUID,
        aliases: tuple[str, ...],
        *,
        created_at: datetime,
    ) -> None:
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

    def _touch_brand(
        self,
        brand: BrandRecord,
        *,
        catalog_version: int,
        updated_at: datetime,
    ) -> None:
        self._session.execute(
            update(vehicle_brands_table)
            .where(vehicle_brands_table.c.id == brand.id)
            .values(
                version=brand.version + 1,
                catalog_version=catalog_version,
                updated_at=updated_at,
            )
        )


__all__ = ["PostgresBrandVehicleRepository"]
