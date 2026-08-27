"""Stage 12 Historical Import HTTP Application Service 边界。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.http import (
    HistoricalCampaignConflictListResponse,
    HistoricalCampaignCreatedResponse,
    HistoricalCampaignCreateRequest,
    HistoricalCampaignItemListResponse,
    HistoricalCampaignListResponse,
    HistoricalCampaignResponse,
    HistoricalDirectoryListQuery,
    HistoricalDirectoryListResponse,
    LocalDataImportCampaignCreatedResponse,
    LocalDataImportCampaignCreateRequest,
    LocalDataImportFileUploadedResponse,
)


class HistoricalCampaignNotFound(LookupError):
    """Historical Campaign 不存在。"""


class HistoricalCampaignStateConflict(RuntimeError):
    """动作与 Campaign 当前持久状态冲突。"""


class HistoricalImportUnavailable(RuntimeError):
    """管理员批准的只读历史目录尚不可用。"""


class HistoricalDirectoryRequestInvalid(ValueError):
    """目录路径、游标或扫描选择未通过安全校验。"""


class HistoricalImportHttpService(Protocol):
    def list_directories(
        self,
        query: HistoricalDirectoryListQuery,
    ) -> HistoricalDirectoryListResponse: ...

    def create_campaign(
        self,
        request: HistoricalCampaignCreateRequest,
        *,
        request_id: str,
    ) -> HistoricalCampaignCreatedResponse: ...

    def create_local_campaign(
        self,
        request: LocalDataImportCampaignCreateRequest,
        *,
        request_id: str,
    ) -> LocalDataImportCampaignCreatedResponse: ...

    def upload_local_file(
        self,
        campaign_id: UUID,
        item_id: UUID,
        *,
        filename: str,
        content_type: str | None,
        source: object,
        request_id: str,
    ) -> LocalDataImportFileUploadedResponse: ...

    def finalize_local_campaign(
        self,
        campaign_id: UUID,
        *,
        request_id: str,
    ) -> HistoricalCampaignResponse: ...

    def list_campaigns(self) -> HistoricalCampaignListResponse: ...

    def get_campaign(self, campaign_id: UUID) -> HistoricalCampaignResponse: ...

    def list_items(self, campaign_id: UUID) -> HistoricalCampaignItemListResponse: ...

    def list_conflicts(self, campaign_id: UUID) -> HistoricalCampaignConflictListResponse: ...

    def start_campaign(
        self,
        campaign_id: UUID,
        *,
        request_id: str | None = None,
    ) -> HistoricalCampaignResponse: ...

    def cancel_campaign(
        self,
        campaign_id: UUID,
        *,
        request_id: str | None = None,
    ) -> HistoricalCampaignResponse: ...

    def retry_failed(
        self,
        campaign_id: UUID,
        *,
        request_id: str | None = None,
    ) -> HistoricalCampaignResponse: ...


__all__ = [
    "HistoricalCampaignNotFound",
    "HistoricalCampaignStateConflict",
    "HistoricalDirectoryRequestInvalid",
    "HistoricalImportHttpService",
    "HistoricalImportUnavailable",
]
