"""Artifact 生命周期编排。"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID, uuid4

from .models import ArtifactRecord, StoredBytes
from .ports import ArtifactMetadataPort, ArtifactStore
from .retention import initial_artifact_expiry

_KIND_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SUFFIX_PATTERN = re.compile(r"^\.[a-z0-9]{1,16}$")


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
        storage_key: str | None = None,
    ) -> ArtifactRecord:
        """先登记 pending，再原子落字节并标记 stored。"""
        if not _KIND_PATTERN.fullmatch(kind):
            raise ValueError("Artifact kind 必须是安全的稳定标识")
        if not content_type:
            raise ValueError("Artifact content_type 不能为空")
        if not retention_class:
            raise ValueError("Artifact retention_class 不能为空")

        artifact_id = uuid4()
        if storage_key is None:
            resolved_storage_key = f"{kind}/{artifact_id}"
        elif not storage_key:
            raise ValueError("Artifact storage_key 不能为空")
        else:
            resolved_storage_key = storage_key
        created_at = datetime.now(UTC)
        pending = ArtifactRecord(
            id=artifact_id,
            kind=kind,
            storage_backend=self._store.backend_name,
            storage_key=resolved_storage_key,
            content_type=content_type,
            encoding=encoding,
            retention_class=retention_class,
            storage_status="pending",
            created_at=created_at,
            expires_at=initial_artifact_expiry(kind, created_at),
        )
        self._metadata.create_pending(pending)

        try:
            stored = self._store.put(resolved_storage_key, data)
        except Exception:
            try:
                self._metadata.mark_error(artifact_id)
            except Exception:
                pass
            raise

        return self._confirm_or_cleanup(
            artifact_id=artifact_id,
            storage_key=resolved_storage_key,
            stored=stored,
        )

    def store_stream(
        self,
        *,
        kind: str,
        content_type: str,
        retention_class: str,
        source: BinaryIO,
        max_bytes: int,
        filename_suffix: str = "",
        encoding: str | None = None,
    ) -> ArtifactRecord:
        """把有界输入流落入同一 Artifact 生命周期，不在内存聚合完整文件。"""

        if not _KIND_PATTERN.fullmatch(kind):
            raise ValueError("Artifact kind 必须是安全的稳定标识")
        if not content_type:
            raise ValueError("Artifact content_type 不能为空")
        if not retention_class:
            raise ValueError("Artifact retention_class 不能为空")
        if filename_suffix and not _SUFFIX_PATTERN.fullmatch(filename_suffix):
            raise ValueError("Artifact filename_suffix 必须是安全的小写扩展名")

        artifact_id = uuid4()
        storage_key = f"{kind}/{artifact_id}{filename_suffix}"
        created_at = datetime.now(UTC)
        pending = ArtifactRecord(
            id=artifact_id,
            kind=kind,
            storage_backend=self._store.backend_name,
            storage_key=storage_key,
            content_type=content_type,
            encoding=encoding,
            retention_class=retention_class,
            storage_status="pending",
            created_at=created_at,
            expires_at=initial_artifact_expiry(kind, created_at),
        )
        self._metadata.create_pending(pending)
        try:
            stored = self._store.put_stream(storage_key, source, max_bytes=max_bytes)
        except Exception:
            try:
                self._metadata.mark_error(artifact_id)
            except Exception:
                pass
            raise
        return self._confirm_or_cleanup(
            artifact_id=artifact_id,
            storage_key=storage_key,
            stored=stored,
        )

    def _confirm_or_cleanup(
        self,
        *,
        artifact_id: UUID,
        storage_key: str,
        stored: StoredBytes,
    ) -> ArtifactRecord:
        """仅在 CAS 证明元数据仍为 pending 时回收刚写入的孤儿字节。"""

        try:
            return self.confirm_stored_bytes(
                artifact_id,
                sha256=stored.sha256,
                byte_size=stored.byte_size,
                stored_at=datetime.now(UTC),
            )
        except Exception:
            # mark_stored 的异常可能发生在数据库已提交但客户端未收到确认之后。
            # 只有 mark_error 的 pending CAS 成功，才能证明 stored 未提交并安全删除字节。
            try:
                self._metadata.mark_error(artifact_id)
            except Exception:
                raise
            try:
                self._store.delete(storage_key)
            except Exception:
                # 保留最初的存储确认失败语义；error 元数据仍提供人工一致性排查入口。
                pass
            raise

    def confirm_stored_bytes(
        self,
        artifact_id: UUID,
        *,
        sha256: str,
        byte_size: int,
        stored_at: datetime,
    ) -> ArtifactRecord:
        """在调用方已验证实体字节后，以 CAS 将 pending 元数据提升为 stored。"""
        if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
            raise ValueError("Artifact sha256 必须是小写十六进制 SHA-256")
        if byte_size < 0:
            raise ValueError("Artifact byte_size 不能为负数")
        if stored_at.utcoffset() is None:
            raise ValueError("Artifact stored_at 必须包含时区")
        return self._metadata.mark_stored(
            artifact_id,
            sha256=sha256,
            byte_size=byte_size,
            stored_at=stored_at,
        )

    def link(self, artifact_id: UUID) -> ArtifactRecord:
        """在业务记录已经建立引用后，把 stored 元数据标记为 linked。"""
        return self._metadata.mark_linked(
            artifact_id,
            linked_at=datetime.now(UTC),
        )
