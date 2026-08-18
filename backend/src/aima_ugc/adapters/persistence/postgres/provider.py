"""PostgreSQL Provider Request/Attempt Repository。"""

from __future__ import annotations

from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.contracts.provider import ProviderAttemptV1, ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.provider_dispatch import (
    ProviderAttemptStateConflict,
    ProviderDispatchPreparation,
)
from aima_ugc.modules.collection.provider_persistence import (
    ProviderAttemptRecord,
    ProviderPersistenceConflictError,
    ProviderRequestLineageMismatchError,
    ProviderRequestNotFoundError,
    ProviderRequestRecord,
    ProviderScopeNotFoundError,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.system.tables import provider_configs_table


class PostgresProviderRepository:
    """Provider 两表的唯一 Collection 写入口；事务由调用方持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_or_get_request(
        self,
        request: ProviderRequestV1,
        *,
        provider_config_id: UUID | None = None,
    ) -> ProviderRequestRecord:
        """校验 Scope/Config 来源并按 Scope + fingerprint 幂等建立逻辑 Request。"""
        scope_row = (
            self._session.execute(
                select(
                    collection_scopes_table.c.run_id,
                    collection_scopes_table.c.platform,
                ).where(collection_scopes_table.c.id == request.scope_id)
            )
            .mappings()
            .one_or_none()
        )
        if scope_row is None:
            raise ProviderScopeNotFoundError(f"Provider Scope 不存在: {request.scope_id}")
        if scope_row["run_id"] != request.run_id or scope_row["operations"] != request.platform:
            raise ProviderRequestLineageMismatchError(
                "Provider Request 的 run_id/operations 与 Collection Scope 不一致"
            )
        if provider_config_id is not None:
            config_row = (
                self._session.execute(
                    select(provider_configs_table.c.provider).where(
                        provider_configs_table.c.id == provider_config_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if config_row is None:
                raise ProviderRequestLineageMismatchError(
                    f"Provider Config 不存在: {provider_config_id}"
                )
            if config_row["provider"] != request.provider:
                raise ProviderRequestLineageMismatchError(
                    "Provider Config 的 provider 与 Provider Request 不一致"
                )

        inserted = (
            self._session.execute(
                postgresql_insert(provider_requests_table)
                .values(
                    id=request.request_id,
                    scope_id=request.scope_id,
                    provider_config_id=provider_config_id,
                    provider=request.provider,
                    operation=request.operation,
                    request_fingerprint=request.request_fingerprint,
                    request_params=request.request_params,
                    pagination_input=request.pagination_input,
                    status="pending",
                    created_at=func.clock_timestamp(),
                )
                .on_conflict_do_nothing()
                .returning(*provider_requests_table.c)
            )
            .mappings()
            .one_or_none()
        )
        if inserted is not None:
            return _row_to_request(inserted)

        candidates = list(
            self._session.execute(
                select(provider_requests_table).where(
                    or_(
                        provider_requests_table.c.id == request.request_id,
                        (provider_requests_table.c.scope_id == request.scope_id)
                        & (
                            provider_requests_table.c.request_fingerprint
                            == request.request_fingerprint
                        ),
                    )
                )
            ).mappings()
        )
        by_id = next((row for row in candidates if row["id"] == request.request_id), None)
        by_key = next(
            (
                row
                for row in candidates
                if row["scope_id"] == request.scope_id
                and row["request_fingerprint"] == request.request_fingerprint
            ),
            None,
        )
        if by_id is not None and by_key is not None and by_id["id"] != by_key["id"]:
            raise ProviderPersistenceConflictError(
                "Provider Request ID 与逻辑幂等键分别绑定到不同记录"
            )

        existing = by_key if by_key is not None else by_id
        if existing is not None and _request_matches(
            existing,
            request,
            provider_config_id=provider_config_id,
        ):
            return _row_to_request(existing)
        raise ProviderPersistenceConflictError(
            "Provider Request ID 或逻辑幂等键已绑定到不同稳定内容"
        )

    def get_request(self, provider_request_id: UUID) -> ProviderRequestRecord | None:
        row = (
            self._session.execute(
                select(provider_requests_table).where(
                    provider_requests_table.c.id == provider_request_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return _row_to_request(row) if row is not None else None

    def create_or_get_non_billable_attempt(
        self,
        *,
        provider_request_id: UUID,
        attempt_id: UUID,
    ) -> ProviderAttemptRecord:
        """串行分配非计费 Attempt 序号，并让同一 Attempt ID 事务重放幂等。"""
        request_row = self._lock_request(provider_request_id)
        existing = self._load_attempt(attempt_id)
        if existing is not None:
            if _is_same_non_billable_reservation(existing, provider_request_id):
                return _row_to_attempt(existing)
            raise ProviderPersistenceConflictError(
                "Provider Attempt ID 已绑定到不同 Request 或执行事实"
            )

        next_attempt_no = cast(int, request_row["attempt_count"]) + 1
        attempt_row = (
            self._session.execute(
                postgresql_insert(provider_request_attempts_table)
                .values(
                    id=attempt_id,
                    provider_request_id=provider_request_id,
                    attempt_no=next_attempt_no,
                    dispatch_status="reserved",
                    unit_price_snapshot=Decimal("0"),
                    billing_status="not_billable",
                    potential_duplicate_charge=False,
                    created_at=func.clock_timestamp(),
                )
                .on_conflict_do_nothing()
                .returning(*provider_request_attempts_table.c)
            )
            .mappings()
            .one_or_none()
        )
        if attempt_row is None:
            concurrent = self._load_attempt(attempt_id)
            if concurrent is not None and _is_same_non_billable_reservation(
                concurrent, provider_request_id
            ):
                return _row_to_attempt(concurrent)
            raise ProviderPersistenceConflictError(
                "Provider Attempt ID 或序号已并发绑定到不同执行事实"
            )
        self._advance_request_attempt_count(
            provider_request_id=provider_request_id,
            next_attempt_no=next_attempt_no,
        )
        return _row_to_attempt(attempt_row)

    def create_or_get_billable_attempt(
        self,
        *,
        provider_request_id: UUID,
        attempt_id: UUID,
        billing: ProviderBillingV1,
    ) -> ProviderAttemptRecord:
        """创建携带 estimated 费用快照的独立 billable reserved Attempt。"""
        if billing.status != "estimated" or billing.currency is None:
            raise ValueError("billable Attempt 必须使用带币种的 estimated Billing")
        if billing.actual_cost != 0:
            raise ValueError("reserved billable Attempt 的 actual_cost 必须为零")
        request_row = self._lock_request(provider_request_id)
        if request_row["provider_config_id"] is None:
            raise ProviderRequestLineageMismatchError(
                "billable Provider Request 必须绑定 provider_config_id"
            )

        existing = self._load_attempt(attempt_id)
        if existing is not None:
            if _is_same_billable_reservation(existing, provider_request_id, billing):
                return _row_to_attempt(existing)
            raise ProviderPersistenceConflictError(
                "Provider Attempt ID 已绑定到不同 Request 或费用事实"
            )

        next_attempt_no = cast(int, request_row["attempt_count"]) + 1
        attempt_row = (
            self._session.execute(
                postgresql_insert(provider_request_attempts_table)
                .values(
                    id=attempt_id,
                    provider_request_id=provider_request_id,
                    attempt_no=next_attempt_no,
                    dispatch_status="reserved",
                    estimated_cost=billing.estimated_cost,
                    actual_cost=Decimal("0"),
                    cost_currency=billing.currency,
                    cost_unit=billing.unit,
                    unit_price_snapshot=billing.unit_price_snapshot,
                    billing_status="estimated",
                    potential_duplicate_charge=False,
                    created_at=func.clock_timestamp(),
                )
                .on_conflict_do_nothing()
                .returning(*provider_request_attempts_table.c)
            )
            .mappings()
            .one_or_none()
        )
        if attempt_row is None:
            concurrent = self._load_attempt(attempt_id)
            if concurrent is not None and _is_same_billable_reservation(
                concurrent,
                provider_request_id,
                billing,
            ):
                return _row_to_attempt(concurrent)
            raise ProviderPersistenceConflictError(
                "Provider Attempt ID 或序号已并发绑定到不同计费执行事实"
            )
        self._advance_request_attempt_count(
            provider_request_id=provider_request_id,
            next_attempt_no=next_attempt_no,
        )
        return _row_to_attempt(attempt_row)

    def load_dispatch_preparation(
        self,
        attempt_id: UUID,
    ) -> ProviderDispatchPreparation | None:
        """沿 Attempt→Request→Scope→Run 返回受约束的 Dispatch 父事实。"""
        row = (
            self._session.execute(
                select(
                    collection_runs_table.c.job_id.label("job_id"),
                    collection_scopes_table.c.run_id.label("run_id"),
                    collection_scopes_table.c.platform.label("operations"),
                    provider_requests_table.c.id.label("request_id"),
                    provider_requests_table.c.scope_id.label("scope_id"),
                    provider_requests_table.c.provider.label("provider"),
                    provider_requests_table.c.operation.label("operation"),
                    provider_requests_table.c.request_fingerprint.label("request_fingerprint"),
                    provider_requests_table.c.request_params.label("request_params"),
                    provider_requests_table.c.pagination_input.label("pagination_input"),
                )
                .select_from(
                    provider_request_attempts_table.join(
                        provider_requests_table,
                        provider_request_attempts_table.c.provider_request_id
                        == provider_requests_table.c.id,
                    )
                    .join(
                        collection_scopes_table,
                        provider_requests_table.c.scope_id == collection_scopes_table.c.id,
                    )
                    .join(
                        collection_runs_table,
                        collection_scopes_table.c.run_id == collection_runs_table.c.id,
                    )
                )
                .where(provider_request_attempts_table.c.id == attempt_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        attempt_row = (
            self._session.execute(
                select(provider_request_attempts_table).where(
                    provider_request_attempts_table.c.id == attempt_id
                )
            )
            .mappings()
            .one()
        )
        request = ProviderRequestV1(
            request_id=row["request_id"],
            run_id=row["run_id"],
            scope_id=row["scope_id"],
            provider=row["provider"],
            platform=row["operations"],
            operation=row["operation"],
            request_fingerprint=row["request_fingerprint"],
            request_params=row["request_params"],
            pagination_input=row["pagination_input"],
        )
        return ProviderDispatchPreparation(
            job_id=row["job_id"],
            request=request,
            attempt=_row_to_attempt(attempt_row),
        )

    def mark_dispatching(self, attempt_id: UUID) -> ProviderAttemptRecord:
        """仅允许一个竞争者将 reserved Attempt 推进到 dispatching。"""
        started_at = func.clock_timestamp()
        row = (
            self._session.execute(
                update(provider_request_attempts_table)
                .where(
                    provider_request_attempts_table.c.id == attempt_id,
                    provider_request_attempts_table.c.dispatch_status == "reserved",
                )
                .values(
                    dispatch_status="dispatching",
                    dispatch_started_at=started_at,
                )
                .returning(*provider_request_attempts_table.c)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ProviderAttemptStateConflict("Provider Attempt 不是 reserved")
        self._session.execute(
            update(provider_requests_table)
            .where(
                provider_requests_table.c.id == row["provider_request_id"],
                provider_requests_table.c.attempt_count == row["attempt_no"],
            )
            .values(
                status="dispatching",
                completed_at=None,
                error_code=None,
                error_detail=None,
            )
        )
        return _row_to_attempt(row)

    def finalize_dispatch(
        self,
        *,
        attempt: ProviderAttemptV1,
        raw_artifact_id: UUID | None,
    ) -> ProviderAttemptRecord:
        """以 CAS 保存终态 Attempt，并更新逻辑 Request 当前汇总。"""
        if attempt.dispatch_status not in {"completed", "not_sent", "unknown"}:
            raise ValueError("Provider Dispatch 终态无效")
        if attempt.dispatch_status == "completed":
            if raw_artifact_id is None or attempt.raw_artifact_id != raw_artifact_id:
                raise ValueError("completed Attempt 必须关联同一 Raw Artifact")
        elif attempt.dispatch_status == "unknown":
            if attempt.raw_artifact_id != raw_artifact_id:
                raise ValueError("unknown Attempt 的 Raw Artifact 引用不一致")
        elif raw_artifact_id is not None or attempt.raw_artifact_id is not None:
            raise ValueError("not_sent Attempt 不能关联 Raw Artifact")

        request_row = self._lock_request(attempt.provider_request_id)
        currency = _merge_cost_dimension(
            request_row["cost_currency"],
            attempt.billing.currency,
            name="currency",
        )
        cost_unit = _merge_cost_dimension(
            request_row["cost_unit"],
            attempt.billing.unit,
            name="unit",
        )
        error_code = attempt.error.code if attempt.error is not None else None
        error_detail = attempt.error.safe_summary if attempt.error is not None else None
        row = (
            self._session.execute(
                update(provider_request_attempts_table)
                .where(
                    provider_request_attempts_table.c.id == attempt.attempt_id,
                    provider_request_attempts_table.c.provider_request_id
                    == attempt.provider_request_id,
                    provider_request_attempts_table.c.attempt_no == attempt.attempt_no,
                    provider_request_attempts_table.c.dispatch_status == "dispatching",
                )
                .values(
                    dispatch_status=attempt.dispatch_status,
                    dispatch_started_at=attempt.dispatch_started_at,
                    completed_at=attempt.completed_at,
                    http_status=attempt.http_status,
                    external_request_id=attempt.external_request_id,
                    raw_artifact_id=raw_artifact_id,
                    estimated_cost=attempt.billing.estimated_cost,
                    actual_cost=attempt.billing.actual_cost,
                    cost_currency=attempt.billing.currency,
                    cost_unit=attempt.billing.unit,
                    unit_price_snapshot=attempt.billing.unit_price_snapshot,
                    billing_status=attempt.billing.status,
                    potential_duplicate_charge=attempt.potential_duplicate_charge,
                    error_code=error_code,
                    error_detail=error_detail,
                )
                .returning(*provider_request_attempts_table.c)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ProviderAttemptStateConflict("Provider Attempt 不是当前 dispatching 状态")

        request_values: dict[str, object] = {
            "estimated_cost": (
                cast(Decimal, request_row["estimated_cost"]) + attempt.billing.estimated_cost
            ),
            "actual_cost": (
                cast(Decimal, request_row["actual_cost"]) + attempt.billing.actual_cost
            ),
            "cost_currency": currency,
            "cost_unit": cost_unit,
        }
        if request_row["attempt_count"] == attempt.attempt_no:
            request_values.update(
                status=attempt.dispatch_status,
                unit_price_snapshot=attempt.billing.unit_price_snapshot,
                completed_at=attempt.completed_at,
                error_code=error_code,
                error_detail=error_detail,
            )
        self._session.execute(
            update(provider_requests_table)
            .where(provider_requests_table.c.id == attempt.provider_request_id)
            .values(**request_values)
        )
        return _row_to_attempt(row)

    def list_attempts(self, provider_request_id: UUID) -> list[ProviderAttemptRecord]:
        rows = self._session.execute(
            select(provider_request_attempts_table)
            .where(provider_request_attempts_table.c.provider_request_id == provider_request_id)
            .order_by(provider_request_attempts_table.c.attempt_no)
        ).mappings()
        return [_row_to_attempt(row) for row in rows]

    def _lock_request(self, provider_request_id: UUID) -> RowMapping:
        row = (
            self._session.execute(
                select(provider_requests_table)
                .where(provider_requests_table.c.id == provider_request_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ProviderRequestNotFoundError(f"Provider Request 不存在: {provider_request_id}")
        return row

    def _load_attempt(self, attempt_id: UUID) -> RowMapping | None:
        return (
            self._session.execute(
                select(provider_request_attempts_table).where(
                    provider_request_attempts_table.c.id == attempt_id
                )
            )
            .mappings()
            .one_or_none()
        )

    def _advance_request_attempt_count(
        self,
        *,
        provider_request_id: UUID,
        next_attempt_no: int,
    ) -> None:
        self._session.execute(
            update(provider_requests_table)
            .where(provider_requests_table.c.id == provider_request_id)
            .values(
                attempt_count=next_attempt_no,
                status="pending",
                completed_at=None,
                error_code=None,
                error_detail=None,
            )
        )


def _request_matches(
    row: RowMapping,
    request: ProviderRequestV1,
    *,
    provider_config_id: UUID | None,
) -> bool:
    config_matches = provider_config_id is None or row["provider_config_id"] == provider_config_id
    return bool(
        config_matches
        and row["scope_id"] == request.scope_id
        and row["provider"] == request.provider
        and row["operation"] == request.operation
        and row["request_fingerprint"] == request.request_fingerprint
        and row["request_params"] == request.request_params
        and row["pagination_input"] == request.pagination_input
    )


def _is_same_non_billable_reservation(row: RowMapping, provider_request_id: UUID) -> bool:
    return bool(
        row["provider_request_id"] == provider_request_id
        and row["dispatch_status"] == "reserved"
        and row["dispatch_started_at"] is None
        and row["completed_at"] is None
        and row["raw_artifact_id"] is None
        and row["billing_status"] == "not_billable"
        and row["estimated_cost"] == 0
        and row["actual_cost"] == 0
        and (row["unit_price_snapshot"] is None or row["unit_price_snapshot"] == 0)
        and cast(bool, row["potential_duplicate_charge"]) is False
    )


def _is_same_billable_reservation(
    row: RowMapping,
    provider_request_id: UUID,
    billing: ProviderBillingV1,
) -> bool:
    return bool(
        row["provider_request_id"] == provider_request_id
        and row["dispatch_status"] == "reserved"
        and row["dispatch_started_at"] is None
        and row["completed_at"] is None
        and row["raw_artifact_id"] is None
        and row["billing_status"] == "estimated"
        and row["estimated_cost"] == billing.estimated_cost
        and row["actual_cost"] == 0
        and row["cost_currency"] == billing.currency
        and row["cost_unit"] == billing.unit
        and row["unit_price_snapshot"] == billing.unit_price_snapshot
        and cast(bool, row["potential_duplicate_charge"]) is False
    )


def _merge_cost_dimension(
    current: str | None,
    incoming: str | None,
    *,
    name: str,
) -> str | None:
    if current is not None and incoming is not None and current != incoming:
        raise ProviderPersistenceConflictError(
            f"Provider Request 的费用 {name} 与已有 Attempt 不一致"
        )
    return incoming if incoming is not None else current


def _row_to_request(row: RowMapping) -> ProviderRequestRecord:
    return ProviderRequestRecord(
        id=cast(UUID, row["id"]),
        scope_id=cast(UUID, row["scope_id"]),
        provider_config_id=cast(UUID | None, row["provider_config_id"]),
        provider=cast(str, row["provider"]),
        operation=cast(str, row["operation"]),
        request_fingerprint=cast(str, row["request_fingerprint"]),
        request_params=cast(dict[str, object], row["request_params"]),
        pagination_input=cast(dict[str, object], row["pagination_input"]),
        status=cast(str, row["status"]),
        attempt_count=cast(int, row["attempt_count"]),
        estimated_cost=cast(Decimal, row["estimated_cost"]),
        actual_cost=cast(Decimal, row["actual_cost"]),
        cost_currency=cast(str | None, row["cost_currency"]),
        cost_unit=cast(str | None, row["cost_unit"]),
        unit_price_snapshot=cast(Decimal | None, row["unit_price_snapshot"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        error_code=cast(str | None, row["error_code"]),
        error_detail=cast(str | None, row["error_detail"]),
    )


def _row_to_attempt(row: RowMapping) -> ProviderAttemptRecord:
    return ProviderAttemptRecord(
        id=cast(UUID, row["id"]),
        provider_request_id=cast(UUID, row["provider_request_id"]),
        attempt_no=cast(int, row["attempt_no"]),
        dispatch_status=cast(str, row["dispatch_status"]),
        dispatch_started_at=row["dispatch_started_at"],
        completed_at=row["completed_at"],
        http_status=cast(int | None, row["http_status"]),
        external_request_id=cast(str | None, row["external_request_id"]),
        raw_artifact_id=cast(UUID | None, row["raw_artifact_id"]),
        estimated_cost=cast(Decimal, row["estimated_cost"]),
        actual_cost=cast(Decimal, row["actual_cost"]),
        cost_currency=cast(str | None, row["cost_currency"]),
        cost_unit=cast(str | None, row["cost_unit"]),
        unit_price_snapshot=cast(Decimal | None, row["unit_price_snapshot"]),
        billing_status=cast(str, row["billing_status"]),
        potential_duplicate_charge=cast(bool, row["potential_duplicate_charge"]),
        error_code=cast(str | None, row["error_code"]),
        error_detail=cast(str | None, row["error_detail"]),
        created_at=row["created_at"],
    )
