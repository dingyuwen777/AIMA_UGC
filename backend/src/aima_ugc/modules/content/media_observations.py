"""Content Owner 共用的媒体观察与属性来源撤销规则，不执行 I/O。"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from aima_ugc.contracts.canonical import CanonicalContentV1

MEDIA_FIELDS = (
    "media_type",
    "external_media_id",
    "url",
    "preview_url",
    "width",
    "height",
    "duration_ms",
    "mime_type",
    "alt_text",
)
_SOURCE_FIELDS = ("provider_attempt_id", "raw_artifact_id", "observed_at")


def media_identity_token(row: Mapping[str, Any]) -> str:
    """旧行无需回填；第一次观察后将稳定身份冻结到元数据。"""
    metadata = row.get("observation_metadata") or {}
    if isinstance(metadata, dict) and isinstance(metadata.get("identity_token"), str):
        return str(metadata["identity_token"])
    identity = (
        row.get("content_id"),
        row.get("position"),
        row.get("media_type"),
        row.get("external_media_id") or row.get("url"),
    )
    return hashlib.sha256(repr(identity).encode()).hexdigest()


def _marker(row: Mapping[str, Any], field: str) -> dict[str, str]:
    """旧行每个属性沿用其整行来源；新行使用属性自己的来源。"""
    metadata = row.get("observation_metadata") or {}
    marker = metadata.get("fields", {}).get(field) if isinstance(metadata, dict) else None
    if isinstance(marker, dict):
        result = dict(marker)
    else:
        result = {
            key: value.isoformat() if hasattr(value, "isoformat") else str(value)
            for key in _SOURCE_FIELDS
            if (value := row.get(key)) is not None
        }
    if isinstance(observed_at := result.get("observed_at"), str):
        # 历史 batch Delta 的 UTC 与 PostgreSQL Session 的 +08:00 表达同一绝对时间。
        parsed = datetime.fromisoformat(observed_at)
        if parsed.utcoffset() is not None:
            result["observed_at"] = parsed.astimezone(UTC).isoformat()
    return result


def merge_media_rows(
    existing: Sequence[Mapping[str, Any]],
    observation: CanonicalContentV1,
    *,
    content_id: UUID,
    attempt_id: UUID,
    raw_id: UUID,
) -> tuple[dict[str, Any], ...]:
    """调用方先认领父级 freshness；这里只合并被本次真实观察到的属性。"""
    previous = {int(row["position"]): deepcopy(dict(row)) for row in existing}
    merged = previous.copy() if observation.media_collection_mode == "partial" else {}
    source: dict[str, Any] = {
        "provider_attempt_id": attempt_id,
        "raw_artifact_id": raw_id,
        "observed_at": observation.observed_at,
    }
    positions: set[int] = set()
    for item in observation.media:
        position = item.position
        if position in positions:
            raise ValueError("Canonical media position 不能重复")
        positions.add(position)
        fields = set(MEDIA_FIELDS if item.observed_fields is None else item.observed_fields)
        old = previous.get(position)
        replaced = (
            old is None
            or ("media_type" in fields and old["media_type"] != item.media_type)
            or (
                "external_media_id" in fields
                and old.get("external_media_id") is not None
                and item.external_media_id is not None
                and old.get("external_media_id") != item.external_media_id
            )
        )
        if replaced:
            row: dict[str, Any] = {field: None for field in MEDIA_FIELDS}
            row.update(
                content_id=content_id, position=position, media_type=item.media_type, **source
            )
            token = hashlib.sha256(
                f"{content_id}:{position}:{item.media_type}:{item.external_media_id}:{attempt_id}".encode()
            ).hexdigest()
            markers: dict[str, Any] = {}
        else:
            assert old is not None
            row = deepcopy(old)
            token = media_identity_token(row)
            markers = {field: _marker(row, field) for field in MEDIA_FIELDS}
        for field in fields:
            value = getattr(item, field)
            row[field] = (
                str(value) if field in {"url", "preview_url"} and value is not None else value
            )
            markers[field] = _marker(source, field)
        row.update(source)
        row["observation_metadata"] = {"identity_token": token, "fields": markers}
        merged[position] = row
    return tuple(merged[position] for position in sorted(merged))


def normalize_legacy_media_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """加列后旧 v1 Delta 缺省 {} 与数据库默认值保持等价。"""
    return tuple(
        {**row, "observation_metadata": row.get("observation_metadata") or {}} for row in rows
    )


def rollback_media_rows(
    current: Sequence[Mapping[str, Any]],
    *,
    before: Sequence[Mapping[str, Any]],
    after: Sequence[Mapping[str, Any]],
    allow_restore_deleted: bool = True,
    content_id: UUID | None = None,
) -> tuple[dict[str, Any], ...]:
    """只回退值、属性来源及媒体身份仍归属于本贡献的部分。"""
    current_by_pos = {int(row["position"]): deepcopy(dict(row)) for row in current}
    before_by_pos = {int(row["position"]): dict(row) for row in before}
    after_by_pos = {int(row["position"]): dict(row) for row in after}
    for position in before_by_pos.keys() | after_by_pos.keys():
        old, applied, row = (
            before_by_pos.get(position),
            after_by_pos.get(position),
            current_by_pos.get(position),
        )
        if applied is None:
            if row is None and old is not None and allow_restore_deleted:
                current_by_pos[position] = deepcopy(old)
            continue

        def identity(value: Mapping[str, Any]) -> str:
            # 历史 Delta 不含 content_id；补入调用方身份才能核对首次 partial 冻结的 token。
            return media_identity_token({"content_id": content_id, **value})

        if row is None or identity(row) != identity(applied):
            continue
        if normalize_legacy_media_rows((row,)) == normalize_legacy_media_rows((applied,)):
            if old is None:
                current_by_pos.pop(position)
            else:
                current_by_pos[position] = deepcopy(old)
            continue
        # 新身份已有后续贡献时只能清除撤销来源的属性，不能复活旧图片或旧视频的 URL。
        baseline = old if old is not None and identity(old) == identity(applied) else None
        metadata = deepcopy(row.get("observation_metadata") or {})
        markers = metadata.setdefault(
            "fields", {field: _marker(row, field) for field in MEDIA_FIELDS}
        )
        for field in MEDIA_FIELDS:
            if row.get(field) != applied.get(field) or _marker(row, field) != _marker(
                applied, field
            ):
                continue
            if baseline is None and field == "media_type":
                continue
            row[field] = baseline.get(field) if baseline is not None else None
            if baseline is not None:
                markers[field] = _marker(baseline, field)
            else:
                markers.pop(field, None)
        row["observation_metadata"] = metadata
        if baseline is not None and all(row.get(key) == applied.get(key) for key in _SOURCE_FIELDS):
            row.update({key: baseline.get(key) for key in _SOURCE_FIELDS})
    # 一次批量恢复可能混合旧 v1 与新 v2 行，所有行必须具有相同的新表列形状。
    return normalize_legacy_media_rows(
        tuple(current_by_pos[position] for position in sorted(current_by_pos))
    )
