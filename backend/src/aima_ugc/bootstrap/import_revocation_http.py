"""Data Import Campaign 撤销的 PostgreSQL Application Service 与最终路由装配。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from sqlalchemy import insert, update
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.historical_revocation import (
    PostgresImportCampaignRevocationRepository,
)
from aima_ugc.adapters.persistence.postgres.import_revocation_lifecycle import (
    PostgresImportRevocationLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.contracts.http import HttpErrorResponse
from aima_ugc.contracts.lifecycle import (
    DataImportRevocationImpactResponse,
    DataImportRevocationPreviewResponse,
    DataImportRevocationResponse,
    DataImportRevokeRequest,
)
from aima_ugc.modules.identity import DevelopmentIdentityResolver, IdentityResolver
from aima_ugc.modules.ingestion.historical_http import (
    HistoricalCampaignNotFound,
    HistoricalCampaignStateConflict,
)
from aima_ugc.modules.ingestion.historical_jobs import HISTORICAL_JOB_PRIORITY
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaigns_table
from aima_ugc.modules.ingestion.revocation import (
    ImportCampaignRevocationConflict,
    ImportCampaignRevocationNotFound,
    ImportCampaignRevocationPreview,
    ImportCampaignRevocationRecord,
    ImportCampaignRevocationService,
)
from aima_ugc.modules.ingestion.revocation_http import ImportRevocationHttpService
from aima_ugc.modules.ingestion.revocation_jobs import (
    DATA_IMPORT_REVOCATION_JOB_TYPE,
    DataImportRevocationJobPayload,
)
from aima_ugc.modules.ingestion.revocation_tables import (
    historical_import_revocation_requests_table,
)
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.storage import ArtifactRecord, ArtifactService
from aima_ugc.platform.storage.ports import ArtifactStore
from aima_ugc.platform.time import beijing_now

SessionFactory = Callable[[], Session]


class PostgresImportRevocationHttpService:
    """以短事务协调撤销资格、Content 重组、来源追溯和安全审计。"""

    def __init__(
        self,
        session_factory: SessionFactory,
        artifact_store: ArtifactStore,
    ) -> None:
        self._session_factory = session_factory
        self._artifact_store = artifact_store

    def preview(self, campaign_id: UUID) -> DataImportRevocationPreviewResponse:
        """只读计算撤销影响与可逆证据，不创建撤销事实或审计记录。"""

        session = self._session_factory()
        try:
            with session.begin():
                operation = PostgresImportCampaignRevocationRepository(session).get_operation(
                    campaign_id
                )
                if operation is not None:
                    return _operation_preview_response(operation)
                try:
                    preview = ImportCampaignRevocationService(
                        PostgresImportCampaignRevocationRepository(session)
                    ).preview(campaign_id)
                except ImportCampaignRevocationNotFound as exc:
                    raise HistoricalCampaignNotFound from exc
                return _preview_response(preview)
        finally:
            session.close()

    def revoke(
        self,
        campaign_id: UUID,
        body: DataImportRevokeRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> DataImportRevocationResponse:
        """原子登记撤销 Job；只有 Job 完成后页面才显示已撤销。"""

        started = perf_counter()
        initial = self.preview(campaign_id)
        if initial.status in {"queued", "running", "succeeded"}:
            return self._load_existing_response(campaign_id)
        if not initial.eligible and initial.status != "failed":
            raise HistoricalCampaignStateConflict("当前导入无法安全自动撤销")

        platforms = (
            self._campaign_contribution_platforms(campaign_id)
            if initial.status == "not_requested"
            else ()
        )
        revocation_artifact = self._store_revocation_artifact(campaign_id) if platforms else None
        session = self._session_factory()
        try:
            with session.begin():
                repository = PostgresImportCampaignRevocationRepository(session)
                campaign_status = repository.get_campaign_status(campaign_id, for_update=True)
                if campaign_status is None:
                    raise HistoricalCampaignNotFound
                existing = repository.get_operation(campaign_id, for_update=True)
                if existing is not None and existing["status"] != "failed":
                    return _operation_response(
                        existing, already_revoked=existing["status"] == "succeeded"
                    )
                if existing is None:
                    requested_at = beijing_now()
                    try:
                        record, _ = ImportCampaignRevocationService(repository).revoke(
                            campaign_id,
                            actor_ref=actor_ref,
                            request_id=request_id,
                            reason=body.reason,
                            revoked_at=requested_at,
                        )
                    except ImportCampaignRevocationNotFound as exc:
                        raise HistoricalCampaignNotFound from exc
                    except ImportCampaignRevocationConflict as exc:
                        raise HistoricalCampaignStateConflict from exc
                    if platforms:
                        if revocation_artifact is None:
                            raise RuntimeError("撤销生命周期缺少不可变来源 Artifact")
                        PostgresImportRevocationLifecycleRepository(
                            session
                        ).create_lifecycle_sources(
                            campaign_id=campaign_id,
                            raw_artifact_id=revocation_artifact.id,
                            revoked_at=requested_at,
                        )
                        PostgresArtifactMetadataRepository(session).mark_linked(
                            revocation_artifact.id,
                            linked_at=requested_at,
                        )
                else:
                    record = None
                    if campaign_status != "revoking":
                        raise HistoricalCampaignStateConflict("撤销失败状态与 Campaign 不一致")
                job = PostgresJobRepository(session).enqueue(
                    job_type=DATA_IMPORT_REVOCATION_JOB_TYPE,
                    payload_version=DATA_IMPORT_REVOCATION_JOB_TYPE,
                    payload=DataImportRevocationJobPayload(campaign_id=campaign_id).model_dump(
                        mode="json"
                    ),
                    internal_idempotency_key=f"data-import-revoke:{campaign_id}:{uuid4()}",
                    request_id=request_id,
                    priority=HISTORICAL_JOB_PRIORITY,
                    max_attempts=10,
                    timeout_seconds=86_400,
                )
                if existing is None:
                    session.execute(
                        insert(historical_import_revocation_requests_table).values(
                            campaign_id=campaign_id,
                            status="queued",
                            job_id=job.id,
                            raw_artifact_id=(
                                revocation_artifact.id if revocation_artifact is not None else None
                            ),
                        )
                    )
                else:
                    session.execute(
                        update(historical_import_revocation_requests_table)
                        .where(
                            historical_import_revocation_requests_table.c.campaign_id == campaign_id
                        )
                        .values(status="queued", job_id=job.id, error_code=None)
                    )
                session.execute(
                    update(historical_import_campaigns_table)
                    .where(historical_import_campaigns_table.c.id == campaign_id)
                    .values(status="revoking")
                )
                if record is not None:
                    PostgresAuditRepository(session).append(
                        AuditEvent(
                            id=uuid4(),
                            actor_kind="principal",
                            actor_ref=actor_ref,
                            event_type="data_import_campaign_revocation_requested",
                            object_type="data_import_campaign",
                            object_id=str(campaign_id),
                            request_id=request_id,
                            safe_detail={
                                "affected_content_count": record.impact.affected_content_count,
                                "job_id": str(job.id),
                            },
                            created_at=record.revoked_at,
                        )
                    )
                operation = repository.get_operation(campaign_id)
                if operation is None:
                    raise RuntimeError("撤销请求未能持久化")
                response = _operation_response(operation, already_revoked=False)
            log_event(
                logging.getLogger(__name__),
                logging.INFO,
                "data_import.revocation_queued",
                "数据导入撤销已入队",
                campaign_id=str(campaign_id),
                job_id=str(job.id),
                affected_content_count=response.impact.affected_content_count,
                duration_ms=int((perf_counter() - started) * 1000),
            )
            return response
        finally:
            session.close()

    def _load_existing_response(self, campaign_id: UUID) -> DataImportRevocationResponse:
        """重复点击时返回同一持久请求，不创建新的 Artifact 或 Job。"""

        session = self._session_factory()
        try:
            with session.begin():
                operation = PostgresImportCampaignRevocationRepository(session).get_operation(
                    campaign_id
                )
                if operation is None:
                    raise HistoricalCampaignNotFound
                return _operation_response(
                    operation, already_revoked=operation["status"] == "succeeded"
                )
        finally:
            session.close()

    def _campaign_contribution_platforms(self, campaign_id: UUID) -> tuple[str, ...]:
        """在写 Artifact 前确认本次是否真的需要生成 Content 生命周期 Version。"""

        session = self._session_factory()
        try:
            with session.begin():
                return PostgresImportRevocationLifecycleRepository(
                    session
                ).campaign_contribution_platforms(campaign_id)
        finally:
            session.close()

    def _store_revocation_artifact(self, campaign_id: UUID) -> ArtifactRecord:
        """保存不含 Secret/用户原因的最小撤销证据，作为内部 imports 来源 Raw。"""

        payload = json.dumps(
            {
                "schema_version": "data-import-revocation.v1",
                "campaign_id": str(campaign_id),
                "action": "revoke_source_contributions",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return ArtifactService(
            metadata=PostgresArtifactMetadataGateway(self._session_factory),
            store=self._artifact_store,
        ).store_bytes(
            kind="provider-raw",
            content_type="application/json",
            retention_class="raw",
            data=payload,
            encoding="utf-8",
        )


def install_import_revocation_routes(
    application: FastAPI,
    *,
    service: ImportRevocationHttpService | None = None,
    identity_resolver: IdentityResolver | None = None,
) -> None:
    """在最终 API 装配撤销预览/执行路由，并复用与主 API 相同的身份解析语义。"""

    resolved_identity = identity_resolver or DevelopmentIdentityResolver()
    database: DatabaseRuntime | None = None
    artifact_store: LocalArtifactStore | None = None

    def current_service() -> ImportRevocationHttpService:
        """测试可注入 Service；生产首次请求时惰性建立数据库与 Artifact Store。"""

        nonlocal artifact_store, database
        if service is not None:
            return service
        if database is None or artifact_store is None:
            settings = load_settings()
            database = DatabaseRuntime(settings)
            artifact_store = LocalArtifactStore(settings.artifact_dir)
        return PostgresImportRevocationHttpService(
            database.new_session,
            artifact_store,
        )

    if service is None:
        router = cast(Any, application.router)
        original_lifespan = router.lifespan_context

        @asynccontextmanager
        async def lifecycle_lifespan(app: FastAPI) -> AsyncIterator[None]:
            """在主 API lifespan 之后释放扩展路由自己的惰性数据库连接池。"""

            async with original_lifespan(app):
                try:
                    yield
                finally:
                    if database is not None:
                        database.dispose()

        router.lifespan_context = lifecycle_lifespan

    @application.get(
        "/api/v1/data-import-campaigns/{campaign_id}/revocation-preview",
        operation_id="previewDataImportCampaignRevocation",
        response_model=DataImportRevocationPreviewResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def preview_data_import_campaign_revocation(
        campaign_id: UUID,
    ) -> DataImportRevocationPreviewResponse:
        """在用户确认前返回撤销影响；不会修改 Campaign 或 Content。"""

        return current_service().preview(campaign_id)

    @application.post(
        "/api/v1/data-import-campaigns/{campaign_id}/revoke",
        operation_id="revokeDataImportCampaign",
        response_model=DataImportRevocationResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def revoke_data_import_campaign(
        campaign_id: UUID,
        body: DataImportRevokeRequest,
        request: Request,
    ) -> DataImportRevocationResponse:
        """撤销已完成导入的来源贡献；权限沿用当前统一导入能力，不新增平行 RBAC。"""

        principal = resolved_identity.resolve(request)
        return current_service().revoke(
            campaign_id,
            body,
            actor_ref=principal.principal_id,
            request_id=_request_id(request),
        )


def _request_id(request: Request) -> str:
    """读取主 API middleware 建立的 request_id；测试直装路由时提供安全兜底。"""

    value = getattr(request.state, "request_id", None)
    return str(value) if value is not None else str(uuid4())


def _impact_response(
    record: ImportCampaignRevocationRecord | ImportCampaignRevocationPreview,
) -> DataImportRevocationImpactResponse:
    """把领域影响映射到不暴露来源账本细节的公共响应。"""

    return DataImportRevocationImpactResponse(
        affected_content_count=record.impact.affected_content_count,
        hidden_content_count=record.impact.hidden_content_count,
        retained_shared_content_count=record.impact.retained_shared_content_count,
        unreversible_content_count=record.impact.unreversible_content_count,
    )


def _preview_response(
    preview: ImportCampaignRevocationPreview,
) -> DataImportRevocationPreviewResponse:
    """构造撤销预览公共 Contract。"""

    return DataImportRevocationPreviewResponse(
        campaign_id=preview.campaign_id,
        eligible=preview.eligible,
        already_revoked=preview.already_revoked,
        ineligible_reason=preview.ineligible_reason,
        impact=_impact_response(preview),
        status="not_requested",
    )


def _operation_impact(operation: Mapping[str, object]) -> DataImportRevocationImpactResponse:
    return DataImportRevocationImpactResponse(
        affected_content_count=cast(int, operation["affected_content_count"]),
        hidden_content_count=cast(int, operation["hidden_content_count"]),
        retained_shared_content_count=cast(int, operation["retained_shared_content_count"]),
        unreversible_content_count=cast(int, operation["unreversible_content_count"]),
    )


def _operation_preview_response(
    operation: Mapping[str, object],
) -> DataImportRevocationPreviewResponse:
    """请求存在时直接读冻结影响，不重复执行全量影响 SQL。"""

    status = cast(Literal["queued", "running", "succeeded", "failed"], operation["status"])
    return DataImportRevocationPreviewResponse(
        campaign_id=cast(UUID, operation["campaign_id"]),
        eligible=status in {"failed", "succeeded"},
        already_revoked=status == "succeeded",
        impact=_operation_impact(operation),
        status=status,
        job_id=cast(UUID | None, operation["job_id"]),
        recomputed_content_count=cast(int, operation["recomputed_content_count"]),
        error_code=cast(str | None, operation["error_code"]),
    )


def _operation_response(
    operation: Mapping[str, object],
    *,
    already_revoked: bool,
) -> DataImportRevocationResponse:
    """构造可轮询的撤销状态；未成功不得暴露完成时间。"""

    status = cast(Literal["queued", "running", "succeeded", "failed"], operation["status"])
    return DataImportRevocationResponse(
        campaign_id=cast(UUID, operation["campaign_id"]),
        already_revoked=already_revoked,
        impact=_operation_impact(operation),
        status=status,
        job_id=cast(UUID | None, operation["job_id"]),
        recomputed_content_count=cast(int, operation["recomputed_content_count"]),
        error_code=cast(str | None, operation["error_code"]),
        revoked_at=(
            cast(datetime, operation["completed_at"] or operation["revoked_at"])
            if status == "succeeded"
            else None
        ),
    )


__all__ = [
    "PostgresImportRevocationHttpService",
    "install_import_revocation_routes",
]
