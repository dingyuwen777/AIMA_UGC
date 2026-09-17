from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection_targets import PostgresCollectionTargetReader
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.platform import PlatformName
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity
from aima_ugc.modules.analysis.tables import (
    analysis_content_results_table,
    analysis_content_run_targets_table,
    analysis_content_runs_table,
)
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.extended_tables import content_external_ids_table
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_PAYLOAD_VERSION, IMPORT_JOB_TYPE
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.tables import artifacts_table
from sqlalchemy import insert

_CURRENT_ANALYSIS_IDENTITY = AnalysisConfigurationIdentity(
    prompt_version="test-v1",
    prompt_sha256="3" * 64,
    taxonomy_sha256="4" * 64,
    model_provider="test",
    model="test-model",
)


@pytest.fixture
def runtime():  # type: ignore[no-untyped-def]
    value = create_worker_runtime(settings=load_settings())

    def cleanup() -> None:
        with value.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, accounts, processing_import_batches "
                "RESTART IDENTITY CASCADE"
            )

    cleanup()
    try:
        yield value
    finally:
        cleanup()
        value.close()


def _seed_batch(runtime) -> tuple[UUID, UUID, UUID, UUID]:  # type: ignore[no-untyped-def]
    now = datetime.now(UTC)
    artifact_id = uuid4()
    batch_id = uuid4()
    job_id = uuid4()
    request_id = uuid4()
    attempt_id = uuid4()
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(artifacts_table).values(
                id=artifact_id,
                kind="file-import.raw",
                storage_backend="local",
                storage_key=f"supplement-eligibility/{artifact_id}",
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                sha256="1" * 64,
                byte_size=1,
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
                internal_idempotency_key=f"supplement-eligibility:{job_id}",
                request_id="supplement-eligibility",
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
                stats={"stage": "succeeded", "rows_ingested": 3},
                created_at=now,
                started_at=now,
                finished_at=now,
            )
        )
        connection.execute(
            insert(provider_requests_table).values(
                id=request_id,
                scope_id=None,
                import_batch_id=batch_id,
                provider_config_id=None,
                provider="file_import",
                operation="excel_import",
                request_fingerprint="2" * 64,
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
    return batch_id, job_id, attempt_id, artifact_id


def _insert_content(
    runtime,  # type: ignore[no-untyped-def]
    *,
    attempt_id: UUID,
    artifact_id: UUID,
    external_content_id: str,
    lookup_id: bool,
    job_id: UUID,
    irrelevant: bool,
    platform: PlatformName = "xiaohongshu",
    lookup_id_type: str = "note_id",
    lookup_value: str | None = None,
) -> UUID:
    now = datetime.now(UTC)
    content_id = uuid4()
    content_type = (
        "image" if platform == "xiaohongshu" else "text" if platform == "weibo" else "video"
    )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(contents_table).values(
                id=content_id,
                platform=platform,
                external_content_id=external_content_id,
                content_type=content_type,
                title="爱玛测试内容",
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
                title="爱玛测试内容",
                provider_attempt_id=attempt_id,
                raw_artifact_id=artifact_id,
                observed_at=now,
            )
        )
        if lookup_id:
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
        if irrelevant:
            run_id = uuid4()
            connection.execute(
                insert(analysis_content_runs_table).values(
                    id=run_id,
                    client_idempotency_key=f"collection-target-test:{run_id}",
                    planner_job_id=job_id,
                    run_intent="initial_analysis",
                    scope="selected",
                    filter_snapshot={"content_ids": [str(content_id)]},
                    status="succeeded",
                    target_count=1,
                    shard_count=1,
                    shard_size=1,
                    prompt_version=_CURRENT_ANALYSIS_IDENTITY.prompt_version,
                    prompt_sha256=_CURRENT_ANALYSIS_IDENTITY.prompt_sha256,
                    taxonomy_sha256=_CURRENT_ANALYSIS_IDENTITY.taxonomy_sha256,
                    model_provider=_CURRENT_ANALYSIS_IDENTITY.model_provider,
                    model=_CURRENT_ANALYSIS_IDENTITY.model,
                    generation_config={},
                    generation_config_hash=(
                        "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
                    ),
                    created_at=now,
                    started_at=now,
                    finished_at=now,
                )
            )
            connection.execute(
                insert(analysis_content_run_targets_table).values(
                    run_id=run_id,
                    target_ordinal=0,
                    content_id=content_id,
                    content_version=1,
                )
            )
            connection.execute(
                insert(analysis_content_results_table).values(
                    id=uuid4(),
                    content_id=content_id,
                    content_version=1,
                    analysis_run_id=run_id,
                    job_id=job_id,
                    schema_version="content-label-analysis.v3",
                    relevance="irrelevant",
                    voice_type="无法判断",
                    sentiment=None,
                    prompt_version=_CURRENT_ANALYSIS_IDENTITY.prompt_version,
                    prompt_sha256=_CURRENT_ANALYSIS_IDENTITY.prompt_sha256,
                    taxonomy_sha256=_CURRENT_ANALYSIS_IDENTITY.taxonomy_sha256,
                    model_provider=_CURRENT_ANALYSIS_IDENTITY.model_provider,
                    model=_CURRENT_ANALYSIS_IDENTITY.model,
                    input_hash="5" * 64,
                    generation_config_hash=(
                        "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
                    ),
                    analyzed_at=now,
                    created_at=now,
                )
            )
    return content_id


def _read_targets(runtime, *, batch_id: UUID, identity: AnalysisConfigurationIdentity):  # type: ignore[no-untyped-def]
    with runtime.database.new_session() as session:
        with session.begin():
            return PostgresCollectionTargetReader(
                session,
                analysis_identity=identity,
            ).list_batch_targets(
                batch_id=batch_id,
                platforms=("xiaohongshu",),
            )


@pytest.mark.parametrize(
    ("platform", "id_type", "native_id"),
    (
        ("xiaohongshu", "note_id", "6a85c701000000001d0040e2"),
        ("douyin", "aweme_id", "7531234567890123456"),
        ("weibo", "status_id", "5337757797058061"),
        ("bilibili", "av_id", "117119547215182"),
        ("kuaishou", "photo_id", "3xv8mv8f3mwrtdk"),
    ),
)
def test_batch_supplement_reads_five_platform_typed_ids_from_content_owner(
    runtime, platform: PlatformName, id_type: str, native_id: str
) -> None:  # type: ignore[no-untyped-def]
    batch_id, job_id, attempt_id, artifact_id = _seed_batch(runtime)
    content_id = _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id=f"source-{platform}",
        lookup_id=True,
        job_id=job_id,
        irrelevant=False,
        platform=platform,
        lookup_id_type=id_type,
        lookup_value=native_id,
    )
    with runtime.database.new_session() as session:
        with session.begin():
            reader = PostgresCollectionTargetReader(
                session, analysis_identity=_CURRENT_ANALYSIS_IDENTITY
            )
            targets = reader.list_batch_targets(batch_id=batch_id, platforms=(platform,))
            diagnostics = reader.list_batch_diagnostics(batch_id=batch_id, platforms=(platform,))

    assert len(targets) == 1
    assert targets[0].content_id == content_id
    assert targets[0].lookup_id_type == id_type
    assert targets[0].lookup_value == native_id
    assert len(diagnostics) == 1
    assert diagnostics[0].direct_target_count == 1
    assert diagnostics[0].blocked_count == 0


