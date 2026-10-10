"""对显式有限目标预检、启动、查看或取消历史一致性修复。"""

import argparse
import json
from uuid import UUID

from aima_ugc.adapters.persistence.postgres.content_consistency_repair import (
    PostgresContentConsistencyRepairRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.content_consistency_repair_worker import repair_run_progress
from aima_ugc.bootstrap.runtime import create_platform_runtime


def _build_parser() -> argparse.ArgumentParser:
    """范围必须明确给出，命令不隐式扫描全库或启动 Worker。"""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("dry-run", "start"):
        child = subparsers.add_parser(command)
        scope = child.add_mutually_exclusive_group(required=True)
        scope.add_argument("--content-id", type=UUID, action="append", dest="content_ids")
        scope.add_argument("--collection-run-id", type=UUID)
        child.add_argument("--max-contents", type=int, required=True)
        child.add_argument("--batch-size", type=int, default=200)
        if command == "start":
            child.add_argument("--idempotency-key", required=True)
            child.add_argument("--created-by", required=True)
            child.add_argument("--request-id")
    for command in ("status", "cancel"):
        child = subparsers.add_parser(command)
        child.add_argument("--run-id", type=UUID, required=True)
    return parser


def main() -> None:
    """仅运行显式命令；生产执行仍由操作者单独授权和限定范围。"""
    parser = _build_parser()
    args = parser.parse_args()
    runtime = create_platform_runtime("content-consistency-repair")
    try:
        with runtime.database.new_session() as session, session.begin():
            repository = PostgresContentConsistencyRepairRepository(session)
            if args.command in ("dry-run", "start"):
                scope = {
                    "content_ids": tuple(args.content_ids or ()),
                    "collection_run_id": args.collection_run_id,
                    "max_contents": args.max_contents,
                    "batch_size": args.batch_size,
                }
                if args.command == "dry-run":
                    # Repeatable read 保证有限多页看到一致事实；不取得目录写锁、不持久写入。
                    session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                    payload = repository.dry_run(**scope)
                else:
                    run, job = repository.enqueue(
                        **scope,
                        idempotency_key=args.idempotency_key,
                        created_by=args.created_by,
                        request_id=args.request_id,
                    )
                    payload = repair_run_progress(run)
                    payload["job_status"] = job.status
            else:
                existing_run = repository.get(args.run_id)
                if existing_run is None:
                    raise ValueError("找不到修复 Run")
                existing_job = (
                    repository.request_cancel(existing_run.id)
                    if args.command == "cancel"
                    else PostgresJobRepository(session).get(existing_run.job_id)
                )
                if existing_job is None:
                    raise ValueError("修复 Run 缺少 Job")
                payload = repair_run_progress(existing_run)
                payload.update(
                    job_status=existing_job.status,
                    job_progress=existing_job.progress,
                    job_error_code=existing_job.error_code,
                )
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        runtime.close()
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
