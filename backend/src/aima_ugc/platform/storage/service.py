"""Artifact 生命周期编排。"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .models import ArtifactRecord
from .ports import ArtifactMetadataPort, ArtifactStore

_KIND_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class ArtifactService:
    """管理 Artifact ID/元数据/生命周期，Store 只处理字节。"""

    def __init__(
        self,
        *,
        metadata: ArtifactMetadataPort,
        store: ArtifactStore,
    ) -> None:
        self._metadata = metadata
        self._store = store

    def store_bytes(
        self,
        *,
        kind: str,
        content_type: str,
        retention_class: str,
        data: bytes,
        encoding: str | None = None,
    ) -> ArtifactRecord:
        """先登记 pending，再原子落字节并标记 stored。"""
        if not _KIND_PATTERN.fullmatch(kind):
            raise ValueError("Artifact kind 必须是安全的稳定标识")
        if not content_type:
            raise ValueError("Artifact content_type 不能为空")
        if not retention_class:
            raise ValueError("Artifact retention_class 不能为空")

        artifact_id = uuid4()
        storage_key = f"{kind}/{artifact_id}"
        pending = ArtifactRecord(
            id=artifact_id,
            kind=kind,
            storage_backend=self._store.backend_name,
            storage_key=storage_key,
            content_type=content_type,
            encoding=encoding,
            retention_class=retention_class,
            storage_status="pending",
            created_at=datetime.now(UTC),
        )
        self._metadata.create_pending(pending)

        try:
            stored = self._store.put(storage_key, data)
        except Exception:
            try:
                self._metadata.mark_error(artifact_id)
            except Exception:
                pass
            raise

        return self._metadata.mark_stored(
            artifact_id,
            sha256=stored.sha256,
            byte_size=stored.byte_size,
            stored_at=datetime.now(UTC),
        )

    def link(self, artifact_id: UUID) -> ArtifactRecord:
        """在业务记录已经建立引用后，把 stored 元数据标记为 linked。"""
        return self._metadata.mark_linked(
            artifact_id,
            linked_at=datetime.now(UTC),
        )
