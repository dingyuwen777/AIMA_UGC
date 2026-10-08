"""为新增身份集成回归提供连接前校验的独占测试数据库。"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from aima_ugc.modules.identity.tables import (
    identity_external_identities_table,
    identity_login_states_table,
    identity_principals_table,
    identity_sessions_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.database.metadata import metadata
from sqlalchemy.orm import Session, sessionmaker


def isolated_identity_database() -> Iterator[sessionmaker[Session]]:
    """仅在已验证的专用 CI/本地测试库清理身份表，所有退出路径释放连接池。

    本地调用须显式设置 AIMA_IDENTITY_TEST_DB=1，库名固定为 aima_sync_test；
    CI 使用仓库既有 aima_ugc 库。两者都要求回环地址和 ci-postgres 专用凭据。
    校验发生在创建 DatabaseRuntime 之前，应用数据库变量本身不授予清库权限。
    """

    if not os.environ.get("AIMA_DB_HOST") or not os.environ.get("AIMA_DB_PORT"):
        pytest.skip("未提供 AIMA_DB_HOST / AIMA_DB_PORT，跳过真实 SQL 校验")
    settings = load_settings()
    ci_mode = os.environ.get("GITHUB_ACTIONS") == "true"
    expected_name = "aima_ugc" if ci_mode else "aima_sync_test"
    if (
        settings.db_host not in {"127.0.0.1", "localhost"}
        or settings.db_user != "aima_ugc"
        or settings.db_name != expected_name
        or (not ci_mode and os.environ.get("AIMA_IDENTITY_TEST_DB") != "1")
        or not settings.postgres_password_file.is_file()
        or settings.postgres_password_file.read_text(encoding="utf-8").strip() != "ci-postgres"
    ):
        raise RuntimeError("拒绝身份测试数据库写入：需要明确授权的回环专用测试库")

    runtime = DatabaseRuntime(settings)
    try:
        metadata.create_all(runtime.engine)
        # 专用库独占且按外键顺序清理；不能让前一用例的身份掩盖企业分流缺陷。
        with runtime.engine.begin() as connection:
            for table in (
                identity_sessions_table,
                identity_login_states_table,
                identity_external_identities_table,
                identity_principals_table,
            ):
                connection.execute(table.delete())
        yield sessionmaker(bind=runtime.engine)
    finally:
        runtime.dispose()
