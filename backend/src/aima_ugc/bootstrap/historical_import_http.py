"""Stage 3 Historical Import HTTP 覆盖层；新 Campaign 冻结 Brand/Vehicle Filter。"""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.contracts.stage3_import import (
    HistoricalCampaignCreateRequest,
    LocalDataImportCampaignCreateRequest,
)
from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot

from . import _historical_import_http_base as _base
from ._historical_import_http_base import *  # noqa: F403


class PostgresHistoricalImportHttpService(_base.PostgresHistoricalImportHttpService):
    """只覆盖 Stage 3 创建路径；上传、启动、取消、重试与查询沿用稳定基线。"""

    def create_campaign(
        self,
        request: HistoricalCampaignCreateRequest,
        *,
        request_id: str,
    ) -> _base.HistoricalCampaignCreatedResponse:
        """服务端目录 Campaign 冻结 Brand Scope；Excel Search 明确不适用。"""

        try:
            for relative_path in request.relative_paths:
                self._browser.resolve(relative_path)
        except _base.HistoricalDirectoryUnavailable as exc:
            raise _base.HistoricalDirectoryRequestInvalid from exc
        except _base.InvalidHistoricalRelativePath as exc:
            raise _base.HistoricalDirectoryRequestInvalid from exc
        filter_snapshot = self._read_brand_vehicle_filter_snapshot(request.brand_ids)
        profile_snapshot: dict[str, object] = {
            "schema_version": "historical-import-profile.v1",
            "profile": request.profile,
            "relative_paths": list(request.relative_paths),
            "chunk_rows": self._runtime.settings.historical_chunk_rows,
            "max_in_flight_jobs": self._runtime.settings.historical_max_in_flight_jobs,
        }
        # 兼容期复用既有 JSONB 列承载版本化 Snapshot；schema_version 决定语义，Stage 7 再清理旧列名。
        filter_snapshot_json = cast(
            dict[str, object],
            filter_snapshot.model_dump(mode="json"),
        )
        campaign_id = uuid4()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = _base.PostgresHistoricalImportRepository(session)
                campaign = repository.create_campaign(
                    campaign_id=campaign_id,
                    client_idempotency_key=request.client_idempotency_key,
                    root_relative_path=(
                        request.relative_paths[0] if len(request.relative_paths) == 1 else ""
                    ),
                    recursive=request.recursive,
                    profile_snapshot=profile_snapshot,
                    keyword_pack_snapshot=filter_snapshot_json,
                    source_kind="server_path",
                    ingestion_policy=request.ingestion_policy,
                )
                if (
                    campaign["profile_snapshot"] != profile_snapshot
                    or campaign["keyword_pack_snapshot"] != filter_snapshot_json
                    or campaign["recursive"] != request.recursive
                    or campaign["source_kind"] != "server_path"
                    or campaign["ingestion_policy"] != request.ingestion_policy
                ):
                    raise _base.HistoricalCampaignStateConflict(
                        "Campaign 幂等键已绑定到不同冻结输入"
                    )
                resolved_id = cast(UUID, campaign["id"])
                payload = _base.HistoricalDiscoverJobPayload(campaign_id=resolved_id)
                job = _base.PostgresJobRepository(session).enqueue(
                    job_type=_base.HISTORICAL_DISCOVER_JOB_TYPE,
                    payload_version=_base.HISTORICAL_DISCOVER_JOB_TYPE,
                    payload=payload.model_dump(mode="json"),
                    internal_idempotency_key=f"historical-discover:{resolved_id}",
                    request_id=request_id,
                    priority=_base.HISTORICAL_JOB_PRIORITY,
                    max_attempts=_base.HISTORICAL_JOB_MAX_ATTEMPTS,
                    timeout_seconds=_base.HISTORICAL_DISCOVER_TIMEOUT_SECONDS,
                )
                self._audit(
                    session,
                    event_type="historical_campaign_created",
                    campaign_id=resolved_id,
                    request_id=request_id,
                    detail={
                        "path_count": len(request.relative_paths),
                        "recursive": request.recursive,
                        "brand_filter_scope": filter_snapshot.catalog.filter_scope,
                        "selected_brand_count": len(filter_snapshot.catalog.selected_brand_ids),
                    },
                )
                return _base.HistoricalCampaignCreatedResponse(
                    campaign_id=resolved_id,
                    discovery_job_id=job.id,
                )
        except _base.HistoricalCampaignConflict as exc:
            raise _base.HistoricalCampaignStateConflict from exc
        finally:
            session.close()

    def create_local_campaign(
        self,
        request: LocalDataImportCampaignCreateRequest,
        *,
        request_id: str,
    ) -> _base.LocalDataImportCampaignCreatedResponse:
        """本地上传 Campaign 冻结同一 Brand Scope，不建立第二套过滤语义。"""

        filter_snapshot = self._read_brand_vehicle_filter_snapshot(request.brand_ids)
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
        filter_snapshot_json = cast(
            dict[str, object],
            filter_snapshot.model_dump(mode="json"),
        )
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = _base.PostgresHistoricalImportRepository(session)
                campaign = repository.create_campaign(
                    campaign_id=uuid4(),
                    client_idempotency_key=request.client_idempotency_key,
                    root_relative_path="",
                    recursive=True,
                    profile_snapshot=profile_snapshot,
                    keyword_pack_snapshot=filter_snapshot_json,
                    source_kind="local_upload",
                    ingestion_policy=request.ingestion_policy,
                    declared_file_count=len(files),
                    initial_status="uploading",
                )
                if (
                    campaign["profile_snapshot"] != profile_snapshot
                    or campaign["keyword_pack_snapshot"] != filter_snapshot_json
                    or campaign["source_kind"] != "local_upload"
                    or campaign["ingestion_policy"] != request.ingestion_policy
                    or campaign["declared_file_count"] != len(files)
                ):
                    raise _base.HistoricalCampaignStateConflict(
                        "Campaign 幂等键已绑定到不同冻结输入"
                    )
                campaign_id = cast(UUID, campaign["id"])
                items = repository.insert_local_source_items(
                    campaign_id=campaign_id,
                    files=files,
                )
                if tuple((row["relative_path"], row["file_size"]) for row in items) != tuple(
                    sorted(files)
                ):
                    raise _base.HistoricalCampaignStateConflict("本地 Campaign 上传清单不一致")
                self._audit(
                    session,
                    event_type="data_import_local_campaign_created",
                    campaign_id=campaign_id,
                    request_id=request_id,
                    detail={
                        "file_count": len(files),
                        "ingestion_policy": request.ingestion_policy,
                        "brand_filter_scope": filter_snapshot.catalog.filter_scope,
                        "selected_brand_count": len(filter_snapshot.catalog.selected_brand_ids),
                    },
                )
                return _base.LocalDataImportCampaignCreatedResponse(
                    campaign_id=campaign_id,
                    upload_items=tuple(
                        _base.LocalDataImportUploadItemResponse(
                            item_id=row["id"],
                            relative_path=row["relative_path"],
                        )
                        for row in items
                    ),
                )
        except _base.HistoricalCampaignConflict as exc:
            raise _base.HistoricalCampaignStateConflict from exc
        finally:
            session.close()

    def _read_brand_vehicle_filter_snapshot(
        self,
        brand_ids: tuple[UUID, ...],
    ) -> BrandVehicleFilterSnapshot:
        """通过 Stage 2 Catalog Lock 读取并冻结 Filter Snapshot。"""

        if len(brand_ids) > 100 or len(brand_ids) != len(set(brand_ids)):
            raise _base.HistoricalCampaignStateConflict("Brand Filter 选择不合法")
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                try:
                    catalog = PostgresBrandVehicleRepository(session).snapshot(
                        brand_ids=brand_ids or None
                    )
                except (LookupError, ValueError) as exc:
                    raise _base.HistoricalCampaignStateConflict(
                        "Brand Filter 目录不存在或不可用"
                    ) from exc
                return BrandVehicleFilterSnapshot(catalog=catalog)
        finally:
            session.close()


__all__ = [
    *getattr(_base, "__all__", ()),
    "PostgresHistoricalImportHttpService",
]
