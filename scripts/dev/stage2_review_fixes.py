"""一次性应用 Stage 2 独立 Review 修复；由 workflow 执行后删除。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0:
        if new in text:
            return
        raise RuntimeError(f"{path}: expected one match, got 0: {old[:120]!r}")
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Snapshot 冻结全局 active Alias 歧义上下文，selected scope 不得隐藏跨 scope 冲突。
path = "backend/src/aima_ugc/modules/vehicles/brand_vehicle.py"
replace_once(
    path,
    "    vehicle_aliases: tuple[VehicleAliasRecord, ...]\n    unresolved_active_vehicle_ids: tuple[UUID, ...] = ()\n",
    "    vehicle_aliases: tuple[VehicleAliasRecord, ...]\n    ambiguous_brand_aliases: tuple[str, ...] = ()\n    ambiguous_vehicle_aliases: tuple[str, ...] = ()\n    unresolved_active_vehicle_ids: tuple[UUID, ...] = ()\n",
)
replace_once(
    path,
    "            for normalized_alias in sorted(matched, key=lambda item: (-len(item), item)):\n                aliases = aliases_by_text[normalized_alias]\n",
    "            for normalized_alias in sorted(matched, key=lambda item: (-len(item), item)):\n                if normalized_alias in snapshot.ambiguous_vehicle_aliases:\n                    conflicts.append(f\"ambiguous_vehicle_alias:{normalized_alias}\")\n                    continue\n                aliases = aliases_by_text[normalized_alias]\n",
)
replace_once(
    path,
    "            for normalized_alias in sorted(matched, key=lambda item: (-len(item), item)):\n                aliases = aliases_by_text[normalized_alias]\n                candidates = {item.brand_id for item in aliases}\n",
    "            for normalized_alias in sorted(matched, key=lambda item: (-len(item), item)):\n                if normalized_alias in snapshot.ambiguous_brand_aliases:\n                    conflicts.append(f\"ambiguous_brand_alias:{normalized_alias}\")\n                    continue\n                aliases = aliases_by_text[normalized_alias]\n                candidates = {item.brand_id for item in aliases}\n",
)

path = "backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py"
replace_once(
    path,
    "    def require_active_brand(self, brand_id: UUID) -> BrandRecord:\n        brand = self.get_brand(brand_id)\n",
    "    def require_active_brand(self, brand_id: UUID) -> BrandRecord:\n        # 与 Brand 停用/删除串行化，避免并发产生 active Vehicle -> deprecated Brand。\n        brand = self.get_brand(brand_id, for_update=True)\n",
)
replace_once(
    path,
    "        return BrandVehicleCatalogSnapshot(\n            catalog_version=self.current_catalog_version(),\n",
    "        ambiguous_brand_aliases = self._ambiguous_active_brand_aliases()\n        ambiguous_vehicle_aliases = self._ambiguous_active_vehicle_aliases()\n        return BrandVehicleCatalogSnapshot(\n            catalog_version=self.current_catalog_version(),\n",
)
replace_once(
    path,
    "            vehicle_aliases=tuple(_vehicle_alias_from_row(row) for row in vehicle_alias_rows),\n            unresolved_active_vehicle_ids=self.unresolved_active_vehicle_ids(),\n        )\n\n    def replace_automatic_brand_evidence(\n",
    "            vehicle_aliases=tuple(_vehicle_alias_from_row(row) for row in vehicle_alias_rows),\n            ambiguous_brand_aliases=ambiguous_brand_aliases,\n            ambiguous_vehicle_aliases=ambiguous_vehicle_aliases,\n            unresolved_active_vehicle_ids=self.unresolved_active_vehicle_ids(),\n        )\n\n    def _ambiguous_active_brand_aliases(self) -> tuple[str, ...]:\n        rows = self._session.execute(\n            select(\n                vehicle_brand_aliases_table.c.normalized_text,\n                vehicle_brand_aliases_table.c.brand_id,\n            )\n            .join(\n                vehicle_brands_table,\n                vehicle_brands_table.c.id == vehicle_brand_aliases_table.c.brand_id,\n            )\n            .where(vehicle_brands_table.c.status == \"active\")\n        )\n        candidates: dict[str, set[UUID]] = {}\n        for normalized_text, brand_id in rows:\n            candidates.setdefault(cast(str, normalized_text), set()).add(cast(UUID, brand_id))\n        return tuple(sorted(alias for alias, ids in candidates.items() if len(ids) > 1))\n\n    def _ambiguous_active_vehicle_aliases(self) -> tuple[str, ...]:\n        rows = self._session.execute(\n            select(\n                vehicle_model_aliases_table.c.normalized_text,\n                vehicle_model_aliases_table.c.vehicle_model_id,\n            )\n            .join(\n                vehicle_models_table,\n                vehicle_models_table.c.id == vehicle_model_aliases_table.c.vehicle_model_id,\n            )\n            .where(vehicle_models_table.c.status == \"active\")\n        )\n        candidates: dict[str, set[UUID]] = {}\n        for normalized_text, vehicle_model_id in rows:\n            candidates.setdefault(cast(str, normalized_text), set()).add(\n                cast(UUID, vehicle_model_id)\n            )\n        return tuple(sorted(alias for alias, ids in candidates.items() if len(ids) > 1))\n\n    def replace_automatic_brand_evidence(\n",
)

# Existing Vehicle update path uses same row lock before validating active Brand.
path = "backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py"
replace_once(
    path,
    "            brand_status = self._session.scalar(\n                select(vehicle_brands_table.c.status).where(\n                    vehicle_brands_table.c.id == requested_brand_id\n                )\n            )\n",
    "            brand_status = self._session.scalar(\n                select(vehicle_brands_table.c.status)\n                .where(vehicle_brands_table.c.id == requested_brand_id)\n                .with_for_update()\n            )\n",
)

# Public snapshot serializes ambiguity context so Stage 3/4 can freeze it rather than re-read live catalog.
path = "backend/src/aima_ugc/contracts/brand_vehicle.py"
replace_once(
    path,
    "    vehicle_aliases: tuple[CatalogVehicleAliasSnapshotItem, ...]\n    unresolved_active_vehicle_ids: tuple[UUID, ...]\n",
    "    vehicle_aliases: tuple[CatalogVehicleAliasSnapshotItem, ...]\n    ambiguous_brand_aliases: tuple[str, ...]\n    ambiguous_vehicle_aliases: tuple[str, ...]\n    unresolved_active_vehicle_ids: tuple[UUID, ...]\n",
)

path = "backend/src/aima_ugc/bootstrap/brand_vehicle_http.py"
replace_once(
    path,
    "        vehicle_aliases=tuple(\n            CatalogVehicleAliasSnapshotItem(\n",
    "        vehicle_aliases=tuple(\n            CatalogVehicleAliasSnapshotItem(\n",
)
replace_once(
    path,
    "            for item in snapshot.vehicle_aliases\n        ),\n        unresolved_active_vehicle_ids=snapshot.unresolved_active_vehicle_ids,\n",
    "            for item in snapshot.vehicle_aliases\n        ),\n        ambiguous_brand_aliases=snapshot.ambiguous_brand_aliases,\n        ambiguous_vehicle_aliases=snapshot.ambiguous_vehicle_aliases,\n        unresolved_active_vehicle_ids=snapshot.unresolved_active_vehicle_ids,\n",
)

# 通用 Vehicle Update 也记录 Brand 归属 old/new，避免存在低可读性的第二条改品牌路径。
path = "backend/src/aima_ugc/bootstrap/administration_http.py"
replace_once(
    path,
    "                repository = PostgresVehicleCatalogRepository(session)\n                try:\n                    model = repository.update_model(\n",
    "                repository = PostgresVehicleCatalogRepository(session)\n                previous = repository.get_model(vehicle_model_id)\n                if previous is None:\n                    raise AdministrationResourceNotFound\n                try:\n                    model = repository.update_model(\n",
)
replace_once(
    path,
    "                    detail={\"version\": model.version, \"catalog_version\": model.catalog_version},\n",
    "                    detail={\n                        \"version\": model.version,\n                        \"catalog_version\": model.catalog_version,\n                        \"brand_id_before\": (\n                            None if previous.brand_id is None else str(previous.brand_id)\n                        ),\n                        \"brand_id_after\": None if model.brand_id is None else str(model.brand_id),\n                    },\n",
)

# Unit: selected scope 仍能显式看见全局歧义，不猜 selected 实体。
path = "tests/unit/test_brand_vehicle_resolver.py"
replace_once(
    path,
    "def test_manual_brand_lock_is_independent_from_vehicle_resolution() -> None:\n",
    "def test_selected_scope_does_not_hide_global_brand_alias_ambiguity() -> None:\n    snapshot = _snapshot()\n    snapshot = BrandVehicleCatalogSnapshot(\n        catalog_version=snapshot.catalog_version,\n        filter_scope=\"selected\",\n        selected_brand_ids=(BRAND_A,),\n        brands=(snapshot.brands[0],),\n        brand_aliases=(snapshot.brand_aliases[0],),\n        vehicles=snapshot.vehicles,\n        vehicle_aliases=snapshot.vehicle_aliases,\n        ambiguous_brand_aliases=(\"爱玛\",),\n    )\n\n    resolution = BrandVehicleResolver().resolve(\n        snapshot,\n        title=\"爱玛新品\",\n        raw_text=None,\n        transcript_text=None,\n    )\n\n    assert resolution.matched is False\n    assert resolution.brand_matches == ()\n    assert resolution.conflicts == (\"ambiguous_brand_alias:爱玛\",)\n\n\ndef test_manual_brand_lock_is_independent_from_vehicle_resolution() -> None:\n",
)

# PostgreSQL: 跨未选中 active Brand 的同名 alias 仍冻结为 ambiguity context。
path = "tests/integration/database/test_brand_vehicle_stage2_repository.py"
replace_once(
    path,
    "    competitor = brand_service.create_brand(\n        BrandCreateRequest(\n            code=\"competitor-b\",\n            display_name=\"竞品 B\",\n            role=\"competitor\",\n            aliases=(\"竞品B\",),\n",
    "    competitor = brand_service.create_brand(\n        BrandCreateRequest(\n            code=\"competitor-b\",\n            display_name=\"竞品 B\",\n            role=\"competitor\",\n            aliases=(\"竞品B\", \"共享品牌词\"),\n",
)
replace_once(
    path,
    "        ),\n        principal=principal,\n        request_id=\"stage2-brand-competitor\",\n    )\n    vehicle = vehicle_service.create_vehicle_model(\n",
    "        ),\n        principal=principal,\n        request_id=\"stage2-brand-competitor\",\n    )\n    brand_service.add_alias(\n        owned.id,\n        BrandAliasCreateRequest(text=\"共享品牌词\"),\n        principal=principal,\n        request_id=\"stage2-brand-owned-shared-alias\",\n    )\n    vehicle = vehicle_service.create_vehicle_model(\n",
)
replace_once(
    path,
    "    BrandCreateRequest,\n    BrandUpdateRequest,\n",
    "    BrandAliasCreateRequest,\n    BrandCreateRequest,\n    BrandUpdateRequest,\n",
)
replace_once(
    path,
    "    assert {item.text for item in selected.brand_aliases} == {\"竞品B\"}\n",
    "    assert {item.text for item in selected.brand_aliases} == {\"竞品B\", \"共享品牌词\"}\n    assert \"共享品牌词\" in selected.ambiguous_brand_aliases\n",
)

# API contract makes ambiguity context part of the frozen payload.
path = "tests/api/test_brand_vehicle_stage2_contract.py"
replace_once(
    path,
    "        \"vehicle_aliases\",\n        \"unresolved_active_vehicle_ids\",\n",
    "        \"vehicle_aliases\",\n        \"ambiguous_brand_aliases\",\n        \"ambiguous_vehicle_aliases\",\n        \"unresolved_active_vehicle_ids\",\n",
)

# Fact doc explicitly records global ambiguity freeze semantics.
path = "docs/blueprint/03_数据库与文件存储.md"
replace_once(
    path,
    "Brand Evidence 与 Vehicle Evidence、Brand Review Lock 与 Vehicle Review Lock 分别独立持久化；人工锁定后自动解析不得覆盖。车型仍允许一条内容匹配 0..N 个，不设主车型；歧义 Alias 保留冲突并 fail-safe，不由系统猜最终结论。",
    "Brand Evidence 与 Vehicle Evidence、Brand Review Lock 与 Vehicle Review Lock 分别独立持久化；人工锁定后自动解析不得覆盖。Snapshot 还冻结全局 active Brand/Vehicle 的歧义 Alias 集合，因此 `selected` Scope 不会因为未选中另一个同名实体而把歧义误判为唯一命中。车型仍允许一条内容匹配 0..N 个，不设主车型；歧义 Alias 保留冲突并 fail-safe，不由系统猜最终结论。",
)

print("Stage 2 independent review fixes applied")