from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
    RevokedCanonicalReplaySource,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.bootstrap.canonical_replay_http import PostgresCanonicalReplayHttpService
from aima_ugc.bootstrap.canonical_replay_worker import PostgresCanonicalReplayJobExecutor
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.contracts.http import CanonicalReplayAllCreateRequest
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.ingestion.canonical_replay import (
    CANONICAL_REPLAY_REVERSAL_JOB_TYPE,
    CanonicalReplayArtifactRecord,
)
from aima_ugc.modules.ingestion.canonical_replay_tables import (
    canonical_replay_all_requests_table,
    canonical_replay_run_artifacts_table,
    canonical_replay_runs_table,
)
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
from aima_ugc.platform.storage.tables import canonical_artifact_links_table
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_NOW = datetime(2026, 9, 11, 8, 0, tzinfo=UTC)


def _job(
    session: Session,
    *,
    job_type: str,
    payload: dict[str, object] | None = None,
) -> UUID:
    job_id = uuid4()
    session.execute(
        insert(jobs_table).values(
            id=job_id,
            job_type=job_type,
            payload_version=job_type,
            payload=payload or {},
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
    source_artifact = _artifact(session, kind="file-import.raw", linked=True)
    batch_id = uuid4()
    session.execute(
        insert(processing_import_batches_table).values(
            id=batch_id,
            input_artifact_id=source_artifact.id,
            status="succeeded",
            stats={},
            historical_mode=True,
            historical_campaign_item_id=parent_id,
            historical_policy_version="historical-fill-only.v1",
            created_at=_NOW,
            started_at=_NOW,
            finished_at=_NOW,
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
            job_id=_job(
                session,
                job_type=HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
                payload={
                    "schema_version": HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
                    "batch_id": str(batch_id),
                    "chunk_item_id": str(chunk_id),
                },
            ),
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


def test_campaign_replay_uses_chunk_job_batch_after_failed_batch_retry(tmp_path) -> None:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
        )
    try:
        session = runtime.new_session()
        try:
            with session.begin():
                canonical_id = _campaign_source(session)
                chunk = session.execute(
                    select(
                        historical_import_campaign_items_table.c.parent_item_id,
                        jobs_table.c.payload,
                    )
                    .join(
                        canonical_artifact_links_table,
                        canonical_artifact_links_table.c.historical_import_campaign_item_id
                        == historical_import_campaign_items_table.c.id,
                    )
                    .join(
                        jobs_table,
                        jobs_table.c.id == historical_import_campaign_items_table.c.job_id,
                    )
                    .where(canonical_artifact_links_table.c.artifact_id == canonical_id)
                ).one()
                expected_batch_id = UUID(str(chunk.payload["batch_id"]))
                failed_batch_id = uuid4()
                input_artifact_id = session.scalar(
                    select(processing_import_batches_table.c.input_artifact_id).where(
                        processing_import_batches_table.c.id == expected_batch_id
                    )
                )
                session.execute(
                    insert(processing_import_batches_table).values(
                        id=failed_batch_id,
                        input_artifact_id=input_artifact_id,
                        status="failed",
                        stats={},
                        historical_mode=True,
                        historical_campaign_item_id=chunk.parent_item_id,
                        historical_policy_version="historical-fill-only.v1",
                        created_at=_NOW,
                        started_at=_NOW,
                        finished_at=_NOW,
                    )
                )
                artifact = PostgresArtifactMetadataRepository(session).get(canonical_id)
                assert artifact is not None
                executor = PostgresCanonicalReplayJobExecutor(
                    SimpleNamespace(
                        database=runtime,
                        artifact_store=LocalArtifactStore(tmp_path),
                    )
                )
                lineage = executor._load_import_lineage_context(  # noqa: SLF001
                    session,
                    CanonicalReplayArtifactRecord(
                        run_id=uuid4(),
                        ordinal=0,
                        artifact_id=canonical_id,
                        source_kind="data_import_canonical_chunk_v2",
                    ),
                    artifact,
                )
                assert lineage is not None
                assert lineage.batch_id == expected_batch_id
                assert lineage.batch_id != failed_batch_id
        finally:
            session.close()
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
            )
        runtime.engine.dispose()


def _tikhub_attempt(
    session: Session,
    *,
    run_id: UUID,
    source_value: str,
    scope_id: UUID | None = None,
    operation: str = "search_notes",
    dispatch_status: str = "completed",
) -> tuple[UUID, UUID, UUID, UUID]:
    if scope_id is None:
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
            operation=operation,
            request_fingerprint=request_id.hex * 2,
            request_params={"keyword": source_value},
            pagination_input={},
            status=dispatch_status,
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
            dispatch_status=dispatch_status,
            dispatch_started_at=_NOW,
            completed_at=_NOW,
            http_status=200 if dispatch_status == "completed" else None,
            raw_artifact_id=raw.id,
            billing_status="not_billable" if dispatch_status == "completed" else "unknown",
            potential_duplicate_charge=dispatch_status != "completed",
            error_code=None if dispatch_status == "completed" else "transport_unknown",
            error_detail=None if dispatch_status == "completed" else "fixture transport unknown",
            created_at=_NOW,
        )
    )
    return scope_id, request_id, attempt_id, raw.id


