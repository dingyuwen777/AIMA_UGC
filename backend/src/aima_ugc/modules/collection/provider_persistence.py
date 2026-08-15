"""Provider 逻辑 Request 与 reserved Attempt 的持久化入口。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.provider import ProviderBillingV1, ProviderRequestV1


@dataclass(frozen=True, slots=True)
class ProviderRequestRecord:
    """`provider_requests` 当前持久化快照。"""

    id: UUID
    scope_id: UUID
    provider_config_id: UUID | None
    provider: str
    operation: str
    request_fingerprint: str
    request_params: dict[str, object]
    pagination_input: dict[str, object]
    status: str
    attempt_count: int
    estimated_cost: Decimal
    actual_cost: Decimal
    cost_currency: str | None
    cost_unit: str | None
    unit_price_snapshot: Decimal | None
    created_at: datetime
    completed_at: datetime | None
    error_code: str | None
    error_detail: str | None


@dataclass(frozen=True, slots=True)
class ProviderAttemptRecord:
    """`provider_request_attempts` 当前持久化快照。"""

    id: UUID
    provider_request_id: UUID
    attempt_no: int
    dispatch_status: str
    dispatch_started_at: datetime | None
    completed_at: datetime | None
    http_status: int | None
    external_request_id: str | None
    raw_artifact_id: UUID | None
    estimated_cost: Decimal
    actual_cost: Decimal
    cost_currency: str | None
    cost_unit: str | None
    unit_price_snapshot: Decimal | None
    billing_status: str
    potential_duplicate_charge: bool
    error_code: str | None
    error_detail: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PreparedProviderAttempt:
    """同一调用方事务中建立或复用的 Request 与 reserved Attempt。"""

    request: ProviderRequestRecord
    attempt: ProviderAttemptRecord


class ProviderScopeNotFoundError(LookupError):
    """Provider Request 引用的 Collection Scope 不存在。"""


class ProviderRequestLineageMismatchError(ValueError):
    """Provider Contract 的 Run/平台/配置与数据库来源不一致。"""


class ProviderPersistenceConflictError(RuntimeError):
    """幂等 ID 或逻辑 Request 键已绑定到不同稳定内容。"""


class ProviderRequestNotFoundError(LookupError):
    """创建 Attempt 时目标 Provider Request 不存在。"""


class ProviderPersistenceRepository(Protocol):
    """Provider 来源链的最小持久化边界。"""

    def create_or_get_request(
        self,
        request: ProviderRequestV1,
        *,
        provider_config_id: UUID | None = None,
    ) -> ProviderRequestRecord: ...

    def get_request(self, provider_request_id: UUID) -> ProviderRequestRecord | None: ...

    def create_or_get_non_billable_attempt(
        self,
        *,
        provider_request_id: UUID,
        attempt_id: UUID,
    ) -> ProviderAttemptRecord: ...

    def create_or_get_billable_attempt(
        self,
        *,
        provider_request_id: UUID,
        attempt_id: UUID,
        billing: ProviderBillingV1,
    ) -> ProviderAttemptRecord: ...


class ProviderPersistenceService:
    """在调用方事务内编排逻辑 Request 与 reserved Attempt。"""

    def __init__(self, repository: ProviderPersistenceRepository) -> None:
        self._repository = repository

    def ensure_request(
        self,
        request: ProviderRequestV1,
        *,
        provider_config_id: UUID | None = None,
    ) -> ProviderRequestRecord:
        """按 Scope + fingerprint 建立或复用逻辑 Request。"""
        if provider_config_id is None:
            return self._repository.create_or_get_request(request)
        return self._repository.create_or_get_request(
            request,
            provider_config_id=provider_config_id,
        )

    def prepare_non_billable_attempt(
        self,
        *,
        request: ProviderRequestV1,
        attempt_id: UUID,
    ) -> PreparedProviderAttempt:
        """原子建立或复用 Request 与一个不执行外部 I/O 的 reserved Attempt。"""
        persisted_request = self.ensure_request(request)
        attempt = self._repository.create_or_get_non_billable_attempt(
            provider_request_id=persisted_request.id,
            attempt_id=attempt_id,
        )
        current_request = self._repository.get_request(persisted_request.id)
        if current_request is None:
            raise ProviderRequestNotFoundError("Provider Request 在 Attempt 创建后不可见")
        return PreparedProviderAttempt(request=current_request, attempt=attempt)

    def prepare_billable_attempt(
        self,
        *,
        request: ProviderRequestV1,
        provider_config_id: UUID,
        attempt_id: UUID,
        billing: ProviderBillingV1,
    ) -> PreparedProviderAttempt:
        """为真实外部调用建立稳定 Provider Config 关联和发送前价格快照。"""
        if billing.status != "estimated":
            raise ValueError("billable Attempt 创建时 billing.status 必须为 estimated")
        if billing.currency is None:
            raise ValueError("billable Attempt 创建时必须声明 currency")
        if billing.unit is None:
            raise ValueError("billable Attempt 创建时必须声明 unit")
        if billing.actual_cost != 0:
            raise ValueError("billable Attempt 创建时不得预填 actual_cost")
        persisted_request = self.ensure_request(
            request,
            provider_config_id=provider_config_id,
        )
        attempt = self._repository.create_or_get_billable_attempt(
            provider_request_id=persisted_request.id,
            attempt_id=attempt_id,
            billing=billing,
        )
        current_request = self._repository.get_request(persisted_request.id)
        if current_request is None:
            raise ProviderRequestNotFoundError("Provider Request 在 Attempt 创建后不可见")
        return PreparedProviderAttempt(request=current_request, attempt=attempt)
