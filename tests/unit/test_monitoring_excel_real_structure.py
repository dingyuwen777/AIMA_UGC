"""基于真实监测导出结构验证目录过滤工具。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from aima_ugc.adapters.providers.imports_test.monitoring_excel_filter.process_directory import (
    process_directory,
)
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from openpyxl import Workbook

_REAL_HEADERS = (
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


def _real_row(
    *,
    sequence: int,
    article_id: str,
    title: str,
    text: str,
    media_name: str,
    url: str,
) -> tuple[object, ...]:
    """按真实 13 列监测导出结构构造一行数据。"""

    return (
        sequence,
        "友商新闻",
        article_id,
        title,
        text,
        media_name,
        "",
        "2026-06-15 12:30:00",
        "网媒",
        "测试作者",
        "中性",
        url,
        100,
    )


def _write_real_structure_workbook(path: Path) -> None:
    """生成覆盖五个平台、非目标平台和跨行正文的真实结构 XLSX。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    duplicate_url = "https://www.xiaohongshu.com/explore/real-note-001"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "文章"
    worksheet.append(list(_REAL_HEADERS))
    rows = [
        _real_row(
            sequence=1,
            article_id="source-1",
            title="爱\u00a0玛 元宇宙体验",
            text="第一行正文\n第二行正文",
            media_name="小红书",
            url=duplicate_url,
        ),
        _real_row(
            sequence=2,
            article_id="source-2",
            title="普通骑行",
            text="正文提到 Q3 车型",
            media_name="抖音",
            url="https://www.douyin.com/video/1234567890123456789",
        ),
        _real_row(
            sequence=3,
            article_id="source-3",
            title="普通内容",
            text="与词包无关",
            media_name="新浪微博",
            url="https://example.com/source/3",
        ),
        _real_row(
            sequence=4,
            article_id="source-4",
            title="普通内容",
            text="与词包无关",
            media_name="哔哩哔哩",
            url="https://example.com/source/4",
        ),
        _real_row(
            sequence=5,
            article_id="source-5",
            title="普通内容",
            text="与词包无关",
            media_name="快手",
            url="https://example.com/source/5",
        ),
        _real_row(
            sequence=6,
            article_id="source-6",
            title="爱玛微信新闻",
            text="即使命中关键词也不是目标平台",
            media_name="微信",
            url="https://example.com/source/6",
        ),
        _real_row(
            sequence=7,
            article_id="source-7",
            title="爱玛 元宇宙体验",
            text="重复内容",
            media_name="小红书",
            url=duplicate_url,
        ),
    ]
    for row in rows:
        worksheet.append(list(row))
    workbook.save(path)
    workbook.close()


def _rewrite_dimension_as_a1(path: Path) -> None:
    """复现真实来源把 worksheet dimension 错写为 ``A1`` 的结构异常。"""

    replacement = path.with_name(f".{path.name}.dimension-a1.tmp")
    changed = False
    with ZipFile(path, "r") as source_archive, ZipFile(
        replacement, "w", compression=ZIP_DEFLATED
    ) as target_archive:
        for item in source_archive.infolist():
            payload = source_archive.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                payload, replacements = re.subn(
                    br'<dimension ref="[^"]+"\s*/>',
                    b'<dimension ref="A1"/>',
                    payload,
                    count=1,
                )
                changed = replacements == 1
            target_archive.writestr(item, payload)
    if not changed:
        replacement.unlink(missing_ok=True)
        raise AssertionError("测试 Fixture 未找到 worksheet dimension")
    replacement.replace(path)


def _read_final_records(path: Path) -> list[UnifiedContentRecordV1]:
    """读取最终 JSONL 并按正式 Contract 校验。"""

    return [
        UnifiedContentRecordV1.model_validate_json(line)
        for line in path.read_bytes().splitlines()
        if line.strip()
    ]


def test_real_monitoring_structure_with_broken_dimension_runs_end_to_end(tmp_path: Path) -> None:
    """真实监测结构即使 dimension=A1，也应完成自动发现、过滤、去重与对账。"""

    input_dir = tmp_path / "input"
    source = input_dir / "2026-06-15_公司品牌_友商新闻.xlsx"
    _write_real_structure_workbook(source)
    _rewrite_dimension_as_a1(source)
    keyword_pack = tmp_path / "keyword_pack.txt"
    keyword_pack.write_text("爱玛\nQ3\n", encoding="utf-8")

    summary = process_directory(
        input_dir=input_dir,
        output_root=tmp_path / "output",
        keyword_pack_file=keyword_pack,
        sheet_name=None,
        run_id="real-structure-a1",
    )

    assert summary.input_file_count == 1
    assert summary.rows_seen == 7
    assert summary.rows_supported_platform == 6
    assert summary.rows_skipped_platform_unmapped == 1
    assert summary.rows_keyword_matched == 3
    assert summary.rows_keyword_filtered_out == 3
    assert summary.rows_after_deduplication == 2
    assert summary.duplicates_removed == 1
    assert summary.skipped_media_names == {"微信": 1}

    records = _read_final_records(summary.deduplicated_path)
    assert [record.content.platform for record in records] == ["xiaohongshu", "douyin"]
    assert [record.content.external_content_id for record in records] == [
        "real-note-001",
        "1234567890123456789",
    ]
    assert [tuple(record.matched_keywords) for record in records] == [("爱玛",), ("Q3",)]

    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["rows_seen"] == (
        payload["rows_supported_platform"] + payload["rows_skipped_platform_unmapped"]
    )
    assert payload["rows_keyword_matched"] == (
        payload["rows_after_deduplication"] + payload["duplicates_removed"]
    )
