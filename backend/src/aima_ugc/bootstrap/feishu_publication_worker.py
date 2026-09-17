"""管理员飞书发布 Job 的正式 Worker 执行器。"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from aima_ugc.adapters.feishu import FeishuAPIError, FeishuApiError, FeishuSyncError
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.bootstrap.feishu_report_publication import (
    FeishuReportPublicationConfigurationError,
    publish_report_to_feishu,
)
from aima_ugc.bootstrap.representative_selection_publication import (
    RepresentativeSelectionPublicationConfigurationError,
    publish_representative_selection_to_feishu,
)
from aima_ugc.modules.administration.feishu_publication_jobs import (
    FeishuPublicationJobExecutor,
    FeishuReportPublicationJobPayload,
    FeishuRepresentativeSelectionJobPayload,
)
from aima_ugc.modules.ingestion.xlsx_security import validate_xlsx_archive
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol
from aima_ugc.platform.security import SecretFileError

from .runtime import PlatformRuntime


class PostgresFeishuPublicationJobExecutor(FeishuPublicationJobExecutor):
    """从现有 Job Payload 读取上传 Artifact，并执行两个正式发布用例。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def execute_report(
        self,
        *,
        payload: FeishuReportPublicationJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        del fence
        try:
            with self._temporary_directory("feishu-report-") as directory_name:
                directory = Path(directory_name)
                input_path = self._materialize_artifact(
                    payload.input_artifact_id,
                    directory / "current.xlsx",
                )
                previous_path = self._materialize_artifact(
                    payload.previous_input_artifact_id,
                    directory / "previous.xlsx",
                )
                validate_xlsx_archive(input_path)
                validate_xlsx_archive(previous_path)
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()
                context.heartbeat(progress=10)
                result = publish_report_to_feishu(
                    input_path=input_path,
                    previous_input_path=previous_path,
                    output_dir=directory / "report",
                    report_date_range=(payload.start_date, payload.end_date),
                    settings=self._runtime.settings,
                    environ=os.environ,
                )
                context.heartbeat(progress=100)
                return JobHandlerResult.succeeded(
                    {
                        "kind": "report",
                        "native_document_url": result.publication.native_document_url,
                        "editable_chart_sheet_url": result.publication.editable_chart_sheet_url,
                        "content_rows": result.report.content_rows,
                        "label_rows": result.report.label_rows,
                        "comment_rows": result.report.comment_rows,
                        "start_date": payload.start_date.isoformat(),
                        "end_date": payload.end_date.isoformat(),
                    }
                )
        except FileNotFoundError:
            return JobHandlerResult.failed("feishu_publication_artifact_missing")
        except (FeishuReportPublicationConfigurationError, SecretFileError):
            return JobHandlerResult.failed("feishu_report_config_unavailable")
        except FeishuApiError as exc:
            if exc.retriable:
                return JobHandlerResult.retry("feishu_report_api_retry")
            return JobHandlerResult.failed("feishu_report_api_failed")
        except (OSError, TimeoutError):
            return JobHandlerResult.retry("feishu_report_io_error")
        except (ValueError, RuntimeError):
            return JobHandlerResult.failed("feishu_report_publication_failed")

    def execute_representative_selection(
        self,
        *,
        payload: FeishuRepresentativeSelectionJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        del fence
        try:
            with self._temporary_directory("feishu-representative-") as directory_name:
                directory = Path(directory_name)
                input_path = self._materialize_artifact(
                    payload.input_artifact_id,
                    directory / "labeled.xlsx",
                )
                validate_xlsx_archive(input_path)
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()
                context.heartbeat(progress=5)
                summary = publish_representative_selection_to_feishu(
                    input_path=input_path,
                    output_dir=directory / "selection",
                    settings=self._runtime.settings,
                    environ=os.environ,
                    progress=lambda value: context.heartbeat(progress=value),
                )
                context.heartbeat(progress=100)
                return JobHandlerResult.succeeded(
                    {
                        "kind": "representative_selection",
                        "target_table_id": summary.target_table_id or "",
                        "target_table_name": summary.target_table_name or "",
                        "created_count": summary.created_count,
                        "updated_count": summary.updated_count,
                        "verified_count": summary.verified_count,
                        "verification_errors": list(summary.verification_errors),
                    }
                )
        except FileNotFoundError:
            return JobHandlerResult.failed("feishu_publication_artifact_missing")
        except (RepresentativeSelectionPublicationConfigurationError, SecretFileError):
            return JobHandlerResult.failed("feishu_representative_config_unavailable")
        except FeishuAPIError as exc:
            if exc.retryable:
                return JobHandlerResult.retry("feishu_bitable_api_retry")
            return JobHandlerResult.failed("feishu_bitable_api_failed")
        except (FeishuSyncError, ValueError):
            return JobHandlerResult.failed("feishu_representative_publication_failed")
        except (OSError, TimeoutError):
            return JobHandlerResult.retry("feishu_representative_io_error")
        except RuntimeError:
            return JobHandlerResult.failed("feishu_representative_publication_failed")

    def _temporary_directory(self, prefix: str) -> TemporaryDirectory[str]:
        root = self._runtime.settings.data_dir / "tmp"
        root.mkdir(parents=True, exist_ok=True)
        return TemporaryDirectory(prefix=prefix, dir=root)

    def _materialize_artifact(self, artifact_id: UUID, destination: Path) -> Path:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                artifact = PostgresArtifactMetadataRepository(session).get(artifact_id)
        finally:
            session.close()
        if artifact is None or artifact.storage_status not in {"stored", "linked"}:
            raise FileNotFoundError(str(artifact_id))
        if artifact.storage_backend != self._runtime.artifact_store.backend_name:
            raise ValueError("上传 Artifact 存储后端不匹配")

        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        total = 0
        with self._runtime.artifact_store.open_read(artifact.storage_key) as source:
            with destination.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
        if artifact.sha256 is None or artifact.byte_size is None:
            raise ValueError("上传 Artifact 完整性元数据缺失")
        if digest.hexdigest() != artifact.sha256 or total != artifact.byte_size:
            raise ValueError("上传 Artifact 完整性校验失败")
        return destination


__all__ = ["PostgresFeishuPublicationJobExecutor"]
