"""Data Import Campaign 撤销的 PostgreSQL Application Service 与最终路由装配。"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.historical_revocation import (
    PostgresImportCampaignRevocationRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.contracts.http import HttpErrorResponse
from aima_ugc.contracts.lifecycle import (
    DataImportRevokeRequest,
    DataImportRevocationImpactResponse,
    DataImportRevocationPreviewResponse,
    DataImportRevocationResponse,
)
from aima_ugc.modules.identity import DevelopmentIdentityResolver, IdentityResolver
from aima_ugc.modules.ingestion.historical_http import (
    HistoricalCampaignNotFound,
    HistoricalCampaignStateConflict,
)
from aima_ugc.modules.ingestion.revocation import (
    ImportCampaignRevocationConflict,
    ImportCampaignRevocationNotFound,
    ImportCampaignRevocationPreview,
    ImportCampaignRevocationRecord,
    ImportCampaignRevocationService,
)
from aima_ugc.modules.ingestion.revocation_http import ImportRevocationHttpService
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.time import beijing_now

SessionFactory = Callable[[], Session]


class PostgresImportRevocationHttpService:
    """以短事务协调撤销领域服务和审计追加，不直接改写 Content。"""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def preview(self, campaign_id: UUID) -> DataImportRevocationPreviewResponse:
        """只读计算撤销影响，不创建撤销事实或审计记录。"""

        session = self._session_factory()
        try:
            with session.begin():
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
        """提交一次幂等撤销；首次提交和安全审计在同一数据库事务完成。"""

        session = self._session_factory()
        try:
            with session.begin():
                try:
                    record, created = ImportCampaignRevocationService(
                        PostgresImportCampaignRevocationRepository(session)
                    ).revoke(
                        campaign_id,
                        actor_ref=actor_ref,
                        request_id=request_id,
                        reason=body.reason,
                        revoked_at=beijing_now(),
                    )
                except ImportCampaignRevocationNotFound as exc:
                    raise HistoricalCampaignNotFound from exc
                except ImportCampaignRevocationConflict as exc:
                    raise HistoricalCampaignStateConflict from exc
                if created:
                    PostgresAuditRepository(session).append(
                        AuditEvent(
                            id=uuid4(),
                            actor_kind="principal",
                            actor_ref=actor_ref,
                            event_type="data_import_campaign_revoked",
                            object_type="data_import_campaign",
                            object_id=str(campaign_id),
                            request_id=request_id,
                            safe_detail={
                                "affected_content_count": record.impact.affected_content_count,
                                "hidden_content_count": record.impact.hidden_content_count,
                                "retained_shared_content_count": (
                                    record.impact.retained_shared_content_count
                                ),
                            },
                            created_at=record.revoked_at,
                        )
                    )
                return _revocation_response(record, already_revoked=not created)
        finally:
            session.close()


def install_import_revocation_routes(
    application: FastAPI,
    *,
    service: ImportRevocationHttpService | None = None,
    identity_resolver: IdentityResolver | None = None,
) -> None:
    """在最终 API 装配撤销预览/执行路由，并复用与主 API 相同的身份解析语义。"""

    resolved_identity = identity_resolver or DevelopmentIdentityResolver()
    database: DatabaseRuntime | None = None

    def current_service() -> ImportRevocationHttpService:
        """测试可注入 Service；生产首次请求时惰性建立生命周期数据库连接池。"""

        nonlocal database
        if service is not None:
            return service
        if database is None:
            database = DatabaseRuntime(load_settings())
        return PostgresImportRevocationHttpService(database.new_session)

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
    )


def _preview_response(
    preview: ImportCampaignRevocationPreview,
) -> DataImportRevocationPreviewResponse:
    """构造撤销预览公共 Contract。"""

    return DataImportRevocationPreviewResponse(
        campaign_id=preview.campaign_id,
        eligible=preview.eligible,
        already_revoked=preview.already_revoked,
        impact=_impact_response(preview),
    )


def _revocation_response(
    record: ImportCampaignRevocationRecord,
    *,
    already_revoked: bool,
) -> DataImportRevocationResponse:
    """构造已提交撤销事实的公共 Contract。"""

    return DataImportRevocationResponse(
        campaign_id=record.campaign_id,
        already_revoked=already_revoked,
        impact=_impact_response(record),
        revoked_at=record.revoked_at,
    )


__all__ = [
    "PostgresImportRevocationHttpService",
    "install_import_revocation_routes",
]
