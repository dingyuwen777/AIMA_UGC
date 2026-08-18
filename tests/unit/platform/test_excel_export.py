from __future__ import annotations

from datetime import UTC, datetime
from importlib.util import find_spec
from pathlib import Path
from zipfile import ZipFile

from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalCommentV1,
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.contracts.export import UnifiedDataExcelAnalysisV1, UnifiedDataExcelV1
from aima_ugc.platform.export import (
    export_unified_data_excel,
    project_canonical_comment,
    project_canonical_content,
)
from openpyxl import load_workbook

_OBSERVED_AT = datetime(2026, 8, 18, 6, 0, tzinfo=UTC)
_PUBLISHED_AT = datetime(2026, 8, 18, 5, 30, tzinfo=UTC)


def _content() -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="00123456789012345678",
        alternate_ids={"source_article_id": "00000042"},
        content_type="image",
        title="=dangerous title",
        text="中文正文 😀",
        canonical_url="https://example.invalid/content/00123456789012345678",
        author=CanonicalAuthorV1(
            display_name="@dangerous author",
            follower_count=1234,
            following_count=56,
            content_count=78,
            total_like_count=9012,
        ),
        published_at=_PUBLISHED_AT,
        observed_at=_OBSERVED_AT,
        metrics=CanonicalMetricsV1(
            like_count=11,
            comment_count=1,
            favorite_count=3,
            share_count=4,
            repost_count=5,
            view_count=6,
            play_count=7,
            danmaku_count=8,
            coin_count=9,
            download_count=10,
        ),
        source=CanonicalSourceV1(
            provider_name="tikhub",
            operation="search",
            item_locator="provider.item[0]",
            observed_at=_OBSERVED_AT,
        ),
        observed_fields=[],
    )


def _comment() -> CanonicalCommentV1:
    return CanonicalCommentV1(
        platform="xiaohongshu",
        external_content_id="00123456789012345678",
        external_comment_id="000000000000000001",
        root_comment_id="000000000000000001",
        parent_comment_id=None,
        author=CanonicalAuthorV1(display_name="评论者"),
        text="+formula-like comment",
        published_at=_PUBLISHED_AT,
        observed_at=_OBSERVED_AT,
        metrics=CanonicalMetricsV1(like_count=2, reply_count=1),
        source=CanonicalSourceV1(
            provider_name="tikhub",
            operation="comments",
            item_locator="provider.comment[0]",
            observed_at=_OBSERVED_AT,
        ),
        observed_fields=[],
    )


def _export_record() -> UnifiedDataExcelV1:
    return UnifiedDataExcelV1(
        content=project_canonical_content(
            _content(),
            matched_keywords=("keyword-a", "keyword-b"),
            analysis=UnifiedDataExcelAnalysisV1(
                sentiment="sentiment-test",
                primary_label="primary-test",
                secondary_label="secondary-test",
                model="model-test",
                prompt_version="prompt-test",
                taxonomy_version="taxonomy-test",
            ),
            raw_locator="raw/search.json#item[0]",
            coverage="partial 1/2",
        ),
        comments=(
            project_canonical_comment(
                _comment(),
                level="一级",
                raw_locator="raw/comments.json#item[0]",
            ),
        ),
    )


def test_shared_exporter_writes_provider_neutral_workbook_and_reopens(tmp_path: Path) -> None:
    output = tmp_path / "raw_data.xlsx"

    summary = export_unified_data_excel((_export_record(),), output, include_analysis=False)

    assert summary.output_path == output
    assert summary.content_rows == 1
    assert summary.comment_rows == 1
    with ZipFile(output) as archive:
        assert archive.testzip() is None

    workbook = load_workbook(output, data_only=False)
    try:
        assert workbook.sheetnames == ["内容", "评论"]
        content_sheet = workbook["内容"]
        comment_sheet = workbook["评论"]
        assert content_sheet.freeze_panes == "A2"
        assert comment_sheet.freeze_panes == "A2"
        assert not content_sheet.merged_cells.ranges
        assert not comment_sheet.merged_cells.ranges

        content_headers = [cell.value for cell in content_sheet[1]]
        comment_headers = [cell.value for cell in comment_sheet[1]]
        assert content_headers == [
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
        ]
        assert comment_headers == [
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
        ]

        content_row = content_sheet[2]
        assert content_row[1].value == "00123456789012345678"
        assert content_row[1].number_format == "@"
        assert content_row[2].value == "00000042"
        assert content_row[2].number_format == "@"
        assert content_row[4].value == "'=dangerous title"
        assert content_row[6].value == "'@dangerous author"
        assert content_row[7].value == "2026-08-18 13:30:00"
        assert content_row[8].hyperlink is not None
        assert content_row[8].hyperlink.target == (
            "https://example.invalid/content/00123456789012345678"
        )
        assert content_row[23].value == "keyword-a；keyword-b"
        assert all(content_row[index].value is None for index in range(24, 30))
        assert content_row[30].value == "tikhub"
        assert content_row[31].value == "raw/search.json#item[0]"
        assert content_row[32].value == "partial 1/2"

        comment_row = comment_sheet[2]
        assert comment_row[1].value == "00123456789012345678"
        assert comment_row[1].number_format == "@"
        assert comment_row[3].value == "000000000000000001"
        assert comment_row[3].number_format == "@"
        assert comment_row[7].value == "'+formula-like comment"
        assert comment_row[8].value == "2026-08-18 13:30:00"
        assert comment_row[12].value == "raw/comments.json#item[0]"
    finally:
        workbook.close()


def test_raw_and_labeled_exports_keep_same_schema(tmp_path: Path) -> None:
    raw_output = tmp_path / "raw.xlsx"
    labeled_output = tmp_path / "labeled.xlsx"
    record = _export_record()

    export_unified_data_excel((record,), raw_output, include_analysis=False)
    export_unified_data_excel((record,), labeled_output, include_analysis=True)

    raw_workbook = load_workbook(raw_output, data_only=False, read_only=True)
    labeled_workbook = load_workbook(labeled_output, data_only=False, read_only=True)
    try:
        raw_headers = [cell.value for cell in next(raw_workbook["内容"].iter_rows(max_row=1))]
        labeled_headers = [
            cell.value for cell in next(labeled_workbook["内容"].iter_rows(max_row=1))
        ]
        assert raw_workbook.sheetnames == labeled_workbook.sheetnames == ["内容", "评论"]
        assert raw_headers == labeled_headers

        raw_values = [cell.value for cell in next(raw_workbook["内容"].iter_rows(min_row=2, max_row=2))]
        labeled_values = [
            cell.value for cell in next(labeled_workbook["内容"].iter_rows(min_row=2, max_row=2))
        ]
        assert raw_values[:24] == labeled_values[:24]
        assert raw_values[24:30] == [None] * 6
        assert labeled_values[24:30] == [
            "sentiment-test",
            "primary-test",
            "secondary-test",
            "model-test",
            "prompt-test",
            "taxonomy-test",
        ]
        assert raw_values[30:] == labeled_values[30:]
    finally:
        raw_workbook.close()
        labeled_workbook.close()


def test_tikhub_parallel_excel_module_is_removed() -> None:
    assert find_spec("aima_ugc.adapters.providers.tikhub_test.core.excel") is None
