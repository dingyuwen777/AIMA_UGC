from __future__ import annotations

from pathlib import Path


def _replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact match, got {count}")
    return text.replace(old, new, 1)


def _patch_single_file() -> None:
    path = Path("tests/integration/ingestion/test_stage8b_import_http_worker.py")
    text = path.read_text(encoding="utf-8")
    marker = "def test_stage3_import_freezes_catalog_and_preserves_manual_evidence"
    if marker in text:
        raise RuntimeError("single-file Stage 3 evidence regression already exists")
    text = _replace_once(
        text,
        "from aima_ugc.adapters.persistence.postgres.collection_targets import PostgresCollectionTargetReader\n"
        "from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository\n",
        "from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository\n"
        "from aima_ugc.adapters.persistence.postgres.collection_targets import PostgresCollectionTargetReader\n"
        "from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository\n"
        "from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository\n",
        label="single repositories imports",
    )
    text = _replace_once(
        text,
        "from aima_ugc.bootstrap.api import create_app\n",
        "from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService\n"
        "from aima_ugc.bootstrap.api import create_app\n",
        label="single administration service import",
    )
    text = _replace_once(
        text,
        "from aima_ugc.contracts.brand_vehicle import BrandCreateRequest\n",
        "from aima_ugc.contracts.administration import (\n"
        "    VehicleModelCreateRequest,\n"
        "    VehicleModelUpdateRequest,\n"
        ")\n"
        "from aima_ugc.contracts.brand_vehicle import BrandCreateRequest\n",
        label="single administration contracts import",
    )
    text = _replace_once(
        text,
        "from aima_ugc.modules.ingestion.tables import processing_import_batches_table\n",
        "from aima_ugc.modules.ingestion.tables import processing_import_batches_table\n"
        "from aima_ugc.modules.vehicles.tables import (\n"
        "    content_brand_evidence_table,\n"
        "    content_brand_review_locks_table,\n"
        "    content_vehicle_evidence_table,\n"
        "    content_vehicle_review_locks_table,\n"
        ")\n",
        label="single evidence tables import",
    )
    text += r'''


def _stage3_evidence_workbook() -> bytes:
    """构造同时命中品牌与 Q7 车型的 Stage 3 固定输入。"""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文章"
    sheet.append(["媒体名称（中文）", "标题", "内文", "作者", "出版日期", "原文链接"])
    sheet.append(
        [
            "小红书",
            "爱玛 Q7 冻结目录验证",
            "同一内容用于验证自动证据不会覆盖人工锁。",
            "官方账号",
            "2026-08-20 12:00:00",
            "https://www.xiaohongshu.com/explore/stage3-evidence-content",
        ]
    )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _stage3_evidence_catalog(runtime) -> tuple[UUID, UUID]:  # type: ignore[no-untyped-def]
    """通过正式 Stage 2 Application Service 建立爱玛 + Q7 目录。"""

    brand = PostgresBrandVehicleHttpService(runtime).create_brand(
        BrandCreateRequest(
            code="AIMA-STAGE3-EVIDENCE",
            display_name="爱玛",
            role="owned",
            aliases=("爱玛",),
        ),
        principal=_principal(),
        request_id="stage3-evidence-brand",
    )
    vehicle = PostgresAdministrationHttpService(runtime).create_vehicle_model(
        VehicleModelCreateRequest(
            code="AIMA-STAGE3-EVIDENCE-Q7",
            display_name="Q7",
            brand_id=brand.id,
            aliases=("Q7",),
        ),
        principal=_principal(),
        request_id="stage3-evidence-vehicle",
    )
    return brand.id, vehicle.id


def _stage3_upload_evidence_batch(client: TestClient, *, brand_id: UUID) -> Response:
    """从正式公开入口创建一个冻结 Brand/Vehicle Snapshot 的单文件任务。"""

    created = client.post(
        "/api/v1/import-batches",
        files=[
            (
                "file",
                (
                    "stage3-evidence.xlsx",
                    _stage3_evidence_workbook(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            ),
            ("brand_ids", (None, str(brand_id))),
        ],
    )
    assert created.status_code == 202
    return created


def _stage3_update_vehicle_alias(runtime, vehicle_id: UUID, alias: str) -> int:  # type: ignore[no-untyped-def]
    """通过正式管理员 Service 修改 live alias，并返回新目录版本。"""

    updated = PostgresAdministrationHttpService(runtime).update_vehicle_model(
        vehicle_id,
        VehicleModelUpdateRequest(aliases=(alias,)),
        principal=_principal(),
        request_id=f"stage3-evidence-alias-{alias}",
    )
    return updated.catalog_version


def _stage3_lock_manual_evidence(
    runtime,
    *,
    content_id: UUID,
    content_version: int,
    brand_id: UUID,
    vehicle_id: UUID,
) -> None:  # type: ignore[no-untyped-def]
    """用正式 Owner Repository 对同一 Content Version 建立 Brand/Vehicle 人工锁。"""

    session = runtime.database.new_session()
    try:
        with session.begin():
            PostgresBrandVehicleRepository(session).replace_manual_brand_evidence(
                content_id=content_id,
                content_version=content_version,
                brand_ids=(brand_id,),
                unlock_existing=False,
                actor_ref="stage3-evidence-reviewer",
            )
            PostgresVehicleCatalogRepository(session).replace_manual_evidence(
                content_id=content_id,
                content_version=content_version,
                model_ids=(vehicle_id,),
                unlock_existing=False,
                actor_ref="stage3-evidence-reviewer",
            )
    finally:
        session.close()


def test_stage3_import_freezes_catalog_and_preserves_manual_evidence(tmp_path: Path) -> None:
    """live alias 漂移后仍按冻结 Snapshot 写证据；同版本重放不得覆盖人工锁。"""

    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    runtime = create_worker_runtime(settings=settings)
    _truncate(runtime)
    try:
        client = TestClient(create_app(import_service=PostgresImportHttpService(runtime)))
        brand_id, vehicle_id = _stage3_evidence_catalog(runtime)
        created = _stage3_upload_evidence_batch(client, brand_id=brand_id)
        with runtime.database.engine.begin() as connection:
            payload = connection.scalar(
                select(jobs_table.c.payload).where(
                    jobs_table.c.id == UUID(created.json()["job_id"])
                )
            )
        assert payload is not None
        frozen_snapshot = payload["filter_snapshot"]
        frozen_catalog_version = frozen_snapshot["catalog"]["catalog_version"]
        assert frozen_snapshot["schema_version"] == "brand-vehicle-filter.v1"

        changed_catalog_version = _stage3_update_vehicle_alias(runtime, vehicle_id, "Q7CHANGED")
        assert changed_catalog_version > frozen_catalog_version

        worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="stage3-evidence-worker",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        assert worker.run_once() is True
        batch = client.get(f"/api/v1/import-batches/{created.json()['batch_id']}")
        assert batch.status_code == 200
        assert batch.json()["status"] == "succeeded"

        with runtime.database.engine.begin() as connection:
            content_id, content_version = connection.execute(
                select(contents_table.c.id, contents_table.c.current_version)
            ).one()
            vehicle_rows = tuple(
                connection.execute(
                    select(content_vehicle_evidence_table).where(
                        content_vehicle_evidence_table.c.content_id == content_id,
                        content_vehicle_evidence_table.c.content_version == content_version,
                        content_vehicle_evidence_table.c.is_active.is_(True),
                    )
                ).mappings()
            )
            brand_rows = tuple(
                connection.execute(
                    select(content_brand_evidence_table).where(
                        content_brand_evidence_table.c.content_id == content_id,
                        content_brand_evidence_table.c.content_version == content_version,
                        content_brand_evidence_table.c.is_active.is_(True),
                    )
                ).mappings()
            )
        assert len(vehicle_rows) == 1
        assert vehicle_rows[0]["vehicle_model_id"] == vehicle_id
        assert vehicle_rows[0]["source"] == "import"
        assert vehicle_rows[0]["matched_text"] == "Q7"
        assert vehicle_rows[0]["catalog_version"] == frozen_catalog_version
        assert len(brand_rows) == 1
        assert brand_rows[0]["brand_id"] == brand_id
        assert brand_rows[0]["source"] == "vehicle_match"
        assert brand_rows[0]["derived_vehicle_model_id"] == vehicle_id
        assert brand_rows[0]["catalog_version"] == frozen_catalog_version

        _stage3_lock_manual_evidence(
            runtime,
            content_id=content_id,
            content_version=content_version,
            brand_id=brand_id,
            vehicle_id=vehicle_id,
        )
        restored_catalog_version = _stage3_update_vehicle_alias(runtime, vehicle_id, "Q7")
        assert restored_catalog_version > changed_catalog_version

        replay = _stage3_upload_evidence_batch(client, brand_id=brand_id)
        assert worker.run_once() is True
        replay_batch = client.get(f"/api/v1/import-batches/{replay.json()['batch_id']}")
        assert replay_batch.status_code == 200
        assert replay_batch.json()["status"] == "succeeded"

        with runtime.database.engine.begin() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 1
            assert connection.scalar(select(contents_table.c.current_version)) == content_version
            active_vehicle_rows = tuple(
                connection.execute(
                    select(content_vehicle_evidence_table).where(
                        content_vehicle_evidence_table.c.content_id == content_id,
                        content_vehicle_evidence_table.c.content_version == content_version,
                        content_vehicle_evidence_table.c.is_active.is_(True),
                    )
                ).mappings()
            )
            active_brand_rows = tuple(
                connection.execute(
                    select(content_brand_evidence_table).where(
                        content_brand_evidence_table.c.content_id == content_id,
                        content_brand_evidence_table.c.content_version == content_version,
                        content_brand_evidence_table.c.is_active.is_(True),
                    )
                ).mappings()
            )
            vehicle_locked = connection.scalar(
                select(content_vehicle_review_locks_table.c.is_locked).where(
                    content_vehicle_review_locks_table.c.content_id == content_id,
                    content_vehicle_review_locks_table.c.content_version == content_version,
                )
            )
            brand_locked = connection.scalar(
                select(content_brand_review_locks_table.c.is_locked).where(
                    content_brand_review_locks_table.c.content_id == content_id,
                    content_brand_review_locks_table.c.content_version == content_version,
                )
            )
        assert [(row["source"], row["is_manual_locked"]) for row in active_vehicle_rows] == [
            ("manual_review", True)
        ]
        assert [(row["source"], row["is_manual_locked"]) for row in active_brand_rows] == [
            ("manual_review", True)
        ]
        assert vehicle_locked is True
        assert brand_locked is True
    finally:
        _truncate(runtime)
        runtime.close()
'''
    path.write_text(text, encoding="utf-8")


