"""Internal V1 新环境的一次性非敏感配置入口。"""

from __future__ import annotations

from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.bootstrap.internal_v1 import (
    bootstrap_internal_v1_external_secrets,
    internal_v1_tikhub_provider_config_id,
    load_internal_v1_provider_settings,
    provision_internal_v1_provider_config,
    validate_internal_v1_llm_settings,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime


def main() -> int:
    """只在首次部署使用 env/注入 Secret；数据库存在后不再让启动配置覆盖运行时。"""

    settings = load_settings()
    provider = load_internal_v1_provider_settings()
    runtime = DatabaseRuntime(settings)
    try:
        session = runtime.new_session()
        try:
            with session.begin():
                repository = PostgresProviderConfigRepository(session)
                tikhub_managed_by_database = (
                    repository.get(internal_v1_tikhub_provider_config_id()) is not None
                )
                llm_configs = repository.list_all(provider_kind="llm")
                llm_managed_by_database = bool(llm_configs)
                active_llm_exists = repository.get_default("llm") is not None
        finally:
            session.close()

        bootstrap_internal_v1_external_secrets(
            settings,
            provider,
            bootstrap_tikhub=not tikhub_managed_by_database,
            bootstrap_llm=not llm_managed_by_database,
        )
        llm_configured = (
            active_llm_exists
            if llm_managed_by_database
            else validate_internal_v1_llm_settings(settings)
        )

        session = runtime.new_session()
        try:
            with session.begin():
                persisted_tikhub = provision_internal_v1_provider_config(
                    session,
                    settings=settings,
                    provider=provider,
                )
        finally:
            session.close()
    finally:
        runtime.dispose()

    tikhub_enabled = persisted_tikhub is not None and persisted_tikhub.enabled
    print(f"TikHub Internal V1: {'ENABLED' if tikhub_enabled else 'DISABLED'}")
    print(f"LLM Runtime: {'CONFIGURED' if llm_configured else 'DISABLED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
