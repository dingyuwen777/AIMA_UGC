from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap import canonical_replay_worker as canonical_replay_worker_module
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.canonical_replay_http import PostgresCanonicalReplayHttpService
from aima_ugc.bootstrap.canonical_replay_worker import PostgresCanonicalReplayJobExecutor
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.contracts.brand_vehicle import BrandAliasCreateRequest, BrandCreateRequest
from aima_ugc.contracts.http import CanonicalReplayCreateRequest
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.ingestion.canonical_replay import (
    CANONICAL_REPLAY_JOB_TYPE,
    CanonicalReplayCounters,
    CanonicalReplayJobPayload,
)
from aima_ugc.modules.ingestion.canonical_replay_tables import (
    canonical_replay_seen_content_table,
)
from aima_ugc.modules.vehicles.tables import content_brand_evidence_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.tables import artifacts_table, canonical_artifact_links_table
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select, text


class _ExecutionContext:
    def __init__(self, fence: JobExecutionFence, *, lose_after_heartbeat: bool = False) -> None:
        self.fence = fence
        self._lose_after_heartbeat = lose_after_heartbeat

    def heartbeat(self, *, progress=None):  # type: ignore[no-untyped-def]
        del progress
        if self._lose_after_heartbeat:
            raise LeaseLostError("模拟首批提交后的 Worker lease 丢失")

    def cancel_requested(self) -> bool:
        return False


def _principal() -> Principal:
    return Principal(
        principal_id="canonical-replay-integration",
        display_name="Canonical Replay 集成测试",
        role="administrator",
        source="development",
    )


def _xlsx(*, rows: tuple[tuple[str, str], ...]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文章"
    sheet.append(["媒体名称（中文）", "标题", "内文", "作者", "出版日期", "原文链接"])
    for external_id, title in rows:
        sheet.append(
            [
                "小红书",
                title,
                "Replay 固定测试正文",
                "测试账号",
                "2026-09-11 08:00:00",
                f"https://www.xiaohongshu.com/explore/{external_id}",
            ]
        )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _truncate(runtime: PlatformRuntime) -> None:
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, accounts "
            "RESTART IDENTITY CASCADE"
        )


def _runtime(tmp_path: Path) -> PlatformRuntime:
    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    return create_worker_runtime(settings=settings)


def _worker(runtime: PlatformRuntime, *, suffix: str):  # type: ignore[no-untyped-def]
    return create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(runtime=runtime),
        worker_id=f"canonical-replay-{suffix}",
        lease_seconds=120,
        retry_delay_seconds=0,
    )


def _create_brand_without_matching_alias(runtime: PlatformRuntime) -> UUID:
    return _create_brand(runtime, alias="绝不命中的旧识别词")


def _create_brand(runtime: PlatformRuntime, *, alias: str) -> UUID:
    created = PostgresBrandVehicleHttpService(runtime).create_brand(
        BrandCreateRequest(
            code=f"REPLAY-{uuid4()}",
            display_name="Replay 测试品牌",
            role="owned",
            aliases=(alias,),
        ),
        principal=_principal(),
        request_id="canonical-replay-brand",
    )
    return created.id


def _add_replay_alias(runtime: PlatformRuntime, brand_id: UUID) -> int:
    updated = PostgresBrandVehicleHttpService(runtime).add_alias(
        brand_id,
        BrandAliasCreateRequest(text="星曜"),
        principal=_principal(),
        request_id="canonical-replay-alias",
    )
    return updated.catalog_version


