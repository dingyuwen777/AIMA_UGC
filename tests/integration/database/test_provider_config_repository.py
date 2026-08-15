"""Stage 7 Provider Config PostgreSQL Repository 集成测试。"""

from __future__ import annotations

from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.modules.system.tables import provider_configs_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime


def test_provider_configs_keep_stable_identity_and_never_store_raw_secret() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    config_id = uuid4()
    first = ProviderConfig(
        id=config_id,
        provider="tikhub",
        display_name="TikHub 主账号",
        base_url="https://api.tikhub.io",
        secret_ref="providers/tikhub/main/api-key",
        enabled=True,
    )
    try:
        repository = PostgresProviderConfigRepository(session)
        with session.begin():
            created = repository.create(first)
        with session.begin():
            updated = repository.update_settings(
                config_id,
                display_name="TikHub 主账号（更新）",
                base_url="https://api.tikhub.io",
                secret_ref="providers/tikhub/main/api-key-v2",
                enabled=False,
            )
            loaded = repository.get(config_id)

        assert created.id == config_id
        assert updated.id == config_id
        assert updated.provider == "tikhub"
        assert updated.display_name == "TikHub 主账号（更新）"
        assert updated.secret_ref == "providers/tikhub/main/api-key-v2"
        assert loaded == updated

        column_names = set(provider_configs_table.c.keys())
        assert "secret_ref" in column_names
        assert "api_key" not in column_names
        assert "token" not in column_names
        assert "credential" not in column_names
    finally:
        session.close()
        runtime.dispose()
