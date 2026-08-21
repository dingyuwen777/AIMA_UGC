"""Stage 8E 统一运行列表的不透明签名 Cursor。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

type RuntimeRecordType = Literal[
    "excel_import",
    "tikhub_discovery",
    "tikhub_batch_supplement",
]


class InvalidCollectionRuntimeCursor(ValueError):
    """Cursor 非法、过期、被篡改或与当前查询不匹配。"""


@dataclass(frozen=True, slots=True)
class CollectionRuntimeCursorPosition:
    created_at: datetime
    record_id: UUID
    record_type: RuntimeRecordType


class CollectionRuntimeCursorCodec:
    """绑定查询条件并用 HMAC-SHA256 签名统一运行列表 Cursor。"""

    _VERSION = 1
    _RECORD_TYPES = frozenset({"excel_import", "tikhub_discovery", "tikhub_batch_supplement"})

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
        self._now = now or (lambda: datetime.now(UTC))

    def encode(self, position: CollectionRuntimeCursorPosition, *, query_hash: str) -> str:
        created_at = _aware_utc(position.created_at)
        expires_at = _aware_utc(self._now()) + self._lifetime
        payload = {
            "created_at": created_at.isoformat(),
            "expires_at": int(expires_at.timestamp()),
            "query_hash": query_hash,
            "record_id": str(position.record_id),
            "record_type": position.record_type,
            "version": self._VERSION,
        }
        raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
        signature = hmac.new(self._secret, raw, hashlib.sha256).digest()
        return f"{_encode(raw)}.{_encode(signature)}"

    def decode(self, cursor: str, *, query_hash: str) -> CollectionRuntimeCursorPosition:
        try:
            encoded_payload, encoded_signature = cursor.split(".", 1)
            raw = _decode(encoded_payload)
            signature = _decode(encoded_signature)
        except (ValueError, binascii.Error) as exc:
            raise InvalidCollectionRuntimeCursor from exc
        expected = hmac.new(self._secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise InvalidCollectionRuntimeCursor
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != {
                "created_at",
                "expires_at",
                "query_hash",
                "record_id",
                "record_type",
                "version",
            }:
                raise ValueError
            record_type = str(payload["record_type"])
            if (
                payload["version"] != self._VERSION
                or payload["query_hash"] != query_hash
                or record_type not in self._RECORD_TYPES
                or int(_aware_utc(self._now()).timestamp()) >= int(payload["expires_at"])
            ):
                raise ValueError
            return CollectionRuntimeCursorPosition(
                created_at=_aware_utc(datetime.fromisoformat(str(payload["created_at"]))),
                record_id=UUID(str(payload["record_id"])),
                record_type=cast(RuntimeRecordType, record_type),
            )
        except (TypeError, ValueError, OverflowError, json.JSONDecodeError) as exc:
            raise InvalidCollectionRuntimeCursor from exc


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
    "CollectionRuntimeCursorCodec",
    "CollectionRuntimeCursorPosition",
    "InvalidCollectionRuntimeCursor",
    "RuntimeRecordType",
]
