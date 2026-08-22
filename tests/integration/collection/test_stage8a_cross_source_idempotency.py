"""Stage 8A Excel/TikHub 跨来源去重、历史与失败重试 PostgreSQL 18 验收。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.keywords import PostgresKeywordCatalogRepository
from aima_ugc.adapters.persistence.postgres.relevance import (
    PostgresGlobalRelevanceRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.providers.tikhub import runtime as tikhub_runtime
from aima_ugc.bootstrap.manual_ingestion import (
    ingest_excel_files_run_to_postgres,
    ingest_excel_run_to_postgres,
)
from aima_ugc.bootstrap.tikhub_test_database import create_tikhub_debug_database_session
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import (
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.contracts.collection import CollectionDecisionPolicyV1
from aima_ugc.modules.collection.providers import ProviderTransportResponse
from aima_ugc.modules.content.tables import (
    content_metric_observations_table,
    content_versions_table,
    contents_table,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.modules.system.models import Keyword, KeywordPack, KeywordPackItem, ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.storage import ArtifactService
from pydantic import SecretStr
from sqlalchemy import func, select

_OLD_OBSERVED_AT = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
_SHARED_CONTENT_ID = "stage8a-shared-content"


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
        )
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def _content(
    *,
    external_content_id: str,
    title: str,
    like_count: int,
    observed_at: datetime = _OLD_OBSERVED_AT,
    source_value: str = "stage8a.xlsx",
) -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=external_content_id,
        content_type="note",
        title=title,
        text="爱玛 Stage 8A 验收正文",
        observed_at=observed_at,
        metrics=CanonicalMetricsV1(like_count=like_count),
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            source_type="file",
            source_value=source_value,
            item_locator=f"content:{external_content_id}",
            observed_at=observed_at,
        ),
        observed_fields=[
            "content_type",
            "title",
            "text",
            "metrics.like_count",
        ],
    )


def _write_unified(path: Path, content: CanonicalContentV1, *, invalid_tail: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = UnifiedContentRecordV1(content=content, matched_keywords=["爱玛"])
    payload = record.model_dump_json() + "\n"
    if invalid_tail:
        payload += '{"invalid":"record"}\n'
    path.write_text(payload, encoding="utf-8")


def _write_unified_records(path: Path, contents: tuple[CanonicalContentV1, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        UnifiedContentRecordV1(content=content, matched_keywords=["爱玛"]).model_dump_json() + "\n"
        for content in contents
    )
    path.write_text(payload, encoding="utf-8")


def _create_provider_config(database_runtime: DatabaseRuntime) -> tuple[ProviderConfig, Path]:
    settings = load_settings()
    secret_ref = f"providers/tikhub/stage8a/{uuid4().hex}"
    secret_path = settings.secret_dir / secret_ref
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_text("fixture-secret\n", encoding="utf-8")
    session = database_runtime.new_session()
    try:
        with session.begin():
            keywords = PostgresKeywordCatalogRepository(session)
            pack = keywords.create_pack(
                KeywordPack(
                    id=uuid4(),
                    name=f"stage8a-cross-relevance-{uuid4()}",
                    description="Stage 8B 全局相关性测试前置事实",
                    enabled=True,
                    version=1,
                )
            )
            keyword = keywords.get_or_create_keyword(
                Keyword(
                    id=uuid4(),
                    text="爱玛",
                    normalized_text="爱玛",
                    enabled=True,
                )
            )
            keywords.add_item(
                KeywordPackItem(
                    pack_id=pack.id,
                    keyword_id=keyword.id,
                    platform_scope="all",
                    priority=10,
                    enabled=True,
                    note="Stage 8A Cross Source Integration",
                )
            )
            PostgresGlobalRelevanceRepository(session).set(pack.id)
            provider_config = PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="Stage 8A Cross Source",
                    base_url="https://api.tikhub.dev",
                    secret_ref=secret_ref,
                    enabled=True,
                )
            )
    finally:
        session.close()
    return provider_config, secret_path


def test_repeated_excel_and_later_tikhub_converge_to_one_current_with_history(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    xlsx_path = tmp_path / "stage8a.xlsx"
    xlsx_path.write_bytes(b"stage8a-xlsx-source")
    unified_path = tmp_path / "deduplicated.jsonl"
    _write_unified(
        unified_path,
        _content(
            external_content_id=_SHARED_CONTENT_ID,
            title="Excel 初始标题",
            like_count=1,
        ),
    )

    first = ingest_excel_run_to_postgres(
        input_path=xlsx_path,
        unified_content_path=unified_path,
        rows_seen=1,
    )
    second = ingest_excel_run_to_postgres(
        input_path=xlsx_path,
        unified_content_path=unified_path,
        rows_seen=1,
    )
    assert first.batch_id != second.batch_id
    assert first.rows_ingested == second.rows_ingested == 1

    provider_config, secret_path = _create_provider_config(database_runtime)
    bridge = create_tikhub_debug_database_session(
        platform="xiaohongshu",
        keywords=("爱玛",),
        run_id=f"stage8a-cross-{uuid4().hex}",
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
        (ProviderTransportResponse(status_code=200, body={"ok": True}),)
    )
    dispatched_attempt_id = None
    try:
        call = tikhub_runtime.build_search_call(
            platform="xiaohongshu",
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
            mirror_response=lambda response: None,
        )
        dispatched_attempt_id = dispatched.provider_attempt_id
        item_locator = "search.page[1].items[0]"
        candidate_id = bridge.discover_candidate(
            provider_attempt_id=dispatched.provider_attempt_id,
            raw_artifact_id=dispatched.raw_artifact_id,
            item_kind="content",
            item_locator=item_locator,
            discovered_at=dispatched.observed_at,
        )
        canonical = tikhub_runtime.map_content(
            platform="xiaohongshu",
            raw={
                "id": _SHARED_CONTENT_ID,
                "type": "normal",
                "title": "TikHub 较新标题",
                "desc": "爱玛 Stage 8A 验收正文",
                "liked_count": 9,
            },
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
        bridge.ingest_content(canonical, candidate_id=candidate_id)
        bridge.finish(error=None, stop_reasons={"爱玛": "provider_exhausted"})
    finally:
        bridge.close()
        secret_path.unlink(missing_ok=True)

    assert transport.call_count == 1
    assert dispatched_attempt_id is not None

    session = database_runtime.new_session()
    try:
        with session.begin():
            rows = (
                session.execute(
                    select(contents_table).where(
                        contents_table.c.platform == "xiaohongshu",
                        contents_table.c.external_content_id == _SHARED_CONTENT_ID,
                    )
                )
                .mappings()
                .all()
            )
            assert len(rows) == 1
            current = rows[0]
            assert current["title"] == "TikHub 较新标题"
            assert current["current_like_count"] == 9
            assert current["current_version"] == 2

            versions = session.execute(
                select(
                    content_versions_table.c.version_no,
                    content_versions_table.c.provider_attempt_id,
                )
                .where(content_versions_table.c.content_id == current["id"])
                .order_by(content_versions_table.c.version_no)
            ).all()
            assert len(versions) == 2
            assert versions[0].provider_attempt_id != versions[1].provider_attempt_id
            assert versions[1].provider_attempt_id == dispatched_attempt_id

            metric_reasons = (
                session.execute(
                    select(content_metric_observations_table.c.reason)
                    .where(content_metric_observations_table.c.content_id == current["id"])
                    .order_by(content_metric_observations_table.c.observed_at)
                )
                .scalars()
                .all()
            )
            assert metric_reasons == ["initial", "changed"]
    finally:
        session.close()


def test_multi_excel_run_keeps_one_artifact_and_batch_per_source(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.xlsx"
    second_path = tmp_path / "second.xlsx"
    first_path.write_bytes(b"stage8a-first-xlsx")
    second_path.write_bytes(b"stage8a-second-xlsx")
    unified_path = tmp_path / "multi-deduplicated.jsonl"
    _write_unified_records(
        unified_path,
        (
            _content(
                external_content_id="stage8a-multi-first",
                title="第一来源",
                like_count=1,
                source_value=first_path.name,
            ),
            _content(
                external_content_id="stage8a-multi-second",
                title="第二来源",
                like_count=2,
                source_value=second_path.name,
            ),
        ),
    )

    summary = ingest_excel_files_run_to_postgres(
        source_rows=((first_path, 3), (second_path, 4)),
        unified_content_path=unified_path,
    )

    assert summary.rows_seen == 7
    assert summary.rows_ingested == 2
    assert summary.rows_rejected == 0
    assert len(summary.batches) == 2
    assert [item.rows_ingested for item in summary.batches] == [1, 1]
    assert len({item.batch_id for item in summary.batches}) == 2
    assert len({item.input_artifact_id for item in summary.batches}) == 2

    session = database_runtime.new_session()
    try:
        with session.begin():
            statuses = (
                session.execute(
                    select(processing_import_batches_table.c.status).order_by(
                        processing_import_batches_table.c.created_at
                    )
                )
                .scalars()
                .all()
            )
            assert statuses == ["succeeded", "succeeded"]
            assert session.scalar(select(func.count()).select_from(contents_table)) == 2
    finally:
        session.close()


def test_failed_database_stage_can_retry_without_business_duplicate(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    xlsx_path = tmp_path / "retry.xlsx"
    xlsx_path.write_bytes(b"stage8a-retry-xlsx")
    unified_path = tmp_path / "retry.jsonl"
    content = _content(
        external_content_id="stage8a-retry-content",
        title="重试标题",
        like_count=3,
    )
    _write_unified(unified_path, content, invalid_tail=True)

    with pytest.raises(ValueError, match="第 2 行"):
        ingest_excel_run_to_postgres(
            input_path=xlsx_path,
            unified_content_path=unified_path,
            rows_seen=2,
        )

    session = database_runtime.new_session()
    try:
        with session.begin():
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(contents_table)
                    .where(
                        contents_table.c.platform == "xiaohongshu",
                        contents_table.c.external_content_id == "stage8a-retry-content",
                    )
                )
                == 0
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(processing_import_batches_table)
                    .where(processing_import_batches_table.c.status == "failed")
                )
                == 1
            )
    finally:
        session.close()

    _write_unified(unified_path, content)
    retry = ingest_excel_run_to_postgres(
        input_path=xlsx_path,
        unified_content_path=unified_path,
        rows_seen=1,
    )
    replay = ingest_excel_run_to_postgres(
        input_path=xlsx_path,
        unified_content_path=unified_path,
        rows_seen=1,
    )
    assert retry.rows_ingested == replay.rows_ingested == 1

    session = database_runtime.new_session()
    try:
        with session.begin():
            current = (
                session.execute(
                    select(contents_table).where(
                        contents_table.c.platform == "xiaohongshu",
                        contents_table.c.external_content_id == "stage8a-retry-content",
                    )
                )
                .mappings()
                .one()
            )
            assert current["current_version"] == 1
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(content_versions_table)
                    .where(content_versions_table.c.content_id == current["id"])
                )
                == 1
            )
            statuses = (
                session.execute(
                    select(processing_import_batches_table.c.status).order_by(
                        processing_import_batches_table.c.created_at
                    )
                )
                .scalars()
                .all()
            )
            assert statuses.count("failed") == 1
            assert statuses.count("succeeded") == 2
    finally:
        session.close()


def test_artifact_link_failure_marks_batch_failed_without_content(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    xlsx_path = tmp_path / "artifact-link-failure.xlsx"
    xlsx_path.write_bytes(b"stage8a-artifact-link-failure")
    unified_path = tmp_path / "artifact-link-failure.jsonl"
    _write_unified(
        unified_path,
        _content(
            external_content_id="stage8a-artifact-link-failure",
            title="Artifact link failure",
            like_count=1,
        ),
    )

    def _fail_link(self: ArtifactService, artifact_id: object) -> object:
        raise RuntimeError("stage8a-artifact-link-failure")

    monkeypatch.setattr(ArtifactService, "link", _fail_link)

    with pytest.raises(RuntimeError, match="stage8a-artifact-link-failure"):
        ingest_excel_run_to_postgres(
            input_path=xlsx_path,
            unified_content_path=unified_path,
            rows_seen=1,
        )

    session = database_runtime.new_session()
    try:
        with session.begin():
            statuses = (
                session.execute(select(processing_import_batches_table.c.status)).scalars().all()
            )
            assert statuses == ["failed"]
            assert session.scalar(select(func.count()).select_from(contents_table)) == 0
    finally:
        session.close()
