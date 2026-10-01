"""数据库报告生成与已生成文件发布的正式 Worker 装配。"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any
from uuid import UUID

from aima_ugc.adapters.feishu import FeishuAPIError, FeishuApiError, FeishuSyncError
from aima_ugc.adapters.feishu.report_publisher import FeishuPublicationCheckpointStore
from aima_ugc.adapters.llm import OpenAICompatibleContentLabelingLLM
from aima_ugc.adapters.llm.openai_compatible import OpenAICompatibleLLMError
from aima_ugc.adapters.persistence.postgres.artifact_metadata import PostgresArtifactMetadataGateway
from aima_ugc.adapters.persistence.postgres.report_runs import PostgresReportRepository
from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingLLMPort,
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
    ContentLabelingStopped,
)
from aima_ugc.modules.analysis.representative_advice import validate_report_advice
from aima_ugc.modules.analysis.representative_selection import validate_group_selection
from aima_ugc.modules.reporting.report_jobs import ReportGenerationPayload, ReportPublicationPayload
from aima_ugc.platform.export.excel import export_unified_data_excel
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, LeaseLostError
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.reporting.chart_spec import ChartSpec
from aima_ugc.platform.reporting.excel_report import (
    ReportGenerationSummary,
    generate_dataset_report,
)
from aima_ugc.platform.security import SecretFileError
from aima_ugc.platform.storage import ArtifactService
from aima_ugc.platform.time import beijing_now

from .feishu_bitable_mirror import register_feishu_bitable_mirror
from .feishu_report_publication import (
    FeishuReportPublicationConfigurationError,
    publish_prepared_report_to_feishu,
)
from .representative_report_pipeline import prepare_dataset_representatives
from .representative_selection_publication import build_selected_representative_rows
from .runtime import PlatformRuntime
from .runtime_config import provider_from_safe_snapshot, resolve_provider_secret


class ReportCheckpoint(FeishuPublicationCheckpointStore):
    """每个成功阶段以当前 fence 持久保存，手动恢复也保持同一业务断点。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        report_id: UUID,
        fence: JobExecutionFence,
        kind: str,
        values: dict[str, Any],
    ) -> None:
        self.runtime, self.report_id, self.fence, self.kind = runtime, report_id, fence, kind
        self.values = dict(values)

    def get(self, key: str) -> object | None:
        """读取已经确认的外部结果。"""
        return self.values.get(key)

    def set(self, key: str, value: object | None) -> None:
        """先提交再更新内存，提交失败不能把未确认结果当作成功。"""
        values = {**self.values, key: value}
        with self.runtime.database.new_session() as session, session.begin():
            PostgresReportRepository(session).checkpoint(
                self.report_id, self.fence, kind=self.kind, values=values
            )
        self.values = values


