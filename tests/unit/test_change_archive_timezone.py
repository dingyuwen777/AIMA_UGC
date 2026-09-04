from __future__ import annotations

import runpy
import zoneinfo
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVER_PATH = ROOT / "scripts" / "quality" / "archive_change_after_merge.py"


def test_archive_script_falls_back_to_utc8_without_iana_tzdata(monkeypatch) -> None:
    """Windows 等无系统 IANA tzdata 环境仍应按现代北京时间完成归档日期换算。"""

    def missing_zoneinfo(key: str) -> object:
        """模拟系统与项目依赖都无法提供 IANA 时区数据库。"""
        raise zoneinfo.ZoneInfoNotFoundError(key)

    monkeypatch.setattr(zoneinfo, "ZoneInfo", missing_zoneinfo)
    module = runpy.run_path(str(ARCHIVER_PATH))

    assert module["BEIJING"].utcoffset(datetime(2026, 9, 5)) == timedelta(hours=8)
    assert module["merge_month_and_date"]("2026-09-04T16:30:00Z") == (
        "2026-09",
        "2026-09-05",
    )
