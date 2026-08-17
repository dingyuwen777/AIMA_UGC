"""Collection Run PostgreSQL 预算准备集成测试。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_run_preparation import (
    PostgresCollectionRunPreparer,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.provider_budget import (
    PostgresProviderBudgetRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.registry import build_default_provider_registry
from aima_ugc.modules.collection.execution import (
    CollectionExecution,
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.provider_budget import (
    ProviderBudgetAccountSpec,
    ProviderBudgetService,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_budget_accounts_table,
    provider_budget_reservations_table,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.modules.system.tables import provider_configs_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table


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


def _clear_data(connection: Connection) -> None:
    connection.execute(delete(provider_budget_reservations_table))
    connection.execute(delete(provider_budget_accounts_table))
    connection.execute(delete(collection_scopes_table))
    connection.execute(delete(collection_runs_table))
    connection.execute(delete(job_attempt_events_table))
    connection.execute(delete(jobs_table))
    connection.execute(delete(provider_configs_table))


def _create_global_budget_accounts(
    session: Session,
    *,
    provider_config_id: UUID,
    period_start: datetime,
    period_end: datetime,
) -> None:
    service = ProviderBudgetService(PostgresProviderBudgetRepository(session))
    service.create_account(
        ProviderBudgetAccountSpec(
            id=uuid4(),
            provider_config_id=provider_config_id,
            scope_type="global",
            run_id=None,
            content_id=None,
            period_start=period_start,
            period_end=period_end,
            dimension="request_count",
            unit="request",
            limit_amount=Decimal("100"),
        )
    )
    service.create_account(
        ProviderBudgetAccountSpec(
            id=uuid4(),
            provider_config_id=provider_config_id,
            scope_type="global",
            run_id=None,
            content_id=None,
            period_start=period_start,
            period_end=period_end,
            dimension="monetary_cost",
            unit="USD",
            limit_amount=Decimal("100"),
        )
    )


def _prepare_execution(
    runtime: DatabaseRuntime,
) -> tuple[CollectionExecution, JobExecutionFence, UUID, UUID]:
    session = runtime.new_session()
    now = datetime.now(UTC)
    xhs_config_id = uuid4()
    douyin_config_id = uuid4()
    try:
        with session.begin():
            configs = PostgresProviderConfigRepository(session)
            for config_id, name in (
                (xhs_config_id, "TikHub XHS"),
                (douyin_config_id, "TikHub Douyin"),
            ):
                configs.create(
                    ProviderConfig(
                        id=config_id,
                        provider="tikhub",
                        display_name=name,
                        base_url="https://api.tikhub.io",
                        secret_ref=f"providers/tikhub/{config_id}",
                        enabled=True,
                    )
                )
                _create_global_budget_accounts(
                    session,
                    provider_config_id=config_id,
                    period_start=now - timedelta(hours=1),
                    period_end=now + timedelta(hours=1),
                )

            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"run-preparer-{uuid4().hex}",
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            execution = CollectionExecutionService(PostgresCollectionRepository(session)).create_run(
                job_id=job.id,
                trigger_type="api",
                config_snapshot={
                    "schema_version": "collection-run-config.v1",
                    "request_budget": 6,
                    "platforms": [
                        {
                            "platform": "xhs",
                            "provider_config_id": str(xhs_config_id),
                            "config": {},
                        },
                        {
                            "platform": "douyin",
                            "provider_config_id": str(douyin_config_id),
                            "config": {},
                        },
                    ],
                },
                scopes=(
                    CollectionScopeDefinition(
                        platform="xhs",
                        source_type="keyword_search",
                        source_value="爱玛",
                        operation_group="content_discovery",
                    ),
                    CollectionScopeDefinition(
                        platform="xhs",
                        source_type="keyword_search",
                        source_value="电动车",
                        operation_group="content_discovery",
                    ),
                    CollectionScopeDefinition(
                        platform="douyin",
                        source_type="keyword_search",
                        source_value="爱玛",
                        operation_group="content_discovery",
                    ),
                ),
            )
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="run-preparer-test",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
        return (
            execution,
            JobExecutionFence(job_id=claimed.id, lease_token=claimed.lease_token),
            xhs_config_id,
            douyin_config_id,
        )
    finally:
        session.close()


def _preparer(runtime: DatabaseRuntime) -> PostgresCollectionRunPreparer:
    return PostgresCollectionRunPreparer(
        session_factory=runtime.new_session,
        provider_registry=build_default_provider_registry(),
        max_verified_unit_price=Decimal("0.010000"),
    )


def test_preparer_allocates_total_run_budget_by_provider_scope_weight(
    database_runtime: DatabaseRuntime,
) -> None:
    execution, fence, xhs_config_id, douyin_config_id = _prepare_execution(database_runtime)

    _preparer(database_runtime).prepare(execution=execution, fence=fence)
    _preparer(database_runtime).prepare(execution=execution, fence=fence)

    session = database_runtime.new_session()
    try:
        with session.begin():
            rows = (
                session.execute(
                    select(provider_budget_accounts_table).where(
                        provider_budget_accounts_table.c.scope_type.in_(("run", "run_comments"))
                    )
                )
                .mappings()
                .all()
            )
        by_key = {
            (row["provider_config_id"], row["scope_type"], row["dimension"]): row
            for row in rows
        }
        assert len(rows) == 8
        for scope_type in ("run", "run_comments"):
            assert by_key[(xhs_config_id, scope_type, "request_count")][
                "limit_amount"
            ] == Decimal("4")
            assert by_key[(douyin_config_id, scope_type, "request_count")][
                "limit_amount"
            ] == Decimal("2")
            assert by_key[(xhs_config_id, scope_type, "monetary_cost")][
                "limit_amount"
            ] == Decimal("0.040000")
            assert by_key[(douyin_config_id, scope_type, "monetary_cost")][
                "limit_amount"
            ] == Decimal("0.020000")
    finally:
        session.close()


def test_preparer_rejects_stale_fence_before_budget_write(
    database_runtime: DatabaseRuntime,
) -> None:
    execution, fence, _, _ = _prepare_execution(database_runtime)
    stale = JobExecutionFence(job_id=fence.job_id, lease_token="stale-token")

    with pytest.raises(LeaseLostError):
        _preparer(database_runtime).prepare(execution=execution, fence=stale)

    session = database_runtime.new_session()
    try:
        with session.begin():
            account_id = session.scalar(
                select(provider_budget_accounts_table.c.id)
                .where(provider_budget_accounts_table.c.scope_type == "run")
                .limit(1)
            )
        assert account_id is None
    finally:
        session.close()
