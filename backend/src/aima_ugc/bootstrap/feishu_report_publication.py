"""正式报告生成与飞书发布用例。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from aima_ugc.adapters.feishu import (
    FeishuPublicationSummary,
    FeishuReportPublisher,
    load_feishu_report_publisher_config,
)
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.reporting import ReportGenerationSummary, generate_excel_report


class FeishuReportPublicationConfigurationError(RuntimeError):
    """报告发布所需的飞书配置不可用。"""

    def __init__(self, missing: tuple[str, ...] = ()) -> None:
        self.missing = missing
        super().__init__("飞书报告发布配置不可用")


@dataclass(frozen=True, slots=True)
class FeishuReportPublicationResult:
    """报告生成和飞书发布的安全结果。"""

    report: ReportGenerationSummary
    publication: FeishuPublicationSummary


def publish_report_to_feishu(
    *,
    input_path: Path,
    previous_input_path: Path,
    output_dir: Path,
    report_date_range: tuple[date, date],
    settings: PlatformSettings,
    environ: Mapping[str, str] | None = None,
) -> FeishuReportPublicationResult:
    """从两份上传 Excel 生成本期报告并发布到飞书。"""

    if report_date_range[0] > report_date_range[1]:
        raise ValueError("报告开始日期不能晚于结束日期")
    source = Path(input_path)
    previous = Path(previous_input_path)
    actual_environment = dict(os.environ if environ is None else environ)
    try:
        publisher_config = load_feishu_report_publisher_config(
            actual_environment,
            secret_root=settings.external_secret_root,
        )
    except (OSError, ValueError) as exc:
        raise FeishuReportPublicationConfigurationError from exc
    if publisher_config is None:
        raise FeishuReportPublicationConfigurationError(
            ("AIMA_FEISHU_REPORT_ENABLED", "AIMA_FEISHU_FOLDER_TOKEN")
        )

    report = generate_excel_report(
        input_path=source,
        previous_input_path=previous,
        output_dir=Path(output_dir),
        report_date_range=report_date_range,
        chart_workbook_name="report-charts.xlsx",
    )
    publication = FeishuReportPublisher(publisher_config).publish(
        word_path=report.word_path,
        markdown_path=report.markdown_path,
        chart_specs=report.chart_specs,
        chart_workbook_path=report.chart_workbook_path,
        title="AIMA 舆情报告",
    )
    chart_workbook_path = report.chart_workbook_path
    if (
        chart_workbook_path is not None
        and chart_workbook_path.name == "report-charts.xlsx"
        and chart_workbook_path.parent == report.word_path.parent
    ):
        chart_workbook_path.unlink(missing_ok=True)
    return FeishuReportPublicationResult(report=report, publication=publication)


__all__ = [
    "FeishuReportPublicationConfigurationError",
    "FeishuReportPublicationResult",
    "publish_report_to_feishu",
]
