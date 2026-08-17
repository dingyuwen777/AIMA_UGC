from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.collection.execution import CollectionExecutionService
from aima_ugc.modules.collection.planning import (
    CollectionPlanDefinition,
    CollectionPlanningService,
    PlanPlatformDefinition,
)
from aima_ugc.modules.collection.tables import (
    collection_plan_keyword_packs_table,
    collection_plan_platforms_table,
    collection_plans_table,
    collection_runs_table,
    collection_schedule_occurrences_table,
    collection_scopes_table,
)
from aima_ugc.modules.system.tables import keyword_packs_table, provider_configs_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from sqlalchemy import delete, insert
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())

    def cleanup() -> None:
        with runtime.engine.begin() as connection:
            connection.execute(delete(collection_scopes_table))
            connection.execute(delete(collection_runs_table))
            connection.execute(delete(collection_schedule_occurrences_table))
            connection.execute(delete(collection_plan_keyword_packs_table))
            connection.execute(delete(collection_plan_platforms_table))
            connection.execute(delete(collection_plans_table))
            connection.execute(delete(job_attempt_events_table))
            connection.execute(delete(jobs_table))
            connection.execute(delete(keyword_packs_table))
            connection.execute(delete(provider_configs_table))

    cleanup()
    try:
        yield runtime
    finally:
        cleanup()
        runtime.dispose()


