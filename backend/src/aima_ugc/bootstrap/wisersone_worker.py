"""有界网站任务阶段与现有 Data Import Campaign 的恢复编排。"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.historical_import import (
    PostgresHistoricalImportRepository,
)
from aima_ugc.adapters.persistence.postgres.wisersone import (
    PostgresWisersOneRepository,
    WisersOneConflict,
)
from aima_ugc.adapters.providers.wisersone.export import WisersOneExporter
from aima_ugc.adapters.providers.wisersone.models import (
    ExportCancelled,
    ExportTask,
    SubmissionUnknown,
)
from aima_ugc.contracts.http import HistoricalCampaignCreateRequest, WisersOneDownloadCreateRequest
from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot
from aima_ugc.modules.ingestion.historical_directory import HistoricalDirectoryBrowser
from aima_ugc.modules.ingestion.wisersone_jobs import WISERSONE_TERMINAL, WisersOneJobPayload
from aima_ugc.platform.jobs import JobHandlerResult, JobRecord, LeaseLostError
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.time import beijing_now

from .historical_import_http import PostgresHistoricalImportHttpService
from .runtime import PlatformRuntime
from .wisersone_http import managed_input_root, managed_relative_path


class PostgresWisersOneJobExecutor:
    def __init__(
        self, runtime: PlatformRuntime, *, exporter: WisersOneExporter | None = None
    ) -> None:
        self.runtime = runtime
        self.exporter = exporter or WisersOneExporter(auth_dir=runtime.settings.wisersone_auth_dir)
        self.imports = PostgresHistoricalImportHttpService(runtime)

    def __call__(
        self, payload: BaseModel, context: JobExecutionContextProtocol
    ) -> JobHandlerResult:
        if not isinstance(payload, WisersOneJobPayload):
            raise TypeError("WisersOne Job Payload 类型错误。")
        try:
            if payload.operation == "cancel":
                return self._cancel(payload, context)
            return self._step(payload, context)
        except LeaseLostError:
            raise
        except ExportCancelled:
            return (
                JobHandlerResult.cancelled()
                if context.cancel_requested()
                else JobHandlerResult.succeeded({"cancel_requested": True})
            )
        except WisersOneConflict:
            # 新阶段已接管；旧阶段不再拥有下载事实，也不能覆盖取消/恢复工作。
            return JobHandlerResult.succeeded({"superseded": True})
        except SubmissionUnknown:
            self._change(
                payload, context, status="attention", error_code="wisersone_submission_unknown"
            )
            return JobHandlerResult.failed("wisersone_submission_unknown")
        except Exception as exc:
            # 外部异常可能携带签名地址/认证头；错误只持久化稳定安全代码。
            log_event(
                self.runtime.logger,
                logging.ERROR,
                "wisersone.stage_failed",
                "WisersOne 阶段失败，可通过同次任务恢复",
                download_id=str(payload.download_id),
                step=payload.step,
                error_type=type(exc).__name__,
            )
            if payload.operation == "cancel":
                return JobHandlerResult.retry("wisersone_cancel_propagation_failed")
            self._change(payload, context, status="failed", error_code="wisersone_stage_failed")
            return JobHandlerResult.failed("wisersone_stage_failed")

    def _change(
        self, payload: WisersOneJobPayload, context: JobExecutionContextProtocol, **values: object
    ) -> None:
        with self.runtime.database.new_session() as session, session.begin():
            repo = PostgresWisersOneRepository(session)
            row = repo.fenced(payload.download_id, context.fence)
            if row["cancel_requested_at"] is not None:
                raise ExportCancelled
            if values.get("status") in WISERSONE_TERMINAL:
                values["finished_at"] = beijing_now()
            repo.update(payload.download_id, **values)

    def _continue(
        self, payload: WisersOneJobPayload, context: JobExecutionContextProtocol, *, delay: int = 30
    ) -> JobHandlerResult:
        with self.runtime.database.new_session() as session, session.begin():
            repo = PostgresWisersOneRepository(session)
            row = repo.fenced(payload.download_id, context.fence)
            if row["cancel_requested_at"] is not None:
                return JobHandlerResult.cancelled()
            repo.enqueue(payload.download_id, step=payload.step + 1, request_id=None, delay=delay)
        return JobHandlerResult.succeeded({"continuation": True})

    def _cancel(
        self, payload: WisersOneJobPayload, context: JobExecutionContextProtocol
    ) -> JobHandlerResult:
        """复用下游取消 Owner；持久阶段只在相关执行结清后投影最终结果。"""
        with self.runtime.database.new_session() as session, session.begin():
            row = PostgresWisersOneRepository(session).fenced(payload.download_id, context.fence)
            campaign_id = cast(UUID, row["campaign_id"])
            campaign = PostgresHistoricalImportRepository(session).get_campaign(campaign_id)
            if campaign is None:
                raise RuntimeError("取消关联的 Campaign 不存在。")
            status = str(campaign["status"])
        if status == "cancelling":
            self.imports.cancel_campaign(campaign_id)
        with self.runtime.database.new_session() as session, session.begin():
            repo = PostgresWisersOneRepository(session)
            repo.fenced(payload.download_id, context.fence)
            campaign = PostgresHistoricalImportRepository(session).get_campaign(campaign_id)
            if campaign is None:
                raise RuntimeError("取消关联的 Campaign 不存在。")
            status = str(campaign["status"])
            if status in {"succeeded", "partial_failed", "failed", "cancelled", "revoked"}:
                repo.update(
                    payload.download_id,
                    status="cancelled" if status == "revoked" else status,
                    finished_at=campaign["finished_at"] or beijing_now(),
                    error_code=None,
                )
                return JobHandlerResult.succeeded(
                    {"campaign_id": str(campaign_id), "status": status}
                )
            repo.enqueue(
                payload.download_id,
                step=payload.step + 1,
                request_id=None,
                delay=30,
                operation="cancel",
            )
        return JobHandlerResult.succeeded({"continuation": True})

    def _step(
        self, payload: WisersOneJobPayload, context: JobExecutionContextProtocol
    ) -> JobHandlerResult:
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        with self.runtime.database.new_session() as session, session.begin():
            row = dict(
                PostgresWisersOneRepository(session).fenced(payload.download_id, context.fence)
            )
        if row["status"] in WISERSONE_TERMINAL or row["cancel_requested_at"] is not None:
            return JobHandlerResult.succeeded({"terminal_or_cancel_requested": True})
        context.heartbeat(progress=5)
        download_id = payload.download_id
        campaign_id = cast(UUID | None, row["campaign_id"])
        if campaign_id is not None:
            return self._campaign(payload, context, campaign_id)
        task_id = cast(str | None, row["website_task_id"])
        if task_id is None:
            receipt = self.exporter.saved_task(download_id)
            if receipt is None and row["send_state"] == "unknown":
                raise SubmissionUnknown

            def confirmed(task: ExportTask) -> None:
                self._change(
                    payload,
                    context,
                    website_task_id=task.task_id,
                    send_state="confirmed",
                    status="waiting",
                )

            if receipt is None:
                receipt = self.exporter.submit(
                    download_id,
                    before_submit=lambda: self._change(
                        payload, context, send_state="unknown", status="submitting"
                    ),
                    on_submitted=confirmed,
                    cancelled=context.cancel_requested,
                )
            confirmed(receipt)
            return self._continue(payload, context)
        root = managed_input_root(self.runtime)
        stage = root / ".staging" / str(download_id) / "wisersone_last24h.xlsx"
        published = root / str(download_id) / "wisersone_last24h.xlsx"
        if not published.exists():
            progress = self.exporter.poll(
                ExportTask(task_id), stage, download=False, cancelled=context.cancel_requested
            )
            self._change(payload, context, percent=progress.percent, status="waiting")
            if not progress.ready:
                return self._continue(payload, context)
            self._change(payload, context, status="downloading")
            result = self.exporter.poll(
                ExportTask(task_id), stage, cancelled=context.cancel_requested
            )
            if result.file is None:
                return self._continue(payload, context)
            # 文件发布前复核当前 token；剩余 rename/crash 窗口由同路径 checksum 恢复。
            self._change(payload, context, percent=100)
            published.parent.mkdir(parents=True, exist_ok=True)
            stage.replace(published)
        checksum = _sha256(published)
        if row["sha256"] is not None and row["sha256"] != checksum:
            raise RuntimeError("冻结下载文件已改变。")
        self._change(payload, context, sha256=checksum, status="preflight")
        approved_root = self.runtime.settings.historical_import_root
        browser = HistoricalDirectoryBrowser(
            approved_root, managed_wisersone_root=self.runtime.settings.wisersone_input_dir
        )
        if _sha256(browser.resolve(managed_relative_path(download_id))) != checksum:
            raise RuntimeError("WisersOne 写入目录与历史输入视图不一致。")
        request = WisersOneDownloadCreateRequest.model_validate(row["request"])

        def attach(session: Session, created_id: UUID) -> None:
            repo = PostgresWisersOneRepository(session)
            current = repo.fenced(download_id, context.fence)
            if current["cancel_requested_at"] is not None:
                raise ExportCancelled
            repo.update(download_id, campaign_id=created_id, status="preflight")

        self.imports.create_campaign(
            HistoricalCampaignCreateRequest(
                client_idempotency_key=f"wisersone:{download_id}",
                relative_paths=(managed_relative_path(download_id),),
                brand_ids=request.brand_ids,
                ingestion_policy="standard_observation",
            ),
            request_id=str(download_id),
            execution_fence=context.fence,
            on_created=attach,
            filter_snapshot=BrandVehicleFilterSnapshot.model_validate(row["filter_snapshot"]),
        )
        return self._continue(payload, context)

    def _campaign(
        self, payload: WisersOneJobPayload, context: JobExecutionContextProtocol, campaign_id: UUID
    ) -> JobHandlerResult:
        with self.runtime.database.new_session() as session, session.begin():
            repo = PostgresWisersOneRepository(session)
            row = repo.fenced(payload.download_id, context.fence)
            if row["cancel_requested_at"] is not None:
                return JobHandlerResult.cancelled()
            imports = PostgresHistoricalImportRepository(session)
            campaign = imports.get_campaign(campaign_id, for_update=True)
            if campaign is None:
                raise RuntimeError("下载关联的 Campaign 不存在。")
            status = str(campaign["status"])
            if status in {"succeeded", "partial_failed", "failed", "cancelled"}:
                repo.update(
                    payload.download_id,
                    status=status,
                    finished_at=beijing_now(),
                    error_code=None if status == "succeeded" else "wisersone_import_incomplete",
                )
                return JobHandlerResult.succeeded(
                    {"campaign_id": str(campaign_id), "status": status}
                )
            if status == "ready":
                batches = dict(imports.prepare_campaign_start(campaign_id))
                imports.schedule_import_jobs(
                    campaign_id=campaign_id,
                    source_batches=batches,
                    max_in_flight=self.runtime.job_window(
                        "historical", ceiling=self.runtime.settings.historical_max_in_flight_jobs
                    ),
                )
                repo.update(payload.download_id, status="importing")
            repo.enqueue(payload.download_id, step=payload.step + 1, request_id=None, delay=30)
        return JobHandlerResult.succeeded({"continuation": True})


def wisersone_terminal_callback(session: Session, job: JobRecord) -> None:
    """只收敛仍指向该阶段的下载；旧阶段成功不能覆盖其后续阶段。"""
    payload = WisersOneJobPayload.model_validate(job.payload)
    repo = PostgresWisersOneRepository(session)
    row = repo.get(payload.download_id, lock=True)
    if row is None or row["job_id"] != job.id or row["status"] in WISERSONE_TERMINAL:
        return
    if row["cancel_requested_at"] is not None and row["campaign_id"] is not None:
        # 通用任务取消/次数耗尽不能消除已承诺的下游传播；新阶段仍可由其他 Worker 接管。
        repo.enqueue(
            payload.download_id,
            step=int(row["step"]) + 1,
            request_id=None,
            delay=30,
            operation="cancel",
        )
        return
    if job.status in {"failed", "cancelled"}:
        repo.update(
            payload.download_id,
            status=job.status,
            finished_at=beijing_now(),
            error_code=job.error_code,
        )


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()
