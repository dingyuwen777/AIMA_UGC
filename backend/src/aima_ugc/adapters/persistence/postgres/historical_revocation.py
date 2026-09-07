"""Data Import Campaign 撤销的 PostgreSQL Ingestion Owner 实现。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import exists, func, insert, literal, select, union
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

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
from aima_ugc.modules.content.contribution_tables import content_source_contributions_table
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
    processing_import_batch_items_table,
)
from aima_ugc.modules.ingestion.revocation import (
    ImportCampaignRevocationImpact,
    ImportCampaignRevocationRecord,
)
from aima_ugc.modules.ingestion.revocation_tables import (
    historical_import_campaign_revocations_table,
)

from .content_visibility import content_has_active_source


class PostgresImportCampaignRevocationRepository:
    """撤销事实、影响分析和 Campaign 锁都由同一调用方事务持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_campaign_status(self, campaign_id: UUID, *, for_update: bool) -> str | None:
        """读取 Campaign 状态；执行撤销时可锁定父事实防止终态漂移。"""

        statement = select(historical_import_campaigns_table.c.status).where(
            historical_import_campaigns_table.c.id == campaign_id
        )
        if for_update:
            statement = statement.with_for_update()
        value = self._session.scalar(statement)
        return cast(str | None, value)

    def get_revocation(self, campaign_id: UUID) -> ImportCampaignRevocationRecord | None:
        """读取已经提交的撤销事实。"""

        row = (
            self._session.execute(
                select(historical_import_campaign_revocations_table).where(
                    historical_import_campaign_revocations_table.c.campaign_id == campaign_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _record(row)

    def calculate_impact(self, campaign_id: UUID) -> ImportCampaignRevocationImpact:
        """计算可见性影响与可逆证据缺口；这里只读，不修改业务数据。"""

        affected = _affected_content_ids(campaign_id).subquery("revocation_affected_contents")
        affected_count = int(self._session.scalar(select(func.count()).select_from(affected)) or 0)
        if affected_count == 0:
            return ImportCampaignRevocationImpact(0, 0, 0, 0)
        retained = int(
            self._session.scalar(
                select(func.count())
                .select_from(affected)
                .where(
                    content_has_active_source(
                        affected.c.content_id,
                        excluding_campaign_id=campaign_id,
                    )
                )
            )
            or 0
        )
        unreversible = _unreversible_content_ids(campaign_id).subquery(
            "revocation_unreversible_contents"
        )
        unreversible_count = int(
            self._session.scalar(select(func.count()).select_from(unreversible)) or 0
        )
        return ImportCampaignRevocationImpact(
            affected_content_count=affected_count,
            hidden_content_count=affected_count - retained,
            retained_shared_content_count=retained,
            unreversible_content_count=unreversible_count,
        )

    def create_revocation(
        self,
        *,
        campaign_id: UUID,
        actor_ref: str,
        request_id: str | None,
        reason: str | None,
        impact: ImportCampaignRevocationImpact,
        revoked_at: datetime,
    ) -> ImportCampaignRevocationRecord:
        """追加唯一撤销事实；父 Campaign 已由上层服务在同事务锁定。"""

        if not impact.safely_reversible:
            raise ValueError("不可安全回退的 Campaign 不能创建撤销事实")
        row = (
            self._session.execute(
                insert(historical_import_campaign_revocations_table)
                .values(
                    campaign_id=campaign_id,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    reason=reason,
                    affected_content_count=impact.affected_content_count,
                    hidden_content_count=impact.hidden_content_count,
                    retained_shared_content_count=impact.retained_shared_content_count,
                    unreversible_content_count=impact.unreversible_content_count,
                    revoked_at=revoked_at,
                )
                .returning(historical_import_campaign_revocations_table)
            )
            .mappings()
            .one()
        )
        return _record(row)


def _affected_content_ids(campaign_id: UUID) -> Any:
    """合并直接文件导入与基于 Campaign 的在线补采贡献，按 Content 去重。"""

    direct = (
        select(processing_import_batch_items_table.c.content_id.label("content_id"))
        .select_from(
            processing_import_batch_items_table.join(
                historical_import_campaign_items_table,
                historical_import_campaign_items_table.c.id
                == processing_import_batch_items_table.c.campaign_item_id,
            )
        )
        .where(
            historical_import_campaign_items_table.c.campaign_id == campaign_id,
            processing_import_batch_items_table.c.content_id.is_not(None),
        )
    )

    ingestion = collection_candidate_ingestions_table.alias("revocation_candidate_ingestion")
    candidate = collection_candidates_table.alias("revocation_candidate")
    attempt = provider_request_attempts_table.alias("revocation_attempt")
    request = provider_requests_table.alias("revocation_request")
    scope = collection_scopes_table.alias("revocation_scope")
    run = collection_runs_table.alias("revocation_run")
    supplemented = (
        select(ingestion.c.content_id.label("content_id"))
        .select_from(
            ingestion.join(candidate, candidate.c.id == ingestion.c.candidate_id)
            .join(attempt, attempt.c.id == candidate.c.provider_request_attempt_id)
            .join(request, request.c.id == attempt.c.provider_request_id)
            .join(scope, scope.c.id == request.c.scope_id)
            .join(run, run.c.id == scope.c.run_id)
        )
        .where(
            run.c.data_import_campaign_id == campaign_id,
            ingestion.c.content_id.is_not(None),
        )
    )
    return union(direct, supplemented)


def _unreversible_content_ids(campaign_id: UUID) -> Any:
    """找出发生过业务写入、但缺少精确 Contribution Delta 的 Content。"""

    ledger = processing_import_batch_items_table.alias("revocation_ledger")
    campaign_item = historical_import_campaign_items_table.alias("revocation_campaign_item")
    contribution = content_source_contributions_table.alias("revocation_direct_contribution")
    attempt = provider_request_attempts_table.alias("revocation_direct_attempt")
    request = provider_requests_table.alias("revocation_direct_request")
    direct_contribution_exists = exists(
        select(literal(1))
        .select_from(
            contribution.join(attempt, attempt.c.id == contribution.c.provider_attempt_id).join(
                request,
                request.c.id == attempt.c.provider_request_id,
            )
        )
        .where(
            contribution.c.content_id == ledger.c.content_id,
            request.c.import_batch_id == ledger.c.batch_id,
        )
    )
    direct_missing = (
        select(ledger.c.content_id.label("content_id"))
        .select_from(
            ledger.join(
                campaign_item,
                campaign_item.c.id == ledger.c.campaign_item_id,
            )
        )
        .where(
            campaign_item.c.campaign_id == campaign_id,
            ledger.c.content_id.is_not(None),
            ledger.c.outcome.in_(("created", "filled", "updated")),
            ~direct_contribution_exists,
        )
    )

    ingestion = collection_candidate_ingestions_table.alias("revocation_missing_ingestion")
    candidate = collection_candidates_table.alias("revocation_missing_candidate")
    source_attempt = provider_request_attempts_table.alias("revocation_missing_source_attempt")
    source_request = provider_requests_table.alias("revocation_missing_source_request")
    scope = collection_scopes_table.alias("revocation_missing_scope")
    run = collection_runs_table.alias("revocation_missing_run")
    supplement_contribution = content_source_contributions_table.alias(
        "revocation_supplement_contribution"
    )
    supplement_contribution_exists = exists(
        select(literal(1)).where(
            supplement_contribution.c.content_id == ingestion.c.content_id,
            supplement_contribution.c.provider_attempt_id
            == candidate.c.provider_request_attempt_id,
        )
    )
    supplemented_missing = (
        select(ingestion.c.content_id.label("content_id"))
        .select_from(
            ingestion.join(candidate, candidate.c.id == ingestion.c.candidate_id)
            .join(source_attempt, source_attempt.c.id == candidate.c.provider_request_attempt_id)
            .join(source_request, source_request.c.id == source_attempt.c.provider_request_id)
            .join(scope, scope.c.id == source_request.c.scope_id)
            .join(run, run.c.id == scope.c.run_id)
        )
        .where(
            run.c.data_import_campaign_id == campaign_id,
            ingestion.c.content_id.is_not(None),
            ~supplement_contribution_exists,
        )
    )
    return union(direct_missing, supplemented_missing)


def _record(row: RowMapping) -> ImportCampaignRevocationRecord:
    """把数据库行转换成稳定领域记录。"""

    return ImportCampaignRevocationRecord(
        campaign_id=cast(UUID, row["campaign_id"]),
        actor_ref=cast(str, row["actor_ref"]),
        request_id=cast(str | None, row["request_id"]),
        reason=cast(str | None, row["reason"]),
        impact=ImportCampaignRevocationImpact(
            affected_content_count=cast(int, row["affected_content_count"]),
            hidden_content_count=cast(int, row["hidden_content_count"]),
            retained_shared_content_count=cast(int, row["retained_shared_content_count"]),
            unreversible_content_count=cast(int, row["unreversible_content_count"]),
        ),
        revoked_at=cast(datetime, row["revoked_at"]),
    )


__all__ = ["PostgresImportCampaignRevocationRepository"]
