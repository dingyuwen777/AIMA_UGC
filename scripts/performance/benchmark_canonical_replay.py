"""在专用空数据库上用正式导入与 Replay 路径测量阶段吞吐。"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.canonical_replay_http import PostgresCanonicalReplayHttpService
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.contracts.brand_vehicle import BrandAliasCreateRequest, BrandCreateRequest
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.ingestion.canonical_replay_tables import (
    canonical_replay_content_changes_table,
    canonical_replay_runs_table,
)
from aima_ugc.modules.vehicles.tables import vehicle_brands_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.tables import artifacts_table
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import event, func, select

_DATABASE_SUFFIX = "_canonical_replay_capacity"


def _require_capacity_database(name: str) -> None:
    """拒绝任何非专用容量数据库，避免基准请求全量重筛真实数据。"""

    if not name.endswith(_DATABASE_SUFFIX):
        raise ValueError(f"Replay 容量基准仅允许数据库名以 {_DATABASE_SUFFIX} 结尾")


def _fixture_xlsx(*, file_index: int, rows_per_file: int, nonce: str) -> bytes:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("文章")
    sheet.append(["媒体名称（中文）", "标题", "内文", "作者", "出版日期", "原文链接"])
    for row_index in range(rows_per_file):
        external_id = f"replay-bench-{nonce}-{file_index}-{row_index}"
        sheet.append(
            [
                "小红书",
                f"星曜容量样本 {file_index}-{row_index}",
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


def run_benchmark(
    *,
    work_dir: Path,
    file_count: int,
    rows_per_file: int,
    workers: int,
) -> dict[str, object]:
    """只测 Replay 执行窗口；输入生成与初次导入不计时。"""

    if not 1 <= file_count <= 1000:
        raise ValueError("file_count 必须在 1 到 1000 之间")
    if not 1 <= rows_per_file <= 10_000:
        raise ValueError("rows_per_file 必须在 1 到 10000 之间")
    if not 1 <= workers <= 8:
        raise ValueError("workers 必须在 1 到 8 之间")
    settings = load_settings()
    _require_capacity_database(settings.db_name)
    root = work_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("Replay 容量基准工作目录必须为空")

    runtime = create_worker_runtime(
        settings=settings.model_copy(update={"data_dir": root / "data", "log_dir": root / "logs"})
    )
    try:
        runtime.logger.setLevel(logging.WARNING)
        with runtime.database.engine.connect() as connection:
            for table in (artifacts_table, jobs_table, vehicle_brands_table, contents_table):
                if connection.scalar(select(func.count()).select_from(table)):
                    raise ValueError("Replay 容量基准数据库必须没有业务数据")

        client = TestClient(
            create_app(
                import_service=PostgresImportHttpService(runtime),
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
                aliases=("导入阶段不会命中的品牌词",),
            ),
            principal=principal,
            request_id="canonical-replay-capacity-brand",
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
                                nonce=nonce,
                            ),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ),
                    ),
                    ("brand_ids", (None, str(brand.id), None)),
                ],
            )
            if created.status_code != 202 or not run_one_job(file_index):
                raise RuntimeError("基准输入导入失败")
            detail = client.get(f"/api/v1/import-batches/{created.json()['batch_id']}")
            if detail.status_code != 200 or detail.json()["status"] != "succeeded":
                raise RuntimeError("基准输入未成功产生 Canonical")
        PostgresBrandVehicleHttpService(runtime).add_alias(
            brand.id,
            BrandAliasCreateRequest(text="星曜"),
            principal=principal,
            request_id="canonical-replay-capacity-alias",
        )
        runtime.logger.setLevel(logging.INFO)
        created = client.post(
            "/api/v1/canonical-replays/all",
            json={"idempotency_key": f"replay-capacity-{nonce}"},
        )
        if created.status_code != 202:
            raise RuntimeError("基准全量 Replay 创建失败")
        request_id = UUID(created.json()["request_id"])
        run_count = int(created.json()["run_count"])
        statement_count = 0
        seen_inserts = 0
        ledger_inserts = 0
        statements_by_table: dict[str, int] = {}

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
            statement_count += 1
            first_table = re.search(r"\b(?:FROM|INTO|UPDATE)\s+([a-z_][a-z_0-9]*)", statement)
            sql_kind = statement.lstrip().split(None, 1)[0].upper()
            table_key = f"{sql_kind} {first_table.group(1) if first_table else 'other'}"
            statements_by_table[table_key] = statements_by_table.get(table_key, 0) + 1
            if statement.startswith("INSERT INTO canonical_replay_seen_content"):
                seen_inserts += 1
            if statement.startswith("INSERT INTO canonical_replay_content_changes"):
                ledger_inserts += 1

        event.listen(runtime.database.engine, "before_cursor_execute", count_sql)
        started = time.perf_counter()
        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                if not all(executor.map(run_one_job, range(file_count, file_count + run_count))):
                    raise RuntimeError("基准 Replay Job 未被领取")
        finally:
            elapsed = time.perf_counter() - started
            event.remove(runtime.database.engine, "before_cursor_execute", count_sql)

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
        if len(statuses) != run_count or any(status != "succeeded" for status in statuses):
            raise RuntimeError("基准 Replay 子任务未全部成功")
        expected_rows = file_count * rows_per_file
        if ledger_count != expected_rows:
            raise RuntimeError("基准 Replay 贡献账本行数与输入不一致")
        if (
            int(counters.rows_seen) != expected_rows
            or int(counters.rows_matched) != expected_rows
            or int(counters.rows_ingested) != expected_rows
            or int(counters.existing_convergence) != 0
        ):
            raise RuntimeError("基准 Replay 持久计数与全命中新内容输入不一致")
        return {
            "schema_version": "canonical-replay-capacity.v1",
            "files": file_count,
            "rows": expected_rows,
            "rows_seen": int(counters.rows_seen),
            "rows_matched": int(counters.rows_matched),
            "rows_ingested": int(counters.rows_ingested),
            "existing_convergence": int(counters.existing_convergence),
            "workers": workers,
            "replay_runs": run_count,
            "elapsed_seconds": round(elapsed, 3),
            "rows_per_second": round(expected_rows / elapsed, 2),
            "sql_statements": statement_count,
            "seen_identity_inserts": seen_inserts,
            "contribution_ledger_inserts": ledger_inserts,
            "top_sql_tables": sorted(
                statements_by_table.items(), key=lambda item: item[1], reverse=True
            )[:15],
        }
    finally:
        runtime.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="专用空数据库上的 Canonical Replay 容量基准")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--files", type=int, default=1)
    parser.add_argument("--rows-per-file", type=int, default=100)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    print(
        json.dumps(
            run_benchmark(
                work_dir=args.work_dir,
                file_count=args.files,
                rows_per_file=args.rows_per_file,
                workers=args.workers,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
