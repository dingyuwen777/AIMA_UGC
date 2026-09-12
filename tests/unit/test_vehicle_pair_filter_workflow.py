"""验证第一阶段宽筛输出可直接作为车型共现二次筛选输入。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from aima_ugc.adapters.providers.imports_test.monitoring_excel_filter.process_directory import (
    process_directory as process_monitoring_directory,
)
from aima_ugc.adapters.providers.imports_test.vehicle_pair_filter.filter_vehicle_pairs import (
    VehiclePairRecordV1,
    filter_vehicle_pairs,
)
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


def _write_monitoring_workbook(path: Path) -> None:
    """生成可同时穿过第一阶段 Mapper 与第二阶段车型共现规则的真实 XLSX。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "文章"
    worksheet.append(list(_HEADERS))
    rows = (
        (
            "小红书",
            "source-a",
            "元宇宙实际体验",
            "Q3也试过，骑感不同",
            "测试作者",
            datetime(2026, 6, 15, 12, 0),
            "https://www.xiaohongshu.com/explore/pair-note-001",
            100,
        ),
        (
            "小红书",
            "source-b",
            "元宇宙单车体验",
            "这里只聊一款车",
            "测试作者",
            datetime(2026, 6, 15, 12, 1),
            "https://www.xiaohongshu.com/explore/target-only-002",
            100,
        ),
        (
            "小红书",
            "source-c",
            "Q3单车体验",
            "这里只聊一款竞品车",
            "测试作者",
            datetime(2026, 6, 15, 12, 2),
            "https://www.xiaohongshu.com/explore/competitor-only-003",
            100,
        ),
        (
            "微信",
            "source-d",
            "元宇宙和Q3",
            "非目标平台即使命中车型也应在第一阶段被跳过",
            "测试作者",
            datetime(2026, 6, 15, 12, 3),
            "https://example.com/not-target-platform",
            100,
        ),
    )
    for row in rows:
        worksheet.append(list(row))
    workbook.save(path)
    workbook.close()


def _write_vehicle_catalog(path: Path) -> None:
    """写入本工作流测试需要的最小爱玛/九号车型目录。"""

    path.write_text(
        json.dumps(
            {
                "schema_version": "vehicle-pair-catalog.v1",
                "target_brand": "爱玛",
                "brands": [
                    {"name": "爱玛", "models": [{"name": "元宇宙", "aliases": []}]},
                    {"name": "九号", "models": [{"name": "Q3", "aliases": []}]},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_vehicle_pair_filter_consumes_monitoring_excel_filter_output(tmp_path: Path) -> None:
    """Runner 应真实执行 Excel → 第一阶段 deduplicated JSONL → 第二阶段共现 JSONL。"""

    input_dir = tmp_path / "input"
    _write_monitoring_workbook(input_dir / "2026-06-15_sample.xlsx")
    first_keyword_pack = tmp_path / "first_keyword_pack.txt"
    first_keyword_pack.write_text("爱玛\n元宇宙\n九号\nQ3\n", encoding="utf-8")

    first = process_monitoring_directory(
        input_dir=input_dir,
        output_root=tmp_path / "monitoring-output",
        keyword_pack_file=first_keyword_pack,
        sheet_name="文章",
        run_id="stage-one",
    )

    assert first.rows_seen == 4
    assert first.rows_supported_platform == 3
    assert first.rows_skipped_platform_unmapped == 1
    assert first.rows_after_deduplication == 3
    assert first.deduplicated_path.is_file()

    catalog_path = tmp_path / "vehicle_catalog.json"
    _write_vehicle_catalog(catalog_path)
    second = filter_vehicle_pairs(
        input_path=first.deduplicated_path,
        catalog_path=catalog_path,
        output_root=tmp_path / "pair-output",
        run_id="stage-two",
    )

    assert second.rows_seen == 3
    assert second.rows_with_target_model == 2
    assert second.rows_with_competitor_model == 2
    assert second.rows_with_cross_brand_pair == 1
    assert second.rows_filtered_out == 2

    lines = [line for line in second.output_path.read_bytes().splitlines() if line.strip()]
    assert len(lines) == 1
    output = VehiclePairRecordV1.model_validate_json(lines[0])
    assert output.record.content.external_content_id == "pair-note-001"
    assert output.matched_target_models == ("元宇宙",)
    assert [(item.brand, item.model) for item in output.matched_competitor_models] == [
        ("九号", "Q3")
    ]
    assert [
        (item.target_model, item.competitor_brand, item.competitor_model)
        for item in output.matched_pairs
    ] == [("元宇宙", "九号", "Q3")]
