"""报告破坏性 fixture 必须在清表和创建运行时之前拒绝不安全连接。"""

from pathlib import Path

import pytest
from aima_ugc.platform.config import load_settings

from tests.integration.reporting import test_database_reports as workflows


@pytest.mark.parametrize(
    ("host", "port", "name", "actions", "explicit"),
    [
        ("127.0.0.1", 5432, "aima_ugc", "", ""),
        ("127.0.0.1", 5432, "aima_ugc", "true", ""),
        ("production.example", 55437, "aima_report_test", "", ""),
        ("production.example", 5432, "aima_ugc", "true", "1"),
        ("127.0.0.1", 5432, "production", "true", "1"),
    ],
)
def test_unsafe_report_database_is_rejected_before_runtime_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    host: str,
    port: int,
    name: str,
    actions: str,
    explicit: str,
) -> None:
    settings = load_settings().model_copy(
        update={"db_host": host, "db_port": port, "db_name": name}
    )
    monkeypatch.setenv("GITHUB_ACTIONS", actions)
    monkeypatch.setenv("AIMA_REPORT_TEST_DATABASE", explicit)
    monkeypatch.setattr(workflows, "load_settings", lambda: settings)

    def forbidden_runtime(**kwargs: object) -> None:
        pytest.fail("不安全数据库配置不得创建运行时或执行清表")

    monkeypatch.setattr(workflows, "create_worker_runtime", forbidden_runtime)
    with pytest.raises(pytest.skip.Exception, match="只允许 report 专用"):
        next(workflows.report_system.__wrapped__(tmp_path))
