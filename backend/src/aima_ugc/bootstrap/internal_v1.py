"""Internal V1 部署的一次性非敏感运行配置装配。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.contracts.collection.provider_config import normalize_provider_base_url
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.security import (
    read_secret_file,
    read_secret_ref,
    validate_secret_ref,
    write_secret_ref,
)

_INTERNAL_TIKHUB_PROVIDER_CONFIG_ID = uuid5(
    NAMESPACE_URL,
    "https://aima.internal/provider/tikhub",
)
_DEFAULT_TIKHUB_BASE_URL = "https://api.tikhub.io"
_DEFAULT_TIKHUB_SECRET_REF = "tikhub_api_key"
_DEFAULT_BOOTSTRAP_SECRET_DIR = Path("/run/secrets")


@dataclass(frozen=True, slots=True)
class InternalV1ProviderSettings:
    """生产部署中可写入 PostgreSQL 的 TikHub 非敏感配置。"""

    enabled: bool
    base_url: str
    secret_ref: str


def _parse_bool(value: str, *, key: str) -> bool:
    """解析部署布尔值。"""

    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} 必须是 true/false、1/0、yes/no 或 on/off")


def _required_nonempty(value: str, *, key: str) -> str:
    """清洗并校验部署必填文本。"""

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


def bootstrap_internal_v1_external_secrets(
    settings: PlatformSettings,
    provider: InternalV1ProviderSettings,
    *,
    bootstrap_secret_dir: Path | None = None,
    bootstrap_tikhub: bool = True,
    bootstrap_llm: bool = True,
) -> None:
    """只在数据库尚未接管对应 Provider 时复制部署 Secret。"""

    needs_tikhub = bootstrap_tikhub and provider.enabled
    needs_llm = bootstrap_llm and any(
        value is not None
        for value in (
            settings.llm_base_url,
            settings.llm_provider_name,
            settings.llm_model,
        )
    )
    if not needs_tikhub and not needs_llm:
        return

    try:
        source_root = (bootstrap_secret_dir or _DEFAULT_BOOTSTRAP_SECRET_DIR).resolve(strict=True)
    except OSError as exc:
        raise ValueError("Bootstrap Secret 目录不可访问") from exc
    if needs_tikhub:
        _copy_bootstrap_secret_once(
            settings,
            source_root=source_root,
            source_name="tikhub_api_key",
            target_ref=provider.secret_ref,
        )
    if needs_llm:
        _copy_bootstrap_secret_once(
            settings,
            source_root=source_root,
            source_name="llm_api_key",
            target_ref="llm_api_key",
        )


def _copy_bootstrap_secret_once(
    settings: PlatformSettings,
    *,
    source_root: Path,
    source_name: str,
    target_ref: str,
) -> None:
    """已有持久化 Secret 只校验不覆盖，避免重启把管理员轮换结果改回环境值。"""

    target = settings.external_secret_root / target_ref
    if target.exists() or target.is_symlink():
        read_secret_ref(settings.external_secret_root, target_ref)
        return
    source = read_secret_file(source_root / source_name, root=source_root)
    write_secret_ref(settings.external_secret_root, target_ref, source)


def validate_internal_v1_provider_secret(
    settings: PlatformSettings,
    provider: InternalV1ProviderSettings,
) -> None:
    """启用 TikHub 时必须能通过既有只读外部 Secret File 边界读取凭据。"""

    if not provider.enabled:
        return
    secret_root = settings.external_secret_root
    read_secret_file(
        secret_root / provider.secret_ref,
        root=secret_root,
    )


def validate_internal_v1_llm_settings(settings: PlatformSettings) -> bool:
    """仅在 DB 尚未接管 LLM 时校验旧启动配置及其 Secret。"""

    supplied = (
        settings.llm_base_url is not None,
        settings.llm_provider_name is not None,
        settings.llm_model is not None,
    )
    if not any(supplied):
        return False
    if settings.llm_base_url is None or settings.llm_model is None:
        raise ValueError("LLM 启用时必须同时配置 AIMA_LLM_BASE_URL 与 AIMA_LLM_MODEL")
    read_secret_file(settings.llm_api_key_file, root=settings.external_secret_root)
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
    """只首次创建 TikHub Provider；已有 DB 记录以后完全由管理员控制面维护。"""

    repository = PostgresProviderConfigRepository(session)
    config_id = internal_v1_tikhub_provider_config_id()
    current = repository.get(config_id)
    if current is not None:
        if current.provider != "tikhub":
            raise RuntimeError("Internal V1 稳定 Provider Config UUID 已被其他 Provider 占用")
        return current
    if not provider.enabled:
        return None

    validate_internal_v1_provider_secret(settings, provider)
    desired = ProviderConfig(
        id=config_id,
        provider="tikhub",
        display_name="TikHub Internal V1",
        base_url=provider.base_url,
        secret_ref=provider.secret_ref,
        enabled=provider.enabled,
    )
    return repository.create(desired)


__all__ = [
    "InternalV1ProviderSettings",
    "bootstrap_internal_v1_external_secrets",
    "internal_v1_tikhub_provider_config_id",
    "load_internal_v1_provider_settings",
    "provision_internal_v1_provider_config",
    "validate_internal_v1_llm_settings",
    "validate_internal_v1_provider_secret",
]
