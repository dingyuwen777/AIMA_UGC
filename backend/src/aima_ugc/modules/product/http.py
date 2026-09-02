"""Count、可用状态、导出列与站内通知服务边界。"""

from __future__ import annotations

from typing import Protocol

from aima_ugc.contracts.http import ContentCountRequest
from aima_ugc.contracts.product import (
    ContentAvailabilityObservationRequest,
    ContentAvailabilityResponse,
    ContentCountResponse,
    ExportColumnCatalogResponse,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationMarkReadResponse,
)
from aima_ugc.modules.identity import Principal


class ProductResourceNotFound(LookupError):
    """U5 产品能力引用的资源不存在。"""


class ProductConflict(RuntimeError):
    """U5 产品动作与当前业务状态冲突。"""


class ProductHttpService(Protocol):
    """Count、可用状态、列目录和 Principal Inbox 的 HTTP 边界。"""

    def count_contents(self, request: ContentCountRequest) -> ContentCountResponse:
        """执行有界内容计数。"""

        ...

    def observe_availability(
        self,
        request: ContentAvailabilityObservationRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ContentAvailabilityResponse:
        """追加可审计的可用状态观察。"""

        ...

    def get_export_column_catalog(self) -> ExportColumnCatalogResponse:
        """返回版本化导出列白名单。"""

        ...

    def list_notifications(self, principal: Principal, *, limit: int) -> NotificationListResponse:
        """读取当前 Principal 的 Inbox。"""

        ...

    def mark_notifications_read(
        self, principal: Principal, request: NotificationMarkReadRequest
    ) -> NotificationMarkReadResponse:
        """标记当前 Principal 自己的通知已读。"""

        ...


__all__ = ["ProductConflict", "ProductHttpService", "ProductResourceNotFound"]
