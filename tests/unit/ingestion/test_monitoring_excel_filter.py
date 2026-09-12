"""监测 Excel 目录批量过滤工具回归测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

from aima_ugc.adapters.providers.imports_test.monitoring_excel_filter.process_directory import (
    convert_supported_platforms,
    discover_input_files,
    process_directory,
)
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1

_HEADERS = (
    "序号",
    "监测项名称",
    "文章编号",
    "标题",
    "内文",
    "媒体名称（中文）",
    "版面",
    "出版日期",
    "媒体类型",
    "作者",
    "全文情感",
    "原文链接",
    "粉丝数",
)


def _write_workbook(path: Path, rows: list[tuple[object, ...]]) -> None:
    """创建与 AIMA Monitoring Excel Profile 兼容的最小 XLSX。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "文章"
    worksheet.append(_HEADERS)
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()


def _row(
    *,
    sequence: int,
    article_id: str,
    title: str,
    text: str,
    media_name: object,
    published_at: str,
    author: str,
    url: str,
) -> tuple[object, ...]:
    """构造一条稳定、可读的监测 Excel 测试行。"""

    return (
        sequence,
        "友商新闻",
        article_id,
        title,
        text,
        media_name,
        "",
        published_at,
        "测试媒体",
        author,
        "中性",
        url,
        100,
    )


def _read_jsonl(path: Path) -> list[bytes]:
    """读取测试生成的 JSONL 非空行。"""

    return [line for line in path.read_bytes().splitlines() if line.strip()]


def test_discover_input_files_recurses_and_ignores_non_inputs(tmp_path: Path) -> None:
    """目录发现应递归读取 XLSX，并忽略临时文件和其他扩展名。"""

    (tmp_path / "2026-04").mkdir()
    (tmp_path / "2026-03").mkdir()
    (tmp_path / "2026-04" / "2026-04-01.xlsx").write_bytes(b"")
    (tmp_path / "2026-03" / "2026-03-01.XLSX").write_bytes(b"")
    (tmp_path / "~$2026-03-02.xlsx").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    discovered = discover_input_files(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in discovered] == [
        "2026-03/2026-03-01.XLSX",
        "2026-04/2026-04-01.xlsx",
    ]


def test_discover_input_files_rejects_empty_directory(tmp_path: Path) -> None:
    """没有 XLSX 时应明确失败，而不是发布空结果。"""

    with pytest.raises(FileNotFoundError, match="未发现 .xlsx"):
        discover_input_files(tmp_path)


def test_convert_supported_platforms_skips_only_unmapped_and_keeps_relative_source(
    tmp_path: Path,
) -> None:
    """五平台应映射为 Canonical，非五平台跳过且同名文件仍可追溯。"""

    input_root = tmp_path / "input"
    first = input_root / "a" / "same.xlsx"
    second = input_root / "b" / "same.xlsx"
    _write_workbook(
        first,
        [
            _row(
                sequence=1,
                article_id="source-1",
                title="爱玛体验",
                text="正文",
                media_name="小红书",
                published_at="2026-06-15 10:00:00",
                author="用户A",
                url="https://www.xiaohongshu.com/explore/note-a",
            ),
            _row(
                sequence=2,
                article_id="source-wechat-1",
                title="微信内容",
                text="正文",
                media_name="微信",
                published_at="2026-06-15 11:00:00",
                author="媒体A",
                url="https://example.com/wechat/1",
            ),
        ],
    )
    _write_workbook(
        second,
        [
            _row(
                sequence=1,
                article_id="source-2",
                title="九号 Q3",
                text="正文",
                media_name="抖音",
                published_at="2026-06-16 10:00:00",
                author="用户B",
                url="https://www.douyin.com/video/123456",
            ),
            _row(
                sequence=2,
                article_id="source-wechat-2",
                title="另一条微信内容",
                text="正文",
                media_name="微信",
                published_at="2026-06-16 11:00:00",
                author="媒体B",
                url="https://example.com/wechat/2",
            ),
        ],
    )

    input_paths = discover_input_files(input_root)
    output_path = tmp_path / "canonical" / "contents.jsonl"
    summary = convert_supported_platforms(
        input_paths=input_paths,
        input_root=input_root,
        output_path=output_path,
        observed_at=datetime(2026, 6, 17, tzinfo=UTC),
    )

    records = [CanonicalContentV1.model_validate_json(line) for line in _read_jsonl(output_path)]
    assert summary.rows_seen == 4
    assert summary.rows_supported_platform == 2
    assert summary.rows_skipped_platform_unmapped == 2
    assert summary.skipped_media_names == (("微信", 2),)
    assert [record.source.source_value for record in records] == ["a/same.xlsx", "b/same.xlsx"]
    assert [record.platform for record in records] == ["xiaohongshu", "douyin"]


