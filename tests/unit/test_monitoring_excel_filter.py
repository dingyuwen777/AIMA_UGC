"""监测 Excel 目录批量过滤工具的直接行为测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aima_ugc.adapters.providers.imports.models import ExcelImportRowError
from aima_ugc.adapters.providers.imports_test.monitoring_excel_filter.process_directory import (
    PROFILE,
    convert_supported_platforms,
    discover_input_files,
    process_directory,
)
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1
from openpyxl import Workbook

_HEADERS = (
    "媒体名称（中文）",
    "文章编号",
    "标题",
    "内文",
    "作者",
    "出版日期",
    "原文链接",
    "粉丝数",
)


def _write_workbook(path: Path, rows: list[tuple[object, ...]]) -> None:
    """写入最小但符合当前 Monitoring Excel Profile 的 XLSX Fixture。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "文章"
    worksheet.append(list(_HEADERS))
    for row in rows:
        worksheet.append(list(row))
    workbook.save(path)
    workbook.close()


def _row(
    *,
    media_name: object,
    article_id: object,
    title: object,
    text: object,
    url: object,
) -> tuple[object, ...]:
    """构造一个测试用监测 Excel 数据行。"""

    return (
        media_name,
        article_id,
        title,
        text,
        "测试作者",
        datetime(2026, 6, 15, 12, 30),
        url,
        100,
    )


def _read_non_empty_lines(path: Path) -> list[bytes]:
    """读取 JSONL 中的非空行，便于测试 Contract。"""

    return [line for line in path.read_bytes().splitlines() if line.strip()]


def test_discover_input_files_recurses_and_ignores_temp_files(tmp_path: Path) -> None:
    """目录发现应递归读取 XLSX、忽略 Excel 临时文件并保持确定性顺序。"""

    first = tmp_path / "2026-03" / "2026-03-01_a.XLSX"
    second = tmp_path / "2026-03-02_b.xlsx"
    first.parent.mkdir(parents=True)
    first.touch()
    second.touch()
    (tmp_path / "~$2026-03-03_temp.xlsx").touch()
    (tmp_path / "ignore.csv").touch()

    assert discover_input_files(tmp_path) == (first, second)


def test_discover_input_files_fails_when_no_xlsx_exists(tmp_path: Path) -> None:
    """目录中没有真实 XLSX 时应明确失败，而不是发布空结果。"""

    (tmp_path / "~$temp.xlsx").touch()
    (tmp_path / "ignore.csv").touch()

    with pytest.raises(FileNotFoundError, match="未发现 XLSX"):
        discover_input_files(tmp_path)


def test_convert_supported_platforms_skips_only_unmapped_platform(tmp_path: Path) -> None:
    """五平台行应写 Canonical，非五平台行只按 platform_unmapped 跳过。"""

    source = tmp_path / "2026-06" / "2026-06-15_sample.xlsx"
    _write_workbook(
        source,
        [
            _row(
                media_name="小红书",
                article_id="source-a",
                title="爱玛元宇宙体验",
                text="正文",
                url="https://www.xiaohongshu.com/explore/abc123",
            ),
            _row(
                media_name="微信",
                article_id="wechat-source",
                title="非目标平台",
                text="正文",
                url="https://example.com/wechat",
            ),
            _row(
                media_name="抖音",
                article_id="douyin-source",
                title="普通内容",
                text="正文",
                url="https://www.douyin.com/video/1234567890123456789",
            ),
        ],
    )
    output_path = tmp_path / "output" / "canonical" / "contents.jsonl"

    summary = convert_supported_platforms(
        input_paths=(source,),
        input_root=tmp_path,
        output_path=output_path,
        profile_name=PROFILE,
        sheet_name="文章",
        observed_at=datetime(2026, 9, 12, 0, 0, tzinfo=UTC),
    )

    assert summary.rows_seen == 3
    assert summary.rows_supported_platform == 2
    assert summary.rows_skipped_platform_unmapped == 1
    assert summary.skipped_media_names == {"微信": 1}
    assert summary.files[0].source == "2026-06/2026-06-15_sample.xlsx"
    assert summary.rows_seen == (
        summary.rows_supported_platform + summary.rows_skipped_platform_unmapped
    )

    records = [
        CanonicalContentV1.model_validate_json(line) for line in _read_non_empty_lines(output_path)
    ]
    assert [record.platform for record in records] == ["xiaohongshu", "douyin"]
    assert all(record.source.source_value == summary.files[0].source for record in records)


