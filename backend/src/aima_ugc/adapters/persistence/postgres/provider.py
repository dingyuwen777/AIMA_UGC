"""PostgreSQL Provider Request/Attempt Repository。"""

from __future__ import annotations

from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.contracts.provider import ProviderRequestV1
from aima_ugc.modules.collection.provider_persistence import (
    ProviderAttemptRecord,
    ProviderPersistenceConflictError,
    ProviderRequestLineageMismatchError,
    ProviderRequestNotFoundError,
    ProviderRequestRecord,
    ProviderScopeNotFoundError,
)
from aima_ugc.modules.collection.tables import (
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)


class PostgresProviderRepository:
    """Provider 两表的唯一 Collection 写入口；事务由调用方持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_or_get_request(self, request: ProviderRequestV1) -> ProviderRequestRecord:
        """校验 Scope 来源并按 Scope + fingerprint 幂等建立逻辑 Request。"""
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
        if scope_row["run_id"] != request.run_id or scope_row["platform"] != request.platform:
            raise ProviderRequestLineageMismatchError(
                "Provider Request 的 run_id/platform 与 Collection Scope 不一致"
            )

        inserted = (
            self._session.execute(
                postgresql_insert(provider_requests_table)
                .values(
                    id=request.request_id,
                    scope_id=request.scope_id,
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
        if existing is not None and _request_matches(existing, request):
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
        """串行分配 Attempt 序号，并让同一 Attempt ID 的事务重放保持幂等。"""
        request_row = (
            self._session.execute(
                select(provider_requests_table)
                .where(provider_requests_table.c.id == provider_request_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if request_row is None:
            raise ProviderRequestNotFoundError(f"Provider Request 不存在: {provider_request_id}")

        existing = (
            self._session.execute(
                select(provider_request_attempts_table).where(
                    provider_request_attempts_table.c.id == attempt_id
                )
            )
            .mappings()
            .one_or_none()
        )
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
            concurrent = (
                self._session.execute(
                    select(provider_request_attempts_table).where(
                        provider_request_attempts_table.c.id == attempt_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if concurrent is not None and _is_same_non_billable_reservation(
                concurrent, provider_request_id
            ):
                return _row_to_attempt(concurrent)
            raise ProviderPersistenceConflictError(
                "Provider Attempt ID 或序号已并发绑定到不同执行事实"
            )
        self._session.execute(
            update(provider_requests_table)
            .where(provider_requests_table.c.id == provider_request_id)
            .values(attempt_count=next_attempt_no)
        )
        return _row_to_attempt(attempt_row)

    def list_attempts(self, provider_request_id: UUID) -> list[ProviderAttemptRecord]:
        rows = self._session.execute(
            select(provider_request_attempts_table)
            .where(provider_request_attempts_table.c.provider_request_id == provider_request_id)
            .order_by(provider_request_attempts_table.c.attempt_no)
        ).mappings()
        return [_row_to_attempt(row) for row in rows]


def _request_matches(row: RowMapping, request: ProviderRequestV1) -> bool:
    return bool(
        row["scope_id"] == request.scope_id
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


def _row_to_request(row: RowMapping) -> ProviderRequestRecord:
    return ProviderRequestRecord(
        id=cast(UUID, row["id"]),
        scope_id=cast(UUID, row["scope_id"]),
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
