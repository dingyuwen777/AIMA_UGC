"""在专用空数据库上用正式导入与 Replay 路径测量阶段吞吐。"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import get_ident
from typing import Any, Literal
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
    PostgresCompleteExistingContentBatchItem,
)
from aima_ugc.adapters.persistence.postgres.content_contributions import (
    ContentContributionSnapshot,
    capture_content_contribution_snapshots_batch,
)
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.canonical_replay_http import PostgresCanonicalReplayHttpService
from aima_ugc.bootstrap.canonical_replay_worker import PostgresCanonicalReplayJobExecutor
from aima_ugc.bootstrap.historical_import_http import PostgresHistoricalImportHttpService
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.contracts.brand_vehicle import BrandAliasCreateRequest, BrandCreateRequest
from aima_ugc.contracts.canonical import CanonicalAuthorV1, CanonicalContentV1
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.ingestion.canonical_replay_tables import (
    canonical_replay_all_requests_table,
    canonical_replay_content_changes_table,
    canonical_replay_runs_table,
)
from aima_ugc.modules.ingestion.historical_jobs import (
    HISTORICAL_DISCOVER_JOB_TYPE,
    HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
    HISTORICAL_SNAPSHOT_JOB_TYPE,
)
from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_TYPE
from aima_ugc.modules.vehicles.tables import vehicle_brands_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs import JobRegistry
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.performance_catalog_fixture import seed_catalog_fixture
from aima_ugc.platform.storage.tables import artifacts_table
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import event, func, select

_DATABASE_SUFFIX = "_canonical_replay_capacity"
_DEFAULT_DISK_BUDGET_BYTES = 512 * 1024 * 1024
_FREE_SPACE_RESERVE_BYTES = 64 * 1024 * 1024


def _require_capacity_database(name: str) -> None:
    """拒绝任何非专用容量数据库，避免基准请求全量重筛真实数据。"""

    if not name.endswith(_DATABASE_SUFFIX):
        raise ValueError(f"Replay 容量基准仅允许数据库名以 {_DATABASE_SUFFIX} 结尾")


def _fixture_xlsx(
    *,
    file_index: int,
    rows_per_file: int,
    existing_rows_per_file: int,
    matched_rows_per_file: int,
    nonce: str,
    match_layout: Literal["clustered", "interleaved"] = "clustered",
) -> bytes:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("文章")
    sheet.append(["媒体名称（中文）", "标题", "内文", "作者", "出版日期", "原文链接"])
    stride = max(1, round(rows_per_file * 0.61803398875))
    while math.gcd(stride, rows_per_file) != 1:
        stride += 1
    for row_index in range(rows_per_file):
        external_id = f"replay-bench-{nonce}-{file_index}-{row_index}"
        rank = (row_index * stride) % rows_per_file if match_layout == "interleaved" else row_index
        keyword = (
            "预置"
            if rank < existing_rows_per_file
            else "星曜"
            if rank < matched_rows_per_file
            else "完全无关容量样本"
        )
        sheet.append(
            [
                "小红书",
                f"{keyword}容量样本 {file_index}-{row_index}",
                "容量测试正文",
                "容量测试账号",
                "2026-09-11 08:00:00",
                f"https://www.xiaohongshu.com/explore/{external_id}",
            ]
        )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _run_foreground_import(
    *,
    client: TestClient,
    runtime: PlatformRuntime,
    registry: JobRegistry,
    brand_id: UUID,
    nonce: str,
    file_index: int,
    row_count: int,
) -> dict[str, object]:
    """用正式 Excel Import Job 测量 Replay 期间正常入库的排队与执行。"""

    created = client.post(
        "/api/v1/import-batches",
        files=[
            (
                "file",
                (
                    f"mixed-{file_index}.xlsx",
                    _fixture_xlsx(
                        file_index=file_index,
                        rows_per_file=row_count,
                        existing_rows_per_file=0,
                        matched_rows_per_file=max(1, row_count // 4),
                        nonce=nonce,
                        match_layout="interleaved",
                    ),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            ),
            ("brand_ids", (None, str(brand_id), None)),
        ],
    )
    if created.status_code != 202:
        raise RuntimeError("混合负载 Excel Import 未入队")
    job_id = UUID(created.json()["job_id"])
    started = time.perf_counter()
    foreground = create_job_worker(
        runtime=runtime,
        registry=registry,
        worker_id=f"canonical-replay-foreground-{file_index}",
        lease_seconds=120,
        retry_delay_seconds=0,
        supported_job_types=(IMPORT_JOB_TYPE,),
    )
    if not foreground.run_once():
        raise RuntimeError("混合负载预留 Worker 未领取 Excel Import")
    elapsed = time.perf_counter() - started
    with runtime.database.engine.connect() as connection:
        job = (
            connection.execute(select(jobs_table).where(jobs_table.c.id == job_id)).mappings().one()
        )
    if job["status"] != "succeeded" or job["started_at"] is None:
        raise RuntimeError("混合负载 Excel Import 未完成")
    return {
        "kind": "legacy_import_batch",
        "input_rows": row_count,
        "matched_rows": max(1, row_count // 4),
        "queue_seconds": round((job["started_at"] - job["created_at"]).total_seconds(), 3),
        "worker_seconds": round(elapsed, 3),
    }


def _run_foreground_unified_import(
    *,
    client: TestClient,
    runtime: PlatformRuntime,
    registry: JobRegistry,
    brand_id: UUID,
    nonce: str,
    file_index: int,
    row_count: int,
    all_active_catalog: bool,
) -> dict[str, object]:
    """用本地文件统一 Data Import 全链路测量 Replay 期间前台吞吐。"""

    payload = _fixture_xlsx(
        file_index=file_index,
        rows_per_file=row_count,
        existing_rows_per_file=0,
        matched_rows_per_file=row_count,
        nonce=nonce,
        match_layout="interleaved",
    )
    file_name = f"mixed-unified-{file_index}.xlsx"
    started = time.perf_counter()
    created = client.post(
        "/api/v1/data-import-campaigns/local",
        json={
            "client_idempotency_key": f"mixed-unified-{nonce}-{file_index}",
            "files": [{"relative_path": file_name, "byte_size": len(payload)}],
            "brand_ids": ([] if all_active_catalog else [str(brand_id)]),
            "ingestion_policy": "standard_observation",
        },
    )
    if created.status_code != 201:
        raise RuntimeError(f"混合负载统一导入 Campaign 未创建: {created.text}")
    campaign_id = created.json()["campaign_id"]
    upload_item = created.json()["upload_items"][0]
    uploaded = client.put(
        f"/api/v1/data-import-campaigns/{campaign_id}/items/{upload_item['item_id']}/content",
        files={
            "file": (
                file_name,
                payload,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    if uploaded.status_code != 200:
        raise RuntimeError("混合负载统一导入文件未上传")
    finalized = client.post(f"/api/v1/data-import-campaigns/{campaign_id}/finalize")
    if finalized.status_code != 202:
        raise RuntimeError("混合负载统一导入预检未入队")

    worker = create_job_worker(
        runtime=runtime,
        registry=registry,
        worker_id=f"canonical-replay-unified-foreground-{file_index}",
        lease_seconds=120,
        retry_delay_seconds=0,
        supported_job_types=(
            HISTORICAL_DISCOVER_JOB_TYPE,
            HISTORICAL_SNAPSHOT_JOB_TYPE,
            HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
        ),
    )

    preflight_started = time.perf_counter()
    for _ in range(10_000):
        detail = client.get(f"/api/v1/historical-import-campaigns/{campaign_id}")
        if detail.status_code != 200:
            raise RuntimeError("混合负载统一导入 Campaign 无法读取")
        status = detail.json()["status"]
        if status == "ready":
            break
        if status in {"failed", "cancelled", "partial_failed"}:
            raise RuntimeError(f"混合负载统一导入预检失败: {status}")
        if not worker.run_once():
            time.sleep(0.005)
    else:
        raise RuntimeError("混合负载统一导入预检未收敛")
    preflight_seconds = time.perf_counter() - preflight_started

    import_started = time.perf_counter()
    accepted = client.post(f"/api/v1/historical-import-campaigns/{campaign_id}/start")
    if accepted.status_code != 200:
        raise RuntimeError("混合负载统一导入未启动")
    for _ in range(10_000):
        detail = client.get(f"/api/v1/historical-import-campaigns/{campaign_id}")
        if detail.status_code != 200:
            raise RuntimeError("混合负载统一导入 Campaign 无法读取")
        status = detail.json()["status"]
        if status == "succeeded":
            break
        if status in {"failed", "cancelled", "partial_failed"}:
            raise RuntimeError(f"混合负载统一导入失败: {status}")
        if not worker.run_once():
            time.sleep(0.005)
    else:
        raise RuntimeError("混合负载统一导入未收敛")
    import_seconds = time.perf_counter() - import_started
    elapsed = time.perf_counter() - started
    return {
        "kind": "unified_local_upload",
        "input_rows": row_count,
        "matched_rows": row_count,
        "preflight_seconds": round(preflight_seconds, 3),
        "import_seconds": round(import_seconds, 3),
        "worker_seconds": round(elapsed, 3),
        "rows_per_second": round(row_count / import_seconds, 2),
    }


def run_benchmark(
    *,
    work_dir: Path,
    file_count: int,
    rows_per_file: int,
    workers: int,
    existing_rows_per_file: int = 0,
    matched_rows_per_file: int | None = None,
    match_layout: Literal["clustered", "interleaved"] = "clustered",
    stable_authors: bool = False,
    scalar_stable_authors: bool = False,
    measure_reversal: bool = False,
    mixed_load: bool = False,
    mixed_reversal_load: bool = False,
    mixed_import_rows: int = 100,
    mixed_import_kind: Literal["legacy", "unified_local"] = "unified_local",
    existing_evidence_change: bool = False,
    catalog_brands: int = 0,
    vehicles_per_brand: int = 0,
    catalog_after_import: bool = False,
    disk_budget_bytes: int = _DEFAULT_DISK_BUDGET_BYTES,
) -> dict[str, object]:
    """只测 Replay 执行窗口；输入生成与初次导入不计时。"""

    if not 1 <= file_count <= 1000:
        raise ValueError("file_count 必须在 1 到 1000 之间")
    if not 1 <= rows_per_file <= 10_000:
        raise ValueError("rows_per_file 必须在 1 到 10000 之间")
    if not 1 <= workers <= 8:
        raise ValueError("workers 必须在 1 到 8 之间")
    if not 0 <= existing_rows_per_file <= rows_per_file:
        raise ValueError("existing_rows_per_file 必须在 0 到 rows_per_file 之间")
    resolved_matched_rows = (
        rows_per_file if matched_rows_per_file is None else matched_rows_per_file
    )
    if not existing_rows_per_file <= resolved_matched_rows <= rows_per_file:
        raise ValueError(
            "matched_rows_per_file 必须在 existing_rows_per_file 到 rows_per_file 之间"
        )
    if match_layout not in {"clustered", "interleaved"}:
        raise ValueError("match_layout 必须为 clustered 或 interleaved")
    if scalar_stable_authors and not stable_authors:
        raise ValueError("scalar_stable_authors 要求同时启用 stable_authors")
    if existing_evidence_change and existing_rows_per_file == 0:
        raise ValueError("证据撤回基准要求包含既有内容")
    if not 1 <= mixed_import_rows <= 10_000:
        raise ValueError("mixed_import_rows 必须在 1 到 10000 之间")
    if mixed_import_kind not in {"legacy", "unified_local"}:
        raise ValueError("mixed_import_kind 必须为 legacy 或 unified_local")
    if mixed_reversal_load and (not mixed_load or not measure_reversal):
        raise ValueError("mixed_reversal_load 要求同时启用 mixed_load 和 measure_reversal")
    if not 0 <= catalog_brands <= 1_000:
        raise ValueError("catalog_brands 必须在 0 到 1000 之间")
    if not 0 <= vehicles_per_brand <= 1_000:
        raise ValueError("vehicles_per_brand 必须在 0 到 1000 之间")
    if catalog_brands * vehicles_per_brand > 50_000:
        raise ValueError("目录车型总数不能超过 50000")
    if catalog_after_import and catalog_brands == 0:
        raise ValueError("catalog_after_import 要求 catalog_brands 大于 0")
    if disk_budget_bytes <= 0:
        raise ValueError("disk_budget_bytes 必须大于 0")
    settings = load_settings()
    _require_capacity_database(settings.db_name)
    root = work_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("Replay 容量基准工作目录必须为空")
    estimated_bytes = file_count * (4 * 1024 * 1024 + rows_per_file * 4096)
    if estimated_bytes > disk_budget_bytes:
        raise ValueError("Replay 容量基准预计临时数据超过磁盘预算")
    free_bytes = shutil.disk_usage(root).free
    if estimated_bytes + _FREE_SPACE_RESERVE_BYTES > free_bytes:
        raise ValueError("Replay 容量基准预计临时数据超过当前可用磁盘")

    try:
        runtime = create_worker_runtime(
            settings=settings.model_copy(
                update={
                    "data_dir": root / "data",
                    "log_dir": root / "logs",
                    "historical_chunk_rows": min(2_000, mixed_import_rows),
                    "historical_max_in_flight_jobs": 2,
                }
            )
        )
    except BaseException:
        _cleanup_generated_outputs(root)
        raise
    completed = False
    try:
        runtime.logger.setLevel(logging.WARNING)
        _reset_capacity_database(runtime)
        with runtime.database.engine.connect() as connection:
            for table in (artifacts_table, jobs_table, vehicle_brands_table, contents_table):
                if connection.scalar(select(func.count()).select_from(table)):
                    raise ValueError("Replay 容量基准数据库必须没有业务数据")

        client = TestClient(
            create_app(
                import_service=PostgresImportHttpService(runtime),
                historical_import_service=PostgresHistoricalImportHttpService(runtime),
                canonical_replay_service=PostgresCanonicalReplayHttpService(runtime),
            )
        )
        principal = Principal(
            principal_id="canonical-replay-capacity",
            display_name="Replay 容量基准",
            role="administrator",
            source="development",
        )
        brand = PostgresBrandVehicleHttpService(runtime).create_brand(
            BrandCreateRequest(
                display_name=f"Replay 容量品牌 {uuid4().hex[:8]}",
                role="owned",
                aliases=(("预置",) if existing_rows_per_file else ("导入阶段不会命中的品牌词",)),
            ),
            principal=principal,
            request_id="canonical-replay-capacity-brand",
        )
        catalog_fixture = seed_catalog_fixture(
            runtime,
            brand_count=(0 if catalog_after_import else catalog_brands),
            vehicles_per_brand=(0 if catalog_after_import else vehicles_per_brand),
        )
        registry = create_collection_job_registry(runtime=runtime)

        def run_one_job(index: int) -> bool:
            return create_job_worker(
                runtime=runtime,
                registry=registry,
                worker_id=f"canonical-replay-capacity-{index}",
                lease_seconds=120,
                retry_delay_seconds=0,
            ).run_once()

        nonce = uuid4().hex

        def run_mixed_import(file_index: int) -> dict[str, object]:
            if mixed_import_kind == "legacy":
                return _run_foreground_import(
                    client=client,
                    runtime=runtime,
                    registry=registry,
                    brand_id=brand.id,
                    nonce=nonce,
                    file_index=file_index,
                    row_count=mixed_import_rows,
                )
            return _run_foreground_unified_import(
                client=client,
                runtime=runtime,
                registry=registry,
                brand_id=brand.id,
                nonce=nonce,
                file_index=file_index,
                row_count=mixed_import_rows,
                all_active_catalog=bool(catalog_brands),
            )

        import_worker_seconds = 0.0
        for file_index in range(file_count):
            created = client.post(
                "/api/v1/import-batches",
                files=[
                    (
                        "file",
                        (
                            f"capacity-{file_index}.xlsx",
                            _fixture_xlsx(
                                file_index=file_index,
                                rows_per_file=rows_per_file,
                                existing_rows_per_file=existing_rows_per_file,
                                matched_rows_per_file=resolved_matched_rows,
                                nonce=nonce,
                                match_layout=match_layout,
                            ),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ),
                    ),
                    ("brand_ids", (None, str(brand.id), None)),
                ],
            )
            if created.status_code != 202:
                raise RuntimeError("基准输入导入请求失败")
            import_started = time.perf_counter()
            imported = run_one_job(file_index)
            import_worker_seconds += time.perf_counter() - import_started
            if not imported:
                raise RuntimeError("基准输入导入失败")
            detail = client.get(f"/api/v1/import-batches/{created.json()['batch_id']}")
            if detail.status_code != 200 or detail.json()["status"] != "succeeded":
                raise RuntimeError("基准输入未成功产生 Canonical")
        if catalog_after_import:
            catalog_fixture = seed_catalog_fixture(
                runtime,
                brand_count=catalog_brands,
                vehicles_per_brand=vehicles_per_brand,
            )
        PostgresBrandVehicleHttpService(runtime).add_alias(
            brand.id,
            BrandAliasCreateRequest(text="预置容量" if existing_evidence_change else "星曜"),
            principal=principal,
            request_id="canonical-replay-capacity-alias",
        )
        if existing_evidence_change and existing_rows_per_file < rows_per_file:
            PostgresBrandVehicleHttpService(runtime).add_alias(
                brand.id,
                BrandAliasCreateRequest(text="星曜"),
                principal=principal,
                request_id="canonical-replay-capacity-new-alias",
            )
        # 容量基准需要保留每个原子批次的阶段耗时，便于区分解析、Content、
        # Evidence 与账本/checkpoint 瓶颈；正式服务仍由部署日志级别控制。
        runtime.logger.setLevel(logging.DEBUG)
        for handler in runtime.logger.handlers:
            handler.setLevel(logging.DEBUG)
        # 先冻结 Replay 受理时间边界，再执行对照导入；这样对照 Artifact 不会
        # 被 Planner 纳入本轮输入，行数与 run_count 仍只反映基准 Fixture。
        acceptance_started = time.perf_counter()
        created = client.post(
            "/api/v1/canonical-replays/all",
            json={"idempotency_key": f"replay-capacity-{nonce}"},
        )
        acceptance_seconds = time.perf_counter() - acceptance_started
        if created.status_code != 202:
            raise RuntimeError("基准全量 Replay 创建失败")
        request_id = UUID(created.json()["request_id"])
        baseline_before = run_mixed_import(899) if mixed_load else None
        planning_seconds = 0.0
        if "planning_status" in created.json():
            planning_started = time.perf_counter()
            if created.json()["planning_status"] != "queued" or not run_one_job(file_count):
                raise RuntimeError("基准全量 Replay Planner 未被领取")
            planned = client.post(
                "/api/v1/canonical-replays/all",
                json={"idempotency_key": f"replay-capacity-{nonce}"},
            )
            if planned.status_code != 202 or planned.json()["planning_status"] != "planned":
                raise RuntimeError("基准全量 Replay Planner 未完成")
            planning_seconds = time.perf_counter() - planning_started
        else:
            planned = created
        run_count = int(planned.json()["run_count"])
        statement_count = 0
        seen_inserts = 0
        ledger_inserts = 0
        statements_by_table: dict[str, int] = {}
        statement_examples: dict[str, str] = {}
        replay_thread_ids: set[int] = set()

        def count_sql(
            connection: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            nonlocal statement_count, seen_inserts, ledger_inserts
            del connection, cursor, parameters, context, executemany
            if mixed_load and get_ident() not in replay_thread_ids:
                return
            statement_count += 1
            first_table = re.search(r"\b(?:FROM|INTO|UPDATE)\s+([a-z_][a-z_0-9]*)", statement)
            sql_kind = statement.lstrip().split(None, 1)[0].upper()
            table_key = f"{sql_kind} {first_table.group(1) if first_table else 'other'}"
            statements_by_table[table_key] = statements_by_table.get(table_key, 0) + 1
            statement_examples.setdefault(table_key, " ".join(statement.split())[:500])
            if statement.startswith("INSERT INTO canonical_replay_seen_content"):
                seen_inserts += 1
            if statement.startswith("INSERT INTO canonical_replay_content_changes"):
                ledger_inserts += 1

        original_lineage = PostgresCanonicalReplayJobExecutor._content_with_lineage
        lineage_method_name = "_content_with_lineage"
        content_batch_method_name = "ingest_contents_with_before_snapshots_batch"
        original_content_batch = (
            PostgresCompleteContentRepository.ingest_contents_with_before_snapshots_batch
        )

        def inject_stable_author(
            session: object,
            content: CanonicalContentV1,
            **kwargs: object,
        ) -> CanonicalContentV1:
            """在正式 lineage 完成后为容量样本注入 TikHub 形态的稳定作者。"""

            mapped = original_lineage(session, content, **kwargs)  # type: ignore[arg-type]
            identity = mapped.external_content_id
            return mapped.model_copy(
                update={
                    "author": CanonicalAuthorV1(
                        external_account_id=f"capacity-author-{identity}",
                        alternate_ids={"red_id": f"capacity-red-{identity}"},
                        display_name=f"容量作者 {identity}",
                    ),
                    "observed_fields": [
                        *mapped.observed_fields,
                        "author.external_account_id",
                        "author.alternate_ids",
                        "author.display_name",
                    ],
                }
            )

        if stable_authors:
            setattr(
                PostgresCanonicalReplayJobExecutor,
                lineage_method_name,
                staticmethod(inject_stable_author),
            )

        def ingest_stable_authors_one_by_one(
            repository: PostgresCompleteContentRepository,
            entries: tuple[tuple[CanonicalContentV1, ContentContributionSnapshot], ...],
        ) -> tuple[PostgresCompleteExistingContentBatchItem, ...]:
            """仅供同机 A/B 复现旧兼容路径，不改变正式 Worker 的默认行为。"""

            completed: list[PostgresCompleteExistingContentBatchItem] = []
            for observation, before in entries:
                result = repository._ingest_content(  # noqa: SLF001
                    observation,
                    before_snapshot=before,
                )
                after = result.contribution_after
                if after is None:
                    after = capture_content_contribution_snapshots_batch(
                        repository._session,  # noqa: SLF001
                        ((observation, result.target_id),),
                    )[0]
                completed.append(
                    PostgresCompleteExistingContentBatchItem(
                        observation=observation,
                        before=before,
                        result=result,
                        contribution_after=after,
                        used_scalar_fallback=True,
                    )
                )
            return tuple(completed)

        if scalar_stable_authors:
            setattr(
                PostgresCompleteContentRepository,
                content_batch_method_name,
                ingest_stable_authors_one_by_one,
            )
        event.listen(runtime.database.engine, "before_cursor_execute", count_sql)
        started = time.perf_counter()
        mixed_measurement: dict[str, object] | None = None
        mixed_overlap_rows_seen: int | None = None
        expected_rows = file_count * rows_per_file
        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:

                def run_replay_job(index: int) -> bool:
                    replay_thread_ids.add(get_ident())
                    return run_one_job(index)

                futures = tuple(
                    executor.submit(run_replay_job, index)
                    for index in range(file_count, file_count + run_count)
                )
                if mixed_load:
                    # 仅看到 running 不能证明 Replay 已进入写入：大 Run 可能仍在预检，
                    # 而尾部小 Run 已完成。至少等到总输入的 5% 已提交，确保导入与
                    # 持续入库窗口真实重叠。
                    overlap_rows = max(1, math.ceil(expected_rows * 0.05))
                    until = time.monotonic() + 30
                    running = 0
                    replay_rows_seen = 0
                    while time.monotonic() < until:
                        with runtime.database.engine.connect() as connection:
                            running, replay_rows_seen = connection.execute(
                                select(
                                    func.count().filter(jobs_table.c.status == "running"),
                                    func.coalesce(
                                        func.sum(canonical_replay_runs_table.c.rows_seen), 0
                                    ),
                                )
                                .select_from(
                                    canonical_replay_runs_table.join(
                                        jobs_table,
                                        jobs_table.c.id == canonical_replay_runs_table.c.job_id,
                                    )
                                )
                                .where(
                                    canonical_replay_runs_table.c.all_request_id == request_id,
                                )
                            ).one()
                        if running and replay_rows_seen >= overlap_rows:
                            break
                        time.sleep(0.01)
                    if not running or replay_rows_seen < overlap_rows:
                        raise RuntimeError("混合负载基准未观察到持续写入中的 Replay")
                    mixed_overlap_rows_seen = int(replay_rows_seen)
                    mixed_measurement = run_mixed_import(900)
                if not all(future.result() for future in futures):
                    raise RuntimeError("基准 Replay Job 未被领取")
        finally:
            elapsed = time.perf_counter() - started
            event.remove(runtime.database.engine, "before_cursor_execute", count_sql)
            setattr(
                PostgresCanonicalReplayJobExecutor,
                lineage_method_name,
                staticmethod(original_lineage),
            )
            setattr(
                PostgresCompleteContentRepository,
                content_batch_method_name,
                original_content_batch,
            )

        with runtime.database.engine.connect() as connection:
            statuses = (
                connection.execute(
                    select(jobs_table.c.status)
                    .select_from(
                        canonical_replay_runs_table.join(
                            jobs_table, canonical_replay_runs_table.c.job_id == jobs_table.c.id
                        )
                    )
                    .where(canonical_replay_runs_table.c.all_request_id == request_id)
                )
                .scalars()
                .all()
            )
            counters = connection.execute(
                select(
                    func.coalesce(func.sum(canonical_replay_runs_table.c.rows_seen), 0).label(
                        "rows_seen"
                    ),
                    func.coalesce(func.sum(canonical_replay_runs_table.c.rows_matched), 0).label(
                        "rows_matched"
                    ),
                    func.coalesce(func.sum(canonical_replay_runs_table.c.rows_ingested), 0).label(
                        "rows_ingested"
                    ),
                    func.coalesce(
                        func.sum(canonical_replay_runs_table.c.existing_convergence),
                        0,
                    ).label("existing_convergence"),
                ).where(canonical_replay_runs_table.c.all_request_id == request_id)
            ).one()
            ledger_count = connection.scalar(
                select(func.count())
                .select_from(canonical_replay_content_changes_table)
                .where(canonical_replay_content_changes_table.c.all_request_id == request_id)
            )
            changed_evidence = connection.scalar(
                select(func.count())
                .select_from(canonical_replay_content_changes_table)
                .where(
                    canonical_replay_content_changes_table.c.all_request_id == request_id,
                    canonical_replay_content_changes_table.c.brand_evidence_before
                    != canonical_replay_content_changes_table.c.brand_evidence_after,
                )
            )
        if len(statuses) != run_count or any(status != "succeeded" for status in statuses):
            raise RuntimeError("基准 Replay 子任务未全部成功")
        expected_matched = file_count * resolved_matched_rows
        expected_existing = file_count * existing_rows_per_file
        expected_ingested = expected_matched - expected_existing
        if ledger_count != expected_matched:
            raise RuntimeError("基准 Replay 贡献账本行数与命中输入不一致")
        if existing_evidence_change and changed_evidence != expected_matched:
            raise RuntimeError("证据撤回基准没有产生预期的品牌证据变化")
        if (
            int(counters.rows_seen) != expected_rows
            or int(counters.rows_matched) != expected_matched
            or int(counters.rows_ingested) != expected_ingested
            or int(counters.existing_convergence) != expected_existing
        ):
            raise RuntimeError("基准 Replay 持久计数与新增/既有分布不一致")
        report = {
            "schema_version": "canonical-replay-capacity.v1",
            "files": file_count,
            "rows": expected_rows,
            "matched_rows": expected_matched,
            "match_rate": round(expected_matched / expected_rows, 4),
            "match_layout": match_layout,
            "existing_rows": expected_existing,
            "initial_import_ingested_rows": expected_existing,
            "initial_import_worker_seconds": round(import_worker_seconds, 3),
            "new_rows": expected_ingested,
            "rows_seen": int(counters.rows_seen),
            "rows_matched": int(counters.rows_matched),
            "rows_ingested": int(counters.rows_ingested),
            "existing_convergence": int(counters.existing_convergence),
            "changed_brand_evidence": changed_evidence,
            "catalog_fixture": {
                "order": "after_initial_import"
                if catalog_after_import
                else "before_initial_import",
                "distractor_brands": catalog_fixture.brand_count,
                "distractor_vehicles": catalog_fixture.vehicle_count,
                "distractor_aliases": catalog_fixture.alias_count,
                "setup_seconds": round(catalog_fixture.setup_seconds, 3),
            },
            "workers": workers,
            "stable_authors": stable_authors,
            "scalar_stable_authors": scalar_stable_authors,
            "replay_runs": run_count,
            "acceptance_seconds": round(acceptance_seconds, 3),
            "planning_seconds": round(planning_seconds, 3),
            "elapsed_seconds": round(elapsed, 3),
            "end_to_end_seconds": round(acceptance_seconds + planning_seconds + elapsed, 3),
            "rows_per_second": round(expected_rows / elapsed, 2),
            "matched_rows_per_second": round(expected_matched / elapsed, 2),
            "sql_statements": statement_count,
            "seen_identity_inserts": seen_inserts,
            "contribution_ledger_inserts": ledger_inserts,
            "disk_budget_bytes": disk_budget_bytes,
            "estimated_bytes": estimated_bytes,
            "work_directory_bytes": _directory_bytes(root),
            "top_sql_tables": sorted(
                statements_by_table.items(), key=lambda item: item[1], reverse=True
            )[:15],
            "top_sql_examples": {
                key: statement_examples[key]
                for key, _ in sorted(
                    statements_by_table.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:15]
            },
        }
        if mixed_load:
            baseline = run_mixed_import(901)
            report["mixed_load"] = {
                "without_replay_before": baseline_before,
                "while_replay": mixed_measurement,
                "without_replay_after": baseline,
                "replay_rows_seen_when_import_started": mixed_overlap_rows_seen,
            }
        if measure_reversal:
            reversal_sql: dict[str, int] = {}
            reversal_thread_ids: set[int] = set()

            def count_reversal_sql(
                connection: object,
                cursor: object,
                statement: str,
                parameters: object,
                context: object,
                executemany: bool,
            ) -> None:
                """按表统计撤回 SQL 往返，不记录参数或业务正文。"""

                del connection, cursor, parameters, context, executemany
                if mixed_reversal_load and get_ident() not in reversal_thread_ids:
                    return
                first_table = re.search(
                    r"\b(?:FROM|INTO|UPDATE|DELETE FROM)\s+([a-z_][a-z_0-9]*)",
                    statement,
                )
                kind = statement.lstrip().split(None, 1)[0].upper()
                key = f"{kind} {first_table.group(1) if first_table else 'other'}"
                reversal_sql[key] = reversal_sql.get(key, 0) + 1

            revoked = client.post(f"/api/v1/canonical-replays/all/{request_id}/revoke")
            if revoked.status_code != 202:
                raise RuntimeError("基准撤回请求未被接受")
            event.listen(runtime.database.engine, "before_cursor_execute", count_reversal_sql)
            reversal_started = time.perf_counter()
            try:
                if mixed_reversal_load:
                    with ThreadPoolExecutor(max_workers=3) as reversal_executor:

                        def run_reversal_job(index: int) -> bool:
                            reversal_thread_ids.add(get_ident())
                            return run_one_job(index)

                        next_worker_index = file_count + run_count + 1
                        future = reversal_executor.submit(run_reversal_job, next_worker_index)
                        next_worker_index += 1
                        until = time.monotonic() + 30
                        while time.monotonic() < until:
                            with runtime.database.engine.connect() as connection:
                                lifecycle, reverted_so_far = connection.execute(
                                    select(
                                        canonical_replay_all_requests_table.c.lifecycle_status,
                                        canonical_replay_all_requests_table.c.reverted_content_count,
                                    ).where(canonical_replay_all_requests_table.c.id == request_id)
                                ).one()
                            if lifecycle == "reverting" and int(reverted_so_far or 0) > 0:
                                break
                            if future.done():
                                break
                            time.sleep(0.01)
                        if future.done():
                            raise RuntimeError("撤回完成过快，未形成可测量的混合负载窗口")
                        while_reversal = run_mixed_import(902)
                        # 父撤回会按实测吞吐创建持久分片；父 Worker 等待分片结清时，
                        # 必须另有 Worker 领取子任务，等同于正式多进程 Worker 拓扑。
                        while not future.done():
                            shard_futures = tuple(
                                reversal_executor.submit(
                                    run_reversal_job,
                                    next_worker_index + offset,
                                )
                                for offset in range(2)
                            )
                            next_worker_index += len(shard_futures)
                            shard_results = tuple(item.result() for item in shard_futures)
                            if not any(shard_results):
                                time.sleep(0.005)
                        if not future.result():
                            raise RuntimeError("基准撤回 Job 未被领取")
                    after_reversal = run_mixed_import(903)
                elif not run_one_job(file_count + run_count + 1):
                    raise RuntimeError("基准撤回 Job 未被领取")
            finally:
                reversal_seconds = time.perf_counter() - reversal_started
                event.remove(runtime.database.engine, "before_cursor_execute", count_reversal_sql)
            with runtime.database.engine.connect() as connection:
                reversal = (
                    connection.execute(
                        select(canonical_replay_all_requests_table).where(
                            canonical_replay_all_requests_table.c.id == request_id
                        )
                    )
                    .mappings()
                    .one()
                )
                reverted_rows = connection.scalar(
                    select(func.count())
                    .select_from(canonical_replay_content_changes_table)
                    .where(
                        canonical_replay_content_changes_table.c.all_request_id == request_id,
                        canonical_replay_content_changes_table.c.reverted_at.is_not(None),
                    )
                )
            if reversal["lifecycle_status"] != "reverted" or reverted_rows != expected_matched:
                raise RuntimeError("基准撤回状态与贡献账本未对账")
            report["reversal"] = {
                "elapsed_seconds": round(reversal_seconds, 3),
                "reverted_rows": reverted_rows,
                "sql_statements": sum(reversal_sql.values()),
                "top_sql_tables": sorted(
                    reversal_sql.items(), key=lambda item: item[1], reverse=True
                )[:15],
            }
            if mixed_reversal_load:
                report["mixed_reversal_load"] = {
                    "without_reversal_before": baseline,
                    "while_reversal": while_reversal,
                    "without_reversal_after": after_reversal,
                }
        _atomic_write_json(root / "capacity_report.json", report)
        completed = True
        return report
    finally:
        try:
            runtime.close()
        finally:
            if not completed:
                _cleanup_generated_outputs(root)


def _reset_capacity_database(runtime: Any) -> None:
    """只清空后缀已校验的专用容量库，保留 Migration seed。"""

    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, accounts "
            "RESTART IDENTITY CASCADE"
        )


def _directory_bytes(root: Path) -> int:
    """统计本次专用工作目录大小；无法读取的瞬态文件按零处理。"""

    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _cleanup_generated_outputs(root: Path) -> None:
    """异常时只清理由本次空目录基准创建的已知直属输出。"""

    resolved_root = root.resolve()
    for name in (
        "data",
        "logs",
        "capacity_report.json",
        "capacity_report.json.tmp",
    ):
        candidate = (resolved_root / name).resolve()
        if candidate.parent != resolved_root:
            raise RuntimeError("Replay 容量基准清理目标越出工作目录")
        if candidate.is_dir():
            shutil.rmtree(candidate)
        else:
            candidate.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    """原子写入容量报告，避免中途中断留下半份 JSON。"""

    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="专用空数据库上的 Canonical Replay 容量基准")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--files", type=int, default=1)
    parser.add_argument("--rows-per-file", type=int, default=100)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--existing-rows-per-file", type=int, default=0)
    parser.add_argument("--matched-rows-per-file", type=int)
    parser.add_argument("--match-layout", choices=("clustered", "interleaved"), default="clustered")
    parser.add_argument("--stable-authors", action="store_true")
    parser.add_argument("--scalar-stable-authors", action="store_true")
    parser.add_argument("--measure-reversal", action="store_true")
    parser.add_argument("--mixed-load", action="store_true")
    parser.add_argument("--mixed-reversal-load", action="store_true")
    parser.add_argument("--mixed-import-rows", type=int, default=100)
    parser.add_argument(
        "--mixed-import-kind",
        choices=("legacy", "unified_local"),
        default="unified_local",
    )
    parser.add_argument("--existing-evidence-change", action="store_true")
    parser.add_argument("--catalog-brands", type=int, default=0)
    parser.add_argument("--vehicles-per-brand", type=int, default=0)
    parser.add_argument("--catalog-after-import", action="store_true")
    parser.add_argument("--disk-budget-mib", type=int, default=512)
    args = parser.parse_args()
    print(
        json.dumps(
            run_benchmark(
                work_dir=args.work_dir,
                file_count=args.files,
                rows_per_file=args.rows_per_file,
                workers=args.workers,
                existing_rows_per_file=args.existing_rows_per_file,
                matched_rows_per_file=args.matched_rows_per_file,
                match_layout=args.match_layout,
                stable_authors=args.stable_authors,
                scalar_stable_authors=args.scalar_stable_authors,
                measure_reversal=args.measure_reversal,
                mixed_load=args.mixed_load,
                mixed_reversal_load=args.mixed_reversal_load,
                mixed_import_rows=args.mixed_import_rows,
                mixed_import_kind=args.mixed_import_kind,
                existing_evidence_change=args.existing_evidence_change,
                catalog_brands=args.catalog_brands,
                vehicles_per_brand=args.vehicles_per_brand,
                catalog_after_import=args.catalog_after_import,
                disk_budget_bytes=args.disk_budget_mib * 1024 * 1024,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
