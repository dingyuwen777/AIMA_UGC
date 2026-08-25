"""系统默认北京时间策略回归；第三方 Raw/外部协议的原始时间解析不被改写。"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aima_ugc.contracts.http import ImportBatchSummaryResponse

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = ROOT / "backend" / "src" / "aima_ugc"

_FORBIDDEN_CURRENT_TIME_PATTERNS = (
    re.compile(r"datetime\.utcnow\s*\("),
    re.compile(r"datetime\.now\s*\(\s*\)"),
    re.compile(r"datetime\.now\s*\(\s*(?:UTC|timezone\.utc)\s*\)"),
    re.compile(r"datetime\.now\s*\(\s*tz\s*=\s*(?:UTC|timezone\.utc)\s*\)"),
    re.compile(r"date\.today\s*\("),
)


def _system_python_files() -> tuple[Path, ...]:
    """返回生产 Python 文件；扫描只限制自产当前时间，不禁止外部 timestamp/epoch 解析。"""
    return tuple(sorted(BACKEND_ROOT.rglob("*.py")))


def test_http_datetime_serialization_uses_beijing_offset() -> None:
    """AIMA 自有 HTTP datetime 即使接收 UTC aware 值，也必须序列化为北京时间。"""
    response = ImportBatchSummaryResponse(
        processing_count=0,
        completed_today_count=0,
        rows_ingested_today=0,
        as_of=datetime(2026, 8, 25, 1, 44, 19, tzinfo=UTC),
    )

    payload = response.model_dump(mode="json")
    assert payload["as_of"] == "2026-08-25T09:44:19+08:00"


def test_system_source_does_not_generate_current_time_from_utc_or_host_local_time() -> None:
    """系统自产当前时间不得再使用 UTC-now、naive now 或宿主 date.today。"""
    violations: list[str] = []
    for path in _system_python_files():
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in _FORBIDDEN_CURRENT_TIME_PATTERNS):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")

    assert not violations, "系统自产时间必须改用 Asia/Shanghai：\n" + "\n".join(violations)


def test_beijing_offset_is_fixed_for_aima_business_time() -> None:
    """当前 AIMA 业务时区在本地日期范围内应保持 UTC+8。"""
    from zoneinfo import ZoneInfo

    beijing = ZoneInfo("Asia/Shanghai")
    value = datetime(2026, 8, 25, 9, 44, 19, tzinfo=beijing)
    assert value.utcoffset() == timedelta(hours=8)