def _seed_dependencies(database_runtime: DatabaseRuntime):
    provider_config_id = uuid4()
    keyword_pack_id = uuid4()
    now = datetime.now(UTC)
    with database_runtime.engine.begin() as connection:
        connection.execute(
            insert(provider_configs_table).values(
                id=provider_config_id,
                provider="tikhub",
                display_name="TikHub 主账号",
                base_url="https://api.tikhub.io",
                secret_ref="providers/tikhub/main",
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(keyword_packs_table).values(
                id=keyword_pack_id,
                name=f"爱玛-{keyword_pack_id}",
                description="",
                enabled=True,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
    return provider_config_id, keyword_pack_id


def _plan_definition(provider_config_id, keyword_pack_id) -> CollectionPlanDefinition:
    return CollectionPlanDefinition(
        name=f"计划-{uuid4()}",
        enabled=True,
        schedule_expr="0 */6 * * *",
        timezone="Asia/Shanghai",
        schedule_version=1,
        misfire_policy="latest_only",
        max_catch_up_runs=0,
        detail_policy="on_change",
        comment_policy="adaptive",
        created_by=None,
        platforms=(
            PlanPlatformDefinition(
                platform="xhs",
                provider_config_id=provider_config_id,
                config={"sort_mode": "latest"},
            ),
        ),
        keyword_pack_ids=(keyword_pack_id,),
    )


def _enqueue_job(repository: PostgresJobRepository, *, key: str):
    return repository.enqueue(
        job_type="collection.run.v1",
        payload_version="collection.run.v1",
        payload={"schema_version": "collection.run.v1"},
        internal_idempotency_key=key,
        request_id=None,
        priority=10,
        max_attempts=2,
        timeout_seconds=300,
    )


def test_repository_persists_plan_platform_and_keyword_pack_relations(
    database_runtime: DatabaseRuntime,
) -> None:
    provider_config_id, keyword_pack_id = _seed_dependencies(database_runtime)
    session = database_runtime.new_session()
    repository = PostgresCollectionPlanningRepository(session)
    service = CollectionPlanningService(repository)
    try:
        with session.begin():
            created = service.create_plan(_plan_definition(provider_config_id, keyword_pack_id))

        with session.begin():
            stored = repository.get_plan(created.id)

        assert stored == created
        assert stored is not None
        assert stored.timezone == "Asia/Shanghai"
        assert stored.schedule_version == 1
        assert stored.misfire_policy == "latest_only"
        assert stored.max_catch_up_runs == 0
        assert stored.platforms[0].platform == "xhs"
        assert stored.platforms[0].provider_config_id == provider_config_id
        assert stored.platforms[0].config == {"sort_mode": "latest"}
        assert stored.keyword_pack_ids == (keyword_pack_id,)
    finally:
        session.close()


def test_database_rejects_unapproved_scheduler_policy(database_runtime: DatabaseRuntime) -> None:
    provider_config_id, keyword_pack_id = _seed_dependencies(database_runtime)
    session = database_runtime.new_session()
    repository = PostgresCollectionPlanningRepository(session)
    try:
        invalid_policy = _plan_definition(provider_config_id, keyword_pack_id)
        invalid_policy = CollectionPlanDefinition(
            name=invalid_policy.name,
            enabled=invalid_policy.enabled,
            schedule_expr=invalid_policy.schedule_expr,
            timezone=invalid_policy.timezone,
            schedule_version=invalid_policy.schedule_version,
            misfire_policy="bounded_catch_up",
            max_catch_up_runs=0,
            detail_policy=invalid_policy.detail_policy,
            comment_policy=invalid_policy.comment_policy,
            created_by=invalid_policy.created_by,
            platforms=invalid_policy.platforms,
            keyword_pack_ids=invalid_policy.keyword_pack_ids,
        )
        with pytest.raises(IntegrityError), session.begin():
            repository.create_plan(invalid_policy)
    finally:
        session.close()


def test_scheduled_occurrence_and_run_share_one_job_and_plan_snapshot(
    database_runtime: DatabaseRuntime,
) -> None:
    provider_config_id, keyword_pack_id = _seed_dependencies(database_runtime)
    session = database_runtime.new_session()
    planning_repository = PostgresCollectionPlanningRepository(session)
    collection_repository = PostgresCollectionRepository(session)
    planning_service = CollectionPlanningService(planning_repository)
    execution_service = CollectionExecutionService(collection_repository)
    job_repository = PostgresJobRepository(session)
    scheduled_for = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
    try:
        with session.begin():
            plan = planning_service.create_plan(
                _plan_definition(provider_config_id, keyword_pack_id)
            )
            job = _enqueue_job(job_repository, key=f"scheduled-{uuid4()}")
            occurrence = planning_service.record_enqueued_occurrence(
                plan_id=plan.id,
                schedule_version=plan.schedule_version,
                scheduled_for=scheduled_for,
                job_id=job.id,
            )
            execution = execution_service.create_run(
                job_id=job.id,
                trigger_type="scheduled",
                config_snapshot={
                    "schema_version": "collection-run-config.v1",
                    "plan_id": str(plan.id),
                    "schedule_version": plan.schedule_version,
                },
                scopes=(),
                occurrence_id=occurrence.id,
            )

        assert occurrence.job_id == job.id
        assert occurrence.status == "enqueued"
        assert execution.run.occurrence_id == occurrence.id
        assert execution.run.manual_plan_id is None
        assert execution.run.trigger_type == "scheduled"
    finally:
        session.close()


def test_manual_run_can_reference_plan_without_occurrence(
    database_runtime: DatabaseRuntime,
) -> None:
    provider_config_id, keyword_pack_id = _seed_dependencies(database_runtime)
    session = database_runtime.new_session()
    planning_service = CollectionPlanningService(PostgresCollectionPlanningRepository(session))
    execution_service = CollectionExecutionService(PostgresCollectionRepository(session))
    job_repository = PostgresJobRepository(session)
    try:
        with session.begin():
            plan = planning_service.create_plan(
                _plan_definition(provider_config_id, keyword_pack_id)
            )
            job = _enqueue_job(job_repository, key=f"manual-{uuid4()}")
            execution = execution_service.create_run(
                job_id=job.id,
                trigger_type="manual",
                config_snapshot={"schema_version": "collection-run-config.v1"},
                scopes=(),
                manual_plan_id=plan.id,
            )

        assert execution.run.manual_plan_id == plan.id
        assert execution.run.occurrence_id is None
    finally:
        session.close()


def test_deferred_constraint_rejects_enqueued_occurrence_without_run(
    database_runtime: DatabaseRuntime,
) -> None:
    provider_config_id, keyword_pack_id = _seed_dependencies(database_runtime)
    session = database_runtime.new_session()
    planning_service = CollectionPlanningService(PostgresCollectionPlanningRepository(session))
    job_repository = PostgresJobRepository(session)
    try:
        with pytest.raises(IntegrityError), session.begin():
            plan = planning_service.create_plan(
                _plan_definition(provider_config_id, keyword_pack_id)
            )
            job = _enqueue_job(job_repository, key=f"orphan-{uuid4()}")
            planning_service.record_enqueued_occurrence(
                plan_id=plan.id,
                schedule_version=plan.schedule_version,
                scheduled_for=datetime(2026, 8, 16, 6, 0, tzinfo=UTC),
                job_id=job.id,
            )
    finally:
        session.close()


def test_deferred_constraint_rejects_occurrence_and_run_job_mismatch(
    database_runtime: DatabaseRuntime,
) -> None:
    provider_config_id, keyword_pack_id = _seed_dependencies(database_runtime)
    session = database_runtime.new_session()
    planning_service = CollectionPlanningService(PostgresCollectionPlanningRepository(session))
    execution_service = CollectionExecutionService(PostgresCollectionRepository(session))
    job_repository = PostgresJobRepository(session)
    try:
        with pytest.raises(IntegrityError), session.begin():
            plan = planning_service.create_plan(
                _plan_definition(provider_config_id, keyword_pack_id)
            )
            occurrence_job = _enqueue_job(job_repository, key=f"occurrence-{uuid4()}")
            run_job = _enqueue_job(job_repository, key=f"run-{uuid4()}")
            occurrence = planning_service.record_enqueued_occurrence(
                plan_id=plan.id,
                schedule_version=plan.schedule_version,
                scheduled_for=datetime(2026, 8, 16, 9, 0, tzinfo=UTC),
                job_id=occurrence_job.id,
            )
            execution_service.create_run(
                job_id=run_job.id,
                trigger_type="scheduled",
                config_snapshot={"schema_version": "collection-run-config.v1"},
                scopes=(),
                occurrence_id=occurrence.id,
            )
    finally:
        session.close()


def test_deferred_constraint_rejects_run_for_skipped_occurrence(
    database_runtime: DatabaseRuntime,
) -> None:
    provider_config_id, keyword_pack_id = _seed_dependencies(database_runtime)
    session = database_runtime.new_session()
    planning_service = CollectionPlanningService(PostgresCollectionPlanningRepository(session))
    execution_service = CollectionExecutionService(PostgresCollectionRepository(session))
    job_repository = PostgresJobRepository(session)
    try:
        with pytest.raises(IntegrityError), session.begin():
            plan = planning_service.create_plan(
                _plan_definition(provider_config_id, keyword_pack_id)
            )
            job = _enqueue_job(job_repository, key=f"skipped-run-{uuid4()}")
            occurrence = planning_service.record_skipped_occurrence(
                plan_id=plan.id,
                schedule_version=plan.schedule_version,
                scheduled_for=datetime(2026, 8, 16, 10, 0, tzinfo=UTC),
                skip_reason="explicit-test-skip",
            )
            execution_service.create_run(
                job_id=job.id,
                trigger_type="scheduled",
                config_snapshot={"schema_version": "collection-run-config.v1"},
                scopes=(),
                occurrence_id=occurrence.id,
            )
    finally:
        session.close()


def test_skipped_occurrence_commits_without_job_or_run(database_runtime: DatabaseRuntime) -> None:
    provider_config_id, keyword_pack_id = _seed_dependencies(database_runtime)
    session = database_runtime.new_session()
    planning_service = CollectionPlanningService(PostgresCollectionPlanningRepository(session))
    try:
        with session.begin():
            plan = planning_service.create_plan(
                _plan_definition(provider_config_id, keyword_pack_id)
            )
            occurrence = planning_service.record_skipped_occurrence(
                plan_id=plan.id,
                schedule_version=plan.schedule_version,
                scheduled_for=datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
                skip_reason="explicit-test-skip",
            )

        assert occurrence.status == "skipped"
        assert occurrence.job_id is None
        assert occurrence.skip_reason == "explicit-test-skip"
    finally:
        session.close()
