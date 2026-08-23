"""Stage 8E Collection HTTP 编排的 PostgreSQL 18 集成测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.bootstrap.collection_http import PostgresCollectionHttpService
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.http import (
    CollectionRunCreateRequest,
    CollectionRunPlatformRequest,
    CollectionRuntimeListQuery,
)
from aima_ugc.entrypoints.worker_main import create_collection_job_registry, create_job_worker
from aima_ugc.modules.collection.http import (
    CollectionConflict,
    CollectionResourceNotFound,
)
from aima_ugc.modules.collection.providers import ProviderTransportResponse
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.extended_tables import (
    comment_thread_coverage_observations_table,
    content_external_ids_table,
)
from aima_ugc.modules.content.tables import comments_table, content_versions_table, contents_table
from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_PAYLOAD_VERSION, IMPORT_JOB_TYPE
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.modules.system.tables import (
    global_relevance_config_table,
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
    provider_configs_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.tables import artifacts_table
from pydantic import SecretStr
from sqlalchemy import func, insert, select, update

_XIAOHONGSHU_FIXTURES = Path("tests/fixtures/providers/tikhub/xiaohongshu")


@pytest.fixture
def runtime():  # type: ignore[no-untyped-def]
    value = create_worker_runtime(settings=load_settings())

    def cleanup() -> None:
        with value.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts, "
                "provider_configs, processing_import_batches RESTART IDENTITY CASCADE"
            )

    cleanup()
    try:
        yield value
    finally:
        cleanup()
        value.close()


def _seed_config_and_relevance(runtime) -> UUID:  # type: ignore[no-untyped-def]
    provider_config_id = uuid4()
    pack_id = uuid4()
    keyword_id = uuid4()
    now = datetime.now(UTC)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(provider_configs_table).values(
                id=provider_config_id,
                provider="tikhub",
                display_name="TikHub 主配置",
                base_url="https://api.tikhub.io",
                secret_ref="providers/tikhub/stage8e",
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(keyword_packs_table).values(
                id=pack_id,
                name=f"stage8e-relevance-{uuid4()}",
                description="stage8e relevance",
                enabled=True,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(keywords_table).values(
                id=keyword_id,
                text="爱玛",
                normalized_text=f"stage8e-aima-{uuid4()}",
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(keyword_pack_items_table).values(
                pack_id=pack_id,
                keyword_id=keyword_id,
                platform_scope="all",
                priority=10,
                enabled=True,
                note="stage8e",
            )
        )
        connection.execute(
            insert(global_relevance_config_table).values(
                singleton_key="global",
                keyword_pack_id=pack_id,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
    return provider_config_id


def test_discovery_run_creation_freezes_inputs_and_commits_job_run_scopes_atomically(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id = _seed_config_and_relevance(runtime)
    service = PostgresCollectionHttpService(
        runtime,
        cursor_signing_secret=b"r" * 32,
    )

    capabilities = service.get_capabilities()
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="discovery",
            keywords=("爱玛", "Q7"),
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu",
                    provider_config_id=provider_config_id,
                ),
            ),
            include_comments=True,
            include_sub_comments=False,
        ),
        request_id="stage8e-create",
    )
    detail = service.get_run(created.run_id)

    with runtime.database.engine.begin() as connection:
        job = (
            connection.execute(select(jobs_table).where(jobs_table.c.id == created.job_id))
            .mappings()
            .one()
        )
        run = (
            connection.execute(
                select(collection_runs_table).where(collection_runs_table.c.id == created.run_id)
            )
            .mappings()
            .one()
        )
        scopes = (
            connection.execute(
                select(collection_scopes_table)
                .where(collection_scopes_table.c.run_id == created.run_id)
                .order_by(collection_scopes_table.c.source_value)
            )
            .mappings()
            .all()
        )

    assert len(capabilities.provider_configs) == 1
    public_capabilities = capabilities.model_dump_json()
    assert "base_url" not in public_capabilities
    assert "secret_ref" not in public_capabilities
    assert "provider_operations" not in public_capabilities
    assert "provider_page_size_policy" not in public_capabilities
    assert job["job_type"] == "collection.run.v1"
    assert job["payload"] == {"schema_version": "collection.run.v1"}
    assert job["request_id"] == "stage8e-create"
    assert job["max_attempts"] == 2
    assert run["import_batch_id"] is None
    assert run["trigger_type"] == "api"
    assert run["config_snapshot"]["mode"] == "discovery"
    assert run["config_snapshot"]["keywords"] == ["爱玛", "Q7"]
    assert run["config_snapshot"]["include_comments"] is True
    assert [scope["source_value"] for scope in scopes] == ["Q7", "爱玛"]
    assert all(scope["source_type"] == "keyword_search" for scope in scopes)
    assert all(scope["operation_group"] == "content_discovery" for scope in scopes)
    assert detail.run_id == created.run_id
    assert detail.job_id == created.job_id
    assert detail.stage == "queued"
    assert len(detail.scopes) == 2


def test_collection_run_rejects_disabled_provider_config(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id = _seed_config_and_relevance(runtime)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(provider_configs_table)
            .where(provider_configs_table.c.id == provider_config_id)
            .values(enabled=False)
        )
    service = PostgresCollectionHttpService(
        runtime,
        cursor_signing_secret=b"r" * 32,
    )

    assert service.get_capabilities().provider_configs == ()
    with pytest.raises(CollectionConflict):
        service.create_run(
            CollectionRunCreateRequest(
                mode="discovery",
                keywords=("爱玛",),
                platforms=(
                    CollectionRunPlatformRequest(
                        platform="xiaohongshu",
                        provider_config_id=provider_config_id,
                    ),
                ),
                include_comments=False,
                include_sub_comments=False,
            ),
            request_id="stage8e-disabled-provider",
        )

    with runtime.database.engine.begin() as connection:
        assert connection.scalar(select(func.count()).select_from(jobs_table)) == 0
        assert connection.scalar(select(func.count()).select_from(collection_runs_table)) == 0


def _insert_succeeded_import(
    runtime,  # type: ignore[no-untyped-def]
    *,
    rows_ingested: int,
) -> tuple[UUID, UUID]:
    now = datetime.now(UTC)
    artifact_id = uuid4()
    batch_id = uuid4()
    job_id = uuid4()
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(artifacts_table).values(
                id=artifact_id,
                kind="file-import.raw",
                storage_backend="local",
                storage_key=f"stage8e-query/{artifact_id}",
                content_type="application/octet-stream",
                sha256="0" * 64,
                byte_size=0,
                retention_class="raw",
                storage_status="linked",
                created_at=now,
                stored_at=now,
                linked_at=now,
            )
        )
        connection.execute(
            insert(jobs_table).values(
                id=job_id,
                job_type=IMPORT_JOB_TYPE,
                payload_version=IMPORT_JOB_PAYLOAD_VERSION,
                payload={},
                status="succeeded",
                internal_idempotency_key=f"stage8e-query:{job_id}",
                request_id="stage8e-query",
                priority=0,
                attempt=1,
                lease_takeover_count=0,
                max_attempts=10,
                timeout_seconds=1800,
                progress=100,
                available_at=now,
                started_at=now,
                finished_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(processing_import_batches_table).values(
                id=batch_id,
                input_artifact_id=artifact_id,
                job_id=job_id,
                status="succeeded",
                stats={
                    "stage": "succeeded",
                    "source_filename": "stage8e.xlsx",
                    "rows_seen": rows_ingested,
                    "rows_matched": rows_ingested,
                    "rows_filtered_out": 0,
                    "duplicates_removed": 0,
                    "rows_ingested": rows_ingested,
                    "rows_rejected": 0,
                },
                created_at=now,
                started_at=now,
                finished_at=now,
            )
        )
    return batch_id, job_id


def test_unified_runtime_list_cursor_filters_and_summary_aggregate_both_owners(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id = _seed_config_and_relevance(runtime)
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    collection = service.create_run(
        CollectionRunCreateRequest(
            mode="discovery",
            keywords=("爱玛",),
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu",
                    provider_config_id=provider_config_id,
                ),
            ),
        ),
        request_id="stage8e-query",
    )
    batch_id, _ = _insert_succeeded_import(runtime, rows_ingested=7)
    now = datetime.now(UTC)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(collection_runs_table)
            .where(collection_runs_table.c.id == collection.run_id)
            .values(
                status="succeeded",
                started_at=now,
                finished_at=now,
                requested_count=3,
                succeeded_count=3,
                content_count=3,
            )
        )
        connection.execute(
            update(collection_scopes_table)
            .where(collection_scopes_table.c.run_id == collection.run_id)
            .values(status="succeeded", progress=100, started_at=now, finished_at=now)
        )
        connection.execute(
            update(jobs_table)
            .where(jobs_table.c.id == collection.job_id)
            .values(
                status="succeeded",
                attempt=1,
                progress=100,
                started_at=now,
                finished_at=now,
                updated_at=now,
            )
        )

    first = service.list_runtime_runs(CollectionRuntimeListQuery(limit=1))
    assert first.has_more is True
    assert first.next_cursor is not None
    second = service.list_runtime_runs(
        CollectionRuntimeListQuery(limit=1, cursor=first.next_cursor)
    )
    filtered = service.list_runtime_runs(
        CollectionRuntimeListQuery(record_types=("tikhub_discovery",))
    )
    keyword_search = service.list_runtime_runs(CollectionRuntimeListQuery(search="爱玛"))
    secret_ref_search = service.list_runtime_runs(
        CollectionRuntimeListQuery(search="providers/tikhub/stage8e")
    )
    summary = service.get_runtime_summary()

    assert {first.items[0].record_id, second.items[0].record_id} == {
        batch_id,
        collection.run_id,
    }
    assert filtered.items[0].record_id == collection.run_id
    assert filtered.items[0].record_type == "tikhub_discovery"
    assert filtered.items[0].keywords == ("爱玛",)
    assert [item.record_id for item in keyword_search.items] == [collection.run_id]
    assert secret_ref_search.items == ()
    assert summary.processing_count == 0
    assert summary.completed_today_count == 2
    assert summary.contents_ingested_today == 10


def _insert_import_content(
    runtime,  # type: ignore[no-untyped-def]
    *,
    external_content_id: str = "stage8e-batch-note",
    title: str = "爱玛 Batch 内容",
) -> tuple[UUID, UUID]:
    batch_id, _ = _insert_succeeded_import(runtime, rows_ingested=1)
    now = datetime.now(UTC)
    request_id = uuid4()
    attempt_id = uuid4()
    content_id = uuid4()
    with runtime.database.engine.begin() as connection:
        artifact_id = connection.scalar(
            select(processing_import_batches_table.c.input_artifact_id).where(
                processing_import_batches_table.c.id == batch_id
            )
        )
        assert artifact_id is not None
        connection.execute(
            insert(provider_requests_table).values(
                id=request_id,
                scope_id=None,
                import_batch_id=batch_id,
                provider_config_id=None,
                provider="file_import",
                operation="excel_import",
                request_fingerprint="1" * 64,
                request_params={},
                pagination_input={},
                status="completed",
                attempt_count=1,
                created_at=now,
                completed_at=now,
            )
        )
        connection.execute(
            insert(provider_request_attempts_table).values(
                id=attempt_id,
                provider_request_id=request_id,
                attempt_no=1,
                dispatch_status="completed",
                dispatch_started_at=now,
                completed_at=now,
                http_status=200,
                raw_artifact_id=artifact_id,
                billing_status="not_billable",
                potential_duplicate_charge=False,
                created_at=now,
            )
        )
        connection.execute(
            insert(contents_table).values(
                id=content_id,
                platform="xiaohongshu",
                external_content_id=external_content_id,
                content_type="image",
                title=title,
                first_seen_at=now,
                last_seen_at=now,
                current_version=1,
                field_observed_at={},
                updated_at=now,
            )
        )
        connection.execute(
            insert(content_versions_table).values(
                id=uuid4(),
                content_id=content_id,
                version_no=1,
                content_type="image",
                title=title,
                provider_attempt_id=attempt_id,
                raw_artifact_id=artifact_id,
                observed_at=now,
            )
        )
        connection.execute(
    insert(content_external_ids_table).values(
        content_id=content_id,
        id_type="note_id",
        external_id=external_content_id,
        provider_attempt_id=attempt_id,
        raw_artifact_id=artifact_id,
        observed_at=now,
    )
)
    return batch_id, content_id


def test_batch_supplement_targets_only_batch_lineage_and_links_run(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id = _seed_config_and_relevance(runtime)
    batch_id, content_id = _insert_import_content(runtime)
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)

    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu",
                    provider_config_id=provider_config_id,
                ),
            ),
            include_comments=True,
            include_sub_comments=True,
        ),
        request_id="stage8e-batch",
    )
    with runtime.database.engine.begin() as connection:
        run = (
            connection.execute(
                select(collection_runs_table).where(collection_runs_table.c.id == created.run_id)
            )
            .mappings()
            .one()
        )
        scope = (
            connection.execute(
                select(collection_scopes_table).where(
                    collection_scopes_table.c.run_id == created.run_id
                )
            )
            .mappings()
            .one()
        )

    assert run["import_batch_id"] == batch_id
    assert scope["source_type"] == "content"
    assert scope["source_value"] == str(content_id)
    assert scope["operation_group"] == "content_enrichment"

    with pytest.raises(CollectionResourceNotFound):
        service.create_run(
            CollectionRunCreateRequest(
                mode="batch_supplement",
                import_batch_id=uuid4(),
                platforms=(
                    CollectionRunPlatformRequest(
                        platform="xiaohongshu",
                        provider_config_id=provider_config_id,
                    ),
                ),
            ),
            request_id="stage8e-missing-batch",
        )
    with pytest.raises(CollectionConflict):
        service.create_run(
            CollectionRunCreateRequest(
                mode="batch_supplement",
                import_batch_id=batch_id,
                platforms=(
                    CollectionRunPlatformRequest(
                        platform="douyin",
                        provider_config_id=provider_config_id,
                    ),
                ),
            ),
            request_id="stage8e-wrong-platform",
        )


def _batch_detail_response(
    *,
    comment_count: int = 0,
    note_id: str = "stage8e-batch-note",
    title: str = "爱玛 Batch 内容已补全",
) -> dict[str, object]:
    body = json.loads(
        (_XIAOHONGSHU_FIXTURES / "image_detail.sanitized.json").read_text(encoding="utf-8")
    )
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
    note["id"] = note_id
    note["title"] = title
    note["desc"] = "爱玛正式 TikHub Detail 补采结果"
    note["comments_count"] = comment_count
    return body


def _batch_comments_response() -> dict[str, object]:
    body = json.loads(
        (_XIAOHONGSHU_FIXTURES / "comments_page1.sanitized.json").read_text(encoding="utf-8")
    )
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)
    comments = page["comments"]
    assert isinstance(comments, list) and comments
    root = comments[0]
    assert isinstance(root, dict)
    root["note_id"] = "stage8e-batch-note"
    root["sub_comment_count"] = 2
    root["sub_comments"] = []
    page["comments"] = [root]
    page["has_more"] = False
    return body


def test_batch_supplement_worker_reuses_detail_mapper_relevance_and_ingestion(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id = _seed_config_and_relevance(runtime)
    batch_id, content_id = _insert_import_content(runtime)
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu",
                    provider_config_id=provider_config_id,
                ),
            ),
            include_comments=False,
            include_sub_comments=False,
        ),
        request_id="stage8e-batch-worker",
    )
    transport = FakeProviderTransport(
        (ProviderTransportResponse(status_code=200, body=_batch_detail_response()),)
    )
    registry = create_collection_job_registry(
        runtime=runtime,
        transport_factory=lambda _config: transport,
        secret_resolver=lambda secret_ref: (
            SecretStr("fixture-secret")
            if secret_ref == "providers/tikhub/stage8e"
            else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
        ),
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=registry,
        worker_id="stage8e-batch-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert worker.run_once() is False
    assert transport.call_count == 1
    assert transport.seen_requests[0].path.endswith("/get_image_note_detail")

    with runtime.database.engine.begin() as connection:
        job = (
            connection.execute(select(jobs_table).where(jobs_table.c.id == created.job_id))
            .mappings()
            .one()
        )
        run = (
            connection.execute(
                select(collection_runs_table).where(collection_runs_table.c.id == created.run_id)
            )
            .mappings()
            .one()
        )
        scope = (
            connection.execute(
                select(collection_scopes_table).where(
                    collection_scopes_table.c.run_id == created.run_id
                )
            )
            .mappings()
            .one()
        )
        content = (
            connection.execute(select(contents_table).where(contents_table.c.id == content_id))
            .mappings()
            .one()
        )
        version_count = connection.scalar(
            select(func.count())
            .select_from(content_versions_table)
            .where(content_versions_table.c.content_id == content_id)
        )

    assert job["status"] == "succeeded"
    assert run["status"] == "succeeded"
    assert scope["status"] == "succeeded"
    assert content["title"] == "爱玛 Batch 内容已补全"
    assert version_count == 2


def test_batch_supplement_rejects_mismatched_existing_content_before_ingestion(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id = _seed_config_and_relevance(runtime)
    batch_id, target_content_id = _insert_import_content(runtime)
    _, other_content_id = _insert_import_content(
        runtime,
        external_content_id="stage8e-other-note",
        title="其他现有内容",
    )
    created = PostgresCollectionHttpService(
        runtime,
        cursor_signing_secret=b"r" * 32,
    ).create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu",
                    provider_config_id=provider_config_id,
                ),
            ),
            include_comments=False,
            include_sub_comments=False,
        ),
        request_id="stage8e-mismatched-detail",
    )
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=200,
                body=_batch_detail_response(
                    note_id="stage8e-other-note",
                    title="爱玛 错误目标被改写",
                ),
            ),
        )
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-mismatched-detail-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True

    with runtime.database.engine.begin() as connection:
        scope_status = connection.scalar(
            select(collection_scopes_table.c.status).where(
                collection_scopes_table.c.run_id == created.run_id
            )
        )
        target_title = connection.scalar(
            select(contents_table.c.title).where(contents_table.c.id == target_content_id)
        )
        other_title = connection.scalar(
            select(contents_table.c.title).where(contents_table.c.id == other_content_id)
        )
        other_version_count = connection.scalar(
            select(func.count())
            .select_from(content_versions_table)
            .where(content_versions_table.c.content_id == other_content_id)
        )

    assert scope_status == "failed"
    assert target_title == "爱玛 Batch 内容"
    assert other_title == "其他现有内容"
    assert other_version_count == 1


def test_batch_supplement_can_fetch_comments_without_sub_comments(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id = _seed_config_and_relevance(runtime)
    batch_id, content_id = _insert_import_content(runtime)
    created = PostgresCollectionHttpService(
        runtime,
        cursor_signing_secret=b"r" * 32,
    ).create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu",
                    provider_config_id=provider_config_id,
                ),
            ),
            include_comments=True,
            include_sub_comments=False,
        ),
        request_id="stage8e-comments-without-replies",
    )
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=200,
                body=_batch_detail_response(comment_count=1),
            ),
            ProviderTransportResponse(status_code=200, body=_batch_comments_response()),
        )
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-comment-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert worker.run_once() is False
    assert [request.path for request in transport.seen_requests] == [
        "/api/v1/xiaohongshu/app_v2/get_image_note_detail",
        "/api/v1/xiaohongshu/app_v2/get_note_comments",
    ]
    with runtime.database.engine.begin() as connection:
        job_status = connection.scalar(
            select(jobs_table.c.status).where(jobs_table.c.id == created.job_id)
        )
        comment_content_id = connection.scalar(select(comments_table.c.content_id))
        coverage = (
            connection.execute(select(comment_thread_coverage_observations_table)).mappings().one()
        )
    assert job_status == "succeeded"
    assert comment_content_id == content_id
    assert coverage["coverage"] == "not_requested"
    assert coverage["stop_reason"] == "sub_comments_disabled"


def test_batch_supplement_retries_provider_5xx_with_new_attempt(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id = _seed_config_and_relevance(runtime)
    batch_id, content_id = _insert_import_content(runtime)
    created = PostgresCollectionHttpService(
        runtime,
        cursor_signing_secret=b"r" * 32,
    ).create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu",
                    provider_config_id=provider_config_id,
                ),
            ),
            include_comments=False,
            include_sub_comments=False,
        ),
        request_id="stage8e-retry",
    )
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(status_code=503, body={"error": "temporary"}),
            ProviderTransportResponse(status_code=200, body=_batch_detail_response()),
        )
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-retry-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert worker.run_once() is True
    assert worker.run_once() is False
    with runtime.database.engine.begin() as connection:
        job = (
            connection.execute(select(jobs_table).where(jobs_table.c.id == created.job_id))
            .mappings()
            .one()
        )
        attempts = tuple(
            connection.execute(
                select(provider_request_attempts_table.c.attempt_no)
                .select_from(
                    provider_request_attempts_table.join(
                        provider_requests_table,
                        provider_request_attempts_table.c.provider_request_id
                        == provider_requests_table.c.id,
                    )
                )
                .where(provider_requests_table.c.provider == "tikhub")
                .order_by(provider_request_attempts_table.c.attempt_no)
            ).scalars()
        )
        version_count = connection.scalar(
            select(func.count())
            .select_from(content_versions_table)
            .where(content_versions_table.c.content_id == content_id)
        )
    assert job["status"] == "succeeded"
    assert job["attempt"] == 2
    assert attempts == (1, 2)
    assert version_count == 2
