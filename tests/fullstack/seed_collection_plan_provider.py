"""为不调用外部 Provider 的 Collection Plan 全栈验收准备路由事实。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from uuid import UUID

from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.bootstrap.runtime import create_platform_runtime
from aima_ugc.modules.system.models import ProviderConfig

PROVIDER_CONFIG_ID = UUID("8f000000-0000-4000-8000-000000000001")


def _require_fullstack_seed_opt_in(environ: Mapping[str, str]) -> None:
    """只允许显式确认的隔离 Full-stack Runtime 写入固定测试配置。"""

    if environ.get("AIMA_FULLSTACK_SEED") != "1":
        raise RuntimeError(
            "拒绝写入 Provider Config：请仅在隔离测试数据库中设置 AIMA_FULLSTACK_SEED=1。"
        )


def main() -> None:
    """在已显式确认的隔离 Full-stack Runtime 中建立测试 Provider Config。"""

    _require_fullstack_seed_opt_in(os.environ)
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