def test_batch_supplement_targets_require_lookup_identity_and_exclude_current_irrelevant(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    batch_id, job_id, attempt_id, artifact_id = _seed_batch(runtime)
    eligible_id = _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="eligible-note",
        lookup_id=True,
        job_id=job_id,
        irrelevant=False,
    )
    _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="irrelevant-note",
        lookup_id=True,
        job_id=job_id,
        irrelevant=True,
    )
    _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="url_sha256:unresolved",
        lookup_id=False,
        job_id=job_id,
        irrelevant=False,
    )

    targets = _read_targets(runtime, batch_id=batch_id, identity=_CURRENT_ANALYSIS_IDENTITY)

    assert [target.content_id for target in targets] == [eligible_id]


def test_batch_eligibility_diagnostics_keep_unresolved_platform_visible(runtime) -> None:  # type: ignore[no-untyped-def]
    """短链候选与无身份内容进入诊断，但不能进入实际补采 Scope。"""
    batch_id, job_id, attempt_id, artifact_id = _seed_batch(runtime)
    _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="6a81d4300000000028002076",
        lookup_id=True,
        job_id=job_id,
        irrelevant=False,
    )
    candidate_id = _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="url_sha256:candidate",
        lookup_id=False,
        job_id=job_id,
        irrelevant=False,
    )
    _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="url_sha256:blocked",
        lookup_id=False,
        job_id=job_id,
        irrelevant=False,
    )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(content_external_ids_table).values(
                content_id=candidate_id,
                id_type="share_text",
                external_id="https://xhslink.com/example",
                provider_attempt_id=attempt_id,
                raw_artifact_id=artifact_id,
                observed_at=datetime.now(UTC),
            )
        )

    with runtime.database.new_session() as session:
        with session.begin():
            reader = PostgresCollectionTargetReader(
                session, analysis_identity=_CURRENT_ANALYSIS_IDENTITY
            )
            targets = reader.list_batch_targets(batch_id=batch_id, platforms=("xiaohongshu",))
            diagnostics = reader.list_batch_diagnostics(
                batch_id=batch_id, platforms=("xiaohongshu",)
            )
            source_items = reader.list_batch_source_items(
                batch_id=batch_id, platforms=("xiaohongshu",)
            )
            candidate_reason = reader.get_batch_unavailable_reason(
                batch_id=batch_id, content_id=candidate_id
            )

    assert len(targets) == 1
    assert len(source_items) == 3
    assert candidate_reason == "exact_resolution_unavailable"
    assert len(diagnostics) == 1
    assert diagnostics[0].direct_target_count == 1
    assert diagnostics[0].resolution_candidate_count == 1
    assert diagnostics[0].blocked_count == 1
    assert diagnostics[0].block_reasons == {
        "exact_resolution_unavailable": 1,
        "identity_unavailable": 1,
    }


