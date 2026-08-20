"""Scheduler 创建 collection.run.v1 后由生产 Worker 装配消费的纵切测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.adapters.persistence.postgres.keywords import PostgresKeywordCatalogRepository
from aima_ugc.adapters.persistence.postgres.relevance import (
    PostgresGlobalRelevanceRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.bootstrap.scheduler import create_scheduler_runtime, run_scheduler_once
from aima_ugc.entrypoints.worker_main import create_collection_job_registry, create_job_worker
from aima_ugc.modules.collection.planning import (
    CollectionPlanDefinition,
    CollectionPlanningService,
    PlanPlatformDefinition,
)
from aima_ugc.modules.collection.providers import ProviderTransportResponse
from aima_ugc.modules.collection.tables import collection_runs_table, collection_scopes_table
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.system.models import Keyword, KeywordPack, KeywordPackItem, ProviderConfig
from aima_ugc.platform.jobs.tables import jobs_table
from pydantic import SecretStr
from sqlalchemy import select

_FIXTURES = Path("tests/fixtures/providers/tikhub/xhs")


def _fixture(name: str) -> dict[str, object]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _search_response() -> dict[str, object]:
    body = _fixture("search_notes_page1.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)
    items = page["items"]
    assert isinstance(items, list) and items
    first = items[0]
    assert isinstance(first, dict)
    note = first["note"]
    assert isinstance(note, dict)
    note["comments_count"] = 0
    page["items"] = [first]
    page["has_more"] = False
    return body


def _detail_response() -> dict[str, object]:
    body = _fixture("image_detail.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    rows = outer["data"]
    assert isinstance(rows, list) and rows
    wrapper = rows[0]
    assert isinstance(wrapper, dict)
    notes = wrapper["note_list"]
    assert isinstance(notes, list) and notes
    note = notes[0]
    assert isinstance(note, dict)
    note["id"] = "note-fixture-1"
    note["comments_count"] = 0
    return body


def test_production_worker_consumes_scheduler_created_collection_run() -> None:
    runtime = create_scheduler_runtime()
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
        )
    try:
        session = runtime.database.new_session()
        try:
            with session.begin():
                keywords = PostgresKeywordCatalogRepository(session)
                providers = PostgresProviderConfigRepository(session)
                pack = keywords.create_pack(
                    KeywordPack(
                        id=uuid4(),
                        name=f"worker-pack-{uuid4()}",
                        description="production worker vertical slice",
                        enabled=True,
                        version=1,
                    )
                )
                keyword = keywords.create_keyword(
                    Keyword(
                        id=uuid4(),
                        text="脱敏",
                        normalized_text=f"脱敏-{uuid4()}",
                        enabled=True,
                    )
                )
                keywords.add_item(
                    KeywordPackItem(
                        pack_id=pack.id,
                        keyword_id=keyword.id,
                        platform="xhs",
                        priority=10,
                        enabled=True,
                        note="worker vertical slice",
                    )
                )
                PostgresGlobalRelevanceRepository(session).set(pack.id)
                provider_config = providers.create(
                    ProviderConfig(
                        id=uuid4(),
                        provider="tikhub",
                        display_name="TikHub Worker Runtime",
                        base_url="https://api.tikhub.io",
                        secret_ref="providers/tikhub/test/worker-runtime",
                        enabled=True,
                    )
                )
                planning_repository = PostgresCollectionPlanningRepository(session)
                plan = CollectionPlanningService(planning_repository).create_plan(
                    CollectionPlanDefinition(
                        name=f"worker-runtime-{uuid4()}",
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
                                provider_config_id=provider_config.id,
                                config={
                                    "sort_mode": "latest",
                                    "published_within": "1d",
                                    "content_type": "all",
                                },
                            ),
                        ),
                        keyword_pack_ids=(pack.id,),
                    )
                )
                planning_repository.update_schedule_cursor(
                    plan_id=plan.id,
                    schedule_version=plan.schedule_version,
                    next_run_at=datetime(2026, 8, 17, 4, 0, tzinfo=UTC),
                    last_scheduled_at=None,
                )
        finally:
            session.close()

        scheduled = run_scheduler_once(
            runtime,
            now=datetime(2026, 8, 17, 5, 0, tzinfo=UTC),
        )
        assert scheduled.enqueued == 1

        transport = FakeProviderTransport(
            (
                ProviderTransportResponse(status_code=200, body=_search_response()),
                ProviderTransportResponse(status_code=200, body=_detail_response()),
            )
        )
        registry = create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda secret_ref: (
                SecretStr("fixture-secret")
                if secret_ref == provider_config.secret_ref
                else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
            ),
        )
        worker = create_job_worker(
            runtime=runtime,
            registry=registry,
            worker_id="collection-worker-integration",
            lease_seconds=120,
            retry_delay_seconds=0,
        )

        assert registry.supported_types == (
            "collection.run.v1",
            "ingestion.import-excel.v1",
            "analysis.content-label.v1",
            "reporting.content-export-excel.v1",
        )
        assert worker.run_once() is True
        assert worker.run_once() is False
        assert transport.call_count == 2

        session = runtime.database.new_session()
        try:
            job = session.execute(select(jobs_table)).mappings().one()
            run = session.execute(select(collection_runs_table)).mappings().one()
            scope = session.execute(select(collection_scopes_table)).mappings().one()
            content = session.execute(select(contents_table)).mappings().one()
        finally:
            session.close()

        assert job["status"] == "succeeded"
        assert run["status"] == "succeeded"
        assert scope["status"] == "succeeded"
        assert content["external_content_id"] == "note-fixture-1"
        assert "request_budget" not in run["config_snapshot"]
    finally:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
            )
        runtime.close()
