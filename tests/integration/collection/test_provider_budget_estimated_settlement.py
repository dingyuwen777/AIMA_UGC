"""TikHub-style estimated Billing 的 PostgreSQL 预算结算回归。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
)
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.provider import PostgresProviderRepository
from aima_ugc.adapters.persistence.postgres.provider_budget import (
    PostgresProviderBudgetRepository,
)
from aima_ugc.adapters.persistence.postgres.provider_dispatch import (
    PostgresProviderDispatchPersistence,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.contracts.provider import ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.provider_budget import (
    ProviderBudgetAccountSpec,
    ProviderBudgetService,
)
from aima_ugc.modules.collection.provider_dispatch import ProviderDispatchService
from aima_ugc.modules.collection.provider_persistence import ProviderPersistenceService
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransportRequest,
    ProviderTransportResponse,
    RawArtifactService,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_budget_accounts_table,
    provider_budget_reservations_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.modules.system.tables import provider_configs_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from aima_ugc.platform.storage import ArtifactService
from aima_ugc.platform.storage.tables import artifacts_table
from sqlalchemy import delete, select


@dataclass(frozen=True, slots=True)
class _BudgetContext:
    provider_config_id: UUID
    run_id: UUID
    request: ProviderRequestV1
    attempt_id: UUID
    fence: JobExecutionFence


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


def _clear_data(connection) -> None:
    connection.execute(delete(provider_budget_reservations_table))
    connection.execute(delete(provider_budget_accounts_table))
    connection.execute(delete(provider_request_attempts_table))
    connection.execute(delete(provider_requests_table))
    connection.execute(delete(collection_scopes_table))
    connection.execute(delete(collection_runs_table))
    connection.execute(delete(job_attempt_events_table))
    connection.execute(delete(jobs_table))
    connection.execute(delete(contents_table))
    connection.execute(delete(artifacts_table))
    connection.execute(delete(provider_configs_table))


def _estimated_billing(amount: Decimal) -> ProviderBillingV1:
    return ProviderBillingV1(
        status="estimated",
        currency="USD",
        unit="request",
        unit_price_snapshot=amount,
        estimated_cost=amount,
        actual_cost=Decimal("0"),
    )


def _prepare_context(
    runtime: DatabaseRuntime,
    *,
    key: str,
    estimated_cost: Decimal,
) -> _BudgetContext:
    session = runtime.new_session()
    try:
        with session.begin():
            provider_config_id = uuid4()
            PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=provider_config_id,
                    provider="fake_provider",
                    display_name="Stage 7 Budget Estimated Fake",
                    base_url="https://provider.invalid",
                    secret_ref="providers/fake/budget-estimated-test",
                    enabled=True,
                )
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=key,
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            execution = CollectionExecutionService(
                PostgresCollectionRepository(session)
            ).create_run(
                job_id=job.id,
                trigger_type="manual",
                config_snapshot={},
                scopes=(
                    CollectionScopeDefinition(
                        platform="xhs",
                        source_type="keyword_search",
                        source_value="爱玛",
                        operation_group="content_discovery",
                    ),
                ),
            )
            request = ProviderRequestV1.create(
                request_id=uuid4(),
                run_id=execution.run.id,
                scope_id=execution.scopes[0].id,
                provider="fake_provider",
                platform="xhs",
                operation="keyword_search",
                request_params={"keyword": "爱玛"},
            )
            attempt_id = uuid4()
            ProviderPersistenceService(
                PostgresProviderRepository(session)
            ).prepare_billable_attempt(
                request=request,
                provider_config_id=provider_config_id,
                attempt_id=attempt_id,
                billing=_estimated_billing(estimated_cost),
            )
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="stage7-budget-estimated-worker",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
        return _BudgetContext(
            provider_config_id=provider_config_id,
            run_id=execution.run.id,
            request=request,
            attempt_id=attempt_id,
            fence=JobExecutionFence(job_id=claimed.id, lease_token=claimed.lease_token),
        )
    finally:
        session.close()


def _create_accounts(
    runtime: DatabaseRuntime,
    *,
    context: _BudgetContext,
):
    now = datetime.now(UTC)
    session = runtime.new_session()
    try:
        service = ProviderBudgetService(PostgresProviderBudgetRepository(session))
        with session.begin():
            accounts = []
            for scope_type in ("global", "run"):
                run_id = context.run_id if scope_type == "run" else None
                accounts.append(
                    service.create_account(
                        ProviderBudgetAccountSpec(
                            id=uuid4(),
                            provider_config_id=context.provider_config_id,
                            scope_type=scope_type,
                            run_id=run_id,
                            content_id=None,
                            period_start=now - timedelta(hours=1),
                            period_end=now + timedelta(hours=1),
                            dimension="request_count",
                            unit="request",
                            limit_amount=Decimal("10"),
                        )
                    )
                )
                accounts.append(
                    service.create_account(
                        ProviderBudgetAccountSpec(
                            id=uuid4(),
                            provider_config_id=context.provider_config_id,
                            scope_type=scope_type,
                            run_id=run_id,
                            content_id=None,
                            period_start=now - timedelta(hours=1),
                            period_end=now + timedelta(hours=1),
                            dimension="monetary_cost",
                            unit="USD",
                            limit_amount=Decimal("10"),
                        )
                    )
                )
        return accounts
    finally:
        session.close()


def _reserve(
    runtime: DatabaseRuntime,
    *,
    context: _BudgetContext,
    estimated_cost: Decimal,
) -> None:
    session = runtime.new_session()
    try:
        with session.begin():
            ProviderBudgetService(PostgresProviderBudgetRepository(session)).reserve_attempt(
                provider_config_id=context.provider_config_id,
                provider_request_id=context.request.request_id,
                provider_request_attempt_id=context.attempt_id,
                run_id=context.run_id,
                content_id=None,
                estimated_cost=estimated_cost,
                currency="USD",
                reserved_at=datetime.now(UTC),
            )
    finally:
        session.close()


def _raw_service(runtime: DatabaseRuntime, artifact_root: Path) -> RawArtifactService:
    store = LocalArtifactStore(artifact_root)
    return RawArtifactService(
        artifacts=ArtifactService(
            metadata=PostgresArtifactMetadataGateway(runtime.new_session),
            store=store,
        ),
        store=store,
    )


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
                billing=_estimated_billing(reserved_cost),
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
    assert outcome.attempt.billing_status == "estimated"
    assert outcome.attempt.actual_cost == 0
    assert outcome.attempt.estimated_cost == reserved_cost
    assert outcome.attempt.unit_price_snapshot == reserved_cost
    assert outcome.attempt.cost_currency == "USD"
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
