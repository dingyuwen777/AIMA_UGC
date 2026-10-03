"""WisersOne 下载请求的短事务与统一导入状态查询。"""

from __future__ import annotations

from pathlib import Path
from typing import cast
from uuid import UUID

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.wisersone import (
    PostgresWisersOneRepository,
    WisersOneConflict,
)
from aima_ugc.adapters.providers.wisersone.auth import default_host_root
from aima_ugc.adapters.providers.wisersone.export import WisersOneExporter
from aima_ugc.contracts.http import (
    WisersOneDownloadCreateRequest,
    WisersOneDownloadListResponse,
    WisersOneDownloadResponse,
)
from aima_ugc.modules.ingestion.wisersone_jobs import WISERSONE_TERMINAL
from aima_ugc.platform.time import beijing_now

from .historical_import_http import PostgresHistoricalImportHttpService
from .runtime import PlatformRuntime


def managed_input_root(runtime: PlatformRuntime) -> Path:
    """Worker 写入 alias 和历史输入只读视图由部署 bind 指向同一宿主目录。"""
    return (
        runtime.settings.wisersone_input_dir
        or default_host_root() / "aima-historical-input" / "wisersone"
    )


def managed_relative_path(download_id: UUID) -> str:
    return f"wisersone/{download_id}/wisersone_last24h.xlsx"


class PostgresWisersOneHttpService:
    def __init__(self, runtime: PlatformRuntime) -> None:
        self.runtime = runtime
        self.imports = PostgresHistoricalImportHttpService(runtime)

    def create(
        self, request: WisersOneDownloadCreateRequest, *, request_id: str
    ) -> WisersOneDownloadResponse:
        if self.runtime.settings.historical_import_root is None:
            raise WisersOneConflict("请配置历史输入根目录和 WisersOne 受管目录。")
        if not managed_input_root(self.runtime).is_dir():
            raise WisersOneConflict("WisersOne 受管目录尚未接入历史输入视图，请先准备宿主目录。")
        existing = self.runtime.settings.historical_import_root / "wisersone"
        if existing.exists() and not existing.samefile(managed_input_root(self.runtime)):
            raise WisersOneConflict("批准目录已有不同的 wisersone 目录，请先消除受管目录冲突。")
        # 在发送外部请求前冻结选择范围，后续 Campaign 和恢复复用同一快照。
        snapshot = self.imports._read_brand_vehicle_filter_snapshot(request.brand_ids)
        with self.runtime.database.new_session() as session, session.begin():
            row = PostgresWisersOneRepository(session).create(
                request, request_id, filter_snapshot=snapshot
            )
            return self._response(dict(row))

    def get(self, download_id: UUID) -> WisersOneDownloadResponse:
        with self.runtime.database.new_session() as session, session.begin():
            row = PostgresWisersOneRepository(session).get(download_id)
            if row is None:
                raise KeyError(download_id)
            return self._response(dict(row))

    def list(self) -> WisersOneDownloadListResponse:
        with self.runtime.database.new_session() as session, session.begin():
            rows = PostgresWisersOneRepository(session).list()
            return WisersOneDownloadListResponse(items=tuple(self._response(dict(r)) for r in rows))

    @staticmethod
    def _response(row: dict[str, object]) -> WisersOneDownloadResponse:
        return WisersOneDownloadResponse.model_validate(
            {name: row[name] for name in WisersOneDownloadResponse.model_fields if name in row}
        )

    def cancel(self, download_id: UUID) -> WisersOneDownloadResponse:
        with self.runtime.database.new_session() as session, session.begin():
            repo = PostgresWisersOneRepository(session)
            row = repo.get(download_id, lock=True)
            if row is None:
                raise KeyError(download_id)
            if row["status"] in WISERSONE_TERMINAL:
                return self._response(dict(row))
            repo.update(download_id, cancel_requested_at=beijing_now())
            job_id = cast(UUID | None, row["job_id"])
            campaign_id = cast(UUID | None, row["campaign_id"])
        # 与既有取消路径保持短事务锁顺序；不持下载行锁再等待 Job/Campaign。
        if job_id is not None:
            with self.runtime.database.new_session() as session, session.begin():
                PostgresJobRepository(session).request_cancel(job_id)
        if campaign_id is not None:
            self.imports.cancel_campaign(campaign_id)
        with self.runtime.database.new_session() as session, session.begin():
            PostgresWisersOneRepository(session).update(
                download_id, status="cancelled", finished_at=beijing_now()
            )
        return self.get(download_id)

    def retry(self, download_id: UUID) -> WisersOneDownloadResponse:
        with self.runtime.database.new_session() as session, session.begin():
            repo = PostgresWisersOneRepository(session)
            row = repo.get(download_id, lock=True)
            if row is None:
                raise KeyError(download_id)
            if row["status"] not in {"failed", "partial_failed", "attention"}:
                raise WisersOneConflict("当前状态不允许恢复。取消后请核对已导入结果。")
            if row["file_deleted_at"] is not None or row["file_delete_pending_at"] is not None:
                raise WisersOneConflict("本次冻结文件已清理，不能以新24小时导出冒充重试。")
            if row["send_state"] == "unknown" and row["website_task_id"] is None:
                exporter = WisersOneExporter(auth_dir=self.runtime.settings.wisersone_auth_dir)
                receipt = exporter.saved_task(download_id)
                if receipt is None:
                    raise WisersOneConflict("提交结果未知且无回执，请核对网站记录，未重复发送。")
                repo.update(download_id, website_task_id=receipt.task_id, send_state="confirmed")
            campaign_id = cast(UUID | None, row["campaign_id"])
            # Campaign 重试必须复用它持有的原 Source/Canonical 和冻结过滤。
            if campaign_id is None:
                repo.update(download_id, status="queued", error_code=None, finished_at=None)
                repo.enqueue(download_id, step=int(row["step"]) + 1, request_id=None)
                return self._response(dict(repo.get(download_id) or row))
        self.imports.retry_failed(campaign_id)
        with self.runtime.database.new_session() as session, session.begin():
            repo = PostgresWisersOneRepository(session)
            current = repo.get(download_id, lock=True)
            if current is None or current["cancel_requested_at"] is not None:
                raise WisersOneConflict("恢复期间已取消。")
            repo.update(download_id, status="importing", error_code=None, finished_at=None)
            repo.enqueue(download_id, step=int(current["step"]) + 1, request_id=None)
        return self.get(download_id)
