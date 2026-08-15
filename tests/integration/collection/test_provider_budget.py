"""Stage 7 Provider Budget Ledger 的 PostgreSQL 并发与 Dispatch 门禁验证。"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, insert, select, update

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
    ProviderBudgetDriftError,
    ProviderBudgetExceededError,
    ProviderBudgetReservationMissingError,
    ProviderBudgetService,
)
from aima_ugc.modules.collection.provider_dispatch import ProviderDispatchService
from aima_ugc.modules.collection.provider_persistence import ProviderPersistenceService
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransportFailure,
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


@dataclass(frozen=True, slots=True)
class BudgetContext:
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


def _estimated_billing(amount: Decimal = Decimal("0.010000")) -> ProviderBillingV1:
    return ProviderBillingV1(
        status="estimated",
        currency="USD",
        unit="request",
        unit_price_snapshot=amount,
        estimated_cost=amount,
    )


def _prepare_context(
    runtime: DatabaseRuntime,
    *,
    key: str,
    estimated_cost: Decimal = Decimal("0.010000"),
) -> BudgetContext:
    session = runtime.new_session()
    try:
        with session.begin():
            provider_config_id = uuid4()
            PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=provider_config_id,
                    provider="fake_provider",
                    display_name="Stage 7 Budget Fake",
                    base_url="https://provider.invalid",
                    secret_ref="providers/fake/budget-test",
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
            prepared = ProviderPersistenceService(
                PostgresProviderRepository(session)
            ).prepare_billable_attempt(
                request=request,
                provider_config_id=provider_config_id,
                attempt_id=attempt_id,
                billing=_estimated_billing(estimated_cost),
            )
            assert prepared.request.provider_config_id == provider_config_id
            assert prepared.attempt.billing_status == "estimated"
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="stage7-budget-worker",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
        return BudgetContext(
            provider_config_id=provider_config_id,
            run_id=execution.run.id,
            request=request,
            attempt_id=attempt_id,
            fence=JobExecutionFence(job_id=claimed.id, lease_token=claimed.lease_token),
        )
    finally:
        session.close()


def _create_content(runtime: DatabaseRuntime) -> UUID:
    content_id = uuid4()
    now = datetime.now(UTC)
    with runtime.engine.begin() as connection:
        connection.execute(
            insert(contents_table).values(
                id=content_id,
                platform="xhs",
                external_content_id=f"budget-{content_id.hex}",
                content_type="note",
                first_seen_at=now,
                last_seen_at=now,
                current_version=1,
                updated_at=now,
            )
        )
    return content_id


def _create_accounts(
    runtime: DatabaseRuntime,
    *,
    context: BudgetContext,
    content_id: UUID | None = None,
    request_limit: Decimal = Decimal("10"),
    monetary_limit: Decimal = Decimal("10"),
):
    now = datetime.now(UTC)
    scope_types = ["global", "run"]
    if content_id is not None:
        scope_types.extend(["run_comments", "content_comments"])
    session = runtime.new_session()
    try:
        repository = PostgresProviderBudgetRepository(session)
        service = ProviderBudgetService(repository)
        with session.begin():
            accounts = []
            for scope_type in scope_types:
                run_id = context.run_id if scope_type in {"run", "run_comments"} else None
                scoped_content_id = content_id if scope_type == "content_comments" else None
                accounts.append(
                    service.create_account(
                        ProviderBudgetAccountSpec(
                            id=uuid4(),
                            provider_config_id=context.provider_config_id,
                            scope_type=scope_type,
                            run_id=run_id,
                            content_id=scoped_content_id,
                            period_start=now - timedelta(hours=1),
                            period_end=now + timedelta(hours=1),
                            dimension="request_count",
                            unit="request",
                            limit_amount=request_limit,
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
                            content_id=scoped_content_id,
                            period_start=now - timedelta(hours=1),
                            period_end=now + timedelta(hours=1),
                            dimension="monetary_cost",
                            unit="USD",
                            limit_amount=monetary_limit,
                        )
                    )
                )
        return accounts
    finally:
        session.close()


def _reserve(
    runtime: DatabaseRuntime,
    *,
    context: BudgetContext,
    attempt_id: UUID | None = None,
    content_id: UUID | None = None,
    estimated_cost: Decimal = Decimal("0.010000"),
):
    session = runtime.new_session()
    try:
        with session.begin():
            return ProviderBudgetService(PostgresProviderBudgetRepository(session)).reserve_attempt(
                provider_config_id=context.provider_config_id,
                provider_request_id=context.request.request_id,
                provider_request_attempt_id=attempt_id or context.attempt_id,
                run_id=context.run_id,
                content_id=content_id,
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


def test_reservation_is_atomic_and_replay_is_idempotent(
    database_runtime: DatabaseRuntime,
) -> None:
    context = _prepare_context(database_runtime, key="budget-reserve-idempotent")
    accounts = _create_accounts(database_runtime, context=context)

    first = _reserve(database_runtime, context=context)
    replay = _reserve(database_runtime, context=context)

    assert len(first) == 4
    assert replay == first
    assert {(item.scope_type, item.dimension, item.status) for item in first} == {
        ("global", "request_count", "reserved"),
        ("global", "monetary_cost", "reserved"),
        ("run", "request_count", "reserved"),
        ("run", "monetary_cost", "reserved"),
    }

    session = database_runtime.new_session()
    try:
        with session.begin():
            audit = ProviderBudgetService(PostgresProviderBudgetRepository(session))
            snapshots = [audit.audit_account(account.id) for account in accounts]
        for snapshot in snapshots:
            expected = (
                Decimal("1") if snapshot.dimension == "request_count" else Decimal("0.010000")
            )
            assert snapshot.reserved_amount == expected
            assert snapshot.settled_amount == 0
            assert snapshot.unknown_amount == 0
    finally:
        session.close()


def test_comment_reservation_uses_all_four_layers(
    database_runtime: DatabaseRuntime,
) -> None:
    context = _prepare_context(database_runtime, key="budget-comment-layers")
    content_id = _create_content(database_runtime)
    _create_accounts(database_runtime, context=context, content_id=content_id)

    reservations = _reserve(database_runtime, context=context, content_id=content_id)

    assert len(reservations) == 8
    assert {item.scope_type for item in reservations} == {
        "global",
        "run",
        "run_comments",
        "content_comments",
    }


def test_missing_budget_fails_before_transport_is_called(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    context = _prepare_context(database_runtime, key="budget-dispatch-fail-closed")
    transport = FakeProviderTransport(
        [ProviderTransportResponse(status_code=200, body={"items": []})]
    )
    service = ProviderDispatchService(
        persistence=PostgresProviderDispatchPersistence(database_runtime.new_session),
        client=ProviderClient(transport=transport),
        raw_artifacts=_raw_service(database_runtime, tmp_path),
    )

    with pytest.raises(ProviderBudgetReservationMissingError):
        service.dispatch(
            attempt_id=context.attempt_id,
            fence=context.fence,
            transport_request=ProviderTransportRequest(
                transport_kind="http",
                method="GET",
                path="/fake/search",
            ),
        )

    assert transport.call_count == 0
    with database_runtime.engine.connect() as connection:
        status = connection.scalar(
            select(provider_request_attempts_table.c.dispatch_status).where(
                provider_request_attempts_table.c.id == context.attempt_id
            )
        )
    assert status == "reserved"


def test_concurrent_reservation_has_only_one_winner(
    database_runtime: DatabaseRuntime,
) -> None:
    context = _prepare_context(database_runtime, key="budget-concurrent")
    _create_accounts(
        database_runtime,
        context=context,
        request_limit=Decimal("1"),
        monetary_limit=Decimal("0.010000"),
    )
    session = database_runtime.new_session()
    try:
        with session.begin():
            second = ProviderPersistenceService(
                PostgresProviderRepository(session)
            ).prepare_billable_attempt(
                request=context.request,
                provider_config_id=context.provider_config_id,
                attempt_id=uuid4(),
                billing=_estimated_billing(),
            )
    finally:
        session.close()

    barrier = Barrier(2)

    def reserve(attempt_id: UUID) -> str:
        thread_session = database_runtime.new_session()
        try:
            barrier.wait(timeout=10)
            try:
                with thread_session.begin():
                    ProviderBudgetService(
                        PostgresProviderBudgetRepository(thread_session)
                    ).reserve_attempt(
                        provider_config_id=context.provider_config_id,
                        provider_request_id=context.request.request_id,
                        provider_request_attempt_id=attempt_id,
                        run_id=context.run_id,
                        content_id=None,
                        estimated_cost=Decimal("0.010000"),
                        currency="USD",
                        reserved_at=datetime.now(UTC),
                    )
            except ProviderBudgetExceededError:
                return "exceeded"
            return "reserved"
        finally:
            thread_session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, (context.attempt_id, second.attempt.id)))

    assert sorted(results) == ["exceeded", "reserved"]
    with database_runtime.engine.connect() as connection:
        reservation_attempts = set(
            connection.execute(
                select(provider_budget_reservations_table.c.provider_request_attempt_id)
            ).scalars()
        )
    assert len(reservation_attempts) == 1


def test_completed_dispatch_settles_actual_cost_even_when_above_reservation(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    context = _prepare_context(database_runtime, key="budget-settle-over-estimate")
    accounts = _create_accounts(
        database_runtime,
        context=context,
        request_limit=Decimal("10"),
        monetary_limit=Decimal("0.015000"),
    )
    _reserve(database_runtime, context=context)
    transport = FakeProviderTransport(
        [
            ProviderTransportResponse(
                status_code=200,
                body={"items": []},
                billing=ProviderBillingV1(
                    status="confirmed",
                    currency="USD",
                    unit="request",
                    unit_price_snapshot=Decimal("0.020000"),
                    estimated_cost=Decimal("0.010000"),
                    actual_cost=Decimal("0.020000"),
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
    assert transport.call_count == 1
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
                assert audit.settled_amount == Decimal("0.020000")
    finally:
        session.close()


def test_not_sent_releases_and_unknown_keeps_reservation_as_unknown(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    not_sent = _prepare_context(database_runtime, key="budget-not-sent")
    not_sent_accounts = _create_accounts(database_runtime, context=not_sent)
    _reserve(database_runtime, context=not_sent)
    not_sent_transport = FakeProviderTransport(
        [
            ProviderTransportFailure.not_sent(
                code="connect_failed",
                safe_summary="连接建立前失败",
            )
        ]
    )
    ProviderDispatchService(
        persistence=PostgresProviderDispatchPersistence(database_runtime.new_session),
        client=ProviderClient(transport=not_sent_transport),
        raw_artifacts=_raw_service(database_runtime, tmp_path / "not-sent"),
    ).dispatch(
        attempt_id=not_sent.attempt_id,
        fence=not_sent.fence,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )

    unknown = _prepare_context(database_runtime, key="budget-unknown")
    unknown_accounts = _create_accounts(database_runtime, context=unknown)
    _reserve(database_runtime, context=unknown)
    unknown_transport = FakeProviderTransport(
        [
            ProviderTransportFailure.unknown(
                code="socket_reset",
                safe_summary="发送后连接中断",
                currency="USD",
                unit="request",
            )
        ]
    )
    ProviderDispatchService(
        persistence=PostgresProviderDispatchPersistence(database_runtime.new_session),
        client=ProviderClient(transport=unknown_transport),
        raw_artifacts=_raw_service(database_runtime, tmp_path / "unknown"),
    ).dispatch(
        attempt_id=unknown.attempt_id,
        fence=unknown.fence,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            service = ProviderBudgetService(PostgresProviderBudgetRepository(session))
            released = [service.audit_account(account.id) for account in not_sent_accounts]
            held_unknown = [service.audit_account(account.id) for account in unknown_accounts]
        assert all(
            item.reserved_amount == item.settled_amount == item.unknown_amount == 0
            for item in released
        )
        for item in held_unknown:
            expected = Decimal("1") if item.dimension == "request_count" else Decimal("0.010000")
            assert item.reserved_amount == 0
            assert item.settled_amount == 0
            assert item.unknown_amount == expected
    finally:
        session.close()


def test_budget_audit_detects_account_aggregate_drift(
    database_runtime: DatabaseRuntime,
) -> None:
    context = _prepare_context(database_runtime, key="budget-audit-drift")
    accounts = _create_accounts(database_runtime, context=context)
    _reserve(database_runtime, context=context)
    target = next(account for account in accounts if account.dimension == "request_count")

    with database_runtime.engine.begin() as connection:
        connection.execute(
            update(provider_budget_accounts_table)
            .where(provider_budget_accounts_table.c.id == target.id)
            .values(reserved_amount=Decimal("9"))
        )

    session = database_runtime.new_session()
    try:
        with pytest.raises(ProviderBudgetDriftError), session.begin():
            ProviderBudgetService(PostgresProviderBudgetRepository(session)).audit_account(
                target.id
            )
    finally:
        session.close()
