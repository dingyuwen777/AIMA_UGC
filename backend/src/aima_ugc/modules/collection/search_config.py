"""Provider-neutral Search Config 默认值与 Capability 校验。"""

from __future__ import annotations

from collections.abc import Mapping

from aima_ugc.contracts.collection import ProviderPlatformCapabilityV1

_SEARCH_CONFIG_FIELDS = (
    ("sort_mode", "supported_sort_modes"),
    ("published_within", "supported_time_filters"),
    ("duration", "supported_duration_filters"),
    ("content_type", "supported_content_types"),
)


def search_config_choices(
    capability: ProviderPlatformCapabilityV1,
) -> dict[str, tuple[str, ...]]:
    """返回公共 Search Config 字段及其当前合法值，不暴露 Provider 私有参数。"""

    search = capability.operation("keyword_search")
    if search is None:
        raise ValueError(f"Provider/Platform 缺少 keyword_search: {capability.platform}")
    return {
        field: tuple(getattr(search, capability_field))
        for field, capability_field in _SEARCH_CONFIG_FIELDS
    }


def normalize_search_config(
    capability: ProviderPlatformCapabilityV1,
    config: Mapping[str, object],
    *,
    require_complete: bool = False,
) -> dict[str, str]:
    """按 Capability 校验并规范化配置；旧 Plan 可在非完整模式保留空配置。"""

    choices = search_config_choices(capability)
    unknown = set(config) - set(choices)
    if unknown:
        raise ValueError(f"平台搜索配置包含未声明字段: {', '.join(sorted(unknown))}")

    normalized: dict[str, str] = {}
    for field, supported in choices.items():
        if field not in config:
            continue
        raw = config[field]
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"平台搜索配置 {field} 必须是非空字符串")
        value = raw.strip()
        if not supported or value not in supported:
            raise ValueError(f"平台搜索配置 {field}={value} 不受当前 Capability 支持")
        normalized[field] = value

    if require_complete:
        required = {field for field, supported in choices.items() if supported}
        missing = required - set(normalized)
        if missing:
            raise ValueError(f"平台搜索配置缺少显式字段: {', '.join(sorted(missing))}")
    return normalized


def manual_discovery_search_config(
    capability: ProviderPlatformCapabilityV1,
) -> dict[str, str]:
    """生成“最新、一天内、全部内容”的平台合法手工发现默认值。"""

    choices = search_config_choices(capability)
    config: dict[str, str] = {}
    preferences = {
        "sort_mode": ("latest",),
        "published_within": ("1d", "day"),
        "duration": ("all",),
        "content_type": ("all",),
    }
    for field, supported in choices.items():
        if not supported:
            continue
        preferred = next(
            (value for value in preferences[field] if value in supported),
            supported[0],
        )
        config[field] = preferred
    return normalize_search_config(capability, config, require_complete=True)


__all__ = [
    "manual_discovery_search_config",
    "normalize_search_config",
    "search_config_choices",
]
