"""Stage 8A Processing / Import Batch 领域边界。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .import_job import (
    IMPORT_JOB_MAX_ATTEMPTS,
    IMPORT_JOB_PAYLOAD_VERSION,
    IMPORT_JOB_TIMEOUT_SECONDS,
    IMPORT_JOB_TYPE,
    ImportJobExecutor,
    ImportJobHandler,
    ImportJobPayload,
    register_import_job,
)
from .xlsx_security import (
    MAX_MULTIPART_BODY_BYTES,
    MAX_XLSX_ARCHIVE_MEMBERS,
    MAX_XLSX_COMPRESSION_RATIO,
    MAX_XLSX_FILE_BYTES,
    MAX_XLSX_MEMBER_BYTES,
    MAX_XLSX_TOTAL_UNCOMPRESSED_BYTES,
    InvalidXlsxError,
    XlsxArchiveSummary,
    XlsxResourceLimitError,
    validate_xlsx_archive,
)


@dataclass(frozen=True, slots=True)
class ProcessingImportBatchRecord:
    """一次手工数据处理的最小业务父事实。"""

    id: UUID
    input_artifact_id: UUID
    job_id: UUID | None
    status: str
    stats: dict[str, object]
    error_summary: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


__all__ = [
    "IMPORT_JOB_MAX_ATTEMPTS",
    "IMPORT_JOB_PAYLOAD_VERSION",
    "IMPORT_JOB_TIMEOUT_SECONDS",
    "IMPORT_JOB_TYPE",
    "MAX_MULTIPART_BODY_BYTES",
    "MAX_XLSX_ARCHIVE_MEMBERS",
    "MAX_XLSX_COMPRESSION_RATIO",
    "MAX_XLSX_FILE_BYTES",
    "MAX_XLSX_MEMBER_BYTES",
    "MAX_XLSX_TOTAL_UNCOMPRESSED_BYTES",
    "ImportJobExecutor",
    "ImportJobHandler",
    "ImportJobPayload",
    "InvalidXlsxError",
    "ProcessingImportBatchRecord",
    "XlsxArchiveSummary",
    "XlsxResourceLimitError",
    "register_import_job",
    "validate_xlsx_archive",
]
