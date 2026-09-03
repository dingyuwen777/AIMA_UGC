"""运行时 Provider 配置解析；数据库优先，进程设置只作未迁移兼容兜底。"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from pydantic import JsonValue, SecretStr
from sqlalchemy.orm import Session

from aima_ugc.adapters.llm import resolve_openai_compatible_provider_name
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.modules.system.models import ProviderConfig, ProviderKind
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.security import read_secret_ref

_LEGACY_LLM_CONFIG_ID = UUID("00000000-0000-4000-8000-000000000001")


def active_llm_provider(session: Session, settings: PlatformSettings) -> ProviderConfig | None:
    """每次创建新 Analysis Run 都重读数据库；仅在 DB 尚无 LLM 配置时使用 env 兜底。"""

    repository = PostgresProviderConfigRepository(session)
    configured = repository.get_default("llm")
    if configured is not None:
        return configured
    # 一旦管理员写入过任意 LLM Provider，数据库就是唯一运行时事实源。
    # 禁用或未指定默认项必须表现为“未配置”，不能悄悄回退到旧 env。
    if repository.list_all(provider_kind="llm"):
        return None
    if settings.llm_base_url is None or settings.llm_model is None:
        return None
    try:
        secret_ref = (
            settings.llm_api_key_file.resolve()
            .relative_to(settings.external_secret_root.resolve())
            .as_posix()
        )
    except OSError, ValueError:
        return None
    return ProviderConfig(
        id=_LEGACY_LLM_CONFIG_ID,
        provider=resolve_openai_compatible_provider_name(
            settings.llm_base_url,
            provider_name=settings.llm_provider_name,
        ),
        provider_kind="llm",
        display_name="Legacy bootstrap LLM",
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        secret_ref=secret_ref,
        timeout_seconds=max(1, int(settings.llm_timeout_seconds)),
        max_retries=max(0, int(settings.llm_validation_retries)),
        max_concurrency=max(1, int(settings.llm_max_connections)),
        is_default=True,
        revision=1,
        enabled=True,
    )


def provider_from_safe_snapshot(payload: object) -> ProviderConfig:
    """从持久化 Run Snapshot 恢复 Provider；Snapshot 不包含 Secret 值。"""

    if not isinstance(payload, dict):
        raise ValueError("Runtime Provider Snapshot 必须为对象")
    data = cast(dict[str, object], payload)
    provider_config_id = data.get("provider_config_id")
    if not isinstance(provider_config_id, str):
        raise ValueError("Runtime Provider Snapshot 缺少 provider_config_id")
    extra_config = data.get("extra_config", {})
    if not isinstance(extra_config, dict):
        raise ValueError("Runtime Provider Snapshot extra_config 必须为对象")
    provider_kind = cast(ProviderKind, _required_str(data, "provider_kind"))
    return ProviderConfig(
        id=UUID(provider_config_id),
        provider=_required_str(data, "provider"),
        provider_kind=provider_kind,
        display_name=f"run-snapshot:{provider_config_id}",
        base_url=_required_str(data, "base_url"),
        model=_optional_str(data, "model"),
        secret_ref=_required_str(data, "secret_ref"),
        timeout_seconds=_required_int(data, "timeout_seconds"),
        max_retries=_required_int(data, "max_retries", minimum=0),
        max_concurrency=_required_int(data, "max_concurrency"),
        max_rps=(_required_int(data, "max_rps") if data.get("max_rps") is not None else None),
        extra_config=cast(dict[str, JsonValue], extra_config),
        is_default=True,
        revision=_required_int(data, "revision"),
        enabled=True,
    )


def resolve_provider_secret(settings: PlatformSettings, config: ProviderConfig) -> SecretStr:
    """按快照中的不可变 `secret_ref` 解析凭据。"""

    return read_secret_ref(settings.external_secret_root, config.secret_ref)


def new_secret_ref(config_id: UUID, revision_token: str) -> str:
    """生成不可变 Secret 文件引用；token 必须由服务端生成。"""

    return f"providers/{config_id}/{revision_token}.key"


def _optional_str(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) else None


def _required_str(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Runtime Provider Snapshot 缺少 {key}")
    return value


def _required_int(data: dict[str, object], key: str, *, minimum: int = 1) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"Runtime Provider Snapshot {key} 不合法")
    return value


__all__ = [
    "active_llm_provider",
    "new_secret_ref",
    "provider_from_safe_snapshot",
    "resolve_provider_secret",
]
