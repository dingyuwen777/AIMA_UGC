"""Stage 8A Provider Request 来源不可变性 PostgreSQL 18 回归测试。"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.provider import PostgresProviderRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.contracts.provider import ProviderRequestV1
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.provider_persistence import ProviderPersistenceService
from aima_ugc.modules.collection.tables import provider_requests_table
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql("TRUNCATE TABLE provider_configs, jobs RESTART IDENTITY CASCADE")
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE provider_configs, jobs RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def _provider_config(*, suffix: str) -> ProviderConfig:
    return ProviderConfig(
        id=uuid4(),
        provider="tikhub",
        display_name=f"Stage 8A Lineage {suffix}",
        base_url="https://api.tikhub.dev",
        secret_ref=f"providers/tikhub/stage8a-lineage/{suffix}",
        enabled=True,
    )


def test_stage8a_keeps_provider_config_immutable_after_attempt(
    database_runtime: DatabaseRuntime,
) -> None:
    first_config = _provider_config(suffix="first")
    second_config = _provider_config(suffix="second")
    session = database_runtime.new_session()
    try:
        with session.begin():
            config_repository = PostgresProviderConfigRepository(session)
            config_repository.create(first_config)
            config_repository.create(second_config)

            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"stage8a-lineage-{uuid4().hex}",
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
            scope = execution.scopes[0]
            request = ProviderRequestV1.create(
                request_id=uuid4(),
                run_id=execution.run.id,
                scope_id=scope.id,
                provider="tikhub",
                platform="xhs",
                operation="search_notes",
                request_params={"keyword": "爱玛"},
                pagination_input={"page": 1},
            )
            stored = ProviderPersistenceService(PostgresProviderRepository(session)).ensure_request(
                request,
                provider_config_id=first_config.id,
            )
            PostgresProviderRepository(session).create_or_get_non_billable_attempt(
                provider_request_id=stored.id,
                attempt_id=uuid4(),
            )

        with pytest.raises(IntegrityError), session.begin():
            session.execute(
                update(provider_requests_table)
                .where(provider_requests_table.c.id == stored.id)
                .values(provider_config_id=second_config.id)
            )
    finally:
        session.close()
