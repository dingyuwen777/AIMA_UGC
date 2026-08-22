"""Stage 8E Import Batch → 当前 Content 补采目标只读查询。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.contracts.platform import PlatformName, require_platform_name
from aima_ugc.modules.analysis.tables import analysis_content_results_table
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.extended_tables import content_external_ids_table
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.modules.ingestion.tables import processing_import_batches_table

# 这里只列当前生产 Runtime 已验证能够直接消费的 lookup identity。
# share/short URL 可以被 Import 识别和保存，但在正式 Resolver/身份合并闭环前不得直接计费补采。
_LOOKUP_ID_PRIORITY: dict[PlatformName, tuple[str, ...]] = {
    "xiaohongshu": ("note_id",),
    "douyin": ("aweme_id",),
    "weibo": ("status_id",),
    "bilibili": ("av_id", "bv_id"),
    "kuaishou": ("photo_id",),
}


@dataclass(frozen=True, slots=True)
class CollectionEnrichmentTarget:
    content_id: UUID
    platform: PlatformName
    external_content_id: str
    content_type: str
    lookup_id_type: str
    lookup_value: str
    alternate_ids: dict[str, str]


class PostgresCollectionTargetReader:
    """按来源账本、最新 AI 结果与 Provider lookup identity 读取补采目标。"""

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
        rows = self._candidate_rows(batch_id=batch_id, platforms=platforms)
        return self._eligible_targets(rows, exclude_irrelevant=True)

    def get_batch_target(
        self,
        *,
        batch_id: UUID,
        content_id: UUID,
    ) -> CollectionEnrichmentTarget | None:
        """执行期复核 Scope 目标仍属于 Batch 且仍有可用 lookup identity。

        相关性只在创建 Run 时冻结资格；避免排队期间新的 AI 结果把已创建 Scope 变成执行错误。
        """

        rows = self._candidate_rows(batch_id=batch_id, content_id=content_id)
        targets = self._eligible_targets(rows, exclude_irrelevant=False)
        return targets[0] if targets else None

    def _candidate_rows(
        self,
        *,
        batch_id: UUID,
        platforms: tuple[PlatformName, ...] | None = None,
        content_id: UUID | None = None,
    ) -> tuple[RowMapping, ...]:
        content = contents_table
        version = content_versions_table
        attempt = provider_request_attempts_table
        request = provider_requests_table
        conditions = [request.c.import_batch_id == batch_id]
        if platforms is not None:
            conditions.append(content.c.platform.in_(platforms))
        if content_id is not None:
            conditions.append(content.c.id == content_id)
        return tuple(
            self._session.execute(
                select(
                    content.c.id,
                    content.c.platform,
                    content.c.external_content_id,
                    content.c.content_type,
                    content.c.current_version,
                )
                .select_from(
                    content.join(version, version.c.content_id == content.c.id)
                    .join(attempt, attempt.c.id == version.c.provider_attempt_id)
                    .join(request, request.c.id == attempt.c.provider_request_id)
                )
                .where(*conditions)
                .distinct()
                .order_by(content.c.platform, content.c.id)
            ).mappings()
        )

    def _eligible_targets(
        self,
        rows: tuple[RowMapping, ...],
        *,
        exclude_irrelevant: bool,
    ) -> tuple[CollectionEnrichmentTarget, ...]:
        if not rows:
            return ()
        content_ids = tuple(cast(UUID, row["id"]) for row in rows)
        alternate_ids = self._alternate_ids(content_ids)
        tikhub_content_ids = self._tikhub_content_ids(content_ids)
        irrelevant_content_ids = (
            self._latest_current_irrelevant_content_ids(content_ids)
            if exclude_irrelevant
            else set()
        )

        targets: list[CollectionEnrichmentTarget] = []
        for row in rows:
            content_id = cast(UUID, row["id"])
            if content_id in irrelevant_content_ids:
                continue
            platform = require_platform_name(cast(str, row["platform"]))
            external_content_id = cast(str, row["external_content_id"])
            ids = dict(alternate_ids.get(content_id, {}))
            lookup = _lookup_identity(
                platform=platform,
                external_content_id=external_content_id,
                alternate_ids=ids,
                has_tikhub_source=content_id in tikhub_content_ids,
            )
            if lookup is None:
                continue
            id_type, value = lookup
            ids.setdefault(id_type, value)
            targets.append(
                CollectionEnrichmentTarget(
                    content_id=content_id,
                    platform=platform,
                    external_content_id=external_content_id,
                    content_type=cast(str, row["content_type"]),
                    lookup_id_type=id_type,
                    lookup_value=value,
                    alternate_ids=ids,
                )
            )
        return tuple(targets)

    def _alternate_ids(self, content_ids: tuple[UUID, ...]) -> dict[UUID, dict[str, str]]:
        rows = self._session.execute(
            select(
                content_external_ids_table.c.content_id,
                content_external_ids_table.c.id_type,
                content_external_ids_table.c.external_id,
            ).where(content_external_ids_table.c.content_id.in_(content_ids))
        ).mappings()
        result: dict[UUID, dict[str, str]] = defaultdict(dict)
        for row in rows:
            result[cast(UUID, row["content_id"])][cast(str, row["id_type"])] = cast(
                str, row["external_id"]
            )
        return dict(result)

    def _tikhub_content_ids(self, content_ids: tuple[UUID, ...]) -> set[UUID]:
        version = content_versions_table
        attempt = provider_request_attempts_table
        request = provider_requests_table
        rows = self._session.execute(
            select(version.c.content_id)
            .select_from(
                version.join(attempt, attempt.c.id == version.c.provider_attempt_id).join(
                    request, request.c.id == attempt.c.provider_request_id
                )
            )
            .where(
                version.c.content_id.in_(content_ids),
                request.c.provider == "tikhub",
            )
            .distinct()
        )
        return {cast(UUID, row[0]) for row in rows}

    def _latest_current_irrelevant_content_ids(
        self,
        content_ids: tuple[UUID, ...],
    ) -> set[UUID]:
        analysis = analysis_content_results_table
        content = contents_table
        latest = (
            select(
                analysis.c.content_id,
                analysis.c.relevance,
            )
            .select_from(analysis.join(content, content.c.id == analysis.c.content_id))
            .where(
                analysis.c.content_id.in_(content_ids),
                analysis.c.content_version == content.c.current_version,
            )
            .distinct(analysis.c.content_id)
            .order_by(
                analysis.c.content_id,
                analysis.c.analyzed_at.desc(),
                analysis.c.id.desc(),
            )
            .subquery()
        )
        rows = self._session.execute(
            select(latest.c.content_id).where(latest.c.relevance == "irrelevant")
        )
        return {cast(UUID, row[0]) for row in rows}


def _lookup_identity(
    *,
    platform: PlatformName,
    external_content_id: str,
    alternate_ids: dict[str, str],
    has_tikhub_source: bool,
) -> tuple[str, str] | None:
    for id_type in _LOOKUP_ID_PRIORITY[platform]:
        value = alternate_ids.get(id_type)
        if value:
            return id_type, value
    if not has_tikhub_source:
        return None
    return _legacy_tikhub_lookup(platform=platform, external_content_id=external_content_id)


def _legacy_tikhub_lookup(
    *,
    platform: PlatformName,
    external_content_id: str,
) -> tuple[str, str] | None:
    value = external_content_id.strip()
    if not value or value.startswith("url_sha256:"):
        return None
    if platform == "xiaohongshu":
        return "note_id", value
    if platform == "douyin" and value.isdigit():
        return "aweme_id", value
    if platform == "weibo" and value.isdigit():
        return "status_id", value
    if platform == "bilibili":
        if value.casefold().startswith("bv"):
            return "bv_id", value
        av_value = value[2:] if value.casefold().startswith("av") else value
        if av_value.isdigit():
            return "av_id", av_value
        return None
    if platform == "kuaishou":
        return "photo_id", value
    return None


def _target(row: RowMapping) -> CollectionEnrichmentTarget:
    """兼容旧测试辅助；新生产路径通过 ``_eligible_targets`` 构造。"""

    platform = require_platform_name(cast(str, row["platform"]))
    external_content_id = cast(str, row["external_content_id"])
    lookup = _legacy_tikhub_lookup(platform=platform, external_content_id=external_content_id)
    if lookup is None:
        raise ValueError("Content 缺少可用 Provider lookup identity")
    id_type, value = lookup
    return CollectionEnrichmentTarget(
        content_id=cast(UUID, row["id"]),
        platform=platform,
        external_content_id=external_content_id,
        content_type=cast(str, row["content_type"]),
        lookup_id_type=id_type,
        lookup_value=value,
        alternate_ids={id_type: value},
    )


__all__ = ["CollectionEnrichmentTarget", "PostgresCollectionTargetReader"]
