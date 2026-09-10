from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.bootstrap.canonical_replay_worker import PostgresCanonicalReplayJobExecutor
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.ingestion.canonical_replay import CanonicalReplayArtifactRecord
from aima_ugc.modules.ingestion.historical_jobs import HISTORICAL_IMPORT_CHUNK_JOB_TYPE
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
)
from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_TYPE
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage import ArtifactRecord, CanonicalArtifactParent
from aima_ugc.platform.storage.canonical import (
    CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE,
    CANONICAL_CONTENT_ARTIFACT_KIND,
)
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_NOW = datetime(2026, 9, 11, 8, 0, tzinfo=UTC)


def _job(session: Session, *, job_type: str) -> UUID:
    job_id = uuid4()
    session.execute(
        insert(jobs_table).values(
            id=job_id,
            job_type=job_type,
            payload_version=job_type,
            payload={},
            status="succeeded",
            internal_idempotency_key=f"canonical-replay-source-{job_id}",
            priority=0,
            attempt=1,
            max_attempts=1,
            timeout_seconds=60,
            progress=100,
            available_at=_NOW,
            created_at=_NOW,
            updated_at=_NOW,
            started_at=_NOW,
            finished_at=_NOW,
        )
    )
    return job_id


def _artifact(session: Session, *, kind: str, linked: bool = False) -> ArtifactRecord:
    artifact_id = uuid4()
    repository = PostgresArtifactMetadataRepository(session)
    suffix = "jsonl.gz" if kind == CANONICAL_CONTENT_ARTIFACT_KIND else "bin"
    content_type = (
        CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE
        if kind == CANONICAL_CONTENT_ARTIFACT_KIND
        else "application/octet-stream"
    )
    repository.create_pending(
        ArtifactRecord(
            id=artifact_id,
            kind=kind,
            storage_backend="local",
            storage_key=f"{kind}/{artifact_id}.{suffix}",
            content_type=content_type,
            encoding="gzip" if kind == CANONICAL_CONTENT_ARTIFACT_KIND else "identity",
            retention_class="canonical" if kind == CANONICAL_CONTENT_ARTIFACT_KIND else "raw",
            storage_status="pending",
            created_at=_NOW,
        )
    )
    stored = repository.mark_stored(
        artifact_id,
        sha256="a" * 64,
        byte_size=1,
        stored_at=_NOW,
    )
    return repository.mark_linked(artifact_id, linked_at=_NOW) if linked else stored


def _excel_source(session: Session) -> UUID:
    raw = _artifact(session, kind="file-import.raw", linked=True)
    batch_id = uuid4()
    session.execute(
        insert(processing_import_batches_table).values(
            id=batch_id,
            job_id=_job(session, job_type=IMPORT_JOB_TYPE),
            input_artifact_id=raw.id,
            status="succeeded",
            stats={},
            created_at=_NOW,
            started_at=_NOW,
            finished_at=_NOW,
        )
    )
    canonical = _artifact(session, kind=CANONICAL_CONTENT_ARTIFACT_KIND)
    PostgresArtifactMetadataRepository(session).link_canonical(
        canonical.id,
        parent=CanonicalArtifactParent(processing_import_batch_id=batch_id),
        linked_at=_NOW,
    )
    return canonical.id


def _campaign_source(session: Session) -> UUID:
    campaign_id = uuid4()
    session.execute(
        insert(historical_import_campaigns_table).values(
            id=campaign_id,
            client_idempotency_key=f"canonical-replay-campaign-{campaign_id}",
            root_relative_path="fixture",
            recursive=False,
            profile_snapshot={},
            keyword_pack_snapshot={},
            status="running",
            created_at=_NOW,
            started_at=_NOW,
        )
    )
    parent_id = uuid4()
    session.execute(
        insert(historical_import_campaign_items_table).values(
            id=parent_id,
            campaign_id=campaign_id,
            item_kind="source_file",
            relative_path="fixture.xlsx",
            manifest_identity="b" * 64,
            file_size=1,
            status="ready",
            created_at=_NOW,
        )
    )
    canonical = _artifact(session, kind=CANONICAL_CONTENT_ARTIFACT_KIND)
    chunk_id = uuid4()
    session.execute(
        insert(historical_import_campaign_items_table).values(
            id=chunk_id,
            campaign_id=campaign_id,
            parent_item_id=parent_id,
            item_kind="chunk",
            relative_path="fixture.xlsx",
            manifest_identity="b" * 64,
            ordinal=0,
            artifact_id=canonical.id,
            job_id=_job(session, job_type=HISTORICAL_IMPORT_CHUNK_JOB_TYPE),
            sha256="a" * 64,
            row_start=2,
            row_end=2,
            row_count=1,
            status="succeeded",
            created_at=_NOW,
            started_at=_NOW,
            finished_at=_NOW,
        )
    )
    PostgresArtifactMetadataRepository(session).link_canonical(
        canonical.id,
        parent=CanonicalArtifactParent(historical_import_campaign_item_id=chunk_id),
        linked_at=_NOW,
    )
    return canonical.id


