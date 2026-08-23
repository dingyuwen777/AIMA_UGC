"""Internal V1 部署的一次性非敏感运行配置装配。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.contracts.collection.provider_config import normalize_provider_base_url
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.security import read_secret_file, validate_secret_ref

_INTERNAL_TIKHUB_PROVIDER_CONFIG_ID = uuid5(
    NAMESPACE_URL,
    "https://aima.internal/provider/tikhub",
)
_DEFAULT_TIKHUB_BASE_URL = "https://api.tikhub.io"
_DEFAULT_TIKHUB_SECRET_REF = "tikhub_api_key"


@dataclass(frozen=True, slots=True)
class InternalV1ProviderSettings:
    """生产部署中可写入 PostgreSQL 的 TikHub 非敏感配置。"""

    enabled: bool
    base_url: str
    secret_ref: str


def _parse_bool(value: str, *, key: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} 必须是 true/false、1/0、yes/no 或 on/off")


def _required_nonempty(value: str, *, key: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{key} 不能为空")
    return normalized


def load_internal_v1_provider_settings(
    environ: Mapping[str, str] | None = None,
) -> InternalV1ProviderSettings:
    """读取 Internal V1 TikHub 非敏感配置；默认禁用外部 Provider。"""

    source = os.environ if environ is None else environ
    enabled = _parse_bool(
        source.get("AIMA_TIKHUB_ENABLED", "false"),
        key="AIMA_TIKHUB_ENABLED",
    )
    base_url = normalize_provider_base_url(
        _required_nonempty(
            source.get("AIMA_TIKHUB_BASE_URL", _DEFAULT_TIKHUB_BASE_URL),
            key="AIMA_TIKHUB_BASE_URL",
        )
    )
    secret_ref = validate_secret_ref(
        _required_nonempty(
            source.get("AIMA_TIKHUB_SECRET_REF", _DEFAULT_TIKHUB_SECRET_REF),
            key="AIMA_TIKHUB_SECRET_REF",
        )
    )
    return InternalV1ProviderSettings(
        enabled=enabled,
        base_url=base_url,
        secret_ref=secret_ref,
    )


def validate_internal_v1_provider_secret(
    settings: PlatformSettings,
    provider: InternalV1ProviderSettings,
) -> None:
    """启用 TikHub 时必须能通过既有只读 Secret File 边界读取凭据。"""

    if not provider.enabled:
        return
    read_secret_file(
        settings.secret_dir / provider.secret_ref,
        root=settings.secret_dir,
    )


def validate_internal_v1_llm_settings(settings: PlatformSettings) -> bool:
    """校验生产 LLM 配置是否完整；完整时要求既有 API Key Secret 可读。"""

    supplied = (
        settings.llm_base_url is not None,
        settings.llm_provider_name is not None,
        settings.llm_model is not None,
    )
    if not any(supplied):
        return False
    if settings.llm_base_url is None or settings.llm_model is None:
        raise ValueError("LLM 启用时必须同时配置 AIMA_LLM_BASE_URL 与 AIMA_LLM_MODEL")
    read_secret_file(settings.llm_api_key_file, root=settings.secret_dir)
    return True


def internal_v1_tikhub_provider_config_id() -> UUID:
    """返回 Internal V1 TikHub Provider Config 的稳定 UUID。"""

    return _INTERNAL_TIKHUB_PROVIDER_CONFIG_ID


def provision_internal_v1_provider_config(
    session: Session,
    *,
    settings: PlatformSettings,
    provider: InternalV1ProviderSettings,
) -> ProviderConfig | None:
    """幂等维护 Internal V1 TikHub Provider Config；数据库永不保存 Secret 原值。"""

    validate_internal_v1_provider_secret(settings, provider)
    repository = PostgresProviderConfigRepository(session)
    config_id = internal_v1_tikhub_provider_config_id()
    current = repository.get(config_id)

    if current is None and not provider.enabled:
        return None
    if current is not None and current.provider != "tikhub":
        raise RuntimeError("Internal V1 稳定 Provider Config UUID 已被其他 Provider 占用")

    desired = ProviderConfig(
        id=config_id,
        provider="tikhub",
        display_name="TikHub Internal V1",
        base_url=provider.base_url,
        secret_ref=provider.secret_ref,
        enabled=provider.enabled,
    )
    if current is None:
        return repository.create(desired)
    if current == desired:
        return current
    return repository.update_settings(
        config_id,
        display_name=desired.display_name,
        base_url=desired.base_url,
        secret_ref=desired.secret_ref,
        enabled=desired.enabled,
    )


__all__ = [
    "InternalV1ProviderSettings",
    "internal_v1_tikhub_provider_config_id",
    "load_internal_v1_provider_settings",
    "provision_internal_v1_provider_config",
    "validate_internal_v1_llm_settings",
    "validate_internal_v1_provider_secret",
]
