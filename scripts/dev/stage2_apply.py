"""临时执行脚本：把 Stage 2 的 brand_id 语义补入既有 Vehicle 管理实现。"""

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
        raise RuntimeError(f"{path}: expected exactly one match, got {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Public Vehicle Contract: expose brand_id without guessing legacy rows; runtime enforces new active create.
replace_once(
    "backend/src/aima_ugc/contracts/administration.py",
    "    display_name: str = Field(min_length=1, max_length=200)\n    aliases: tuple[str, ...] = Field(default=(), max_length=100)\n",
    "    display_name: str = Field(min_length=1, max_length=200)\n    brand_id: UUID | None = None\n    aliases: tuple[str, ...] = Field(default=(), max_length=100)\n",
)
replace_once(
    "backend/src/aima_ugc/contracts/administration.py",
    "    status: Literal[\"active\", \"deprecated\"] | None = None\n    series_name: str | None = Field(default=None, min_length=1, max_length=200)\n",
    "    status: Literal[\"active\", \"deprecated\"] | None = None\n    brand_id: UUID | None = None\n    series_name: str | None = Field(default=None, min_length=1, max_length=200)\n",
)
replace_once(
    "backend/src/aima_ugc/contracts/administration.py",
    "            and not self.model_fields_set.intersection({\"series_name\", \"category_name\"})\n",
    "            and not self.model_fields_set.intersection(\n                {\"brand_id\", \"series_name\", \"category_name\"}\n            )\n",
)
replace_once(
    "backend/src/aima_ugc/contracts/administration.py",
    "    display_name: str\n    series_name: str | None = None\n",
    "    display_name: str\n    brand_id: UUID | None = None\n    series_name: str | None = None\n",
)

# Vehicle domain repository: carry brand_id through rows/create/update and fail closed on active status.
replace_once(
    "backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py",
    "    vehicle_catalog_versions_table,\n    vehicle_model_aliases_table,\n",
    "    vehicle_catalog_versions_table,\n    vehicle_brands_table,\n    vehicle_model_aliases_table,\n",
)
replace_once(
    "backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py",
    "        display_name=cast(str, row[\"display_name\"]),\n        series_name=cast(str | None, row[\"series_name\"]),\n",
    "        display_name=cast(str, row[\"display_name\"]),\n        brand_id=cast(UUID | None, row[\"brand_id\"]),\n        series_name=cast(str | None, row[\"series_name\"]),\n",
)
replace_once(
    "backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py",
    "        aliases: tuple[str, ...],\n        actor_ref: str,\n        series_name: str | None = None,\n",
    "        aliases: tuple[str, ...],\n        actor_ref: str,\n        brand_id: UUID | None = None,\n        series_name: str | None = None,\n",
)
replace_once(
    "backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py",
    "                    display_name=display_name,\n                    series_name=series_name,\n",
    "                    display_name=display_name,\n                    brand_id=brand_id,\n                    series_name=series_name,\n",
)
replace_once(
    "backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py",
    "        classification: dict[str, str | None] | None = None,\n",
    "        classification: dict[str, object | None] | None = None,\n",
)
replace_once(
    "backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py",
    "        if current.status == \"merged\":\n            raise RuntimeError(\"已合并车型不能直接编辑\")\n        catalog_version = self.next_catalog_version(reason=\"vehicle_updated\", actor_ref=actor_ref)\n",
    "        if current.status == \"merged\":\n            raise RuntimeError(\"已合并车型不能直接编辑\")\n        requested_brand_id = current.brand_id\n        if classification is not None and \"brand_id\" in classification:\n            requested_brand_id = cast(UUID | None, classification[\"brand_id\"])\n        effective_status = status or current.status\n        if effective_status == \"active\":\n            if requested_brand_id is None:\n                raise RuntimeError(\"active 车型必须绑定 active 品牌\")\n            brand_status = self._session.scalar(\n                select(vehicle_brands_table.c.status).where(\n                    vehicle_brands_table.c.id == requested_brand_id\n                )\n            )\n            if brand_status != \"active\":\n                raise RuntimeError(\"active 车型只能绑定有效 active 品牌\")\n        catalog_version = self.next_catalog_version(reason=\"vehicle_updated\", actor_ref=actor_ref)\n",
)
replace_once(
    "backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py",
    "        for field in (\"series_name\", \"category_name\"):\n",
    "        for field in (\"brand_id\", \"series_name\", \"category_name\"):\n",
)

# Administration service: new active Vehicle requires an explicit active Brand; update remains one transaction/version.
replace_once(
    "backend/src/aima_ugc/bootstrap/administration_http.py",
    "from aima_ugc.adapters.persistence.postgres.system import (\n",
    "from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository\nfrom aima_ugc.adapters.persistence.postgres.system import (\n",
)
replace_once(
    "backend/src/aima_ugc/bootstrap/administration_http.py",
    "                repository = PostgresVehicleCatalogRepository(session)\n                model = repository.create_model(\n",
    "                repository = PostgresVehicleCatalogRepository(session)\n                brand_repository = PostgresBrandVehicleRepository(session)\n                if body.brand_id is None:\n                    raise AdministrationConflict(\"新建 active 车型必须绑定 active 品牌\")\n                try:\n                    brand_repository.require_active_brand(body.brand_id)\n                except LookupError as exc:\n                    raise AdministrationResourceNotFound from exc\n                except RuntimeError as exc:\n                    raise AdministrationConflict(str(exc)) from exc\n                model = repository.create_model(\n",
)
replace_once(
    "backend/src/aima_ugc/bootstrap/administration_http.py",
    "                    aliases=body.aliases,\n                    series_name=body.series_name,\n",
    "                    aliases=body.aliases,\n                    brand_id=body.brand_id,\n                    series_name=body.series_name,\n",
)
replace_once(
    "backend/src/aima_ugc/bootstrap/administration_http.py",
    "                    detail={\"code\": model.code, \"catalog_version\": model.catalog_version},\n",
    "                    detail={\n                        \"code\": model.code,\n                        \"brand_id\": str(model.brand_id),\n                        \"catalog_version\": model.catalog_version,\n                    },\n",
)
replace_once(
    "backend/src/aima_ugc/bootstrap/administration_http.py",
    "                        classification=body.model_dump(\n                            include={\"series_name\", \"category_name\"}, exclude_unset=True\n                        ),\n",
    "                        classification=body.model_dump(\n                            include={\"brand_id\", \"series_name\", \"category_name\"},\n                            exclude_unset=True,\n                        ),\n",
)
replace_once(
    "backend/src/aima_ugc/bootstrap/administration_http.py",
    "        display_name=model.display_name,\n        series_name=model.series_name,\n",
    "        display_name=model.display_name,\n        brand_id=model.brand_id,\n        series_name=model.series_name,\n",
)

print("Stage 2 production patches applied.")
