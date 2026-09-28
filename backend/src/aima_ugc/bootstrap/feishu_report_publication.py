"""正式报告生成与飞书发布用例。"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from aima_ugc.adapters.feishu import (
    FeishuPublicationCheckpointStore,
    FeishuPublicationSummary,
    FeishuReportPublisher,
    FeishuReportPublisherConfig,
    FeishuSyncSummary,
    load_feishu_report_publisher_config,
)
from aima_ugc.bootstrap.representative_report_pipeline import prepare_representative_report
from aima_ugc.bootstrap.representative_selection_publication import (
    build_selected_representative_rows,
    publish_representative_rows_to_feishu,
)
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.reporting import ReportGenerationSummary, generate_excel_report
from aima_ugc.platform.time import beijing_now


class FeishuReportPublicationConfigurationError(RuntimeError):
    """报告发布所需的飞书配置不可用。"""

    def __init__(self, missing: tuple[str, ...] = ()) -> None:
        self.missing = missing
        super().__init__("飞书报告发布配置不可用")


class FeishuReportPublicationSnapshotMismatch(RuntimeError):
    """重试时本地生成结果与首次外部发布输入不一致。"""


@dataclass(frozen=True, slots=True)
class FeishuReportPublicationResult:
    """报告生成和飞书发布的安全结果。"""

    report: ReportGenerationSummary
    publication: FeishuPublicationSummary | None
    representative_sync: FeishuSyncSummary | None = None
    dry_run: bool = False
    representative_count: int = 0


def publish_report_to_feishu(
    *,
    input_path: Path,
    previous_input_path: Path,
    output_dir: Path,
    report_date_range: tuple[date, date],
    settings: PlatformSettings,
    environ: Mapping[str, str] | None = None,
    embed_representative_bitable: bool = False,
    idempotency_key: str | None = None,
    checkpoint: FeishuPublicationCheckpointStore | None = None,
) -> FeishuReportPublicationResult:
    """从两份上传 Excel 生成本期报告并发布到飞书。"""

    if report_date_range[0] > report_date_range[1]:
        raise ValueError("报告开始日期不能晚于结束日期")
    source = Path(input_path)
    previous = Path(previous_input_path)
    actual_environment = dict(os.environ if environ is None else environ)
    publisher_config = _load_publisher_config(settings, actual_environment)

    report = generate_excel_report(
        input_path=source,
        previous_input_path=previous,
        output_dir=Path(output_dir),
        report_date_range=report_date_range,
        chart_workbook_name="report-charts.xlsx",
    )
    if idempotency_key is None and checkpoint is None:
        publication = _publish_generated_report(
            report,
            publisher_config,
            embed_representative_bitable=embed_representative_bitable,
        )
    else:
        publication = _publish_generated_report(
            report,
            publisher_config,
            embed_representative_bitable=embed_representative_bitable,
            idempotency_key=idempotency_key,
            checkpoint=checkpoint,
        )
    return FeishuReportPublicationResult(report=report, publication=publication)


def publish_all_report_to_feishu(
    *,
    input_path: Path,
    previous_input_path: Path,
    output_dir: Path,
    report_date_range: tuple[date, date],
    settings: PlatformSettings,
    environ: Mapping[str, str] | None = None,
    dry_run: bool = False,
    progress: Callable[[int], None] | None = None,
    idempotency_key: str | None = None,
    checkpoint: FeishuPublicationCheckpointStore | None = None,
) -> FeishuReportPublicationResult:
    """执行网页按钮对应的完整 ``generate_report.py --publish-all`` 流程。

    Dry Run 仍执行代表性筛选、行动建议和报告生成，但不调用任何飞书写入接口，
    也不产生伪造的飞书链接。
    """

    if report_date_range[0] > report_date_range[1]:
        raise ValueError("报告开始日期不能晚于结束日期")
    source = Path(input_path)
    previous = Path(previous_input_path)
    target = Path(output_dir)
    actual_environment = dict(os.environ if environ is None else environ)
    publisher_config = None if dry_run else _load_publisher_config(settings, actual_environment)

    generated_at = _publication_generated_at(checkpoint) if not dry_run else None

    preparation = prepare_representative_report(
        input_path=source,
        output_dir=target / "representative_selection",
        settings=settings,
        environment=actual_environment,
        progress=progress,
    )
    if progress is not None:
        progress(40)
    report = generate_excel_report(
        input_path=source,
        previous_input_path=previous,
        output_dir=target,
        report_date_range=report_date_range,
        chart_workbook_name="report-charts.xlsx",
        generated_at=generated_at,
        representative_rows=preparation.rows,
    )
    if progress is not None:
        progress(60)

    if dry_run:
        if progress is not None:
            progress(100)
        return FeishuReportPublicationResult(
            report=report,
            publication=None,
            dry_run=True,
            representative_sync=None,
            representative_count=len(preparation.rows),
        )

    representative_rows = build_selected_representative_rows(
        preparation.selection_run.selected,
        report_rows=preparation.rows,
    )
    if checkpoint is not None:
        current_digest = _prepared_publication_digest(report, representative_rows)
        frozen_digest = checkpoint.get("prepared_publication_digest")
        if frozen_digest is None:
            checkpoint.set("prepared_publication_digest", current_digest)
        elif not isinstance(frozen_digest, str) or frozen_digest != current_digest:
            raise FeishuReportPublicationSnapshotMismatch(
                "报告重试的本地生成结果与首次外部发布输入不一致，已停止继续写飞书"
            )

    assert publisher_config is not None
    if idempotency_key is None and checkpoint is None:
        publication = _publish_generated_report(
            report,
            publisher_config,
            embed_representative_bitable=True,
        )
    else:
        publication = _publish_generated_report(
            report,
            publisher_config,
            embed_representative_bitable=True,
            idempotency_key=idempotency_key,
            checkpoint=checkpoint,
        )
    embedded_token = publication.representative_bitable_token
    if embedded_token is None:
        raise RuntimeError("飞书在线报告未返回内嵌多维表 token")
    if progress is not None:
        progress(82)
    representative_sync = publish_representative_rows_to_feishu(
        rows=representative_rows,
        output_dir=target / "representative_selection",
        settings=settings,
        target_bitable_block_token=embedded_token,
        target_document_token=publication.native_document_token,
        target_document_url=publication.native_document_url,
        idempotency_key=idempotency_key,
        checkpoint=checkpoint,
    )
    if progress is not None:
        progress(100)
    return FeishuReportPublicationResult(
        report=report,
        publication=publication,
        representative_sync=representative_sync,
        representative_count=len(preparation.rows),
    )


def _publication_generated_at(
    checkpoint: FeishuPublicationCheckpointStore | None,
) -> datetime | None:
    """为真实发布冻结一次人类可见生成时间，使重试不会只因时钟变化而漂移。"""

    if checkpoint is None:
        return None
    value = checkpoint.get("prepared_generated_at")
    if value is None:
        generated_at = beijing_now()
        checkpoint.set("prepared_generated_at", generated_at.isoformat())
        return generated_at
    if not isinstance(value, str):
        raise FeishuReportPublicationSnapshotMismatch("报告生成时间 checkpoint 数据损坏")
    try:
        generated_at = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FeishuReportPublicationSnapshotMismatch("报告生成时间 checkpoint 数据损坏") from exc
    if generated_at.utcoffset() is None:
        raise FeishuReportPublicationSnapshotMismatch("报告生成时间 checkpoint 缺少时区")
    return generated_at


def _prepared_publication_digest(
    report: ReportGenerationSummary,
    representative_rows: tuple[dict[str, object], ...],
) -> str:
    """摘要首次外部发布的语义输入，忽略 DOCX/XLSX 包内非确定时间元数据。"""

    digest = hashlib.sha256()
    markdown_path = Path(report.markdown_path)
    if not markdown_path.is_file():
        raise FileNotFoundError(markdown_path)
    digest.update(b"markdown")
    digest.update(hashlib.sha256(markdown_path.read_bytes()).digest())
    digest.update(b"chart-specs")
    digest.update(
        json.dumps(
            [asdict(spec) for spec in report.chart_specs],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )

    normalized_rows: list[dict[str, object]] = []
    for row in representative_rows:
        normalized: dict[str, object] = {}
        for key, value in row.items():
            if isinstance(value, Path):
                if not value.is_file():
                    raise FileNotFoundError(value)
                normalized[key] = {
                    "name": value.name,
                    "sha256": hashlib.sha256(value.read_bytes()).hexdigest(),
                }
            else:
                normalized[key] = value
        normalized_rows.append(normalized)
    digest.update(
        json.dumps(
            normalized_rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    )
    return digest.hexdigest()


def _load_publisher_config(
    settings: PlatformSettings,
    environ: Mapping[str, str],
) -> FeishuReportPublisherConfig:
    try:
        publisher_config = load_feishu_report_publisher_config(
            environ,
            secret_root=settings.external_secret_root,
        )
    except (OSError, ValueError) as exc:
        raise FeishuReportPublicationConfigurationError from exc
    if publisher_config is None:
        raise FeishuReportPublicationConfigurationError(
            ("AIMA_FEISHU_REPORT_ENABLED", "AIMA_FEISHU_FOLDER_TOKEN")
        )
    return publisher_config


def _publish_generated_report(
    report: ReportGenerationSummary,
    publisher_config: FeishuReportPublisherConfig,
    *,
    embed_representative_bitable: bool,
    idempotency_key: str | None = None,
    checkpoint: FeishuPublicationCheckpointStore | None = None,
) -> FeishuPublicationSummary:
    publisher = FeishuReportPublisher(publisher_config)
    if idempotency_key is None and checkpoint is None:
        publication = publisher.publish(
            word_path=report.word_path,
            markdown_path=report.markdown_path,
            chart_specs=report.chart_specs,
            chart_workbook_path=report.chart_workbook_path,
            title="AIMA 舆情报告",
            embed_representative_bitable=embed_representative_bitable,
        )
    else:
        publication = publisher.publish(
            word_path=report.word_path,
            markdown_path=report.markdown_path,
            chart_specs=report.chart_specs,
            chart_workbook_path=report.chart_workbook_path,
            title="AIMA 舆情报告",
            embed_representative_bitable=embed_representative_bitable,
            idempotency_key=idempotency_key,
            checkpoint=checkpoint,
        )
    chart_workbook_path = report.chart_workbook_path
    if (
        chart_workbook_path is not None
        and chart_workbook_path.name == "report-charts.xlsx"
        and chart_workbook_path.parent == report.word_path.parent
    ):
        chart_workbook_path.unlink(missing_ok=True)
    return publication


__all__ = [
    "FeishuReportPublicationConfigurationError",
    "FeishuReportPublicationResult",
    "FeishuReportPublicationSnapshotMismatch",
    "publish_all_report_to_feishu",
    "publish_report_to_feishu",
]
