"""AIMA 系统统一北京时间能力。"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    """返回带明确 Asia/Shanghai 时区的当前北京时间。"""
    return datetime.now(BEIJING_TIMEZONE)


def beijing_today() -> date:
    """返回按北京时间计算的当前日期。"""
    return beijing_now().date()


def to_beijing(value: datetime) -> datetime:
    """把带时区 datetime 转换为北京时间，并拒绝无时区值。"""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime 必须包含时区")
    return value.astimezone(BEIJING_TIMEZONE)


def serialize_beijing_datetime(value: datetime) -> str:
    """把带时区 datetime 序列化为带 +08:00 偏移的 ISO-8601 北京时间。"""
    return to_beijing(value).isoformat()
