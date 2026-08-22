"""Stage 8E Import Batch → 当前 Content 补采目标只读查询。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.contracts.platform import PlatformName, require_platform_name
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.modules.ingestion.tables import processing_import_batches_table


@dataclass(frozen=True, slots=True)
class CollectionEnrichmentTarget:
    content_id: UUID
    platform: PlatformName
    external_content_id: str
    content_type: str


class PostgresCollectionTargetReader:
    """按正式来源账本读取 Batch 关联的当前 Content，不接受浏览器外部 ID。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def batch_exists(self, batch_id: UUID) -> bool:
        return (
            self._session.scalar(
                select(processing_import_batches_table.c.id).where(
                    processing_import_batches_table.c.id == batch_id
                )
            )
            is not None
        )

    def list_batch_targets(
        self,
        *,
        batch_id: UUID,
        platforms: tuple[PlatformName, ...],
    ) -> tuple[CollectionEnrichmentTarget, ...]:
        content = contents_table
        version = content_versions_table
        attempt = provider_request_attempts_table
        request = provider_requests_table
        rows = self._session.execute(
            select(
                content.c.id,
                content.c.platform,
                content.c.external_content_id,
                content.c.content_type,
            )
            .select_from(
                content.join(version, version.c.content_id == content.c.id)
                .join(attempt, attempt.c.id == version.c.provider_attempt_id)
                .join(request, request.c.id == attempt.c.provider_request_id)
            )
            .where(
                request.c.import_batch_id == batch_id,
                content.c.platform.in_(platforms),
            )
            .distinct()
            .order_by(content.c.platform, content.c.id)
        ).mappings()
        return tuple(_target(row) for row in rows)

    def get_batch_target(
        self,
        *,
        batch_id: UUID,
        content_id: UUID,
    ) -> CollectionEnrichmentTarget | None:
        """执行期复核 Scope 目标仍属于 Run 冻结的 Import Batch。"""

        content = contents_table
        version = content_versions_table
        attempt = provider_request_attempts_table
        request = provider_requests_table
        row = (
            self._session.execute(
                select(
                    content.c.id,
                    content.c.platform,
                    content.c.external_content_id,
                    content.c.content_type,
                )
                .select_from(
                    content.join(version, version.c.content_id == content.c.id)
                    .join(attempt, attempt.c.id == version.c.provider_attempt_id)
                    .join(request, request.c.id == attempt.c.provider_request_id)
                )
                .where(
                    request.c.import_batch_id == batch_id,
                    content.c.id == content_id,
                )
                .distinct()
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _target(row)


def _target(row: RowMapping) -> CollectionEnrichmentTarget:
    return CollectionEnrichmentTarget(
        content_id=cast(UUID, row["id"]),
        platform=require_platform_name(cast(str, row["platform"])),
        external_content_id=cast(str, row["external_content_id"]),
        content_type=cast(str, row["content_type"]),
    )


__all__ = ["CollectionEnrichmentTarget", "PostgresCollectionTargetReader"]
