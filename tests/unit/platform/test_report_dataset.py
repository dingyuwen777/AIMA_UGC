"""数据库报告遵循平台身份及真实用户统计范围。"""

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aima_ugc.contracts.export import (
    UnifiedDataExcelAnalysisV1,
    UnifiedDataExcelCommentV1,
    UnifiedDataExcelContentV1,
    UnifiedDataExcelLabelPairV1,
    UnifiedDataExcelV1,
)
from aima_ugc.platform.reporting.excel_report import generate_dataset_report


def test_same_external_id_on_two_platforms_keeps_distinct_sentiment_scope(tmp_path: Path) -> None:
    """商业内容与真实用户即使外部ID相同，也不能污染用户议题与情感。"""
    current = []
    for platform, voice, sentiment in (
        ("douyin", "真实用户发声", "正面"),
        ("xiaohongshu", "商业营销发声", "负面"),
    ):
        current.append(
            UnifiedDataExcelV1(
                content=UnifiedDataExcelContentV1(
                    platform=platform,
                    external_content_id="same-external-id",
                    published_at=datetime(2026, 8, 20, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
                    analysis=UnifiedDataExcelAnalysisV1(
                        voice_type=voice,
                        sentiment=sentiment,
                        primary_label="品牌评价",
                        secondary_label="口碑与信任",
                        label_pairs=(
                            UnifiedDataExcelLabelPairV1(
                                primary_label="品牌评价", secondary_label="口碑与信任"
                            ),
                        ),
                    ),
                ),
                comments=(
                    UnifiedDataExcelCommentV1(
                        platform=platform,
                        external_content_id="same-external-id",
                        external_comment_id=f"{platform}-comment",
                        level="root",
                        published_at=datetime(2026, 8, 20, 11, tzinfo=ZoneInfo("Asia/Shanghai")),
                    ),
                ),
            )
        )
    result = generate_dataset_report(
        records=current,
        previous_records=(),
        output_dir=tmp_path,
        report_date_range=(date(2026, 8, 20), date(2026, 8, 20)),
    )
    assert result.content_rows == 2
    assert result.comment_rows == 2
    text = result.markdown_path.read_text(encoding="utf-8")
    assert "| 正面 | 1 |" in text
    assert "| 负面内容 | 0（0.00%） |" in text
    assert "| 负面 | 1 |" not in text
