from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage import ArtifactRecord
from aima_ugc.platform.storage.canonical import (
    CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE,
    CANONICAL_CONTENT_ARTIFACT_KIND,
    CanonicalArtifactParent,
)
from aima_ugc.platform.storage.models import ArtifactStateConflict
from aima_ugc.platform.storage.tables import canonical_artifact_links_table
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_NOW = datetime(2026, 9, 11, 2, 0, tzinfo=UTC)


def _pending_artifact(*, kind: str = CANONICAL_CONTENT_ARTIFACT_KIND) -> ArtifactRecord:
    """构造满足当前 Artifact Schema 的 pending 元数据。"""

    artifact_id = uuid4()
    return ArtifactRecord(
        id=artifact_id,
        kind=kind,
        storage_backend="local",
        storage_key=f"{kind}/{artifact_id}.jsonl.gz",
        content_type=CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE,
        encoding="gzip",
        retention_class="canonical",
        storage_status="pending",
        created_at=_NOW,
    )


def _create_stored_canonical(session: Session) -> ArtifactRecord:
    """通过正式 Repository 状态机建立可绑定的 Canonical Artifact。"""

    repository = PostgresArtifactMetadataRepository(session)
    pending = _pending_artifact()
    repository.create_pending(pending)
    return repository.mark_stored(
        pending.id,
        sha256="a" * 64,
        byte_size=128,
        stored_at=_NOW,
    )


def _seed_real_parents(session: Session) -> tuple[CanonicalArtifactParent, ...]:
    """建立四类真实父事实及其最小上游外键。"""

    source_artifact = _pending_artifact(kind="file-import.raw")
    PostgresArtifactMetadataRepository(session).create_pending(source_artifact)
    batch_id = uuid4()
    session.execute(
        insert(processing_import_batches_table).values(
            id=batch_id,
            input_artifact_id=source_artifact.id,
            status="succeeded",
            stats={},
            created_at=_NOW,
            started_at=_NOW,
            finished_at=_NOW,
        )
    )

    campaign_id = uuid4()
    campaign_item_id = uuid4()
    session.execute(
        insert(historical_import_campaigns_table).values(
            id=campaign_id,
            client_idempotency_key=f"canonical-{campaign_id}",
            root_relative_path="fixture",
            recursive=False,
            profile_snapshot={"schema_version": "canonical-artifact-test.v1"},
            keyword_pack_snapshot={},
            status="running",
            created_at=_NOW,
            started_at=_NOW,
        )
    )
    session.execute(
        insert(historical_import_campaign_items_table).values(
            id=campaign_item_id,
            campaign_id=campaign_id,
            item_kind="source_file",
            relative_path="fixture.xlsx",
            manifest_identity="b" * 64,
            file_size=1,
            status="ready",
            created_at=_NOW,
        )
    )

    job_id = uuid4()
    run_id = uuid4()
    scope_id = uuid4()
    request_id = uuid4()
    attempt_id = uuid4()
    session.execute(
        insert(jobs_table).values(
            id=job_id,
            job_type="collection.run.v1",
            payload_version="collection-run.v1",
            payload={},
            status="queued",
            internal_idempotency_key=f"canonical-{job_id}",
            priority=0,
            attempt=0,
            max_attempts=1,
            timeout_seconds=60,
            progress=0,
            available_at=_NOW,
            created_at=_NOW,
            updated_at=_NOW,
        )
    )
    session.execute(
        insert(collection_runs_table).values(
            id=run_id,
            job_id=job_id,
            trigger_type="backfill",
            config_snapshot={"platforms": ["xiaohongshu"]},
            status="queued",
            created_at=_NOW,
        )
    )
    session.execute(
        insert(collection_scopes_table).values(
            id=scope_id,
            run_id=run_id,
            platform="xiaohongshu",
            source_type="keyword_search",
            source_value="爱玛",
            operation_group="content_discovery",
            status="running",
        )
    )
    session.execute(
        insert(provider_requests_table).values(
            id=request_id,
            scope_id=scope_id,
            provider="tikhub",
            operation="search_notes",
            request_fingerprint="c" * 64,
            request_params={"keyword": "爱玛"},
            pagination_input={},
            status="completed",
            attempt_count=1,
            created_at=_NOW,
            completed_at=_NOW,
        )
    )
    session.execute(
        insert(provider_request_attempts_table).values(
            id=attempt_id,
            provider_request_id=request_id,
            attempt_no=1,
            dispatch_status="completed",
            dispatch_started_at=_NOW,
            completed_at=_NOW,
            http_status=200,
            billing_status="not_billable",
            potential_duplicate_charge=False,
            created_at=_NOW,
        )
    )
    return (
        CanonicalArtifactParent(processing_import_batch_id=batch_id),
        CanonicalArtifactParent(historical_import_campaign_item_id=campaign_item_id),
        CanonicalArtifactParent(collection_scope_id=scope_id),
        CanonicalArtifactParent(provider_attempt_id=attempt_id),
    )