def _tikhub_attempt(
    session: Session,
    *,
    run_id: UUID,
    source_value: str,
) -> tuple[UUID, UUID, UUID, UUID]:
    scope_id = uuid4()
    session.execute(
        insert(collection_scopes_table).values(
            id=scope_id,
            run_id=run_id,
            platform="xiaohongshu",
            source_type="keyword_search",
            source_value=source_value,
            operation_group="content_discovery",
            status="succeeded",
        )
    )
    request_id = uuid4()
    session.execute(
        insert(provider_requests_table).values(
            id=request_id,
            scope_id=scope_id,
            provider="tikhub",
            operation="search_notes",
            request_fingerprint="c" * 64,
            request_params={"keyword": source_value},
            pagination_input={},
            status="completed",
            attempt_count=1,
            created_at=_NOW,
            completed_at=_NOW,
        )
    )
    raw = _artifact(session, kind="provider-raw.v1", linked=True)
    attempt_id = uuid4()
    session.execute(
        insert(provider_request_attempts_table).values(
            id=attempt_id,
            provider_request_id=request_id,
            attempt_no=1,
            dispatch_status="completed",
            dispatch_started_at=_NOW,
            completed_at=_NOW,
            http_status=200,
            raw_artifact_id=raw.id,
            billing_status="not_billable",
            potential_duplicate_charge=False,
            created_at=_NOW,
        )
    )
    return scope_id, request_id, attempt_id, raw.id


def _tikhub_source(session: Session) -> UUID:
    run_id = uuid4()
    session.execute(
        insert(collection_runs_table).values(
            id=run_id,
            job_id=_job(session, job_type="collection.run.v1"),
            trigger_type="backfill",
            config_snapshot={},
            status="succeeded",
            created_at=_NOW,
            started_at=_NOW,
            finished_at=_NOW,
        )
    )
    _, _, attempt_id, _ = _tikhub_attempt(session, run_id=run_id, source_value="爱玛")
    canonical = _artifact(session, kind=CANONICAL_CONTENT_ARTIFACT_KIND)
    PostgresArtifactMetadataRepository(session).link_canonical(
        canonical.id,
        parent=CanonicalArtifactParent(provider_attempt_id=attempt_id),
        linked_at=_NOW,
    )
    return canonical.id


