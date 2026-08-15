"""Provider Run/Comment 技术预算包络的 PostgreSQL 建立器。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.provider_budget import (
    ProviderBudgetAccountMissingError,
    ProviderBudgetAccountSpec,
    ProviderBudgetLineageError,
    ProviderBudgetService,
)
from aima_ugc.modules.collection.run_budget import RunProviderBudgetEnvelope
from aima_ugc.modules.collection.tables import provider_budget_accounts_table

from .provider_budget import PostgresProviderBudgetRepository


class PostgresProviderBudgetEnvelopeProvisioner:
    """在既有 Global 硬预算下建立当前 Run 的更窄技术包络。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._service = ProviderBudgetService(PostgresProviderBudgetRepository(session))

    def ensure_run_envelope(
        self,
        *,
        provider_config_id: UUID,
        run_id: UUID,
        envelope: RunProviderBudgetEnvelope,
        at: datetime,
        currency: str = "USD",
    ) -> None:
        if envelope.provider_config_id != provider_config_id:
            raise ProviderBudgetLineageError("Run Budget Envelope 的 Provider Config 不一致")
        period_start, period_end = self._global_period(
            provider_config_id=provider_config_id,
            at=at,
            currency=currency,
        )
        for scope_type in ("run", "run_comments"):
            self._ensure_account(
                provider_config_id=provider_config_id,
                scope_type=scope_type,
                run_id=run_id,
                content_id=None,
                period_start=period_start,
                period_end=period_end,
                dimension="request_count",
                unit="request",
                limit_amount=Decimal(envelope.request_limit),
            )
            self._ensure_account(
                provider_config_id=provider_config_id,
                scope_type=scope_type,
                run_id=run_id,
                content_id=None,
                period_start=period_start,
                period_end=period_end,
                dimension="monetary_cost",
                unit=currency,
                limit_amount=envelope.monetary_limit,
            )

    def ensure_content_comment_envelope(
        self,
        *,
        provider_config_id: UUID,
        content_id: UUID,
        envelope: RunProviderBudgetEnvelope,
        at: datetime,
        currency: str = "USD",
    ) -> None:
        """首版单内容上限继承 Provider 在该 Run 的总包络；Run 层仍约束总和。"""
        if envelope.provider_config_id != provider_config_id:
            raise ProviderBudgetLineageError("Content Budget Envelope 的 Provider Config 不一致")
        period_start, period_end = self._global_period(
            provider_config_id=provider_config_id,
            at=at,
            currency=currency,
        )
        self._ensure_account(
            provider_config_id=provider_config_id,
            scope_type="content_comments",
            run_id=None,
            content_id=content_id,
            period_start=period_start,
            period_end=period_end,
            dimension="request_count",
            unit="request",
            limit_amount=Decimal(envelope.request_limit),
        )
        self._ensure_account(
            provider_config_id=provider_config_id,
            scope_type="content_comments",
            run_id=None,
            content_id=content_id,
            period_start=period_start,
            period_end=period_end,
            dimension="monetary_cost",
            unit=currency,
            limit_amount=envelope.monetary_limit,
        )

    def _global_period(
        self,
        *,
        provider_config_id: UUID,
        at: datetime,
        currency: str,
    ) -> tuple[datetime, datetime]:
        rows = (
            self._session.execute(
                select(provider_budget_accounts_table).where(
                    provider_budget_accounts_table.c.provider_config_id == provider_config_id,
                    provider_budget_accounts_table.c.scope_type == "global",
                    provider_budget_accounts_table.c.enabled.is_(True),
                    provider_budget_accounts_table.c.period_start <= at,
                    provider_budget_accounts_table.c.period_end > at,
                    (
                        (
                            (provider_budget_accounts_table.c.dimension == "request_count")
                            & (provider_budget_accounts_table.c.unit == "request")
                        )
                        | (
                            (provider_budget_accounts_table.c.dimension == "monetary_cost")
                            & (provider_budget_accounts_table.c.unit == currency)
                        )
                    ),
                )
            )
            .mappings()
            .all()
        )
        by_key = {(row["dimension"], row["unit"]): row for row in rows}
        required = {("request_count", "request"), ("monetary_cost", currency)}
        missing = required - set(by_key)
        if missing:
            missing_text = ", ".join(f"{dimension}/{unit}" for dimension, unit in sorted(missing))
            raise ProviderBudgetAccountMissingError(
                f"Provider Config 缺少当前有效 Global 预算账户: {missing_text}"
            )
        period_start = max(row["period_start"] for row in by_key.values())
        period_end = min(row["period_end"] for row in by_key.values())
        if period_end <= period_start:
            raise ProviderBudgetAccountMissingError("Global 请求/金额预算周期没有有效交集")
        return period_start, period_end

    def _ensure_account(
        self,
        *,
        provider_config_id: UUID,
        scope_type: str,
        run_id: UUID | None,
        content_id: UUID | None,
        period_start: datetime,
        period_end: datetime,
        dimension: str,
        unit: str,
        limit_amount: Decimal,
    ) -> None:
        scope_key = (
            f"run:{run_id}"
            if scope_type == "run"
            else f"run_comments:{run_id}"
            if scope_type == "run_comments"
            else f"content_comments:{content_id}"
        )
        existing = (
            self._session.execute(
                select(provider_budget_accounts_table).where(
                    provider_budget_accounts_table.c.provider_config_id == provider_config_id,
                    provider_budget_accounts_table.c.scope_key == scope_key,
                    provider_budget_accounts_table.c.period_start == period_start,
                    provider_budget_accounts_table.c.dimension == dimension,
                    provider_budget_accounts_table.c.unit == unit,
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if existing["period_end"] != period_end or Decimal(existing["limit_amount"]) != limit_amount:
                raise ProviderBudgetLineageError(
                    f"既有预算账户与派生包络不一致: {scope_key}/{dimension}/{unit}"
                )
            return

        self._service.create_account(
            ProviderBudgetAccountSpec(
                id=_budget_account_id(
                    provider_config_id=provider_config_id,
                    scope_key=scope_key,
                    period_start=period_start,
                    dimension=dimension,
                    unit=unit,
                ),
                provider_config_id=provider_config_id,
                scope_type=scope_type,  # type: ignore[arg-type]
                run_id=run_id,
                content_id=content_id,
                period_start=period_start,
                period_end=period_end,
                dimension=dimension,  # type: ignore[arg-type]
                unit=unit,
                limit_amount=limit_amount,
                enabled=True,
            )
        )


def _budget_account_id(
    *,
    provider_config_id: UUID,
    scope_key: str,
    period_start: datetime,
    dimension: str,
    unit: str,
) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"aima-ugc:provider-budget:{provider_config_id}:{scope_key}:{period_start.isoformat()}:{dimension}:{unit}",
    )


__all__ = ["PostgresProviderBudgetEnvelopeProvisioner"]
