"""Stage 12 Historical Import 的 HTTP 事务与持久 Job 编排。"""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
from typing import BinaryIO, Literal, cast
from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.historical_import import (
    HistoricalCampaignConflict,
    HistoricalCampaignProgress,
    PostgresHistoricalImportRepository,
)
from aima_ugc.adapters.persistence.postgres.historical_import import (
    HistoricalCampaignNotFound as RepositoryCampaignNotFound,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.contracts.http import (
    HistoricalCampaignConflictListResponse,
    HistoricalCampaignConflictResponse,
    HistoricalCampaignCreatedResponse,
    HistoricalCampaignCreateRequest,
    HistoricalCampaignItemListResponse,
    HistoricalCampaignItemResponse,
    HistoricalCampaignListResponse,
    HistoricalCampaignProgressResponse,
    HistoricalCampaignResponse,
    HistoricalCampaignStatsResponse,
    HistoricalCampaignStatus,
    HistoricalDirectoryEntryResponse,
    HistoricalDirectoryListQuery,
    HistoricalDirectoryListResponse,
    LocalDataImportCampaignCreatedResponse,
    LocalDataImportCampaignCreateRequest,
    LocalDataImportFileUploadedResponse,
    LocalDataImportUploadItemResponse,
)
from aima_ugc.modules.ingestion.historical_directory import (
    HistoricalDirectoryBrowser,
    HistoricalDirectoryUnavailable,
    InvalidHistoricalDirectoryCursor,
    InvalidHistoricalRelativePath,
)
from aima_ugc.modules.ingestion.historical_http import (
    HistoricalCampaignNotFound,
    HistoricalCampaignStateConflict,
    HistoricalDirectoryRequestInvalid,
)
from aima_ugc.modules.ingestion.historical_jobs import (
    HISTORICAL_DISCOVER_JOB_TYPE,
    HISTORICAL_DISCOVER_TIMEOUT_SECONDS,
    HISTORICAL_JOB_MAX_ATTEMPTS,
    HISTORICAL_JOB_PRIORITY,
    HistoricalDiscoverJobPayload,
)
from aima_ugc.modules.ingestion.http import ImportUploadTooLarge, InvalidImportFile
from aima_ugc.modules.ingestion.xlsx_security import MAX_XLSX_FILE_BYTES
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.storage import ArtifactRecord, ArtifactService, ArtifactSizeLimitError
from aima_ugc.platform.time import beijing_now

from .import_http import read_import_keyword_selection
from .runtime import PlatformRuntime


class PostgresHistoricalImportHttpService:
    """HTTP 请求只建立 Campaign/Job；目录扫描、快照和导入均由 Worker 执行。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime
        self._browser = HistoricalDirectoryBrowser(runtime.settings.historical_import_root)

    def list_directories(
        self,
        query: HistoricalDirectoryListQuery,
    ) -> HistoricalDirectoryListResponse:
        try:
            page = self._browser.list_entries(
                relative_path=query.relative_path,
                cursor=query.cursor,
                limit=query.limit,
            )
        except HistoricalDirectoryUnavailable as exc:
            return HistoricalDirectoryListResponse(
                available=False,
                unavailable_reason=str(exc),
            )
        except (InvalidHistoricalDirectoryCursor, InvalidHistoricalRelativePath) as exc:
            raise HistoricalDirectoryRequestInvalid from exc
        return HistoricalDirectoryListResponse(
            available=True,
            items=tuple(
                HistoricalDirectoryEntryResponse(
                    relative_path=item.relative_path,
                    name=item.name,
                    kind=cast(Literal["directory", "file"], item.kind),
                    byte_size=item.byte_size,
                    modified_at_ns=item.modified_at_ns,
                )
                for item in page.items
            ),
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        )

    def create_campaign(
        self,
        request: HistoricalCampaignCreateRequest,
        *,
        request_id: str,
    ) -> HistoricalCampaignCreatedResponse:
        try:
            for relative_path in request.relative_paths:
                self._browser.resolve(relative_path)
        except HistoricalDirectoryUnavailable as exc:
            raise HistoricalDirectoryRequestInvalid from exc
        except InvalidHistoricalRelativePath as exc:
            raise HistoricalDirectoryRequestInvalid from exc
        selection = read_import_keyword_selection(
            self._runtime, request.keyword_pack_ids, request.vehicle_model_ids
        )
        profile_snapshot: dict[str, object] = {
            "schema_version": "historical-import-profile.v1",
            "profile": request.profile,
            "relative_paths": list(request.relative_paths),
            "chunk_rows": self._runtime.settings.historical_chunk_rows,
            "max_in_flight_jobs": self._runtime.settings.historical_max_in_flight_jobs,
        }
        keyword_snapshot = cast(
            dict[str, object],
            selection.model_dump(mode="json"),
        )
        campaign_id = uuid4()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresHistoricalImportRepository(session)
                campaign = repository.create_campaign(
                    campaign_id=campaign_id,
                    client_idempotency_key=request.client_idempotency_key,
                    root_relative_path=(
                        request.relative_paths[0] if len(request.relative_paths) == 1 else ""
                    ),
                    recursive=request.recursive,
                    profile_snapshot=profile_snapshot,
                    keyword_pack_snapshot=keyword_snapshot,
                    source_kind="server_path",
                    ingestion_policy=request.ingestion_policy,
                )
                if (
                    campaign["profile_snapshot"] != profile_snapshot
                    or campaign["keyword_pack_snapshot"] != keyword_snapshot
                    or campaign["recursive"] != request.recursive
                    or campaign["source_kind"] != "server_path"
                    or campaign["ingestion_policy"] != request.ingestion_policy
                ):
                    raise HistoricalCampaignStateConflict("Campaign 幂等键已绑定到不同冻结输入")
                resolved_id = cast(UUID, campaign["id"])
                payload = HistoricalDiscoverJobPayload(campaign_id=resolved_id)
                job = PostgresJobRepository(session).enqueue(
                    job_type=HISTORICAL_DISCOVER_JOB_TYPE,
                    payload_version=HISTORICAL_DISCOVER_JOB_TYPE,
                    payload=payload.model_dump(mode="json"),
                    internal_idempotency_key=f"historical-discover:{resolved_id}",
                    request_id=request_id,
                    priority=HISTORICAL_JOB_PRIORITY,
                    max_attempts=HISTORICAL_JOB_MAX_ATTEMPTS,
                    timeout_seconds=HISTORICAL_DISCOVER_TIMEOUT_SECONDS,
                )
                self._audit(
                    session,
                    event_type="historical_campaign_created",
                    campaign_id=resolved_id,
                    request_id=request_id,
                    detail={
                        "path_count": len(request.relative_paths),
                        "recursive": request.recursive,
                    },
                )
                return HistoricalCampaignCreatedResponse(
                    campaign_id=resolved_id,
                    discovery_job_id=job.id,
                )
        except HistoricalCampaignConflict as exc:
            raise HistoricalCampaignStateConflict from exc
        finally:
            session.close()

    def create_local_campaign(
        self,
        request: LocalDataImportCampaignCreateRequest,
        *,
        request_id: str,
    ) -> LocalDataImportCampaignCreatedResponse:
        selection = read_import_keyword_selection(
            self._runtime, request.keyword_pack_ids, request.vehicle_model_ids
        )
        files = tuple((item.relative_path, item.byte_size) for item in request.files)
        profile_snapshot: dict[str, object] = {
            "schema_version": "data-import-profile.v2",
            "source_kind": "local_upload",
            "profile": request.profile,
            "files": [
                {"relative_path": relative_path, "byte_size": byte_size}
                for relative_path, byte_size in files
            ],
            "chunk_rows": self._runtime.settings.historical_chunk_rows,
            "max_in_flight_jobs": self._runtime.settings.historical_max_in_flight_jobs,
        }
        keyword_snapshot = cast(dict[str, object], selection.model_dump(mode="json"))
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresHistoricalImportRepository(session)
                campaign = repository.create_campaign(
                    campaign_id=uuid4(),
                    client_idempotency_key=request.client_idempotency_key,
                    root_relative_path="",
                    recursive=True,
                    profile_snapshot=profile_snapshot,
                    keyword_pack_snapshot=keyword_snapshot,
                    source_kind="local_upload",
                    ingestion_policy=request.ingestion_policy,
                    declared_file_count=len(files),
                    initial_status="uploading",
                )
                if (
                    campaign["profile_snapshot"] != profile_snapshot
                    or campaign["keyword_pack_snapshot"] != keyword_snapshot
                    or campaign["source_kind"] != "local_upload"
                    or campaign["ingestion_policy"] != request.ingestion_policy
                    or campaign["declared_file_count"] != len(files)
                ):
                    raise HistoricalCampaignStateConflict("Campaign 幂等键已绑定到不同冻结输入")
                campaign_id = cast(UUID, campaign["id"])
                items = repository.insert_local_source_items(
                    campaign_id=campaign_id,
                    files=files,
                )
                if tuple((row["relative_path"], row["file_size"]) for row in items) != tuple(
                    sorted(files)
                ):
                    raise HistoricalCampaignStateConflict("本地 Campaign 上传清单不一致")
                self._audit(
                    session,
                    event_type="data_import_local_campaign_created",
                    campaign_id=campaign_id,
                    request_id=request_id,
                    detail={
                        "file_count": len(files),
                        "ingestion_policy": request.ingestion_policy,
                    },
                )
                return LocalDataImportCampaignCreatedResponse(
                    campaign_id=campaign_id,
                    upload_items=tuple(
                        LocalDataImportUploadItemResponse(
                            item_id=row["id"],
                            relative_path=row["relative_path"],
                        )
                        for row in items
                    ),
                )
        except HistoricalCampaignConflict as exc:
            raise HistoricalCampaignStateConflict from exc
        finally:
            session.close()

    def upload_local_file(
        self,
        campaign_id: UUID,
        item_id: UUID,
        *,
        filename: str,
        content_type: str | None,
        source: object,
        request_id: str,
    ) -> LocalDataImportFileUploadedResponse:
        del content_type
        upload = cast(BinaryIO, source)
        item, existing = self._local_upload_target(campaign_id, item_id)
        expected_name = PurePosixPath(cast(str, item["relative_path"])).name
        if filename != expected_name or not filename.casefold().endswith(".xlsx"):
            raise InvalidImportFile
        try:
            upload.seek(0, 2)
            byte_size = upload.tell()
            upload.seek(0)
        except (OSError, ValueError) as exc:
            raise InvalidImportFile from exc
        if byte_size != item["file_size"]:
            raise InvalidImportFile
        if existing is not None:
            if existing.sha256 != _stream_sha256(upload):
                raise InvalidImportFile
            return _local_upload_response(campaign_id, item_id, existing)

        artifacts = ArtifactService(
            metadata=PostgresArtifactMetadataGateway(self._runtime.database.new_session),
            store=self._runtime.artifact_store,
        )
        try:
            artifact = artifacts.store_stream(
                kind="data-import.source",
                content_type=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                retention_class="raw",
                source=upload,
                max_bytes=MAX_XLSX_FILE_BYTES,
                filename_suffix=".xlsx",
            )
        except ArtifactSizeLimitError as exc:
            raise ImportUploadTooLarge from exc
        if artifact.sha256 is None or artifact.byte_size is None:
            raise InvalidImportFile
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresHistoricalImportRepository(session)
                repository.bind_local_source_artifact(
                    campaign_id=campaign_id,
                    item_id=item_id,
                    artifact_id=artifact.id,
                    sha256=artifact.sha256,
                    byte_size=artifact.byte_size,
                )
                # Artifact 关系与 linked 状态必须同事务提交，避免崩溃后被保留策略误删。
                PostgresArtifactMetadataRepository(session).mark_linked(
                    artifact.id,
                    linked_at=beijing_now(),
                )
                self._audit(
                    session,
                    event_type="data_import_local_file_uploaded",
                    campaign_id=campaign_id,
                    request_id=request_id,
                    detail={"item_id": str(item_id), "byte_size": artifact.byte_size},
                )
        except RepositoryCampaignNotFound as exc:
            raise HistoricalCampaignNotFound from exc
        except HistoricalCampaignConflict as exc:
            raise HistoricalCampaignStateConflict from exc
        finally:
            session.close()
        return _local_upload_response(campaign_id, item_id, artifact)

    def finalize_local_campaign(
        self,
        campaign_id: UUID,
        *,
        request_id: str,
    ) -> HistoricalCampaignResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresHistoricalImportRepository(session)
                repository.finalize_local_upload(campaign_id)
                repository.schedule_snapshot_jobs(
                    campaign_id,
                    max_in_flight=self._runtime.settings.historical_max_in_flight_jobs,
                )
                self._audit(
                    session,
                    event_type="data_import_local_campaign_finalized",
                    campaign_id=campaign_id,
                    request_id=request_id,
                    detail={},
                )
                row = repository.get_campaign(campaign_id)
                if row is None:
                    raise HistoricalCampaignNotFound
                progress = repository.campaign_progresses((campaign_id,))[campaign_id]
                return _campaign_response(row, progress)
        except RepositoryCampaignNotFound as exc:
            raise HistoricalCampaignNotFound from exc
        except HistoricalCampaignConflict as exc:
            raise HistoricalCampaignStateConflict from exc
        finally:
            session.close()

    def _local_upload_target(
        self,
        campaign_id: UUID,
        item_id: UUID,
    ) -> tuple[RowMapping, ArtifactRecord | None]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresHistoricalImportRepository(session)
                campaign = repository.get_campaign(campaign_id)
                item = repository.get_item(item_id)
                if (
                    campaign is None
                    or item is None
                    or item["campaign_id"] != campaign_id
                    or campaign["source_kind"] != "local_upload"
                ):
                    raise HistoricalCampaignNotFound
                if campaign["status"] != "uploading" or item["status"] != "discovered":
                    raise HistoricalCampaignStateConflict("Campaign 当前不接受本地文件上传")
                artifact_id = cast(UUID | None, item["artifact_id"])
                existing = (
                    PostgresArtifactMetadataRepository(session).get(artifact_id)
                    if artifact_id is not None
                    else None
                )
                if existing is not None and (
                    existing.storage_status not in {"stored", "linked"}
                    or existing.sha256 != item["sha256"]
                    or existing.byte_size != item["file_size"]
                ):
                    raise HistoricalCampaignStateConflict(
                        "本地 Source Item 的不可变 Artifact 不可用"
                    )
                return item, existing
        finally:
            session.close()

    def list_campaigns(self) -> HistoricalCampaignListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresHistoricalImportRepository(session)
                rows = repository.list_campaigns()
                progresses = repository.campaign_progresses(row["id"] for row in rows)
                return HistoricalCampaignListResponse(
                    items=tuple(_campaign_response(row, progresses[row["id"]]) for row in rows)
                )
        finally:
            session.close()

    def get_campaign(self, campaign_id: UUID) -> HistoricalCampaignResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresHistoricalImportRepository(session)
                row = repository.get_campaign(campaign_id)
                if row is None:
                    raise HistoricalCampaignNotFound
                progress = repository.campaign_progresses((campaign_id,))[campaign_id]
                return _campaign_response(row, progress)
        finally:
            session.close()

    def list_items(self, campaign_id: UUID) -> HistoricalCampaignItemListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresHistoricalImportRepository(session)
                if repository.get_campaign(campaign_id) is None:
                    raise HistoricalCampaignNotFound
                rows = repository.list_items(campaign_id)
                total_count = repository.count_items(campaign_id)
                return HistoricalCampaignItemListResponse(
                    items=tuple(_item_response(row) for row in rows),
                    total_count=total_count,
                    has_more=total_count > len(rows),
                )
        finally:
            session.close()

    def list_conflicts(self, campaign_id: UUID) -> HistoricalCampaignConflictListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresHistoricalImportRepository(session)
                if repository.get_campaign(campaign_id) is None:
                    raise HistoricalCampaignNotFound
                rows = repository.list_conflicts(campaign_id)
                total_count = repository.count_conflicts(campaign_id)
                return HistoricalCampaignConflictListResponse(
                    items=tuple(
                        HistoricalCampaignConflictResponse.model_validate(dict(row)) for row in rows
                    ),
                    total_count=total_count,
                    has_more=total_count > len(rows),
                )
        finally:
            session.close()

    def start_campaign(
        self,
        campaign_id: UUID,
        *,
        request_id: str | None = None,
    ) -> HistoricalCampaignResponse:
        return self._change_campaign(
            campaign_id,
            action="start",
            request_id=request_id,
        )

    def cancel_campaign(
        self,
        campaign_id: UUID,
        *,
        request_id: str | None = None,
    ) -> HistoricalCampaignResponse:
        return self._change_campaign(
            campaign_id,
            action="cancel",
            request_id=request_id,
        )

    def retry_failed(
        self,
        campaign_id: UUID,
        *,
        request_id: str | None = None,
    ) -> HistoricalCampaignResponse:
        return self._change_campaign(
            campaign_id,
            action="retry",
            request_id=request_id,
        )

    def _change_campaign(
        self,
        campaign_id: UUID,
        *,
        action: str,
        request_id: str | None,
    ) -> HistoricalCampaignResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresHistoricalImportRepository(session)
                if action == "start":
                    batches = dict(repository.prepare_campaign_start(campaign_id))
                    scheduled = repository.schedule_import_jobs(
                        campaign_id=campaign_id,
                        source_batches=batches,
                        max_in_flight=self._runtime.settings.historical_max_in_flight_jobs,
                    )
                    if scheduled == 0:
                        raise HistoricalCampaignConflict("Campaign 没有可执行 Chunk")
                elif action == "cancel":
                    repository.request_cancel(campaign_id)
                elif action == "retry":
                    batches = repository.prepare_failed_retry(campaign_id)
                    scheduled = repository.schedule_import_jobs(
                        campaign_id=campaign_id,
                        source_batches=batches,
                        max_in_flight=self._runtime.settings.historical_max_in_flight_jobs,
                    )
                    if scheduled == 0:
                        raise HistoricalCampaignConflict("Campaign 没有可重试 Chunk")
                else:
                    raise AssertionError("未知 Historical Campaign 动作")
                self._audit(
                    session,
                    event_type=f"historical_campaign_{action}",
                    campaign_id=campaign_id,
                    request_id=request_id,
                    detail={},
                )
                row = repository.get_campaign(campaign_id)
                if row is None:
                    raise HistoricalCampaignNotFound
                progress = repository.campaign_progresses((campaign_id,))[campaign_id]
                return _campaign_response(row, progress)
        except RepositoryCampaignNotFound as exc:
            raise HistoricalCampaignNotFound from exc
        except HistoricalCampaignConflict as exc:
            raise HistoricalCampaignStateConflict from exc
        finally:
            session.close()

    @staticmethod
    def _audit(
        session: Session,
        *,
        event_type: str,
        campaign_id: UUID,
        request_id: str | None,
        detail: dict[str, object],
    ) -> None:
        PostgresAuditRepository(session).append(
            AuditEvent(
                id=uuid4(),
                actor_kind="system",
                actor_ref=None,
                event_type=event_type,
                object_type="historical_import_campaign",
                object_id=str(campaign_id),
                request_id=request_id,
                safe_detail=cast(dict[str, JsonValue], detail),
                created_at=beijing_now(),
            )
        )


def _campaign_response(
    row: RowMapping,
    progress: HistoricalCampaignProgress,
) -> HistoricalCampaignResponse:
    raw_stats = cast(dict[str, object], row["stats"] or {})
    stats = HistoricalCampaignStatsResponse(
        **{
            name: value
            for name in HistoricalCampaignStatsResponse.model_fields
            if isinstance((value := raw_stats.get(name)), int)
            and not isinstance(value, bool)
            and value >= 0
        }
    )
    return HistoricalCampaignResponse(
        id=row["id"],
        status=cast(HistoricalCampaignStatus, row["status"]),
        source_kind=row["source_kind"],
        ingestion_policy=row["ingestion_policy"],
        declared_file_count=row["declared_file_count"],
        root_relative_path=row["root_relative_path"],
        recursive=row["recursive"],
        discovered_file_count=row["discovered_file_count"],
        ready_item_count=row["ready_item_count"],
        total_rows=row["total_rows"],
        failed_chunk_count=progress.failed_chunk_count,
        progress=HistoricalCampaignProgressResponse(
            preflight_completed_file_count=progress.preflight_completed_file_count,
            preflight_percent=progress.preflight_percent,
            migration_completed_row_count=progress.migration_completed_row_count,
            migration_percent=progress.migration_percent,
        ),
        stats=stats,
        error_summary=row["error_summary"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def _item_response(row: RowMapping) -> HistoricalCampaignItemResponse:
    return HistoricalCampaignItemResponse.model_validate(
        {name: row[name] for name in HistoricalCampaignItemResponse.model_fields}
    )


def _local_upload_response(
    campaign_id: UUID,
    item_id: UUID,
    artifact: ArtifactRecord,
) -> LocalDataImportFileUploadedResponse:
    artifact_id = artifact.id
    sha256 = artifact.sha256
    byte_size = artifact.byte_size
    if sha256 is None or byte_size is None:
        raise InvalidImportFile
    return LocalDataImportFileUploadedResponse(
        campaign_id=campaign_id,
        item_id=item_id,
        artifact_id=artifact_id,
        sha256=sha256,
        byte_size=byte_size,
    )


def _stream_sha256(source: BinaryIO) -> str:
    """流式校验重复 PUT，避免同一 Item 静默接受不同内容。"""

    digest = hashlib.sha256()
    try:
        source.seek(0)
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
        source.seek(0)
    except (OSError, ValueError) as exc:
        raise InvalidImportFile from exc
    return digest.hexdigest()


__all__ = ["PostgresHistoricalImportHttpService"]
