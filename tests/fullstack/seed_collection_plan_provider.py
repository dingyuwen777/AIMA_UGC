"""为不调用外部 Provider 的 Collection Plan 全栈验收准备路由事实。"""

from __future__ import annotations

from uuid import UUID

from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.bootstrap.runtime import create_platform_runtime
from aima_ugc.modules.system.models import ProviderConfig

PROVIDER_CONFIG_ID = UUID("8f000000-0000-4000-8000-000000000001")


def main() -> None:
    runtime = create_platform_runtime("fullstack-seed")
    session = runtime.database.new_session()
    try:
        with session.begin():
            repository = PostgresProviderConfigRepository(session)
            current = repository.get(PROVIDER_CONFIG_ID)
            if current is None:
                repository.create(
                    ProviderConfig(
                        id=PROVIDER_CONFIG_ID,
                        provider="tikhub",
                        display_name="Stage 8F Plan Full-stack",
                        base_url="https://api.tikhub.io",
                        secret_ref="stage8f-plan-provider-not-used",
                        enabled=True,
                    )
                )
            else:
                repository.update_settings(
                    PROVIDER_CONFIG_ID,
                    display_name="Stage 8F Plan Full-stack",
                    base_url="https://api.tikhub.io",
                    secret_ref="stage8f-plan-provider-not-used",
                    enabled=True,
                )
    finally:
        session.close()
        runtime.close()


if __name__ == "__main__":
    main()
