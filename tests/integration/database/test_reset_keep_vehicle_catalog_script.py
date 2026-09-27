"""部署重置脚本中的品牌/车型目录指纹 PostgreSQL 集成验证。"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import text


_SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts" / "deploy" / "reset_keep_vehicle_catalog.sh"
)


def _catalog_fingerprint_sql() -> str:
    """从正式 Shell 脚本提取目录指纹 SQL，避免测试复制第二套查询实现。"""

    script = _SCRIPT.read_text(encoding="utf-8")
    match = re.search(
        r'CATALOG_FINGERPRINT="\$\(cat <<\'SQL\' \| db\n(?P<sql>SELECT\n.*?);\nSQL\n\)"',
        script,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError("未找到 CATALOG_FINGERPRINT 正式 SQL")
    return f"{match.group('sql')};"


def test_reset_catalog_fingerprint_sql_runs_on_postgresql_and_detects_change() -> None:
    """真实 PostgreSQL 应能执行正式指纹 SQL，并感知目录内容变化。"""

    runtime = DatabaseRuntime(load_settings())
    connection = runtime.engine.connect()
    transaction = connection.begin()
    try:
        fingerprint_sql = text(_catalog_fingerprint_sql())
        before = connection.scalar(fingerprint_sql)
        assert isinstance(before, str)
        assert len(before.split("|")) == 5

        brand_id = uuid4()
        connection.execute(
            text(
                """
                INSERT INTO vehicle_brands(
                  id, code, display_name, role, status, version,
                  catalog_version, created_at, updated_at
                ) VALUES (
                  :id, :code, :name, 'owned', 'active', 1,
                  1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": brand_id,
                "code": f"reset-fingerprint-{brand_id.hex}",
                "name": "重置指纹测试品牌",
            },
        )

        after = connection.scalar(fingerprint_sql)
        assert isinstance(after, str)
        assert after != before
    finally:
        transaction.rollback()
        connection.close()
        runtime.dispose()
