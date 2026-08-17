"""TikHub 调试结果的人工审阅 XLSX。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

_FORMULA_PREFIXES = ("=", "+", "-", "@")
_HEADER_FILL = PatternFill(fill_type="solid", fgColor="DCEAF7")
_BLOCK_FILL = PatternFill(fill_type="solid", fgColor="F7FAFC")
_WHITE_FILL = PatternFill(fill_type="solid", fgColor="FFFFFF")
_HEADER_FONT = Font(name="Microsoft YaHei", size=10, bold=True, color="203040")
_BODY_FONT = Font(name="Microsoft YaHei", size=10, color="283442")
_LINK_FONT = Font(name="Microsoft YaHei", size=10, color="0563C1", underline="single")
_THIN_SEPARATOR = Side(style="thin", color="D7DEE7")
_BOTTOM_BORDER = Border(bottom=_THIN_SEPARATOR)

_CONTENT_HEADERS = (
    "平台",
    "内容ID",
    "内容类型",
    "标题",
    "正文",
    "作者",
    "发布时间",
    "内容链接",
    "点赞",
    "评论数",
    "收藏数",
    "分享数",
    "评论覆盖",
    "Raw定位",
)
_COMMENT_HEADERS = (
    "评论层级",
    "评论ID",
    "根评论ID",
    "父评论ID",
    "评论作者",
    "评论内容",
    "评论时间",
    "评论点赞",
    "回复数",
    "评论Raw定位",
)
_HEADERS = _CONTENT_HEADERS + _COMMENT_HEADERS
_TEXT_ID_COLUMNS = {2, 16, 17, 18}
_WRAP_COLUMNS = {4, 5, 13, 14, 19, 20, 24}
_COLUMN_WIDTHS = {
    1: 10,
    2: 24,
    3: 11,
    4: 28,
    5: 46,
    6: 18,
    7: 20,
    8: 34,
    9: 11,
    10: 11,
    11: 11,
    12: 11,
    13: 18,
    14: 34,
    15: 10,
    16: 24,
    17: 24,
    18: 24,
    19: 18,
    20: 44,
    21: 20,
    22: 11,
    23: 11,
    24: 34,
}


@dataclass(frozen=True, slots=True)
class ReviewContent:
    platform: str
    external_content_id: str
    content_type: str
    title: str | None
    text: str | None
    author: str | None
    published_at: str | None
    content_url: str | None
    like_count: int | None
    comment_count: int | None
    favorite_count: int | None
    share_count: int | None
    coverage: str
    raw_locator: str


@dataclass(frozen=True, slots=True)
class ReviewCommentRow:
    level: str
    comment_id: str
    root_comment_id: str | None
    parent_comment_id: str | None
    author: str | None
    text: str | None
    published_at: str | None
    like_count: int | None
    reply_count: int | None
    raw_locator: str


@dataclass(frozen=True, slots=True)
class ReviewBlock:
    content: ReviewContent
    comments: tuple[ReviewCommentRow, ...] = ()


def write_review_workbook(blocks: tuple[ReviewBlock, ...], path: str | Path) -> Path:
    """生成已批准的 `内容与评论` 纵向区块人工审阅 Workbook。"""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "内容与评论"
    _configure_sheet(sheet)
    _write_header(sheet)

    row = 2
    for block_index, block in enumerate(blocks):
        rows = block.comments or (_empty_comment_row(),)
        start_row = row
        fill = _BLOCK_FILL if block_index % 2 == 0 else _WHITE_FILL
        for comment in rows:
            _write_content_row(sheet, row, block.content)
            _write_comment_row(sheet, row, comment)
            _style_body_row(sheet, row, fill=fill)
            row += 1
        end_row = row - 1
        if end_row > start_row:
            for column in range(1, len(_CONTENT_HEADERS) + 1):
                sheet.merge_cells(
                    start_row=start_row,
                    start_column=column,
                    end_row=end_row,
                    end_column=column,
                )
        _apply_content_hyperlink(sheet, start_row, block.content.content_url)
        _apply_block_separator(sheet, end_row)

    workbook.save(output)
    return output


def _configure_sheet(sheet: Worksheet) -> None:
    sheet.freeze_panes = "A2"
    sheet.sheet_view.showGridLines = False
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(_HEADERS))}1"
    sheet.row_dimensions[1].height = 32
    for column, width in _COLUMN_WIDTHS.items():
        sheet.column_dimensions[get_column_letter(column)].width = width
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.outlinePr.summaryBelow = True


def _write_header(sheet: Worksheet) -> None:
    for column, value in enumerate(_HEADERS, start=1):
        cell = sheet.cell(row=1, column=column, value=value)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BOTTOM_BORDER


def _write_content_row(sheet: Worksheet, row: int, content: ReviewContent) -> None:
    values: tuple[object, ...] = (
        content.platform,
        content.external_content_id,
        content.content_type,
        content.title,
        content.text,
        content.author,
        content.published_at,
        content.content_url,
        content.like_count,
        content.comment_count,
        content.favorite_count,
        content.share_count,
        content.coverage,
        content.raw_locator,
    )
    for column, value in enumerate(values, start=1):
        _set_value(sheet.cell(row=row, column=column), value, text_id=column in _TEXT_ID_COLUMNS)


def _write_comment_row(sheet: Worksheet, row: int, comment: ReviewCommentRow) -> None:
    values: tuple[object, ...] = (
        comment.level,
        comment.comment_id,
        comment.root_comment_id,
        comment.parent_comment_id,
        comment.author,
        comment.text,
        comment.published_at,
        comment.like_count,
        comment.reply_count,
        comment.raw_locator,
    )
    for offset, value in enumerate(values, start=1):
        column = len(_CONTENT_HEADERS) + offset
        _set_value(sheet.cell(row=row, column=column), value, text_id=column in _TEXT_ID_COLUMNS)


def _set_value(cell: object, value: object, *, text_id: bool) -> None:
    # openpyxl Cell 类型运行时拥有 value/number_format；保持这里的小型 helper 易于静态复核。
    target = cell
    if isinstance(value, str):
        safe_value = _safe_external_text(value)
    else:
        safe_value = value
    setattr(target, "value", safe_value)
    if text_id:
        setattr(target, "number_format", "@")


def _style_body_row(sheet: Worksheet, row: int, *, fill: PatternFill) -> None:
    sheet.row_dimensions[row].height = 44
    for column in range(1, len(_HEADERS) + 1):
        cell = sheet.cell(row=row, column=column)
        cell.font = _BODY_FONT
        cell.fill = fill
        cell.alignment = Alignment(
            vertical="top",
            horizontal="left",
            wrap_text=column in _WRAP_COLUMNS,
        )
        cell.border = Border()


def _apply_content_hyperlink(sheet: Worksheet, row: int, content_url: str | None) -> None:
    if not content_url or not content_url.startswith(("https://", "http://")):
        return
    cell = sheet.cell(row=row, column=8)
    cell.hyperlink = content_url
    cell.font = _LINK_FONT


def _apply_block_separator(sheet: Worksheet, row: int) -> None:
    for column in range(1, len(_HEADERS) + 1):
        sheet.cell(row=row, column=column).border = _BOTTOM_BORDER


def _safe_external_text(value: str) -> str:
    if value.startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def _empty_comment_row() -> ReviewCommentRow:
    return ReviewCommentRow(
        level="—",
        comment_id="",
        root_comment_id=None,
        parent_comment_id=None,
        author=None,
        text=None,
        published_at=None,
        like_count=None,
        reply_count=None,
        raw_locator="",
    )


__all__ = [
    "ReviewBlock",
    "ReviewCommentRow",
    "ReviewContent",
    "write_review_workbook",
]