def _patch_historical() -> None:
    path = Path("tests/integration/ingestion/test_stage12_historical_campaign_worker.py")
    text = path.read_text(encoding="utf-8")
    marker = "def test_historical_stage3_freezes_catalog_and_preserves_manual_evidence"
    if marker in text:
        raise RuntimeError("historical Stage 3 evidence regression already exists")
    text = _replace_once(
        text,
        "from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository\n",
        "from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository\n"
        "from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository\n"
        "from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository\n",
        label="historical repositories imports",
    )
    text = _replace_once(
        text,
        "from aima_ugc.bootstrap.api import create_app\n",
        "from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService\n"
        "from aima_ugc.bootstrap.api import create_app\n",
        label="historical administration service import",
    )
    text = _replace_once(
        text,
        "from aima_ugc.contracts.brand_vehicle import BrandCreateRequest\n",
        "from aima_ugc.contracts.administration import (\n"
        "    VehicleModelCreateRequest,\n"
        "    VehicleModelUpdateRequest,\n"
        ")\n"
        "from aima_ugc.contracts.brand_vehicle import BrandCreateRequest\n",
        label="historical administration contracts import",
    )
    text = _replace_once(
        text,
        "from aima_ugc.modules.ingestion.historical_tables import (\n"
        "    historical_import_campaign_items_table,\n",
        "from aima_ugc.modules.ingestion.historical_tables import (\n"
        "    historical_import_campaign_items_table,\n"
        "    historical_import_campaigns_table,\n",
        label="historical campaigns table import",
    )
    text = _replace_once(
        text,
        "from aima_ugc.modules.ingestion.tables import processing_import_batches_table\n",
        "from aima_ugc.modules.ingestion.tables import processing_import_batches_table\n"
        "from aima_ugc.modules.vehicles.tables import (\n"
        "    content_brand_evidence_table,\n"
        "    content_brand_review_locks_table,\n"
        "    content_vehicle_evidence_table,\n"
        "    content_vehicle_review_locks_table,\n"
        ")\n",
        label="historical evidence tables import",
    )
    text += r'''


def _stage3_historical_evidence_catalog(runtime: PlatformRuntime) -> tuple[UUID, UUID]:
    """通过正式 Stage 2 Application Service 建立 Historical 验收目录。"""

    brand = PostgresBrandVehicleHttpService(runtime).create_brand(
        BrandCreateRequest(
            code="AIMA-STAGE3-HISTORICAL-EVIDENCE",
            display_name="爱玛",
            role="owned",
            aliases=("爱玛",),
        ),
        principal=_principal(),
        request_id="stage3-historical-evidence-brand",
    )
    vehicle = PostgresAdministrationHttpService(runtime).create_vehicle_model(
        VehicleModelCreateRequest(
            code="AIMA-STAGE3-HISTORICAL-Q7",
            display_name="Q7",
            brand_id=brand.id,
            aliases=("Q7",),
        ),
        principal=_principal(),
        request_id="stage3-historical-evidence-vehicle",
    )
    return brand.id, vehicle.id


def _stage3_historical_update_alias(
    runtime: PlatformRuntime, vehicle_id: UUID, alias: str
) -> int:
    """通过正式管理员 Service 修改 live alias，并返回新目录版本。"""

    updated = PostgresAdministrationHttpService(runtime).update_vehicle_model(
        vehicle_id,
        VehicleModelUpdateRequest(aliases=(alias,)),
        principal=_principal(),
        request_id=f"stage3-historical-evidence-alias-{alias}",
    )
    return updated.catalog_version


def _stage3_historical_lock_evidence(
    runtime: PlatformRuntime,
    *,
    content_id: UUID,
    content_version: int,
    brand_id: UUID,
    vehicle_id: UUID,
) -> None:
    """在同一 Content Version 上锁定 Brand/Vehicle 人工结论。"""

    session = runtime.database.new_session()
    try:
        with session.begin():
            PostgresBrandVehicleRepository(session).replace_manual_brand_evidence(
                content_id=content_id,
                content_version=content_version,
                brand_ids=(brand_id,),
                unlock_existing=False,
                actor_ref="stage3-historical-evidence-reviewer",
            )
            PostgresVehicleCatalogRepository(session).replace_manual_evidence(
                content_id=content_id,
                content_version=content_version,
                model_ids=(vehicle_id,),
                unlock_existing=False,
                actor_ref="stage3-historical-evidence-reviewer",
            )
    finally:
        session.close()


def _stage3_run_historical_campaign(
    client: TestClient,
    worker,
    *,
    campaign_id: str,
) -> dict[str, object]:  # type: ignore[no-untyped-def]
    """把一个单文件 Historical Campaign 从 discovering 驱动到终态。"""

    for _ in range(10):
        response = client.get(f"/api/v1/historical-import-campaigns/{campaign_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] == "ready":
            break
        assert payload["status"] in {"discovering", "snapshotting"}
        assert worker.run_once() is True
    else:
        pytest.fail("Historical Campaign 未在测试预算内进入 ready")

    started = client.post(f"/api/v1/historical-import-campaigns/{campaign_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "queued"
    for _ in range(10):
        response = client.get(f"/api/v1/historical-import-campaigns/{campaign_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"succeeded", "partial_failed", "failed", "cancelled"}:
            return payload
        assert worker.run_once() is True
    pytest.fail("Historical Campaign 未在测试预算内进入终态")


def test_historical_stage3_freezes_catalog_and_preserves_manual_evidence(
    tmp_path: Path,
) -> None:
    """Historical 用冻结目录写 Evidence；同版本再次 Campaign 不覆盖人工锁。"""

    historical_root = tmp_path / "approved-history"
    historical_root.mkdir()
    (historical_root / "stage3-evidence.xlsx").write_bytes(
        _xlsx(title="爱玛 Q7 历史冻结目录验证", text="Historical Evidence 固定正文")
    )
    settings = load_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "log_dir": tmp_path / "logs",
            "historical_import_root": historical_root,
            "historical_chunk_rows": 100,
            "historical_max_in_flight_jobs": 1,
        }
    )
    runtime = create_worker_runtime(settings=settings)
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, "
            "accounts RESTART IDENTITY CASCADE"
        )
    try:
        client = TestClient(
            create_app(
                historical_import_service=PostgresHistoricalImportHttpService(runtime),
                import_service=PostgresImportHttpService(runtime),
            )
        )
        brand_id, vehicle_id = _stage3_historical_evidence_catalog(runtime)
        created = client.post(
            "/api/v1/historical-import-campaigns",
            json={
                "client_idempotency_key": f"stage3-historical-evidence-{uuid4()}",
                "relative_paths": ["stage3-evidence.xlsx"],
                "recursive": False,
                "brand_ids": [str(brand_id)],
            },
        )
        assert created.status_code == 202
        campaign_id = created.json()["campaign_id"]
        with runtime.database.engine.begin() as connection:
            frozen_snapshot = connection.scalar(
                select(historical_import_campaigns_table.c.keyword_pack_snapshot).where(
                    historical_import_campaigns_table.c.id == UUID(campaign_id)
                )
            )
        assert frozen_snapshot is not None
        frozen_catalog_version = frozen_snapshot["catalog"]["catalog_version"]
        assert frozen_snapshot["schema_version"] == "brand-vehicle-filter.v1"

        changed_catalog_version = _stage3_historical_update_alias(
            runtime, vehicle_id, "Q7CHANGED"
        )
        assert changed_catalog_version > frozen_catalog_version
        worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="stage3-historical-evidence-worker",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        completed = _stage3_run_historical_campaign(
            client,
            worker,
            campaign_id=campaign_id,
        )
        assert completed["status"] == "succeeded"

        with runtime.database.engine.begin() as connection:
            content_id, content_version = connection.execute(
                select(contents_table.c.id, contents_table.c.current_version)
            ).one()
            vehicle_rows = tuple(
                connection.execute(
                    select(content_vehicle_evidence_table).where(
                        content_vehicle_evidence_table.c.content_id == content_id,
                        content_vehicle_evidence_table.c.content_version == content_version,
                        content_vehicle_evidence_table.c.is_active.is_(True),
                    )
                ).mappings()
            )
            brand_rows = tuple(
                connection.execute(
                    select(content_brand_evidence_table).where(
                        content_brand_evidence_table.c.content_id == content_id,
                        content_brand_evidence_table.c.content_version == content_version,
                        content_brand_evidence_table.c.is_active.is_(True),
                    )
                ).mappings()
            )
        assert len(vehicle_rows) == 1
        assert vehicle_rows[0]["vehicle_model_id"] == vehicle_id
        assert vehicle_rows[0]["source"] == "import"
        assert vehicle_rows[0]["matched_text"] == "Q7"
        assert vehicle_rows[0]["catalog_version"] == frozen_catalog_version
        assert len(brand_rows) == 1
        assert brand_rows[0]["brand_id"] == brand_id
        assert brand_rows[0]["source"] == "vehicle_match"
        assert brand_rows[0]["derived_vehicle_model_id"] == vehicle_id
        assert brand_rows[0]["catalog_version"] == frozen_catalog_version

        _stage3_historical_lock_evidence(
            runtime,
            content_id=content_id,
            content_version=content_version,
            brand_id=brand_id,
            vehicle_id=vehicle_id,
        )
        restored_catalog_version = _stage3_historical_update_alias(runtime, vehicle_id, "Q7")
        assert restored_catalog_version > changed_catalog_version

        replay = client.post(
            "/api/v1/historical-import-campaigns",
            json={
                "client_idempotency_key": f"stage3-historical-evidence-replay-{uuid4()}",
                "relative_paths": ["stage3-evidence.xlsx"],
                "recursive": False,
                "brand_ids": [str(brand_id)],
            },
        )
        assert replay.status_code == 202
        replay_completed = _stage3_run_historical_campaign(
            client,
            worker,
            campaign_id=replay.json()["campaign_id"],
        )
        assert replay_completed["status"] == "succeeded"

        with runtime.database.engine.begin() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 1
            assert connection.scalar(select(contents_table.c.current_version)) == content_version
            active_vehicle_rows = tuple(
                connection.execute(
                    select(content_vehicle_evidence_table).where(
                        content_vehicle_evidence_table.c.content_id == content_id,
                        content_vehicle_evidence_table.c.content_version == content_version,
                        content_vehicle_evidence_table.c.is_active.is_(True),
                    )
                ).mappings()
            )
            active_brand_rows = tuple(
                connection.execute(
                    select(content_brand_evidence_table).where(
                        content_brand_evidence_table.c.content_id == content_id,
                        content_brand_evidence_table.c.content_version == content_version,
                        content_brand_evidence_table.c.is_active.is_(True),
                    )
                ).mappings()
            )
            vehicle_locked = connection.scalar(
                select(content_vehicle_review_locks_table.c.is_locked).where(
                    content_vehicle_review_locks_table.c.content_id == content_id,
                    content_vehicle_review_locks_table.c.content_version == content_version,
                )
            )
            brand_locked = connection.scalar(
                select(content_brand_review_locks_table.c.is_locked).where(
                    content_brand_review_locks_table.c.content_id == content_id,
                    content_brand_review_locks_table.c.content_version == content_version,
                )
            )
        assert [(row["source"], row["is_manual_locked"]) for row in active_vehicle_rows] == [
            ("manual_review", True)
        ]
        assert [(row["source"], row["is_manual_locked"]) for row in active_brand_rows] == [
            ("manual_review", True)
        ]
        assert vehicle_locked is True
        assert brand_locked is True
    finally:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, "
                "accounts RESTART IDENTITY CASCADE"
            )
        runtime.close()
'''
    path.write_text(text, encoding="utf-8")


def main() -> None:
    _patch_single_file()
    _patch_historical()
    print("Patched Stage 3 single-file and Historical persistence evidence regressions")


if __name__ == "__main__":
    main()
