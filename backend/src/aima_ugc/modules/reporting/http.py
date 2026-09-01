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


class DataExportResourceNotFound(LookupError):
    pass


class DataExportNotReady(RuntimeError):
    pass


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
        actor_ref: str,
    ) -> DataExportCreatedResponse: ...

    def get_export(self, export_id: UUID) -> DataExportResponse: ...

    def list_exports(self) -> DataExportListResponse: ...

    def download_export(self, export_id: UUID) -> ArtifactDownload: ...


__all__ = [
    "ArtifactDownload",
    "DataExportNotReady",
    "DataExportResourceNotFound",
    "ReportingHttpService",
]
