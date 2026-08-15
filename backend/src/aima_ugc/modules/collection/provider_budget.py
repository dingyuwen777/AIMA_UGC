"""Stage 7 Provider 多级预算领域模型与编排。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

BudgetScopeType = Literal["global", "run", "run_comments", "content_comments"]
BudgetDimension = Literal["request_count", "monetary_cost"]
BudgetReservationStatus = Literal["reserved", "settled", "released", "unknown"]
ProviderBillingStatus = Literal["not_billable", "estimated", "confirmed", "unknown"]


class ProviderBudgetError(RuntimeError):
    """Provider 预算操作失败的基础异常。"""


class ProviderBudgetAccountMissingError(ProviderBudgetError):
    """调用时刻缺少必需预算账户。"""


class ProviderBudgetExceededError(ProviderBudgetError):
    """至少一个必需账户的剩余额度不足。"""


class ProviderBudgetReservationMissingError(ProviderBudgetError):
    """计费 Attempt 在发送前没有完整预算预留。"""


class ProviderBudgetLineageError(ProviderBudgetError):
    """预算父事实与 Attempt/Request/Run/Provider Config 不一致。"""


class ProviderBudgetDriftError(ProviderBudgetError):
    """账户累计值与 Reservation 账本重算结果不一致。"""


@dataclass(frozen=True, slots=True)
class ProviderBudgetRequirement:
    """一次 Attempt 在一个账户维度需要预留的额度。"""

    scope_type: BudgetScopeType
    run_id: UUID | None
    content_id: UUID | None
    dimension: BudgetDimension
    unit: str
    amount: Decimal

    @property
    def scope_key(self) -> str:
        if self.scope_type == "global":
            return "global"
        if self.scope_type == "run":
            return f"run:{self.run_id}"
        if self.scope_type == "run_comments":
            return f"run_comments:{self.run_id}"
        return f"content_comments:{self.content_id}"


@dataclass(frozen=True, slots=True)
class ProviderBudgetAccountSpec:
    """一个 Provider Config 在某时间窗口内的硬预算账户定义。"""

    id: UUID
    provider_config_id: UUID
    scope_type: BudgetScopeType
    run_id: UUID | None
    content_id: UUID | None
    period_start: datetime
    period_end: datetime
    dimension: BudgetDimension
    unit: str
    limit_amount: Decimal
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.period_start.tzinfo is None or self.period_end.tzinfo is None:
            raise ValueError("预算周期必须使用带时区时间")
        if self.period_end <= self.period_start:
            raise ValueError("预算 period_end 必须晚于 period_start")
        if self.limit_amount < 0:
            raise ValueError("预算 limit_amount 不能为负数")
        if self.scope_type == "global":
            valid_scope = self.run_id is None and self.content_id is None
        elif self.scope_type in {"run", "run_comments"}:
            valid_scope = self.run_id is not None and self.content_id is None
        else:
            valid_scope = self.run_id is None and self.content_id is not None
        if not valid_scope:
            raise ValueError("预算 scope_type 与 run_id/content_id 不一致")
        if self.dimension == "request_count":
            if self.unit != "request":
                raise ValueError("request_count 预算单位必须为 request")
        elif len(self.unit) != 3 or not self.unit.isascii() or not self.unit.isupper():
            raise ValueError("monetary_cost 预算单位必须为大写三字母币种")

    @property
    def scope_key(self) -> str:
        return ProviderBudgetRequirement(
            scope_type=self.scope_type,
            run_id=self.run_id,
            content_id=self.content_id,
            dimension=self.dimension,
            unit=self.unit,
            amount=Decimal("0"),
        ).scope_key


@dataclass(frozen=True, slots=True)
class ProviderBudgetAccountRecord:
    """`provider_budget_accounts` 当前持久化快照。"""

    id: UUID
    provider_config_id: UUID
    scope_type: BudgetScopeType
    scope_key: str
    run_id: UUID | None
    content_id: UUID | None
    period_start: datetime
    period_end: datetime
    dimension: BudgetDimension
    unit: str
    limit_amount: Decimal
    reserved_amount: Decimal
    settled_amount: Decimal
    unknown_amount: Decimal
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderBudgetReservationRecord:
    """一次 Attempt 对一个 Budget Account 的预留/终态账本。"""

    id: UUID
    budget_account_id: UUID
    provider_request_id: UUID
    provider_request_attempt_id: UUID
    scope_type: BudgetScopeType
    dimension: BudgetDimension
    unit: str
    reserved_amount: Decimal
    settled_amount: Decimal | None
    status: BudgetReservationStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderBudgetAuditSnapshot:
    """由 Reservation 重算并与账户累计值核对后的审计快照。"""

    account_id: UUID
    dimension: BudgetDimension
    unit: str
    reserved_amount: Decimal
    settled_amount: Decimal
    unknown_amount: Decimal


class ProviderBudgetRepository(Protocol):
    """Provider Budget 的 Collection Owner 持久化边界。"""

    def create_account(self, spec: ProviderBudgetAccountSpec) -> ProviderBudgetAccountRecord: ...

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
    ) -> tuple[ProviderBudgetReservationRecord, ...]: ...

    def assert_dispatch_ready(self, provider_request_attempt_id: UUID) -> None: ...

    def finalize_attempt(
        self,
        *,
        provider_request_attempt_id: UUID,
        dispatch_status: Literal["completed", "not_sent", "unknown"],
        billing_status: ProviderBillingStatus,
        actual_cost: Decimal,
        currency: str | None,
    ) -> None: ...

    def audit_account(self, account_id: UUID) -> ProviderBudgetAuditSnapshot: ...


class ProviderBudgetService:
    """不执行外部 I/O 的预算业务编排。"""

    def __init__(self, repository: ProviderBudgetRepository) -> None:
        self._repository = repository

    def create_account(self, spec: ProviderBudgetAccountSpec) -> ProviderBudgetAccountRecord:
        return self._repository.create_account(spec)

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
        build_attempt_budget_requirements(
            run_id=run_id,
            content_id=content_id,
            estimated_cost=estimated_cost,
            currency=currency,
        )
        return self._repository.reserve_attempt(
            provider_config_id=provider_config_id,
            provider_request_id=provider_request_id,
            provider_request_attempt_id=provider_request_attempt_id,
            run_id=run_id,
            content_id=content_id,
            estimated_cost=estimated_cost,
            currency=currency,
            reserved_at=reserved_at,
        )

    def assert_dispatch_ready(self, provider_request_attempt_id: UUID) -> None:
        self._repository.assert_dispatch_ready(provider_request_attempt_id)

    def finalize_attempt(
        self,
        *,
        provider_request_attempt_id: UUID,
        dispatch_status: Literal["completed", "not_sent", "unknown"],
        billing_status: ProviderBillingStatus,
        actual_cost: Decimal,
        currency: str | None,
    ) -> None:
        self._repository.finalize_attempt(
            provider_request_attempt_id=provider_request_attempt_id,
            dispatch_status=dispatch_status,
            billing_status=billing_status,
            actual_cost=actual_cost,
            currency=currency,
        )

    def audit_account(self, account_id: UUID) -> ProviderBudgetAuditSnapshot:
        return self._repository.audit_account(account_id)


def build_attempt_budget_requirements(
    *,
    run_id: UUID,
    content_id: UUID | None,
    estimated_cost: Decimal,
    currency: str,
) -> tuple[ProviderBudgetRequirement, ...]:
    """构造普通/评论 Attempt 必须同时满足的最终预算层级。"""
    if estimated_cost < 0:
        raise ValueError("estimated_cost 不能为负数")
    if len(currency) != 3 or not currency.isascii() or not currency.isupper():
        raise ValueError("currency 必须为大写三字母币种")

    scopes: list[tuple[BudgetScopeType, UUID | None, UUID | None]] = [
        ("global", None, None),
        ("run", run_id, None),
    ]
    if content_id is not None:
        scopes.extend(
            [
                ("run_comments", run_id, None),
                ("content_comments", None, content_id),
            ]
        )

    requirements: list[ProviderBudgetRequirement] = []
    for scope_type, scoped_run_id, scoped_content_id in scopes:
        requirements.append(
            ProviderBudgetRequirement(
                scope_type=scope_type,
                run_id=scoped_run_id,
                content_id=scoped_content_id,
                dimension="request_count",
                unit="request",
                amount=Decimal("1"),
            )
        )
        requirements.append(
            ProviderBudgetRequirement(
                scope_type=scope_type,
                run_id=scoped_run_id,
                content_id=scoped_content_id,
                dimension="monetary_cost",
                unit=currency,
                amount=estimated_cost,
            )
        )
    return tuple(requirements)


def completed_budget_settlement_amount(
    *,
    dimension: BudgetDimension,
    reserved_amount: Decimal,
    billing_status: ProviderBillingStatus,
    actual_cost: Decimal,
    billing_currency: str | None,
    account_unit: str,
) -> Decimal:
    """计算 completed Attempt 的预算结算值，不把 estimate 冒充权威实际费用。"""
    if reserved_amount < 0:
        raise ProviderBudgetLineageError("Provider Budget reserved_amount 不能为负数")
    if actual_cost < 0:
        raise ProviderBudgetLineageError("Provider actual_cost 不能为负数")
    if dimension == "request_count":
        return Decimal("1")

    if billing_status == "confirmed":
        if billing_currency is None or billing_currency != account_unit:
            raise ProviderBudgetLineageError("Provider 实际费用币种与预算账户不一致")
        return actual_cost

    if billing_status == "estimated":
        if billing_currency is None or billing_currency != account_unit:
            raise ProviderBudgetLineageError("Provider 估算费用币种与预算账户不一致")
        if actual_cost != 0:
            raise ProviderBudgetLineageError("estimated Billing 不得携带非零 actual_cost")
        return reserved_amount

    if billing_status == "not_billable":
        if actual_cost != 0:
            raise ProviderBudgetLineageError("not_billable Billing 不得携带非零 actual_cost")
        return Decimal("0")

    raise ProviderBudgetLineageError("completed Attempt 不允许 unknown Billing")
