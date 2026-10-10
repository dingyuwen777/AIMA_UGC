"""Content Owner 的播放身份、URL 来源代次和短期会话规则。"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from .content_cursor import ContentCursorCodec, ContentCursorPosition, InvalidContentCursor
from .media_observations import media_identity_token

REFRESHABLE_STREAM_FAILURES = frozenset(
    {
        "cdn_forbidden",
        "cdn_not_found",
        "cdn_gone",
        "cdn_timeout",
        "cdn_network_error",
        "cdn_unavailable",
    }
)


def media_source_revision(row: Mapping[str, Any]) -> str:
    """URL 值与其真实属性来源共同参与 CAS；更新封面不会误使流失效。"""
    metadata = row.get("observation_metadata") or {}
    marker = metadata.get("fields", {}).get("url") if isinstance(metadata, dict) else None
    if not isinstance(marker, dict):
        marker = {
            key: row.get(key) for key in ("provider_attempt_id", "raw_artifact_id", "observed_at")
        }
    observed = marker.get("observed_at")
    if isinstance(observed, str):
        observed = datetime.fromisoformat(observed)
    if isinstance(observed, datetime):
        observed = observed.astimezone(UTC).isoformat()
    values = [
        media_identity_token(row),
        row.get("url"),
        str(marker.get("provider_attempt_id")),
        str(marker.get("raw_artifact_id")),
        observed,
    ]
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ContentPlaybackSource:
    """短事务读取的来源快照，不把 CDN URL 放进公共 Contract。"""

    content_id: UUID
    position: int
    note_id: str
    identity_token: str
    source_revision: str
    url: str | None
    generation: int
    job_id: UUID | None = None
    run_id: UUID | None = None
    state: str = "ready"
    failure_code: str | None = None
    failure_source_revision: str | None = None
    cooldown_until: datetime | None = None


class ContentPlaybackSessionCodec:
    """复用已有签名协议并分离密钥用途，令牌绑定一个 viewer 的一个媒体来源。"""

    def __init__(self, *, secret: bytes, now: Callable[[], datetime] | None = None) -> None:
        self._codec = ContentCursorCodec(
            secret=hmac.new(secret, b"aima-content-video-session.v1", hashlib.sha256).digest(),
            lifetime=timedelta(minutes=15),
            now=now,
        )

    @staticmethod
    def _binding(
        *,
        principal_id: str,
        content_id: UUID,
        position: int,
        identity_token: str,
        source_revision: str,
    ) -> str:
        values = [principal_id, str(content_id), position, identity_token, source_revision]
        return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()

    def issue(
        self,
        *,
        principal_id: str,
        content_id: UUID,
        position: int,
        identity_token: str,
        source_revision: str,
    ) -> str:
        """令牌只有内容身份与签名，不携带 CDN URL、Provider Key 或 Cookie。"""
        return self._codec.encode(
            ContentCursorPosition(None, content_id),
            query_hash=self._binding(
                principal_id=principal_id,
                content_id=content_id,
                position=position,
                identity_token=identity_token,
                source_revision=source_revision,
            ),
        )

    def verify(
        self,
        session: str,
        *,
        principal_id: str,
        content_id: UUID,
        position: int,
        identity_token: str,
        source_revision: str,
    ) -> None:
        """使用当前数据库来源验证；URL 来源更新后旧会话自动失效。"""
        decoded = self._codec.decode(
            session,
            query_hash=self._binding(
                principal_id=principal_id,
                content_id=content_id,
                position=position,
                identity_token=identity_token,
                source_revision=source_revision,
            ),
        )
        if decoded.content_id != content_id:
            raise InvalidContentCursor
