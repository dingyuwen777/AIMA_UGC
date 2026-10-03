"""在显式隔离环境验证浏览器计划的正式调度、下载来源与导入结果。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping
from uuid import UUID

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.bootstrap.scheduler import create_scheduler_runtime, run_scheduler_once
from aima_ugc.bootstrap.wisersone_http import managed_input_root, managed_relative_path
from aima_ugc.modules.collection.tables import collection_schedule_occurrences_table
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
    processing_import_batch_items_table,
)
from aima_ugc.modules.ingestion.wisersone_jobs import WISERSONE_JOB_TYPE
from aima_ugc.modules.ingestion.wisersone_tables import wisersone_downloads_table
from aima_ugc.modules.vehicles.tables import content_brand_evidence_table
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.canonical import CanonicalArtifactReader
from aima_ugc.platform.storage.tables import canonical_artifact_links_table
from aima_ugc.platform.time import beijing_now
from sqlalchemy import select


def _require_fullstack_opt_in(environ: Mapping[str, str]) -> None:
    """创建 Runtime 及任何数据库连接前检查测试环境的显式授权。"""
    if environ.get("AIMA_FULLSTACK_SEED") != "1":
        raise RuntimeError("WisersOne 调度验证仅允许 AIMA_FULLSTACK_SEED=1 的隔离环境")
    if not environ.get("AIMA_WISERSONE_INPUT_DIR") or not environ.get(
        "AIMA_HISTORICAL_IMPORT_ROOT"
    ):
        raise RuntimeError(
            "隔离验收必须显式设置 AIMA_WISERSONE_INPUT_DIR 和 AIMA_HISTORICAL_IMPORT_ROOT"
        )


def main() -> None:
    """schedule 只执行正式 tick；result 只读取目标计划的完整来源链。"""
    _require_fullstack_opt_in(os.environ)
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("schedule", "result"))
    parser.add_argument("plan_id", type=UUID)
    parser.add_argument("schedule_version", type=int)
    parser.add_argument("brand_id", type=UUID)
    parser.add_argument("name")
    parser.add_argument("schedule_expr")
    args = parser.parse_args()
    runtime = create_scheduler_runtime()
    try:
        with runtime.database.new_session() as session:
            plan = PostgresCollectionPlanningRepository(session).get_plan(args.plan_id)
            assert plan is not None
            assert plan.plan_type == "wisersone" and plan.enabled
            assert plan.name == args.name and plan.schedule_expr == args.schedule_expr
            assert plan.schedule_version == args.schedule_version
            assert plan.brand_ids == (args.brand_id,)
            assert plan.platforms == () and plan.keyword_pack_ids == ()

        if args.phase == "schedule":
            run_scheduler_once(runtime, now=beijing_now())
            with runtime.database.new_session() as session:
                initialized = PostgresCollectionPlanningRepository(session).get_plan(args.plan_id)
                assert initialized is not None and initialized.next_run_at is not None
                scheduled_for = initialized.next_run_at
            # 复用生产时间参数，重复同一槽位；不修改计划游标或 Job available_at。
            run_scheduler_once(runtime, now=scheduled_for)
            run_scheduler_once(runtime, now=scheduled_for)

        with runtime.database.new_session() as session:
            occurrences = (
                session.execute(
                    select(collection_schedule_occurrences_table).where(
                        collection_schedule_occurrences_table.c.plan_id == args.plan_id,
                        collection_schedule_occurrences_table.c.schedule_version
                        == args.schedule_version,
                    )
                )
                .mappings()
                .all()
            )
            assert len(occurrences) == 1, occurrences
            occurrence = occurrences[0]
            assert occurrence["status"] == "enqueued" and occurrence["skip_reason"] is None
            downloads = (
                session.execute(
                    select(wisersone_downloads_table).where(
                        wisersone_downloads_table.c.occurrence_id == occurrence["id"]
                    )
                )
                .mappings()
                .all()
            )
            assert len(downloads) == 1, downloads
            download = downloads[0]
            download_id = download["id"]
            assert download["request"]["brand_ids"] == [str(args.brand_id)]
            frozen = download["filter_snapshot"]
            assert frozen["catalog"]["selected_brand_ids"] == [str(args.brand_id)]
            assert len(frozen["catalog"]["brands"]) == 1
            jobs = (
                session.execute(
                    select(jobs_table)
                    .where(
                        jobs_table.c.job_type == WISERSONE_JOB_TYPE,
                        jobs_table.c.payload["download_id"].astext == str(download_id),
                    )
                    .order_by(jobs_table.c.created_at)
                )
                .mappings()
                .all()
            )
            initial_jobs = [job for job in jobs if job["payload"]["step"] == 0]
            assert len(initial_jobs) == 1 and initial_jobs[0]["id"] == occurrence["job_id"]
            current = PostgresCollectionPlanningRepository(session).get_plan(args.plan_id)
            assert current is not None and current.last_scheduled_at == occurrence["scheduled_for"]
            assert (
                current.next_run_at is not None and current.next_run_at > current.last_scheduled_at
            )
            evidence = {
                "plan_type": plan.plan_type,
                "name": plan.name,
                "schedule_expr": plan.schedule_expr,
                "schedule_version": plan.schedule_version,
                "brand_ids": [str(item) for item in plan.brand_ids],
                "occurrence_count": len(occurrences),
                "occurrence_id": str(occurrence["id"]),
                "download_id": str(download_id),
                "initial_job_id": str(initial_jobs[0]["id"]),
            }

            if args.phase == "result":
                assert download["status"] == "succeeded", dict(download)
                assert download["send_state"] == "confirmed" and download["percent"] == 100
                assert download["error_code"] is None and download["finished_at"] is not None
                assert all(job["status"] == "succeeded" for job in jobs), jobs
                campaign = (
                    session.execute(
                        select(historical_import_campaigns_table).where(
                            historical_import_campaigns_table.c.client_idempotency_key
                            == f"wisersone:{download_id}"
                        )
                    )
                    .mappings()
                    .one()
                )
                assert campaign["id"] == download["campaign_id"]
                assert campaign["status"] == "succeeded"
                assert campaign["ingestion_policy"] == "standard_observation"
                assert campaign["keyword_pack_snapshot"] == frozen
                assert campaign["total_rows"] == 2
                assert campaign["stats"]["created"] == 1 and campaign["stats"]["filtered"] == 1
                items = (
                    session.execute(
                        select(historical_import_campaign_items_table).where(
                            historical_import_campaign_items_table.c.campaign_id == campaign["id"]
                        )
                    )
                    .mappings()
                    .all()
                )
                sources = [item for item in items if item["item_kind"] == "source_file"]
                chunks = [item for item in items if item["item_kind"] == "chunk"]
                assert len(sources) == 1 and len(chunks) == 1
                assert all(item["status"] == "succeeded" for item in items)
                source, chunk = sources[0], chunks[0]
                assert source["relative_path"] == managed_relative_path(download_id)
                assert source["sha256"] == download["sha256"]
                artifacts = PostgresArtifactMetadataRepository(session)
                source_artifact = artifacts.get(source["artifact_id"])
                assert source_artifact is not None and source_artifact.sha256 == download["sha256"]
                source_bytes = runtime.artifact_store.read(source_artifact.storage_key)
                assert hashlib.sha256(source_bytes).hexdigest() == download["sha256"]
                published = (
                    managed_input_root(runtime) / str(download_id) / "wisersone_last24h.xlsx"
                )
                assert published.read_bytes() == source_bytes
                linked = session.execute(
                    select(canonical_artifact_links_table.c.artifact_id).where(
                        canonical_artifact_links_table.c.historical_import_campaign_item_id
                        == chunk["id"]
                    )
                ).scalar_one()
                assert linked == chunk["artifact_id"]
                canonical_artifact = artifacts.get(linked)
                assert canonical_artifact is not None
                canonical = tuple(
                    CanonicalArtifactReader(store=runtime.artifact_store).read(canonical_artifact)
                )
                assert len(canonical) == 2
                ledger = (
                    session.execute(
                        select(processing_import_batch_items_table).where(
                            processing_import_batch_items_table.c.campaign_item_id == chunk["id"]
                        )
                    )
                    .mappings()
                    .all()
                )
                assert sorted(row["outcome"] for row in ledger) == ["created", "filtered"]
                created_row = next(row for row in ledger if row["outcome"] == "created")
                content = (
                    session.execute(
                        select(contents_table).where(
                            contents_table.c.id == created_row["content_id"]
                        )
                    )
                    .mappings()
                    .one()
                )
                assert content["title"] == f"爱玛 WisersOne 全栈 {download_id}"
                assert (
                    session.execute(
                        select(content_brand_evidence_table.c.id).where(
                            content_brand_evidence_table.c.content_id == content["id"],
                            content_brand_evidence_table.c.brand_id == args.brand_id,
                            content_brand_evidence_table.c.is_active.is_(True),
                        )
                    ).first()
                    is not None
                )
                fixture_root = runtime.settings.data_dir / "fullstack-wisersone"
                events = [
                    json.loads(line)
                    for line in (fixture_root / f"events-{download_id.hex}.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                ]
                assert [event["action"] for event in events].count("submit") == 1
                assert [event["action"] for event in events].count("download") == 1
                assert all(event["task_id"] == download["website_task_id"] for event in events)
                evidence.update(
                    campaign_id=str(campaign["id"]),
                    content_id=str(content["id"]),
                    canonical_rows=len(canonical),
                    outcomes=sorted(row["outcome"] for row in ledger),
                    submissions=1,
                    downloads=1,
                )
            print(json.dumps(evidence, ensure_ascii=False))
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
