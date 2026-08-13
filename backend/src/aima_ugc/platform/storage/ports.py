"""Artifact 可替换边界。"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from .models import ArtifactRecord, StoredBytes


class ArtifactStore(Protocol):
    """仅按 storage_key 存取字节；禁止反查数据库。"""

    @property
    def backend_name(self) -> str: ...

    def put(self, storage_key: str, data: bytes) -> StoredBytes: ...

    def read(self, storage_key: str) -> bytes: ...

    def exists(self, storage_key: str) -> bool: ...


class ArtifactMetadataPort(Protocol):
    """ArtifactService 的元数据持久化边界；Stage 3 再实现 PostgreSQL Repository。"""

    def create_pending(self, record: ArtifactRecord) -> None: ...

    def mark_stored(
        self,
        artifact_id: UUID,
        *,
        sha256: str,
        byte_size: int,
        stored_at: datetime,
    ) -> ArtifactRecord: ...

    def mark_linked(
        self,
        artifact_id: UUID,
        *,
        linked_at: datetime,
    ) -> ArtifactRecord: ...

    def mark_error(self, artifact_id: UUID) -> ArtifactRecord: ...
