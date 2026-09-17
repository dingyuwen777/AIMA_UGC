"""Stage 8E Collection HTTP 编排的 PostgreSQL 18 集成测试。"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection_content import (
    PostgresCollectionContentStateReader,
)
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
from aima_ugc.modules.collection.providers import (
    ProviderTransportFailure,
    ProviderTransportResponse,
)
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
from aima_ugc.modules.ingestion.historical_jobs import HISTORICAL_IMPORT_CHUNK_JOB_TYPE
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
    processing_import_batch_items_table,
)
from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_PAYLOAD_VERSION, IMPORT_JOB_TYPE
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.modules.system.tables import (
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
    provider_configs_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.security import SecretFileError
from aima_ugc.platform.storage.tables import artifacts_table
from pydantic import SecretStr
from sqlalchemy import func, insert, select, update

from tests.integration.stage3_brand_support import stage3_filter_brand_id

_XIAOHONGSHU_FIXTURES = Path("tests/fixtures/providers/tikhub/xiaohongshu")
_DOUYIN_FIXTURES = Path("tests/fixtures/providers/tikhub/douyin")
_TIKHUB_FIXTURES = Path("tests/fixtures/providers/tikhub")


@pytest.fixture
def runtime():  # type: ignore[no-untyped-def]
    value = create_worker_runtime(settings=load_settings())

    def cleanup() -> None:
        with value.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts, "
                "provider_configs, processing_import_batches, historical_import_campaigns "
                "RESTART IDENTITY CASCADE"
            )

    cleanup()
    try:
        yield value
    finally:
        cleanup()
        value.close()


def _seed_config_and_search_pack(runtime) -> tuple[UUID, UUID]:  # type: ignore[no-untyped-def]
    provider_config_id = uuid4()
    pack_id = uuid4()
    keyword_id = uuid4()
    q7_keyword_id = uuid4()
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
            insert(keywords_table).values(
                id=q7_keyword_id,
                text="Q7",
                normalized_text=f"stage8e-q7-{uuid4()}",
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(keyword_pack_items_table).values(
                pack_id=pack_id,
                keyword_id=q7_keyword_id,
                platform_scope="all",
                priority=10,
                enabled=True,
                note="stage8e",
            )
        )
    stage3_filter_brand_id(runtime, alias="爱玛")
    return provider_config_id, pack_id


def test_discovery_run_creation_freezes_inputs_and_commits_job_run_scopes_atomically(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, pack_id = _seed_config_and_search_pack(runtime)
    brand_id = UUID(stage3_filter_brand_id(runtime, alias="爱玛"))
    service = PostgresCollectionHttpService(
        runtime,
        cursor_signing_secret=b"r" * 32,
    )

    capabilities = service.get_capabilities()
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="discovery",
            keyword_pack_ids=(pack_id,),
            brand_ids=(brand_id,),
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
    xiaohongshu = next(item for item in capabilities.capabilities if item.platform == "xiaohongshu")
    assert xiaohongshu.search is not None
    assert xiaohongshu.search.manual_default.model_dump(exclude_none=True) == {
        "sort_mode": "latest",
        "published_within": "1d",
        "content_type": "all",
    }
    assert job["job_type"] == "collection.run.v1"
    assert job["payload"] == {"schema_version": "collection.run.v1"}
    assert job["request_id"] == "stage8e-create"
    assert job["max_attempts"] == 2
    assert run["import_batch_id"] is None
    assert run["trigger_type"] == "api"
    assert run["config_snapshot"]["schema_version"] == "collection-run-config.v2"
    assert run["config_snapshot"]["mode"] == "discovery"
    assert run["config_snapshot"]["keywords"] == ["爱玛", "Q7"]
    assert run["config_snapshot"]["search_snapshot"]["terms"] == ["爱玛", "Q7"]
    assert run["config_snapshot"]["brand_vehicle_filter"]["search_semantics"] == ("keyword_pack")
    assert run["config_snapshot"]["brand_vehicle_filter"]["catalog"]["selected_brand_ids"] == [
        str(brand_id)
    ]
    assert "relevance" not in run["config_snapshot"]
    assert run["config_snapshot"]["include_comments"] is True
    assert run["config_snapshot"]["platforms"][0]["config"] == {
        "sort_mode": "latest",
        "published_within": "1d",
        "content_type": "all",
    }
    assert [scope["source_value"] for scope in scopes] == ["Q7", "爱玛"]
    assert len(scopes) == 2
    assert all(scope["source_type"] == "keyword_search" for scope in scopes)
    assert all(scope["operation_group"] == "content_discovery" for scope in scopes)
    assert detail.run_id == created.run_id
    assert detail.job_id == created.job_id
    assert detail.stage == "queued"
    assert detail.brand_ids == (brand_id,)
    assert len(detail.scopes) == 2


def test_collection_run_rejects_disabled_provider_config(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, pack_id = _seed_config_and_search_pack(runtime)
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
                keyword_pack_ids=(pack_id,),
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


def test_discovery_run_rejects_target_platform_without_keyword_search_term(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    """目标平台不能因词包无适用词而被静默丢弃。"""

    provider_config_id, pack_id = _seed_config_and_search_pack(runtime)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            keyword_pack_items_table.update()
            .where(keyword_pack_items_table.c.pack_id == pack_id)
            .values(platform_scope="xiaohongshu")
        )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)

    with pytest.raises(CollectionConflict, match="目标平台"):
        service.create_run(
            CollectionRunCreateRequest(
                mode="discovery",
                keyword_pack_ids=(pack_id,),
                platforms=(
                    CollectionRunPlatformRequest(
                        platform="douyin",
                        provider_config_id=provider_config_id,
                    ),
                ),
            ),
            request_id="stage4-missing-platform-keyword",
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
    provider_config_id, pack_id = _seed_config_and_search_pack(runtime)
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    collection = service.create_run(
        CollectionRunCreateRequest(
            mode="discovery",
            keyword_pack_ids=(pack_id,),
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
    assert filtered.items[0].keywords == ("爱玛", "Q7")
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
    current_comment_count: int | None = None,
    batch_id: UUID | None = None,
    lookup_id_type: str | None = "note_id",
    lookup_value: str | None = None,
    platform: str = "xiaohongshu",
    content_type: str = "image",
) -> tuple[UUID, UUID]:
    if batch_id is None:
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
                request_fingerprint=uuid4().hex * 2,
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
                platform=platform,
                external_content_id=external_content_id,
                content_type=content_type,
                title=title,
                current_comment_count=current_comment_count,
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
                content_type=content_type,
                title=title,
                provider_attempt_id=attempt_id,
                raw_artifact_id=artifact_id,
                observed_at=now,
            )
        )
        if lookup_id_type is not None:
            connection.execute(
                insert(content_external_ids_table).values(
                    content_id=content_id,
                    id_type=lookup_id_type,
                    external_id=lookup_value or external_content_id,
                    provider_attempt_id=attempt_id,
                    raw_artifact_id=artifact_id,
                    observed_at=now,
                )
            )
    return batch_id, content_id


def _insert_campaign_content(
    runtime,  # type: ignore[no-untyped-def]
    *,
    outcome: str = "unchanged",
) -> tuple[UUID, UUID]:
    batch_id, content_id = _insert_import_content(runtime)
    campaign_id = uuid4()
    source_item_id = uuid4()
    chunk_item_id = uuid4()
    now = datetime.now(UTC)
    manifest_identity = "2" * 64
    with runtime.database.engine.begin() as connection:
        batch_job_id = connection.scalar(
            select(processing_import_batches_table.c.job_id).where(
                processing_import_batches_table.c.id == batch_id
            )
        )
        assert batch_job_id is not None
        connection.execute(
            update(jobs_table)
            .where(jobs_table.c.id == batch_job_id)
            .values(job_type=HISTORICAL_IMPORT_CHUNK_JOB_TYPE)
        )
        connection.execute(
            insert(historical_import_campaigns_table).values(
                id=campaign_id,
                client_idempotency_key=f"stage8e-campaign-{campaign_id}",
                source_kind="local_upload",
                ingestion_policy="standard_observation",
                declared_file_count=1,
                root_relative_path="campaign.xlsx",
                recursive=False,
                profile_snapshot={"schema_version": "stage8e-test"},
                keyword_pack_snapshot={},
                status="succeeded",
                discovered_file_count=1,
                ready_item_count=1,
                total_rows=1,
                stats={outcome: 1},
                created_at=now,
                started_at=now,
                finished_at=now,
            )
        )
        connection.execute(
            insert(historical_import_campaign_items_table),
            [
                {
                    "id": source_item_id,
                    "campaign_id": campaign_id,
                    "parent_item_id": None,
                    "item_kind": "source_file",
                    "relative_path": "campaign.xlsx",
                    "manifest_identity": manifest_identity,
                    "ordinal": None,
                    "row_count": 1,
                    "status": "succeeded",
                    "created_at": now,
                    "started_at": now,
                    "finished_at": now,
                },
                {
                    "id": chunk_item_id,
                    "campaign_id": campaign_id,
                    "parent_item_id": source_item_id,
                    "item_kind": "chunk",
                    "relative_path": "campaign.xlsx",
                    "manifest_identity": manifest_identity,
                    "ordinal": 0,
                    "row_start": 1,
                    "row_end": 1,
                    "row_count": 1,
                    "status": "succeeded",
                    "created_at": now,
                    "started_at": now,
                    "finished_at": now,
                },
            ],
        )
        connection.execute(
            insert(processing_import_batch_items_table).values(
                id=uuid4(),
                batch_id=batch_id,
                campaign_item_id=chunk_item_id,
                source_row_ordinal=1,
                platform="xiaohongshu",
                external_content_id_hash="3" * 64,
                content_id=content_id,
                outcome=outcome,
                committed_chunk_ordinal=0,
                created_at=now,
            )
        )
    return campaign_id, content_id


def test_campaign_runtime_projection_and_summary_use_campaign_parent_once(runtime) -> None:  # type: ignore[no-untyped-def]
    _seed_config_and_search_pack(runtime)
    campaign_id, _ = _insert_campaign_content(runtime, outcome="updated")
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)

    listing = service.list_runtime_runs(
        CollectionRuntimeListQuery(record_types=("data_import_campaign",))
    )
    summary = service.get_runtime_summary()

    assert len(listing.items) == 1
    item = listing.items[0]
    assert item.record_id == campaign_id
    assert item.data_import_campaign_id == campaign_id
    assert item.job_id is None
    assert item.record_type == "data_import_campaign"
    assert item.status == "succeeded"
    assert item.progress == 100
    assert item.import_stats is not None
    assert item.import_stats.rows_seen == 1
    assert item.import_stats.rows_ingested == 1
    assert summary.completed_today_count == 1
    assert summary.contents_ingested_today == 1


def test_ready_campaign_is_reported_as_queued_and_processing(runtime) -> None:  # type: ignore[no-untyped-def]
    _seed_config_and_search_pack(runtime)
    campaign_id, _ = _insert_campaign_content(runtime)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(historical_import_campaigns_table)
            .where(historical_import_campaigns_table.c.id == campaign_id)
            .values(status="ready", finished_at=None)
        )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)

    listing = service.list_runtime_runs(
        CollectionRuntimeListQuery(record_types=("data_import_campaign",))
    )
    summary = service.get_runtime_summary()

    assert len(listing.items) == 1
    assert listing.items[0].status == "queued"
    assert listing.items[0].progress == 100
    assert summary.processing_count == 1


def test_campaign_unchanged_ledger_is_eligible_and_persisted_as_run_source(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    campaign_id, content_id = _insert_campaign_content(runtime)
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)

    eligibility = service.get_campaign_supplement_eligibility(campaign_id)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            data_import_campaign_id=campaign_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu",
                    provider_config_id=provider_config_id,
                ),
            ),
            include_comments=False,
            include_sub_comments=False,
        ),
        request_id="stage8e-campaign-supplement",
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

    assert [(item.platform, item.target_count) for item in eligibility.targets] == [
        ("xiaohongshu", 1)
    ]
    assert created.data_import_campaign_id == campaign_id
    assert created.import_batch_id is None
    assert run["data_import_campaign_id"] == campaign_id
    assert run["import_batch_id"] is None
    assert scope["source_value"] == str(content_id)


def test_running_campaign_cannot_be_used_as_supplement_source(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    campaign_id, _ = _insert_campaign_content(runtime)
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(historical_import_campaigns_table)
            .where(historical_import_campaigns_table.c.id == campaign_id)
            .values(status="running")
        )

    with pytest.raises(CollectionConflict):
        service.get_campaign_supplement_eligibility(campaign_id)
    with pytest.raises(CollectionConflict):
        service.create_run(
            CollectionRunCreateRequest(
                mode="batch_supplement",
                data_import_campaign_id=campaign_id,
                platforms=(
                    CollectionRunPlatformRequest(
                        platform="xiaohongshu",
                        provider_config_id=provider_config_id,
                    ),
                ),
            ),
            request_id="stage8e-running-campaign",
        )


def test_batch_supplement_targets_only_batch_lineage_and_links_run(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
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


def test_batch_supplement_worker_reuses_detail_mapper_and_ingestion_without_refiltering(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
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


@pytest.mark.parametrize(
    ("platform", "lookup_id_type", "lookup_value"),
    [
        ("xiaohongshu", "note_id", "xhs-note-1"),
        ("douyin", "aweme_id", "100001"),
        ("weibo", "status_id", "100001"),
        ("bilibili", "av_id", "100010"),
        ("kuaishou", "photo_id", "100003"),
    ],
)
def test_batch_supplement_native_ids_reach_worker_and_persist_platform_comments(
    runtime, platform: str, lookup_id_type: str, lookup_value: str
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, content_id = _insert_import_content(
        runtime,
        platform=platform,
        external_content_id=lookup_value,
        lookup_id_type=lookup_id_type,
    )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    eligibility = service.get_batch_supplement_eligibility(batch_id)
    assert [(item.platform, item.target_count) for item in eligibility.targets] == [(platform, 1)]
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform=platform,
                    provider_config_id=provider_config_id,
                ),
            ),
            include_comments=True,
            include_sub_comments=False,
        ),
        request_id=f"stage8e-native-{platform}",
    )
    body = json.loads(
        (_TIKHUB_FIXTURES / platform / "comments_page1.sanitized.json").read_text(
            encoding="utf-8"
        )
    )
    detail_name = (
        "image_detail.sanitized.json"
        if platform == "xiaohongshu"
        else "detail.sanitized.json"
    )
    detail = json.loads((_TIKHUB_FIXTURES / platform / detail_name).read_text(encoding="utf-8"))
    if platform == "xiaohongshu":
        detail["data"]["data"][0]["note_list"][0]["id"] = lookup_value
        detail["data"]["data"][0]["note_list"][0]["comments_count"] = 2
        body["data"]["data"]["comment_count"] = 2
        body["data"]["data"]["comment_count_l1"] = 2
    elif platform == "douyin":
        detail["data"]["aweme_detail"]["aweme_id"] = lookup_value
        detail["data"]["aweme_detail"]["statistics"]["comment_count"] = 2
        body["data"]["comments"][0]["aweme_id"] = lookup_value
    elif platform == "weibo":
        detail["data"]["detailInfo"]["status"]["idstr"] = lookup_value
        detail["data"]["detailInfo"]["status"]["id"] = int(lookup_value)
        detail["data"]["detailInfo"]["status"]["comments_count"] = 2
    elif platform == "bilibili":
        detail["data"]["data"]["aid"] = int(lookup_value)
        detail["data"]["data"]["stat"]["aid"] = int(lookup_value)
        detail["data"]["data"]["stat"]["reply"] = 2
        body["data"]["data"]["cursor"]["pagination_reply"]["next_offset"] = 1
    else:
        detail["data"]["photos"][0]["photo_id"] = int(lookup_value)
        detail["data"]["photos"][0]["comment_count"] = 2
    final_comments_page = deepcopy(body)
    if platform == "xiaohongshu":
        final_comments_page["data"]["data"]["comments"][0]["id"] = "xhs-comment-root-2"
        final_comments_page["data"]["data"]["cursor"] = "cursor-end"
        final_comments_page["data"]["data"]["has_more"] = False
    elif platform == "douyin":
        final_comments_page["data"]["comments"][0]["cid"] = "douyin-comment-root-2"
        final_comments_page["data"]["has_more"] = 0
    elif platform == "weibo":
        second_root = final_comments_page["data"]["items"][0]["data"]
        second_root.update(
            id=100004,
            idstr="weibo-comment-root-2",
            mid="weibo-comment-root-2",
            rootid=100004,
            rootidstr="weibo-comment-root-2",
        )
        final_comments_page["data"].pop("moreInfo")
    elif platform == "bilibili":
        second_root = final_comments_page["data"]["data"]["replies"][0]
        second_root.update(rpid=100012, rpid_str="bili-comment-root-2")
        final_comments_page["data"]["data"]["cursor"]["is_end"] = True
    else:
        final_comments_page["data"]["rootComments"][0]["comment_id"] = 100005
        final_comments_page["data"]["pcursor"] = "cursor-second"
    responses = [
        ProviderTransportResponse(status_code=200, body=detail),
        ProviderTransportResponse(status_code=200, body=body),
        ProviderTransportResponse(status_code=200, body=final_comments_page),
    ]
    if platform == "kuaishou":
        responses.append(
            ProviderTransportResponse(
                status_code=200,
                body={"data": {"result": 1, "rootComments": [], "pcursor": ""}},
            )
        )
    transport = FakeProviderTransport(tuple(responses))
    registry = create_collection_job_registry(
        runtime=runtime,
        transport_factory=lambda _config: transport,
        secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=registry,
        worker_id=f"stage8e-native-{platform}",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    run = service.get_run(created.run_id)
    with runtime.database.engine.begin() as connection:
        scope_outcomes = connection.execute(
            select(collection_scopes_table.c.status, collection_scopes_table.c.stop_reason).where(
                collection_scopes_table.c.run_id == created.run_id
            )
        ).all()
    assert run.status == "succeeded", (scope_outcomes, run.scopes[0], transport.call_count)
    assert transport.seen_requests[0].params
    with runtime.database.engine.begin() as connection:
        comments = connection.execute(
            select(comments_table).where(comments_table.c.content_id == content_id)
        ).mappings().all()
        assert sum(
            comment["root_comment_id"] == comment["external_comment_id"]
            and comment["parent_comment_id"] is None
            for comment in comments
        ) == 2
        content_platform = connection.scalar(
            select(contents_table.c.platform).where(contents_table.c.id == content_id)
        )
        assert content_platform == platform
        attempts = connection.scalar(
            select(func.count())
            .select_from(provider_request_attempts_table.join(provider_requests_table))
            .where(provider_requests_table.c.scope_id.in_(
                select(collection_scopes_table.c.id).where(
                    collection_scopes_table.c.run_id == created.run_id
                )
            ))
        )
        assert attempts == len(responses)


@pytest.mark.parametrize(
    ("platform", "lookup_id_type", "lookup_value", "reply_file"),
    [
        ("xiaohongshu", "note_id", "xhs-note-1", "sub_comments_page1.sanitized.json"),
        ("douyin", "aweme_id", "100001", "replies_page1.sanitized.json"),
        ("weibo", "status_id", "100001", "sub_comments_page1.sanitized.json"),
        ("bilibili", "av_id", "100010", "replies_page1.sanitized.json"),
        ("kuaishou", "photo_id", "100003", "sub_comments_page1.sanitized.json"),
    ],
)
def test_batch_supplement_native_ids_persist_replies_under_their_root(
    runtime, platform: str, lookup_id_type: str, lookup_value: str, reply_file: str
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, content_id = _insert_import_content(
        runtime,
        platform=platform,
        external_content_id=lookup_value,
        lookup_id_type=lookup_id_type,
    )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform=platform,
                    provider_config_id=provider_config_id,
                ),
            ),
            include_comments=True,
            include_sub_comments=True,
        ),
        request_id=f"stage8e-native-reply-{platform}",
    )
    fixture_dir = _TIKHUB_FIXTURES / platform
    detail_file = (
        "image_detail.sanitized.json"
        if platform == "xiaohongshu"
        else "detail.sanitized.json"
    )
    detail = json.loads((fixture_dir / detail_file).read_text(encoding="utf-8"))
    roots = json.loads((fixture_dir / "comments_page1.sanitized.json").read_text(encoding="utf-8"))
    replies = json.loads((fixture_dir / reply_file).read_text(encoding="utf-8"))
    if platform == "xiaohongshu":
        note = detail["data"]["data"][0]["note_list"][0]
        note.update(id=lookup_value, comments_count=1)
        page = roots["data"]["data"]
        page.update(has_more=False, comment_count=1, comment_count_l1=1)
        root = page["comments"][0]
        root.update(sub_comment_count=1, sub_comments=[])
        replies["data"]["data"]["has_more"] = False
    elif platform == "douyin":
        video = detail["data"]["aweme_detail"]
        video["aweme_id"] = lookup_value
        video["statistics"]["comment_count"] = 1
        root = roots["data"]["comments"][0]
        root.update(aweme_id=lookup_value, reply_comment_total=1)
        roots["data"]["has_more"] = 0
        reply = replies["data"]["comments"][0]
        reply.update(aweme_id=lookup_value, reply_to_reply_id="0")
        replies["data"]["has_more"] = 0
    elif platform == "weibo":
        status = detail["data"]["detailInfo"]["status"]
        status.update(id=int(lookup_value), idstr=lookup_value, comments_count=1)
        root = roots["data"]["items"][0]["data"]
        root["total_number"] = 1
        roots["data"].pop("moreInfo")
        replies["data"]["max_id"] = 0
    elif platform == "bilibili":
        video = detail["data"]["data"]
        video["aid"] = int(lookup_value)
        video["stat"].update(aid=int(lookup_value), reply=1)
        root = roots["data"]["data"]["replies"][0]
        root["rcount"] = 1
        roots["data"]["data"]["cursor"]["is_end"] = True
        replies["data"]["data"]["root"]["rcount"] = 1
        replies["data"]["data"]["cursor"]["is_end"] = True
    else:
        photo = detail["data"]["photos"][0]
        photo.update(photo_id=int(lookup_value), comment_count=1)
        root = roots["data"]["rootComments"][0]
        root["subCommentCount"] = 2
        for offset, reply in enumerate(replies["data"]["subComments"]):
            reply["comment_id"] = 100006 + offset
    root_id = str(
        root.get("idstr")
        or root.get("rpid_str")
        or root.get("id")
        or root.get("cid")
        or root.get("comment_id")
    )
    responses = [
        ProviderTransportResponse(status_code=200, body=detail),
        ProviderTransportResponse(status_code=200, body=roots),
        ProviderTransportResponse(status_code=200, body=replies),
    ]
    if platform == "kuaishou":
        responses.extend(
            [
                ProviderTransportResponse(
                    status_code=200,
                    body={"data": {"result": 1, "subComments": [], "pcursor": ""}},
                ),
                ProviderTransportResponse(
                    status_code=200,
                    body={"data": {"result": 1, "rootComments": [], "pcursor": ""}},
                ),
            ]
        )
    observed_stages: list[tuple[str | None, int]] = []

    class ObservingTransport(FakeProviderTransport):
        def send(self, request):  # type: ignore[no-untyped-def]
            if self.call_count in (1, 2):
                current = service.get_run(created.run_id).scopes[0]
                observed_stages.append(
                    (current.comment_stage, current.stats.root_comment_count)
                )
            return super().send(request)

    transport = ObservingTransport(tuple(responses))
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id=f"stage8e-native-reply-{platform}",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    run = service.get_run(created.run_id)
    assert run.status == "succeeded", (run.scopes[0].stop_reason, transport.call_count)
    assert run.scopes[0].comment_coverage == "complete"
    assert run.scopes[0].identity_status == "resolved"
    assert run.scopes[0].comment_stage == "finished"
    assert run.scopes[0].stats.root_comment_count == 1
    assert run.scopes[0].stats.reply_count == (2 if platform == "kuaishou" else 1)
    assert observed_stages == [("roots", 0), ("replies", 1)]
    with runtime.database.engine.begin() as connection:
        comments = connection.execute(
            select(comments_table).where(comments_table.c.content_id == content_id)
        ).mappings().all()
        thread_coverage = connection.execute(
            select(comment_thread_coverage_observations_table).where(
                comment_thread_coverage_observations_table.c.content_id == content_id,
                comment_thread_coverage_observations_table.c.root_comment_id == root_id,
            )
        ).mappings().one()
    assert any(
        item["external_comment_id"] == root_id and item["parent_comment_id"] is None
        for item in comments
    )
    assert any(
        item["root_comment_id"] == root_id and item["external_comment_id"] != root_id
        for item in comments
    )
    assert thread_coverage["coverage"] == "complete"
    assert thread_coverage["captured_count"] == (2 if platform == "kuaishou" else 1)
    assert transport.call_count == len(responses)


@pytest.mark.parametrize(
    ("platform", "lookup_id_type", "lookup_value"),
    [
        ("xiaohongshu", "note_id", "xhs-note-1"),
        ("douyin", "aweme_id", "100001"),
        ("weibo", "status_id", "100001"),
        ("bilibili", "av_id", "100010"),
        ("kuaishou", "photo_id", "100003"),
    ],
)
def test_batch_supplement_native_id_comment_retry_reuses_detail_raw(
    runtime, platform: str, lookup_id_type: str, lookup_value: str
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, content_id = _insert_import_content(
        runtime,
        platform=platform,
        external_content_id=lookup_value,
        lookup_id_type=lookup_id_type,
    )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform=platform,
                    provider_config_id=provider_config_id,
                ),
            ),
            include_comments=True,
            include_sub_comments=False,
        ),
        request_id=f"stage8e-native-retry-{platform}",
    )
    fixture_dir = _TIKHUB_FIXTURES / platform
    detail_file = (
        "image_detail.sanitized.json"
        if platform == "xiaohongshu"
        else "detail.sanitized.json"
    )
    detail = json.loads((fixture_dir / detail_file).read_text(encoding="utf-8"))
    comments = json.loads(
        (fixture_dir / "comments_page1.sanitized.json").read_text(encoding="utf-8")
    )
    if platform == "xiaohongshu":
        note = detail["data"]["data"][0]["note_list"][0]
        note.update(id=lookup_value, comments_count=1)
        comments["data"]["data"].update(
            comment_count=1, comment_count_l1=1, has_more=False
        )
    elif platform == "douyin":
        video = detail["data"]["aweme_detail"]
        video["aweme_id"] = lookup_value
        video["statistics"]["comment_count"] = 1
        comments["data"]["comments"][0]["aweme_id"] = lookup_value
        comments["data"]["has_more"] = 0
    elif platform == "weibo":
        status = detail["data"]["detailInfo"]["status"]
        status.update(id=int(lookup_value), idstr=lookup_value, comments_count=1)
        comments["data"].pop("moreInfo")
    elif platform == "bilibili":
        video = detail["data"]["data"]
        video["aid"] = int(lookup_value)
        video["stat"].update(aid=int(lookup_value), reply=1)
        comments["data"]["data"]["cursor"]["is_end"] = True
    else:
        detail["data"]["photos"][0].update(
            photo_id=int(lookup_value), comment_count=1
        )
    responses = [
        ProviderTransportResponse(status_code=200, body=detail),
        ProviderTransportResponse(status_code=503, body={"error": "temporary"}),
        ProviderTransportResponse(status_code=200, body=comments),
    ]
    if platform == "kuaishou":
        responses.append(
            ProviderTransportResponse(
                status_code=200,
                body={"data": {"result": 1, "rootComments": [], "pcursor": ""}},
            )
        )
    transport = FakeProviderTransport(tuple(responses))
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id=f"stage8e-native-retry-{platform}",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert worker.run_once() is True
    assert worker.run_once() is False
    assert service.get_run(created.run_id).status == "succeeded"
    assert transport.call_count == len(responses)
    assert transport.seen_requests[1].params == transport.seen_requests[2].params
    with runtime.database.engine.begin() as connection:
        persisted = connection.scalar(
            select(func.count())
            .select_from(comments_table)
            .where(comments_table.c.content_id == content_id)
        )
        details = connection.scalar(
            select(func.count())
            .select_from(provider_requests_table)
            .where(
                provider_requests_table.c.operation
                == transport.seen_requests[0].path.rsplit("/", 1)[-1],
            )
        )
    assert persisted >= 1
    assert details == 1


def test_batch_supplement_resumes_second_comment_page_without_refetching_first(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, content_id = _insert_import_content(
        runtime,
        external_content_id="xhs-note-1",
        lookup_id_type="note_id",
    )
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
            include_sub_comments=False,
        ),
        request_id="stage8e-second-page-retry",
    )
    detail = _batch_detail_response()
    detail["data"]["data"][0]["note_list"][0]["id"] = "xhs-note-1"
    detail["data"]["data"][0]["note_list"][0]["comments_count"] = 2
    first = json.loads(
        (_TIKHUB_FIXTURES / "xiaohongshu" / "comments_page1.sanitized.json").read_text(
            encoding="utf-8"
        )
    )
    first["data"]["data"].update(comment_count=2, comment_count_l1=2)
    second = deepcopy(first)
    second["data"]["data"]["comments"][0]["id"] = "xhs-comment-root-2"
    second["data"]["data"].update(cursor="cursor-end", has_more=False)
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(status_code=200, body=detail),
            ProviderTransportResponse(status_code=200, body=first),
            ProviderTransportResponse(status_code=503, body={"error": "temporary"}),
            ProviderTransportResponse(status_code=200, body=second),
        )
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-second-page-retry-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert worker.run_once() is True
    assert service.get_run(created.run_id).status == "succeeded"
    assert transport.call_count == 4
    assert transport.seen_requests[2].params == transport.seen_requests[3].params
    with runtime.database.engine.begin() as connection:
        roots = connection.scalar(
            select(func.count())
            .select_from(comments_table)
            .where(
                comments_table.c.content_id == content_id,
                comments_table.c.parent_comment_id.is_(None),
            )
        )
    assert roots == 2


def test_batch_supplement_resolves_xhs_shortlink_and_keeps_import_content_identity(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    shortlink = "https://xhslink.com/o/8fCmVEVQWmp"
    batch_id, content_id = _insert_import_content(
        runtime,
        external_content_id="url_sha256:shortlink-source",
        lookup_id_type="share_text",
        lookup_value=shortlink,
    )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu", provider_config_id=provider_config_id
                ),
            ),
            include_comments=True,
            include_sub_comments=False,
        ),
        request_id="stage8e-shortlink-resolution",
    )
    comments = _batch_comments_response()
    page = comments["data"]["data"]
    page["comments"][0]["sub_comment_count"] = 0
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=200,
                body=_batch_detail_response(comment_count=1),
            ),
            ProviderTransportResponse(status_code=200, body=comments),
        )
    )
    registry = create_collection_job_registry(
        runtime=runtime,
        transport_factory=lambda _config: transport,
        secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=registry,
        worker_id="stage8e-shortlink-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert transport.call_count == 2
    assert transport.seen_requests[0].params == {"share_text": shortlink}
    assert transport.seen_requests[1].params["note_id"] == "stage8e-batch-note"
    run = service.get_run(created.run_id)
    assert run.status == "succeeded"
    with runtime.database.engine.begin() as connection:
        content = (
            connection.execute(select(contents_table).where(contents_table.c.id == content_id))
            .mappings()
            .one()
        )
        note_id = (
            connection.execute(
                select(content_external_ids_table).where(
                    content_external_ids_table.c.content_id == content_id,
                    content_external_ids_table.c.id_type == "note_id",
                )
            )
            .mappings()
            .one()
        )
        stored_comment_count = connection.scalar(
            select(func.count())
            .select_from(comments_table)
            .where(comments_table.c.content_id == content_id)
        )
    assert content["external_content_id"] == "url_sha256:shortlink-source"
    assert note_id["external_id"] == "stage8e-batch-note"
    assert note_id["provider_attempt_id"] is not None
    assert note_id["raw_artifact_id"] is not None
    assert stored_comment_count == 1


def test_batch_supplement_resolves_douyin_shortlink_before_comments(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    shortlink = "https://v.douyin.com/e3x2fjE/"
    aweme_id = "7675702103746898533"
    batch_id, content_id = _insert_import_content(
        runtime,
        external_content_id="url_sha256:douyin-share-source",
        lookup_id_type="douyin_share_url",
        lookup_value=shortlink,
        platform="douyin",
        content_type="video",
    )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="douyin", provider_config_id=provider_config_id
                ),
            ),
            include_comments=True,
            include_sub_comments=False,
        ),
        request_id="stage8e-douyin-share-resolution",
    )
    detail = json.loads((_DOUYIN_FIXTURES / "detail.sanitized.json").read_text(encoding="utf-8"))
    detail["data"]["aweme_detail"]["aweme_id"] = aweme_id
    detail["data"]["aweme_detail"]["desc"] = "爱玛分享短链内容"
    detail["data"]["aweme_detail"]["statistics"]["comment_count"] = 1
    comments = json.loads(
        (_DOUYIN_FIXTURES / "comments_page1.sanitized.json").read_text(encoding="utf-8")
    )
    comments["data"]["comments"] = [comments["data"]["comments"][0]]
    comments["data"]["comments"][0]["aweme_id"] = aweme_id
    comments["data"]["comments"][0]["reply_comment_total"] = 0
    comments["data"]["total"] = 1
    comments["data"]["has_more"] = 0
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(status_code=200, body=detail),
            ProviderTransportResponse(status_code=200, body=comments),
        )
    )
    registry = create_collection_job_registry(
        runtime=runtime,
        transport_factory=lambda _config: transport,
        secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=registry,
        worker_id="stage8e-douyin-share-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert transport.call_count == 2
    assert transport.seen_requests[0].params == {"share_url": shortlink}
    assert transport.seen_requests[1].params["aweme_id"] == aweme_id
    run = service.get_run(created.run_id)
    assert run.status == "succeeded"
    with runtime.database.engine.begin() as connection:
        content = (
            connection.execute(select(contents_table).where(contents_table.c.id == content_id))
            .mappings()
            .one()
        )
        stored_aweme_id = (
            connection.execute(
                select(content_external_ids_table).where(
                    content_external_ids_table.c.content_id == content_id,
                    content_external_ids_table.c.id_type == "aweme_id",
                )
            )
            .mappings()
            .one()
        )
        stored_comment_count = connection.scalar(
            select(func.count())
            .select_from(comments_table)
            .where(comments_table.c.content_id == content_id)
        )
    assert content["external_content_id"] == "url_sha256:douyin-share-source"
    assert stored_aweme_id["external_id"] == aweme_id
    assert stored_aweme_id["provider_attempt_id"] is not None
    assert stored_aweme_id["raw_artifact_id"] is not None
    assert stored_comment_count == 1


def test_batch_supplement_reuses_shortlink_resolution_after_comment_retry(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    shortlink = "https://xhslink.com/o/8fCmVEVQWmp"
    batch_id, content_id = _insert_import_content(
        runtime,
        external_content_id="url_sha256:retry-share-source",
        lookup_id_type="share_text",
        lookup_value=shortlink,
    )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu", provider_config_id=provider_config_id
                ),
            ),
            include_comments=True,
            include_sub_comments=False,
        ),
        request_id="stage8e-shortlink-comment-retry",
    )
    comments = _batch_comments_response()
    comments["data"]["data"]["comments"][0]["sub_comment_count"] = 0
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=200, body=_batch_detail_response(comment_count=1)
            ),
            ProviderTransportResponse(status_code=503, body={"error": "temporary"}),
            ProviderTransportResponse(status_code=200, body=comments),
        )
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-shortlink-retry-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert worker.run_once() is True
    assert worker.run_once() is False
    assert transport.call_count == 3
    assert transport.seen_requests[0].params == {"share_text": shortlink}
    assert transport.seen_requests[1].params == transport.seen_requests[2].params
    assert transport.seen_requests[1].params["note_id"] == "stage8e-batch-note"
    assert service.get_run(created.run_id).status == "succeeded"
    with runtime.database.engine.begin() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(comments_table)
                .where(comments_table.c.content_id == content_id)
            )
            == 1
        )


def test_batch_supplement_reports_unavailable_when_shortlink_detail_is_empty(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, content_id = _insert_import_content(
        runtime,
        external_content_id="url_sha256:empty-share-source",
        lookup_id_type="share_text",
        lookup_value="https://xhslink.com/o/8fCmVEVQWmp",
    )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu", provider_config_id=provider_config_id
                ),
            ),
            include_comments=True,
            include_sub_comments=False,
        ),
        request_id="stage8e-empty-shortlink-detail",
    )
    transport = FakeProviderTransport(
        (ProviderTransportResponse(status_code=200, body={"code": 200, "data": {"data": []}}),)
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-empty-shortlink-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert transport.call_count == 1
    run = service.get_run(created.run_id)
    assert run.status == "failed"
    assert run.scopes[0].stop_reason == "identity_unavailable"
    with runtime.database.engine.begin() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(content_external_ids_table)
                .where(
                    content_external_ids_table.c.content_id == content_id,
                    content_external_ids_table.c.id_type == "note_id",
                )
            )
            == 0
        )


def test_batch_supplement_blocks_ambiguous_shortlink_without_comment_request(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, content_id = _insert_import_content(
        runtime,
        external_content_id="url_sha256:ambiguous-share-source",
        lookup_id_type="share_text",
        lookup_value="https://xhslink.com/o/8fCmVEVQWmp",
    )
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
        request_id="stage8e-ambiguous-shortlink",
    )
    detail = _batch_detail_response()
    first_note = detail["data"]["data"][0]["note_list"][0]
    other_note = deepcopy(first_note)
    other_note["id"] = "different-note"
    detail["data"]["data"][0]["note_list"].append(other_note)
    transport = FakeProviderTransport(
        (ProviderTransportResponse(status_code=200, body=detail),)
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-ambiguous-shortlink-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    run = service.get_run(created.run_id)
    assert run.status == "failed"
    assert run.scopes[0].stop_reason == "identity_ambiguous"
    assert run.scopes[0].identity_status == "ambiguous"
    assert transport.call_count == 1
    with runtime.database.engine.begin() as connection:
        assert connection.scalar(
            select(func.count())
            .select_from(comments_table)
            .where(comments_table.c.content_id == content_id)
        ) == 0
        attempt = connection.execute(
            select(provider_request_attempts_table)
            .select_from(provider_request_attempts_table.join(provider_requests_table))
            .where(provider_requests_table.c.scope_id == run.scopes[0].id)
        ).mappings().one()
    assert attempt["raw_artifact_id"] is not None


@pytest.mark.parametrize("bypass_early_check", [False, True])
def test_batch_supplement_shortlink_identity_owned_by_other_content_is_blocked(
    runtime, monkeypatch, bypass_early_check: bool,
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, source_content_id = _insert_import_content(
        runtime,
        external_content_id="url_sha256:conflicting-share-source",
        lookup_id_type="share_text",
        lookup_value="https://xhslink.com/o/8fCmVEVQWmp",
    )
    _, other_content_id = _insert_import_content(
        runtime,
        external_content_id="xhs-note-1",
        lookup_id_type="note_id",
        lookup_value="xhs-note-1",
    )
    if bypass_early_check:
        monkeypatch.setattr(
            PostgresCollectionContentStateReader,
            "lookup_identity_owned_by_other_content",
            lambda *args, **kwargs: False,
        )
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
            include_sub_comments=False,
        ),
        request_id="stage8e-conflicting-shortlink",
    )
    detail = _batch_detail_response(note_id="xhs-note-1")
    detail["data"]["data"][0]["note_list"][0]["comments_count"] = 1
    transport = FakeProviderTransport(
        (ProviderTransportResponse(status_code=200, body=detail),)
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-conflicting-shortlink-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    run = service.get_run(created.run_id)
    assert run.status == "failed"
    assert run.scopes[0].stop_reason == "identity_conflict"
    assert run.scopes[0].comment_coverage == "unavailable"
    assert run.scopes[0].identity_status == "conflict"
    assert transport.call_count == 1
    with runtime.database.engine.begin() as connection:
        assert connection.scalar(
            select(func.count())
            .select_from(comments_table)
            .where(comments_table.c.content_id.in_((source_content_id, other_content_id)))
        ) == 0
        conflicting_ids = connection.scalar(
            select(func.count())
            .select_from(content_external_ids_table)
            .where(
                content_external_ids_table.c.content_id == source_content_id,
                content_external_ids_table.c.id_type == "note_id",
            )
        )
    assert conflicting_ids == 0


def test_batch_supplement_shortlink_unknown_delivery_keeps_auditable_attempt(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, content_id = _insert_import_content(
        runtime,
        external_content_id="url_sha256:unknown-share-source",
        lookup_id_type="share_text",
        lookup_value="https://xhslink.com/o/8fCmVEVQWmp",
    )
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
            include_sub_comments=False,
        ),
        request_id="stage8e-unknown-shortlink",
    )
    detail = _batch_detail_response()
    detail["data"]["data"][0]["note_list"][0]["comments_count"] = 0
    transport = FakeProviderTransport(
        (
            ProviderTransportFailure.unknown(
                code="connection_closed", safe_summary="发送结果未知"
            ),
            ProviderTransportResponse(status_code=200, body=detail),
        )
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-unknown-shortlink-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert worker.run_once() is True
    assert transport.call_count == 2
    assert service.get_run(created.run_id).status == "succeeded"
    with runtime.database.engine.begin() as connection:
        attempts = connection.execute(
            select(provider_request_attempts_table)
            .select_from(provider_request_attempts_table.join(provider_requests_table))
            .where(
                provider_requests_table.c.scope_id
                == service.get_run(created.run_id).scopes[0].id
            )
            .order_by(provider_request_attempts_table.c.attempt_no)
        ).mappings().all()
        typed_count = connection.scalar(
            select(func.count())
            .select_from(content_external_ids_table)
            .where(
                content_external_ids_table.c.content_id == content_id,
                content_external_ids_table.c.id_type == "note_id",
            )
        )
    assert len(attempts) == 2
    assert attempts[0]["dispatch_status"] == "unknown"
    assert attempts[0]["billing_status"] == "unknown"
    assert attempts[1]["raw_artifact_id"] is not None
    assert typed_count == 1


def test_batch_supplement_persists_safe_error_when_provider_secret_is_unavailable(
    runtime,  # type: ignore[no-untyped-def]
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, _ = _insert_import_content(runtime)
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
        request_id="stage8e-provider-secret-unavailable",
    )
    transport = FakeProviderTransport(())

    def unavailable_secret(_secret_ref: str) -> SecretStr:
        """模拟 Worker 无法读取 Provider Secret，且不向测试日志暴露路径。"""

        raise SecretFileError("providers/tikhub/test-secret-should-not-leak")

    registry = create_collection_job_registry(
        runtime=runtime,
        transport_factory=lambda _config: transport,
        secret_resolver=unavailable_secret,
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=registry,
        worker_id="stage8e-provider-secret-unavailable-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert worker.run_once() is False
    assert transport.call_count == 0

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

    assert job["status"] == "failed"
    assert job["error_code"] == "collection_run_failed"
    assert run["status"] == "failed"
    assert run["error_summary"] == "provider_secret_unavailable"
    assert scope["status"] == "failed"
    assert scope["stop_reason"] == "provider_secret_unavailable"
    response = service.get_run(created.run_id)
    assert response.error_summary == "provider_secret_unavailable"
    assert response.scopes[0].stop_reason == "provider_secret_unavailable"
    assert "providers/tikhub/test-secret-should-not-leak" not in caplog.text


def test_batch_supplement_rejects_mismatched_existing_content_before_ingestion(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
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
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, content_id = _insert_import_content(runtime, current_comment_count=1)
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


def test_batch_supplement_reply_shortfall_is_partial_in_run_and_coverage(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, content_id = _insert_import_content(runtime, current_comment_count=1)
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu", provider_config_id=provider_config_id
                ),
            ),
            include_comments=True,
            include_sub_comments=True,
        ),
        request_id="stage8e-reply-shortfall",
    )
    replies = json.loads(
        (_XIAOHONGSHU_FIXTURES / "sub_comments_page1.sanitized.json").read_text(encoding="utf-8")
    )
    replies["data"]["data"]["comments"][0]["note_id"] = "stage8e-batch-note"
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=200, body=_batch_detail_response(comment_count=1)
            ),
            ProviderTransportResponse(status_code=200, body=_batch_comments_response()),
            ProviderTransportResponse(status_code=200, body=replies),
        )
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-reply-shortfall-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert transport.call_count == 3
    with runtime.database.engine.begin() as connection:
        thread = (
            connection.execute(select(comment_thread_coverage_observations_table)).mappings().one()
        )
    run = service.get_run(created.run_id)
    assert thread["content_id"] == content_id
    assert thread["coverage"] == "partial"
    assert run.status == "partial_success"
    assert run.scopes[0].status == "partial_success"
    assert run.scopes[0].comment_coverage == "partial"


def test_batch_supplement_does_not_stop_at_comment_sample_target(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, _ = _insert_import_content(runtime, current_comment_count=1)
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu", provider_config_id=provider_config_id
                ),
            ),
            include_comments=True,
            include_sub_comments=False,
        ),
        request_id="stage8e-page-after-target",
    )
    first_page = _batch_comments_response()
    first_page["data"]["data"]["has_more"] = True
    last_page = _batch_comments_response()
    last_page["data"]["data"]["comments"] = []
    last_page["data"]["data"]["has_more"] = False
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=200, body=_batch_detail_response(comment_count=1)
            ),
            ProviderTransportResponse(status_code=200, body=first_page),
            ProviderTransportResponse(status_code=200, body=last_page),
        )
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-page-after-target-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert transport.call_count == 3
    run = service.get_run(created.run_id)
    assert run.scopes[0].comment_coverage == "complete"
    assert run.status == "succeeded"


def test_batch_supplement_reports_unresolved_sibling_without_provider_request(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
    batch_id, _ = _insert_import_content(runtime)
    _, blocked_content_id = _insert_import_content(
        runtime,
        batch_id=batch_id,
        external_content_id="url_sha256:unresolved",
        lookup_id_type="share_text",
    )
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    created = service.create_run(
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=batch_id,
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu", provider_config_id=provider_config_id
                ),
            ),
            include_comments=False,
            include_sub_comments=False,
        ),
        request_id="stage8e-mixed-identity",
    )
    transport = FakeProviderTransport(
        (ProviderTransportResponse(status_code=200, body=_batch_detail_response()),)
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(
            runtime=runtime,
            transport_factory=lambda _config: transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
        ),
        worker_id="stage8e-mixed-identity-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    assert transport.call_count == 1
    run = service.get_run(created.run_id)
    assert run.status == "partial_success"
    assert len(run.scopes) == 2
    assert any(
        scope.status == "failed" and scope.stop_reason == "exact_resolution_unavailable"
        for scope in run.scopes
    )
    assert any(scope.status == "succeeded" for scope in run.scopes)
    with runtime.database.engine.begin() as connection:
        source_values = {
            row["source_value"]
            for row in connection.execute(
                select(collection_scopes_table.c.source_value).where(
                    collection_scopes_table.c.run_id == created.run_id
                )
            ).mappings()
        }
    assert str(blocked_content_id) in source_values


def test_batch_supplement_retries_provider_5xx_with_new_attempt(runtime) -> None:  # type: ignore[no-untyped-def]
    provider_config_id, _ = _seed_config_and_search_pack(runtime)
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