def test_convert_supported_platforms_does_not_swallow_target_data_errors(tmp_path: Path) -> None:
    """除 platform_unmapped 外的 Mapper 错误必须继续失败关闭。"""

    source = tmp_path / "broken.xlsx"
    _write_workbook(
        source,
        [
            _row(
                media_name=None,
                article_id="missing-platform",
                title="爱玛",
                text="正文",
                url="https://www.xiaohongshu.com/explore/abc123",
            )
        ],
    )

    with pytest.raises(ExcelImportRowError, match="媒体名称（中文）不能为空") as exc_info:
        convert_supported_platforms(
            input_paths=(source,),
            input_root=tmp_path,
            output_path=tmp_path / "canonical.jsonl",
            profile_name=PROFILE,
            sheet_name="文章",
            observed_at=datetime(2026, 9, 12, 0, 0, tzinfo=UTC),
        )

    assert exc_info.value.code == "platform_missing"
    assert not (tmp_path / "canonical.jsonl").exists()


def test_process_directory_filters_and_deduplicates_across_files(tmp_path: Path) -> None:
    """真实目录入口应完成同名文件追踪、关键词 OR 过滤和跨文件去重。"""

    input_dir = tmp_path / "input"
    first = input_dir / "2026-06-14" / "data.xlsx"
    second = input_dir / "2026-06-15" / "data.xlsx"
    duplicate_url = "https://www.xiaohongshu.com/explore/shared-note"
    _write_workbook(
        first,
        [
            _row(
                media_name="小红书",
                article_id="first-source-id",
                title="爱玛元宇宙体验",
                text="正文",
                url=duplicate_url,
            ),
            _row(
                media_name="微信",
                article_id="wechat-id",
                title="爱玛但不是目标平台",
                text="正文",
                url="https://example.com/wechat",
            ),
        ],
    )
    _write_workbook(
        second,
        [
            _row(
                media_name="小红书",
                article_id="second-source-id",
                title="爱玛元宇宙体验",
                text="正文",
                url=duplicate_url,
            ),
            _row(
                media_name="抖音",
                article_id="douyin-id",
                title="与目标无关",
                text="普通正文",
                url="https://www.douyin.com/video/9876543210123456789",
            ),
        ],
    )
    keyword_pack = tmp_path / "keyword_pack.txt"
    keyword_pack.write_text("# 品牌和车型\n爱玛\n元宇宙\n", encoding="utf-8")

    summary = process_directory(
        input_dir=input_dir,
        output_root=tmp_path / "output",
        keyword_pack_file=keyword_pack,
        sheet_name="文章",
        run_id="case-001",
    )

    assert summary.input_file_count == 2
    assert summary.rows_seen == 4
    assert summary.rows_supported_platform == 3
    assert summary.rows_skipped_platform_unmapped == 1
    assert summary.rows_keyword_matched == 2
    assert summary.rows_keyword_filtered_out == 1
    assert summary.rows_after_deduplication == 1
    assert summary.duplicates_removed == 1
    assert summary.skipped_media_names == {"微信": 1}
    assert [item.source for item in summary.files] == [
        "2026-06-14/data.xlsx",
        "2026-06-15/data.xlsx",
    ]
    assert summary.rows_seen == (
        summary.rows_supported_platform + summary.rows_skipped_platform_unmapped
    )
    assert summary.rows_keyword_matched == (
        summary.rows_after_deduplication + summary.duplicates_removed
    )

    canonical_records = [
        CanonicalContentV1.model_validate_json(line)
        for line in _read_non_empty_lines(summary.canonical_path)
    ]
    assert [record.source.source_value for record in canonical_records] == [
        "2026-06-14/data.xlsx",
        "2026-06-15/data.xlsx",
        "2026-06-15/data.xlsx",
    ]

    final_lines = _read_non_empty_lines(summary.deduplicated_path)
    assert len(final_lines) == 1
    record = UnifiedContentRecordV1.model_validate_json(final_lines[0])
    assert record.content.platform == "xiaohongshu"
    assert record.content.external_content_id == "shared-note"
    assert set(record.matched_keywords) == {"爱玛", "元宇宙"}

    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "monitoring-excel-filter-run.v2"
    assert payload["rows_seen"] == 4
    assert payload["rows_supported_platform"] == 3
    assert payload["rows_skipped_platform_unmapped"] == 1
    assert payload["rows_keyword_matched"] == 2
    assert payload["rows_after_deduplication"] == 1
    assert payload["duplicates_removed"] == 1
    assert len(payload["files"]) == 2
