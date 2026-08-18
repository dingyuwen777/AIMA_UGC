"""唯一 Provider-neutral Excel 导出实现。"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font
from pydantic import ValidationError

from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.contracts.export import (
    UnifiedDataExcelAnalysisV1,
    UnifiedDataExcelCommentV1,
    UnifiedDataExcelContentV1,
    UnifiedDataExcelV1,
)

_BEIJING = ZoneInfo("Asia/Shanghai")
_CONTENT_SHEET = "内容"
_COMMENT_SHEET = "评论"
_ExcelCellValue = str | int | float | bool | datetime | None
_CONTENT_HEADERS = (
    "平台",
    "内容ID",
    "来源项ID",
    "内容类型",
    "标题",
    "正文",
    "作者",
    "发布时间",
    "内容链接",
    "作者粉丝数",
    "作者关注数",
    "作者内容数",
    "作者获赞数",
    "点赞",
    "评论数",
    "收藏数",
    "分享数",
    "转发数",
    "浏览数",
    "播放数",
    "弹幕数",
    "投币数",
    "下载数",
    "命中关键词",
    "情感标签",
    "一级标签",
    "二级标签",
    "分析模型",
    "Prompt版本",
    "Taxonomy版本",
    "来源Provider",
    "Raw/来源定位",
    "评论覆盖",
)
_COMMENT_HEADERS = (
    "平台",
    "内容ID",
    "评论层级",
    "评论ID",
    "根评论ID",
    "父评论ID",
    "作者",
    "评论内容",
    "评论时间",
    "评论点赞",
    "回复数",
    "来源Provider",
    "Raw/来源定位",
)
_HEADER_FONT = Font(bold=True)
_WRAP_ALIGNMENT = Alignment(vertical="top", wrap_text=True)


@dataclass(frozen=True, slots=True)
class ExcelExportSummary:
    """共享 Excel 导出结果摘要。"""

    output_path: Path
    content_rows: int
    comment_rows: int


def project_canonical_content(
    content: CanonicalContentV1,
    *,
    matched_keywords: Iterable[str] = (),
    analysis: UnifiedDataExcelAnalysisV1 | None = None,
    raw_locator: str | None = None,
    coverage: str | None = None,
) -> UnifiedDataExcelContentV1:
    """把 Canonical 内容投影为统一 Excel 内容行，不修改 Canonical。"""

    author = content.author
    metrics = content.metrics
    content_url = content.canonical_url or content.share_url
    return UnifiedDataExcelContentV1(
        platform=content.platform,
        external_content_id=content.external_content_id,
        source_item_id=content.alternate_ids.get("source_article_id"),
        content_type=content.content_type,
        title=content.title,
        text=content.text,
        author_display_name=author.display_name if author is not None else None,
        published_at=content.published_at,
        content_url=str(content_url) if content_url is not None else None,
        author_follower_count=author.follower_count if author is not None else None,
        author_following_count=author.following_count if author is not None else None,
        author_content_count=author.content_count if author is not None else None,
        author_total_like_count=author.total_like_count if author is not None else None,
        like_count=metrics.like_count,
        comment_count=metrics.comment_count,
        favorite_count=metrics.favorite_count,
        share_count=metrics.share_count,
        repost_count=metrics.repost_count,
        view_count=metrics.view_count,
        play_count=metrics.play_count,
        danmaku_count=metrics.danmaku_count,
        coin_count=metrics.coin_count,
        download_count=metrics.download_count,
        matched_keywords=tuple(matched_keywords),
        analysis=analysis,
        source_provider=content.source.provider_name,
        raw_locator=raw_locator if raw_locator is not None else content.source.item_locator,
        coverage=coverage,
    )


def project_canonical_comment(
    comment: CanonicalCommentV1,
    *,
    level: str,
    raw_locator: str | None = None,
) -> UnifiedDataExcelCommentV1:
    """把 Canonical 评论投影为统一 Excel 评论行。"""

    author = comment.author
    return UnifiedDataExcelCommentV1(
        platform=comment.platform,
        external_content_id=comment.external_content_id,
        level=level,
        external_comment_id=comment.external_comment_id,
        root_comment_id=comment.root_comment_id,
        parent_comment_id=comment.parent_comment_id,
        author_display_name=author.display_name if author is not None else None,
        text=comment.text,
        published_at=comment.published_at,
        like_count=comment.metrics.like_count,
        reply_count=comment.metrics.reply_count,
        source_provider=comment.source.provider_name,
        raw_locator=raw_locator if raw_locator is not None else comment.source.item_locator,
    )


def export_unified_content_jsonl_to_excel(
    *,
    input_path: Path,
    output_path: Path,
    include_analysis: bool,
) -> ExcelExportSummary:
    """直接从 UnifiedContentRecordV1 JSONL 派生 Excel，不回读源 XLSX。"""

    return export_unified_data_excel(
        _iter_unified_content_jsonl(Path(input_path)),
        Path(output_path),
        include_analysis=include_analysis,
    )


def export_unified_data_excel(
    records: Iterable[UnifiedDataExcelV1],
    output_path: Path,
    *,
    include_analysis: bool,
) -> ExcelExportSummary:
    """使用 write-only Workbook 流式写出唯一 UnifiedDataExcelV1 视图。"""

    target_path = Path(output_path)
    if target_path.suffix.lower() != ".xlsx":
        raise ValueError("统一 Excel 导出目标必须使用 .xlsx 扩展名")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".{target_path.stem}.tmp{target_path.suffix}")
    temp_path.unlink(missing_ok=True)

    workbook = Workbook(write_only=True)
    content_sheet = workbook.create_sheet(_CONTENT_SHEET)
    comment_sheet = workbook.create_sheet(_COMMENT_SHEET)
    for sheet in (content_sheet, comment_sheet):
        sheet.freeze_panes = "A2"
        sheet.sheet_view.showGridLines = False
    content_sheet.append(_header_cells(content_sheet, _CONTENT_HEADERS))
    comment_sheet.append(_header_cells(comment_sheet, _COMMENT_HEADERS))

    content_rows = 0
    comment_rows = 0
    first_content_id: str | None = None
    first_comment_id: str | None = None
    try:
        for record in records:
            content = record.content
            content_sheet.append(_content_cells(content_sheet, content, include_analysis))
            content_rows += 1
            if first_content_id is None:
                first_content_id = content.external_content_id
            for comment in record.comments:
                comment_sheet.append(_comment_cells(comment_sheet, comment))
                comment_rows += 1
                if first_comment_id is None:
                    first_comment_id = comment.external_comment_id
        workbook.save(temp_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        workbook.close()

    try:
        _verify_workbook(
            temp_path,
            content_rows=content_rows,
            comment_rows=comment_rows,
            first_content_id=first_content_id,
            first_comment_id=first_comment_id,
        )
        os.replace(temp_path, target_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    return ExcelExportSummary(
        output_path=target_path,
        content_rows=content_rows,
        comment_rows=comment_rows,
    )


def _iter_unified_content_jsonl(path: Path) -> Iterator[UnifiedDataExcelV1]:
    with path.open("rb") as input_file:
        for line_number, raw_line in enumerate(input_file, start=1):
            if not raw_line.strip():
                raise ValueError(f"{path}: 第 {line_number} 行为空，拒绝导出")
            try:
                record = UnifiedContentRecordV1.model_validate_json(raw_line)
            except ValidationError as exc:
                raise ValueError(
                    f"{path}: 第 {line_number} 行不是合法 UnifiedContentRecordV1"
                ) from exc
            analysis = None
            if record.analysis is not None:
                analysis = UnifiedDataExcelAnalysisV1(
                    sentiment=record.analysis.sentiment,
                    primary_label=record.analysis.primary_label,
                    secondary_label=record.analysis.secondary_label,
                    model=record.analysis.model,
                    prompt_version=record.analysis.prompt_version,
                    taxonomy_version=record.analysis.taxonomy_sha256,
                )
            yield UnifiedDataExcelV1(
                content=project_canonical_content(
                    record.content,
                    matched_keywords=record.matched_keywords,
                    analysis=analysis,
                )
            )


def _content_cells(
    sheet: Any,
    content: UnifiedDataExcelContentV1,
    include_analysis: bool,
) -> list[Cell]:
    analysis = content.analysis if include_analysis else None
    values: tuple[tuple[_ExcelCellValue, bool, bool], ...] = (
        (content.platform, False, False),
        (content.external_content_id, True, False),
        (content.source_item_id, True, False),
        (content.content_type, False, False),
        (content.title, False, False),
        (content.text, False, False),
        (content.author_display_name, False, False),
        (_display_datetime(content.published_at), False, False),
        (content.content_url, False, True),
        (content.author_follower_count, False, False),
        (content.author_following_count, False, False),
        (content.author_content_count, False, False),
        (content.author_total_like_count, False, False),
        (content.like_count, False, False),
        (content.comment_count, False, False),
        (content.favorite_count, False, False),
        (content.share_count, False, False),
        (content.repost_count, False, False),
        (content.view_count, False, False),
        (content.play_count, False, False),
        (content.danmaku_count, False, False),
        (content.coin_count, False, False),
        (content.download_count, False, False),
        ("；".join(content.matched_keywords) or None, False, False),
        (analysis.sentiment if analysis is not None else None, False, False),
        (analysis.primary_label if analysis is not None else None, False, False),
        (analysis.secondary_label if analysis is not None else None, False, False),
        (analysis.model if analysis is not None else None, False, False),
        (analysis.prompt_version if analysis is not None else None, False, False),
        (analysis.taxonomy_version if analysis is not None else None, False, False),
        (content.source_provider, False, False),
        (content.raw_locator, False, False),
        (content.coverage, False, False),
    )
    return [
        _data_cell(sheet, value, text_id=text_id, hyperlink=link)
        for value, text_id, link in values
    ]


def _comment_cells(sheet: Any, comment: UnifiedDataExcelCommentV1) -> list[Cell]:
    values: tuple[tuple[_ExcelCellValue, bool], ...] = (
        (comment.platform, False),
        (comment.external_content_id, True),
        (comment.level, False),
        (comment.external_comment_id, True),
        (comment.root_comment_id, True),
        (comment.parent_comment_id, True),
        (comment.author_display_name, False),
        (comment.text, False),
        (_display_datetime(comment.published_at), False),
        (comment.like_count, False),
        (comment.reply_count, False),
        (comment.source_provider, False),
        (comment.raw_locator, False),
    )
    return [_data_cell(sheet, value, text_id=text_id) for value, text_id in values]


def _header_cells(sheet: Any, headers: tuple[str, ...]) -> list[Cell]:
    cells: list[Cell] = []
    for value in headers:
        cell = WriteOnlyCell(sheet, value=value)
        cell.font = _HEADER_FONT
        cell.alignment = _WRAP_ALIGNMENT
        cells.append(cell)
    return cells


def _data_cell(
    sheet: Any,
    value: _ExcelCellValue,
    *,
    text_id: bool = False,
    hyperlink: bool = False,
) -> Cell:
    safe_value = _safe_excel_value(value)
    cell = WriteOnlyCell(sheet, value=safe_value)
    cell.alignment = _WRAP_ALIGNMENT
    if text_id and safe_value is not None:
        cell.number_format = "@"
    if hyperlink and isinstance(value, str) and _is_http_url(value):
        cell.hyperlink = value
    return cell


def _safe_excel_value(value: _ExcelCellValue) -> _ExcelCellValue:
    if not isinstance(value, str) or not value:
        return value
    if value[0] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + value
    return value


def _is_http_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _display_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(_BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def _verify_workbook(
    path: Path,
    *,
    content_rows: int,
    comment_rows: int,
    first_content_id: str | None,
    first_comment_id: str | None,
) -> None:
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        if workbook.sheetnames != [_CONTENT_SHEET, _COMMENT_SHEET]:
            raise OSError("统一 Excel 导出后 Sheet 结构校验失败")
        _verify_sheet(
            workbook[_CONTENT_SHEET],
            _CONTENT_HEADERS,
            expected_rows=content_rows,
            first_id=first_content_id,
            id_column=2,
        )
        _verify_sheet(
            workbook[_COMMENT_SHEET],
            _COMMENT_HEADERS,
            expected_rows=comment_rows,
            first_id=first_comment_id,
            id_column=4,
        )
    finally:
        workbook.close()


def _verify_sheet(
    sheet: Any,
    headers: tuple[str, ...],
    *,
    expected_rows: int,
    first_id: str | None,
    id_column: int,
) -> None:
    header = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if header != headers:
        raise OSError(f"统一 Excel 导出后表头校验失败: {sheet.title}")
    sheet.calculate_dimension(force=True)
    if sheet.max_row != expected_rows + 1:
        raise OSError(f"统一 Excel 导出后行数校验失败: {sheet.title}")
    if first_id is None:
        return
    first_row_id = next(
        sheet.iter_rows(
            min_row=2,
            max_row=2,
            min_col=id_column,
            max_col=id_column,
            values_only=True,
        )
    )[0]
    if first_row_id != _safe_excel_value(first_id):
        raise OSError(f"统一 Excel 导出后关键 ID 校验失败: {sheet.title}")
