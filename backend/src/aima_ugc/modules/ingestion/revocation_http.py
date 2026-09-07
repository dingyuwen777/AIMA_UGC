"""Data Import Campaign 撤销的 HTTP Application Service 边界。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.lifecycle import (
    DataImportRevokeRequest,
    DataImportRevocationPreviewResponse,
    DataImportRevocationResponse,
)


class ImportRevocationHttpService(Protocol):
    """公开路由只依赖业务服务，不直接访问 Ingestion 表。"""

    def preview(self, campaign_id: UUID) -> DataImportRevocationPreviewResponse: ...

    def revoke(
        self,
        campaign_id: UUID,
        body: DataImportRevokeRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> DataImportRevocationResponse: ...


__all__ = ["ImportRevocationHttpService"]
