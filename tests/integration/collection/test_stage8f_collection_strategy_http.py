"""Stage 8F 采集策略产品化的 PostgreSQL 18 集成测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
    StaleCollectionPlanError,
)
from aima_ugc.bootstrap.collection_strategy_http import (
    PostgresCollectionStrategyHttpService,
)
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.http import (
    CollectionPlanCreateRequest,
    CollectionPlanListQuery,
    CollectionPlanPlatformRequest,
    KeywordPackListQuery,
    ResourceEnabledRequest,
)
from aima_ugc.modules.collection.strategy_http import CollectionStrategyConflict
from aima_ugc.modules.collection.tables import collection_plans_table, collection_runs_table
from aima_ugc.modules.system.tables import (
    global_relevance_config_table,
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
    provider_configs_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs.tables import jobs_table
from sqlalchemy import func, insert, select


@pytest.fixture
def runtime():  # type: ignore[no-untyped-def]
    value = create_worker_runtime(settings=load_settings())

    def cleanup() -> None:
        with value.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, collection_plans, keyword_packs, "
                "accounts, provider_configs RESTART IDENTITY CASCADE"
            )

    cleanup()
    try:
        yield value
    finally:
        cleanup()
        value.close()


def _seed_strategy_facts(runtime) -> tuple[UUID, UUID, UUID]:  # type: ignore[no-untyped-def]
    provider_id = uuid4()
    discovery_pack_id = uuid4()
    relevance_pack_id = uuid4()
    discovery_keyword_id = uuid4()
    relevance_keyword_id = uuid4()
    now = datetime.now(UTC)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(provider_configs_table).values(
                id=provider_id,
                provider="tikhub",
                display_name="TikHub 主配置",
                base_url="https://api.tikhub.io",
                secret_ref="providers/tikhub/stage8f",
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(keyword_packs_table).values(
                [
                    {
                        "id": discovery_pack_id,
                        "name": f"stage8f-discovery-{uuid4()}",
                        "description": "Discovery",
                        "enabled": True,
                        "version": 1,
                        "created_at": now,
                        "updated_at": now,
                    },
                    {
                        "id": relevance_pack_id,
                        "name": f"stage8f-relevance-{uuid4()}",
                        "description": "Relevance",
                        "enabled": True,
                        "version": 1,
                        "created_at": now,
                        "updated_at": now,
                    },
                ]
            )
        )
        connection.execute(
            insert(keywords_table).values(
                [
                    {
                        "id": discovery_keyword_id,
                        "text": "爱玛 Q7",
                        "normalized_text": f"stage8f-discovery-{uuid4()}",
                        "enabled": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                    {
                        "id": relevance_keyword_id,
                        "text": "爱玛",
                        "normalized_text": f"stage8f-relevance-{uuid4()}",
                        "enabled": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                ]
            )
        )
        connection.execute(
            insert(keyword_pack_items_table).values(
                [
                    {
                        "pack_id": discovery_pack_id,
                        "keyword_id": discovery_keyword_id,
                        "platform_scope": "all",
                        "priority": 10,
                        "enabled": True,
                        "note": "Stage 8F Discovery",
                    },
                    {
                        "pack_id": relevance_pack_id,
                        "keyword_id": relevance_keyword_id,
                        "platform_scope": "all",
                        "priority": 10,
                        "enabled": True,
                        "note": "Stage 8F Relevance",
                    },
                ]
            )
        )
        connection.execute(
            insert(global_relevance_config_table).values(
                singleton_key="global",
                keyword_pack_id=relevance_pack_id,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
    return provider_id, discovery_pack_id, relevance_pack_id


def _plan_request(provider_id: UUID, pack_id: UUID) -> CollectionPlanCreateRequest:
    return CollectionPlanCreateRequest(
        name=f"stage8f-plan-{uuid4()}",
        schedule_expr="0 9 * * *",
        platforms=(
            CollectionPlanPlatformRequest(
                platform="xiaohongshu",
                provider_config_id=provider_id,
                search_config={
                    "sort_mode": "latest",
                    "published_within": "1d",
                    "content_type": "all",
                },
            ),
        ),
        keyword_pack_ids=(pack_id,),
        enabled=True,
    )


def test_strategy_service_creates_queryable_plan_without_creating_job(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_id, discovery_pack_id, _ = _seed_strategy_facts(runtime)
    service = PostgresCollectionStrategyHttpService(runtime)

    packs = service.list_keyword_packs(KeywordPackListQuery(limit=20))
    created = service.create_plan(_plan_request(provider_id, discovery_pack_id))
    listing = service.list_plans(CollectionPlanListQuery(platform="xiaohongshu", limit=20))
    by_plan_id = service.list_plans(CollectionPlanListQuery(search=str(created.id)[:12], limit=20))
    loaded = service.get_plan(created.id)

    assert packs.total == 2
    assert {item.keyword_count for item in packs.items} == {1}
    assert listing.total == listing.enabled_count == 1
    assert listing.items == (created,)
    assert by_plan_id.total == 1
    assert by_plan_id.items == (created,)
    assert loaded == created
    assert created.timezone == "Asia/Shanghai"
    assert created.detail_policy == "on_change"
    assert created.comment_policy == "adaptive"
    assert created.platforms[0].search_config.model_dump(exclude_none=True) == {
        "sort_mode": "latest",
        "published_within": "1d",
        "content_type": "all",
    }
    with runtime.database.engine.begin() as connection:
        assert connection.scalar(select(func.count()).select_from(collection_plans_table)) == 1
        assert connection.scalar(select(func.count()).select_from(jobs_table)) == 0
        assert connection.scalar(select(func.count()).select_from(collection_runs_table)) == 0


def test_plan_and_pack_enablement_are_fenced_and_preserve_global_relevance(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_id, discovery_pack_id, relevance_pack_id = _seed_strategy_facts(runtime)
    service = PostgresCollectionStrategyHttpService(runtime)
    created = service.create_plan(_plan_request(provider_id, discovery_pack_id))

    with pytest.raises(CollectionStrategyConflict):
        service.set_keyword_pack_enabled(
            relevance_pack_id,
            ResourceEnabledRequest(enabled=False),
        )
    with pytest.raises(CollectionStrategyConflict):
        service.set_keyword_pack_enabled(
            discovery_pack_id,
            ResourceEnabledRequest(enabled=False),
        )

    disabled = service.set_plan_enabled(created.id, ResourceEnabledRequest(enabled=False))
    pack = service.set_keyword_pack_enabled(
        discovery_pack_id,
        ResourceEnabledRequest(enabled=False),
    )
    assert disabled.enabled is False
    assert disabled.schedule_version == created.schedule_version + 1
    assert disabled.next_run_at is None
    assert pack.enabled is False

    with pytest.raises(CollectionStrategyConflict):
        service.set_plan_enabled(created.id, ResourceEnabledRequest(enabled=True))

    service.set_keyword_pack_enabled(
        discovery_pack_id,
        ResourceEnabledRequest(enabled=True),
    )
    reenabled = service.set_plan_enabled(created.id, ResourceEnabledRequest(enabled=True))
    assert reenabled.enabled is True
    assert reenabled.schedule_version == created.schedule_version + 2

    session = runtime.database.new_session()
    try:
        with session.begin():
            with pytest.raises(StaleCollectionPlanError):
                PostgresCollectionPlanningRepository(session).update_schedule_cursor(
                    plan_id=created.id,
                    schedule_version=created.schedule_version,
                    next_run_at=datetime.now(UTC) + timedelta(hours=1),
                    last_scheduled_at=None,
                )
    finally:
        session.close()


def test_enabled_plan_requires_keyword_for_every_platform(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_id, discovery_pack_id, _ = _seed_strategy_facts(runtime)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            keyword_pack_items_table.update()
            .where(keyword_pack_items_table.c.pack_id == discovery_pack_id)
            .values(platform_scope="douyin")
        )
    service = PostgresCollectionStrategyHttpService(runtime)

    with pytest.raises(CollectionStrategyConflict):
        service.create_plan(_plan_request(provider_id, discovery_pack_id))

    with runtime.database.engine.begin() as connection:
        assert connection.scalar(select(func.count()).select_from(collection_plans_table)) == 0


def test_new_plan_requires_complete_platform_search_config(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_id, discovery_pack_id, _ = _seed_strategy_facts(runtime)
    request = _plan_request(provider_id, discovery_pack_id).model_copy(
        update={
            "platforms": (
                CollectionPlanPlatformRequest(
                    platform="xiaohongshu",
                    provider_config_id=provider_id,
                    search_config={"sort_mode": "latest", "content_type": "all"},
                ),
            )
        }
    )

    with pytest.raises(CollectionStrategyConflict):
        PostgresCollectionStrategyHttpService(runtime).create_plan(request)

    with runtime.database.engine.begin() as connection:
        assert connection.scalar(select(func.count()).select_from(collection_plans_table)) == 0


def test_strategy_service_does_not_mask_unsupported_persisted_policy(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_id, discovery_pack_id, _ = _seed_strategy_facts(runtime)
    service = PostgresCollectionStrategyHttpService(runtime)
    created = service.create_plan(_plan_request(provider_id, discovery_pack_id))
    with runtime.database.engine.begin() as connection:
        connection.execute(
            collection_plans_table.update()
            .where(collection_plans_table.c.id == created.id)
            .values(detail_policy="unsupported")
        )

    with pytest.raises(RuntimeError, match="Plan 策略事实"):
        service.get_plan(created.id)
