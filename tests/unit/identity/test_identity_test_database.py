"""验证身份集成环境在连接前拒绝业务库，并在初始化失败时释放资源。"""

from __future__ import annotations

from pathlib import Path

import pytest
from aima_ugc.platform.config import PlatformSettings

from tests.integration.platform import identity_test_database


@pytest.mark.parametrize(
    ("ci_mode", "host", "database", "user", "password", "opt_in"),
    [
        (False, "127.0.0.1", "aima_ugc", "aima_ugc", "ci-postgres", "1"),
        (False, "127.0.0.1", "aima_sync_test", "aima_ugc", "ci-postgres", ""),
        (False, "db.example", "aima_sync_test", "aima_ugc", "ci-postgres", "1"),
        (False, "127.0.0.1", "aima_sync_test", "business_owner", "ci-postgres", "1"),
        (False, "127.0.0.1", "aima_sync_test", "aima_ugc", "business-secret", "1"),
        (True, "127.0.0.1", "business_db", "aima_ugc", "ci-postgres", ""),
        (True, "127.0.0.1", "aima_ugc", "aima_ugc", "business-secret", ""),
    ],
)
def test_non_test_target_is_rejected_before_runtime_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ci_mode: bool,
    host: str,
    database: str,
    user: str,
    password: str,
    opt_in: str,
) -> None:
    """应用连接变量不足以授权清库，拒绝路径不得创建数据库运行时。"""

    (tmp_path / "postgres_password").write_text(password, encoding="utf-8")
    settings = PlatformSettings(
        data_dir=tmp_path,
        log_dir=tmp_path,
        secret_dir=tmp_path,
        db_host=host,
        db_name=database,
        db_user=user,
    )
    monkeypatch.setenv("AIMA_DB_HOST", host)
    monkeypatch.setenv("AIMA_DB_PORT", "5432")
    monkeypatch.setenv("GITHUB_ACTIONS", "true" if ci_mode else "false")
    monkeypatch.setenv("AIMA_IDENTITY_TEST_DB", opt_in)
    monkeypatch.setattr(identity_test_database, "load_settings", lambda: settings)
    created: list[bool] = []

    def forbidden_runtime(settings: PlatformSettings) -> None:
        """记录越过连接前保护的尝试，不创建任何 Engine。"""

        created.append(True)
        raise AssertionError("拒绝配置仍创建了数据库运行时")

    monkeypatch.setattr(identity_test_database, "DatabaseRuntime", forbidden_runtime)
    with pytest.raises(RuntimeError, match="拒绝身份测试数据库写入"):
        next(identity_test_database.isolated_identity_database())
    assert created == []


@pytest.mark.parametrize("ci_mode", [False, True])
def test_approved_test_target_disposes_when_initialization_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ci_mode: bool
) -> None:
    """合法本地/CI 配置可到达初始化，初始化异常仍必须释放其连接资源。"""

    (tmp_path / "postgres_password").write_text("ci-postgres", encoding="utf-8")
    settings = PlatformSettings(
        data_dir=tmp_path,
        log_dir=tmp_path,
        secret_dir=tmp_path,
        db_name="aima_ugc" if ci_mode else "aima_sync_test",
    )
    monkeypatch.setenv("AIMA_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("AIMA_DB_PORT", "5432")
    monkeypatch.setenv("GITHUB_ACTIONS", "true" if ci_mode else "false")
    monkeypatch.setenv("AIMA_IDENTITY_TEST_DB", "1")
    monkeypatch.setattr(identity_test_database, "load_settings", lambda: settings)
    disposed: list[bool] = []

    class FailingRuntime:
        """模拟合法测试库初始化异常，不建立真实数据库连接。"""

        def __init__(self, settings: PlatformSettings) -> None:
            """接受已经通过校验的设置。"""

        @property
        def engine(self) -> None:
            """在首次 Engine 访问时模拟连接失败。"""

            raise RuntimeError("isolated initialization failed")

        def dispose(self) -> None:
            """记录异常退出时的资源释放。"""

            disposed.append(True)

    monkeypatch.setattr(identity_test_database, "DatabaseRuntime", FailingRuntime)
    with pytest.raises(RuntimeError, match="isolated initialization failed"):
        next(identity_test_database.isolated_identity_database())
    assert disposed == [True]
