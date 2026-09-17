"""创建、查询或取消旧 Content 品牌车型重分类 Run。"""

from __future__ import annotations

import argparse
import json
from typing import Any
from uuid import UUID

from aima_ugc.adapters.persistence.postgres.content_reclassification import (
    PostgresContentReclassificationRepository,
)
from aima_ugc.bootstrap.runtime import create_platform_runtime
from aima_ugc.modules.vehicles.content_reclassification import (
    ContentReclassificationRunRecord,
)
from aima_ugc.platform.jobs import JobRecord


def _uuid(value: str) -> UUID:
    """把命令行 UUID 转成稳定类型，并保留 argparse 的错误表达。"""

    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是合法 UUID") from exc


def _build_parser() -> argparse.ArgumentParser:
    """构建不会隐式选择生产范围的显式子命令。"""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="冻结目录并创建一个有界 Run")
    start.add_argument("--idempotency-key", required=True)
    start.add_argument("--created-by", required=True)
    start.add_argument("--request-id")
    start.add_argument("--shard-index", type=int, required=True)
    start.add_argument("--shard-count", type=int, required=True)
    start.add_argument("--start-after-content-id", type=_uuid)
    start.add_argument("--end-at-content-id", type=_uuid)
    start.add_argument("--batch-size", type=int, default=200)
    start.add_argument("--max-contents", type=int, required=True)

    status = subparsers.add_parser("status", help="读取检查点、统计和 Job 状态")
    status.add_argument("--run-id", type=_uuid, required=True)

    cancel = subparsers.add_parser("cancel", help="请求取消 Run 对应 Job")
    cancel.add_argument("--run-id", type=_uuid, required=True)
    return parser


def _run_payload(run, job) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """输出不含正文与冻结别名明细的安全运维投影。"""

    return {
        "run_id": str(run.id),
        "job_id": str(run.job_id),
        "job_status": job.status,
        "job_progress": job.progress,
        "job_error_code": job.error_code,
        "catalog_version": run.catalog_snapshot.catalog_version,
        "shard_index": run.shard_index,
        "shard_count": run.shard_count,
        "start_after_content_id": (
            None if run.start_after_content_id is None else str(run.start_after_content_id)
        ),
        "end_at_content_id": (
            None if run.end_at_content_id is None else str(run.end_at_content_id)
        ),
        "checkpoint_content_id": (
            None if run.checkpoint_content_id is None else str(run.checkpoint_content_id)
        ),
        "batch_size": run.batch_size,
        "max_contents": run.max_contents,
        "processed_count": run.processed_count,
        "matched_count": run.matched_count,
        "unmatched_count": run.unmatched_count,
        "brand_evidence_count": run.brand_evidence_count,
        "vehicle_evidence_count": run.vehicle_evidence_count,
        "conflict_count": run.conflict_count,
        "brand_locked_count": run.brand_locked_count,
        "vehicle_locked_count": run.vehicle_locked_count,
        "created_by": run.created_by,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


def main() -> None:
    """执行一次本地受控运维命令；不会自行启动 Worker 或扩大范围。"""

    args = _build_parser().parse_args()
    runtime = create_platform_runtime("content-reclassification")
    try:
        session = runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresContentReclassificationRepository(session)
                run: ContentReclassificationRunRecord
                job: JobRecord
                if args.command == "start":
                    run, job = repository.enqueue(
                        idempotency_key=args.idempotency_key,
                        shard_index=args.shard_index,
                        shard_count=args.shard_count,
                        start_after_content_id=args.start_after_content_id,
                        end_at_content_id=args.end_at_content_id,
                        batch_size=args.batch_size,
                        max_contents=args.max_contents,
                        created_by=args.created_by,
                        request_id=args.request_id,
                    )
                else:
                    maybe_run = repository.get(args.run_id)
                    run = maybe_run
                    if run is None:
                        raise SystemExit(f"找不到重分类 Run: {args.run_id}")
                    maybe_job = (
                        repository.request_cancel(args.run_id)
                        if args.command == "cancel"
                        else repository.get_job(args.run_id)
                    )
                    if maybe_job is None:
                        raise SystemExit(f"重分类 Run 缺少 Job: {args.run_id}")
                    job = maybe_job
                payload = _run_payload(run, job)
        finally:
            session.close()
    finally:
        runtime.close()
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
