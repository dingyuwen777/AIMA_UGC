"""Stage 8C Import Batch 列表的不透明签名 Cursor。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from aima_ugc.platform.time import beijing_now


class InvalidImportCursor(ValueError):
    """Cursor 非法、过期、被篡改或与当前查询不匹配。"""


@dataclass(frozen=True, slots=True)
class ImportBatchCursorPosition:
    created_at: datetime
    batch_id: UUID


class ImportBatchCursorCodec:
    """绑定查询条件并用 HMAC-SHA256 签名 Cursor。"""

    _VERSION = 1

    def __init__(
        self,
        *,
        secret: bytes,
        lifetime: timedelta = timedelta(minutes=30),
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if len(secret) < 32:
            raise ValueError("Cursor 签名 Secret 至少需要 32 字节")
        if lifetime <= timedelta(0):
            raise ValueError("Cursor 有效期必须为正数")
        self._secret = secret
        self._lifetime = lifetime
        self._now = now or (lambda: beijing_now())

    def encode(self, position: ImportBatchCursorPosition, *, query_hash: str) -> str:
        created_at = _aware_utc(position.created_at)
        expires_at = _aware_utc(self._now()) + self._lifetime
        payload = {
            "batch_id": str(position.batch_id),
            "created_at": created_at.isoformat(),
            "expires_at": int(expires_at.timestamp()),
            "query_hash": query_hash,
            "version": self._VERSION,
        }
        raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
        signature = hmac.new(self._secret, raw, hashlib.sha256).digest()
        return f"{_encode(raw)}.{_encode(signature)}"

    def decode(self, cursor: str, *, query_hash: str) -> ImportBatchCursorPosition:
        try:
            encoded_payload, encoded_signature = cursor.split(".", 1)
            raw = _decode(encoded_payload)
            signature = _decode(encoded_signature)
        except (ValueError, binascii.Error) as exc:
            raise InvalidImportCursor from exc
        expected = hmac.new(self._secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise InvalidImportCursor
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != {
                "batch_id",
                "created_at",
                "expires_at",
                "query_hash",
                "version",
            }:
                raise ValueError
            if payload["version"] != self._VERSION or payload["query_hash"] != query_hash:
                raise ValueError
            expires_at = int(payload["expires_at"])
            if int(_aware_utc(self._now()).timestamp()) >= expires_at:
                raise ValueError
            created_at = datetime.fromisoformat(str(payload["created_at"]))
            return ImportBatchCursorPosition(
                created_at=_aware_utc(created_at),
                batch_id=UUID(str(payload["batch_id"])),
            )
        except (TypeError, ValueError, OverflowError, json.JSONDecodeError) as exc:
            raise InvalidImportCursor from exc


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Cursor 时间必须包含时区")
    return value.astimezone(UTC)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    if not value:
        raise ValueError
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)


__all__ = [
    "ImportBatchCursorCodec",
    "ImportBatchCursorPosition",
    "InvalidImportCursor",
]