def _import_canonical(
    client: TestClient,
    runtime: PlatformRuntime,
    *,
    filename: str,
    rows: tuple[tuple[str, str], ...],
    brand_ids: tuple[UUID, ...],
) -> UUID:
    files: list[tuple[str, tuple[str | None, object, str | None]]] = [
        (
            "file",
            (
                filename,
                _xlsx(rows=rows),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
    ]
    files.extend(("brand_ids", (None, str(brand_id), None)) for brand_id in brand_ids)
    created = client.post(
        "/api/v1/import-batches",
        files=files,
    )
    assert created.status_code == 202
    assert _worker(runtime, suffix=f"import-{filename}").run_once() is True
    batch = client.get(f"/api/v1/import-batches/{created.json()['batch_id']}")
    assert batch.status_code == 200
    assert batch.json()["status"] == "succeeded"
    assert batch.json()["stats"]["rows_ingested"] == 0
    with runtime.database.engine.connect() as connection:
        artifact_id = connection.scalar(
            select(canonical_artifact_links_table.c.artifact_id).where(
                canonical_artifact_links_table.c.processing_import_batch_id
                == UUID(created.json()["batch_id"])
            )
        )
    assert isinstance(artifact_id, UUID)
    return artifact_id


def _create_replay(
    client: TestClient,
    *,
    artifact_ids: tuple[UUID, ...],
    brand_id: UUID,
    idempotency_key: str,
    batch_size: int = 1,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/canonical-replays",
        json={
            "idempotency_key": idempotency_key,
            "artifact_ids": [str(item) for item in artifact_ids],
            "brand_ids": [str(brand_id)],
            "batch_size": batch_size,
        },
    )
    assert response.status_code == 202
    return response.json()


def test_new_alias_replay_deduplicates_and_converges_through_content_owner(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    _truncate(runtime)
    try:
        client = TestClient(
            create_app(
                import_service=PostgresImportHttpService(runtime),
                canonical_replay_service=PostgresCanonicalReplayHttpService(runtime),
            )
        )
        brand_id = _create_brand_without_matching_alias(runtime)
        artifact_id = _import_canonical(
            client,
            runtime,
            filename="replay-duplicate.xlsx",
            rows=(
                ("canonical-replay-same", "星曜首条"),
                ("canonical-replay-same", "星曜重复记录"),
            ),
            brand_ids=(brand_id,),
        )
        catalog_version = _add_replay_alias(runtime, brand_id)

        first = _create_replay(
            client,
            artifact_ids=(artifact_id,),
            brand_id=brand_id,
            idempotency_key=f"replay-first-{uuid4()}",
        )
        assert _worker(runtime, suffix="first").run_once() is True
        first_run = client.get(f"/api/v1/canonical-replays/{first['run_id']}")

        assert first_run.status_code == 200
        assert first_run.json()["job"]["status"] == "succeeded"
        assert first_run.json()["catalog_version"] == catalog_version
        assert first_run.json()["stats"] == {
            "rows_seen": 2,
            "rows_matched": 2,
            "rows_filtered_out": 0,
            "duplicates_removed": 1,
            "rows_ingested": 1,
            "existing_convergence": 0,
            "invalid_artifact_rows": 0,
        }

        replay_again = _create_replay(
            client,
            artifact_ids=(artifact_id,),
            brand_id=brand_id,
            idempotency_key=f"replay-existing-{uuid4()}",
        )
        assert _worker(runtime, suffix="existing").run_once() is True
        second_run = client.get(f"/api/v1/canonical-replays/{replay_again['run_id']}")

        assert second_run.json()["stats"] == {
            "rows_seen": 2,
            "rows_matched": 2,
            "rows_filtered_out": 0,
            "duplicates_removed": 1,
            "rows_ingested": 0,
            "existing_convergence": 1,
            "invalid_artifact_rows": 0,
        }
        with runtime.database.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 1
            assert (
                connection.scalar(
                    select(func.count()).select_from(canonical_replay_seen_content_table)
                )
                == 2
            )
            evidence = connection.execute(select(content_brand_evidence_table)).mappings().all()
        assert {row["brand_id"] for row in evidence} == {brand_id}
        assert {row["catalog_version"] for row in evidence} == {catalog_version}
    finally:
        _truncate(runtime)
        runtime.close()


def test_all_artifacts_are_preflighted_before_first_content_write(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _truncate(runtime)
    try:
        client = TestClient(
            create_app(
                import_service=PostgresImportHttpService(runtime),
                canonical_replay_service=PostgresCanonicalReplayHttpService(runtime),
            )
        )
        brand_id = _create_brand_without_matching_alias(runtime)
        first_artifact = _import_canonical(
            client,
            runtime,
            filename="replay-valid.xlsx",
            rows=(("canonical-replay-valid", "星曜合法记录"),),
            brand_ids=(brand_id,),
        )
        second_artifact = _import_canonical(
            client,
            runtime,
            filename="replay-corrupt.xlsx",
            rows=(("canonical-replay-corrupt", "星曜损坏记录"),),
            brand_ids=(brand_id,),
        )
        _add_replay_alias(runtime, brand_id)
        with runtime.database.engine.connect() as connection:
            storage_key = connection.scalar(
                select(artifacts_table.c.storage_key).where(artifacts_table.c.id == second_artifact)
            )
        assert isinstance(storage_key, str)
        target = runtime.artifact_store.root.joinpath(*storage_key.split("/"))
        target.write_bytes(b"corrupted-after-link")

        replay = _create_replay(
            client,
            artifact_ids=(first_artifact, second_artifact),
            brand_id=brand_id,
            idempotency_key=f"replay-preflight-{uuid4()}",
        )
        assert _worker(runtime, suffix="preflight").run_once() is True
        failed = client.get(f"/api/v1/canonical-replays/{replay['run_id']}")

        assert failed.status_code == 200
        assert failed.json()["job"]["status"] == "failed"
        assert failed.json()["job"]["error_code"] == "canonical_replay_artifact_invalid"
        assert failed.json()["stats"]["rows_seen"] == 0
        with runtime.database.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 0
            assert (
                connection.scalar(
                    select(func.count()).select_from(canonical_replay_seen_content_table)
                )
                == 0
            )
    finally:
        _truncate(runtime)
        runtime.close()


def test_replay_enqueue_is_idempotent_and_rejects_parameter_drift(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _truncate(runtime)
    try:
        client = TestClient(
            create_app(
                import_service=PostgresImportHttpService(runtime),
                canonical_replay_service=PostgresCanonicalReplayHttpService(runtime),
            )
        )
        brand_id = _create_brand_without_matching_alias(runtime)
        artifact_id = _import_canonical(
            client,
            runtime,
            filename="replay-idempotency.xlsx",
            rows=(("canonical-replay-idempotency", "星曜幂等记录"),),
            brand_ids=(brand_id,),
        )
        _add_replay_alias(runtime, brand_id)
        key = f"replay-idempotency-{uuid4()}"

        first = _create_replay(
            client,
            artifact_ids=(artifact_id,),
            brand_id=brand_id,
            idempotency_key=key,
        )
        repeated = _create_replay(
            client,
            artifact_ids=(artifact_id,),
            brand_id=brand_id,
            idempotency_key=key,
        )
        drift = client.post(
            "/api/v1/canonical-replays",
            json={
                "idempotency_key": key,
                "artifact_ids": [str(artifact_id)],
                "brand_ids": [str(brand_id)],
                "batch_size": 2,
            },
        )

        assert repeated == first
        assert drift.status_code == 409
        assert drift.json()["errors"][0]["code"] == "canonical_replay_conflict"
    finally:
        _truncate(runtime)
        runtime.close()


def test_concurrent_same_idempotency_key_returns_one_run_and_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime(tmp_path)
    _truncate(runtime)
    try:
        client = TestClient(create_app(import_service=PostgresImportHttpService(runtime)))
        brand_id = _create_brand_without_matching_alias(runtime)
        artifact_id = _import_canonical(
            client,
            runtime,
            filename="replay-concurrent.xlsx",
            rows=(("canonical-replay-concurrent", "并发幂等记录"),),
            brand_ids=(brand_id,),
        )
        body = CanonicalReplayCreateRequest(
            idempotency_key=f"replay-concurrent-{uuid4()}",
            artifact_ids=(artifact_id,),
            brand_ids=(brand_id,),
            batch_size=1,
        )
        barrier = Barrier(2, timeout=5)
        original = PostgresCanonicalReplayRepository._lock_idempotency_key

        def synchronized_lock(repository, key):  # type: ignore[no-untyped-def]
            barrier.wait()
            original(repository, key)

        monkeypatch.setattr(
            PostgresCanonicalReplayRepository,
            "_lock_idempotency_key",
            synchronized_lock,
        )

        def create(index: int):  # type: ignore[no-untyped-def]
            return PostgresCanonicalReplayHttpService(runtime).create_replay(
                body,
                actor_ref=_principal().principal_id,
                request_id=f"canonical-replay-concurrent-{index}",
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = tuple(executor.map(create, range(2)))

        assert responses[0] == responses[1]
        with runtime.database.engine.connect() as connection:
            assert (
                connection.scalar(
                    select(func.count())
                    .select_from(jobs_table)
                    .where(jobs_table.c.job_type == CANONICAL_REPLAY_JOB_TYPE)
                )
                == 1
            )
    finally:
        _truncate(runtime)
        runtime.close()


def test_small_batches_open_each_artifact_once_after_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime(tmp_path)
    _truncate(runtime)
    try:
        client = TestClient(
            create_app(
                import_service=PostgresImportHttpService(runtime),
                canonical_replay_service=PostgresCanonicalReplayHttpService(runtime),
            )
        )
        brand_id = _create_brand(runtime, alias="星曜")
        artifact_id = _import_canonical(
            client,
            runtime,
            filename="replay-linear-read.xlsx",
            rows=tuple(
                (f"canonical-replay-linear-{index}", f"星曜线性读取 {index}") for index in range(5)
            ),
            brand_ids=(brand_id,),
        )
        calls = 0
        original = canonical_replay_worker_module.CanonicalArtifactReader.read

        def counted_read(reader, artifact):  # type: ignore[no-untyped-def]
            nonlocal calls
            calls += 1
            yield from original(reader, artifact)

        monkeypatch.setattr(
            canonical_replay_worker_module.CanonicalArtifactReader,
            "read",
            counted_read,
        )
        _create_replay(
            client,
            artifact_ids=(artifact_id,),
            brand_id=brand_id,
            idempotency_key=f"replay-linear-{uuid4()}",
            batch_size=1,
        )

        assert _worker(runtime, suffix="linear-read").run_once() is True
        assert calls == 2
    finally:
        _truncate(runtime)
        runtime.close()


def test_selected_replay_preserves_existing_out_of_scope_brand_evidence(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    _truncate(runtime)
    try:
        client = TestClient(
            create_app(
                import_service=PostgresImportHttpService(runtime),
                canonical_replay_service=PostgresCanonicalReplayHttpService(runtime),
            )
        )
        selected_brand = _create_brand(runtime, alias="星曜")
        out_of_scope_brand = _create_brand(runtime, alias="月影")
        artifact_id = _import_canonical(
            client,
            runtime,
            filename="replay-preserve-evidence.xlsx",
            rows=(("canonical-replay-preserve-evidence", "星曜与月影联名"),),
            brand_ids=(selected_brand, out_of_scope_brand),
        )
        with runtime.database.engine.connect() as connection:
            before = set(
                connection.scalars(
                    select(content_brand_evidence_table.c.brand_id).where(
                        content_brand_evidence_table.c.is_active.is_(True)
                    )
                )
            )
        assert before == {selected_brand, out_of_scope_brand}

        replay = _create_replay(
            client,
            artifact_ids=(artifact_id,),
            brand_id=selected_brand,
            idempotency_key=f"replay-preserve-evidence-{uuid4()}",
        )
        assert _worker(runtime, suffix="preserve-evidence").run_once() is True
        response = client.get(f"/api/v1/canonical-replays/{replay['run_id']}")
        assert response.json()["stats"]["existing_convergence"] == 1
        with runtime.database.engine.connect() as connection:
            after = set(
                connection.scalars(
                    select(content_brand_evidence_table.c.brand_id).where(
                        content_brand_evidence_table.c.is_active.is_(True)
                    )
                )
            )
        assert after == {selected_brand, out_of_scope_brand}
    finally:
        _truncate(runtime)
        runtime.close()


def test_repository_snapshot_is_exactly_the_requested_active_brand(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _truncate(runtime)
    try:
        selected = _create_brand_without_matching_alias(runtime)
        ignored = _create_brand_without_matching_alias(runtime)
        session = runtime.database.new_session()
        try:
            with session.begin():
                snapshot = PostgresBrandVehicleRepository(session).snapshot(brand_ids=(selected,))
        finally:
            session.close()

        assert snapshot.scope == "selected"
        assert {item.id for item in snapshot.brands} == {selected}
        assert ignored not in {item.id for item in snapshot.brands}
    finally:
        _truncate(runtime)
        runtime.close()


def test_replay_takeover_resumes_checkpoint_and_rejects_stale_fence(tmp_path: Path) -> None:
    """首批提交后接管从检查点续跑，旧 Token 不能再推进统计。"""

    runtime = _runtime(tmp_path)
    _truncate(runtime)
    try:
        client = TestClient(
            create_app(
                import_service=PostgresImportHttpService(runtime),
                canonical_replay_service=PostgresCanonicalReplayHttpService(runtime),
            )
        )
        brand_id = _create_brand_without_matching_alias(runtime)
        artifact_id = _import_canonical(
            client,
            runtime,
            filename="replay-takeover.xlsx",
            rows=(
                ("canonical-replay-takeover-1", "星曜接管第一条"),
                ("canonical-replay-takeover-2", "星曜接管第二条"),
            ),
            brand_ids=(brand_id,),
        )
        _add_replay_alias(runtime, brand_id)
        created = _create_replay(
            client,
            artifact_ids=(artifact_id,),
            brand_id=brand_id,
            idempotency_key=f"replay-takeover-{uuid4()}",
            batch_size=1,
        )
        run_id = UUID(str(created["run_id"]))
        job_id = UUID(str(created["job_id"]))

        first_session = runtime.database.new_session()
        try:
            with first_session.begin():
                first_claim = PostgresJobRepository(first_session).claim_next(
                    supported_job_types=(CANONICAL_REPLAY_JOB_TYPE,),
                    worker_id="replay-old-worker",
                    lease_seconds=30,
                )
                assert first_claim is not None
                assert first_claim.lease_token is not None
        finally:
            first_session.close()
        old_fence = JobExecutionFence(job_id=job_id, lease_token=first_claim.lease_token)

        with pytest.raises(LeaseLostError):
            PostgresCanonicalReplayJobExecutor(runtime).execute(
                payload=CanonicalReplayJobPayload(run_id=run_id),
                fence=old_fence,
                context=_ExecutionContext(old_fence, lose_after_heartbeat=True),
            )

        with runtime.database.engine.begin() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 1
            connection.execute(
                text(
                    "UPDATE jobs SET lease_expires_at = clock_timestamp() - interval '1 second' "
                    "WHERE id = :job_id"
                ),
                {"job_id": job_id},
            )

        takeover_session = runtime.database.new_session()
        try:
            with takeover_session.begin():
                takeover = PostgresJobRepository(takeover_session).claim_next(
                    supported_job_types=(CANONICAL_REPLAY_JOB_TYPE,),
                    worker_id="replay-new-worker",
                    lease_seconds=30,
                )
                assert takeover is not None
                assert takeover.lease_token is not None
                assert takeover.lease_token != first_claim.lease_token
        finally:
            takeover_session.close()
        takeover_fence = JobExecutionFence(job_id=job_id, lease_token=takeover.lease_token)

        stale_session = runtime.database.new_session()
        try:
            with pytest.raises(LeaseLostError), stale_session.begin():
                PostgresCanonicalReplayRepository(stale_session).advance(
                    run_id=run_id,
                    expected_artifact_ordinal=0,
                    expected_row_number=1,
                    next_artifact_ordinal=0,
                    next_row_number=2,
                    counters=CanonicalReplayCounters(1, 1, 0, 0, 1, 0),
                    fence=old_fence,
                )
        finally:
            stale_session.close()

        result = PostgresCanonicalReplayJobExecutor(runtime).execute(
            payload=CanonicalReplayJobPayload(run_id=run_id),
            fence=takeover_fence,
            context=_ExecutionContext(takeover_fence),
        )

        assert result.outcome == "succeeded"
        assert result.result == {
            "run_id": str(run_id),
            "artifact_count": 1,
            "rows_seen": 2,
            "rows_matched": 2,
            "rows_filtered_out": 0,
            "duplicates_removed": 0,
            "rows_ingested": 2,
            "existing_convergence": 0,
            "invalid_artifact_rows": 0,
        }
        with runtime.database.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 2
    finally:
        _truncate(runtime)
        runtime.close()
