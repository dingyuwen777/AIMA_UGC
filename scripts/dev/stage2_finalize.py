"""一次性 Stage 2 收尾补丁；执行后由 workflow 删除，不进入最终 PR。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Resolver: Vehicle 派生 Brand Evidence 继承真实匹配文本/字段，保证可追溯。
path = "backend/src/aima_ugc/modules/vehicles/brand_vehicle.py"
replace_once(
    path,
    "                vehicle_ids=vehicle_ids,\n                texts=texts,\n",
    "                vehicle_ids=vehicle_ids,\n                vehicle_evidence=vehicle_evidence,\n                texts=texts,\n",
)
replace_once(
    path,
    "        vehicle_ids: tuple[UUID, ...],\n        texts: dict[str, str | None],\n",
    "        vehicle_ids: tuple[UUID, ...],\n        vehicle_evidence: tuple[ResolverEvidence, ...],\n        texts: dict[str, str | None],\n",
)
replace_once(
    path,
    "            resolved.add(vehicle.brand_id)\n            evidence.append(\n                ResolverEvidence(\n                    entity_id=vehicle.brand_id,\n                    source=\"vehicle_match\",\n                    matched_text=None,\n                    source_field=None,\n                    derived_vehicle_model_id=vehicle_id,\n                )\n            )\n",
    "            resolved.add(vehicle.brand_id)\n            provenance = next(\n                (item for item in vehicle_evidence if item.entity_id == vehicle_id),\n                None,\n            )\n            evidence.append(\n                ResolverEvidence(\n                    entity_id=vehicle.brand_id,\n                    source=\"vehicle_match\",\n                    matched_text=None if provenance is None else provenance.matched_text,\n                    source_field=None if provenance is None else provenance.source_field,\n                    derived_vehicle_model_id=vehicle_id,\n                )\n            )\n",
)

# Existing U1-U5 PostgreSQL tests: public active Vehicle create now explicitly binds a Brand.
path = "tests/integration/database/test_u1_u5_administration.py"
replace_once(
    path,
    "from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService\n",
    "from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService\nfrom aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService\n",
)
replace_once(
    path,
    ")\nfrom aima_ugc.modules.administration import (\n",
    ")\nfrom aima_ugc.contracts.brand_vehicle import BrandCreateRequest\nfrom aima_ugc.modules.administration import (\n",
)
replace_once(
    path,
    "\n\ndef test_vehicle_merge_redirects_future_references_and_audits_mutations(runtime) -> None:  # type: ignore[no-untyped-def]\n",
    "\n\ndef _create_owned_brand(runtime, principal: Principal, *, code: str):  # type: ignore[no-untyped-def]\n    return PostgresBrandVehicleHttpService(runtime).create_brand(\n        BrandCreateRequest(\n            code=code,\n            display_name=f\"测试品牌 {code}\",\n            role=\"owned\",\n            aliases=(f\"{code}品牌\",),\n        ),\n        principal=principal,\n        request_id=f\"brand-{code}\",\n    )\n\n\ndef test_vehicle_merge_redirects_future_references_and_audits_mutations(runtime) -> None:  # type: ignore[no-untyped-def]\n",
)
replace_once(
    path,
    "    )\n    source = service.create_vehicle_model(\n        VehicleModelCreateRequest(code=\"Q7-OLD\", display_name=\"旧 Q7\", aliases=(\"旧Q7\",)),\n",
    "    )\n    brand = _create_owned_brand(runtime, principal, code=\"U1-MERGE\")\n    source = service.create_vehicle_model(\n        VehicleModelCreateRequest(\n            code=\"Q7-OLD\", display_name=\"旧 Q7\", brand_id=brand.id, aliases=(\"旧Q7\",)\n        ),\n",
)
replace_once(
    path,
    "        VehicleModelCreateRequest(code=\"Q7\", display_name=\"爱玛 Q7\", aliases=(\"Q7\",)),\n",
    "        VehicleModelCreateRequest(\n            code=\"Q7\", display_name=\"爱玛 Q7\", brand_id=brand.id, aliases=(\"Q7\",)\n        ),\n",
)
replace_once(
    path,
    "            display_name=\"爱玛 Q7 标准车型\",\n            aliases=(\"爱玛Q7标准车型\",),\n",
    "            display_name=\"爱玛 Q7 标准车型\",\n            brand_id=brand.id,\n            aliases=(\"爱玛Q7标准车型\",),\n",
)
replace_once(
    path,
    "    )\n    created = service.create_vehicle_model(\n        VehicleModelCreateRequest(\n            code=\"CLASS-Q7\",\n",
    "    )\n    brand = _create_owned_brand(runtime, principal, code=\"U1-CLASS\")\n    created = service.create_vehicle_model(\n        VehicleModelCreateRequest(\n            code=\"CLASS-Q7\",\n",
)
replace_once(
    path,
    "            display_name=\"爱玛 Q7\",\n            series_name=\" Q 系列 \",\n",
    "            display_name=\"爱玛 Q7\",\n            brand_id=brand.id,\n            series_name=\" Q 系列 \",\n",
)
replace_once(
    path,
    "    )\n    created = service.create_vehicle_model(\n        VehicleModelCreateRequest(code=\"LUNA\", display_name=\"爱玛露娜\", aliases=(\"露娜\",)),\n",
    "    )\n    brand = _create_owned_brand(runtime, principal, code=\"U1-DELETE\")\n    created = service.create_vehicle_model(\n        VehicleModelCreateRequest(\n            code=\"LUNA\", display_name=\"爱玛露娜\", brand_id=brand.id, aliases=(\"露娜\",)\n        ),\n",
)

# Static quality: use Annotated Query metadata and deterministic import ordering.
path = "backend/src/aima_ugc/bootstrap/brand_vehicle_http.py"
replace_once(path, "from typing import Any, cast\n", "from typing import Annotated, Any, cast\n")
replace_once(
    path,
    "    BrandAliasResponse,\n    BrandFilterScope,\n",
    "    BrandAliasResponse,\n    BrandCreateRequest,\n    BrandFilterScope,\n",
)
replace_once(path, "    BrandVehicleCatalogSnapshotResponse,\n    BrandCreateRequest,\n", "    BrandVehicleCatalogSnapshotResponse,\n")
replace_once(
    path,
    "        search: str | None = Query(default=None, min_length=1, max_length=200),\n        status_value: BrandStatus | None = Query(default=None, alias=\"status\"),\n        role: BrandRole | None = None,\n        offset: int = Query(default=0, ge=0),\n        limit: int = Query(default=50, ge=1, le=200),\n",
    "        search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,\n        status_value: Annotated[BrandStatus | None, Query(alias=\"status\")] = None,\n        role: BrandRole | None = None,\n        offset: Annotated[int, Query(ge=0)] = 0,\n        limit: Annotated[int, Query(ge=1, le=200)] = 50,\n",
)
replace_once(
    path,
    "        brand_id: list[UUID] | None = Query(default=None),\n",
    "        brand_id: Annotated[list[UUID] | None, Query()] = None,\n",
)

path = "backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py"
replace_once(
    path,
    "    vehicle_catalog_versions_table,\n    vehicle_brands_table,\n",
    "    vehicle_brands_table,\n    vehicle_catalog_versions_table,\n",
)

path = "tests/integration/database/test_brand_vehicle_stage2_repository.py"
replace_once(
    path,
    "            # 该用例只验证 Evidence/Lock Owner 语义；临时关闭 FK trigger，避免构造无关 Content 聚合。\n",
    "            # 这里只验证 Evidence/Lock Owner 语义；关闭 FK trigger，\n            # 避免为该独立持久化测试构造无关 Content 聚合。\n",
)

# Fact doc: Stage 2 now has a formal management/readiness/snapshot boundary; runtime filtering is still Stage 3/4.
path = "docs/blueprint/03_数据库与文件存储.md"
replace_once(
    path,
    "Vehicle Catalog 拥有品牌/车型目录、Pack↔车型关系以及内容品牌/车型证据和人工锁；Collection 只拥有 Plan↔车型关联表。定义分别位于 [`backend/src/aima_ugc/modules/vehicles/tables.py`](../../backend/src/aima_ugc/modules/vehicles/tables.py) 与 [`backend/src/aima_ugc/modules/collection/tables.py`](../../backend/src/aima_ugc/modules/collection/tables.py)。品牌与车型共用 `vehicle_catalog_versions`；`vehicle_models.brand_id` 当前为 nullable，旧车型不会在 Migration 中被猜测或回填品牌。车型允许 0..N 个，不设主车型。无引用车型可以物理删除；有引用后只允许废弃/合并。连续合并保持指向最终标准车型的单跳重定向；查询/导出按最终车型聚合，历史内容证据仍保留原模型和目录版本。精确品牌证据来源、幂等约束和索引继续以当前 SQLAlchemy metadata 与 Alembic Migration 为机器事实。\n",
    "Vehicle Catalog 拥有品牌/车型目录、Pack↔车型关系以及内容品牌/车型证据和人工锁；Collection 只拥有 Plan↔车型关联表。定义分别位于 [`backend/src/aima_ugc/modules/vehicles/tables.py`](../../backend/src/aima_ugc/modules/vehicles/tables.py) 与 [`backend/src/aima_ugc/modules/collection/tables.py`](../../backend/src/aima_ugc/modules/collection/tables.py)。品牌与车型共用唯一 `vehicle_catalog_versions`；Brand 创建、修改、识别词变更以及 Vehicle 品牌归属变更都会推进同一目录版本。`vehicle_models.brand_id` 的数据库列仍为 nullable，用于承接 Stage 1 前已存在且尚未人工校准的车型；Stage 2 的正式管理 API 新建 active Vehicle 时必须显式绑定有效 active Brand，旧车型不会根据 Keyword Pack、名称或其他关系被猜测回填。`/api/v1/vehicle-catalog/readiness` 用于暴露尚未完成有效品牌归属的 active Vehicle，由管理员显式修复。\n\nStage 2 另外提供独立的 Brand/Vehicle 统一 Catalog Snapshot。`all_active` 冻结全部 active Brand，`selected` 冻结显式 Brand ID；选择 Brand 会自动包含该 Brand 的全部 active Vehicle，并同时冻结 Brand Alias、Vehicle Alias 与 `catalog_version`。这套 Snapshot/Resolver 是后续 Excel/TikHub 自动过滤的稳定输入，但 Stage 2 **没有**切换采集/导入 Runtime，Collection 现有 Vehicle snapshot Contract 和 Pack/Plan 关系保持不变。Brand Evidence 与 Vehicle Evidence、Brand Review Lock 与 Vehicle Review Lock 分别独立持久化；人工锁定后自动解析不得覆盖。车型仍允许一条内容匹配 0..N 个，不设主车型；歧义 Alias 保留冲突并 fail-safe，不由系统猜最终结论。无引用车型可以物理删除；有引用后只允许废弃/合并。连续合并保持指向最终标准车型的单跳重定向；查询/导出按最终车型聚合，历史内容证据仍保留原模型和目录版本。精确品牌证据来源、幂等约束和索引继续以当前 SQLAlchemy metadata 与 Alembic Migration 为机器事实。\n",
)

print("Stage 2 finalization patches applied")