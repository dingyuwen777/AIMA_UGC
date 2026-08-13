"""AIMA_UGC 一行结构化日志 Formatter。"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

_BEIJING: Final = ZoneInfo("Asia/Shanghai")
_FIELD_LIMIT: Final = 2_048
_EXCEPTION_LIMIT: Final = 4_096
_LINE_LIMIT: Final = 8_192

_STANDARD_LOG_RECORD_KEYS: Final = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
    | {
        "message",
        "asctime",
        "service",
        "event",
    }
)
_KEY_PATTERN: Final = re.compile(r"^[A-Za-z0-9_.-]+$")
_SENSITIVE_KEY_PATTERN: Final = re.compile(
    r"(?:authorization|cookie|password|passwd|secret|token|api[_ -]?key)",
    re.IGNORECASE,
)
_INLINE_PATTERNS: Final = (
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer ***"),
    (
        re.compile(
            r"(?i)\b(authorization|cookie|password|passwd|secret|token|api[_ -]?key)"
            r"\s*([=:])\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
        ),
        r"\1\2***",
    ),
    (
        re.compile(r"(?i)\b(postgresql(?:\+psycopg)?://[^:\s/@]+):[^@\s/]+@"),
        r"\1:***@",
    ),
    (
        re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"),
        "***@***",
    ),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "***"),
    (re.compile(r"(?<!\d)\d{17}[\dXx](?![\dXx])"), "***"),
)


def _redact_text(value: str) -> str:
    redacted = value
    for pattern, replacement in _INLINE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _truncate(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[: max(0, limit - 3)] + "...", True


def _render_value(key: str, value: object) -> tuple[str, bool]:
    if _SENSITIVE_KEY_PATTERN.search(key):
        return json.dumps("***", ensure_ascii=False), False
    if value is None:
        return "null", False
    if isinstance(value, bool):
        return ("true" if value else "false"), False
    if isinstance(value, (int, float)):
        return str(value), False

    rendered, truncated = _truncate(_redact_text(str(value)), _FIELD_LIMIT)
    return json.dumps(rendered, ensure_ascii=False), truncated


class AimaLogFormatter(logging.Formatter):
    """输出北京时间毫秒时间、稳定事件字段和安全的一行日志。"""

    def __init__(self, *, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        moment = datetime.fromtimestamp(record.created, tz=_BEIJING)
        timestamp = moment.strftime("%Y-%m-%d %H:%M:%S.") + f"{moment.microsecond // 1000:03d}"
        source = f"{Path(record.pathname).name}:{record.lineno}"
        event = str(getattr(record, "event", "log.message"))

        message, truncated = _truncate(_redact_text(record.getMessage()), _FIELD_LIMIT)
        parts = [
            f"[{timestamp}]",
            f"[{record.levelname}]",
            f"service={self._service}",
            f"source={source}",
            f"event={event}",
        ]

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_RECORD_KEYS
        }
        for key in sorted(extras):
            if not _KEY_PATTERN.fullmatch(key):
                continue
            rendered, field_truncated = _render_value(key, extras[key])
            truncated = truncated or field_truncated
            parts.append(f"{key}={rendered}")

        if record.exc_info:
            exception = _redact_text(self.formatException(record.exc_info))
            exception, exception_truncated = _truncate(exception, _EXCEPTION_LIMIT)
            truncated = truncated or exception_truncated
            parts.append(f"exception={json.dumps(exception, ensure_ascii=False)}")

        parts.append(f"message={json.dumps(message, ensure_ascii=False)}")
        if truncated:
            parts.append("truncated=true")

        line = " ".join(parts)
        if len(line) > _LINE_LIMIT:
            line = line[: _LINE_LIMIT - 21] + '..." truncated=true'
        return line.replace("\r", r"\r").replace("\n", r"\n")
