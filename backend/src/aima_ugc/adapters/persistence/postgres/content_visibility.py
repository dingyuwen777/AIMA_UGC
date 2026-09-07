"""Content 的业务可见性：至少存在一个未撤销来源才对新业务操作可见。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, exists, literal, or_, select
from sqlalchemy.sql.elements import ColumnElement

from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.tables import content_versions_table
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    processing_import_batch_items_table,
)
from aima_ugc.modules.ingestion.revocation_tables import (
    historical_import_campaign_revocations_table,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table


def _campaign_available(
    campaign_id: ColumnElement[UUID],
    *,
    excluding_campaign_id: UUID | None,
) -> ColumnElement[bool]:
    """判断一个 Campaign 来源当前是否仍贡献业务可见性。"""

    revocation = historical_import_campaign_revocations_table.alias()
    available: ColumnElement[bool] = ~exists(
        select(literal(1)).where(revocation.c.campaign_id == campaign_id)
    )
    if excluding_campaign_id is not None:
        available = and_(campaign_id != excluding_campaign_id, available)
    return available


def content_has_active_source(
    content_id: ColumnElement[UUID],
    *,
    excluding_campaign_id: UUID | None = None,
) -> ColumnElement[bool]:
    """返回可用于 SELECT/COUNT 的统一来源可见性谓词。

    `excluding_campaign_id` 用于撤销预览：目标 Campaign 即使尚未真正写入撤销事实，也按已撤销处理。
    历史单文件 Import 等无法映射到 Data Import Campaign 的来源视为不可撤销的有效来源。
    """

    ledger = processing_import_batch_items_table.alias("visibility_import_ledger")
    campaign_item = historical_import_campaign_items_table.alias("visibility_campaign_item")
    direct_import_source = exists(
        select(literal(1))
        .select_from(ledger.join(campaign_item, campaign_item.c.id == ledger.c.campaign_item_id))
        .where(
            ledger.c.content_id == content_id,
            _campaign_available(
                campaign_item.c.campaign_id,
                excluding_campaign_id=excluding_campaign_id,
            ),
        )
    )

    candidate_ingestion = collection_candidate_ingestions_table.alias(
        "visibility_candidate_ingestion"
    )
    candidate = collection_candidates_table.alias("visibility_candidate")
    candidate_attempt = provider_request_attempts_table.alias("visibility_candidate_attempt")
    candidate_request = provider_requests_table.alias("visibility_candidate_request")
    candidate_scope = collection_scopes_table.alias("visibility_candidate_scope")
    candidate_run = collection_runs_table.alias("visibility_candidate_run")
    collection_candidate_source = exists(
        select(literal(1))
        .select_from(
            candidate_ingestion.join(
                candidate,
                candidate.c.id == candidate_ingestion.c.candidate_id,
            )
            .join(
                candidate_attempt,
                candidate_attempt.c.id == candidate.c.provider_request_attempt_id,
            )
            .join(
                candidate_request,
                candidate_request.c.id == candidate_attempt.c.provider_request_id,
            )
            .join(candidate_scope, candidate_scope.c.id == candidate_request.c.scope_id)
            .join(candidate_run, candidate_run.c.id == candidate_scope.c.run_id)
        )
        .where(
            candidate_ingestion.c.content_id == content_id,
            or_(
                candidate_run.c.data_import_campaign_id.is_(None),
                _campaign_available(
                    candidate_run.c.data_import_campaign_id,
                    excluding_campaign_id=excluding_campaign_id,
                ),
            ),
        )
    )

    import_version = content_versions_table.alias("visibility_import_version")
    import_attempt = provider_request_attempts_table.alias("visibility_import_attempt")
    import_request = provider_requests_table.alias("visibility_import_request")
    import_batch = processing_import_batches_table.alias("visibility_import_batch")
    import_campaign_item = historical_import_campaign_items_table.alias(
        "visibility_import_campaign_item"
    )
    import_version_source = exists(
        select(literal(1))
        .select_from(
            import_version.join(
                import_attempt,
                import_attempt.c.id == import_version.c.provider_attempt_id,
            )
            .join(
                import_request,
                import_request.c.id == import_attempt.c.provider_request_id,
            )
            .join(import_batch, import_batch.c.id == import_request.c.import_batch_id)
            .outerjoin(
                import_campaign_item,
                import_campaign_item.c.id == import_batch.c.historical_campaign_item_id,
            )
        )
        .where(
            import_version.c.content_id == content_id,
            import_request.c.import_batch_id.is_not(None),
            or_(
                import_batch.c.historical_campaign_item_id.is_(None),
                _campaign_available(
                    import_campaign_item.c.campaign_id,
                    excluding_campaign_id=excluding_campaign_id,
                ),
            ),
        )
    )

    collection_version = content_versions_table.alias("visibility_collection_version")
    collection_attempt = provider_request_attempts_table.alias("visibility_collection_attempt")
    collection_request = provider_requests_table.alias("visibility_collection_request")
    collection_scope = collection_scopes_table.alias("visibility_collection_scope")
    collection_run = collection_runs_table.alias("visibility_collection_run")
    collection_version_source = exists(
        select(literal(1))
        .select_from(
            collection_version.join(
                collection_attempt,
                collection_attempt.c.id == collection_version.c.provider_attempt_id,
            )
            .join(
                collection_request,
                collection_request.c.id == collection_attempt.c.provider_request_id,
            )
            .join(collection_scope, collection_scope.c.id == collection_request.c.scope_id)
            .join(collection_run, collection_run.c.id == collection_scope.c.run_id)
        )
        .where(
            collection_version.c.content_id == content_id,
            collection_request.c.scope_id.is_not(None),
            or_(
                collection_run.c.data_import_campaign_id.is_(None),
                _campaign_available(
                    collection_run.c.data_import_campaign_id,
                    excluding_campaign_id=excluding_campaign_id,
                ),
            ),
        )
    )

    return or_(
        direct_import_source,
        collection_candidate_source,
        import_version_source,
        collection_version_source,
    )


__all__ = ["content_has_active_source"]
