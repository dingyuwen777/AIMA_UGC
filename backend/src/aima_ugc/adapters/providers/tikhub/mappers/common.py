"""TikHub 多平台纯 Mapper 共用的小型值转换工具。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from uuid import UUID

from aima_ugc.contracts.canonical import CanonicalSourceV1


@dataclass(frozen=True, slots=True)
class TikHubMappingContext:
    """Mapper 显式采集上下文；不得包含 Secret。"""

    provider_request_id: str
    provider_attempt_id: str
    raw_artifact_id: UUID
    operation: str
    source_type: str
    source_value: str
    observed_at: datetime
    external_content_id: str | None = None
    root_comment_id: str | None = None


def source(context: TikHubMappingContext, item_locator: str) -> CanonicalSourceV1:
    return CanonicalSourceV1(
        provider_name="tikhub",
        operation=context.operation,
        provider_request_id=context.provider_request_id,
        provider_attempt_id=context.provider_attempt_id,
        raw_artifact_id=context.raw_artifact_id,
        source_type=context.source_type,
        source_value=context.source_value,
        item_locator=item_locator,
        observed_at=context.observed_at,
    )


def first_dict(raw: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return {}


def optional_string(raw: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key not in raw or raw[key] is None:
            continue
        text = str(raw[key]).strip()
        if text:
            return text
    return None


def required_string(raw: dict[str, Any], *keys: str) -> str:
    value = optional_string(raw, *keys)
    if value is None:
        raise ValueError(f"缺少稳定外部 ID: {keys}")
    return value


def optional_bool(raw: dict[str, Any], *keys: str) -> bool | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, bool):
            return value
    return None


def count(raw: dict[str, Any], *keys: str) -> tuple[int | None, bool]:
    for key in keys:
        if key not in raw:
            continue
        value = raw[key]
        if value is None:
            return None, True
        if isinstance(value, bool):
            return None, False
        try:
            parsed = int(value)
        except TypeError, ValueError:
            return None, False
        return (parsed if parsed >= 0 else None), parsed >= 0
    return None, False


def timestamp(raw: dict[str, Any], *keys: str) -> datetime | None:
    for key in keys:
        if key not in raw or raw[key] is None:
            continue
        parsed = parse_timestamp(raw[key])
        if parsed is not None:
            return parsed
    return None


def parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, bool):
        return None
    numeric: float | None = None
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            numeric = float(text)
        else:
            iso_text = text[:-1] + "+00:00" if text.endswith("Z") else text
            try:
                parsed_iso = datetime.fromisoformat(iso_text)
            except ValueError:
                parsed_iso = None
            if parsed_iso is not None and parsed_iso.tzinfo is not None:
                return parsed_iso.astimezone(UTC)
            try:
                parsed_mail = parsedate_to_datetime(text)
            except TypeError, ValueError, OverflowError:
                parsed_mail = None
            if parsed_mail is not None and parsed_mail.tzinfo is not None:
                return parsed_mail.astimezone(UTC)
            return None
    if numeric is None:
        return None
    if numeric > 10_000_000_000:
        numeric /= 1000
    try:
        return datetime.fromtimestamp(numeric, tz=UTC)
    except OverflowError, OSError, ValueError:
        return None


def http_url(raw: dict[str, Any], *keys: str) -> str | None:
    value = optional_string(raw, *keys)
    if value is None or not value.startswith(("http://", "https://")):
        return None
    return value
