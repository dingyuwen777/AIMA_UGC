"""Stage 7 Scheduler PostgreSQL 运行闭环测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres import (
    PostgresCollectionPlanningRepository,
    PostgresCollectionRunExecutionRepository,
    PostgresGlobalRelevanceRepository,
    PostgresJobRepository,
    PostgresScheduledKeywordSnapshotRepository,
)
from aima_ugc.bootstrap.scheduler import (
    _create_scheduler_runtime,
    _run_scheduler_tick,
)
from aima_ugc.modules.collection.planning import (
    CollectionPlanDefinition,
    CollectionPlanningService,
    PlanPlatformDefinition,
)
from aima_ugc.modules.collection.tables import (
    collection_occurrences_table,
    collection_plan_platforms_table,
    collection_plans_table,
    collection_run_cursors_table,
    collection_runs_table,
    provider_configs_table,
)
from aima_ugc.modules.system.tables import (
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobRegistry, JobWorker, register_job_runtime
from sqlalchemy import delete, insert, select

pytestmark = pytest.mark.integration


@pytest.fixture
def scheduler_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AIMA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AIMA_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("AIMA_SECRET_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("AIMA_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("AIMA_DB_PORT", "5432")
    monkeypatch.setenv("AIMA_DB_NAME", "aima_ugc")
    monkeypatch.setenv("AIMA_DB_USER", "aima_ugc")
    monkeypatch.setenv("AIMA_DB_CONNECT_TIMEOUT_SECONDS", "3")

    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(parents=True, exist_ok=True)
    (secret_dir / "postgres_password").write_text("stage7-scheduler-ci\n", encoding="utf-8")

    settings = load_settings()
    runtime = _create_scheduler_runtime(settings)
    try:
        yield runtime
    finally:
        runtime.close()


def _cleanup(runtime) -> None:
    tables = (
        collection_run_cursors_table,
        collection_occurrences_table,
        collection_plan_platforms_table,
        collection_plans_table,
        collection_runs_table,
        keyword_pack_items_table,
        keyword_packs_table,
        keywords_table,
        provider_configs_table,
    )
    with runtime.database_runtime.session_factory() as session:
        with session.begin():
            for table in tables:
                session.execute(delete(table))


def _create_plan(runtime):
    provider_config_id = uuid4()
    keyword_pack_id = uuid4()
    keyword_id = uuid4()
    with runtime.database_runtime.session_factory() as session:
        with session.begin():
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
                    platform_scope="xiaohongshu",
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
                            platform="xiaohongshu",
                            provider_config_id=provider_config_id,
                            order_index=0,
                            enabled=True,
                            config={
                                "operations": ["keyword_search"],
                                "search": {"sort_mode": "latest"},
                            },
                        ),
                    ),
                    keyword_pack_ids=(keyword_pack_id,),
                )
            )
    return plan


def _worker(runtime) -> JobWorker:
    registry = JobRegistry()
    register_job_runtime(registry)
    return JobWorker(
        repository=PostgresJobRepository(runtime.database_runtime.session_factory),
        registry=registry,
        worker_id="scheduler-test-worker",
        max_attempts=1,
    )


def test_scheduler_initializes_future_cursor_without_pre_creation_backfill(
    scheduler_runtime,
) -> None:
    plan = _create_plan(scheduler_runtime)
    try:
        now = datetime.now(UTC)
        outcome = _run_scheduler_tick(scheduler_runtime, now)
        assert outcome.scanned_plan_count == 1
        assert outcome.enqueued_count == 0
        assert outcome.initialized_count == 1
        with scheduler_runtime.database_runtime.session_factory() as session:
            cursor = session.execute(
                select(collection_run_cursors_table).where(
                    collection_run_cursors_table.c.plan_id == plan.id
                )
            ).mappings().one()
            assert cursor["next_run_at"] > now
            assert session.scalar(select(collection_occurrences_table.c.id)) is None
    finally:
        _cleanup(scheduler_runtime)


def test_latest_only_recovery_commits_skipped_job_occurrence_run_and_cursor_atomically(
    scheduler_runtime,
) -> None:
    plan = _create_plan(scheduler_runtime)
    try:
        now = datetime.now(UTC)
        _run_scheduler_tick(scheduler_runtime, now)
        with scheduler_runtime.database_runtime.session_factory() as session:
            cursor = session.execute(
                select(collection_run_cursors_table).where(
                    collection_run_cursors_table.c.plan_id == plan.id
                )
            ).mappings().one()
            due_at = cursor["next_run_at"]
        later = due_at + timedelta(hours=12, minutes=1)
        outcome = _run_scheduler_tick(scheduler_runtime, later)
        assert outcome.enqueued_count == 1
        assert outcome.skipped_count == 2
        with scheduler_runtime.database_runtime.session_factory() as session:
            occurrences = session.execute(
                select(collection_occurrences_table)
                .where(collection_occurrences_table.c.plan_id == plan.id)
                .order_by(collection_occurrences_table.c.scheduled_for)
            ).mappings().all()
            assert [item["status"] for item in occurrences] == ["skipped", "skipped", "enqueued"]
            runs = session.execute(
                select(collection_runs_table).where(collection_runs_table.c.plan_id == plan.id)
            ).mappings().all()
            assert len(runs) == 1
            assert runs[0]["trigger"] == "scheduled"
            cursor = session.execute(
                select(collection_run_cursors_table).where(
                    collection_run_cursors_table.c.plan_id == plan.id
                )
            ).mappings().one()
            assert cursor["next_run_at"] > later
    finally:
        _cleanup(scheduler_runtime)


def test_two_scheduler_ticks_do_not_duplicate_same_occurrence(scheduler_runtime) -> None:
    plan = _create_plan(scheduler_runtime)
    try:
        now = datetime.now(UTC)
        _run_scheduler_tick(scheduler_runtime, now)
        with scheduler_runtime.database_runtime.session_factory() as session:
            due_at = session.scalar(
                select(collection_run_cursors_table.c.next_run_at).where(
                    collection_run_cursors_table.c.plan_id == plan.id
                )
            )
        assert due_at is not None
        first = _run_scheduler_tick(scheduler_runtime, due_at)
        second = _run_scheduler_tick(scheduler_runtime, due_at)
        assert first.enqueued_count == 1
        assert second.enqueued_count == 0
        with scheduler_runtime.database_runtime.session_factory() as session:
            occurrences = session.scalars(
                select(collection_occurrences_table.c.id).where(
                    collection_occurrences_table.c.plan_id == plan.id,
                    collection_occurrences_table.c.scheduled_for == due_at,
                )
            ).all()
            assert len(occurrences) == 1
    finally:
        _cleanup(scheduler_runtime)
