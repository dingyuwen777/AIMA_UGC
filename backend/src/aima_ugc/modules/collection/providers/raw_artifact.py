"""Provider Raw Envelope 的 Artifact 写入与回放。"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from aima_ugc.contracts.provider import (
    ProviderAttemptV1,
    ProviderRequestV1,
    RawEnvelopeV1,
    terminal_attempt_with_raw,
)
from aima_ugc.platform.storage import ArtifactRecord, ArtifactService, ArtifactStore

from .transport import ProviderDispatchResult

_BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


class RawArtifactIntegrityError(RuntimeError):
    """Raw Artifact 字节完整性或 Envelope Contract 校验失败。"""


@dataclass(frozen=True, slots=True)
class CapturedRawArtifact:
    """Raw 已落盘后可供后续 Attempt Repository 关联的结果。"""

    artifact: ArtifactRecord
    attempt: ProviderAttemptV1
    envelope: RawEnvelopeV1


class RawArtifactService:
    """复用 ArtifactService 保存不可覆盖 Raw，并在回放时重新校验。"""

    def __init__(self, *, artifacts: ArtifactService, store: ArtifactStore) -> None:
        self._artifacts = artifacts
        self._store = store

    def capture(
        self,
        *,
        request: ProviderRequestV1,
        dispatch: ProviderDispatchResult,
    ) -> CapturedRawArtifact:
        """把 completed/unknown Attempt 的脱敏证据保存为 gzip JSON。"""
        attempt = dispatch.attempt
        if dispatch.request != request or attempt.provider_request_id != request.request_id:
            raise ValueError("Raw Request、Dispatch 与 Attempt 来源不一致")
        if attempt.dispatch_status not in {"completed", "unknown"}:
            raise ValueError("只有 completed/unknown Attempt 可以保存 Raw")
        if attempt.dispatch_started_at is None or attempt.completed_at is None:
            raise ValueError("Raw Attempt 缺少发送或完成时间")

        envelope = RawEnvelopeV1(
            provider=request.provider,
            platform=request.platform,
            operation=request.operation,
            request_id=request.request_id,
            attempt_id=attempt.attempt_id,
            run_id=request.run_id,
            scope_id=request.scope_id,
            requested_at=attempt.dispatch_started_at,
            completed_at=attempt.completed_at,
            dispatch_status=attempt.dispatch_status,
            request=dispatch.raw_request,
            response=dispatch.raw_response,
            billing=attempt.billing,
            error=attempt.error,
        )
        plain = (
            json.dumps(
                envelope.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        compressed = gzip.compress(plain, compresslevel=9, mtime=0)
        if gzip.decompress(compressed) != plain:
            raise RawArtifactIntegrityError("Raw gzip 写入前校验失败")

        local_date = attempt.dispatch_started_at.astimezone(_BUSINESS_TIMEZONE)
        storage_key = (
            f"raw/{request.provider}/{request.platform}/"
            f"{local_date:%Y/%m/%d}/{request.run_id}/{request.scope_id}/"
            f"{attempt.attempt_id}.json.gz"
        )
        artifact = self._artifacts.store_bytes(
            kind="provider-raw",
            content_type="application/json",
            retention_class="raw",
            data=compressed,
            encoding="gzip",
            storage_key=storage_key,
        )
        linked_attempt = terminal_attempt_with_raw(attempt, artifact.id)
        return CapturedRawArtifact(
            artifact=artifact,
            attempt=linked_attempt,
            envelope=envelope,
        )

    def replay(self, artifact: ArtifactRecord) -> RawEnvelopeV1:
        """按 Artifact 元数据验证 Hash/大小/gzip/Contract 后返回 Raw Envelope。"""
        if artifact.kind != "provider-raw" or artifact.encoding != "gzip":
            raise RawArtifactIntegrityError("Artifact 不是 Provider Raw gzip")
        if artifact.storage_status not in {"stored", "linked"}:
            raise RawArtifactIntegrityError("Artifact 尚未完整存储")
        if artifact.sha256 is None or artifact.byte_size is None:
            raise RawArtifactIntegrityError("Artifact 缺少完整性元数据")

        compressed = self._store.read(artifact.storage_key)
        actual_sha256 = hashlib.sha256(compressed).hexdigest()
        if actual_sha256 != artifact.sha256:
            raise RawArtifactIntegrityError("Raw SHA-256 校验失败")
        if len(compressed) != artifact.byte_size:
            raise RawArtifactIntegrityError("Raw 字节大小校验失败")
        try:
            plain = gzip.decompress(compressed)
        except (EOFError, OSError) as exc:
            raise RawArtifactIntegrityError("Raw gzip 无法读取") from exc
        try:
            return RawEnvelopeV1.model_validate_json(plain)
        except ValidationError as exc:
            raise RawArtifactIntegrityError("Raw Envelope Contract 校验失败") from exc
