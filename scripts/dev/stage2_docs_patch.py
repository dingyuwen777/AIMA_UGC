"""Temporary Stage 2 branch docs patch; deleted before PR validation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: expected one match, got {text.count(old)}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py",
    '    """Stage 2 Brand 管理、统一快照、车型品牌归属和证据写入 Owner。"""',
    '    """Brand 管理、统一快照和证据 Owner；Vehicle 写入委托唯一 Vehicle Owner。"""',
)

replace_once(
    "docs/blueprint/03_数据库与文件存储.md",
    "Vehicle Catalog 拥有品牌/车型目录、Pack↔车型关系以及内容品牌/车型证据和人工锁；Collection 只拥有 Plan↔车型关联表。定义分别位于 [`backend/src/aima_ugc/modules/vehicles/tables.py`](../../backend/src/aima_ugc/modules/vehicles/tables.py) 与 [`backend/src/aima_ugc/modules/collection/tables.py`](../../backend/src/aima_ugc/modules/collection/tables.py)。品牌与车型共用 `vehicle_catalog_versions`；`vehicle_models.brand_id` 当前为 nullable，旧车型不会在 Migration 中被猜测或回填品牌。车型允许 0..N 个，不设主车型。无引用车型可以物理删除；有引用后只允许废弃/合并。连续合并保持指向最终标准车型的单跳重定向；查询/导出按最终车型聚合，历史内容证据仍保留原模型和目录版本。精确品牌证据来源、幂等约束和索引继续以当前 SQLAlchemy metadata 与 Alembic Migration 为机器事实。",
    "Vehicle Catalog 拥有品牌/车型目录、Pack↔车型关系以及内容品牌/车型证据和人工锁；Collection 只拥有 Plan↔车型关联表。定义分别位于 [`backend/src/aima_ugc/modules/vehicles/tables.py`](../../backend/src/aima_ugc/modules/vehicles/tables.py) 与 [`backend/src/aima_ugc/modules/collection/tables.py`](../../backend/src/aima_ugc/modules/collection/tables.py)。品牌与车型共用 `vehicle_catalog_versions`；`vehicle_models.brand_id` 在数据库层仍为 nullable，用作 Stage 1 历史数据的显式修复窗口，但 Stage 2 起所有新的 active Vehicle 创建，以及任何更新后仍为 active 的 Vehicle，都必须绑定有效 active Brand。存在 active Vehicle 的 Brand 不能停用；历史 active Vehicle 若品牌为空或品牌已失效，会被完整性检查显式暴露，不能从 Keyword Pack、Collection Plan 或旧关系猜测品牌。\n\nStage 2 的统一 `CatalogSnapshot` 支持 `all_active` 与 `selected brand_ids` 两种冻结 Scope。`selected` 会把所选 active Brand 下的全部 active Vehicle 及对应 Brand/Vehicle Alias 一并冻结；`all_active` 在仍有 active Vehicle 缺少有效 active Brand 时 fail closed。Snapshot 与目录写都在同一个 `vehicle_catalog_versions` seed lock 上协调，因此一个事务读取到的 catalog version、Brand、Vehicle 和 Alias 集合不会被并发目录写穿透。纯确定性 `BrandVehicleResolver` 只消费 `CanonicalContentV1.title/text` 与冻结 Snapshot：Brand Alias 产生 Brand，Vehicle Alias 同时产生 Vehicle 与所属 Brand；不同非歧义 Brand/Vehicle 可以同时命中，只有同一规范化 Alias 指向多个 active 实体时保留冲突且不猜结论。现有 Collection `VehicleCatalogSnapshot`、Keyword Pack/Plan 关系与运行语义保持不变。车型允许 0..N 个，不设主车型；无引用车型可以物理删除，有引用后只允许废弃/合并。历史内容证据仍保留原模型和目录版本。精确品牌证据来源、幂等约束和索引继续以当前 SQLAlchemy metadata 与 Alembic Migration 为机器事实。",
)

print("Stage 2 docs patch applied")
