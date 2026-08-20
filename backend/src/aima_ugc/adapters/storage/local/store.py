"""路径安全、原子发布且不覆盖的本地 ArtifactStore。"""

from __future__ import annotations

import hashlib
import os
import re
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from aima_ugc.platform.storage import ArtifactSizeLimitError, StoredBytes

_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_STREAM_CHUNK_BYTES = 1024 * 1024


class LocalArtifactStore:
    """只按 storage_key 存取字节，不知道 Artifact UUID 或数据库。"""

    backend_name = "local"

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve(strict=False)

    @property
    def root(self) -> Path:
        return self._root

    def ensure_ready(self) -> None:
        """创建并验证根目录可写。"""
        self._root.mkdir(parents=True, exist_ok=True)
        probe = self._root / f".aima-write-probe-{uuid4().hex}"
        try:
            with probe.open("xb") as handle:
                handle.write(b"ok")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            probe.unlink(missing_ok=True)

    def _target(self, storage_key: str, *, create_parent: bool) -> Path:
        if not storage_key or "\x00" in storage_key or "\\" in storage_key:
            raise ValueError("storage_key 非法")
        segments = storage_key.split("/")
        if any(not segment or not _SEGMENT_PATTERN.fullmatch(segment) for segment in segments):
            raise ValueError("storage_key 必须由安全的相对路径段组成")

        candidate = self._root.joinpath(*segments)
        parent = candidate.parent
        if create_parent:
            parent.mkdir(parents=True, exist_ok=True)

        resolved_parent = parent.resolve(strict=False)
        try:
            resolved_parent.relative_to(self._root)
        except ValueError as exc:
            raise ValueError("storage_key 不能逃逸 Artifact 根目录") from exc

        target = resolved_parent / candidate.name
        if target.is_symlink():
            raise ValueError("Artifact 目标不能是符号链接")
        if target.exists():
            resolved_target = target.resolve(strict=True)
            try:
                resolved_target.relative_to(self._root)
            except ValueError as exc:
                raise ValueError("Artifact 目标不能逃逸根目录") from exc
        return target

    def put(self, storage_key: str, data: bytes) -> StoredBytes:
        return self.put_stream(storage_key, BytesIO(data), max_bytes=len(data))

    def put_stream(
        self,
        storage_key: str,
        source: BinaryIO,
        *,
        max_bytes: int,
    ) -> StoredBytes:
        target = self._target(storage_key, create_parent=True)
        if target.exists():
            raise FileExistsError(storage_key)
        if max_bytes < 0:
            raise ValueError("max_bytes 不能为负数")

        temp = target.parent / f".{target.name}.{uuid4().hex}.tmp"
        digest = hashlib.sha256()
        byte_size = 0
        try:
            with temp.open("xb") as handle:
                while chunk := source.read(_STREAM_CHUNK_BYTES):
                    byte_size += len(chunk)
                    if byte_size > max_bytes:
                        raise ArtifactSizeLimitError("Artifact 实际字节超过上限")
                    digest.update(chunk)
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            if os.name != "nt":
                temp.chmod(0o600)

            # hard link 的目标创建是原子 no-overwrite：若竞争者先占用同 key，
            # 操作会失败而不是像 os.replace 一样覆盖已存在 Artifact。
            try:
                os.link(temp, target)
            except FileExistsError as exc:
                raise FileExistsError(storage_key) from exc
        finally:
            temp.unlink(missing_ok=True)

        return StoredBytes(sha256=digest.hexdigest(), byte_size=byte_size)

    def read(self, storage_key: str) -> bytes:
        target = self._target(storage_key, create_parent=False)
        if not target.is_file():
            raise FileNotFoundError(storage_key)
        return target.read_bytes()

    def open_read(self, storage_key: str) -> BinaryIO:
        """打开经路径与符号链接校验的只读流；调用方负责关闭。"""
        target = self._target(storage_key, create_parent=False)
        if not target.is_file():
            raise FileNotFoundError(storage_key)
        return target.open("rb")

    def copy_to(self, storage_key: str, destination: BinaryIO) -> StoredBytes:
        target = self._target(storage_key, create_parent=False)
        if not target.is_file():
            raise FileNotFoundError(storage_key)
        digest = hashlib.sha256()
        byte_size = 0
        with target.open("rb") as source:
            while chunk := source.read(_STREAM_CHUNK_BYTES):
                digest.update(chunk)
                byte_size += len(chunk)
                destination.write(chunk)
        return StoredBytes(sha256=digest.hexdigest(), byte_size=byte_size)

    def exists(self, storage_key: str) -> bool:
        target = self._target(storage_key, create_parent=False)
        return target.is_file()
