"""配置目录经过管理员重筛、持久 Job 和 Evidence Owner 的真实回归。"""

from collections.abc import Iterator
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.canonical_replay_http import PostgresCanonicalReplayHttpService
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.contracts.administration import VehicleModelCreateRequest
from aima_ugc.contracts.brand_vehicle import BrandCreateRequest
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.modules.ingestion.canonical_replay_tables import (
    canonical_replay_all_requests_table,
    canonical_replay_content_changes_table,
    canonical_replay_run_artifacts_table,
    canonical_replay_runs_table,
)
from aima_ugc.modules.vehicles.tables import (
    content_brand_evidence_table,
    content_vehicle_evidence_table,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from tests.integration.ingestion.test_canonical_replay_worker import (
    _create_all_replay,
    _create_brand,
    _create_replay_vehicle,
    _import_canonical,
    _principal,
    _runtime,
    _truncate,
    _worker,
)


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[PlatformRuntime]:
    value = _runtime(tmp_path)
    _truncate(value)
    try:
        yield value
    finally:
        _truncate(value)
        value.close()


def _client(runtime: PlatformRuntime) -> TestClient:
    return TestClient(
        create_app(
            import_service=PostgresImportHttpService(runtime),
            canonical_replay_service=PostgresCanonicalReplayHttpService(runtime),
        )
    )


def test_all_replay_deactivates_obsolete_automatic_evidence_without_deleting_content(
    runtime: PlatformRuntime,
) -> None:
    client = _client(runtime)
    brand_id = _create_brand(runtime, alias="星曜")
    _create_replay_vehicle(runtime, brand_id=brand_id)
    _import_canonical(
        client,
        runtime,
        filename="negative-evidence.xlsx",
        rows=(("negative-evidence", "星曜旧规则车型"),),
        brand_ids=(brand_id,),
        expected_rows_ingested=1,
    )
    with runtime.database.new_session() as session:
        alias = PostgresBrandVehicleRepository(session).list_brand_aliases(brand_id)[0]
    PostgresBrandVehicleHttpService(runtime).delete_alias(
        brand_id, alias.id, principal=_principal(), request_id="negative-evidence-delete"
    )
    created = _create_all_replay(client, runtime, idempotency_key=f"negative-{uuid4()}")
    request_id = UUID(cast(str, created["request_id"]))
    with runtime.database.engine.connect() as connection:
        snapshot = connection.scalar(
            select(canonical_replay_all_requests_table.c.filter_snapshot).where(
                canonical_replay_all_requests_table.c.id == request_id
            )
        )
        assert snapshot["catalog"]["resolver_semantics"] == "brand_scoped_vehicle_v2"
    assert _worker(runtime, suffix="negative-evidence").run_once()
    with runtime.database.engine.connect() as connection:
        content_id = connection.scalar(select(contents_table.c.id))
        assert isinstance(content_id, UUID)
        assert (
            connection.scalar(
                select(func.count())
                .select_from(content_vehicle_evidence_table)
                .where(content_vehicle_evidence_table.c.is_active.is_(True))
            )
            == 0
        )
        assert (
            connection.scalar(
                select(func.count())
                .select_from(content_brand_evidence_table)
                .where(content_brand_evidence_table.c.is_active.is_(True))
            )
            == 0
        )
        assert connection.scalar(select(contents_table.c.rule_filter_visible)) is False
        assert connection.scalar(select(func.count()).select_from(content_versions_table)) == 1
        ledger = (
            connection.execute(
                select(canonical_replay_content_changes_table).where(
                    canonical_replay_content_changes_table.c.all_request_id == request_id
                )
            )
            .mappings()
            .one()
        )
        assert ledger["vehicle_evidence_before"]
        assert ledger["vehicle_evidence_after"]
        assert not any(item["is_active"] for item in ledger["vehicle_evidence_after"])


def test_replay_manual_brand_limits_automatic_vehicles(runtime: PlatformRuntime) -> None:
    client = _client(runtime)
    brands = PostgresBrandVehicleHttpService(runtime)
    administration = PostgresAdministrationHttpService(runtime)
    aima = brands.create_brand(
        BrandCreateRequest(display_name="品牌A", role="owned", aliases=("爱玛",)),
        principal=_principal(),
        request_id="manual-scope-a",
    )
    competitor = brands.create_brand(
        BrandCreateRequest(display_name="品牌B", role="competitor", aliases=("竞品",)),
        principal=_principal(),
        request_id="manual-scope-b",
    )
    vehicle_a = administration.create_vehicle_model(
        VehicleModelCreateRequest(display_name="车型A", brand_id=aima.id, aliases=("露娜Air",)),
        principal=_principal(),
        request_id="manual-scope-vehicle-a",
    )
    vehicle_b = administration.create_vehicle_model(
        VehicleModelCreateRequest(display_name="车型B", brand_id=competitor.id, aliases=("竞速X",)),
        principal=_principal(),
        request_id="manual-scope-vehicle-b",
    )
    _import_canonical(
        client,
        runtime,
        filename="manual-scope.xlsx",
        rows=(("manual-scope", "爱玛露娜Air 对比竞品竞速X"),),
        brand_ids=(aima.id,),
        expected_rows_ingested=1,
    )
    with runtime.database.new_session() as session, session.begin():
        content_id = cast(UUID, session.scalar(select(contents_table.c.id)))
        PostgresBrandVehicleRepository(session).replace_manual_brand_evidence(
            content_id=content_id,
            content_version=1,
            brand_ids=(competitor.id,),
            unlock_existing=False,
            actor_ref="reviewer",
        )
    _create_all_replay(client, runtime, idempotency_key=f"manual-scope-{uuid4()}")
    assert _worker(runtime, suffix="manual-scope").run_once()
    with runtime.database.engine.connect() as connection:
        active = set(
            connection.scalars(
                select(content_vehicle_evidence_table.c.vehicle_model_id).where(
                    content_vehicle_evidence_table.c.is_active.is_(True)
                )
            )
        )
        assert active == {vehicle_b.id}
        assert vehicle_a.id not in active
        assert set(
            connection.scalars(
                select(content_brand_evidence_table.c.brand_id).where(
                    content_brand_evidence_table.c.is_active.is_(True)
                )
            )
        ) == {competitor.id}


def test_normal_import_carries_manual_brand_lock_to_new_current_version(
    runtime: PlatformRuntime,
) -> None:
    client = _client(runtime)
    a = _create_brand(runtime, alias="星曜")
    b = (
        PostgresBrandVehicleHttpService(runtime)
        .create_brand(
            BrandCreateRequest(display_name="人工品牌", role="competitor", aliases=("人工词",)),
            principal=_principal(),
            request_id="normal-manual-brand",
        )
        .id
    )
    _create_replay_vehicle(runtime, brand_id=a)
    _import_canonical(
        client,
        runtime,
        filename="normal-manual-first.xlsx",
        rows=(("normal-manual", "星曜车型"),),
        brand_ids=(a,),
        expected_rows_ingested=1,
    )
    with runtime.database.new_session() as session, session.begin():
        content_id = session.scalar(select(contents_table.c.id))
        assert isinstance(content_id, UUID)
        PostgresBrandVehicleRepository(session).replace_manual_brand_evidence(
            content_id=content_id,
            content_version=1,
            brand_ids=(b,),
            unlock_existing=False,
            actor_ref="normal-manual-review",
        )
    _import_canonical(
        client,
        runtime,
        filename="normal-manual-second.xlsx",
        rows=(("normal-manual", "星曜车型新正文"),),
        brand_ids=(a,),
        expected_rows_ingested=1,
    )
    with runtime.database.engine.connect() as connection:
        assert connection.scalar(select(contents_table.c.current_version)) == 2
        assert set(
            connection.scalars(
                select(content_brand_evidence_table.c.brand_id).where(
                    content_brand_evidence_table.c.content_version == 2,
                    content_brand_evidence_table.c.is_active.is_(True),
                )
            )
        ) == {b}
        assert not tuple(
            connection.scalars(
                select(content_vehicle_evidence_table.c.vehicle_model_id).where(
                    content_vehicle_evidence_table.c.content_version == 2,
                    content_vehicle_evidence_table.c.is_active.is_(True),
                )
            )
        )


def test_database_configured_multi_brand_models_project_and_filter_as_complete_sets(
    runtime: PlatformRuntime,
) -> None:
    from aima_ugc.bootstrap.content_http import PostgresContentHttpService
    from aima_ugc.contracts.http import ContentListQuery
    from aima_ugc.modules.content.read_model_tables import voice_plaza_content_projection_table

    client = _client(runtime)
    a = _create_brand(runtime, alias="星曜")
    ma = _create_replay_vehicle(runtime, brand_id=a)
    b = (
        PostgresBrandVehicleHttpService(runtime)
        .create_brand(
            BrandCreateRequest(display_name="竞品配置品牌", role="competitor", aliases=("竞品",)),
            principal=_principal(),
            request_id="multi-brand-db",
        )
        .id
    )
    mb = (
        PostgresAdministrationHttpService(runtime)
        .create_vehicle_model(
            VehicleModelCreateRequest(display_name="竞品配置车型", brand_id=b, aliases=("竞品X",)),
            principal=_principal(),
            request_id="multi-model-db",
        )
        .id
    )
    _import_canonical(
        client,
        runtime,
        filename="multi-projection.xlsx",
        rows=(("multi-projection", "星曜车型 对比竞品X"),),
        brand_ids=(a, b),
        expected_rows_ingested=1,
    )
    with runtime.database.engine.connect() as connection:
        row = connection.execute(select(voice_plaza_content_projection_table)).mappings().one()
        assert set(row["brand_ids"]) == {a, b}
        assert set(row["vehicle_model_ids"]) == {ma, mb}
        assert row["competition_scope"] == "mixed"
    service = PostgresContentHttpService(
        runtime, cursor_signing_secret=b"brand-query-secret-is-32-bytes-ok"
    )
    for query in (
        ContentListQuery(brand_ids=(a, b)),
        ContentListQuery(brand_ids=(a,)),
        ContentListQuery(brand_ids=(b,)),
        ContentListQuery(vehicle_model_ids=(ma, mb)),
        ContentListQuery(vehicle_model_ids=(ma,)),
        ContentListQuery(vehicle_model_ids=(mb,)),
        ContentListQuery(competition_scopes=("competitor_only", "mixed")),
    ):
        assert len(service.list_contents(query).items) == 1
    assert (
        service.list_contents(ContentListQuery(competition_scopes=("competitor_only",))).items == ()
    )


def test_frozen_legacy_replay_keeps_model_inference_and_idempotency_after_v2_deploy(
    runtime: PlatformRuntime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aima_ugc.adapters.persistence.postgres import brand_vehicle as catalog_module
    from aima_ugc.adapters.persistence.postgres import canonical_replay as replay_repository_module

    client = _client(runtime)
    brand = _create_brand(runtime, alias="不匹配的配置品牌")
    _import_canonical(
        client,
        runtime,
        filename="legacy-freeze.xlsx",
        rows=(("legacy-freeze", "星曜车型"),),
        brand_ids=(brand,),
    )
    model = _create_replay_vehicle(runtime, brand_id=brand)
    key = f"legacy-freeze-{uuid4()}"
    # 以原生产目录语义创建旧任务；退出上下文后模拟新版已部署。
    with monkeypatch.context() as legacy:
        legacy.setattr(catalog_module, "CURRENT_RESOLVER_SEMANTICS", "field_priority_v1")
        legacy.setattr(replay_repository_module, "CURRENT_RESOLVER_SEMANTICS", "field_priority_v1")
        created = _create_all_replay(client, runtime, idempotency_key=key)
    duplicate = client.post("/api/v1/canonical-replays/all", json={"idempotency_key": key})
    assert duplicate.status_code == 202
    assert duplicate.json()["request_id"] == created["request_id"]
    with runtime.database.engine.connect() as connection:
        frozen = connection.scalar(
            select(canonical_replay_all_requests_table.c.filter_snapshot).where(
                canonical_replay_all_requests_table.c.id == UUID(str(created["request_id"]))
            )
        )
        assert "resolver_semantics" not in frozen["catalog"]
    assert _worker(runtime, suffix="legacy-freeze").run_once()
    with runtime.database.engine.connect() as connection:
        assert connection.scalar(select(content_vehicle_evidence_table.c.vehicle_model_id)) == model
        assert connection.scalar(select(content_brand_evidence_table.c.source)) == "vehicle_match"
    newer = _create_all_replay(client, runtime, idempotency_key=f"new-freeze-{uuid4()}")
    assert newer["request_id"] != created["request_id"]
    assert _worker(runtime, suffix="v2-freeze").run_once()
    with runtime.database.engine.connect() as connection:
        assert not tuple(
            connection.scalars(
                select(content_vehicle_evidence_table.c.vehicle_model_id).where(
                    content_vehicle_evidence_table.c.is_active.is_(True)
                )
            )
        )


@pytest.mark.parametrize(
    ("source_field", "remains_active"),
    [
        ("title", False),
        ("raw_text", False),
        ("transcript_text", False),
        ("title_text", False),
        ("vehicle_model", True),
        (None, True),
    ],
)
def test_negative_replay_distinguishes_legacy_text_matches_from_explicit_import_facts(
    runtime: PlatformRuntime,
    source_field: str | None,
    remains_active: bool,
) -> None:
    client = _client(runtime)
    brand = _create_brand(runtime, alias="星曜")
    _create_replay_vehicle(runtime, brand_id=brand)
    _import_canonical(
        client,
        runtime,
        filename="legacy-import.xlsx",
        rows=(("legacy-import", "星曜车型"),),
        brand_ids=(brand,),
        expected_rows_ingested=1,
    )
    with runtime.database.new_session() as session, session.begin():
        session.execute(
            update(content_vehicle_evidence_table).values(
                source="import", source_field=source_field
            )
        )
        alias = PostgresBrandVehicleRepository(session).list_brand_aliases(brand)[0]
    PostgresBrandVehicleHttpService(runtime).delete_alias(
        brand, alias.id, principal=_principal(), request_id="legacy-import-remove-alias"
    )
    _create_all_replay(client, runtime, idempotency_key=f"legacy-import-{uuid4()}")
    assert _worker(runtime, suffix="legacy-import").run_once()
    with runtime.database.engine.connect() as connection:
        assert (
            connection.scalar(select(content_vehicle_evidence_table.c.is_active)) is remains_active
        )


def test_negative_replay_revoke_restores_evidence_without_new_content_version(
    runtime: PlatformRuntime,
) -> None:
    client = _client(runtime)
    brand = _create_brand(runtime, alias="星曜")
    _create_replay_vehicle(runtime, brand_id=brand)
    _import_canonical(
        client,
        runtime,
        filename="negative-revoke.xlsx",
        rows=(("negative-revoke", "星曜车型"),),
        brand_ids=(brand,),
        expected_rows_ingested=1,
    )
    with runtime.database.new_session() as session:
        alias = PostgresBrandVehicleRepository(session).list_brand_aliases(brand)[0]
    PostgresBrandVehicleHttpService(runtime).delete_alias(
        brand, alias.id, principal=_principal(), request_id="negative-revoke-remove"
    )
    created = _create_all_replay(client, runtime, idempotency_key=f"negative-revoke-{uuid4()}")
    request_id = created["request_id"]
    assert _worker(runtime, suffix="negative-revoke-run").run_once()
    assert client.post(f"/api/v1/canonical-replays/all/{request_id}/revoke").status_code == 202
    assert _worker(runtime, suffix="negative-revoke-restore").run_once()
    with runtime.database.engine.connect() as connection:
        assert connection.scalar(select(content_vehicle_evidence_table.c.is_active)) is True
        assert connection.scalar(select(content_brand_evidence_table.c.is_active)) is True
        assert connection.scalar(select(func.count()).select_from(content_versions_table)) == 1
        assert connection.scalar(select(contents_table.c.replay_visibility_owner_id)) is None


def test_older_replay_cannot_restore_evidence_after_newer_negative_replay(
    runtime: PlatformRuntime,
) -> None:
    from aima_ugc.platform.jobs.tables import jobs_table
    from sqlalchemy import text

    client = _client(runtime)
    brand = _create_brand(runtime, alias="星曜")
    _create_replay_vehicle(runtime, brand_id=brand)
    _import_canonical(
        client,
        runtime,
        filename="older-replay.xlsx",
        rows=(("older-replay", "星曜车型"),),
        brand_ids=(brand,),
        expected_rows_ingested=1,
    )
    older = _create_all_replay(client, runtime, idempotency_key=f"older-{uuid4()}")
    with runtime.database.new_session() as session, session.begin():
        older_job = session.scalar(
            select(canonical_replay_runs_table.c.job_id).where(
                canonical_replay_runs_table.c.all_request_id == UUID(str(older["request_id"]))
            )
        )
        assert isinstance(older_job, UUID)
        session.execute(
            update(jobs_table)
            .where(jobs_table.c.id == older_job)
            .values(available_at=text("clock_timestamp() + interval '5 minutes'"))
        )
        alias = PostgresBrandVehicleRepository(session).list_brand_aliases(brand)[0]
    PostgresBrandVehicleHttpService(runtime).delete_alias(
        brand, alias.id, principal=_principal(), request_id="older-replay-remove"
    )
    newer = _create_all_replay(client, runtime, idempotency_key=f"newer-{uuid4()}")
    assert _worker(runtime, suffix="newer-negative").run_once()
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(jobs_table)
            .where(jobs_table.c.id == older_job)
            .values(available_at=text("clock_timestamp()"))
        )
    assert _worker(runtime, suffix="older-positive").run_once()
    with runtime.database.engine.connect() as connection:
        assert connection.scalar(select(content_vehicle_evidence_table.c.is_active)) is False
        assert connection.scalar(select(content_brand_evidence_table.c.is_active)) is False
        assert connection.scalar(select(contents_table.c.replay_visibility_owner_id)) == UUID(
            str(newer["request_id"])
        )


def test_replay_classifies_current_text_instead_of_older_positive_raw(
    runtime: PlatformRuntime,
) -> None:
    from datetime import timedelta

    from aima_ugc.platform.time import beijing_now

    client = _client(runtime)
    brand = _create_brand(runtime, alias="星曜")
    model = _create_replay_vehicle(runtime, brand_id=brand)
    _import_canonical(
        client,
        runtime,
        filename="old-positive.xlsx",
        rows=(("current-not-raw", "星曜车型"),),
        brand_ids=(brand,),
        expected_rows_ingested=1,
    )
    # 模拟已经由较新来源提交的 Current；旧 Raw 的 observed_at 不得逆转新正文。
    with runtime.database.new_session() as session, session.begin():
        session.execute(
            update(contents_table).values(
                title="无关内容",
                field_observed_at={"title": (beijing_now() + timedelta(days=1)).isoformat()},
            )
        )
    _create_all_replay(client, runtime, idempotency_key=f"current-not-raw-{uuid4()}")
    assert _worker(runtime, suffix="current-not-raw").run_once()
    with runtime.database.engine.connect() as connection:
        assert connection.scalar(select(contents_table.c.title)) == "无关内容"
        assert not tuple(
            connection.scalars(
                select(content_vehicle_evidence_table.c.vehicle_model_id).where(
                    content_vehicle_evidence_table.c.is_active.is_(True)
                )
            )
        )
        assert model is not None


@pytest.mark.parametrize("later_normal_write", [False, True])
def test_negative_then_positive_preserves_continuous_or_newer_external_baseline(
    runtime: PlatformRuntime,
    monkeypatch: pytest.MonkeyPatch,
    later_normal_write: bool,
) -> None:
    client = _client(runtime)
    a = _create_brand(runtime, alias="占位")
    b = (
        PostgresBrandVehicleHttpService(runtime)
        .create_brand(
            BrandCreateRequest(display_name="当前品牌", role="competitor", aliases=("星曜",)),
            principal=_principal(),
            request_id="chain-brand",
        )
        .id
    )
    _create_replay_vehicle(runtime, brand_id=b)
    negative_artifact = _import_canonical(
        client,
        runtime,
        filename="chain-negative.xlsx",
        rows=(("chain-content", "占位旧正文"),),
        brand_ids=(a,),
        expected_rows_ingested=1,
    )
    positive_artifact = _import_canonical(
        client,
        runtime,
        filename="chain-positive.xlsx",
        rows=(("chain-content", "星曜当前车型"),),
        brand_ids=(b,),
        expected_rows_ingested=1,
    )
    with runtime.database.new_session() as session:
        alias = PostgresBrandVehicleRepository(session).list_brand_aliases(a)[0]
    PostgresBrandVehicleHttpService(runtime).delete_alias(
        a, alias.id, principal=_principal(), request_id="chain-remove-old"
    )
    created = _create_all_replay(client, runtime, idempotency_key=f"chain-{uuid4()}")
    request = UUID(str(created["request_id"]))
    with runtime.database.engine.begin() as connection:
        run_ids = select(canonical_replay_runs_table.c.id).where(
            canonical_replay_runs_table.c.all_request_id == request
        )
        connection.execute(
            update(canonical_replay_run_artifacts_table)
            .where(canonical_replay_run_artifacts_table.c.run_id.in_(run_ids))
            .values(ordinal=canonical_replay_run_artifacts_table.c.ordinal + 10000)
        )
        for ordinal, artifact_id in enumerate((negative_artifact, positive_artifact)):
            connection.execute(
                update(canonical_replay_run_artifacts_table)
                .where(
                    canonical_replay_run_artifacts_table.c.run_id.in_(run_ids),
                    canonical_replay_run_artifacts_table.c.artifact_id == artifact_id,
                )
                .values(ordinal=ordinal)
            )
    from aima_ugc.bootstrap import canonical_replay_worker as replay_module

    original_partition = replay_module._partition_resolved_batch

    def partition(resolved, *, matched_target_rows, raw_limit_rows=None):  # type: ignore[no-untyped-def]
        del raw_limit_rows
        return original_partition(
            resolved, matched_target_rows=matched_target_rows, raw_limit_rows=1
        )

    monkeypatch.setattr(replay_module, "_partition_resolved_batch", partition)
    original_ingest = replay_module.PostgresCanonicalReplayJobExecutor._ingest_batch
    intervened = []

    def ingest(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        result = original_ingest(self, *args, **kwargs)
        if later_normal_write and not intervened:
            with runtime.database.engine.connect() as connection:
                owner = connection.scalar(select(contents_table.c.replay_visibility_owner_id))
            assert owner == request  # 首个负向批次已提交，第二个正向批次尚未写入。
            intervened.append(True)
            _import_canonical(
                client,
                runtime,
                filename="chain-normal.xlsx",
                rows=(("chain-content", "星曜正常写入"),),
                brand_ids=(b,),
                expected_rows_ingested=1,
            )
        return result

    monkeypatch.setattr(replay_module.PostgresCanonicalReplayJobExecutor, "_ingest_batch", ingest)
    assert _worker(runtime, suffix="chain-run").run_once()
    with runtime.database.engine.connect() as connection:
        row = (
            connection.execute(
                select(canonical_replay_content_changes_table).where(
                    canonical_replay_content_changes_table.c.all_request_id == request
                )
            )
            .mappings()
            .one()
        )
        assert row["delta"]["resolver_outcome"] == "matched"
        if later_normal_write:
            assert intervened == [True]
            assert row["delta"]["classification_preserved"] is True
            assert row["visibility_owner_before"] is None
        else:
            assert row["visibility_owner_before"] is None
            assert row["version_before"] == row["version_after"] == 2
    assert client.post(f"/api/v1/canonical-replays/all/{request}/revoke").status_code == 202
    assert _worker(runtime, suffix="chain-revoke").run_once()
    with runtime.database.engine.connect() as connection:
        assert connection.scalar(select(contents_table.c.title)) == (
            "星曜正常写入" if later_normal_write else "星曜当前车型"
        )
        assert connection.scalar(select(contents_table.c.current_version)) == (
            3 if later_normal_write else 2
        )
        assert tuple(
            connection.scalars(
                select(content_vehicle_evidence_table.c.vehicle_model_id).where(
                    content_vehicle_evidence_table.c.is_active.is_(True)
                )
            )
        )
