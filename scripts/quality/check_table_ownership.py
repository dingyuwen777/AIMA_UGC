"""检查数据库表写入 Owner；Stage 1 尚无业务表时明确跳过。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    versions = ROOT / "migrations" / "versions"
    migration_files = list(versions.glob("*.py")) if versions.exists() else []
    if not migration_files:
        print("TABLE_OWNER_NOT_APPLICABLE: Stage 1 尚未建立业务表或 Alembic Revision。")
        return 0

    print("TABLE_OWNER_RULE_NOT_READY: 已发现 Migration，需在 Stage 3 实现表 Owner 校验。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
