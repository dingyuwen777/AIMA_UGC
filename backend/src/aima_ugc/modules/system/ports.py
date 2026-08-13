"""System 模块持久化边界。"""

from __future__ import annotations

from typing import Protocol

from pydantic import JsonValue

from .models import AuditEvent, SystemSetting


class SystemSettingsRepository(Protocol):
    """读写非敏感系统设置。"""

    def get(self, key: str) -> SystemSetting | None: ...

    def put(self, key: str, value: JsonValue) -> SystemSetting: ...


class AuditRepository(Protocol):
    """只追加 Provider 中立审计事件。"""

    def append(self, event: AuditEvent) -> None: ...
