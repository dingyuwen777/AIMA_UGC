"""Stage 8D Content Excel Export Job 正式执行器。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.reporting import (
    DataExportNotFound,
    PostgresDataExportRepository,
)
from aima_ugc.contracts.export import UnifiedDataExcelV1
from aima_ugc.modules.reporting.data_export_job import (
    MAX_EXPORT_ARTIFACT_BYTES,
    DataExportJobPayload,
)
from aima_ugc.platform.export.excel import export_unified_data_excel
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol
from aima_ugc.platform.storage import ArtifactService, ArtifactSizeLimitError

from .analysis_identity import current_analysis_identity
from .runtime import PlatformRuntime

_EXPORT_PAGE_SIZE = 100


@dataclass(slots=True)
class _ExportCounters:
    content_count: int = 0
    analyzed_count: int = 0
    unanalyzed_count: int = 0


class _ExportCancelled(RuntimeError):
    pass


class PostgresDataExportJobExecutor:
    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def execute(
        self,
        *,
        payload: DataExportJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        existing = self._existing_result(payload.export_id)
        if existing is not None:
            return JobHandlerResult.succeeded(existing)

        temporary_root = self._runtime.settings.data_dir / "tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        counters = _ExportCounters()
        try:
            with TemporaryDirectory(prefix="content-export-", dir=temporary_root) as directory:
                output_path = Path(directory) / f"aima-ugc-voice-plaza-{payload.export_id}.xlsx"
                summary = export_unified_data_excel(
                    self._iter_records(payload.export_id, counters, context),
                    output_path,
                    include_analysis=True,
                )
                with output_path.open("rb") as source:
                    artifact = ArtifactService(
                        metadata=PostgresArtifactMetadataGateway(
                            self._runtime.database.new_session
                        ),
                        store=self._runtime.artifact_store,
                    ).store_stream(
                        kind="content-export.xlsx",
                        content_type=(
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        ),
                        retention_class="export",
                        source=source,
                        max_bytes=MAX_EXPORT_ARTIFACT_BYTES,
                        filename_suffix=".xlsx",
                    )
        except ArtifactSizeLimitError:
            return JobHandlerResult.failed("export_artifact_too_large")
        except DataExportNotFound:
            return JobHandlerResult.failed("export_not_found")
        except OSError:
            return JobHandlerResult.retry("export_io_error")
        except ValueError:
            return JobHandlerResult.failed("export_data_invalid")
        except _ExportCancelled:
            return JobHandlerResult.cancelled()

        stats: dict[str, object] = {
            "content_count": summary.content_rows,
            "analyzed_count": counters.analyzed_count,
            "unanalyzed_count": counters.unanalyzed_count,
            "comment_count": summary.comment_rows,
        }
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresDataExportRepository(session).attach_artifact(
                    fence=fence,
                    export_id=payload.export_id,
                    artifact_id=artifact.id,
                    stats=stats,
                )
                PostgresArtifactMetadataRepository(session).mark_linked(
                    artifact.id,
                    linked_at=datetime.now(UTC),
                )
        finally:
            session.close()
        return JobHandlerResult.succeeded(
            {
                "export_id": str(payload.export_id),
                "artifact_id": str(artifact.id),
                **stats,
            }
        )

    def _iter_records(
        self,
        export_id: UUID,
        counters: _ExportCounters,
        context: JobExecutionContextProtocol,
    ) -> Iterator[UnifiedDataExcelV1]:
        after_ordinal = -1
        while True:
            session = self._runtime.database.new_session()
            try:
                with session.begin():
                    page = PostgresDataExportRepository(
                        session,
                        analysis_identity=current_analysis_identity(self._runtime.settings),
                    ).load_page(
                        export_id,
                        after_ordinal=after_ordinal,
                        limit=_EXPORT_PAGE_SIZE,
                    )
                    export_record = PostgresDataExportRepository(session).get(export_id)
                    if export_record is None:
                        raise DataExportNotFound
                    target_count = _nonnegative_int(
                        export_record.request_snapshot.get("target_count")
                    )
            finally:
                session.close()
            if not page:
                return
            for ordinal, record in page:
                counters.content_count += 1
                if record.content.analysis is None:
                    counters.unanalyzed_count += 1
                else:
                    counters.analyzed_count += 1
                after_ordinal = ordinal
                yield record
            context.heartbeat(
                progress=min(95, int(counters.content_count * 95 / max(target_count, 1)))
            )
            if context.cancel_requested():
                raise _ExportCancelled

    def _existing_result(self, export_id: UUID) -> dict[str, object] | None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                export = PostgresDataExportRepository(session).get(export_id)
                if export is None:
                    raise DataExportNotFound
                if export.artifact_id is None or export.stats is None:
                    return None
                return {
                    "export_id": str(export.id),
                    "artifact_id": str(export.artifact_id),
                    **export.stats,
                }
        finally:
            session.close()


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


__all__ = ["PostgresDataExportJobExecutor"]
