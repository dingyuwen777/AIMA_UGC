"""Stage 12 Historical Campaign 的 PostgreSQL Owner Repository。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import case, func, insert, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from aima_ugc.modules.ingestion.historical_directory import HistoricalDirectoryEntry
from aima_ugc.modules.ingestion.historical_jobs import (
    HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
    HISTORICAL_IMPORT_TIMEOUT_SECONDS,
    HISTORICAL_JOB_MAX_ATTEMPTS,
    HISTORICAL_JOB_PRIORITY,
    HISTORICAL_SNAPSHOT_JOB_TYPE,
    HISTORICAL_SNAPSHOT_TIMEOUT_SECONDS,
    HistoricalImportChunkJobPayload,
    HistoricalSnapshotJobPayload,
)
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
    processing_import_batch_identities_table,
    processing_import_batch_item_conflicts_table,
    processing_import_batch_items_table,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.time import beijing_now

from .jobs import PostgresJobRepository


class HistoricalCampaignConflict(RuntimeError):
    pass


class HistoricalCampaignNotFound(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class HistoricalCampaignProgress:
    """从 Campaign Item 与 Job 持久状态聚合的可恢复进度。"""

    preflight_completed_file_count: int
    preflight_percent: int
    migration_completed_row_count: int
    migration_percent: int
    failed_chunk_count: int


class PostgresHistoricalImportRepository:
    """只写 Ingestion Owner 表；Content 仍由专用历史批量入口写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_campaign(self, campaign_id: UUID, *, for_update: bool = False) -> RowMapping | None:
        statement = select(historical_import_campaigns_table).where(
            historical_import_campaigns_table.c.id == campaign_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.execute(statement).mappings().one_or_none()

    def get_campaign_by_idempotency_key(self, key: str) -> RowMapping | None:
        return (
            self._session.execute(
                select(historical_import_campaigns_table).where(
                    historical_import_campaigns_table.c.client_idempotency_key == key
                )
            )
            .mappings()
            .one_or_none()
        )

    def list_campaigns(self, *, limit: int = 100) -> tuple[RowMapping, ...]:
        return tuple(
            self._session.execute(
                select(historical_import_campaigns_table)
                .order_by(
                    historical_import_campaigns_table.c.created_at.desc(),
                    historical_import_campaigns_table.c.id.desc(),
                )
                .limit(limit)
            ).mappings()
        )

    def campaign_progresses(
        self,
        campaign_ids: Iterable[UUID],
    ) -> dict[UUID, HistoricalCampaignProgress]:
        """集合式聚合进度，避免 Campaign 列表产生逐项数据库往返。"""

        unique_ids = tuple(dict.fromkeys(campaign_ids))
        if not unique_ids:
            return {}

        item = historical_import_campaign_items_table
        source_progress = case(
            (item.c.status == "discovered", 0),
            (item.c.status == "snapshotting", func.coalesce(jobs_table.c.progress, 0)),
            else_=100,
        )
        source_totals = (
            select(
                item.c.campaign_id.label("campaign_id"),
                func.count()
                .filter(item.c.status.not_in(("discovered", "snapshotting")))
                .label("completed_file_count"),
                func.coalesce(func.sum(source_progress), 0).label("progress_points"),
            )
            .select_from(item.outerjoin(jobs_table, jobs_table.c.id == item.c.job_id))
            .where(
                item.c.item_kind == "source_file",
                item.c.campaign_id.in_(unique_ids),
            )
            .group_by(item.c.campaign_id)
            .subquery()
        )
        chunk_totals = (
            select(
                item.c.campaign_id.label("campaign_id"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                item.c.status.in_(("succeeded", "failed", "cancelled")),
                                item.c.row_count,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("completed_row_count"),
                func.count().filter(item.c.status == "failed").label("failed_chunk_count"),
            )
            .where(
                item.c.item_kind == "chunk",
                item.c.campaign_id.in_(unique_ids),
            )
            .group_by(item.c.campaign_id)
            .subquery()
        )
        rows = self._session.execute(
            select(
                historical_import_campaigns_table.c.id,
                historical_import_campaigns_table.c.discovered_file_count,
                historical_import_campaigns_table.c.total_rows,
                func.coalesce(source_totals.c.completed_file_count, 0).label(
                    "completed_file_count"
                ),
                func.coalesce(source_totals.c.progress_points, 0).label("progress_points"),
                func.coalesce(chunk_totals.c.completed_row_count, 0).label("completed_row_count"),
                func.coalesce(chunk_totals.c.failed_chunk_count, 0).label("failed_chunk_count"),
            )
            .outerjoin(
                source_totals,
                source_totals.c.campaign_id == historical_import_campaigns_table.c.id,
            )
            .outerjoin(
                chunk_totals,
                chunk_totals.c.campaign_id == historical_import_campaigns_table.c.id,
            )
            .where(historical_import_campaigns_table.c.id.in_(unique_ids))
        ).mappings()
        result: dict[UUID, HistoricalCampaignProgress] = {}
        for row in rows:
            discovered_file_count = int(row["discovered_file_count"])
            total_rows = int(row["total_rows"])
            completed_file_count = min(
                discovered_file_count,
                int(row["completed_file_count"]),
            )
            completed_row_count = min(total_rows, int(row["completed_row_count"]))
            result[row["id"]] = HistoricalCampaignProgress(
                preflight_completed_file_count=completed_file_count,
                preflight_percent=_bounded_percent(
                    int(row["progress_points"]),
                    discovered_file_count * 100,
                ),
                migration_completed_row_count=completed_row_count,
                migration_percent=_bounded_percent(completed_row_count, total_rows),
                failed_chunk_count=int(row["failed_chunk_count"]),
            )
        return result

    def create_campaign(
        self,
        *,
        campaign_id: UUID,
        client_idempotency_key: str,
        root_relative_path: str,
        recursive: bool,
        profile_snapshot: dict[str, object],
        keyword_pack_snapshot: dict[str, object],
        source_kind: str = "server_path",
        ingestion_policy: str = "historical_fill_only",
        declared_file_count: int = 0,
        initial_status: str = "discovering",
    ) -> RowMapping:
        inserted = (
            self._session.execute(
                pg_insert(historical_import_campaigns_table)
                .values(
                    id=campaign_id,
                    client_idempotency_key=client_idempotency_key,
                    source_kind=source_kind,
                    ingestion_policy=ingestion_policy,
                    declared_file_count=declared_file_count,
                    root_relative_path=root_relative_path,
                    recursive=recursive,
                    profile_snapshot=profile_snapshot,
                    keyword_pack_snapshot=keyword_pack_snapshot,
                    status=initial_status,
                    stats={},
                    created_at=func.clock_timestamp(),
                )
                .on_conflict_do_nothing(
                    index_elements=[historical_import_campaigns_table.c.client_idempotency_key]
                )
                .returning(*historical_import_campaigns_table.c)
            )
            .mappings()
            .one_or_none()
        )
        if inserted is not None:
            return inserted
        existing = self.get_campaign_by_idempotency_key(client_idempotency_key)
        if existing is None:
            raise HistoricalCampaignConflict("Campaign 幂等创建发生并发冲突")
        return existing

    def insert_local_source_items(
        self,
        *,
        campaign_id: UUID,
        files: tuple[tuple[str, int], ...],
    ) -> tuple[RowMapping, ...]:
        """冻结浏览器声明的相对路径与大小，并返回稳定上传 Item。"""

        created_at = beijing_now()
        values = [
            {
                "id": uuid4(),
                "campaign_id": campaign_id,
                "item_kind": "source_file",
                "relative_path": relative_path,
                "manifest_identity": _local_manifest_identity(relative_path, byte_size),
                "file_size": byte_size,
                "row_count": 0,
                "status": "discovered",
                "attempt_count": 0,
                "stats": {"declared_byte_size": byte_size},
                "created_at": created_at,
            }
            for relative_path, byte_size in files
        ]
        if values:
            self._session.execute(
                pg_insert(historical_import_campaign_items_table)
                .values(values)
                .on_conflict_do_nothing()
            )
        return tuple(
            self._session.execute(
                select(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.item_kind == "source_file",
                )
                .order_by(historical_import_campaign_items_table.c.relative_path)
            ).mappings()
        )

    def insert_source_items(
        self,
        *,
        campaign_id: UUID,
        entries: tuple[HistoricalDirectoryEntry, ...],
    ) -> None:
        created_at = beijing_now()
        values: list[dict[str, object]] = [
            {
                "id": uuid4(),
                "campaign_id": campaign_id,
                "item_kind": "source_file",
                "relative_path": entry.relative_path,
                "manifest_identity": _manifest_identity(entry),
                "file_size": entry.byte_size,
                "file_mtime_ns": entry.modified_at_ns,
                "row_count": 0,
                "status": "discovered",
                "attempt_count": 0,
                "stats": {},
                "created_at": created_at,
            }
            for entry in entries
        ]
        if values:
            self._session.execute(insert(historical_import_campaign_items_table), values)

    def get_item(self, item_id: UUID, *, for_update: bool = False) -> RowMapping | None:
        statement = select(historical_import_campaign_items_table).where(
            historical_import_campaign_items_table.c.id == item_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.execute(statement).mappings().one_or_none()

    def get_chunk(self, parent_item_id: UUID, ordinal: int) -> RowMapping | None:
        return (
            self._session.execute(
                select(historical_import_campaign_items_table).where(
                    historical_import_campaign_items_table.c.parent_item_id == parent_item_id,
                    historical_import_campaign_items_table.c.item_kind == "chunk",
                    historical_import_campaign_items_table.c.ordinal == ordinal,
                )
            )
            .mappings()
            .one_or_none()
        )

    def list_items(self, campaign_id: UUID, *, limit: int = 200) -> tuple[RowMapping, ...]:
        """有界返回优先需要处置的 Item，避免大 Campaign 明细拖垮页面。"""

        item = historical_import_campaign_items_table
        status_priority = case(
            {
                "failed": 0,
                "cancelled": 1,
                "running": 2,
                "queued": 3,
                "snapshotting": 4,
                "discovered": 5,
                "ready": 6,
                "succeeded": 7,
            },
            value=item.c.status,
            else_=8,
        )
        return tuple(
            self._session.execute(
                select(item)
                .where(item.c.campaign_id == campaign_id)
                .order_by(
                    status_priority,
                    case((item.c.item_kind == "source_file", 0), else_=1),
                    item.c.relative_path,
                    item.c.ordinal.nullsfirst(),
                    item.c.id,
                )
                .limit(limit)
            ).mappings()
        )

    def count_items(self, campaign_id: UUID) -> int:
        return cast(
            int,
            self._session.scalar(
                select(func.count()).where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id
                )
            )
            or 0,
        )

    def list_conflicts(self, campaign_id: UUID, *, limit: int = 500) -> tuple[RowMapping, ...]:
        conflict = processing_import_batch_item_conflicts_table
        ledger = processing_import_batch_items_table
        item = historical_import_campaign_items_table
        return tuple(
            self._session.execute(
                select(
                    conflict.c.batch_item_id,
                    ledger.c.source_row_ordinal,
                    ledger.c.content_id,
                    conflict.c.field_name,
                    conflict.c.content_version,
                    conflict.c.current_value_hash,
                    conflict.c.historical_value_hash,
                    conflict.c.created_at,
                )
                .join(ledger, ledger.c.id == conflict.c.batch_item_id)
                .join(item, item.c.id == ledger.c.campaign_item_id)
                .where(item.c.campaign_id == campaign_id)
                .order_by(conflict.c.created_at, conflict.c.id)
                .limit(limit)
            ).mappings()
        )

    def count_conflicts(self, campaign_id: UUID) -> int:
        conflict = processing_import_batch_item_conflicts_table
        ledger = processing_import_batch_items_table
        item = historical_import_campaign_items_table
        return cast(
            int,
            self._session.scalar(
                select(func.count())
                .select_from(conflict)
                .join(ledger, ledger.c.id == conflict.c.batch_item_id)
                .join(item, item.c.id == ledger.c.campaign_item_id)
                .where(item.c.campaign_id == campaign_id)
            )
            or 0,
        )

    def mark_discovered(self, campaign_id: UUID, *, file_count: int) -> None:
        self._session.execute(
            update(historical_import_campaigns_table)
            .where(
                historical_import_campaigns_table.c.id == campaign_id,
                historical_import_campaigns_table.c.status == "discovering",
            )
            .values(
                status="snapshotting",
                discovered_file_count=file_count,
                declared_file_count=file_count,
            )
        )

    def schedule_snapshot_jobs(self, campaign_id: UUID, *, max_in_flight: int) -> int:
        if self.get_campaign(campaign_id, for_update=True) is None:
            raise HistoricalCampaignNotFound
        active = cast(
            int,
            self._session.scalar(
                select(func.count())
                .select_from(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.item_kind == "source_file",
                    historical_import_campaign_items_table.c.status.in_(("snapshotting",)),
                )
            )
            or 0,
        )
        slots = max(0, max_in_flight - active)
        if slots == 0:
            return 0
        rows = tuple(
            self._session.execute(
                select(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.item_kind == "source_file",
                    historical_import_campaign_items_table.c.status == "discovered",
                )
                .order_by(historical_import_campaign_items_table.c.relative_path)
                .limit(slots)
                .with_for_update(skip_locked=True)
            ).mappings()
        )
        jobs = PostgresJobRepository(self._session)
        for row in rows:
            item_id = cast(UUID, row["id"])
            attempt = cast(int, row["attempt_count"]) + 1
            payload = HistoricalSnapshotJobPayload(campaign_item_id=item_id)
            job = jobs.enqueue(
                job_type=HISTORICAL_SNAPSHOT_JOB_TYPE,
                payload_version=HISTORICAL_SNAPSHOT_JOB_TYPE,
                payload=payload.model_dump(mode="json"),
                internal_idempotency_key=f"historical-snapshot:{item_id}:{attempt}",
                request_id=None,
                priority=HISTORICAL_JOB_PRIORITY,
                max_attempts=HISTORICAL_JOB_MAX_ATTEMPTS,
                timeout_seconds=HISTORICAL_SNAPSHOT_TIMEOUT_SECONDS,
            )
            self._session.execute(
                update(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.id == item_id,
                    historical_import_campaign_items_table.c.status == "discovered",
                )
                .values(status="snapshotting", job_id=job.id, attempt_count=attempt)
            )
        return len(rows)

    def create_chunk(
        self,
        *,
        source_item: RowMapping,
        artifact_id: UUID,
        sha256: str,
        ordinal: int,
        row_start: int,
        row_end: int,
        row_count: int,
        stats: dict[str, object],
    ) -> UUID:
        existing = (
            self._session.execute(
                select(historical_import_campaign_items_table).where(
                    historical_import_campaign_items_table.c.parent_item_id == source_item["id"],
                    historical_import_campaign_items_table.c.item_kind == "chunk",
                    historical_import_campaign_items_table.c.ordinal == ordinal,
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if (
                existing["sha256"] != sha256
                or existing["row_start"] != row_start
                or existing["row_end"] != row_end
                or existing["row_count"] != row_count
            ):
                raise HistoricalCampaignConflict("同一 Chunk ordinal 已绑定到不同不可变内容")
            return cast(UUID, existing["id"])
        item_id = uuid4()
        self._session.execute(
            insert(historical_import_campaign_items_table).values(
                id=item_id,
                campaign_id=source_item["campaign_id"],
                parent_item_id=source_item["id"],
                item_kind="chunk",
                relative_path=source_item["relative_path"],
                manifest_identity=source_item["manifest_identity"],
                ordinal=ordinal,
                artifact_id=artifact_id,
                sha256=sha256,
                row_start=row_start,
                row_end=row_end,
                row_count=row_count,
                status="ready",
                stats=stats,
                created_at=func.clock_timestamp(),
            )
        )
        return item_id

    def bind_source_artifact(
        self,
        *,
        item_id: UUID,
        artifact_id: UUID,
        sha256: str,
    ) -> None:
        """在解析前冻结源 Artifact，使同一技术 Job 重试复用相同输入。"""

        bound = self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.id == item_id,
                historical_import_campaign_items_table.c.item_kind == "source_file",
                historical_import_campaign_items_table.c.status == "snapshotting",
                historical_import_campaign_items_table.c.artifact_id.is_(None),
            )
            .values(artifact_id=artifact_id, sha256=sha256)
            .returning(historical_import_campaign_items_table.c.id)
        ).scalar_one_or_none()
        if bound is not None:
            return
        current = self.get_item(item_id)
        if (
            current is not None
            and current["artifact_id"] == artifact_id
            and current["sha256"] == sha256
        ):
            return
        raise HistoricalCampaignConflict("Historical Source Item 已绑定到其他 Artifact")

    def bind_local_source_artifact(
        self,
        *,
        campaign_id: UUID,
        item_id: UUID,
        artifact_id: UUID,
        sha256: str,
        byte_size: int,
    ) -> None:
        """只允许 uploading Campaign 把声明 Item 绑定到一个不可变 Artifact。"""

        campaign = self.get_campaign(campaign_id, for_update=True)
        item = self.get_item(item_id, for_update=True)
        if campaign is None or item is None or item["campaign_id"] != campaign_id:
            raise HistoricalCampaignNotFound
        if campaign["source_kind"] != "local_upload" or campaign["status"] != "uploading":
            raise HistoricalCampaignConflict("Campaign 当前不接受本地文件上传")
        if item["item_kind"] != "source_file" or item["file_size"] != byte_size:
            raise HistoricalCampaignConflict("上传文件与冻结清单不一致")
        if item["artifact_id"] is not None:
            if item["artifact_id"] == artifact_id and item["sha256"] == sha256:
                return
            raise HistoricalCampaignConflict("本地 Source Item 已绑定到其他 Artifact")
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.id == item_id,
                historical_import_campaign_items_table.c.artifact_id.is_(None),
            )
            .values(artifact_id=artifact_id, sha256=sha256)
        )

    def finalize_local_upload(self, campaign_id: UUID) -> None:
        """确认声明文件全部冻结后，进入复用的快照/预检队列。"""

        campaign = self.get_campaign(campaign_id, for_update=True)
        if campaign is None:
            raise HistoricalCampaignNotFound
        if campaign["source_kind"] != "local_upload":
            raise HistoricalCampaignConflict("只有本地上传 Campaign 需要 finalize")
        if campaign["status"] in {"snapshotting", "ready"}:
            return
        if campaign["status"] != "uploading":
            raise HistoricalCampaignConflict("Campaign 当前状态不能完成上传")
        source_count, uploaded_count = self._session.execute(
            select(
                func.count(),
                func.count().filter(
                    historical_import_campaign_items_table.c.artifact_id.is_not(None)
                ),
            ).where(
                historical_import_campaign_items_table.c.campaign_id == campaign_id,
                historical_import_campaign_items_table.c.item_kind == "source_file",
            )
        ).one()
        if int(source_count) != int(campaign["declared_file_count"]) or int(uploaded_count) != int(
            source_count
        ):
            raise HistoricalCampaignConflict("本地文件尚未全部形成不可变 Artifact")
        self._session.execute(
            update(historical_import_campaigns_table)
            .where(
                historical_import_campaigns_table.c.id == campaign_id,
                historical_import_campaigns_table.c.status == "uploading",
            )
            .values(
                status="snapshotting",
                discovered_file_count=source_count,
                finished_at=None,
            )
        )

    def complete_source_snapshot(
        self,
        *,
        item_id: UUID,
        artifact_id: UUID,
        sha256: str,
        row_count: int,
        stats: dict[str, object],
    ) -> None:
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.id == item_id,
                historical_import_campaign_items_table.c.status == "snapshotting",
            )
            .values(
                artifact_id=artifact_id,
                sha256=sha256,
                row_count=row_count,
                status="ready",
                stats=stats,
                finished_at=func.clock_timestamp(),
            )
        )

    def fail_item(self, item_id: UUID, *, error_code: str) -> None:
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.id == item_id,
                historical_import_campaign_items_table.c.status.in_(
                    ("discovered", "snapshotting", "queued", "running")
                ),
            )
            .values(status="failed", error_code=error_code, finished_at=func.clock_timestamp())
        )

    def cancel_item(self, item_id: UUID) -> None:
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.id == item_id,
                historical_import_campaign_items_table.c.status.in_(
                    ("discovered", "snapshotting", "ready", "queued", "running")
                ),
            )
            .values(status="cancelled", finished_at=func.clock_timestamp())
        )

    def fail_campaign(self, campaign_id: UUID, *, error_code: str) -> None:
        self._session.execute(
            update(historical_import_campaigns_table)
            .where(
                historical_import_campaigns_table.c.id == campaign_id,
                historical_import_campaigns_table.c.status.in_(("discovering", "snapshotting")),
            )
            .values(
                status="failed",
                error_summary=error_code,
                finished_at=func.clock_timestamp(),
            )
        )

    def finalize_preflight(self, campaign_id: UUID) -> str:
        rows = self._source_status_counts(campaign_id)
        total = sum(rows.values())
        terminal = rows.get("ready", 0) + rows.get("failed", 0) + rows.get("cancelled", 0)
        if terminal < total:
            return "snapshotting"
        if total == 0 or rows.get("failed", 0) or rows.get("cancelled", 0):
            status = "failed"
        else:
            status = "ready"
        ready = rows.get("ready", 0)
        total_rows = cast(
            int,
            self._session.scalar(
                select(
                    func.coalesce(
                        func.sum(historical_import_campaign_items_table.c.row_count),
                        0,
                    )
                ).where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.item_kind == "source_file",
                )
            )
            or 0,
        )
        self._session.execute(
            update(historical_import_campaigns_table)
            .where(
                historical_import_campaigns_table.c.id == campaign_id,
                historical_import_campaigns_table.c.status == "snapshotting",
            )
            .values(
                status=status,
                ready_item_count=ready,
                total_rows=total_rows,
                finished_at=func.clock_timestamp() if status == "failed" else None,
            )
        )
        return status

    def prepare_campaign_start(self, campaign_id: UUID) -> tuple[tuple[UUID, UUID], ...]:
        campaign = self.get_campaign(campaign_id, for_update=True)
        if campaign is None:
            raise HistoricalCampaignNotFound
        if campaign["status"] != "ready":
            raise HistoricalCampaignConflict("Campaign 尚未完成全部预检")
        source_rows = tuple(
            self._session.execute(
                select(historical_import_campaign_items_table).where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.item_kind == "source_file",
                    historical_import_campaign_items_table.c.status == "ready",
                )
            ).mappings()
        )
        batches: list[tuple[UUID, UUID]] = []
        policy_version = _batch_policy_version(cast(str, campaign["ingestion_policy"]))
        for source in source_rows:
            artifact_id = cast(UUID | None, source["artifact_id"])
            if artifact_id is None:
                raise HistoricalCampaignConflict("预检成功文件缺少不可变 Artifact")
            batch_id = uuid4()
            self._session.execute(
                insert(processing_import_batches_table).values(
                    id=batch_id,
                    input_artifact_id=artifact_id,
                    status="processing",
                    stats={"stage": "queued", "source_item_id": str(source["id"])},
                    historical_mode=policy_version == "historical-fill-only.v1",
                    historical_campaign_item_id=source["id"],
                    historical_policy_version=policy_version,
                    created_at=func.clock_timestamp(),
                )
            )
            batches.append((cast(UUID, source["id"]), batch_id))
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.campaign_id == campaign_id,
                historical_import_campaign_items_table.c.item_kind == "source_file",
                historical_import_campaign_items_table.c.status == "ready",
            )
            .values(status="queued")
        )
        self._session.execute(
            update(historical_import_campaigns_table)
            .where(
                historical_import_campaigns_table.c.id == campaign_id,
                historical_import_campaigns_table.c.status == "ready",
            )
            .values(status="queued", started_at=func.clock_timestamp(), finished_at=None)
        )
        return tuple(batches)

    def prepare_failed_retry(self, campaign_id: UUID) -> dict[UUID, UUID]:
        """只重置失败 Chunk，并为其来源创建引用同一快照 Artifact 的新 Batch。"""

        campaign = self.get_campaign(campaign_id, for_update=True)
        if campaign is None:
            raise HistoricalCampaignNotFound
        if campaign["status"] not in {"partial_failed", "failed"}:
            raise HistoricalCampaignConflict("Campaign 当前没有可重试失败项")
        failed_chunks = tuple(
            self._session.execute(
                select(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.item_kind == "chunk",
                    historical_import_campaign_items_table.c.status == "failed",
                )
                .with_for_update()
            ).mappings()
        )
        if not failed_chunks:
            raise HistoricalCampaignConflict("Campaign 当前没有失败 Chunk")
        source_ids = {cast(UUID, row["parent_item_id"]) for row in failed_chunks}
        previous = self.source_batches(campaign_id)
        source_rows = {
            cast(UUID, row["id"]): row
            for row in self._session.execute(
                select(historical_import_campaign_items_table).where(
                    historical_import_campaign_items_table.c.id.in_(tuple(source_ids))
                )
            ).mappings()
        }
        batches: dict[UUID, UUID] = {}
        policy_version = _batch_policy_version(cast(str, campaign["ingestion_policy"]))
        for source_id in sorted(source_ids, key=str):
            source = source_rows[source_id]
            artifact_id = cast(UUID | None, source["artifact_id"])
            if artifact_id is None:
                raise HistoricalCampaignConflict("失败项来源缺少不可变 Artifact")
            previous_batch_id = previous.get(source_id)
            batch_id = uuid4()
            self._session.execute(
                insert(processing_import_batches_table).values(
                    id=batch_id,
                    input_artifact_id=artifact_id,
                    status="processing",
                    stats={"stage": "retry_queued", "source_item_id": str(source_id)},
                    historical_mode=policy_version == "historical-fill-only.v1",
                    historical_campaign_item_id=source_id,
                    historical_policy_version=policy_version,
                    retry_of_batch_id=previous_batch_id,
                    created_at=func.clock_timestamp(),
                )
            )
            if previous_batch_id is not None:
                self._session.execute(
                    insert(processing_import_batch_identities_table).from_select(
                        ["batch_id", "identity_hash", "first_row_ordinal"],
                        select(
                            literal(batch_id),
                            processing_import_batch_identities_table.c.identity_hash,
                            processing_import_batch_identities_table.c.first_row_ordinal,
                        ).where(
                            processing_import_batch_identities_table.c.batch_id == previous_batch_id
                        ),
                    )
                )
            batches[source_id] = batch_id
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.id.in_(
                    tuple(row["id"] for row in failed_chunks)
                )
            )
            .values(
                status="ready",
                job_id=None,
                error_code=None,
                started_at=None,
                finished_at=None,
            )
        )
        self._session.execute(
            update(historical_import_campaigns_table)
            .where(historical_import_campaigns_table.c.id == campaign_id)
            .values(status="queued", error_summary=None, finished_at=None)
        )
        return batches

    def schedule_import_jobs(
        self,
        *,
        campaign_id: UUID,
        source_batches: dict[UUID, UUID],
        max_in_flight: int,
    ) -> int:
        if self.get_campaign(campaign_id, for_update=True) is None:
            raise HistoricalCampaignNotFound
        active = cast(
            int,
            self._session.scalar(
                select(func.count())
                .select_from(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.item_kind == "chunk",
                    historical_import_campaign_items_table.c.status.in_(("queued", "running")),
                )
            )
            or 0,
        )
        slots = max(0, max_in_flight - active)
        if slots == 0:
            return 0
        chunk = historical_import_campaign_items_table
        active_chunk = historical_import_campaign_items_table.alias("active_historical_chunk")
        active_for_same_source = (
            select(active_chunk.c.id)
            .where(
                active_chunk.c.campaign_id == campaign_id,
                active_chunk.c.item_kind == "chunk",
                active_chunk.c.parent_item_id == chunk.c.parent_item_id,
                active_chunk.c.status.in_(("queued", "running")),
            )
            .exists()
        )
        ranked_ready = (
            select(
                chunk.c.id.label("chunk_id"),
                func.row_number()
                .over(
                    partition_by=chunk.c.parent_item_id,
                    order_by=chunk.c.ordinal,
                )
                .label("source_rank"),
            )
            .where(
                chunk.c.campaign_id == campaign_id,
                chunk.c.item_kind == "chunk",
                chunk.c.status == "ready",
                chunk.c.parent_item_id.in_(tuple(source_batches)),
                ~active_for_same_source,
            )
            .subquery("ranked_ready_historical_chunks")
        )
        chunk_rows = tuple(
            self._session.execute(
                select(chunk)
                .join(ranked_ready, ranked_ready.c.chunk_id == chunk.c.id)
                .where(
                    ranked_ready.c.source_rank == 1,
                )
                .order_by(
                    chunk.c.relative_path,
                    chunk.c.ordinal,
                )
                .limit(slots)
                .with_for_update(of=chunk, skip_locked=True)
            ).mappings()
        )
        jobs = PostgresJobRepository(self._session)
        for chunk_row in chunk_rows:
            chunk_id = cast(UUID, chunk_row["id"])
            parent_id = cast(UUID, chunk_row["parent_item_id"])
            batch_id = source_batches[parent_id]
            attempt = cast(int, chunk_row["attempt_count"]) + 1
            payload = HistoricalImportChunkJobPayload(batch_id=batch_id, chunk_item_id=chunk_id)
            job = jobs.enqueue(
                job_type=HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
                payload_version=HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
                payload=payload.model_dump(mode="json"),
                internal_idempotency_key=f"historical-import-chunk:{chunk_id}:{attempt}",
                request_id=None,
                priority=HISTORICAL_JOB_PRIORITY,
                max_attempts=HISTORICAL_JOB_MAX_ATTEMPTS,
                timeout_seconds=HISTORICAL_IMPORT_TIMEOUT_SECONDS,
            )
            self._session.execute(
                update(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.id == chunk_id,
                    historical_import_campaign_items_table.c.status == "ready",
                )
                .values(status="queued", job_id=job.id, attempt_count=attempt)
            )
        return len(chunk_rows)

    def source_batches(self, campaign_id: UUID) -> dict[UUID, UUID]:
        rows = self._session.execute(
            select(
                processing_import_batches_table.c.id,
                processing_import_batches_table.c.historical_campaign_item_id,
            )
            .join(
                historical_import_campaign_items_table,
                historical_import_campaign_items_table.c.id
                == processing_import_batches_table.c.historical_campaign_item_id,
            )
            .where(historical_import_campaign_items_table.c.campaign_id == campaign_id)
            .order_by(processing_import_batches_table.c.created_at)
        )
        return {cast(UUID, row.historical_campaign_item_id): cast(UUID, row.id) for row in rows}

    def request_cancel(self, campaign_id: UUID) -> None:
        campaign = self.get_campaign(campaign_id, for_update=True)
        if campaign is None:
            raise HistoricalCampaignNotFound
        if campaign["status"] == "uploading":
            if campaign["source_kind"] != "local_upload":
                raise HistoricalCampaignConflict("Campaign 当前状态不可取消")
            # 本地字节尚未全部冻结时没有 Job 可接管，直接把清单和 Campaign 收敛到终态。
            self._session.execute(
                update(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.item_kind == "source_file",
                    historical_import_campaign_items_table.c.status == "discovered",
                )
                .values(status="cancelled", finished_at=func.clock_timestamp())
            )
            self._session.execute(
                update(historical_import_campaigns_table)
                .where(historical_import_campaigns_table.c.id == campaign_id)
                .values(status="cancelled", finished_at=func.clock_timestamp())
            )
            return
        if campaign["status"] not in {"queued", "running", "cancelling"}:
            raise HistoricalCampaignConflict("Campaign 当前状态不可取消")
        self._session.execute(
            update(historical_import_campaigns_table)
            .where(historical_import_campaigns_table.c.id == campaign_id)
            .values(status="cancelling")
        )
        job_items = tuple(
            self._session.execute(
                select(
                    historical_import_campaign_items_table.c.id,
                    historical_import_campaign_items_table.c.job_id,
                ).where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.job_id.is_not(None),
                    historical_import_campaign_items_table.c.status.in_(
                        ("snapshotting", "queued", "running")
                    ),
                )
            )
        )
        jobs = PostgresJobRepository(self._session)
        for item_id, job_id in job_items:
            job = jobs.request_cancel(cast(UUID, job_id))
            if job.status == "cancelled":
                self._session.execute(
                    update(historical_import_campaign_items_table)
                    .where(
                        historical_import_campaign_items_table.c.id == item_id,
                        historical_import_campaign_items_table.c.status == "queued",
                    )
                    .values(status="cancelled", finished_at=func.clock_timestamp())
                )
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.campaign_id == campaign_id,
                historical_import_campaign_items_table.c.item_kind == "chunk",
                historical_import_campaign_items_table.c.status == "ready",
            )
            .values(status="cancelled", finished_at=func.clock_timestamp())
        )
        remaining_chunks = cast(
            int,
            self._session.scalar(
                select(func.count())
                .select_from(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.item_kind == "chunk",
                    historical_import_campaign_items_table.c.status.not_in(
                        ("succeeded", "failed", "cancelled")
                    ),
                )
            )
            or 0,
        )
        if remaining_chunks == 0:
            campaign_stats = self._campaign_accounting_counts(campaign_id)
            self._session.execute(
                update(historical_import_campaigns_table)
                .where(historical_import_campaigns_table.c.id == campaign_id)
                .values(
                    status="cancelled",
                    stats=campaign_stats,
                    finished_at=func.clock_timestamp(),
                )
            )
        processing_batches = tuple(
            self._session.execute(
                select(
                    processing_import_batches_table.c.id,
                    processing_import_batches_table.c.historical_campaign_item_id,
                    processing_import_batches_table.c.stats,
                ).where(
                    processing_import_batches_table.c.historical_campaign_item_id.in_(
                        select(historical_import_campaign_items_table.c.id).where(
                            historical_import_campaign_items_table.c.campaign_id == campaign_id,
                            historical_import_campaign_items_table.c.item_kind == "source_file",
                        )
                    ),
                    processing_import_batches_table.c.status == "processing",
                )
            ).mappings()
        )
        for batch in processing_batches:
            batch_counts = self._batch_accounting_counts(
                cast(UUID, batch["id"]),
                cast(UUID, batch["historical_campaign_item_id"]),
            )
            self._session.execute(
                update(processing_import_batches_table)
                .where(processing_import_batches_table.c.id == batch["id"])
                .values(
                    status="failed",
                    stats=merge_stats(
                        cast(dict[str, object], batch["stats"] or {}),
                        batch_counts.items(),
                    ),
                    error_summary="historical_campaign_cancelled",
                    finished_at=func.clock_timestamp(),
                )
            )
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.campaign_id == campaign_id,
                historical_import_campaign_items_table.c.item_kind == "source_file",
                historical_import_campaign_items_table.c.status.in_(("queued", "running")),
            )
            .values(status="cancelled", finished_at=func.clock_timestamp())
        )

    def mark_chunk_running(self, item_id: UUID) -> None:
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.id == item_id,
                historical_import_campaign_items_table.c.status == "queued",
            )
            .values(status="running", started_at=func.clock_timestamp())
        )
        parent_id = self._session.scalar(
            select(historical_import_campaign_items_table.c.parent_item_id).where(
                historical_import_campaign_items_table.c.id == item_id
            )
        )
        if parent_id is not None:
            self._session.execute(
                update(historical_import_campaign_items_table)
                .where(
                    historical_import_campaign_items_table.c.id == parent_id,
                    historical_import_campaign_items_table.c.status == "queued",
                )
                .values(status="running", started_at=func.clock_timestamp())
            )
        campaign_id = self._session.scalar(
            select(historical_import_campaign_items_table.c.campaign_id).where(
                historical_import_campaign_items_table.c.id == item_id
            )
        )
        if campaign_id is not None:
            self._session.execute(
                update(historical_import_campaigns_table)
                .where(
                    historical_import_campaigns_table.c.id == campaign_id,
                    historical_import_campaigns_table.c.status == "queued",
                )
                .values(status="running")
            )

    def complete_chunk(self, item_id: UUID, *, stats: dict[str, object]) -> None:
        self._session.execute(
            update(historical_import_campaign_items_table)
            .where(
                historical_import_campaign_items_table.c.id == item_id,
                historical_import_campaign_items_table.c.status == "running",
            )
            .values(status="succeeded", stats=stats, finished_at=func.clock_timestamp())
        )

    def refresh_batch_and_campaign(self, *, campaign_id: UUID, batch_id: UUID) -> str:
        source_id = cast(
            UUID,
            self._session.scalar(
                select(processing_import_batches_table.c.historical_campaign_item_id).where(
                    processing_import_batches_table.c.id == batch_id
                )
            ),
        )
        batch_counts = self._batch_accounting_counts(batch_id, source_id)
        chunk_statuses = tuple(
            self._session.execute(
                select(historical_import_campaign_items_table.c.status).where(
                    historical_import_campaign_items_table.c.parent_item_id == source_id,
                    historical_import_campaign_items_table.c.item_kind == "chunk",
                )
            ).scalars()
        )
        if chunk_statuses and all(
            value in {"succeeded", "failed", "cancelled"} for value in chunk_statuses
        ):
            has_failed = any(value == "failed" for value in chunk_statuses)
            has_cancelled = any(value == "cancelled" for value in chunk_statuses)
            batch_status = "failed" if has_failed or has_cancelled else "succeeded"
            source_status = (
                "failed" if has_failed else "cancelled" if has_cancelled else "succeeded"
            )
            current_stats = cast(
                dict[str, object],
                self._session.scalar(
                    select(processing_import_batches_table.c.stats).where(
                        processing_import_batches_table.c.id == batch_id
                    )
                )
                or {},
            )
            self._session.execute(
                update(processing_import_batches_table)
                .where(
                    processing_import_batches_table.c.id == batch_id,
                    processing_import_batches_table.c.status == "processing",
                )
                .values(
                    status=batch_status,
                    stats=merge_stats(current_stats, batch_counts.items()),
                    error_summary="historical_chunk_failed" if batch_status == "failed" else None,
                    finished_at=func.clock_timestamp(),
                )
            )
            self._session.execute(
                update(historical_import_campaign_items_table)
                .where(historical_import_campaign_items_table.c.id == source_id)
                .values(status=source_status, finished_at=func.clock_timestamp())
            )
        campaign_statuses = tuple(
            self._session.execute(
                select(historical_import_campaign_items_table.c.status).where(
                    historical_import_campaign_items_table.c.campaign_id == campaign_id,
                    historical_import_campaign_items_table.c.item_kind == "chunk",
                )
            ).scalars()
        )
        if campaign_statuses and all(
            value in {"succeeded", "failed", "cancelled"} for value in campaign_statuses
        ):
            if any(value == "failed" for value in campaign_statuses):
                status = (
                    "partial_failed"
                    if any(value == "succeeded" for value in campaign_statuses)
                    else "failed"
                )
            elif any(value == "cancelled" for value in campaign_statuses):
                status = "cancelled"
            else:
                status = "succeeded"
            campaign_stats = self._campaign_accounting_counts(campaign_id)
            self._session.execute(
                update(historical_import_campaigns_table)
                .where(historical_import_campaigns_table.c.id == campaign_id)
                .values(
                    status=status,
                    stats=campaign_stats,
                    finished_at=func.clock_timestamp(),
                )
            )
            return status
        return "running"

    def _source_status_counts(self, campaign_id: UUID) -> dict[str, int]:
        rows = self._session.execute(
            select(
                historical_import_campaign_items_table.c.status,
                func.count().label("count"),
            )
            .where(
                historical_import_campaign_items_table.c.campaign_id == campaign_id,
                historical_import_campaign_items_table.c.item_kind == "source_file",
            )
            .group_by(historical_import_campaign_items_table.c.status)
        )
        return {cast(str, row.status): cast(int, row.count) for row in rows}

    def _ledger_counts(self, batch_id: UUID) -> dict[str, int]:
        rows = self._session.execute(
            select(processing_import_batch_items_table.c.outcome, func.count().label("count"))
            .where(processing_import_batch_items_table.c.batch_id == batch_id)
            .group_by(processing_import_batch_items_table.c.outcome)
        )
        return {cast(str, row.outcome): cast(int, row.count) for row in rows}

    def _batch_accounting_counts(self, batch_id: UUID, source_id: UUID) -> dict[str, int]:
        counts = self._ledger_counts(batch_id)
        failed_rows = self._terminal_unprocessed_row_count(
            historical_import_campaign_items_table.c.parent_item_id == source_id
        )
        if failed_rows:
            counts["failed"] = counts.get("failed", 0) + failed_rows
        return counts

    def _campaign_ledger_counts(self, campaign_id: UUID) -> dict[str, int]:
        rows = self._session.execute(
            select(processing_import_batch_items_table.c.outcome, func.count().label("count"))
            .join(
                historical_import_campaign_items_table,
                historical_import_campaign_items_table.c.id
                == processing_import_batch_items_table.c.campaign_item_id,
            )
            .where(historical_import_campaign_items_table.c.campaign_id == campaign_id)
            .group_by(processing_import_batch_items_table.c.outcome)
        )
        return {cast(str, row.outcome): cast(int, row.count) for row in rows}

    def _campaign_accounting_counts(self, campaign_id: UUID) -> dict[str, int]:
        counts = self._campaign_ledger_counts(campaign_id)
        failed_rows = self._terminal_unprocessed_row_count(
            historical_import_campaign_items_table.c.campaign_id == campaign_id
        )
        if failed_rows:
            counts["failed"] = counts.get("failed", 0) + failed_rows
        return counts

    def _terminal_unprocessed_row_count(self, scope: ColumnElement[bool]) -> int:
        """用冻结 Chunk 行数对账未进入事务的失败或取消区间。"""

        value = self._session.scalar(
            select(
                func.coalesce(
                    func.sum(historical_import_campaign_items_table.c.row_count),
                    0,
                )
            ).where(
                scope,
                historical_import_campaign_items_table.c.item_kind == "chunk",
                historical_import_campaign_items_table.c.status.in_(("failed", "cancelled")),
            )
        )
        return int(value or 0)


def merge_stats(
    existing: dict[str, object],
    updates: Iterable[tuple[str, int]],
) -> dict[str, object]:
    result = dict(existing)
    for key, value in updates:
        result[key] = value
    return result


def _bounded_percent(completed: int, total: int) -> int:
    """用整数运算返回 0..100，避免大规模行数转换为浮点数。"""

    if total <= 0:
        return 0
    return max(0, min(100, completed * 100 // total))


def _manifest_identity(entry: HistoricalDirectoryEntry) -> str:
    payload = json.dumps(
        [entry.relative_path, entry.byte_size, entry.modified_at_ns],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _local_manifest_identity(relative_path: str, byte_size: int) -> str:
    payload = json.dumps(
        [relative_path, byte_size],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _batch_policy_version(ingestion_policy: str) -> str:
    if ingestion_policy == "historical_fill_only":
        return "historical-fill-only.v1"
    if ingestion_policy == "standard_observation":
        return "standard-observation.v1"
    raise HistoricalCampaignConflict("Campaign 写入策略不受支持")


__all__ = [
    "HistoricalCampaignConflict",
    "HistoricalCampaignNotFound",
    "HistoricalCampaignProgress",
    "PostgresHistoricalImportRepository",
]