def test_repository_atomically_links_each_real_parent_and_marks_linked() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    try:
        with session.begin():
            parents = _seed_real_parents(session)
            repository = PostgresArtifactMetadataRepository(session)
            linked = [
                repository.link_canonical(
                    _create_stored_canonical(session).id,
                    parent=parent,
                    linked_at=_NOW,
                )
                for parent in parents
            ]
            rows = session.execute(select(canonical_artifact_links_table)).mappings().all()

        linked_ids = {record.id for record in linked}
        matching_rows = [row for row in rows if row["artifact_id"] in linked_ids]
        assert all(record.storage_status == "linked" for record in linked)
        assert len(matching_rows) == 4
        assert {
            sum(
                row[name] is not None
                for name in (
                    "processing_import_batch_id",
                    "historical_import_campaign_item_id",
                    "collection_scope_id",
                    "provider_attempt_id",
                )
            )
            for row in matching_rows
        } == {1}
    finally:
        session.close()
        runtime.dispose()


def test_missing_parent_rolls_back_linked_state() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    try:
        with session.begin():
            artifact = _create_stored_canonical(session)

        with pytest.raises(IntegrityError):
            with session.begin():
                PostgresArtifactMetadataRepository(session).link_canonical(
                    artifact.id,
                    parent=CanonicalArtifactParent(collection_scope_id=uuid4()),
                    linked_at=_NOW,
                )

        with session.begin():
            current = PostgresArtifactMetadataRepository(session).get(artifact.id)
        assert current is not None
        assert current.storage_status == "stored"
    finally:
        session.close()
        runtime.dispose()


def test_canonical_artifact_cannot_bypass_parent_link_contract() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    try:
        with session.begin():
            artifact = _create_stored_canonical(session)
            repository = PostgresArtifactMetadataRepository(session)
            with pytest.raises(ArtifactStateConflict):
                repository.mark_linked(artifact.id, linked_at=_NOW)

            current = repository.get(artifact.id)
            assert current is not None
            assert current.storage_status == "stored"
    finally:
        session.close()
        runtime.dispose()


def test_canonical_artifact_rejects_duplicate_parent_binding() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    try:
        with session.begin():
            parent = _seed_real_parents(session)[0]
            artifact = _create_stored_canonical(session)
            repository = PostgresArtifactMetadataRepository(session)
            repository.link_canonical(artifact.id, parent=parent, linked_at=_NOW)
            with pytest.raises(ArtifactStateConflict):
                repository.link_canonical(artifact.id, parent=parent, linked_at=_NOW)
    finally:
        session.close()
        runtime.dispose()


@pytest.mark.parametrize("parent_count", [0, 2])
def test_database_rejects_zero_or_multiple_parents(parent_count: int) -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    try:
        with session.begin():
            artifact = _create_stored_canonical(session)
            parents = _seed_real_parents(session)

        values: dict[str, UUID] = {"artifact_id": artifact.id}
        if parent_count == 2:
            values.update(
                processing_import_batch_id=parents[0].processing_import_batch_id,
                collection_scope_id=parents[2].collection_scope_id,
            )
        with pytest.raises(IntegrityError):
            with session.begin():
                session.execute(insert(canonical_artifact_links_table).values(**values))
    finally:
        session.close()
        runtime.dispose()
