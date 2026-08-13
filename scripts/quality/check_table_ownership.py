from __future__ import annotations

from pathlib import Path

from aima_ugc.database_schema import metadata

ALLOWED_OWNERS = {
    "analysis",
    "collection",
    "content",
    "dashboard",
    "monitoring",
    "platform",
    "reporting",
    "system",
}


def main() -> int:
    migration_files = sorted(Path("migrations/versions").glob("*.py"))
    if not migration_files:
        print(
            "TABLE_OWNER_MIGRATION_REQUIRED: migrations/versions/ 缺少 Revision；"
            "先建立 Alembic Migration，再校验表 Owner。"
        )
        return 1

    if not metadata.tables:
        print(
            "TABLE_OWNER_SCHEMA_EMPTY: aima_ugc.database_schema 未注册任何表；"
            "每个应用表必须由唯一 Owner Table 定义注册。"
        )
        return 1

    errors: list[str] = []
    for table_name, table in sorted(metadata.tables.items()):
        owner = table.info.get("owner")
        if not isinstance(owner, str) or not owner:
            errors.append(
                f"TABLE_OWNER_MISSING: table={table_name} 缺少 Table.info['owner']；"
                "由唯一写入模块声明 owner。"
            )
        elif owner not in ALLOWED_OWNERS:
            errors.append(
                f"TABLE_OWNER_UNKNOWN: table={table_name} owner={owner!r} 不在已批准模块集合；"
                "修正 Owner 或先更新架构边界。"
            )

    if errors:
        for error in errors:
            print(error)
        return 1

    owners = ", ".join(
        f"{name}:{table.info['owner']}" for name, table in sorted(metadata.tables.items())
    )
    print(f"TABLE_OWNER_OK: {owners}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
