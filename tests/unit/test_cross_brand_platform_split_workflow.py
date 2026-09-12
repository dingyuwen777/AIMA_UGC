"""验证 Excel 到五平台共现文件的三阶段真实文件工作流。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from aima_ugc.adapters.providers.imports_test.cross_brand_platform_split.split_by_platform import (
    split_by_platform,
)
from aima_ugc.adapters.providers.imports_test.monitoring_excel_filter.process_directory import (
    process_directory as process_monitoring_directory,
)
from aima_ugc.adapters.providers.imports_test.vehicle_pair_filter.filter_vehicle_pairs import (
    VehiclePairRecordV1,
    filter_vehicle_pairs,
)
from aima_ugc.contracts.platform import PLATFORM_NAMES
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
    """生成五个平台共现帖、一个目标车型单帖和一个非目标平台帖。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "文章"
    worksheet.append(list(_HEADERS))
    rows = (
        (
            "小红书",
            "xhs-pair",
            "元宇宙实际体验",
            "Q3也试过",
            "测试作者",
            datetime(2026, 6, 15, 12, 0),
            "https://www.xiaohongshu.com/explore/xhs-pair",
            100,
        ),
        (
            "抖音",
            "douyin-pair",
            "墩墩实际体验",
            "莱茵也试过",
            "测试作者",
            datetime(2026, 6, 15, 12, 1),
            "https://www.douyin.com/video/douyin-pair",
            100,
        ),
        (
            "新浪微博",
            "weibo-pair",
            "元宇宙实际体验",
            "Y果冻也试过",
            "测试作者",
            datetime(2026, 6, 15, 12, 2),
            "https://weibo.com/1/weibo-pair",
            100,
        ),
        (
            "哔哩哔哩",
            "bilibili-pair",
            "墩墩实际体验",
            "QZ1也试过",
            "测试作者",
            datetime(2026, 6, 15, 12, 3),
            "https://www.bilibili.com/video/BV1testpair",
            100,
        ),
        (
            "快手",
            "kuaishou-pair",
            "元宇宙实际体验",
            "Mo1也试过",
            "测试作者",
            datetime(2026, 6, 15, 12, 4),
            "https://www.kuaishou.com/short-video/kuaishou-pair",
            100,
        ),
        (
            "小红书",
            "xhs-target-only",
            "元宇宙单车体验",
            "这里只聊一个爱玛车型",
            "测试作者",
            datetime(2026, 6, 15, 12, 5),
            "https://www.xiaohongshu.com/explore/xhs-target-only",
            100,
        ),
        (
            "微信",
            "wechat-pair",
            "元宇宙和Q3",
            "非目标平台应在第一阶段跳过",
            "测试作者",
            datetime(2026, 6, 15, 12, 6),
            "https://example.com/wechat-pair",
            100,
        ),
    )
    for row in rows:
        worksheet.append(list(row))
    workbook.save(path)
    workbook.close()


def _write_vehicle_catalog(path: Path) -> None:
    """写入三阶段工作流需要的爱玛与四个竞品品牌车型目录。"""

    path.write_text(
        json.dumps(
            {
                "schema_version": "vehicle-pair-catalog.v1",
                "target_brand": "爱玛",
                "brands": [
                    {
                        "name": "爱玛",
                        "models": [
                            {"name": "元宇宙", "aliases": []},
                            {"name": "墩墩", "aliases": []},
                        ],
                    },
                    {
                        "name": "雅迪",
                        "models": [{"name": "莱茵", "aliases": []}],
                    },
                    {
                        "name": "九号",
                        "models": [
                            {"name": "Q3", "aliases": []},
                            {"name": "QZ1", "aliases": []},
                        ],
                    },
                    {
                        "name": "小牛",
                        "models": [{"name": "Y果冻", "aliases": []}],
                    },
                    {
                        "name": "极核",
                        "models": [{"name": "Mo1", "aliases": []}],
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_three_stage_workflow_splits_cross_brand_posts_into_five_platform_files(
    tmp_path: Path,
) -> None:
    """Runner 应真实执行 XLSX → 第一阶段 → 第二阶段 → 第三阶段五平台文件。"""

    input_dir = tmp_path / "input"
    _write_monitoring_workbook(input_dir / "2026-06-15_sample.xlsx")
    keyword_pack = tmp_path / "keyword_pack.txt"
    keyword_pack.write_text(
        "元宇宙\n墩墩\nQ3\nQZ1\n莱茵\nY果冻\nMo1\n",
        encoding="utf-8",
    )

    first = process_monitoring_directory(
        input_dir=input_dir,
        output_root=tmp_path / "monitoring-output",
        keyword_pack_file=keyword_pack,
        sheet_name="文章",
        run_id="stage-one",
    )

    assert first.rows_seen == 7
    assert first.rows_supported_platform == 6
    assert first.rows_skipped_platform_unmapped == 1
    assert first.rows_after_deduplication == 6

    catalog_path = tmp_path / "vehicle_catalog.json"
    _write_vehicle_catalog(catalog_path)
    second = filter_vehicle_pairs(
        input_path=first.deduplicated_path,
        catalog_path=catalog_path,
        output_root=tmp_path / "pair-output",
        run_id="stage-two",
    )

    assert second.rows_seen == 6
    assert second.rows_with_cross_brand_pair == 5
    assert second.rows_filtered_out == 1

    third = split_by_platform(
        input_path=second.output_path,
        output_root=tmp_path / "platform-output",
        run_id="stage-three",
    )

    assert third.rows_seen == 5
    assert third.platform_counts == {platform: 1 for platform in PLATFORM_NAMES}
    assert sum(third.platform_counts.values()) == third.rows_seen

    for platform in PLATFORM_NAMES:
        lines = [
            line for line in third.output_paths[platform].read_bytes().splitlines() if line.strip()
        ]
        assert len(lines) == 1
        record = VehiclePairRecordV1.model_validate_json(lines[0])
        assert record.record.content.platform == platform
