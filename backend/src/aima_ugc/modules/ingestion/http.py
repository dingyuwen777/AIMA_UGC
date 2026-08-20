"""Stage 8B HTTP Application Service 的稳定边界与安全错误。"""

from __future__ import annotations

from typing import BinaryIO, Protocol
from uuid import UUID

from aima_ugc.contracts.http import (
    GlobalRelevanceConfigRequest,
    GlobalRelevanceConfigResponse,
    ImportBatchCreatedResponse,
    ImportBatchListQuery,
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportBatchSummaryResponse,
    JobStatusResponse,
    KeywordPackCreateRequest,
    KeywordPackKeywordCreateRequest,
    KeywordPackResponse,
)
from aima_ugc.modules.ingestion.import_batch_cursor import InvalidImportCursor


class ImportResourceNotFound(LookupError):
    """公共资源不存在。"""


class ImportConflict(RuntimeError):
    """请求与现有公共资源冲突。"""


class ImportUploadTooLarge(ValueError):
    """上传或 XLSX 解压资源超过限制。"""


class InvalidImportFile(ValueError):
    """上传不是受支持且结构合法的 XLSX。"""


class RelevanceConfigurationError(RuntimeError):
    """全局 Relevance 配置缺失、停用或为空。"""


class ImportCursorUnavailable(RuntimeError):
    """Cursor 签名 Secret 不可安全读取。"""


class ImportHttpService(Protocol):
    def create_import(
        self,
        *,
        filename: str,
        content_type: str | None,
        source: BinaryIO,
        request_id: str,
    ) -> ImportBatchCreatedResponse: ...

    def get_import_batch(self, batch_id: UUID) -> ImportBatchResponse: ...

    def list_import_batches(self, query: ImportBatchListQuery) -> ImportBatchListResponse: ...

    def get_import_batch_summary(self) -> ImportBatchSummaryResponse: ...

    def get_job(self, job_id: UUID) -> JobStatusResponse: ...

    def create_keyword_pack(self, request: KeywordPackCreateRequest) -> KeywordPackResponse: ...

    def add_keyword(
        self,
        pack_id: UUID,
        request: KeywordPackKeywordCreateRequest,
    ) -> KeywordPackResponse: ...

    def get_keyword_pack(self, pack_id: UUID) -> KeywordPackResponse: ...

    def set_global_relevance(
        self, request: GlobalRelevanceConfigRequest
    ) -> GlobalRelevanceConfigResponse: ...

    def get_global_relevance(self) -> GlobalRelevanceConfigResponse: ...


__all__ = [
    "ImportHttpService",
    "ImportConflict",
    "ImportCursorUnavailable",
    "ImportResourceNotFound",
    "ImportUploadTooLarge",
    "InvalidImportFile",
    "InvalidImportCursor",
    "RelevanceConfigurationError",
]
