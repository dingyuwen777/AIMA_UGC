"""Data Import 撤销时的 Content Current 重组与真实生命周期来源。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from itertools import batched
from typing import Any, cast
from uuid import UUID, uuid5

from sqlalchemy import cast as sql_cast
from sqlalchemy import column, delete, insert, select, tuple_, update
from sqlalchemy import values as sql_values
from sqlalchemy.engine import RowMapping

from aima_ugc.contracts.provider import ProviderAttemptV1, ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.provider_persistence import ProviderPersistenceService
from aima_ugc.modules.content.extended_tables import content_external_ids_table
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaign_items_table
from aima_ugc.modules.ingestion.revocation_tables import (
    historical_import_revocation_content_versions_table,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.time import beijing_now

from .content_lifecycle import _CONTENT_FIELD_COLUMNS, PostgresContentLifecycleRepository
from .provider import PostgresProviderRepository


class PostgresImportRevocationLifecycleRepository(PostgresContentLifecycleRepository):
    """复用 Content Owner Delta 规则，并把撤销重组记录成真实内部 imports 来源。"""

    def parent_import_batch_id(self, campaign_id: UUID) -> UUID | None:
        """选择 Campaign 最早的真实 Processing Batch 作为内部撤销 Request 父事实。"""

        return cast(
            UUID | None,
            self._session.scalar(
                select(processing_import_batches_table.c.id)
                .join(
                    historical_import_campaign_items_table,
                    historical_import_campaign_items_table.c.id
                    == processing_import_batches_table.c.historical_campaign_item_id,
                )
                .where(historical_import_campaign_items_table.c.campaign_id == campaign_id)
                .order_by(
                    processing_import_batches_table.c.created_at,
                    processing_import_batches_table.c.id,
                )
                .limit(1)
            ),
        )

    def campaign_contribution_platforms(self, campaign_id: UUID) -> tuple[str, ...]:
        """返回真正需要重组 Current 的 Content 平台集合。"""

        contributions = self.list_campaign_contributions(campaign_id)
        content_ids = tuple({cast(UUID, row["content_id"]) for row in contributions})
        if not content_ids:
            return ()
        return tuple(
            cast(str, value)
            for value in self._session.scalars(
                select(contents_table.c.platform)
                .where(contents_table.c.id.in_(content_ids))
                .distinct()
                .order_by(contents_table.c.platform)
            )
        )

    def create_lifecycle_sources(
        self,
        *,
        campaign_id: UUID,
        raw_artifact_id: UUID,
        revoked_at: datetime,
    ) -> dict[str, tuple[UUID, UUID]]:
        """为每个平台创建确定性的非计费 imports/data_import_revoke 来源。"""

        if revoked_at.utcoffset() is None:
            raise ValueError("revoked_at 必须包含时区")
        platforms = self.campaign_contribution_platforms(campaign_id)
        if not platforms:
            return {}
        parent_batch_id = self.parent_import_batch_id(campaign_id)
        if parent_batch_id is None:
            raise ValueError("需要 Current 重组的 Campaign 缺少真实 Processing Batch 父事实")

        repository = PostgresProviderRepository(self._session)
        service = ProviderPersistenceService(repository)
        sources: dict[str, tuple[UUID, UUID]] = {}
        for platform in platforms:
            request_id = uuid5(campaign_id, f"data-import-revoke-request:{platform}")
            attempt_id = uuid5(campaign_id, f"data-import-revoke-attempt:{platform}")
            prepared = service.prepare_non_billable_attempt(
                request=ProviderRequestV1.create_for_import(
                    request_id=request_id,
                    import_batch_id=parent_batch_id,
                    provider="imports",
                    platform=platform,
                    operation="data_import_revoke",
                    request_params={
                        "campaign_id": str(campaign_id),
                        "platform": platform,
                    },
                    pagination_input={},
                ),
                attempt_id=attempt_id,
            )
            dispatching = repository.mark_dispatching(prepared.attempt.id)
            dispatch_started_at = dispatching.dispatch_started_at
            if dispatch_started_at is None:
                raise RuntimeError("撤销生命周期 Attempt 未进入 dispatching")
            completed_at = max(beijing_now(), dispatching.created_at, dispatch_started_at)
            finalized = repository.finalize_dispatch(
                attempt=ProviderAttemptV1(
                    attempt_id=dispatching.id,
                    provider_request_id=prepared.request.id,
                    attempt_no=dispatching.attempt_no,
                    dispatch_status="completed",
                    dispatch_started_at=dispatch_started_at,
                    completed_at=completed_at,
                    raw_artifact_id=raw_artifact_id,
                    billing=ProviderBillingV1(status="not_billable"),
                    created_at=dispatching.created_at,
                ),
                raw_artifact_id=raw_artifact_id,
            )
            sources[platform] = (finalized.id, raw_artifact_id)
        return sources

    def apply_campaign_revocation_with_sources(
        self,
        campaign_id: UUID,
        *,
        revoked_at: datetime,
        lifecycle_sources: dict[str, tuple[UUID, UUID]],
    ) -> tuple[tuple[UUID, int], ...]:
        """逆序回退 Campaign Delta，并以内部撤销来源追加 Current Version 与追溯记录。"""

        if revoked_at.utcoffset() is None:
            raise ValueError("revoked_at 必须包含时区")
        contributions = self.list_campaign_contributions(campaign_id)
        if all(
            isinstance(row["delta"], dict)
            and not row["delta"].get("account")
            and isinstance(row["delta"].get("collections") or {}, dict)
            and set(row["delta"].get("collections") or {}) <= {"alternate_ids"}
            for row in contributions
        ):
            return self._apply_common_campaign_revocation(
                campaign_id,
                contributions=contributions,
                revoked_at=revoked_at,
                lifecycle_sources=lifecycle_sources,
            )
        by_content: dict[UUID, list[RowMapping]] = defaultdict(list)
        for contribution in contributions:
            by_content[cast(UUID, contribution["content_id"])].append(contribution)

        versions: list[tuple[UUID, int]] = []
        for content_id in sorted(by_content, key=str):
            current = dict(
                self._session.execute(
                    select(contents_table)
                    .where(contents_table.c.id == content_id)
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            current_version = cast(int, current["current_version"])
            version_row = (
                self._session.execute(
                    select(content_versions_table).where(
                        content_versions_table.c.content_id == content_id,
                        content_versions_table.c.version_no == current_version,
                    )
                )
                .mappings()
                .one()
            )
            author_snapshot = (
                dict(cast(dict[str, Any], version_row["author_snapshot"]))
                if isinstance(version_row["author_snapshot"], dict)
                else None
            )
            raw_freshness = current.get("field_observed_at") or {}
            if not isinstance(raw_freshness, dict):
                raise ValueError("Content field_observed_at 必须是对象")
            freshness = {str(key): str(value) for key, value in raw_freshness.items()}

            ordered = sorted(
                by_content[content_id],
                key=lambda row: (row["created_at"], str(row["id"])),
                reverse=True,
            )
            for contribution in ordered:
                delta = contribution["delta"]
                if (
                    not isinstance(delta, dict)
                    or delta.get("schema_version") != "content-source-contribution.v1"
                ):
                    raise ValueError("Content 来源贡献 Delta 版本不受支持")
                author_snapshot = self._apply_delta(
                    content_id=content_id,
                    current=current,
                    freshness=freshness,
                    author_snapshot=author_snapshot,
                    delta=delta,
                )

            platform = cast(str, current["platform"])
            source = lifecycle_sources.get(platform)
            if source is None:
                raise ValueError(f"撤销生命周期缺少平台来源: {platform}")
            version_no = current_version + 1
            current["current_version"] = version_no
            current["field_observed_at"] = freshness
            current["updated_at"] = revoked_at
            self._session.execute(
                update(contents_table)
                .where(contents_table.c.id == content_id)
                .values(
                    **{
                        column: current[column]
                        for column in set(_CONTENT_FIELD_COLUMNS.values())
                        if column in current
                    },
                    field_observed_at=freshness,
                    current_version=version_no,
                    updated_at=revoked_at,
                )
            )
            self._session.execute(
                insert(content_versions_table).values(
                    id=uuid5(campaign_id, f"revocation-content-version:{content_id}:{version_no}"),
                    content_id=content_id,
                    version_no=version_no,
                    content_type=current["content_type"],
                    title=current["title"],
                    text=current["text"],
                    canonical_url=current["canonical_url"],
                    share_url=current["share_url"],
                    author_snapshot=author_snapshot,
                    published_at=current["published_at"],
                    source_updated_at=current["source_updated_at"],
                    status=current["status"],
                    provider_attempt_id=source[0],
                    raw_artifact_id=source[1],
                    observed_at=revoked_at,
                )
            )
            self._session.execute(
                insert(historical_import_revocation_content_versions_table).values(
                    campaign_id=campaign_id,
                    content_id=content_id,
                    version_no=version_no,
                    created_at=beijing_now(),
                )
            )
            versions.append((content_id, version_no))
        return tuple(versions)

    def _apply_common_campaign_revocation(
        self,
        campaign_id: UUID,
        *,
        contributions: tuple[RowMapping, ...],
        revoked_at: datetime,
        lifecycle_sources: dict[str, tuple[UUID, UUID]],
    ) -> tuple[tuple[UUID, int], ...]:
        """按有界批次预读 Current/Version/备用 ID，并集合提交常见撤销写入。"""

        by_content: dict[UUID, list[RowMapping]] = defaultdict(list)
        for row in contributions:
            by_content[cast(UUID, row["content_id"])].append(row)
        versions: list[tuple[UUID, int]] = []
        content_columns = tuple(sorted(set(_CONTENT_FIELD_COLUMNS.values())))
        for content_ids_batch in batched(sorted(by_content, key=str), 500, strict=False):
            content_ids = tuple(content_ids_batch)
            currents = {
                cast(UUID, row["id"]): dict(row)
                for row in self._session.execute(
                    select(contents_table)
                    .where(contents_table.c.id.in_(content_ids))
                    .order_by(contents_table.c.id)
                    .with_for_update()
                ).mappings()
            }
            version_rows = {
                cast(UUID, row["content_id"]): row
                for row in self._session.execute(
                    select(content_versions_table).where(
                        tuple_(
                            content_versions_table.c.content_id,
                            content_versions_table.c.version_no,
                        ).in_(
                            tuple(
                                (content_id, currents[content_id]["current_version"])
                                for content_id in content_ids
                            )
                        )
                    )
                ).mappings()
            }
            alternate_rows: dict[UUID, list[dict[str, object]]] = defaultdict(list)
            for row in self._session.execute(
                select(content_external_ids_table)
                .where(content_external_ids_table.c.content_id.in_(content_ids))
                .order_by(
                    content_external_ids_table.c.content_id,
                    content_external_ids_table.c.id_type,
                )
            ).mappings():
                alternate_rows[cast(UUID, row["content_id"])].append(
                    {str(key): value for key, value in row.items() if key != "content_id"}
                )

            updates: list[dict[str, object]] = []
            content_versions: list[dict[str, object]] = []
            lineage_versions: list[dict[str, object]] = []
            changed_alternate_ids: list[UUID] = []
            restored_alternate_ids: list[dict[str, object]] = []
            for content_id in content_ids:
                current = currents[content_id]
                current_version = cast(int, current["current_version"])
                version_row = version_rows[content_id]
                author_snapshot = (
                    dict(cast(dict[str, Any], version_row["author_snapshot"]))
                    if isinstance(version_row["author_snapshot"], dict)
                    else None
                )
                raw_freshness = current.get("field_observed_at") or {}
                if not isinstance(raw_freshness, dict):
                    raise ValueError("Content field_observed_at 必须是对象")
                freshness = {str(key): str(value) for key, value in raw_freshness.items()}
                collection_cache = {"alternate_ids": tuple(alternate_rows[content_id])}
                collection_updates: dict[str, list[dict[str, object]]] = {}
                ordered = sorted(
                    by_content[content_id],
                    key=lambda row: (row["created_at"], str(row["id"])),
                    reverse=True,
                )
                for contribution in ordered:
                    delta = contribution["delta"]
                    if delta.get("schema_version") != "content-source-contribution.v1":
                        raise ValueError("Content 来源贡献 Delta 版本不受支持")
                    author_snapshot = self._apply_delta(
                        content_id=content_id,
                        current=current,
                        freshness=freshness,
                        author_snapshot=author_snapshot,
                        delta=delta,
                        collection_cache=collection_cache,
                        collection_updates=collection_updates,
                    )
                if "alternate_ids" in collection_updates:
                    changed_alternate_ids.append(content_id)
                    restored_alternate_ids.extend(
                        {"content_id": content_id, **row}
                        for row in collection_updates["alternate_ids"]
                    )
                source = lifecycle_sources.get(cast(str, current["platform"]))
                if source is None:
                    raise ValueError("撤销生命周期缺少平台来源")
                version_no = current_version + 1
                updates.append(
                    {
                        "target_content_id": content_id,
                        **{column: current[column] for column in content_columns},
                        "field_observed_at": freshness,
                        "current_version": version_no,
                        "updated_at": revoked_at,
                    }
                )
                content_versions.append(
                    {
                        "id": uuid5(
                            campaign_id,
                            f"revocation-content-version:{content_id}:{version_no}",
                        ),
                        "content_id": content_id,
                        "version_no": version_no,
                        "content_type": current["content_type"],
                        "title": current["title"],
                        "text": current["text"],
                        "canonical_url": current["canonical_url"],
                        "share_url": current["share_url"],
                        "author_snapshot": author_snapshot,
                        "published_at": current["published_at"],
                        "source_updated_at": current["source_updated_at"],
                        "status": current["status"],
                        "provider_attempt_id": source[0],
                        "raw_artifact_id": source[1],
                        "observed_at": revoked_at,
                    }
                )
                lineage_versions.append(
                    {
                        "campaign_id": campaign_id,
                        "content_id": content_id,
                        "version_no": version_no,
                        "created_at": revoked_at,
                    }
                )
                versions.append((content_id, version_no))

            if changed_alternate_ids:
                self._session.execute(
                    delete(content_external_ids_table).where(
                        content_external_ids_table.c.content_id.in_(changed_alternate_ids)
                    )
                )
            if restored_alternate_ids:
                self._session.execute(insert(content_external_ids_table), restored_alternate_ids)
            if updates:
                updated_columns = (
                    *content_columns,
                    "field_observed_at",
                    "current_version",
                    "updated_at",
                )
                batch_values = sql_values(
                    column("target_content_id", contents_table.c.id.type),
                    *(column(name, contents_table.c[name].type) for name in updated_columns),
                    name="revocation_values",
                ).data(
                    tuple(
                        (row["target_content_id"], *(row[name] for name in updated_columns))
                        for row in updates
                    )
                )
                self._session.execute(
                    update(contents_table)
                    .where(
                        contents_table.c.id
                        == sql_cast(batch_values.c.target_content_id, contents_table.c.id.type)
                    )
                    .values(
                        {
                            name: sql_cast(batch_values.c[name], contents_table.c[name].type)
                            for name in updated_columns
                        }
                    )
                )
                self._session.execute(insert(content_versions_table).values(content_versions))
                self._session.execute(
                    insert(historical_import_revocation_content_versions_table).values(
                        lineage_versions
                    )
                )
        return tuple(versions)


__all__ = ["PostgresImportRevocationLifecycleRepository"]
