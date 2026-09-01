"""Stage 8D durable Content Excel Export PostgreSQL Owner/Read Adapter。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.contracts.analysis import ContentRelevance, ContentVoiceType
from aima_ugc.contracts.export import (
    UnifiedDataExcelAnalysisV1,
    UnifiedDataExcelCommentV1,
    UnifiedDataExcelContentV1,
    UnifiedDataExcelLabelPairV1,
    UnifiedDataExcelV1,
)
from aima_ugc.contracts.platform import require_platform_name
from aima_ugc.modules.analysis.manual_override_tables import (
    analysis_content_manual_overrides_table,
)
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity
from aima_ugc.modules.analysis.tables import (
    analysis_content_label_pairs_table,
    analysis_content_results_table,
    analysis_content_runs_table,
)
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.availability_tables import (
    content_availability_observations_table,
)
from aima_ugc.modules.content.query import ContentTarget
from aima_ugc.modules.content.tables import (
    comment_coverage_observations_table,
    comment_versions_table,
    comments_table,
    content_versions_table,
    contents_table,
)
from aima_ugc.modules.reporting.models import DataExportRecord
from aima_ugc.modules.reporting.tables import (
    reporting_data_export_items_table,
    reporting_data_exports_table,
)
from aima_ugc.modules.vehicles.tables import (
    content_vehicle_evidence_table,
    vehicle_models_table,
)
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.time import beijing_now


class DataExportNotFound(LookupError):
    pass


class PostgresDataExportRepository:
    """Reporting 表唯一写入口，并提供共享 Excel exporter 的只读投影。"""

    def __init__(
        self,
        session: Session,
        *,
        analysis_identity: AnalysisConfigurationIdentity | None = None,
    ) -> None:
        self._session = session
        self._analysis_identity = analysis_identity

    def create(
        self,
        *,
        export_id: UUID,
        job_id: UUID,
        request_snapshot: dict[str, object],
        targets: tuple[ContentTarget, ...],
        columns: tuple[str, ...],
        column_catalog_version: int,
    ) -> None:
        if not targets:
            raise ValueError("Data Export 至少需要一个目标")
        self._session.execute(
            insert(reporting_data_exports_table).values(
                id=export_id,
                job_id=job_id,
                artifact_id=None,
                format="xlsx",
                request_snapshot=request_snapshot,
                columns=list(columns),
                column_catalog_version=column_catalog_version,
                created_at=beijing_now(),
            )
        )
        self._session.execute(
            insert(reporting_data_export_items_table),
            [
                {
                    "export_id": export_id,
                    "content_id": target.content_id,
                    "content_version": target.content_version,
                    "ordinal": ordinal,
                }
                for ordinal, target in enumerate(targets)
            ],
        )

    def get(self, export_id: UUID) -> DataExportRecord | None:
        row = (
            self._session.execute(
                select(reporting_data_exports_table).where(
                    reporting_data_exports_table.c.id == export_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return _row_to_export(row) if row is not None else None

    def get_by_job_id(self, job_id: UUID) -> DataExportRecord | None:
        """按唯一 Job 身份读取导出，用于终态通知投影。"""

        row = (
            self._session.execute(
                select(reporting_data_exports_table).where(
                    reporting_data_exports_table.c.job_id == job_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return _row_to_export(row) if row is not None else None

    def list_recent(self, *, limit: int = 20) -> tuple[DataExportRecord, ...]:
        rows = self._session.execute(
            select(reporting_data_exports_table)
            .order_by(
                reporting_data_exports_table.c.created_at.desc(),
                reporting_data_exports_table.c.id.desc(),
            )
            .limit(limit)
        ).mappings()
        return tuple(_row_to_export(row) for row in rows)

    def load_page(
        self,
        export_id: UUID,
        *,
        after_ordinal: int,
        limit: int,
    ) -> tuple[tuple[int, UnifiedDataExcelV1], ...]:
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        item = reporting_data_export_items_table
        content = contents_table
        version = content_versions_table
        attempt = provider_request_attempts_table
        request = provider_requests_table
        rows = tuple(
            self._session.execute(
                select(
                    item.c.ordinal,
                    item.c.content_id,
                    item.c.content_version,
                    content.c.platform,
                    content.c.external_content_id,
                    version.c.content_type,
                    version.c.title,
                    version.c.text,
                    version.c.author_snapshot,
                    version.c.published_at,
                    version.c.canonical_url,
                    version.c.share_url,
                    content.c.current_like_count,
                    content.c.current_comment_count,
                    content.c.current_favorite_count,
                    content.c.current_share_count,
                    content.c.current_repost_count,
                    content.c.current_view_count,
                    content.c.current_play_count,
                    content.c.current_danmaku_count,
                    content.c.current_coin_count,
                    content.c.current_download_count,
                    request.c.provider.label("source_provider"),
                    version.c.raw_artifact_id,
                )
                .select_from(
                    item.join(content, content.c.id == item.c.content_id)
                    .join(
                        version,
                        and_(
                            version.c.content_id == item.c.content_id,
                            version.c.version_no == item.c.content_version,
                        ),
                    )
                    .join(attempt, attempt.c.id == version.c.provider_attempt_id)
                    .join(request, request.c.id == attempt.c.provider_request_id)
                )
                .where(item.c.export_id == export_id, item.c.ordinal > after_ordinal)
                .order_by(item.c.ordinal)
                .limit(limit)
            ).mappings()
        )
        if not rows:
            if self.get(export_id) is None:
                raise DataExportNotFound
            return ()
        content_ids = tuple(cast(UUID, row["content_id"]) for row in rows)
        versions = {
            cast(UUID, row["content_id"]): cast(int, row["content_version"]) for row in rows
        }
        analyses = self._analysis_by_content(versions)
        comments = self._comments_by_content(content_ids)
        coverage = self._coverage_by_content(content_ids)
        vehicles = self._vehicles_by_content(versions)
        availability = self._availability_by_content(content_ids)
        return tuple(
            (
                cast(int, row["ordinal"]),
                UnifiedDataExcelV1(
                    content=_content_projection(
                        row,
                        analysis=analyses.get(cast(UUID, row["content_id"])),
                        coverage=coverage.get(cast(UUID, row["content_id"])),
                        vehicles=vehicles.get(cast(UUID, row["content_id"]), ()),
                        availability=availability.get(cast(UUID, row["content_id"])),
                    ),
                    comments=comments.get(cast(UUID, row["content_id"]), ()),
                ),
            )
            for row in rows
        )

    def attach_artifact(
        self,
        *,
        fence: JobExecutionFence,
        export_id: UUID,
        artifact_id: UUID,
        stats: dict[str, object],
    ) -> DataExportRecord:
        job = PostgresJobRepository(self._session).lock_current_execution(fence)
        row = (
            self._session.execute(
                update(reporting_data_exports_table)
                .where(
                    reporting_data_exports_table.c.id == export_id,
                    reporting_data_exports_table.c.job_id == job.id,
                    reporting_data_exports_table.c.artifact_id.is_(None),
                )
                .values(
                    artifact_id=artifact_id,
                    stats=stats,
                    completed_at=beijing_now(),
                )
                .returning(reporting_data_exports_table)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            existing = self.get(export_id)
            if existing is None:
                raise DataExportNotFound
            if existing.job_id != job.id or existing.artifact_id != artifact_id:
                raise ValueError("Data Export Artifact 关联冲突")
            return existing
        return _row_to_export(row)

    def _analysis_by_content(
        self,
        versions: dict[UUID, int],
    ) -> dict[UUID, UnifiedDataExcelAnalysisV1]:
        result = analysis_content_results_table
        run = analysis_content_runs_table
        conditions = [
            and_(result.c.content_id == content_id, result.c.content_version == version)
            for content_id, version in versions.items()
        ]
        ranked = (
            select(
                result,
                func.row_number()
                .over(
                    partition_by=(result.c.content_id, result.c.content_version),
                    order_by=(run.c.sequence_no.desc(), result.c.id.desc()),
                )
                .label("rank"),
            )
            .select_from(result.join(run, run.c.id == result.c.analysis_run_id))
            .where(
                or_(*conditions),
            )
            .subquery()
        )
        rows = tuple(self._session.execute(select(ranked).where(ranked.c.rank == 1)).mappings())
        manual_rows = self._session.execute(
            select(analysis_content_manual_overrides_table).where(
                or_(
                    *(
                        and_(
                            analysis_content_manual_overrides_table.c.content_id == content_id,
                            analysis_content_manual_overrides_table.c.content_version == version,
                        )
                        for content_id, version in versions.items()
                    )
                )
            )
        ).mappings()
        manual_by_content = {
            cast(UUID, manual["content_id"]): manual for manual in manual_rows
        }
        result_ids = tuple(cast(UUID, row["id"]) for row in rows)
        labels: dict[UUID, list[tuple[int, str, str]]] = defaultdict(list)
        if result_ids:
            for row in self._session.execute(
                select(analysis_content_label_pairs_table).where(
                    analysis_content_label_pairs_table.c.analysis_result_id.in_(result_ids)
                )
            ).mappings():
                labels[cast(UUID, row["analysis_result_id"])].append(
                    (
                        cast(int, row["ordinal"]),
                        cast(str, row["primary_label"]),
                        cast(str, row["secondary_label"]),
                    )
                )
        projected: dict[UUID, UnifiedDataExcelAnalysisV1] = {}
        for row in rows:
            content_id = cast(UUID, row["content_id"])
            manual = manual_by_content.get(content_id)
            if manual is not None and bool(manual["labels_locked"]):
                pairs = tuple(
                    UnifiedDataExcelLabelPairV1.model_validate(item)
                    for item in cast(list[dict[str, str]], manual["labels"])
                )
            else:
                pairs = tuple(
                    UnifiedDataExcelLabelPairV1(primary_label=primary, secondary_label=secondary)
                    for _, primary, secondary in sorted(
                        labels[cast(UUID, row["id"])], key=lambda item: item[0]
                    )
                )
            voice_type = cast(
                ContentVoiceType,
                (
                    manual["voice_type"]
                    if manual is not None and bool(manual["voice_type_locked"])
                    else row["voice_type"]
                ),
            )
            sentiment = cast(
                str | None,
                (
                    manual["sentiment"]
                    if manual is not None and bool(manual["sentiment_locked"])
                    else row["sentiment"]
                ),
            )
            projected[content_id] = UnifiedDataExcelAnalysisV1(
                relevance=cast(ContentRelevance, row["relevance"]),
                voice_type=voice_type,
                sentiment=sentiment,
                primary_label="\n".join(item.primary_label for item in pairs),
                secondary_label="\n".join(item.secondary_label for item in pairs),
                label_pairs=pairs,
                model=cast(str, row["model"]),
                prompt_version=cast(str, row["prompt_version"]),
                taxonomy_version=cast(str, row["taxonomy_sha256"]),
            )
        return projected

    def _comments_by_content(
        self,
        content_ids: tuple[UUID, ...],
    ) -> dict[UUID, tuple[UnifiedDataExcelCommentV1, ...]]:
        comment = comments_table
        version = comment_versions_table
        attempt = provider_request_attempts_table
        request = provider_requests_table
        rows = self._session.execute(
            select(
                comment.c.content_id,
                contents_table.c.platform,
                contents_table.c.external_content_id,
                comment.c.external_comment_id,
                comment.c.root_comment_id,
                comment.c.parent_comment_id,
                version.c.author_snapshot,
                comment.c.text,
                comment.c.published_at,
                comment.c.current_like_count,
                comment.c.current_reply_count,
                request.c.provider,
                version.c.raw_artifact_id,
            )
            .select_from(
                comment.join(contents_table, contents_table.c.id == comment.c.content_id)
                .join(
                    version,
                    and_(
                        version.c.comment_id == comment.c.id,
                        version.c.version_no == comment.c.current_version,
                    ),
                )
                .join(attempt, attempt.c.id == version.c.provider_attempt_id)
                .join(request, request.c.id == attempt.c.provider_request_id)
            )
            .where(comment.c.content_id.in_(content_ids))
            .order_by(comment.c.content_id, comment.c.published_at, comment.c.id)
        ).mappings()
        grouped: dict[UUID, list[UnifiedDataExcelCommentV1]] = defaultdict(list)
        for row in rows:
            author = row["author_snapshot"]
            grouped[cast(UUID, row["content_id"])].append(
                UnifiedDataExcelCommentV1(
                    platform=require_platform_name(cast(str, row["platform"])),
                    external_content_id=cast(str, row["external_content_id"]),
                    level="reply" if row["parent_comment_id"] else "root",
                    external_comment_id=cast(str, row["external_comment_id"]),
                    root_comment_id=cast(str | None, row["root_comment_id"]),
                    parent_comment_id=cast(str | None, row["parent_comment_id"]),
                    author_display_name=(
                        cast(str, author["display_name"])
                        if isinstance(author, dict) and author.get("display_name") is not None
                        else None
                    ),
                    text=cast(str | None, row["text"]),
                    published_at=row["published_at"],
                    like_count=cast(int | None, row["current_like_count"]),
                    reply_count=cast(int | None, row["current_reply_count"]),
                    source_provider=cast(str, row["provider"]),
                    raw_locator=f"artifact:{row['raw_artifact_id']}",
                )
            )
        return {key: tuple(value) for key, value in grouped.items()}

    def _coverage_by_content(self, content_ids: tuple[UUID, ...]) -> dict[UUID, str]:
        coverage = comment_coverage_observations_table
        ranked = (
            select(
                coverage,
                func.row_number()
                .over(
                    partition_by=coverage.c.content_id,
                    order_by=(coverage.c.observed_at.desc(), coverage.c.id.desc()),
                )
                .label("rank"),
            )
            .where(coverage.c.content_id.in_(content_ids))
            .subquery()
        )
        rows = self._session.execute(select(ranked).where(ranked.c.rank == 1)).mappings()
        return {
            cast(UUID, row["content_id"]): (
                f"{row['coverage']}: {row['collected_count']}/"
                f"{row['reported_total'] if row['reported_total'] is not None else '?'}"
            )
            for row in rows
        }

    def _vehicles_by_content(self, versions: dict[UUID, int]) -> dict[UUID, tuple[str, ...]]:
        """按导出冻结的 Content Version 读取车型，而非读取 Worker 执行时的未来版本。"""

        conditions = tuple(
            and_(
                content_vehicle_evidence_table.c.content_id == content_id,
                content_vehicle_evidence_table.c.content_version == version,
            )
            for content_id, version in versions.items()
        )

        effective_vehicle = vehicle_models_table.alias("effective_export_vehicle")
        rows = self._session.execute(
            select(
                content_vehicle_evidence_table.c.content_id,
                func.coalesce(
                    effective_vehicle.c.display_name,
                    vehicle_models_table.c.display_name,
                ).label("effective_display_name"),
            )
            .join(
                vehicle_models_table,
                vehicle_models_table.c.id == content_vehicle_evidence_table.c.vehicle_model_id,
            )
            .outerjoin(
                effective_vehicle,
                effective_vehicle.c.id == vehicle_models_table.c.merged_into_id,
            )
            .where(
                or_(*conditions),
                content_vehicle_evidence_table.c.is_active.is_(True),
            )
            .order_by(
                content_vehicle_evidence_table.c.content_id,
                func.coalesce(effective_vehicle.c.code, vehicle_models_table.c.code),
            )
        ).mappings()
        grouped: dict[UUID, list[str]] = defaultdict(list)
        for row in rows:
            name = cast(str, row["effective_display_name"])
            values = grouped[cast(UUID, row["content_id"])]
            if name not in values:
                values.append(name)
        return {key: tuple(value) for key, value in grouped.items()}

    def _availability_by_content(self, content_ids: tuple[UUID, ...]) -> dict[UUID, str]:
        """读取每个 Content 最新可用状态观察。"""

        availability = content_availability_observations_table
        ranked = (
            select(
                availability.c.content_id,
                availability.c.status,
                func.row_number()
                .over(
                    partition_by=availability.c.content_id,
                    order_by=(availability.c.observed_at.desc(), availability.c.id.desc()),
                )
                .label("rank"),
            )
            .where(availability.c.content_id.in_(content_ids))
            .subquery()
        )
        rows = self._session.execute(select(ranked).where(ranked.c.rank == 1)).mappings()
        return {
            cast(UUID, row["content_id"]): cast(str, row["status"])
            for row in rows
        }


def _content_projection(
    row: Any,
    *,
    analysis: UnifiedDataExcelAnalysisV1 | None,
    coverage: str | None,
    vehicles: tuple[str, ...],
    availability: str | None,
) -> UnifiedDataExcelContentV1:
    author = row["author_snapshot"]
    content_url = row["canonical_url"] or row["share_url"]
    return UnifiedDataExcelContentV1(
        platform=require_platform_name(cast(str, row["platform"])),
        external_content_id=cast(str, row["external_content_id"]),
        content_type=cast(str, row["content_type"]),
        title=cast(str | None, row["title"]),
        text=cast(str | None, row["text"]),
        author_display_name=(
            cast(str, author["display_name"])
            if isinstance(author, dict) and author.get("display_name") is not None
            else None
        ),
        published_at=row["published_at"],
        content_url=cast(str | None, content_url),
        author_follower_count=_author_count(author, "follower_count"),
        author_following_count=_author_count(author, "following_count"),
        author_content_count=_author_count(author, "content_count"),
        author_total_like_count=_author_count(author, "total_like_count"),
        like_count=cast(int | None, row["current_like_count"]),
        comment_count=cast(int | None, row["current_comment_count"]),
        favorite_count=cast(int | None, row["current_favorite_count"]),
        share_count=cast(int | None, row["current_share_count"]),
        repost_count=cast(int | None, row["current_repost_count"]),
        view_count=cast(int | None, row["current_view_count"]),
        play_count=cast(int | None, row["current_play_count"]),
        danmaku_count=cast(int | None, row["current_danmaku_count"]),
        coin_count=cast(int | None, row["current_coin_count"]),
        download_count=cast(int | None, row["current_download_count"]),
        vehicles=vehicles,
        availability=availability,
        analysis=analysis,
        source_provider=cast(str, row["source_provider"]),
        raw_locator=f"artifact:{row['raw_artifact_id']}",
        coverage=coverage,
    )


def _author_count(author: object, key: str) -> int | None:
    if not isinstance(author, dict):
        return None
    value = author.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _row_to_export(row: Any) -> DataExportRecord:
    return DataExportRecord(
        id=cast(UUID, row["id"]),
        job_id=cast(UUID, row["job_id"]),
        artifact_id=cast(UUID | None, row["artifact_id"]),
        request_snapshot=cast(dict[str, object], row["request_snapshot"]),
        columns=tuple(cast(list[str], row["columns"])),
        column_catalog_version=cast(int, row["column_catalog_version"]),
        stats=cast(dict[str, object] | None, row["stats"]),
        created_at=cast(datetime, row["created_at"]),
        completed_at=cast(datetime | None, row["completed_at"]),
    )


__all__ = ["DataExportNotFound", "PostgresDataExportRepository"]
