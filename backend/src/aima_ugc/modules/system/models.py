"""System 模块稳定业务对象。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import JsonValue

ActorKind = Literal["system", "principal"]


@dataclass(frozen=True, slots=True)
class SystemSetting:
    """非敏感、需要数据库事实源的系统设置。"""

    key: str
    value: JsonValue
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """与具体身份 Provider 解耦的审计事件。"""

    id: UUID
    actor_kind: ActorKind
    actor_ref: str | None
    event_type: str
    object_type: str | None
    object_id: str | None
    request_id: str | None
    safe_detail: dict[str, JsonValue]
    created_at: datetime