def test_repository_accepts_only_the_three_current_canonical_lineages() -> None:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, accounts "
            "RESTART IDENTITY CASCADE"
        )
    session = runtime.new_session()
    try:
        with session.begin():
            artifacts = (_excel_source(session), _campaign_source(session), _tikhub_source(session))
            repository = PostgresCanonicalReplayRepository(session)
            assert tuple(repository.classify_artifact(item) for item in artifacts) == (
                "excel_import_v2",
                "data_import_canonical_chunk_v2",
                "tikhub_search_attempt_v1",
            )
    finally:
        session.close()
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, accounts "
                "RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def test_scope_only_canonical_is_rejected_by_database_after_clean_break() -> None:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, accounts "
            "RESTART IDENTITY CASCADE"
        )
    session = runtime.new_session()
    try:
        with session.begin():
            run_id = uuid4()
            session.execute(
                insert(collection_runs_table).values(
                    id=run_id,
                    job_id=_job(session, job_type="collection.run.v1"),
                    trigger_type="backfill",
                    config_snapshot={},
                    status="succeeded",
                    created_at=_NOW,
                )
            )
            scope_id = uuid4()
            session.execute(
                insert(collection_scopes_table).values(
                    id=scope_id,
                    run_id=run_id,
                    platform="xiaohongshu",
                    source_type="keyword_search",
                    source_value="爱玛",
                    operation_group="content_discovery",
                    status="succeeded",
                )
            )
            canonical = _artifact(session, kind=CANONICAL_CONTENT_ARTIFACT_KIND)
            with pytest.raises(IntegrityError):
                with session.begin_nested():
                    PostgresArtifactMetadataRepository(session).link_canonical(
                        canonical.id,
                        parent=CanonicalArtifactParent(collection_scope_id=scope_id),
                        linked_at=_NOW,
                    )
    finally:
        session.close()
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, accounts "
                "RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def test_tikhub_preflight_rejects_row_from_another_scope_in_the_same_run(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, accounts "
            "RESTART IDENTITY CASCADE"
        )
    session = runtime.new_session()
    try:
        with session.begin():
            collection_run_id = uuid4()
            session.execute(
                insert(collection_runs_table).values(
                    id=collection_run_id,
                    job_id=_job(session, job_type="collection.run.v1"),
                    trigger_type="backfill",
                    config_snapshot={},
                    status="succeeded",
                    created_at=_NOW,
                    started_at=_NOW,
                    finished_at=_NOW,
                )
            )
            _, _, parent_attempt_id, _ = _tikhub_attempt(
                session,
                run_id=collection_run_id,
                source_value="父 Scope",
            )
            _, foreign_request_id, foreign_attempt_id, foreign_raw_id = _tikhub_attempt(
                session,
                run_id=collection_run_id,
                source_value="另一个 Scope",
            )
            canonical = _artifact(session, kind=CANONICAL_CONTENT_ARTIFACT_KIND)
            PostgresArtifactMetadataRepository(session).link_canonical(
                canonical.id,
                parent=CanonicalArtifactParent(provider_attempt_id=parent_attempt_id),
                linked_at=_NOW,
            )
            run, _ = PostgresCanonicalReplayRepository(session).enqueue(
                idempotency_key=f"cross-scope-{uuid4()}",
                artifact_ids=(canonical.id,),
                brand_ids=(),
                batch_size=1,
                created_by="cross-scope-test",
                request_id="cross-scope-test",
            )
            selected = PostgresCanonicalReplayRepository(session).list_artifacts(run.id)[0]

        claim_session = runtime.new_session()
        try:
            with claim_session.begin():
                claim = PostgresJobRepository(claim_session).claim_next(
                    supported_job_types=("ingestion.canonical-replay.v1",),
                    worker_id="cross-scope-worker",
                    lease_seconds=30,
                )
                assert claim is not None and claim.lease_token is not None
        finally:
            claim_session.close()

        content = CanonicalContentV1(
            platform="xiaohongshu",
            external_content_id="cross-scope-content",
            content_type="unknown",
            observed_at=_NOW,
            observed_fields=["content_type"],
            source=CanonicalSourceV1(
                provider_name="tikhub",
                operation="search_notes",
                provider_request_id=str(foreign_request_id),
                provider_attempt_id=str(foreign_attempt_id),
                raw_artifact_id=foreign_raw_id,
                source_type="keyword_search",
                source_value="另一个 Scope",
                observed_at=_NOW,
            ),
        )
        executor = PostgresCanonicalReplayJobExecutor(
            SimpleNamespace(
                database=runtime,
                artifact_store=LocalArtifactStore(tmp_path),
            )
        )

        with pytest.raises(ValueError, match="父级 Scope"):
            executor._validate_source_rows(  # noqa: SLF001 - 纵切验证 fail-closed 边界
                CanonicalReplayArtifactRecord(
                    run_id=selected.run_id,
                    ordinal=selected.ordinal,
                    artifact_id=selected.artifact_id,
                    source_kind=selected.source_kind,
                ),
                (content,),
                fence=JobExecutionFence(job_id=claim.id, lease_token=claim.lease_token),
            )
    finally:
        session.close()
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, accounts "
                "RESTART IDENTITY CASCADE"
            )
        runtime.dispose()
