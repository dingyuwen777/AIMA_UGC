"""Artifact Platform 数据结构。"""

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


class ArtifactStateConflict(RuntimeError):
    """Artifact 当前状态不允许请求的状态转换。"""


class ArtifactSizeLimitError(ValueError):
    """Artifact 实际流式字节超过调用方批准上限。"""


@dataclass(frozen=True, slots=True)
class CanonicalArtifactParent:
    """Canonical Artifact 可绑定的一个真实 Import 或 Collection 父级。"""

    processing_import_batch_id: UUID | None = None
    historical_import_campaign_item_id: UUID | None = None
    collection_scope_id: UUID | None = None
    provider_attempt_id: UUID | None = None

    def __post_init__(self) -> None:
        """在进入持久化前拒绝缺失或含糊的父级身份。"""

        parent_count = sum(
            value is not None
            for value in (
                self.processing_import_batch_id,
                self.historical_import_campaign_item_id,
                self.collection_scope_id,
                self.provider_attempt_id,
            )
        )
        if parent_count != 1:
            raise ValueError("Canonical Artifact 必须恰好一个真实父级")


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
    expires_at: datetime | None = None
    deleted_at: datetime | None = None
