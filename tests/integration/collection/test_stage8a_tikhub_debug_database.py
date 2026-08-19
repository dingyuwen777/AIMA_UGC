"""Stage 8A tikhub_test 数据库模式的 PostgreSQL 18/Fake Transport 纵切。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.providers.tikhub import runtime as tikhub_runtime
from aima_ugc.bootstrap.tikhub_test_database import create_tikhub_debug_database_session
from aima_ugc.contracts.collection import CollectionDecisionPolicyV1
from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.providers import ProviderTransportResponse
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.tables import artifacts_table

_FIXTURE = Path("tests/fixtures/providers/tikhub/xhs/search_notes_page1.sanitized.json")


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


def _search_response() -> dict[str, object]:
    body = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)
    items = page["items"]
    assert isinstance(items, list) and items
    first = items[0]
    assert isinstance(first, dict)
    page["items"] = [first]
    page["has_more"] = False
    return body


def test_tikhub_debug_database_uses_formal_source_chain_and_sends_once(
    database_runtime: DatabaseRuntime,
) -> None:
    settings = load_settings()
    secret_ref = f"providers/tikhub/stage8a/{uuid4().hex}"
    secret_path = settings.secret_dir / secret_ref
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_text("fixture-secret\n", encoding="utf-8")

    session = database_runtime.new_session()
    try:
        with session.begin():
            provider_config = PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="Stage 8A TikHub Debug",
                    base_url="https://api.tikhub.dev",
                    secret_ref=secret_ref,
                    enabled=True,
                )
            )
    finally:
        session.close()

    bridge = create_tikhub_debug_database_session(
        platform="xhs",
        keywords=("爱玛",),
        run_id=f"stage8a-{uuid4().hex}",
        provider_config_id=provider_config.id,
        expected_base_url="https://api.tikhub.dev",
        expected_api_key=SecretStr("fixture-secret"),
        provider_timeout_seconds=45,
        search_config={
            "sort_mode": "latest",
            "published_within": "1d",
            "content_type": "all",
        },
        policy=CollectionDecisionPolicyV1(comments_enabled=False),
    )
    transport = FakeProviderTransport(
        (ProviderTransportResponse(status_code=200, body=_search_response()),)
    )
    mirrored: list[ProviderTransportResponse] = []
    try:
        call = tikhub_runtime.build_search_call(
            platform="xhs",
            keyword="爱玛",
            config={
                "sort_mode": "latest",
                "published_within": "1d",
                "content_type": "all",
            },
            state=None,
        )
        dispatched = bridge.dispatch(
            keyword="爱玛",
            call=call,
            transport=transport,
            mirror_response=mirrored.append,
        )
        body = dispatched.response.body
        assert isinstance(body, dict)
        items = tikhub_runtime.extract_search_items("xhs", body)
        assert len(items) == 1
        item_locator = "search.page[1].items[0]"
        candidate_id = bridge.discover_candidate(
            provider_attempt_id=dispatched.provider_attempt_id,
            raw_artifact_id=dispatched.raw_artifact_id,
            item_kind="content",
            item_locator=item_locator,
            discovered_at=dispatched.observed_at,
        )
        content = tikhub_runtime.map_content(
            platform="xhs",
            raw=items[0],
            context=tikhub_runtime.mapping_context(
                provider_request_id=str(dispatched.provider_request_id),
                provider_attempt_id=str(dispatched.provider_attempt_id),
                raw_artifact_id=dispatched.raw_artifact_id,
                operation=call.operation,
                source_type="keyword_search",
                source_value="爱玛",
                observed_at=dispatched.observed_at,
            ),
            item_locator=item_locator,
        )
        bridge.ingest_content(content, candidate_id=candidate_id)
        bridge.finish(error=None, stop_reasons={"爱玛": "provider_exhausted"})
    finally:
        bridge.close()
        secret_path.unlink(missing_ok=True)

    assert transport.call_count == 1
    assert len(mirrored) == 1

    session = database_runtime.new_session()
    try:
        with session.begin():
            assert session.scalar(select(func.count()).select_from(provider_requests_table)) == 1
            assert (
                session.scalar(select(func.count()).select_from(provider_request_attempts_table))
                == 1
            )
            assert session.scalar(select(func.count()).select_from(artifacts_table)) == 1
            assert (
                session.scalar(select(func.count()).select_from(collection_candidates_table)) == 1
            )
            assert (
                session.scalar(
                    select(func.count()).select_from(collection_candidate_ingestions_table)
                )
                == 1
            )
            assert session.scalar(select(func.count()).select_from(contents_table)) == 1
            run = session.execute(select(collection_runs_table)).mappings().one()
            scope = session.execute(select(collection_scopes_table)).mappings().one()
            job = session.execute(select(jobs_table)).mappings().one()
        assert run["trigger_type"] == "manual"
        assert run["status"] == "succeeded"
        assert scope["source_type"] == "keyword_search"
        assert scope["status"] == "succeeded"
        assert job["status"] == "succeeded"
    finally:
        session.close()
