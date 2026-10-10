"""Stage 8D 数据导出 HTTP Application Service 边界。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.http import (
    DataExportCreatedResponse,
    DataExportListResponse,
    DataExportResponse,
    DataExportSubmitRequest,
)
from aima_ugc.contracts.product import ExportColumnDefaultResponse, ExportColumnDefaultUpdateRequest
from aima_ugc.modules.identity import Principal


class DataExportResourceNotFound(LookupError):
    pass


class DataExportNotReady(RuntimeError):
    pass


class ExportColumnDefaultConflict(RuntimeError):
    """个人配置或列目录已被其他请求更新。"""


class ExportColumnsInvalid(ValueError):
    """请求包含当前身份不可使用的列。"""


@dataclass(frozen=True, slots=True)
class ArtifactDownload:
    content_type: str
    filename: str
    byte_size: int
    chunks: Iterator[bytes]


class ReportingHttpService(Protocol):
    def create_export(
        self,
        request: DataExportSubmitRequest,
        *,
        request_id: str,
        principal: Principal,
    ) -> DataExportCreatedResponse: ...

    def get_export(self, export_id: UUID, *, principal: Principal) -> DataExportResponse: ...

    def list_exports(self, *, principal: Principal) -> DataExportListResponse: ...

    def download_export(self, export_id: UUID, *, principal: Principal) -> ArtifactDownload: ...

    def get_column_default(self, principal: Principal) -> ExportColumnDefaultResponse: ...

    def save_column_default(
        self,
        request: ExportColumnDefaultUpdateRequest,
        *,
        principal: Principal,
    ) -> ExportColumnDefaultResponse: ...


__all__ = [
    "ArtifactDownload",
    "DataExportNotReady",
    "DataExportResourceNotFound",
    "ReportingHttpService",
]
