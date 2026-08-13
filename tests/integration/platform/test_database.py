from sqlalchemy import text

from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime


def test_database_runtime_connects_to_real_postgresql_18() -> None:
    settings = load_settings()
    runtime = DatabaseRuntime(settings)

    try:
        assert runtime.ping() is True
        with runtime.new_session() as session:
            version_num = int(session.execute(text("SHOW server_version_num")).scalar_one())
        assert version_num // 10_000 == 18
    finally:
        runtime.dispose()
