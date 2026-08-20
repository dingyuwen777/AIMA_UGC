"""Stage 7 Scheduler Runtime PostgreSQL 集成测试。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.adapters.persistence.postgres.relevance import (
    PostgresGlobalRelevanceRepository,
)
from aima_ugc.bootstrap.scheduler import create_scheduler_runtime, run_scheduler_once
from aima_ugc.modules.collection.corrective_tables import (
    collection_plan_decision_policies_table,
)
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
from aima_ugc.modules.system.tables import (
    global_relevance_config_table,
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
    provider_configs_table,
)
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from sqlalchemy import delete, insert, select


@pytest.fixture
def scheduler_runtime():
    runtime = create_scheduler_runtime()

    def cleanup() -> None:
        with runtime.database.engine.begin() as connection:
            connection.execute(delete(collection_scopes_table))
            connection.execute(delete(collection_runs_table))
            connection.execute(delete(collection_schedule_occurrences_table))
            connection.execute(delete(collection_plan_keyword_packs_table))
            connection.execute(delete(collection_plan_platforms_table))
            connection.execute(delete(collection_plan_decision_policies_table))
            connection.execute(delete(collection_plans_table))
            connection.execute(delete(job_attempt_events_table))
            connection.execute(delete(jobs_table))
            connection.execute(delete(global_relevance_config_table))
            connection.execute(delete(keyword_pack_items_table))
            connection.execute(delete(keywords_table))
            connection.execute(delete(keyword_packs_table))
            connection.execute(delete(provider_configs_table))

    cleanup()
    try:
        yield runtime
    finally:
        cleanup()
        runtime.close()


def _create_plan(scheduler_runtime):
    session = scheduler_runtime.database.new_session()
    try:
        with session.begin():
            provider_config_id = uuid4()
            keyword_pack_id = uuid4()
            keyword_id = uuid4()
            now = datetime.now(UTC)
            session.execute(
                insert(provider_configs_table).values(
                    id=provider_config_id,
                    provider="tikhub",
                    display_name=f"scheduler-provider-{uuid4()}",
                    base_url="https://api.tikhub.io",
                    secret_ref=f"providers/tikhub/test/scheduler-{uuid4()}",
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.execute(
                insert(keyword_packs_table).values(
                    id=keyword_pack_id,
                    name=f"scheduler-pack-{uuid4()}",
                    description="scheduler runtime fixture",
                    enabled=True,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.execute(
                insert(keywords_table).values(
                    id=keyword_id,
                    text="爱玛",
                    normalized_text=f"scheduler-aima-{uuid4()}",
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.execute(
                insert(keyword_pack_items_table).values(
                    pack_id=keyword_pack_id,
                    keyword_id=keyword_id,
                    platform="xhs",
                    priority=10,
                    enabled=True,
                    note="scheduler runtime fixture",
                )
            )
            PostgresGlobalRelevanceRepository(session).set(keyword_pack_id)
            plan = CollectionPlanningService(
                PostgresCollectionPlanningRepository(session)
            ).create_plan(
                CollectionPlanDefinition(
                    name=f"scheduler-{uuid4()}",
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
                            config={},
                        ),
                    ),
                    keyword_pack_ids=(keyword_pack_id,),
                )
            )
        return plan
    finally:
        session.close()


def _force_due_cursor(scheduler_runtime, plan_id, *, scheduled_for: datetime) -> None:
    session = scheduler_runtime.database.new_session()
    try:
        with session.begin():
            repository = PostgresCollectionPlanningRepository(session)
            plan = repository.get_plan_for_update(plan_id)
            assert plan is not None
            repository.update_schedule_cursor(
                plan_id=plan.id,
                schedule_version=plan.schedule_version,
                next_run_at=scheduled_for,
                last_scheduled_at=None,
            )
    finally:
        session.close()


def test_scheduler_initializes_future_cursor_without_pre_creation_backfill(
    scheduler_runtime,
) -> None:
    plan = _create_plan(scheduler_runtime)
    now = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)

    result = run_scheduler_once(scheduler_runtime, now=now)

    session = scheduler_runtime.database.new_session()
    try:
        with session.begin():
            stored = PostgresCollectionPlanningRepository(session).get_plan(plan.id)
            occurrences = session.execute(
                select(collection_schedule_occurrences_table).where(
                    collection_schedule_occurrences_table.c.plan_id == plan.id
                )
            ).all()
        assert stored is not None
        assert stored.next_run_at == datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
        assert stored.last_scheduled_at is None
        assert occurrences == []
        assert result.initialized == 1
        assert result.enqueued == 0
    finally:
        session.close()


def test_latest_only_recovery_commits_skipped_job_occurrence_run_and_cursor_atomically(
    scheduler_runtime,
) -> None:
    plan = _create_plan(scheduler_runtime)
    _force_due_cursor(
        scheduler_runtime,
        plan.id,
        scheduled_for=datetime(2026, 8, 14, 22, 0, tzinfo=UTC),
    )
    now = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)

    first = run_scheduler_once(scheduler_runtime, now=now)
    second = run_scheduler_once(scheduler_runtime, now=now)

    session = scheduler_runtime.database.new_session()
    try:
        with session.begin():
            stored = PostgresCollectionPlanningRepository(session).get_plan(plan.id)
            occurrences = (
                session.execute(
                    select(collection_schedule_occurrences_table)
                    .where(collection_schedule_occurrences_table.c.plan_id == plan.id)
                    .order_by(collection_schedule_occurrences_table.c.scheduled_for)
                )
                .mappings()
                .all()
            )
            runs = session.execute(select(collection_runs_table)).mappings().all()
            jobs = session.execute(select(jobs_table)).mappings().all()

        assert stored is not None
        assert stored.last_scheduled_at == datetime(2026, 8, 15, 4, 0, tzinfo=UTC)
        assert stored.next_run_at == datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
        assert [
            (row["scheduled_for"], row["status"], row["skip_reason"]) for row in occurrences
        ] == [
            (
                datetime(2026, 8, 14, 22, 0, tzinfo=UTC),
                "skipped",
                "misfire_superseded",
            ),
            (datetime(2026, 8, 15, 4, 0, tzinfo=UTC), "enqueued", None),
        ]
        assert len(jobs) == 1
        assert len(runs) == 1
        assert runs[0]["job_id"] == jobs[0]["id"] == occurrences[1]["job_id"]
        assert runs[0]["occurrence_id"] == occurrences[1]["id"]
        assert first.enqueued == 1
        assert first.skipped == 1
        assert second.enqueued == 0
        assert second.skipped == 0
    finally:
        session.close()


def test_two_scheduler_ticks_do_not_duplicate_same_occurrence(scheduler_runtime) -> None:
    plan = _create_plan(scheduler_runtime)
    _force_due_cursor(
        scheduler_runtime,
        plan.id,
        scheduled_for=datetime(2026, 8, 15, 4, 0, tzinfo=UTC),
    )
    now = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: run_scheduler_once(scheduler_runtime, now=now),
                range(2),
            )
        )

    with scheduler_runtime.database.engine.begin() as connection:
        occurrences = (
            connection.execute(
                select(collection_schedule_occurrences_table).where(
                    collection_schedule_occurrences_table.c.plan_id == plan.id
                )
            )
            .mappings()
            .all()
        )
        runs = connection.execute(select(collection_runs_table)).mappings().all()
        jobs = connection.execute(select(jobs_table)).mappings().all()

    assert len(occurrences) == 1
    assert occurrences[0]["status"] == "enqueued"
    assert len(runs) == 1
    assert len(jobs) == 1
    assert sum(item.enqueued for item in results) == 1
