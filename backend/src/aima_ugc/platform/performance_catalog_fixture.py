"""专用容量数据库的大品牌车型目录 Fixture；正式服务不调用。"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select

from aima_ugc.modules.vehicles.models import normalize_vehicle_text
from aima_ugc.modules.vehicles.tables import (
    vehicle_brand_aliases_table,
    vehicle_brands_table,
    vehicle_catalog_versions_table,
    vehicle_model_aliases_table,
    vehicle_models_table,
)
from aima_ugc.platform.time import beijing_now

if TYPE_CHECKING:
    from aima_ugc.bootstrap.runtime import PlatformRuntime


@dataclass(frozen=True, slots=True)
class CatalogFixtureSummary:
    """基准目录规模和准备耗时。"""

    brand_ids: tuple[UUID, ...]
    brand_count: int
    vehicle_count: int
    alias_count: int
    setup_seconds: float


def seed_catalog_fixture(
    runtime: PlatformRuntime,
    *,
    brand_count: int,
    vehicles_per_brand: int,
) -> CatalogFixtureSummary:
    """一次事务批量建立互不命中的目录噪声，计时窗口仍只跑生产读写实现。"""

    if not runtime.settings.db_name.endswith("_capacity"):
        raise RuntimeError("大目录 Fixture 只允许写入专用容量数据库")
    if not 0 <= brand_count <= 1_000:
        raise ValueError("catalog brand_count 必须在 0 到 1000 之间")
    if not 0 <= vehicles_per_brand <= 1_000:
        raise ValueError("catalog vehicles_per_brand 必须在 0 到 1000 之间")
    if brand_count == 0 and vehicles_per_brand:
        raise ValueError("没有目录品牌时不能创建车型")
    vehicle_count = brand_count * vehicles_per_brand
    if vehicle_count > 50_000:
        raise ValueError("catalog Fixture 车型总数不能超过 50000")
    if brand_count == 0:
        return CatalogFixtureSummary((), 0, 0, 0, 0.0)

    started = perf_counter()
    now = beijing_now()
    nonce = uuid4().hex[:10]
    brand_rows: list[dict[str, object]] = []
    brand_alias_rows: list[dict[str, object]] = []
    vehicle_rows: list[dict[str, object]] = []
    vehicle_alias_rows: list[dict[str, object]] = []
    brand_ids: list[UUID] = []

    with runtime.database.engine.begin() as connection:
        catalog_version = (
            int(connection.scalar(select(func.max(vehicle_catalog_versions_table.c.version))) or 0)
            + 1
        )
        connection.execute(
            insert(vehicle_catalog_versions_table).values(
                version=catalog_version,
                reason="performance_catalog_fixture",
                actor_ref="capacity-benchmark",
                created_at=now,
            )
        )
        for brand_index in range(brand_count):
            brand_id = uuid4()
            brand_ids.append(brand_id)
            brand_alias = f"目录噪声品牌{nonce}{brand_index:04d}"
            brand_rows.append(
                {
                    "id": brand_id,
                    "code": f"CAP_{nonce.upper()}_{brand_index:04d}",
                    "display_name": brand_alias,
                    "role": "competitor",
                    "status": "active",
                    "version": 1,
                    "catalog_version": catalog_version,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            brand_alias_rows.append(
                {
                    "id": uuid4(),
                    "brand_id": brand_id,
                    "text": brand_alias,
                    "normalized_text": normalize_vehicle_text(brand_alias),
                    "created_at": now,
                }
            )
            for vehicle_index in range(vehicles_per_brand):
                vehicle_id = uuid4()
                vehicle_alias = f"目录噪声车型{nonce}{brand_index:04d}{vehicle_index:04d}"
                vehicle_rows.append(
                    {
                        "id": vehicle_id,
                        "code": (
                            f"CAP_MODEL_{nonce.upper()}_{brand_index:04d}_{vehicle_index:04d}"
                        ),
                        "display_name": vehicle_alias,
                        "series_name": None,
                        "category_name": None,
                        "brand_id": brand_id,
                        "status": "active",
                        "version": 1,
                        "catalog_version": catalog_version,
                        "merged_into_id": None,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                vehicle_alias_rows.append(
                    {
                        "id": uuid4(),
                        "vehicle_model_id": vehicle_id,
                        "text": vehicle_alias,
                        "normalized_text": normalize_vehicle_text(vehicle_alias),
                        "created_at": now,
                    }
                )
        connection.execute(insert(vehicle_brands_table), brand_rows)
        connection.execute(insert(vehicle_brand_aliases_table), brand_alias_rows)
        if vehicle_rows:
            connection.execute(insert(vehicle_models_table), vehicle_rows)
            connection.execute(insert(vehicle_model_aliases_table), vehicle_alias_rows)

    return CatalogFixtureSummary(
        brand_ids=tuple(brand_ids),
        brand_count=brand_count,
        vehicle_count=vehicle_count,
        alias_count=brand_count + vehicle_count,
        setup_seconds=perf_counter() - started,
    )


__all__ = ["CatalogFixtureSummary", "seed_catalog_fixture"]
