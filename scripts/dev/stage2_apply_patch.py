"""Temporary Stage 2 branch patch; deleted before PR merge."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = _read(path)
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: expected one literal match, got {text.count(old)}")
    _write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str) -> None:
    text = _read(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, got {count}")
    _write(path, updated)


ADMIN_CONTRACT = "backend/src/aima_ugc/contracts/administration.py"
replace_once(
    ADMIN_CONTRACT,
    "    display_name: str = Field(min_length=1, max_length=200)\n    aliases: tuple[str, ...] = Field(default=(), max_length=100)\n",
    "    display_name: str = Field(min_length=1, max_length=200)\n"
    "    brand_id: UUID\n"
    "    aliases: tuple[str, ...] = Field(default=(), max_length=100)\n",
)
replace_once(
    ADMIN_CONTRACT,
    "    status: Literal[\"active\", \"deprecated\"] | None = None\n    series_name: str | None = Field(default=None, min_length=1, max_length=200)\n",
    "    status: Literal[\"active\", \"deprecated\"] | None = None\n"
    "    brand_id: UUID | None = None\n"
    "    series_name: str | None = Field(default=None, min_length=1, max_length=200)\n",
)
replace_once(
    ADMIN_CONTRACT,
    "            and self.status is None\n            and not self.model_fields_set.intersection({\"series_name\", \"category_name\"})\n",
    "            and self.status is None\n"
    "            and \"brand_id\" not in self.model_fields_set\n"
    "            and not self.model_fields_set.intersection({\"series_name\", \"category_name\"})\n",
)
replace_once(
    ADMIN_CONTRACT,
    "    category_name: str | None = None\n    status: VehicleModelStatus\n",
    "    category_name: str | None = None\n    brand_id: UUID | None = None\n    status: VehicleModelStatus\n",
)

VEHICLES = "backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py"
replace_once(
    VEHICLES,
    "    keyword_pack_vehicle_models_table,\n    vehicle_catalog_versions_table,\n",
    "    keyword_pack_vehicle_models_table,\n    vehicle_brands_table,\n    vehicle_catalog_versions_table,\n",
)
replace_once(
    VEHICLES,
    "        category_name=cast(str | None, row[\"category_name\"]),\n        status=cast(VehicleStatus, row[\"status\"]),\n",
    "        category_name=cast(str | None, row[\"category_name\"]),\n"
    "        brand_id=cast(UUID | None, row[\"brand_id\"]),\n"
    "        status=cast(VehicleStatus, row[\"status\"]),\n",
)
replace_once(
    VEHICLES,
    "        return int(value)\n\n    def next_catalog_version",
    "        return int(value)\n\n"
    "    def lock_catalog_version(self) -> int:\n"
    "        \"\"\"以共享锁冻结当前目录版本，阻止并发目录写穿透 Snapshot。\"\"\"\n\n"
    "        seed = self._session.scalar(\n"
    "            select(vehicle_catalog_versions_table.c.version)\n"
    "            .where(vehicle_catalog_versions_table.c.version == 1)\n"
    "            .with_for_update(read=True)\n"
    "        )\n"
    "        if seed is None:\n"
    "            raise RuntimeError(\"Vehicle Catalog 尚未初始化\")\n"
    "        return self.current_catalog_version()\n\n"
    "    def next_catalog_version",
)
regex_once(
    VEHICLES,
    r"    def create_model\(\n.*?(?=    def get_model\()",
    '''    def create_model(
        self,
        *,
        code: str,
        display_name: str,
        aliases: tuple[str, ...],
        actor_ref: str,
        brand_id: UUID | None = None,
        series_name: str | None = None,
        category_name: str | None = None,
    ) -> VehicleModel:
        """创建 active 车型；Stage 2 起必须显式绑定有效 active Brand。"""

        if brand_id is None:
            raise RuntimeError("active 车型必须绑定有效品牌")
        self._require_active_brand(brand_id)
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
                    series_name=series_name,
                    category_name=category_name,
                    brand_id=brand_id,
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

''',
)
regex_once(
    VEHICLES,
    r"    def update_model\(\n.*?(?=    def merge_model\()",
    '''    def update_model(
        self,
        model_id: UUID,
        *,
        display_name: str | None,
        aliases: tuple[str, ...] | None,
        status: str | None,
        actor_ref: str,
        classification: dict[str, str | None] | None = None,
        ownership: dict[str, UUID | None] | None = None,
    ) -> VehicleModel:
        """更新车型；任何 active 结果都必须拥有有效 active Brand。"""

        current = self.get_model(model_id, for_update=True)
        if current is None:
            raise LookupError(model_id)
        if current.status == "merged":
            raise RuntimeError("已合并车型不能直接编辑")

        target_status = cast(VehicleStatus, status or current.status)
        brand_changed = ownership is not None and "brand_id" in ownership
        target_brand_id = ownership["brand_id"] if brand_changed else current.brand_id
        if target_status == "active":
            if target_brand_id is None:
                raise RuntimeError("active 车型必须绑定有效品牌")
            self._require_active_brand(target_brand_id)
        elif brand_changed and target_brand_id is not None:
            self._require_active_brand(target_brand_id)

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
        if brand_changed:
            values["brand_id"] = target_brand_id
        # 仅显式传入的字段参与更新；null 用于清除，缺省保留原值。
        for field in ("series_name", "category_name"):
            if classification is not None and field in classification:
                values[field] = classification[field]
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

    def assign_brand(
        self,
        model_id: UUID,
        brand_id: UUID | None,
        *,
        actor_ref: str,
    ) -> VehicleModel:
        """显式修复 / 修改车型品牌归属；车型表写入仍由本 Repository 独占。"""

        current = self.get_model(model_id, for_update=True)
        if current is None:
            raise LookupError(model_id)
        if current.status == "merged":
            raise RuntimeError("已合并车型不能修改品牌归属")
        if current.status == "active" and brand_id is None:
            raise RuntimeError("active 车型不能清空品牌归属")
        if brand_id is not None:
            self._require_active_brand(brand_id)
        catalog_version = self.next_catalog_version(
            reason="vehicle_brand_assigned",
            actor_ref=actor_ref,
        )
        row = (
            self._session.execute(
                update(vehicle_models_table)
                .where(vehicle_models_table.c.id == model_id)
                .values(
                    brand_id=brand_id,
                    version=current.version + 1,
                    catalog_version=catalog_version,
                    updated_at=beijing_now(),
                )
                .returning(vehicle_models_table)
            )
            .mappings()
            .one()
        )
        return _vehicle_from_row(row)

''',
)
replace_once(
    VEHICLES,
    "        if source.status == \"merged\" or target.status != \"active\":\n"
    "            raise RuntimeError(\"合并源必须未合并且目标必须为 active\")\n"
    "        catalog_version = self.next_catalog_version",
    "        if source.status == \"merged\" or target.status != \"active\":\n"
    "            raise RuntimeError(\"合并源必须未合并且目标必须为 active\")\n"
    "        if target.brand_id is None:\n"
    "            raise RuntimeError(\"active 合并目标必须绑定有效品牌\")\n"
    "        self._require_active_brand(target.brand_id)\n"
    "        catalog_version = self.next_catalog_version",
)
replace_once(
    VEHICLES,
    "    def _replace_aliases(\n",
    '''    def _require_active_brand(self, brand_id: UUID) -> None:
        status = self._session.scalar(
            select(vehicle_brands_table.c.status).where(vehicle_brands_table.c.id == brand_id)
        )
        if status is None:
            raise LookupError("品牌不存在")
        if status != "active":
            raise RuntimeError("车型只能绑定 active 品牌")

    def _replace_aliases(
''',
)

ADMIN_SERVICE = "backend/src/aima_ugc/bootstrap/administration_http.py"
replace_once(
    ADMIN_SERVICE,
    "                model = repository.create_model(\n"
    "                    code=body.code,\n"
    "                    display_name=body.display_name,\n"
    "                    aliases=body.aliases,\n"
    "                    series_name=body.series_name,\n"
    "                    category_name=body.category_name,\n"
    "                    actor_ref=principal.principal_id,\n"
    "                )\n",
    "                try:\n"
    "                    model = repository.create_model(\n"
    "                        code=body.code,\n"
    "                        display_name=body.display_name,\n"
    "                        aliases=body.aliases,\n"
    "                        brand_id=body.brand_id,\n"
    "                        series_name=body.series_name,\n"
    "                        category_name=body.category_name,\n"
    "                        actor_ref=principal.principal_id,\n"
    "                    )\n"
    "                except LookupError as exc:\n"
    "                    raise AdministrationResourceNotFound from exc\n"
    "                except RuntimeError as exc:\n"
    "                    raise AdministrationConflict from exc\n",
)
replace_once(
    ADMIN_SERVICE,
    "                    detail={\"code\": model.code, \"catalog_version\": model.catalog_version},\n",
    "                    detail={\n"
    "                        \"code\": model.code,\n"
    "                        \"brand_id\": str(model.brand_id),\n"
    "                        \"catalog_version\": model.catalog_version,\n"
    "                    },\n",
)
replace_once(
    ADMIN_SERVICE,
    "                        classification=body.model_dump(\n"
    "                            include={\"series_name\", \"category_name\"}, exclude_unset=True\n"
    "                        ),\n"
    "                        actor_ref=principal.principal_id,\n",
    "                        classification=body.model_dump(\n"
    "                            include={\"series_name\", \"category_name\"}, exclude_unset=True\n"
    "                        ),\n"
    "                        ownership=body.model_dump(include={\"brand_id\"}, exclude_unset=True),\n"
    "                        actor_ref=principal.principal_id,\n",
)
replace_once(
    ADMIN_SERVICE,
    "                    detail={\"version\": model.version, \"catalog_version\": model.catalog_version},\n",
    "                    detail={\n"
    "                        \"version\": model.version,\n"
    "                        \"brand_id\": None if model.brand_id is None else str(model.brand_id),\n"
    "                        \"catalog_version\": model.catalog_version,\n"
    "                    },\n",
)
replace_once(
    ADMIN_SERVICE,
    "        category_name=model.category_name,\n        status=model.status,\n",
    "        category_name=model.category_name,\n"
    "        brand_id=model.brand_id,\n"
    "        status=model.status,\n",
)

BRAND_REPO = "backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py"
replace_once(
    BRAND_REPO,
    "from sqlalchemy import delete, func, insert, select, update\n",
    "from sqlalchemy import delete, func, insert, or_, select, update\n",
)
replace_once(
    BRAND_REPO,
    "    BrandStatus,\n    CatalogSnapshot,\n",
    "    BrandStatus,\n    CatalogFilterMode,\n    CatalogSnapshot,\n",
)
replace_once(
    BRAND_REPO,
    "    def delete_unreferenced_brand(self, brand_id: UUID, *, actor_ref: str) -> bool:\n",
    '''    def is_brand_referenced(self, brand_id: UUID) -> bool:
        return self._session.scalar(
            select(vehicle_models_table.c.id)
            .where(vehicle_models_table.c.brand_id == brand_id)
            .limit(1)
        ) is not None or self._session.scalar(
            select(content_brand_evidence_table.c.id)
            .where(content_brand_evidence_table.c.brand_id == brand_id)
            .limit(1)
        ) is not None

    def delete_unreferenced_brand(self, brand_id: UUID, *, actor_ref: str) -> bool:
''',
)
replace_once(
    BRAND_REPO,
    "        if self._session.scalar(\n"
    "            select(vehicle_models_table.c.id).where(vehicle_models_table.c.brand_id == brand_id).limit(1)\n"
    "        ) is not None or self._session.scalar(\n"
    "            select(content_brand_evidence_table.c.id)\n"
    "            .where(content_brand_evidence_table.c.brand_id == brand_id)\n"
    "            .limit(1)\n"
    "        ) is not None:\n",
    "        if self.is_brand_referenced(brand_id):\n",
)
regex_once(
    BRAND_REPO,
    r"    def assign_vehicle_brand\(\n.*?(?=    def replace_automatic_brand_evidence\()",
    '''    def get_vehicle_model(self, vehicle_model_id: UUID) -> VehicleModel | None:
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
            raise RuntimeError("仍有 active 车型缺少有效 active Brand，不能冻结 all_active Snapshot")

        brand_statement = select(vehicle_brands_table).where(vehicle_brands_table.c.status == "active")
        if filter_mode == "selected":
            brand_statement = brand_statement.where(vehicle_brands_table.c.id.in_(selected_brand_ids))
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

''',
)

print("Stage 2 patch applied")
