"""北京时间系统与外部时间协议边界回归。"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from aima_ugc.platform.reporting import docx_package as docx_package_module


def test_docx_core_properties_convert_beijing_clock_to_utc_z(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OOXML W3CDTF 的 Z 时间必须是同一北京时间时刻转换后的 UTC。"""
    fixed = datetime(2026, 8, 25, 9, 44, 19, tzinfo=ZoneInfo("Asia/Shanghai"))
    monkeypatch.setattr(docx_package_module, "beijing_now", lambda: fixed)

    xml = docx_package_module._core_props_xml()

    assert "2026-08-25T01:44:19Z" in xml
    assert "2026-08-25T09:44:19Z" not in xml
