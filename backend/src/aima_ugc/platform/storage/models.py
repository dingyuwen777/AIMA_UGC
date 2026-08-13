"""Artifact Platform 数据结构；数据库表由 Stage 3 Migration 落地。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

ArtifactStatus = Literal[
    "pending",
    "stored",
    "linked",
    "delete_pending",
    "deleted",
    "error",
]


@dataclass(frozen=True, slots=True)
class StoredBytes:
    """ArtifactStore 成功写入的完整性结果。"""

    sha256: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """ArtifactService 管理的元数据快照。"""

    id: UUID
    kind: str
    storage_backend: str
    storage_key: str
    content_type: str
    encoding: str | None
    retention_class: str
    storage_status: ArtifactStatus
    created_at: datetime
    sha256: str | None = None
    byte_size: int | None = None
    stored_at: datetime | None = None
    linked_at: datetime | None = None
