"""U5 产品能力 PostgreSQL HTTP Application Service。"""

from __future__ import annotations

from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.content_product import (
    PostgresContentProductRepository,
)
from aima_ugc.adapters.persistence.postgres.notifications import (
    PostgresNotificationRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.contracts.http import ContentCountRequest
from aima_ugc.contracts.product import (
    ContentAvailabilityObservationRequest,
    ContentAvailabilityResponse,
    ContentCountResponse,
    ExportColumnCatalogResponse,
    ExportColumnResponse,
    NotificationItemResponse,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationMarkReadResponse,
)
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.product import ProductResourceNotFound
from aima_ugc.modules.reporting.column_catalog import (
    EXPORT_COLUMN_CATALOG_VERSION,
    EXPORT_COLUMNS,
)
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.time import beijing_now

from .analysis_identity import active_analysis_configuration
from .runtime import PlatformRuntime


class PostgresProductHttpService:
    """U5 Count、可用状态、导出目录和 Principal Inbox 应用服务。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        """绑定统一 Platform Runtime。"""

        self._runtime = runtime

    def count_contents(self, request: ContentCountRequest) -> ContentCountResponse:
        """执行 none、受限 exact 或有条件 estimated 计数。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configuration = active_analysis_configuration(session, self._runtime.settings)
                repository = PostgresContentProductRepository(
                    session,
                    analysis_identity=configuration.identity,
                )
                if request.count_mode == "none":
                    return ContentCountResponse(
                        count_mode="none",
                        count=None,
                        count_kind="none",
                        as_of=beijing_now(),
                    )
                if request.count_mode == "estimated":
                    estimate = repository.estimated_count(request.filters)
                    return ContentCountResponse(
                        count_mode="estimated",
                        count=estimate,
                        count_kind="estimated" if estimate is not None else "none",
                        as_of=beijing_now(),
                    )
                assert request.exact_limit is not None
                count, truncated = repository.exact_count(
                    request.filters, limit=request.exact_limit
                )
                return ContentCountResponse(
                    count_mode="exact",
                    count=None if truncated else count,
                    count_kind="none" if truncated else "exact",
                    as_of=beijing_now(),
                    truncated=truncated,
                )
        finally:
            session.close()

    def observe_availability(
        self,
        request: ContentAvailabilityObservationRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ContentAvailabilityResponse:
        """由管理员追加可审计的 Provider-neutral 可用状态观察。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configuration = active_analysis_configuration(session, self._runtime.settings)
                try:
                    content_version, observed_at = PostgresContentProductRepository(
                        session,
                        analysis_identity=configuration.identity,
                    ).append_availability(request)
                except LookupError as exc:
                    raise ProductResourceNotFound from exc
                PostgresAuditRepository(session).append(
                    AuditEvent(
                        id=uuid4(),
                        actor_kind="principal",
                        actor_ref=principal.principal_id,
                        event_type="content_availability_observed",
                        object_type="content",
                        object_id=str(request.content_id),
                        request_id=request_id,
                        safe_detail={
                            "content_version": content_version,
                            "status": request.status,
                            "reason_code": request.reason_code,
                            "evidence_kind": request.evidence_kind,
                        },
                        created_at=observed_at,
                    )
                )
                return ContentAvailabilityResponse(
                    status=request.status,
                    reason_code=request.reason_code,
                    evidence_kind=request.evidence_kind,
                    observed_at=observed_at,
                )
        finally:
            session.close()

    def get_export_column_catalog(self) -> ExportColumnCatalogResponse:
        """返回 Reporting Owner 维护的当前安全列白名单。"""

        return ExportColumnCatalogResponse(
            version=EXPORT_COLUMN_CATALOG_VERSION,
            columns=tuple(
                ExportColumnResponse(
                    key=item.key,
                    label=item.label,
                    sensitive=item.sensitive,
                    default_selected=item.default_selected,
                )
                for item in EXPORT_COLUMNS
            ),
        )

    def list_notifications(self, principal: Principal, *, limit: int) -> NotificationListResponse:
        """读取当前 Principal 自己的 Inbox。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                rows, unread = PostgresNotificationRepository(session).list_for_principal(
                    principal.principal_id, limit=limit
                )
                return NotificationListResponse(
                    items=tuple(
                        NotificationItemResponse(
                            id=row["id"],
                            event_type=row["event_type"],
                            title=row["title"],
                            message=row["message"],
                            resource_type=row["resource_type"],
                            resource_id=row["resource_id"],
                            is_read=row["is_read"],
                            created_at=row["created_at"],
                            read_at=row["read_at"],
                        )
                        for row in rows
                    ),
                    unread_count=unread,
                )
        finally:
            session.close()

    def mark_notifications_read(
        self, principal: Principal, request: NotificationMarkReadRequest
    ) -> NotificationMarkReadResponse:
        """幂等标记当前 Principal 自己的通知已读。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                changed = PostgresNotificationRepository(session).mark_read(
                    principal.principal_id, request.item_ids
                )
                return NotificationMarkReadResponse(
                    requested_count=len(request.item_ids), changed_count=changed
                )
        finally:
            session.close()


__all__ = ["PostgresProductHttpService"]