def test_legacy_weibo_ttarticle_identity_is_blocked_even_with_status_id(runtime) -> None:  # type: ignore[no-untyped-def]
    batch_id, job_id, attempt_id, artifact_id = _seed_batch(runtime)
    ordinary_id = _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="5191839277071122",
        lookup_id=True,
        lookup_id_type="status_id",
        job_id=job_id,
        irrelevant=False,
        platform="weibo",
    )
    article_id = _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="5337665377009857",
        lookup_id=True,
        lookup_id_type="status_id",
        job_id=job_id,
        irrelevant=False,
        platform="weibo",
    )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(content_external_ids_table).values(
                content_id=article_id,
                id_type="ttarticle_id",
                external_id="2309405337665377009857",
                provider_attempt_id=attempt_id,
                raw_artifact_id=artifact_id,
                observed_at=datetime.now(UTC),
            )
        )

    with runtime.database.new_session() as session:
        with session.begin():
            reader = PostgresCollectionTargetReader(
                session, analysis_identity=_CURRENT_ANALYSIS_IDENTITY
            )
            targets = reader.list_batch_targets(batch_id=batch_id, platforms=("weibo",))
            diagnostics = reader.list_batch_diagnostics(batch_id=batch_id, platforms=("weibo",))
            blocked_reason = reader.get_batch_unavailable_reason(
                batch_id=batch_id, content_id=article_id
            )

    assert {target.content_id for target in targets} == {ordinary_id}
    assert len(diagnostics) == 1
    assert diagnostics[0].direct_target_count == 1
    assert diagnostics[0].blocked_count == 1
    assert diagnostics[0].block_reasons == {"identity_unavailable": 1}
    assert blocked_reason == "identity_unavailable"


def test_typed_lookup_that_does_not_match_stable_content_identity_is_eligible(
    runtime,
) -> None:  # type: ignore[no-untyped-def]
    batch_id, job_id, attempt_id, artifact_id = _seed_batch(runtime)
    eligible_id = _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="eligible-note",
        lookup_id=True,
        job_id=job_id,
        irrelevant=False,
    )
    mismatched_id = _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="SOURCE-ARTICLE-ONLY",
        lookup_id=False,
        job_id=job_id,
        irrelevant=False,
    )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(content_external_ids_table).values(
                content_id=mismatched_id,
                id_type="note_id",
                external_id="real-provider-note-id",
                provider_attempt_id=attempt_id,
                raw_artifact_id=artifact_id,
                observed_at=datetime.now(UTC),
            )
        )

    targets = _read_targets(runtime, batch_id=batch_id, identity=_CURRENT_ANALYSIS_IDENTITY)

    assert {target.content_id for target in targets} == {eligible_id, mismatched_id}
    mismatched = next(target for target in targets if target.content_id == mismatched_id)
    assert mismatched.lookup_id_type == "note_id"
    assert mismatched.lookup_value == "real-provider-note-id"


def test_runtime_model_change_does_not_bypass_latest_run_irrelevance(runtime) -> None:  # type: ignore[no-untyped-def]
    batch_id, job_id, attempt_id, artifact_id = _seed_batch(runtime)
    content_id = _insert_content(
        runtime,
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        external_content_id="stale-analysis-note",
        lookup_id=True,
        job_id=job_id,
        irrelevant=True,
    )
    changed_identity = AnalysisConfigurationIdentity(
        prompt_version=_CURRENT_ANALYSIS_IDENTITY.prompt_version,
        prompt_sha256=_CURRENT_ANALYSIS_IDENTITY.prompt_sha256,
        taxonomy_sha256=_CURRENT_ANALYSIS_IDENTITY.taxonomy_sha256,
        model_provider=_CURRENT_ANALYSIS_IDENTITY.model_provider,
        model="new-model",
    )

    targets = _read_targets(runtime, batch_id=batch_id, identity=changed_identity)

    assert content_id is not None
    assert targets == ()
