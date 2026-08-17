"""Collection live runtime 的 Fenced Provider Request/Attempt 准备集成测试。"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_provider_execution import (
    PostgresFencedProviderAttemptPreparer,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.contracts.provider import ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from sqlalchemy import func, select


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, accounts RESTART IDENTITY CASCADE"
        )
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, accounts RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def _provider_config(runtime: DatabaseRuntime) -> ProviderConfig:
    session = runtime.new_session()
    try:
        with session.begin():
            return PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name=f"TikHub Runtime {uuid4()}",
                    base_url="https://api.tikhub.io",
                    secret_ref=f"providers/tikhub/runtime/{uuid4()}",
                    enabled=True,
                )
            )
    finally:
        session.close()


def _claimed_scope(
    runtime: DatabaseRuntime,
    *,
    source_value: str,
) -> tuple[UUID, UUID, JobExecutionFence]:
    session = runtime.new_session()
    try:
        with session.begin():
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"provider-runtime:{uuid4().hex}",
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            execution = CollectionExecutionService(
                PostgresCollectionRepository(session)
            ).create_run(
                job_id=job.id,
                trigger_type="api",
                config_snapshot={"schema_version": "collection-run-config.v1"},
                scopes=(
                    CollectionScopeDefinition(
                        platform="xhs",
                        source_type="keyword_search",
                        source_value=source_value,
                        operation_group="content_discovery",
                    ),
                ),
            )
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id=f"provider-runtime-{job.id}",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.id == job.id and claimed.lease_token is not None
        return (
            execution.run.id,
            execution.scopes[0].id,
            JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token),
        )
    finally:
        session.close()


def _request(*, run_id: UUID, scope_id: UUID, keyword: str) -> ProviderRequestV1:
    return ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=run_id,
        scope_id=scope_id,
        provider="tikhub",
        platform="xhs",
        operation="search_notes",
        request_params={"keyword": keyword, "sort_type": "time_descending"},
        pagination_input={},
    )


def _billing() -> ProviderBillingV1:
    return ProviderBillingV1(
        status="estimated",
        currency="USD",
        unit="request",
        unit_price_snapshot=Decimal("0.001"),
        estimated_cost=Decimal("0.001"),
        actual_cost=Decimal("0"),
    )


def _counts(runtime: DatabaseRuntime) -> tuple[int, int]:
    session = runtime.new_session()
    try:
        with session.begin():
            requests = session.scalar(select(func.count()).select_from(provider_requests_table))
            attempts = session.scalar(
                select(func.count()).select_from(provider_request_attempts_table)
            )
        assert requests is not None and attempts is not None
        return requests, attempts
    finally:
        session.close()


def test_current_fence_prepares_billable_request_and_attempt(
    database_runtime: DatabaseRuntime,
) -> None:
    config = _provider_config(database_runtime)
    run_id, scope_id, fence = _claimed_scope(database_runtime, source_value="爱玛")
    request = _request(run_id=run_id, scope_id=scope_id, keyword="爱玛")

    prepared = PostgresFencedProviderAttemptPreparer(
        database_runtime.new_session
    ).prepare_billable_attempt(
        request=request,
        provider_config_id=config.id,
        attempt_id=uuid4(),
        billing=_billing(),
        fence=fence,
    )

    assert prepared.request.id == request.request_id
    assert prepared.request.provider_config_id == config.id
    assert prepared.attempt.provider_request_id == request.request_id
    assert prepared.attempt.dispatch_status == "reserved"
    assert prepared.attempt.billing_status == "estimated"
    assert _counts(database_runtime) == (1, 1)


def test_stale_fence_cannot_prepare_provider_request_or_attempt(
    database_runtime: DatabaseRuntime,
) -> None:
    config = _provider_config(database_runtime)
    run_id, scope_id, fence = _claimed_scope(database_runtime, source_value="爱玛")
    stale = JobExecutionFence(job_id=fence.job_id, lease_token="stale-token")

    with pytest.raises(LeaseLostError):
        PostgresFencedProviderAttemptPreparer(
            database_runtime.new_session
        ).prepare_billable_attempt(
            request=_request(run_id=run_id, scope_id=scope_id, keyword="爱玛"),
            provider_config_id=config.id,
            attempt_id=uuid4(),
            billing=_billing(),
            fence=stale,
        )

    assert _counts(database_runtime) == (0, 0)


def test_valid_fence_cannot_prepare_request_for_another_jobs_scope(
    database_runtime: DatabaseRuntime,
) -> None:
    config = _provider_config(database_runtime)
    _first_run_id, _first_scope_id, first_fence = _claimed_scope(
        database_runtime,
        source_value="爱玛",
    )
    second_run_id, second_scope_id, _second_fence = _claimed_scope(
        database_runtime,
        source_value="电动车",
    )

    with pytest.raises(LeaseLostError):
        PostgresFencedProviderAttemptPreparer(
            database_runtime.new_session
        ).prepare_billable_attempt(
            request=_request(
                run_id=second_run_id,
                scope_id=second_scope_id,
                keyword="电动车",
            ),
            provider_config_id=config.id,
            attempt_id=uuid4(),
            billing=_billing(),
            fence=first_fence,
        )

    assert _counts(database_runtime) == (0, 0)


def test_resolve_or_prepare_reuses_existing_reserved_attempt(
    database_runtime: DatabaseRuntime,
) -> None:
    config = _provider_config(database_runtime)
    run_id, scope_id, fence = _claimed_scope(database_runtime, source_value="爱玛")
    preparer = PostgresFencedProviderAttemptPreparer(database_runtime.new_session)
    first_request = _request(run_id=run_id, scope_id=scope_id, keyword="爱玛")
    first_attempt_id = uuid4()
    first = preparer.prepare_billable_attempt(
        request=first_request,
        provider_config_id=config.id,
        attempt_id=first_attempt_id,
        billing=_billing(),
        fence=fence,
    )

    resumed = preparer.resolve_or_prepare_billable_attempt(
        request=_request(run_id=run_id, scope_id=scope_id, keyword="爱玛"),
        provider_config_id=config.id,
        attempt_id=uuid4(),
        billing=_billing(),
        fence=fence,
    )

    assert resumed.request.id == first.request.id
    assert resumed.attempt.id == first_attempt_id
    assert resumed.attempt.dispatch_status == "reserved"
    assert _counts(database_runtime) == (1, 1)
