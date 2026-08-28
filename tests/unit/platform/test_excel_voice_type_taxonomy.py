from __future__ import annotations

from pathlib import Path

import pytest
from aima_ugc.contracts.export import (
    UnifiedDataExcelAnalysisV1,
    UnifiedDataExcelContentV1,
    UnifiedDataExcelLabelPairV1,
    UnifiedDataExcelV1,
)
from aima_ugc.platform.export import export_unified_data_excel
from openpyxl import load_workbook


@pytest.mark.parametrize(
    ("voice_type", "expected_display"),
    [
        ("user_voice", "真实用户发声"),
        ("brand_official", "品牌官方发声"),
        ("dealer_promotion", "门店经销商发声"),
        ("creator_marketing", "营销推广发声"),
        ("industry_professional", "行业从业发声"),
        ("media_information", "媒体机构发声"),
        ("unknown", "无法判断"),
        ("other_organization", "其他机构传播"),
        ("future_prompt_voice_type", "future_prompt_voice_type"),
        (None, None),
    ],
)
def test_excel_voice_type_display_does_not_enforce_a_parallel_taxonomy(
    tmp_path: Path,
    voice_type: str | None,
    expected_display: str | None,
) -> None:
    """Excel 只提供中文展示别名，合法 voice_type 集合仍由 Prompt Taxonomy 决定。"""

    output = tmp_path / "voice-type.xlsx"
    label_pair = UnifiedDataExcelLabelPairV1(
        primary_label="测试一级标签",
        secondary_label="测试二级标签",
    )
    record = UnifiedDataExcelV1(
        content=UnifiedDataExcelContentV1(
            platform="xiaohongshu",
            external_content_id="voice-type-taxonomy-export-test",
            analysis=UnifiedDataExcelAnalysisV1(
                voice_type=voice_type,
                primary_label=label_pair.primary_label,
                secondary_label=label_pair.secondary_label,
                label_pairs=(label_pair,),
            ),
        )
    )

    export_unified_data_excel((record,), output, include_analysis=True)

    workbook = load_workbook(output, data_only=False, read_only=True)
    try:
        sheet = workbook["内容"]
        headers = [cell.value for cell in next(sheet.iter_rows(max_row=1))]
        values = [cell.value for cell in next(sheet.iter_rows(min_row=2, max_row=2))]
        assert values[headers.index("发声类型")] == expected_display
    finally:
        workbook.close()
