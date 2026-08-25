from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import text


def test_database_runtime_connects_to_real_postgresql_18() -> None:
    """真实 PostgreSQL Session 使用北京时间，同时 timestamptz 保持同一绝对时刻。"""
    settings = load_settings()
    runtime = DatabaseRuntime(settings)

    try:
        assert runtime.ping() is True
        with runtime.new_session() as session:
            version_num = int(session.execute(text("SHOW server_version_num")).scalar_one())
            session_timezone = str(session.execute(text("SHOW TimeZone")).scalar_one())
            instant = session.execute(
                text("SELECT TIMESTAMPTZ '2026-08-25 01:44:19+00'")
            ).scalar_one()
        assert version_num // 10_000 == 18
        assert session_timezone == "Asia/Shanghai"
        assert instant.isoformat() == "2026-08-25T09:44:19+08:00"
    finally:
        runtime.dispose()