class _CheckpointLLM:
    """请求失败交还 durable Job 做计划退避，成功输出跨尝试复用。"""

    def __init__(
        self,
        inner: ContentLabelingLLMPort,
        checkpoint: ReportCheckpoint,
        context: JobExecutionContextProtocol,
    ) -> None:
        self.inner, self.checkpoint, self.context = inner, checkpoint, context
        self.provider_name, self.model_name = inner.provider_name, inner.model_name

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        """发送前后检查取消与fence，日志只保留安全类别和关联身份。"""
        if self.context.cancel_requested():
            raise ContentLabelingStopped("report_cancelled")
        key = hashlib.sha256(
            json.dumps(
                {"prompt": request.prompt, "items": [asdict(item) for item in request.items]},
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cached = self.checkpoint.get(key)
        if isinstance(cached, str):
            return ContentLabelingLLMResponse(raw_text=cached)
        started = monotonic()
        log_event(
            self.checkpoint.runtime.logger,
            logging.INFO,
            "report.llm.started",
            "报告模型请求开始",
            report_run_id=str(self.checkpoint.report_id),
            job_id=str(self.checkpoint.fence.job_id),
            logical_request_id=key,
            item_count=len(request.items),
            model=self.model_name,
        )
        response = self.inner.complete(replace(request, logical_request_id=key))
        if self.context.cancel_requested():
            raise ContentLabelingStopped("report_cancelled")
        if "selected_item_nos" in request.prompt:
            validate_group_selection(
                response.raw_text,
                expected_item_nos=(item.item_no for item in request.items),
                max_per_group=10,
            )
        else:
            validate_report_advice(
                response.raw_text, expected={item.item_no for item in request.items}
            )
        self.checkpoint.set(key, response.raw_text)
        log_event(
            self.checkpoint.runtime.logger,
            logging.INFO,
            "report.llm.completed",
            "报告模型请求返回",
            report_run_id=str(self.checkpoint.report_id),
            job_id=str(self.checkpoint.fence.job_id),
            logical_request_id=key,
            elapsed_ms=round((monotonic() - started) * 1000),
        )
        return response


class PostgresReportJobExecutor:
    """LLM、文件 I/O 和飞书 I/O 不持数据库事务。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self.runtime = runtime

    def generate(
        self, payload: ReportGenerationPayload, context: JobExecutionContextProtocol
    ) -> JobHandlerResult:
        """从冻结输入生成全部产物，只有完整提交才提供下载。"""
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        report_id, fence = payload.report_run_id, context.fence
        try:
            with self.runtime.database.new_session() as session, session.begin():
                repository = PostgresReportRepository(session)
                row = repository.get(report_id)
                if row["completed_at"]:
                    return JobHandlerResult.succeeded({"report_run_id": str(report_id)})
                records = repository.load_records(report_id, "current")
                previous = repository.load_records(report_id, "previous")
            context.heartbeat(progress=10)
            snapshot = row["snapshot"]
            provider = provider_from_safe_snapshot(snapshot["provider"])
            checkpoint = ReportCheckpoint(
                self.runtime, report_id, fence, "generation", row["generation_checkpoint"]
            )
            root = self.runtime.settings.data_dir / "tmp"
            root.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix=f"report-{report_id}-", dir=root) as directory:
                target = Path(directory)
                prompt = target / "selection.md"
                prompt.write_text(snapshot["selection_prompt_text"], encoding="utf-8")
                template = target / "template.md"
                template.write_text(snapshot["template_text"], encoding="utf-8")
                with OpenAICompatibleContentLabelingLLM(
                    api_key=resolve_provider_secret(self.runtime.settings, provider),
                    model=provider.model or "",
                    provider_name=provider.provider,
                    base_url=provider.base_url,
                    timeout_seconds=snapshot["request_timeout_seconds"],
                    max_connections=1,
                ) as raw_llm:
                    prepared = prepare_dataset_representatives(
                        records=records,
                        prompt_path=prompt,
                        llm=_CheckpointLLM(raw_llm, checkpoint, context),
                        advice_prompt=snapshot["advice_prompt_text"],
                    )
                context.heartbeat(progress=50)
                output = target / "output"
                report = generate_dataset_report(
                    records=records,
                    previous_records=previous,
                    output_dir=output,
                    report_date_range=(row["start_date"], row["end_date"]),
                    template_path=template,
                    generated_at=row["created_at"],
                    representative_rows=prepared.rows,
                )
                context.heartbeat(progress=75)
                excel = output / "report-data.xlsx"
                export_unified_data_excel(
                    records, excel, include_analysis=True, require_complete_analysis=False
                )
                context.heartbeat(progress=85)
                feishu_rows = (
                    build_selected_representative_rows(
                        prepared.selection_run.selected, report_rows=prepared.rows
                    )
                    if prepared.rows
                    else ()
                )
                result = {
                    "representative_rows": list(feishu_rows),
                    "chart_specs": [asdict(spec) for spec in report.chart_specs],
                    "content_rows": report.content_rows,
                    "label_rows": report.label_rows,
                    "comment_rows": report.comment_rows,
                }
                types = {
                    "report.docx": "word_report",
                    "report-data.xlsx": "excel_report",
                    "report.md": "markdown_source",
                    "report-charts.xlsx": "chart_workbook",
                }
                files = []
                artifacts = ArtifactService(
                    metadata=PostgresArtifactMetadataGateway(self.runtime.database.new_session),
                    store=self.runtime.artifact_store,
                )
                for path in sorted(output.rglob("*")):
                    if not path.is_file():
                        continue
                    if context.cancel_requested():
                        return JobHandlerResult.cancelled()
                    relative = path.relative_to(output).as_posix()
                    with path.open("rb") as source:
                        artifact = artifacts.store_stream(
                            kind="report.output",
                            retention_class="report",
                            content_type=mimetypes.guess_type(path.name)[0]
                            or "application/octet-stream",
                            source=source,
                            max_bytes=500 * 1024 * 1024,
                            filename_suffix=path.suffix,
                        )
                    files.append((artifact.id, types.get(relative, "image_asset"), relative))
                with self.runtime.database.new_session() as session, session.begin():
                    PostgresReportRepository(session).complete(
                        report_id,
                        fence,
                        files=tuple(files),
                        result=result,
                        retention_days=snapshot["retention_days"],
                    )
                log_event(
                    self.runtime.logger,
                    logging.INFO,
                    "report.generated",
                    "报告产物已完整提交",
                    report_run_id=str(report_id),
                    job_id=str(fence.job_id),
                    artifact_count=len(files),
                    content_count=len(records),
                )
                return JobHandlerResult.succeeded(
                    {"report_run_id": str(report_id), "artifact_count": len(files)}
                )
        except ContentLabelingStopped:
            return JobHandlerResult.cancelled()
        except LeaseLostError:
            raise
        except OpenAICompatibleLLMError as exc:
            self._failure(report_id, fence, exc.error_code, retry=exc.retryable)
            return (
                JobHandlerResult.retry(exc.error_code)
                if exc.retryable
                else JobHandlerResult.failed(exc.error_code)
            )
        except SecretFileError:
            self._failure(report_id, fence, "report_model_secret_unavailable", retry=False)
            return JobHandlerResult.failed("report_model_secret_unavailable")
        except OSError:
            self._failure(report_id, fence, "report_io_error", retry=True)
            return JobHandlerResult.retry("report_io_error")
        except ValueError:
            self._failure(report_id, fence, "report_data_or_model_output_invalid", retry=False)
            return JobHandlerResult.failed("report_data_or_model_output_invalid")

    def publish(
        self, payload: ReportPublicationPayload, context: JobExecutionContextProtocol
    ) -> JobHandlerResult:
        """只恢复已生成的报告与外部checkpoint，绝不重新调用模型。"""
        report_id, fence = payload.report_run_id, context.fence
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        if self.runtime.settings.feishu_dry_run:
            return JobHandlerResult.failed("report_publication_dry_run")
        try:
            with self.runtime.database.new_session() as session, session.begin():
                repository = PostgresReportRepository(session)
                row = repository.get(report_id)
                files = repository.artifacts(report_id)
            if not row["completed_at"] or row["expires_at"] <= beijing_now():
                return JobHandlerResult.failed("report_expired_or_not_generated")
            root = self.runtime.settings.data_dir / "tmp"
            root.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix=f"publish-{report_id}-", dir=root) as directory:
                output = Path(directory)
                for artifact in files:
                    if context.cancel_requested():
                        return JobHandlerResult.cancelled()
                    if (
                        artifact["storage_status"] != "linked"
                        or artifact["storage_backend"] != self.runtime.artifact_store.backend_name
                    ):
                        return JobHandlerResult.failed("report_artifact_unavailable")
                    relative = Path(artifact["filename"])
                    if relative.is_absolute() or ".." in relative.parts:
                        raise ValueError("报告产物路径不安全")
                    path = output / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("wb") as destination:
                        stored = self.runtime.artifact_store.copy_to(
                            artifact["storage_key"], destination
                        )
                    if stored.sha256 != artifact["sha256"]:
                        raise ValueError("报告产物校验失败")
                result = row["generation_result"]
                charts = tuple(
                    ChartSpec(
                        **{
                            **spec,
                            "categories": tuple(spec["categories"]),
                            "series": tuple(tuple(values) for values in spec["series"]),
                            "series_names": tuple(spec["series_names"]),
                            "pie_labels": tuple(spec["pie_labels"]),
                        }
                    )
                    for spec in result["chart_specs"]
                )
                summary = ReportGenerationSummary(
                    source_excel_path=output / "report-data.xlsx",
                    template_path=output / "report.md",
                    markdown_path=output / "report.md",
                    word_path=output / "report.docx",
                    content_rows=result["content_rows"],
                    label_rows=result["label_rows"],
                    comment_rows=result["comment_rows"],
                    start_date=str(row["start_date"]),
                    end_date=str(row["end_date"]),
                    word_chart_count=len(charts),
                    content_rows_excluded_by_period=0,
                    label_rows_excluded_by_period=0,
                    comment_rows_excluded_by_period=0,
                    chart_workbook_path=output / "report-charts.xlsx"
                    if (output / "report-charts.xlsx").exists()
                    else None,
                    chart_specs=charts,
                )
                checkpoint = ReportCheckpoint(
                    self.runtime, report_id, fence, "publication", row["publication_checkpoint"]
                )

                def before_request() -> None:
                    """每次外部发送前检查取消、deadline和当前执行身份。"""
                    if context.cancel_requested():
                        raise ContentLabelingStopped("report_cancelled")
                    with self.runtime.database.new_session() as session, session.begin():
                        PostgresReportRepository(session).validate_execution(
                            report_id, fence, "publication"
                        )

                published = publish_prepared_report_to_feishu(
                    report=summary,
                    rows=result["representative_rows"],
                    settings=self.runtime.settings,
                    environ=os.environ,
                    checkpoint=checkpoint,
                    idempotency_key=f"report:{report_id}",
                    progress=lambda value: context.heartbeat(progress=value),
                    before_request=before_request,
                    on_representative_sync=lambda sync: register_feishu_bitable_mirror(
                        self.runtime,
                        sync,
                        publication_job_id=fence.job_id,
                        fence=fence,
                    ),
                )
                log_event(
                    self.runtime.logger,
                    logging.INFO,
                    "report.published",
                    "已生成报告完成飞书发布",
                    report_run_id=str(report_id),
                    job_id=str(fence.job_id),
                )
                return JobHandlerResult.succeeded(published)
        except ContentLabelingStopped:
            return JobHandlerResult.cancelled()
        except LeaseLostError:
            raise
        except (FeishuAPIError, FeishuApiError) as exc:
            retry = bool(getattr(exc, "retryable", getattr(exc, "retriable", False)))
            self._failure(report_id, fence, "report_feishu_api_error", retry=retry)
            return (
                JobHandlerResult.retry("report_feishu_api_error")
                if retry
                else JobHandlerResult.failed("report_feishu_api_error")
            )
        except FeishuReportPublicationConfigurationError, SecretFileError:
            self._failure(report_id, fence, "report_feishu_config_unavailable", retry=False)
            return JobHandlerResult.failed("report_feishu_config_unavailable")
        except FeishuSyncError:
            self._failure(report_id, fence, "report_feishu_sync_invalid", retry=False)
            return JobHandlerResult.failed("report_feishu_sync_invalid")
        except OSError:
            self._failure(report_id, fence, "report_publication_io_error", retry=True)
            return JobHandlerResult.retry("report_publication_io_error")
        except ValueError:
            self._failure(report_id, fence, "report_publication_invalid", retry=False)
            return JobHandlerResult.failed("report_publication_invalid")

    def _failure(
        self, report_id: UUID, fence: JobExecutionFence, code: str, *, retry: bool
    ) -> None:
        """不记录凭据、原始响应或用户正文，Job 记录实际退避与耗尽事件。"""
        log_event(
            self.runtime.logger,
            logging.WARNING if retry else logging.ERROR,
            "report.retry_requested" if retry else "report.failed",
            "报告任务请求计划重试" if retry else "报告任务失败",
            report_run_id=str(report_id),
            job_id=str(fence.job_id),
            error_code=code,
            retryable=retry,
        )
