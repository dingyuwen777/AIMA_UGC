"""Stage 7 Scheduler 词包 → 显式 Run Scope PostgreSQL 集成测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.adapters.persistence.postgres.keywords import PostgresKeywordCatalogRepository
from aima_ugc.adapters.persistence.postgres.relevance import (
    PostgresGlobalRelevanceRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
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
from aima_ugc.modules.system.models import Keyword, KeywordPack, KeywordPackItem, ProviderConfig
from aima_ugc.modules.system.tables import (
    global_relevance_config_table,
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
    provider_configs_table,
)
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from sqlalchemy import delete, select


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


def test_scheduler_freezes_keyword_pack_version_and_explicit_platform_scopes(
    scheduler_runtime,
) -> None:
    session = scheduler_runtime.database.new_session()
    try:
        with session.begin():
            keyword_repository = PostgresKeywordCatalogRepository(session)
            provider_repository = PostgresProviderConfigRepository(session)
            pack = keyword_repository.create_pack(
                KeywordPack(
                    id=uuid4(),
                    name=f"scheduled-pack-{uuid4()}",
                    description="scheduled scope snapshot",
                    enabled=True,
                    version=3,
                )
            )
            aima = keyword_repository.create_keyword(
                Keyword(id=uuid4(), text="爱玛", normalized_text=f"爱玛-{uuid4()}", enabled=True)
            )
            ev = keyword_repository.create_keyword(
                Keyword(
                    id=uuid4(),
                    text="电动车",
                    normalized_text=f"电动车-{uuid4()}",
                    enabled=True,
                )
            )
            keyword_repository.add_item(
                KeywordPackItem(
                    pack_id=pack.id,
                    keyword_id=aima.id,
                    platform_scope="all",
                    priority=10,
                    enabled=True,
                    note="all platforms",
                )
            )
            keyword_repository.add_item(
                KeywordPackItem(
                    pack_id=pack.id,
                    keyword_id=ev.id,
                    platform_scope="xiaohongshu",
                    priority=20,
                    enabled=True,
                    note="xiaohongshu only",
                )
            )
            PostgresGlobalRelevanceRepository(session).set(pack.id)
            xhs_config = provider_repository.create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="TikHub XHS",
                    base_url="https://api.tikhub.io",
                    secret_ref="providers/tikhub/test/xiaohongshu",
                    enabled=True,
                )
            )
            douyin_config = provider_repository.create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="TikHub Douyin",
                    base_url="https://api.tikhub.io",
                    secret_ref="providers/tikhub/test/douyin",
                    enabled=True,
                )
            )
            planning_repository = PostgresCollectionPlanningRepository(session)
            plan = CollectionPlanningService(planning_repository).create_plan(
                CollectionPlanDefinition(
                    name=f"scheduled-scope-{uuid4()}",
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
                            provider_config_id=xhs_config.id,
                            config={},
                        ),
                        PlanPlatformDefinition(
                            platform="douyin",
                            provider_config_id=douyin_config.id,
                            config={},
                        ),
                    ),
                    keyword_pack_ids=(pack.id,),
                )
            )
            planning_repository.update_schedule_cursor(
                plan_id=plan.id,
                schedule_version=plan.schedule_version,
                next_run_at=datetime(2026, 8, 15, 4, 0, tzinfo=UTC),
                last_scheduled_at=None,
            )
    finally:
        session.close()

    result = run_scheduler_once(
        scheduler_runtime,
        now=datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
    )
    assert result.enqueued == 1

    session = scheduler_runtime.database.new_session()
    try:
        run = session.execute(select(collection_runs_table)).mappings().one()
        scopes = (
            session.execute(select(collection_scopes_table).order_by(collection_scopes_table.c.id))
            .mappings()
            .all()
        )

        assert {
            (row["platform"], row["source_type"], row["source_value"], row["operation_group"])
            for row in scopes
        } == {
            ("xiaohongshu", "keyword_search", "爱玛", "content_discovery"),
            ("douyin", "keyword_search", "爱玛", "content_discovery"),
            ("xiaohongshu", "keyword_search", "电动车", "content_discovery"),
        }
        assert run["config_snapshot"]["keyword_pack_ids"] == [str(pack.id)]
        assert run["config_snapshot"]["keyword_packs"] == [
            {"id": str(pack.id), "version": 5, "enabled": True}
        ]
        assert run["config_snapshot"]["keyword_scope_count"] == 3
        assert "request_budget" not in run["config_snapshot"]
    finally:
        session.close()
