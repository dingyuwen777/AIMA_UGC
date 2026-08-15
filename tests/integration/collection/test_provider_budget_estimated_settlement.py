"""TikHub-style estimated Billing 的 PostgreSQL 预算结算回归。"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from aima_ugc.adapters.persistence.postgres.provider_budget import (
    PostgresProviderBudgetRepository,
)
from aima_ugc.adapters.persistence.postgres.provider_dispatch import (
    PostgresProviderDispatchPersistence,
)
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.contracts.provider import ProviderBillingV1
from aima_ugc.modules.collection.provider_budget import ProviderBudgetService
from aima_ugc.modules.collection.provider_dispatch import ProviderDispatchService
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransportRequest,
    ProviderTransportResponse,
)
from aima_ugc.modules.collection.tables import provider_request_attempts_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import select

from tests.integration.collection.test_provider_budget import (
    _clear_data,
    _create_accounts,
    _prepare_context,
    _raw_service,
    _reserve,
)


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        _clear_data(connection)
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            _clear_data(connection)
        runtime.dispose()


def test_completed_estimated_billing_keeps_actual_zero_and_settles_reserved_upper_bound(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    reserved_cost = Decimal("0.010000")
    context = _prepare_context(
        database_runtime,
        key="budget-estimated-settlement",
        estimated_cost=reserved_cost,
    )
    accounts = _create_accounts(database_runtime, context=context)
    _reserve(database_runtime, context=context, estimated_cost=reserved_cost)
    transport = FakeProviderTransport(
        [
            ProviderTransportResponse(
                status_code=200,
                body={"items": []},
                billing=ProviderBillingV1(
                    status="estimated",
                    currency="USD",
                    unit="request",
                    unit_price_snapshot=reserved_cost,
                    estimated_cost=reserved_cost,
                    actual_cost=Decimal("0"),
                ),
            )
        ]
    )

    outcome = ProviderDispatchService(
        persistence=PostgresProviderDispatchPersistence(database_runtime.new_session),
        client=ProviderClient(transport=transport),
        raw_artifacts=_raw_service(database_runtime, tmp_path),
    ).dispatch(
        attempt_id=context.attempt_id,
        fence=context.fence,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )

    assert outcome.attempt.dispatch_status == "completed"
    assert outcome.attempt.billing.status == "estimated"
    assert outcome.attempt.billing.actual_cost == 0
    with database_runtime.engine.connect() as connection:
        persisted_actual_cost = connection.scalar(
            select(provider_request_attempts_table.c.actual_cost).where(
                provider_request_attempts_table.c.id == context.attempt_id
            )
        )
    assert persisted_actual_cost == 0

    session = database_runtime.new_session()
    try:
        with session.begin():
            service = ProviderBudgetService(PostgresProviderBudgetRepository(session))
            audits = [service.audit_account(account.id) for account in accounts]
        for audit in audits:
            assert audit.reserved_amount == 0
            assert audit.unknown_amount == 0
            if audit.dimension == "request_count":
                assert audit.settled_amount == 1
            else:
                assert audit.settled_amount == reserved_cost
    finally:
        session.close()