def test_convert_supported_platforms_does_not_swallow_target_data_errors(
    tmp_path: Path,
) -> None:
    """除 platform_unmapped 外的 Mapper 错误必须继续 fail closed。"""

    input_root = tmp_path / "input"
    source = input_root / "invalid.xlsx"
    _write_workbook(
        source,
        [
            _row(
                sequence=1,
                article_id="source-1",
                title="缺平台",
                text="正文",
                media_name=None,
                published_at="2026-06-15 10:00:00",
                author="用户A",
                url="https://www.xiaohongshu.com/explore/note-a",
            )
        ],
    )

    with pytest.raises(ValueError, match=r"\[platform_missing\]"):
        convert_supported_platforms(
            input_paths=(source,),
            input_root=input_root,
            output_path=tmp_path / "canonical" / "contents.jsonl",
            observed_at=datetime(2026, 6, 17, tzinfo=UTC),
        )

    assert not (tmp_path / "canonical" / "contents.jsonl").exists()


def test_process_directory_filters_or_deduplicates_and_writes_summary(tmp_path: Path) -> None:
    """完整入口应按任意关键词 OR 过滤，并跨文件统一去重、输出可对账摘要。"""

    input_root = tmp_path / "input"
    first = input_root / "2026-06-15_a.xlsx"
    second = input_root / "nested" / "2026-06-16_b.xlsx"
    _write_workbook(
        first,
        [
            _row(
                sequence=1,
                article_id="source-1",
                title="爱玛通勤体验",
                text="正文",
                media_name="小红书",
                published_at="2026-06-15 10:00:00",
                author="用户A",
                url="https://www.xiaohongshu.com/explore/note-1",
            ),
            _row(
                sequence=2,
                article_id="source-2",
                title="普通骑行内容",
                text="完全无关",
                media_name="小红书",
                published_at="2026-06-15 11:00:00",
                author="用户B",
                url="https://www.xiaohongshu.com/explore/note-2",
            ),
            _row(
                sequence=3,
                article_id="source-wechat",
                title="爱玛微信新闻",
                text="正文",
                media_name="微信",
                published_at="2026-06-15 12:00:00",
                author="媒体A",
                url="https://example.com/wechat",
            ),
        ],
    )
    _write_workbook(
        second,
        [
            _row(
                sequence=1,
                article_id="source-1",
                title="爱玛通勤体验",
                text="正文",
                media_name="小红书",
                published_at="2026-06-15 10:00:00",
                author="用户A",
                url="https://www.xiaohongshu.com/explore/note-1",
            ),
            _row(
                sequence=2,
                article_id="source-3",
                title="日常试驾",
                text="九号 Q3 骑行感受",
                media_name="抖音",
                published_at="2026-06-16 10:00:00",
                author="用户C",
                url="https://www.douyin.com/video/123456",
            ),
        ],
    )
    keyword_pack = tmp_path / "keyword_pack.txt"
    keyword_pack.write_text("爱玛\nQ3\n", encoding="utf-8")

    result = process_directory(
        input_dir=input_root,
        output_root=tmp_path / "output",
        keyword_pack_file=keyword_pack,
        run_id="test-run",
        observed_at=datetime(2026, 6, 17, tzinfo=UTC),
    )

    canonical_lines = _read_jsonl(result.canonical_path)
    filtered_records = [
        UnifiedContentRecordV1.model_validate_json(line)
        for line in _read_jsonl(result.filtered_path)
    ]
    final_records = [
        UnifiedContentRecordV1.model_validate_json(line)
        for line in _read_jsonl(result.deduplicated_path)
    ]
    payload = json.loads(result.run_summary_path.read_text(encoding="utf-8"))

    assert len(canonical_lines) == 4
    assert len(filtered_records) == 3
    assert len(final_records) == 2
    assert {tuple(record.matched_keywords) for record in final_records} == {("爱玛",), ("Q3",)}
    assert payload["input_file_count"] == 2
    assert payload["keyword_count"] == 2
    assert payload["rows_seen"] == 5
    assert payload["rows_supported_platform"] == 4
    assert payload["rows_skipped_platform_unmapped"] == 1
    assert payload["rows_keyword_matched"] == 3
    assert payload["rows_keyword_filtered_out"] == 1
    assert payload["rows_after_deduplication"] == 2
    assert payload["duplicates_removed"] == 1
    assert payload["deduplication_conflicts"] == 1
    assert payload["skipped_media_names"] == {"微信": 1}
    assert result.deduplication_conflicts_path.is_file()
