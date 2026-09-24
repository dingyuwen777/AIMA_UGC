"""持久 CanonicalContentV1 的可复现 JSONL.gz Artifact 边界。"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryFile
from typing import BinaryIO, cast

from pydantic import ValidationError

from aima_ugc.contracts.canonical import CanonicalContentV1

from .models import (
    ArtifactRecord,
    ArtifactSizeLimitError,
    CanonicalArtifactParent,
)
from .ports import ArtifactStore
from .service import ArtifactService

CANONICAL_CONTENT_ARTIFACT_KIND = "canonical-content.v1"
CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE = "application/x-ndjson"
_CANONICAL_CONTENT_ARTIFACT_ENCODING = "gzip"
_CANONICAL_CONTENT_ARTIFACT_SUFFIX = ".jsonl.gz"


class CanonicalArtifactIntegrityError(RuntimeError):
    """Canonical Artifact 元数据、压缩字节或逐行 Contract 不可信。"""


class CanonicalArtifactWriter:
    """用磁盘临时流生成可复现 JSONL.gz，并交给正式 Artifact 生命周期。"""

    def __init__(
        self,
        *,
        artifacts: ArtifactService,
        temporary_directory: Path | None = None,
    ) -> None:
        self._artifacts = artifacts
        self._temporary_directory = temporary_directory

    def write(
        self,
        contents: Iterable[CanonicalContentV1],
        *,
        parent: CanonicalArtifactParent,
        retention_class: str,
        max_bytes: int,
    ) -> ArtifactRecord:
        """逐条压缩合法 Canonical，存储后原子绑定父级与 linked 状态。"""

        if max_bytes < 0:
            raise ValueError("max_bytes 不能为负数")
        with TemporaryFile(mode="w+b", dir=self._temporary_directory) as temporary:
            stream = cast(BinaryIO, temporary)
            self._write_compressed(contents, temporary=stream, max_bytes=max_bytes)
            stream.seek(0)
            artifact = self._artifacts.store_stream(
                kind=CANONICAL_CONTENT_ARTIFACT_KIND,
                content_type=CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE,
                retention_class=retention_class,
                source=stream,
                max_bytes=max_bytes,
                filename_suffix=_CANONICAL_CONTENT_ARTIFACT_SUFFIX,
                encoding=_CANONICAL_CONTENT_ARTIFACT_ENCODING,
            )
        return self._artifacts.link_canonical(artifact.id, parent=parent)

    @staticmethod
    def _write_compressed(
        contents: Iterable[CanonicalContentV1],
        *,
        temporary: BinaryIO,
        max_bytes: int,
    ) -> None:
        """保持 O(单条 Canonical) 内存，并在压缩输出增长时尽早拒绝。"""

        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=temporary,
            mtime=0,
        ) as compressed:
            for content in contents:
                if not isinstance(content, CanonicalContentV1):
                    raise TypeError("Canonical Artifact Writer 只接受 CanonicalContentV1")
                payload = json.dumps(
                    content.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
                compressed.write(payload)
                compressed.write(b"\n")
                if temporary.tell() > max_bytes:
                    raise ArtifactSizeLimitError("Canonical Artifact 压缩字节超过上限")
        if temporary.tell() > max_bytes:
            raise ArtifactSizeLimitError("Canonical Artifact 压缩字节超过上限")


class CanonicalArtifactReader:
    """从 ArtifactStore 读取已绑定 Canonical，并在首条输出前完成全文件预检。"""

    def __init__(self, *, store: ArtifactStore) -> None:
        self._store = store
        self._preflighted: set[tuple[object, ...]] = set()

    def read(self, artifact: ArtifactRecord) -> Iterator[CanonicalContentV1]:
        """校验同一磁盘临时副本两遍，避免失败 Artifact 产生部分输出。"""

        with self._verified_temporary(artifact) as stream:
            # 普通消费者的首条输出仍以全文件 Contract 校验完成为前提。
            for _ in self._read_validated_lines(stream):
                pass
            stream.seek(0)
            yield from self._read_validated_lines(stream)

    def read_for_preflight(self, artifact: ArtifactRecord) -> Iterator[CanonicalContentV1]:
        """Replay 只读预检单遍解析；完整耗尽后才授予当前 Reader 复用资格。"""

        with self._verified_temporary(artifact) as stream:
            yield from self._read_validated_lines(stream)
        self._preflighted.add(self._preflight_key(artifact))

    def read_for_bounded_staging(self, artifact: ArtifactRecord) -> Iterator[CanonicalContentV1]:
        """供事务外完整装入有界 Chunk 的调用方单遍校验，不缓存预检资格。"""

        with self._verified_temporary(artifact) as stream:
            yield from self._read_validated_lines(stream)

    def verify_bytes_for_preflight(self, artifact: ArtifactRecord) -> None:
        """已有同版本验证证明时仍逐字节核对当前文件，避免只信数据库摘要。"""

        with self._verified_temporary(artifact):
            pass
        self._preflighted.add(self._preflight_key(artifact))

    def read_preflighted(self, artifact: ArtifactRecord) -> Iterator[CanonicalContentV1]:
        """仅对同一 Reader 已完整预检的 Artifact 单遍读取，并重新核对字节摘要。"""

        if self._preflight_key(artifact) not in self._preflighted:
            raise CanonicalArtifactIntegrityError("Canonical Artifact 尚未完成当前 Replay 预检")
        with self._verified_temporary(artifact) as stream:
            yield from self._read_validated_lines(stream)

    @staticmethod
    def _preflight_key(artifact: ArtifactRecord) -> tuple[object, ...]:
        """把复用资格绑定到 Artifact 身份、位置与压缩字节元数据。"""

        return (
            artifact.id,
            artifact.storage_backend,
            artifact.storage_key,
            artifact.sha256,
            artifact.byte_size,
        )

    @contextmanager
    def _verified_temporary(self, artifact: ArtifactRecord) -> Iterator[BinaryIO]:
        """每次打开仍复制并校验压缩字节，防止预检后文件被替换。"""

        self._validate_metadata(artifact)
        with TemporaryFile(mode="w+b") as temporary:
            stream = cast(BinaryIO, temporary)
            try:
                actual = self._store.copy_to(artifact.storage_key, stream)
            except FileNotFoundError as exc:
                raise CanonicalArtifactIntegrityError("Canonical Artifact 文件不存在") from exc
            except (OSError, ValueError) as exc:
                raise CanonicalArtifactIntegrityError(
                    "Canonical Artifact 文件无法安全读取"
                ) from exc
            if actual.sha256 != artifact.sha256:
                raise CanonicalArtifactIntegrityError("Canonical Artifact SHA-256 校验失败")
            if actual.byte_size != artifact.byte_size:
                raise CanonicalArtifactIntegrityError("Canonical Artifact 字节大小校验失败")
            stream.seek(0)
            yield stream

    def _validate_metadata(self, artifact: ArtifactRecord) -> None:
        """拒绝未绑定、格式不符或属于其他 Store 的 Artifact 元数据。"""

        if (
            artifact.kind != CANONICAL_CONTENT_ARTIFACT_KIND
            or artifact.content_type != CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE
            or artifact.encoding != _CANONICAL_CONTENT_ARTIFACT_ENCODING
            or not artifact.storage_key.endswith(_CANONICAL_CONTENT_ARTIFACT_SUFFIX)
        ):
            raise CanonicalArtifactIntegrityError("Artifact 不是当前 Canonical JSONL.gz")
        if artifact.storage_backend != self._store.backend_name:
            raise CanonicalArtifactIntegrityError("Canonical Artifact Store 与元数据不一致")
        if artifact.storage_status != "linked":
            raise CanonicalArtifactIntegrityError("Canonical Artifact 尚未完成父级绑定")
        if artifact.sha256 is None or artifact.byte_size is None:
            raise CanonicalArtifactIntegrityError("Canonical Artifact 缺少完整性元数据")

    @staticmethod
    def _read_validated_lines(source: BinaryIO) -> Iterator[CanonicalContentV1]:
        """逐行验证当前 Canonical Contract，并把错误定位到安全的行号。"""

        try:
            with gzip.GzipFile(fileobj=source, mode="rb") as compressed:
                for line_number, raw_line in enumerate(compressed, start=1):
                    try:
                        yield CanonicalContentV1.model_validate_json(raw_line)
                    except ValidationError as exc:
                        error_types = {str(item.get("type")) for item in exc.errors()}
                        category = "JSON" if "json_invalid" in error_types else "Contract"
                        raise CanonicalArtifactIntegrityError(
                            f"Canonical Artifact 第 {line_number} 行 {category} 校验失败"
                        ) from exc
        except CanonicalArtifactIntegrityError:
            raise
        except (EOFError, OSError) as exc:
            raise CanonicalArtifactIntegrityError("Canonical Artifact gzip 校验失败") from exc


__all__ = [
    "CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE",
    "CANONICAL_CONTENT_ARTIFACT_KIND",
    "CanonicalArtifactIntegrityError",
    "CanonicalArtifactParent",
    "CanonicalArtifactReader",
    "CanonicalArtifactWriter",
]
