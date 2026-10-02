"""仅在专用 aima_content_test 数据库运行的日期补采容量复现探针。"""

import json
import tracemalloc
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from aima_ugc.bootstrap.collection_http import PostgresCollectionHttpService
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.contracts.http import CollectionRunCreateRequest, CollectionSupplementPreviewRequest
from aima_ugc.modules.collection.tables import collection_scopes_table
from aima_ugc.modules.content.extended_tables import content_external_ids_table
from aima_ugc.modules.content.tables import contents_table
from sqlalchemy import insert, select, text

from tests.integration.collection.test_collection_supplement_target_eligibility import _seed_batch
from tests.integration.collection.test_stage8e_collection_http_runtime import (
    _seed_config_and_search_pack,
)

print("phase: runtime", flush=True)
runtime = create_worker_runtime()
if (
    runtime.settings.db_name != "aima_content_test"
    or runtime.settings.db_host != "127.0.0.1"
    or runtime.settings.db_port != 15479
):
    runtime.close()
    raise RuntimeError("容量探针只允许使用本任务的隔离数据库")
now = datetime.fromisoformat("2026-09-01T12:00:00+08:00")
try:
    print("phase: database transaction", flush=True)
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE jobs, artifacts, accounts, keyword_packs, provider_configs CASCADE"
        )
    print("phase: seed provider", flush=True)
    config, _ = _seed_config_and_search_pack(runtime)
    _, _, attempt_id, artifact_id = _seed_batch(runtime)
    print("phase: insert fixture", flush=True)
    ids = [uuid4() for _ in range(10000)]
    with runtime.database.engine.begin() as connection:
        connection.execute(
            insert(contents_table),
            [
                {
                    "id": value,
                    "platform": "xiaohongshu",
                    "external_content_id": f"capacity-{value}",
                    "content_type": "image",
                    "published_at": now,
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "updated_at": now,
                    "current_version": 1,
                    "field_observed_at": {},
                }
                for value in ids
            ],
        )
        connection.execute(
            insert(content_external_ids_table),
            [
                {
                    "content_id": value,
                    "id_type": "note_id",
                    "external_id": f"capacity-{value}",
                    "observed_at": now,
                    "provider_attempt_id": attempt_id,
                    "raw_artifact_id": artifact_id,
                }
                for value in ids
            ],
        )
        # 代表宽表背景，少量日期窗口仍能使用已有 published_at 索引。
        connection.execute(
            text(
                "INSERT INTO contents (id, platform, external_content_id, content_type, "
                "published_at, first_seen_at, last_seen_at, updated_at, current_version, "
                "field_observed_at) SELECT gen_random_uuid(), 'douyin', "
                "'background-' || n::text, 'video', :published, :now, :now, :now, 1, "
                "'{}'::jsonb FROM generate_series(1, 90000) n"
            ),
            {"published": now - timedelta(days=365), "now": now},
        )
        connection.exec_driver_sql("ANALYZE contents")
        plan = connection.execute(
            text(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
                "SELECT id, platform, external_content_id, content_type, current_version "
                "FROM contents WHERE published_at >= :lo AND published_at <= :hi "
                "AND platform IN ('xiaohongshu','douyin','weibo','bilibili','kuaishou') "
                "ORDER BY platform, id"
            ),
            {
                "lo": now.replace(hour=0),
                "hi": now.replace(hour=23, minute=59, second=59, microsecond=999000),
            },
        ).scalar_one()
    print("phase: create 10000 scopes", flush=True)
    service = PostgresCollectionHttpService(runtime, cursor_signing_secret=b"r" * 32)
    targets = {
        "kind": "published_date_range",
        "published_from": now.replace(hour=0),
        "published_to": now.replace(hour=23, minute=59, second=59, microsecond=999000),
    }
    preview = service.preview_supplement(
        CollectionSupplementPreviewRequest(
            targets=targets, platforms=("xiaohongshu",), include_comments=False
        )
    )
    request = CollectionRunCreateRequest(
        mode="content_supplement",
        supplement_targets=targets,
        expected_target_count=preview.target_count,
        expected_target_fingerprint=preview.target_fingerprint,
        platforms=({"platform": "xiaohongshu", "provider_config_id": config},),
        include_comments=False,
    )
    tracemalloc.start()
    start = perf_counter()
    created = service.create_run(request, request_id="date-capacity")
    seconds = perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    with runtime.database.engine.begin() as connection:
        count = len(
            connection.scalars(
                select(collection_scopes_table.c.id).where(
                    collection_scopes_table.c.run_id == created.run_id
                )
            ).all()
        )
    assert count == 10000
    result = {
        "fixture_rows": 100000,
        "selected_rows": 10000,
        "create_seconds_with_tracemalloc": seconds,
        "peak_python_bytes": peak,
        "scope_count": count,
        "explain": plan,
    }
    Path(".runtime/content-test-runtime/capacity.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in result.items() if k != "explain"}))
finally:
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE jobs, artifacts, accounts, contents, keyword_packs, provider_configs CASCADE"
        )
    runtime.close()