def _tikhub_content(
    *,
    external_content_id: str,
    operation: str,
    request_id: UUID,
    attempt_id: UUID,
    raw_artifact_id: UUID,
) -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=external_content_id,
        content_type="unknown",
        observed_at=_NOW,
        observed_fields=["content_type"],
        source=CanonicalSourceV1(
            provider_name="tikhub",
            operation=operation,
            provider_request_id=str(request_id),
            provider_attempt_id=str(attempt_id),
            raw_artifact_id=raw_artifact_id,
            source_type="keyword_search",
            source_value="爱玛",
            observed_at=_NOW,
        ),
    )


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
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts "
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
            all_request = repository.enqueue_all(
                idempotency_key="all-three-lineages",
                created_by="replay-admin",
                request_id="all-three-lineages",
            )
            run_id = session.scalar(
                select(canonical_replay_runs_table.c.id).where(
                    canonical_replay_runs_table.c.all_request_id == all_request.id
                )
            )
            assert run_id is not None
            selected = repository.list_artifacts(run_id)
            assert {item.artifact_id: item.source_kind for item in selected} == {
                artifacts[0]: "excel_import_v2",
                artifacts[1]: "data_import_canonical_chunk_v2",
                artifacts[2]: "tikhub_search_attempt_v1",
            }
    finally:
        session.close()
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts "
                "RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


