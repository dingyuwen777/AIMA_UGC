"""Provider V1 公共类型、Secret 边界与 JSON 脱敏。"""

from __future__ import annotations

import re
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr

ProviderName = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
]
PlatformName = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
]
OperationName = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9_.-]*$"),
]
StableCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9_.-]*$"),
]
JsonObject = dict[str, JsonValue]

REDACTED = "[REDACTED]"

_SENSITIVE_NAMES = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "set_cookie",
    "token",
}
_SENSITIVE_SUFFIXES = (
    "_api_key",
    "_authorization",
    "_cookie",
    "_credential",
    "_password",
    "_secret",
    "_token",
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_INLINE_SECRET_PATTERN = re.compile(
    r"(?i)\b("
    r"[a-z0-9_-]*(?:api[_-]?key|authorization|cookie|credential|password|secret|token)"
    r")=([^&\s]+)"
)


class ProviderBaseModel(BaseModel):
    """拒绝额外字段并冻结 Provider/Raw 事实快照。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


def is_sensitive_key(key: str) -> bool:
    """识别不得进入 Provider Request 或 Raw 的常见 Secret 字段名。"""
    normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
    return normalized in _SENSITIVE_NAMES or normalized.endswith(_SENSITIVE_SUFFIXES)


def assert_secret_free(value: object, *, path: str = "request") -> None:
    """递归拒绝逻辑 Provider Request 中的 Secret 字段。"""
    if isinstance(value, dict):
        for key, nested in value.items():
            current = f"{path}.{key}"
            if is_sensitive_key(str(key)):
                raise ValueError(f"Provider Request 不能包含 Secret 字段: {current}")
            assert_secret_free(nested, path=current)
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            assert_secret_free(nested, path=f"{path}[{index}]")
    elif isinstance(value, SecretStr):
        raise ValueError(f"Provider Request 不能包含 Secret 值: {path}")


def _redact_text(value: str) -> str:
    redacted = _BEARER_PATTERN.sub(REDACTED, value)
    return _INLINE_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        redacted,
    )


def redact_json(value: Any) -> JsonValue:
    """递归脱敏 JSON 数据；未知对象拒绝进入 Raw。"""
    if isinstance(value, SecretStr):
        return REDACTED
    if isinstance(value, dict):
        return {
            str(key): REDACTED if is_sensitive_key(str(key)) else redact_json(nested)
            for key, nested in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_json(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise TypeError(f"Raw 只接受 JSON 值，收到 {type(value).__name__}")


def assert_redacted_json(value: object, *, path: str = "raw") -> None:
    """拒绝仍包含已知 Secret 字段或文本模式的 Raw 值。"""
    if redact_json(value) != value:
        raise ValueError(f"Raw 值必须先完成脱敏: {path}")
