from __future__ import annotations

from pathlib import Path

from aima_ugc.database_schema import metadata

ALLOWED_OWNERS = {
    "analysis",
    "collection",
    "content",
    "dashboard",
    "ingestion",
    "monitoring",
    "notification",
    "platform",
    "reporting",
    "system",
    "vehicles",
}
_PLATFORM_TABLES = {"artifacts", "jobs", "job_attempt_events"}
_SYSTEM_TABLES = {
    "audit_events",
    "keyword_pack_items",
    "keyword_packs",
    "keywords",
    "provider_configs",
    "system_settings",
}
_INGESTION_TABLES = {"processing_import_batches"}
_NOTIFICATION_TABLES = {"notification_events", "notification_inbox_items"}
_VEHICLE_TABLES = {
    "content_vehicle_evidence",
    "content_vehicle_review_locks",
    "keyword_pack_vehicle_models",
    "vehicle_catalog_versions",
    "vehicle_model_aliases",
    "vehicle_models",
}
_CONTENT_PREFIXES = (
    "account_",
    "accounts",
    "comment_",
    "comments",
    "content_",
    "contents",
)
_COLLECTION_PREFIXES = ("collection_", "provider_request")


def _expected_owner(table_name: str) -> str | None:
    """对当前已经形成稳定命名的表族给出唯一 Owner 期望。"""
    if table_name in _PLATFORM_TABLES:
        return "platform"
    if table_name in _SYSTEM_TABLES:
        return "system"
    if table_name in _INGESTION_TABLES:
        return "ingestion"
    if table_name in _NOTIFICATION_TABLES:
        return "notification"
    if table_name in _VEHICLE_TABLES:
        return "vehicles"
    if table_name.startswith(_CONTENT_PREFIXES):
        return "content"
    if table_name.startswith(_COLLECTION_PREFIXES):
        return "collection"
    return None


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
            continue
        if owner not in ALLOWED_OWNERS:
            errors.append(
                f"TABLE_OWNER_UNKNOWN: table={table_name} owner={owner!r} 不在已批准模块集合；"
                "修正 Owner 或先更新架构边界。"
            )
            continue
        expected = _expected_owner(table_name)
        if expected is not None and owner != expected:
            errors.append(
                f"TABLE_OWNER_MISMATCH: table={table_name} owner={owner!r} expected={expected!r}；"
                "稳定表族不得绕过唯一写 Owner。"
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
