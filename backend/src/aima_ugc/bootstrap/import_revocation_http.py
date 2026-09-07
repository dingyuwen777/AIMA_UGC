"""Data Import Campaign 撤销的 PostgreSQL Application Service 与最终路由装配。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
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
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.adapters.storage.local import LocalArtifactStore
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
from aima_ugc.platform.storage import ArtifactService
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
        """提交一次幂等撤销；缺可逆证据时在产生 Artifact 前直接拒绝。"""

        initial = self.preview(campaign_id)
        if initial.already_revoked:
            return self._load_existing_response(campaign_id)
        if not initial.eligible:
            raise HistoricalCampaignStateConflict("当前导入无法安全自动撤销")

        platforms = self._campaign_contribution_platforms(campaign_id)
        revocation_artifact = (
            self._store_revocation_artifact(campaign_id) if platforms else None
        )
        revoked_at = beijing_now()
        session = self._session_factory()
        try:
            with session.begin():
                repository = PostgresImportCampaignRevocationRepository(session)
                try:
                    record, created = ImportCampaignRevocationService(repository).revoke(
                        campaign_id,
                        actor_ref=actor_ref,
                        request_id=request_id,
                        reason=body.reason,
                        revoked_at=revoked_at,
                    )
                except ImportCampaignRevocationNotFound as exc:
                    raise HistoricalCampaignNotFound from exc
                except ImportCampaignRevocationConflict as exc:
                    raise HistoricalCampaignStateConflict from exc
                if not created:
                    return _revocation_response(record, already_revoked=True)

                lifecycle = PostgresImportRevocationLifecycleRepository(session)
                lifecycle_sources: dict[str, tuple[UUID, UUID]] = {}
                if platforms:
                    if revocation_artifact is None:
                        raise RuntimeError("撤销生命周期缺少不可变来源 Artifact")
                    lifecycle_sources = lifecycle.create_lifecycle_sources(
                        campaign_id=campaign_id,
                        raw_artifact_id=revocation_artifact.id,
                        revoked_at=revoked_at,
                    )
                versions = lifecycle.apply_campaign_revocation_with_sources(
                    campaign_id,
                    revoked_at=revoked_at,
                    lifecycle_sources=lifecycle_sources,
                )
                if revocation_artifact is not None:
                    PostgresArtifactMetadataRepository(session).mark_linked(
                        revocation_artifact.id,
                        linked_at=revoked_at,
                    )
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
                            "recomputed_content_count": len(versions),
                        },
                        created_at=record.revoked_at,
                    )
                )
                return _revocation_response(record, already_revoked=False)
        finally:
            session.close()

    def _load_existing_response(self, campaign_id: UUID) -> DataImportRevocationResponse:
        """重复点击时读取已提交事实，不创建新的 Artifact、Version 或审计。"""

        session = self._session_factory()
        try:
            with session.begin():
                record = PostgresImportCampaignRevocationRepository(session).get_revocation(
                    campaign_id
                )
                if record is None:
                    raise HistoricalCampaignNotFound
                return _revocation_response(record, already_revoked=True)
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

    def _store_revocation_artifact(self, campaign_id: UUID):
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