@pytest.mark.parametrize("campaign_status", ("revoking", "revoked"))
def test_replay_excludes_revoked_campaign_source(campaign_status: str) -> None:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
        )
    session = runtime.new_session()
    try:
        with session.begin():
            valid_artifact_id = _excel_source(session)
            revoked_artifact_id = _campaign_source(session)
            repository = PostgresCanonicalReplayRepository(session)
            queued_run, _ = repository.enqueue(
                idempotency_key=f"queued-before-{campaign_status}",
                artifact_ids=(revoked_artifact_id,),
                brand_ids=(),
                batch_size=1000,
                created_by="replay-admin",
                request_id=f"queued-before-{campaign_status}",
            )
            campaign_id = session.scalar(
                select(historical_import_campaign_items_table.c.campaign_id)
                .join(
                    canonical_artifact_links_table,
                    canonical_artifact_links_table.c.historical_import_campaign_item_id
                    == historical_import_campaign_items_table.c.id,
                )
                .where(canonical_artifact_links_table.c.artifact_id == revoked_artifact_id)
            )
            assert campaign_id is not None
            session.execute(
                update(historical_import_campaigns_table)
                .where(historical_import_campaigns_table.c.id == campaign_id)
                .values(status=campaign_status)
            )
            assert repository.list_artifacts(queued_run.id)[0].artifact_id == revoked_artifact_id
            with pytest.raises(RevokedCanonicalReplaySource):
                repository.classify_artifact(revoked_artifact_id)
            request = repository.enqueue_all(
                idempotency_key=f"exclude-{campaign_status}",
                created_by="replay-admin",
                request_id=f"exclude-{campaign_status}",
            )
            selected = session.scalars(
                select(canonical_replay_run_artifacts_table.c.artifact_id)
                .join(
                    canonical_replay_runs_table,
                    canonical_replay_run_artifacts_table.c.run_id
                    == canonical_replay_runs_table.c.id,
                )
                .where(canonical_replay_runs_table.c.all_request_id == request.id)
            ).all()
            assert selected == [valid_artifact_id]
    finally:
        session.close()
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def test_all_replay_http_admission_only_enqueues_planner_and_freezes_retry_boundary() -> None:
    """HTTP 受理不创建子 Run；同幂等键恢复第一次受理边界。"""

    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
        )
    try:
        session = runtime.new_session()
        try:
            with session.begin():
                tuple(_excel_source(session) for _ in range(101))
        finally:
            session.close()

        service = PostgresCanonicalReplayHttpService(SimpleNamespace(database=runtime))  # type: ignore[arg-type]
        body = CanonicalReplayAllCreateRequest(idempotency_key="all-history-admission")
        created = service.create_all_replays(
            body,
            actor_ref="replay-admin",
            request_id="all-history-admission",
        )
        assert created.planning_status == "queued"
        assert created.artifact_count == 0
        assert created.run_count == 0

        session = runtime.new_session()
        try:
            with session.begin():
                request = (
                    session.execute(select(canonical_replay_all_requests_table)).mappings().one()
                )
                planner = PostgresJobRepository(session).get(request["planner_job_id"])
                assert planner is not None
                assert planner.job_type == "ingestion.canonical-replay-plan.v1"
                assert planner.status == "queued"
                assert (
                    session.scalar(select(func.count()).select_from(canonical_replay_runs_table))
                    == 0
                )
                accepted_before = request["accepted_before"]
        finally:
            session.close()

        session = runtime.new_session()
        try:
            with session.begin():
                _excel_source(session)
        finally:
            session.close()

        repeated = service.create_all_replays(
            body,
            actor_ref="replay-admin",
            request_id="all-history-admission-retry",
        )
        assert repeated == created
        session = runtime.new_session()
        try:
            with session.begin():
                request = (
                    session.execute(select(canonical_replay_all_requests_table)).mappings().one()
                )
                assert request["accepted_before"] == accepted_before
                assert (
                    session.scalar(select(func.count()).select_from(canonical_replay_runs_table))
                    == 0
                )
        finally:
            session.close()
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def test_planner_cutoff_excludes_artifact_created_before_but_linked_after_admission() -> None:
    """selection 以受理前已完成 linked 为边界，不能只看 Artifact 创建时间。"""

    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
        )
    try:
        session = runtime.new_session()
        try:
            with session.begin():
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
        finally:
            session.close()

        service = PostgresCanonicalReplayHttpService(SimpleNamespace(database=runtime))  # type: ignore[arg-type]
        accepted = service.create_all_replays(
            CanonicalReplayAllCreateRequest(idempotency_key="late-link-cutoff"),
            actor_ref="replay-admin",
            request_id="late-link-cutoff",
        )
        assert accepted.planning_status == "queued"

        session = runtime.new_session()
        try:
            with session.begin():
                request = (
                    session.execute(select(canonical_replay_all_requests_table)).mappings().one()
                )
                accepted_before = request["accepted_before"]
                PostgresArtifactMetadataRepository(session).link_canonical(
                    canonical.id,
                    parent=CanonicalArtifactParent(processing_import_batch_id=batch_id),
                    linked_at=accepted_before + timedelta(microseconds=1),
                )
        finally:
            session.close()

        session = runtime.new_session()
        try:
            with session.begin():
                selected = PostgresCanonicalReplayRepository(session).list_replayable_artifacts(
                    accepted_before=accepted_before
                )
            assert canonical.id not in {artifact_id for artifact_id, _ in selected}
        finally:
            session.close()
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def test_sync_repository_enqueue_all_keeps_zero_input_compatibility() -> None:
    """内部同步原语仍可直接冻结空 selection，避免扩大 Repository Contract 破坏面。"""

    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
        )
    try:
        session = runtime.new_session()
        try:
            with session.begin():
                request = PostgresCanonicalReplayRepository(session).enqueue_all(
                    idempotency_key="sync-empty",
                    created_by="replay-admin",
                    request_id="sync-empty",
                )
                assert request.artifact_count == 0
                assert request.run_count == 0
                assert request.planning_status == "planned"
                assert request.planner_job_id is None
        finally:
            session.close()
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def test_all_replay_reversal_is_durable_idempotent_and_legacy_fail_closed() -> None:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
        )
    try:
        session = runtime.new_session()
        try:
            with session.begin():
                repository = PostgresCanonicalReplayRepository(session)
                request = repository.enqueue_all(
                    idempotency_key="empty-reversible-replay",
                    created_by="replay-admin",
                    request_id="create-empty-replay",
                )
                assert request.reversible is True
                reverting = repository.request_all_reversal(
                    request.id,
                    cancel_active=False,
                    actor_ref="replay-admin",
                    http_request_id="revoke-empty-replay",
                )
                assert reverting.lifecycle_status == "reverting"
                assert reverting.reversal_job_id is not None
                repeated = repository.request_all_reversal(
                    request.id,
                    cancel_active=False,
                    actor_ref="replay-admin",
                    http_request_id="revoke-empty-replay-retry",
                )
                assert repeated.reversal_job_id == reverting.reversal_job_id
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(jobs_table)
                        .where(jobs_table.c.job_type == CANONICAL_REPLAY_REVERSAL_JOB_TYPE)
                    )
                    == 1
                )

                legacy_id = uuid4()
                session.execute(
                    insert(canonical_replay_all_requests_table).values(
                        id=legacy_id,
                        client_idempotency_key=f"legacy-{legacy_id}",
                        selection_digest="c" * 64,
                        artifact_count=0,
                        run_count=0,
                        artifacts_per_run=100,
                        batch_size=1000,
                        created_by="legacy-admin",
                        created_at=_NOW,
                        accepted_before=_NOW,
                        planning_status="planned",
                    )
                )
                with pytest.raises(RuntimeError, match="没有精确贡献账本"):
                    repository.request_all_reversal(
                        legacy_id,
                        cancel_active=False,
                        actor_ref="replay-admin",
                        http_request_id="reject-legacy-replay",
                    )
        finally:
            session.close()
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def test_all_replay_cancel_immediately_cancels_queued_children_and_enqueues_reversal() -> None:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
        )
    try:
        session = runtime.new_session()
        try:
            with session.begin():
                _excel_source(session)
                repository = PostgresCanonicalReplayRepository(session)
                request = repository.enqueue_all(
                    idempotency_key="cancel-queued-replay",
                    created_by="replay-admin",
                    request_id="create-cancel-queued-replay",
                )
                child_job_id = session.scalar(
                    select(canonical_replay_runs_table.c.job_id).where(
                        canonical_replay_runs_table.c.all_request_id == request.id
                    )
                )
                assert child_job_id is not None

                cancelling = repository.request_all_reversal(
                    request.id,
                    cancel_active=True,
                    actor_ref="replay-admin",
                    http_request_id="cancel-queued-replay",
                )

                child = PostgresJobRepository(session).get(child_job_id)
                assert child is not None
                assert child.status == "cancelled"
                assert cancelling.lifecycle_status == "reverting"
                assert cancelling.cancellation_requested_at is not None
                assert cancelling.reversal_job_id is not None
                reversal = PostgresJobRepository(session).get(cancelling.reversal_job_id)
                assert reversal is not None
                assert reversal.status == "queued"
                assert reversal.job_type == CANONICAL_REPLAY_REVERSAL_JOB_TYPE
        finally:
            session.close()
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def test_scope_only_canonical_is_rejected_by_database_after_clean_break() -> None:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts "
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
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts "
                "RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def test_tikhub_preflight_accepts_search_and_detail_and_rejects_lineage_drift(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts "
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
            scope_id, search_request_id, search_attempt_id, search_raw_id = _tikhub_attempt(
                session,
                run_id=collection_run_id,
                source_value="爱玛",
            )
            _, detail_request_id, detail_attempt_id, detail_raw_id = _tikhub_attempt(
                session,
                run_id=collection_run_id,
                source_value="爱玛",
                scope_id=scope_id,
                operation="get_image_note_detail",
            )
            _, unknown_request_id, unknown_attempt_id, unknown_raw_id = _tikhub_attempt(
                session,
                run_id=collection_run_id,
                source_value="爱玛",
                scope_id=scope_id,
                operation="get_video_note_detail",
                dispatch_status="unknown",
            )
            canonical = _artifact(session, kind=CANONICAL_CONTENT_ARTIFACT_KIND)
            PostgresArtifactMetadataRepository(session).link_canonical(
                canonical.id,
                parent=CanonicalArtifactParent(provider_attempt_id=search_attempt_id),
                linked_at=_NOW,
            )
            run, _ = PostgresCanonicalReplayRepository(session).enqueue(
                idempotency_key=f"tikhub-lineage-{uuid4()}",
                artifact_ids=(canonical.id,),
                brand_ids=(),
                batch_size=10,
                created_by="tikhub-lineage-test",
                request_id="tikhub-lineage-test",
            )
            selected = PostgresCanonicalReplayRepository(session).list_artifacts(run.id)[0]

        claim_session = runtime.new_session()
        try:
            with claim_session.begin():
                claim = PostgresJobRepository(claim_session).claim_next(
                    supported_job_types=("ingestion.canonical-replay.v1",),
                    worker_id="tikhub-lineage-worker",
                    lease_seconds=30,
                )
                assert claim is not None and claim.lease_token is not None
        finally:
            claim_session.close()

        search = _tikhub_content(
            external_content_id="search-content",
            operation="search_notes",
            request_id=search_request_id,
            attempt_id=search_attempt_id,
            raw_artifact_id=search_raw_id,
        )
        detail = _tikhub_content(
            external_content_id="detail-content",
            operation="get_image_note_detail",
            request_id=detail_request_id,
            attempt_id=detail_attempt_id,
            raw_artifact_id=detail_raw_id,
        )
        executor = PostgresCanonicalReplayJobExecutor(
            SimpleNamespace(
                database=runtime,
                artifact_store=LocalArtifactStore(tmp_path),
            )
        )
        fence = JobExecutionFence(job_id=claim.id, lease_token=claim.lease_token)

        executor._validate_source_rows(  # noqa: SLF001 - 纵切验证真实 Search/Detail 来源链
            CanonicalReplayArtifactRecord(
                run_id=selected.run_id,
                ordinal=selected.ordinal,
                artifact_id=selected.artifact_id,
                source_kind=selected.source_kind,
            ),
            (search, detail),
            fence=fence,
        )

        invalid_rows = (
            detail.model_copy(
                update={
                    "source": detail.source.model_copy(update={"provider_request_id": str(uuid4())})
                }
            ),
            detail.model_copy(
                update={
                    "source": detail.source.model_copy(update={"provider_attempt_id": str(uuid4())})
                }
            ),
            detail.model_copy(
                update={"source": detail.source.model_copy(update={"raw_artifact_id": uuid4()})}
            ),
            detail.model_copy(update={"platform": "douyin"}),
            detail.model_copy(
                update={
                    "source": detail.source.model_copy(
                        update={"operation": "get_video_note_detail"}
                    )
                }
            ),
            _tikhub_content(
                external_content_id="unknown-content",
                operation="get_video_note_detail",
                request_id=unknown_request_id,
                attempt_id=unknown_attempt_id,
                raw_artifact_id=unknown_raw_id,
            ),
        )
        for invalid in invalid_rows:
            with pytest.raises(ValueError, match="父级 Scope"):
                executor._validate_source_rows(  # noqa: SLF001 - 逐字段验证 fail-closed
                    CanonicalReplayArtifactRecord(
                        run_id=selected.run_id,
                        ordinal=selected.ordinal,
                        artifact_id=selected.artifact_id,
                        source_kind=selected.source_kind,
                    ),
                    (invalid,),
                    fence=fence,
                )
    finally:
        session.close()
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts "
                "RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def test_tikhub_preflight_rejects_row_from_another_scope_in_the_same_run(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
            "keyword_packs, vehicle_brands, accounts "
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

        content = _tikhub_content(
            external_content_id="cross-scope-content",
            operation="search_notes",
            request_id=foreign_request_id,
            attempt_id=foreign_attempt_id,
            raw_artifact_id=foreign_raw_id,
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
                "TRUNCATE TABLE canonical_replay_all_requests, jobs, artifacts, "
                "keyword_packs, vehicle_brands, accounts "
                "RESTART IDENTITY CASCADE"
            )
        runtime.dispose()
