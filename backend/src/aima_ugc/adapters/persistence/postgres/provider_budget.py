"""Provider Budget Ledger 的 PostgreSQL Collection Owner Repository。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.provider_budget import (
    BudgetDimension,
    BudgetReservationStatus,
    BudgetScopeType,
    ProviderBudgetAccountMissingError,
    ProviderBudgetAccountRecord,
    ProviderBudgetAccountSpec,
    ProviderBudgetAuditSnapshot,
    ProviderBudgetDriftError,
    ProviderBudgetExceededError,
    ProviderBudgetLineageError,
    ProviderBudgetReservationMissingError,
    ProviderBudgetReservationRecord,
    build_attempt_budget_requirements,
)
from aima_ugc.modules.collection.tables import (
    collection_scopes_table,
    provider_budget_accounts_table,
    provider_budget_reservations_table,
    provider_request_attempts_table,
    provider_requests_table,
)


class PostgresProviderBudgetRepository:
    """预算账户与 Reservation 的唯一 Collection 写入口；事务由调用方持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_account(self, spec: ProviderBudgetAccountSpec) -> ProviderBudgetAccountRecord:
        now = func.clock_timestamp()
        row = (
            self._session.execute(
                insert(provider_budget_accounts_table)
                .values(
                    id=spec.id,
                    provider_config_id=spec.provider_config_id,
                    scope_type=spec.scope_type,
                    scope_key=spec.scope_key,
                    run_id=spec.run_id,
                    content_id=spec.content_id,
                    period_start=spec.period_start,
                    period_end=spec.period_end,
                    dimension=spec.dimension,
                    unit=spec.unit,
                    limit_amount=spec.limit_amount,
                    enabled=spec.enabled,
                    created_at=now,
                    updated_at=now,
                )
                .returning(provider_budget_accounts_table)
            )
            .mappings()
            .one()
        )
        return _account_from_row(row)

    def reserve_attempt(
        self,
        *,
        provider_config_id: UUID,
        provider_request_id: UUID,
        provider_request_attempt_id: UUID,
        run_id: UUID,
        content_id: UUID | None,
        estimated_cost: Decimal,
        currency: str,
        reserved_at: datetime,
    ) -> tuple[ProviderBudgetReservationRecord, ...]:
        requirements = build_attempt_budget_requirements(
            run_id=run_id,
            content_id=content_id,
            estimated_cost=estimated_cost,
            currency=currency,
        )
        self._validate_attempt_lineage(
            provider_config_id=provider_config_id,
            provider_request_id=provider_request_id,
            provider_request_attempt_id=provider_request_attempt_id,
            run_id=run_id,
            estimated_cost=estimated_cost,
            currency=currency,
        )

        existing = self._reservation_rows(provider_request_attempt_id)
        if existing:
            return self._validate_replay(existing, requirements)

        keys = {(item.scope_key, item.dimension, item.unit) for item in requirements}
        account_rows = list(
            self._session.execute(
                select(provider_budget_accounts_table)
                .where(
                    provider_budget_accounts_table.c.provider_config_id == provider_config_id,
                    provider_budget_accounts_table.c.enabled.is_(True),
                    provider_budget_accounts_table.c.period_start <= reserved_at,
                    provider_budget_accounts_table.c.period_end > reserved_at,
                )
                .order_by(provider_budget_accounts_table.c.id)
                .with_for_update()
            ).mappings()
        )
        account_by_key = {
            (row["scope_key"], row["dimension"], row["unit"]): row
            for row in account_rows
            if (row["scope_key"], row["dimension"], row["unit"]) in keys
        }
        missing = keys - set(account_by_key)
        if missing:
            missing_text = ", ".join(
                f"{scope_key}/{dimension}/{unit}" for scope_key, dimension, unit in sorted(missing)
            )
            raise ProviderBudgetAccountMissingError(
                f"Provider Attempt 缺少覆盖调用时刻的预算账户: {missing_text}"
            )

        created: list[ProviderBudgetReservationRecord] = []
        for requirement in requirements:
            key = (requirement.scope_key, requirement.dimension, requirement.unit)
            account = account_by_key[key]
            used = (
                cast(Decimal, account["reserved_amount"])
                + cast(Decimal, account["settled_amount"])
                + cast(Decimal, account["unknown_amount"])
            )
            if used + requirement.amount > cast(Decimal, account["limit_amount"]):
                raise ProviderBudgetExceededError(
                    "Provider Budget 额度不足: "
                    f"scope={requirement.scope_key}, dimension={requirement.dimension}, "
                    f"unit={requirement.unit}"
                )

            now = func.clock_timestamp()
            reservation = (
                self._session.execute(
                    insert(provider_budget_reservations_table)
                    .values(
                        id=uuid4(),
                        budget_account_id=account["id"],
                        provider_request_id=provider_request_id,
                        provider_request_attempt_id=provider_request_attempt_id,
                        reserved_amount=requirement.amount,
                        settled_amount=None,
                        status="reserved",
                        created_at=now,
                        updated_at=now,
                    )
                    .returning(provider_budget_reservations_table)
                )
                .mappings()
                .one()
            )
            self._session.execute(
                update(provider_budget_accounts_table)
                .where(provider_budget_accounts_table.c.id == account["id"])
                .values(
                    reserved_amount=(
                        provider_budget_accounts_table.c.reserved_amount + requirement.amount
                    ),
                    updated_at=func.clock_timestamp(),
                )
            )
            created.append(_reservation_from_rows(reservation, account))
        return tuple(created)

    def assert_dispatch_ready(self, provider_request_attempt_id: UUID) -> None:
        attempt = self._attempt_budget_context(provider_request_attempt_id)
        if attempt is None:
            raise ProviderBudgetReservationMissingError(
                f"Provider Attempt 不存在: {provider_request_attempt_id}"
            )
        if attempt["billing_status"] == "not_billable":
            return
        if attempt["billing_status"] != "estimated":
            raise ProviderBudgetReservationMissingError(
                "只有 estimated 计费 Attempt 可以从 reserved 进入 dispatching"
            )
        provider_config_id = cast(UUID | None, attempt["provider_config_id"])
        if provider_config_id is None:
            raise ProviderBudgetReservationMissingError(
                "计费 Provider Request 缺少 provider_config_id"
            )
        currency = cast(str | None, attempt["cost_currency"])
        if currency is None:
            raise ProviderBudgetReservationMissingError("计费 Provider Attempt 缺少 cost_currency")

        rows = self._reservation_rows(provider_request_attempt_id)
        if not rows:
            raise ProviderBudgetReservationMissingError("计费 Provider Attempt 尚未取得预算预留")
        if any(row["reservation_status"] != "reserved" for row in rows):
            raise ProviderBudgetReservationMissingError(
                "Provider Attempt 的预算 Reservation 已不是 reserved"
            )
        if any(row["provider_config_id"] != provider_config_id for row in rows):
            raise ProviderBudgetReservationMissingError("预算账户与 Provider Request Config 不一致")

        scope_types = {cast(str, row["scope_type"]) for row in rows}
        content_id = None
        if scope_types - {"global", "run"}:
            if scope_types != {"global", "run", "run_comments", "content_comments"}:
                raise ProviderBudgetReservationMissingError("评论 Attempt 的四层预算预留不完整")
            content_ids = {
                cast(UUID, row["content_id"])
                for row in rows
                if row["scope_type"] == "content_comments"
            }
            if len(content_ids) != 1:
                raise ProviderBudgetReservationMissingError("content_comments 预算目标不唯一")
            content_id = next(iter(content_ids))

        requirements = build_attempt_budget_requirements(
            run_id=cast(UUID, attempt["run_id"]),
            content_id=content_id,
            estimated_cost=cast(Decimal, attempt["estimated_cost"]),
            currency=currency,
        )
        expected = {
            (item.scope_key, item.dimension, item.unit): item.amount for item in requirements
        }
        actual = {
            (row["scope_key"], row["dimension"], row["unit"]): cast(
                Decimal, row["reservation_reserved_amount"]
            )
            for row in rows
        }
        if actual != expected:
            raise ProviderBudgetReservationMissingError(
                "Provider Attempt 的预算预留层级或金额不完整"
            )

        now = self._session.scalar(select(func.clock_timestamp()))
        if now is None or any(not (row["period_start"] <= now < row["period_end"]) for row in rows):
            raise ProviderBudgetReservationMissingError(
                "Provider Attempt 的预算周期已不覆盖发送时刻"
            )

    def finalize_attempt(
        self,
        *,
        provider_request_attempt_id: UUID,
        dispatch_status: str,
        actual_cost: Decimal,
        currency: str | None,
    ) -> None:
        rows = list(
            self._session.execute(
                select(
                    provider_budget_reservations_table,
                    provider_budget_accounts_table.c.dimension.label("dimension"),
                    provider_budget_accounts_table.c.unit.label("unit"),
                )
                .select_from(
                    provider_budget_reservations_table.join(
                        provider_budget_accounts_table,
                        provider_budget_reservations_table.c.budget_account_id
                        == provider_budget_accounts_table.c.id,
                    )
                )
                .where(
                    provider_budget_reservations_table.c.provider_request_attempt_id
                    == provider_request_attempt_id
                )
                .order_by(provider_budget_accounts_table.c.id)
                .with_for_update(of=provider_budget_accounts_table)
            ).mappings()
        )
        if not rows:
            return
        if any(row["status"] != "reserved" for row in rows):
            raise ProviderBudgetLineageError(
                "Provider Budget Reservation 不是可结算的 reserved 状态"
            )
        if dispatch_status not in {"completed", "not_sent", "unknown"}:
            raise ValueError("Provider Budget 终态无效")

        for row in rows:
            reserved = cast(Decimal, row["reserved_amount"])
            dimension = cast(str, row["dimension"])
            unit = cast(str, row["unit"])
            if dispatch_status == "completed":
                if dimension == "request_count":
                    settled = Decimal("1")
                else:
                    if currency is None or currency != unit:
                        raise ProviderBudgetLineageError("Provider 实际费用币种与预算账户不一致")
                    settled = actual_cost
                status = "settled"
                account_values = {
                    "reserved_amount": provider_budget_accounts_table.c.reserved_amount - reserved,
                    "settled_amount": provider_budget_accounts_table.c.settled_amount + settled,
                }
            elif dispatch_status == "unknown":
                settled = None
                status = "unknown"
                account_values = {
                    "reserved_amount": provider_budget_accounts_table.c.reserved_amount - reserved,
                    "unknown_amount": provider_budget_accounts_table.c.unknown_amount + reserved,
                }
            else:
                settled = Decimal("0")
                status = "released"
                account_values = {
                    "reserved_amount": provider_budget_accounts_table.c.reserved_amount - reserved
                }

            self._session.execute(
                update(provider_budget_accounts_table)
                .where(provider_budget_accounts_table.c.id == row["budget_account_id"])
                .values(**account_values, updated_at=func.clock_timestamp())
            )
            self._session.execute(
                update(provider_budget_reservations_table)
                .where(provider_budget_reservations_table.c.id == row["id"])
                .values(
                    status=status,
                    settled_amount=settled,
                    updated_at=func.clock_timestamp(),
                )
            )

    def audit_account(self, account_id: UUID) -> ProviderBudgetAuditSnapshot:
        account = (
            self._session.execute(
                select(provider_budget_accounts_table).where(
                    provider_budget_accounts_table.c.id == account_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if account is None:
            raise ProviderBudgetAccountMissingError(f"Provider Budget Account 不存在: {account_id}")
        rows = list(
            self._session.execute(
                select(provider_budget_reservations_table).where(
                    provider_budget_reservations_table.c.budget_account_id == account_id
                )
            ).mappings()
        )
        reserved = sum(
            (
                cast(Decimal, row["reserved_amount"])
                for row in rows
                if row["status"] == "reserved"
            ),
            Decimal("0"),
        )
        settled = sum(
            (
                cast(Decimal, row["settled_amount"])
                for row in rows
                if row["status"] == "settled" and row["settled_amount"] is not None
            ),
            Decimal("0"),
        )
        unknown = sum(
            (
                cast(Decimal, row["reserved_amount"])
                for row in rows
                if row["status"] == "unknown"
            ),
            Decimal("0"),
        )
        if (
            reserved != cast(Decimal, account["reserved_amount"])
            or settled != cast(Decimal, account["settled_amount"])
            or unknown != cast(Decimal, account["unknown_amount"])
        ):
            raise ProviderBudgetDriftError(f"Provider Budget Account 聚合值漂移: {account_id}")
        return ProviderBudgetAuditSnapshot(
            account_id=account_id,
            dimension=cast(BudgetDimension, account["dimension"]),
            unit=cast(str, account["unit"]),
            reserved_amount=reserved,
            settled_amount=settled,
            unknown_amount=unknown,
        )

    def _validate_attempt_lineage(
        self,
        *,
        provider_config_id: UUID,
        provider_request_id: UUID,
        provider_request_attempt_id: UUID,
        run_id: UUID,
        estimated_cost: Decimal,
        currency: str,
    ) -> None:
        row = self._attempt_budget_context(provider_request_attempt_id)
        if row is None:
            raise ProviderBudgetLineageError(
                f"Provider Attempt 不存在: {provider_request_attempt_id}"
            )
        if (
            row["provider_request_id"] != provider_request_id
            or row["run_id"] != run_id
            or row["provider_config_id"] != provider_config_id
        ):
            raise ProviderBudgetLineageError("Budget 与 Provider Attempt 来源链不一致")
        if row["dispatch_status"] != "reserved" or row["billing_status"] != "estimated":
            raise ProviderBudgetLineageError("只有 reserved/estimated Attempt 可以取得预算预留")
        if row["estimated_cost"] != estimated_cost or row["cost_currency"] != currency:
            raise ProviderBudgetLineageError("Budget 估算金额/币种与 Provider Attempt 不一致")

    def _attempt_budget_context(self, attempt_id: UUID) -> RowMapping | None:
        return (
            self._session.execute(
                select(
                    provider_request_attempts_table.c.id.label("attempt_id"),
                    provider_request_attempts_table.c.provider_request_id,
                    provider_request_attempts_table.c.dispatch_status,
                    provider_request_attempts_table.c.billing_status,
                    provider_request_attempts_table.c.estimated_cost,
                    provider_request_attempts_table.c.cost_currency,
                    provider_requests_table.c.provider_config_id,
                    collection_scopes_table.c.run_id,
                )
                .select_from(
                    provider_request_attempts_table.join(
                        provider_requests_table,
                        provider_request_attempts_table.c.provider_request_id
                        == provider_requests_table.c.id,
                    ).join(
                        collection_scopes_table,
                        provider_requests_table.c.scope_id == collection_scopes_table.c.id,
                    )
                )
                .where(provider_request_attempts_table.c.id == attempt_id)
            )
            .mappings()
            .one_or_none()
        )

    def _reservation_rows(self, attempt_id: UUID) -> list[RowMapping]:
        return list(
            self._session.execute(
                select(
                    provider_budget_reservations_table.c.id.label("reservation_id"),
                    provider_budget_reservations_table.c.budget_account_id,
                    provider_budget_reservations_table.c.provider_request_id,
                    provider_budget_reservations_table.c.provider_request_attempt_id,
                    provider_budget_reservations_table.c.reserved_amount.label(
                        "reservation_reserved_amount"
                    ),
                    provider_budget_reservations_table.c.settled_amount.label(
                        "reservation_settled_amount"
                    ),
                    provider_budget_reservations_table.c.status.label("reservation_status"),
                    provider_budget_reservations_table.c.created_at.label("reservation_created_at"),
                    provider_budget_reservations_table.c.updated_at.label("reservation_updated_at"),
                    provider_budget_accounts_table.c.provider_config_id,
                    provider_budget_accounts_table.c.scope_type,
                    provider_budget_accounts_table.c.scope_key,
                    provider_budget_accounts_table.c.run_id,
                    provider_budget_accounts_table.c.content_id,
                    provider_budget_accounts_table.c.period_start,
                    provider_budget_accounts_table.c.period_end,
                    provider_budget_accounts_table.c.dimension,
                    provider_budget_accounts_table.c.unit,
                )
                .select_from(
                    provider_budget_reservations_table.join(
                        provider_budget_accounts_table,
                        provider_budget_reservations_table.c.budget_account_id
                        == provider_budget_accounts_table.c.id,
                    )
                )
                .where(
                    provider_budget_reservations_table.c.provider_request_attempt_id == attempt_id
                )
                .order_by(
                    provider_budget_accounts_table.c.scope_key,
                    provider_budget_accounts_table.c.dimension,
                )
            ).mappings()
        )

    def _validate_replay(
        self,
        rows: list[RowMapping],
        requirements,
    ) -> tuple[ProviderBudgetReservationRecord, ...]:
        expected = {
            (item.scope_key, item.dimension, item.unit): item.amount for item in requirements
        }
        rows_by_key = {
            (row["scope_key"], row["dimension"], row["unit"]): row
            for row in rows
            if row["reservation_status"] == "reserved"
        }
        actual = {
            key: cast(Decimal, row["reservation_reserved_amount"])
            for key, row in rows_by_key.items()
        }
        if actual != expected or len(rows) != len(expected):
            raise ProviderBudgetLineageError("同一 Attempt 已存在不同或非 reserved 的预算账本")
        return tuple(
            _reservation_from_joined_row(
                rows_by_key[(requirement.scope_key, requirement.dimension, requirement.unit)]
            )
            for requirement in requirements
        )


def _account_from_row(row: RowMapping) -> ProviderBudgetAccountRecord:
    return ProviderBudgetAccountRecord(
        id=cast(UUID, row["id"]),
        provider_config_id=cast(UUID, row["provider_config_id"]),
        scope_type=cast(BudgetScopeType, row["scope_type"]),
        scope_key=cast(str, row["scope_key"]),
        run_id=cast(UUID | None, row["run_id"]),
        content_id=cast(UUID | None, row["content_id"]),
        period_start=row["period_start"],
        period_end=row["period_end"],
        dimension=cast(BudgetDimension, row["dimension"]),
        unit=cast(str, row["unit"]),
        limit_amount=cast(Decimal, row["limit_amount"]),
        reserved_amount=cast(Decimal, row["reserved_amount"]),
        settled_amount=cast(Decimal, row["settled_amount"]),
        unknown_amount=cast(Decimal, row["unknown_amount"]),
        enabled=cast(bool, row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _reservation_from_rows(
    reservation: RowMapping,
    account: RowMapping,
) -> ProviderBudgetReservationRecord:
    return ProviderBudgetReservationRecord(
        id=cast(UUID, reservation["id"]),
        budget_account_id=cast(UUID, reservation["budget_account_id"]),
        provider_request_id=cast(UUID, reservation["provider_request_id"]),
        provider_request_attempt_id=cast(UUID, reservation["provider_request_attempt_id"]),
        scope_type=cast(BudgetScopeType, account["scope_type"]),
        dimension=cast(BudgetDimension, account["dimension"]),
        unit=cast(str, account["unit"]),
        reserved_amount=cast(Decimal, reservation["reserved_amount"]),
        settled_amount=cast(Decimal | None, reservation["settled_amount"]),
        status=cast(BudgetReservationStatus, reservation["status"]),
        created_at=reservation["created_at"],
        updated_at=reservation["updated_at"],
    )


def _reservation_from_joined_row(row: RowMapping) -> ProviderBudgetReservationRecord:
    return ProviderBudgetReservationRecord(
        id=cast(UUID, row["reservation_id"]),
        budget_account_id=cast(UUID, row["budget_account_id"]),
        provider_request_id=cast(UUID, row["provider_request_id"]),
        provider_request_attempt_id=cast(UUID, row["provider_request_attempt_id"]),
        scope_type=cast(BudgetScopeType, row["scope_type"]),
        dimension=cast(BudgetDimension, row["dimension"]),
        unit=cast(str, row["unit"]),
        reserved_amount=cast(Decimal, row["reservation_reserved_amount"]),
        settled_amount=cast(Decimal | None, row["reservation_settled_amount"]),
        status=cast(BudgetReservationStatus, row["reservation_status"]),
        created_at=row["reservation_created_at"],
        updated_at=row["reservation_updated_at"],
    )
