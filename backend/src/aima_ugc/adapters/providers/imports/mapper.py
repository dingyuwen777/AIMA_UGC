"""AIMA Monitoring Excel 行 → CanonicalContentV1 纯 Mapper。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta, timezone

from pydantic import AnyHttpUrl

from aima_ugc.contracts.canonical import CanonicalAuthorV1, CanonicalContentV1, CanonicalSourceV1

from .excel_profile import ExcelImportProfile
from .identity import resolve_content_identity
from .models import ExcelImportRow, ExcelImportRowError

_SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")


def map_excel_row(
    row: ExcelImportRow,
    *,
    profile: ExcelImportProfile,
    input_name: str,
    sheet_name: str,
    observed_at: datetime,
) -> CanonicalContentV1:
    """把一行源 Excel 映射为 Provider-neutral Canonical 内容事实。"""

    values = row.values
    platform = profile.resolve_platform(values.get("媒体名称（中文）"))
    identity = resolve_content_identity(
        platform=platform,
        canonical_url=values.get("原文链接"),
        source_article_id=values.get("文章编号"),
    )

    observed_fields: list[str] = []
    title = _optional_text(values.get("标题"))
    if title is not None:
        observed_fields.append("title")
    text = _optional_text(values.get("内文"))
    if text is not None:
        observed_fields.append("text")

    canonical_url = (
        AnyHttpUrl(identity.normalized_url) if identity.normalized_url is not None else None
    )
    if canonical_url is not None:
        observed_fields.append("canonical_url")

    published_at = _published_at(values.get("出版日期"))
    if published_at is not None:
        observed_fields.append("published_at")

    author, author_fields = _author(values)
    observed_fields.extend(f"author.{field}" for field in author_fields)

    if identity.alternate_ids:
        observed_fields.append("alternate_ids")

    return CanonicalContentV1(
        platform=platform,
        external_content_id=identity.external_content_id,
        alternate_ids=identity.alternate_ids,
        content_type="unknown",
        title=title,
        text=text,
        canonical_url=canonical_url,
        author=author,
        published_at=published_at,
        observed_at=observed_at,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            source_type=profile.name,
            source_value=input_name,
            item_locator=f"sheet={sheet_name};row={row.row_number}",
            observed_at=observed_at,
        ),
        observed_fields=observed_fields,
    )


def _author(values: Mapping[str, object]) -> tuple[CanonicalAuthorV1 | None, tuple[str, ...]]:
    display_name = _optional_text(values.get("作者"))
    follower_count = _non_negative_int(values.get("粉丝数"))
    fields: list[str] = []
    if display_name is not None:
        fields.append("display_name")
    if follower_count is not None:
        fields.append("follower_count")
    if not fields:
        return None, ()
    return (
        CanonicalAuthorV1(display_name=display_name, follower_count=follower_count),
        tuple(fields),
    )


def _published_at(value: object) -> datetime | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    parsed: datetime
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        text = value.strip().replace("/", "-")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ExcelImportRowError("published_at_invalid", "出版日期无法解析") from exc
    else:
        raise ExcelImportRowError("published_at_invalid", "出版日期必须是日期或日期时间")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_SHANGHAI)
    return parsed.astimezone(UTC)


def _non_negative_int(value: object) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ExcelImportRowError("follower_count_invalid", "粉丝数必须是非负整数")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise ExcelImportRowError("follower_count_invalid", "粉丝数必须是非负整数")
        parsed = int(value)
    else:
        text = str(value).strip().replace(",", "")
        try:
            parsed = int(text)
        except ValueError as exc:
            raise ExcelImportRowError("follower_count_invalid", "粉丝数必须是非负整数") from exc
    if parsed < 0:
        raise ExcelImportRowError("follower_count_invalid", "粉丝数必须是非负整数")
    return parsed


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
