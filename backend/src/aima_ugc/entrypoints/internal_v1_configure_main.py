"""Internal V1 新环境的一次性非敏感配置入口。"""

from __future__ import annotations

from aima_ugc.bootstrap.internal_v1 import (
    bootstrap_internal_v1_external_secrets,
    load_internal_v1_provider_settings,
    provision_internal_v1_provider_config,
    validate_internal_v1_llm_settings,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime


def main() -> int:
    """幂等写入生产 Provider Config，并只输出安全能力摘要。"""

    settings = load_settings()
    provider = load_internal_v1_provider_settings()
    bootstrap_internal_v1_external_secrets(settings, provider)
    llm_configured = validate_internal_v1_llm_settings(settings)
    runtime = DatabaseRuntime(settings)
    try:
        session = runtime.new_session()
        try:
            with session.begin():
                provision_internal_v1_provider_config(
                    session,
                    settings=settings,
                    provider=provider,
                )
        finally:
            session.close()
    finally:
        runtime.dispose()

    print(f"TikHub Internal V1: {'ENABLED' if provider.enabled else 'DISABLED'}")
    print(f"LLM Runtime: {'CONFIGURED' if llm_configured else 'DISABLED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
