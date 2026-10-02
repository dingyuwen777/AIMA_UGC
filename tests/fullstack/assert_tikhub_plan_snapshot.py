"""验证真实浏览器创建的计划经生产 Scheduler 冻结到 Run。"""

from __future__ import annotations

import json
import os
import sys
from uuid import UUID

from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.bootstrap.scheduler import create_scheduler_runtime, run_scheduler_once
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_schedule_occurrences_table,
)
from aima_ugc.platform.time import beijing_now
from sqlalchemy import select


def main() -> None:
    """仅在显式隔离测试环境中执行生产 tick，不启动 Worker 或调用 Provider。"""
    if os.environ.get("AIMA_FULLSTACK_SEED") != "1":
        raise RuntimeError("Scheduler 验证仅允许 AIMA_FULLSTACK_SEED=1 的隔离环境")
    plan_id = UUID(sys.argv[1])
    expected_mode = sys.argv[2]
    expected_version = int(sys.argv[3])
    runtime = create_scheduler_runtime()
    try:
        run_scheduler_once(runtime, now=beijing_now())
        with runtime.database.new_session() as session:
            plan = PostgresCollectionPlanningRepository(session).get_plan(plan_id)
            assert plan is not None and plan.next_run_at is not None
            scheduled_for = plan.next_run_at
        run_scheduler_once(runtime, now=scheduled_for)
        with runtime.database.new_session() as session:
            snapshots = (
                session.execute(
                    select(collection_runs_table.c.config_snapshot)
                    .join(
                        collection_schedule_occurrences_table,
                        collection_runs_table.c.occurrence_id
                        == collection_schedule_occurrences_table.c.id,
                    )
                    .where(collection_schedule_occurrences_table.c.plan_id == plan_id)
                )
                .scalars()
                .all()
            )
            snapshot = next(
                item for item in snapshots if item["schedule_version"] == expected_version
            )
            assert snapshot["schema_version"] == "collection-run-config.v4"
            assert snapshot["plan_type"] == "tikhub"
            assert snapshot["comment_policy"] == expected_mode
            assert snapshot["decision_policy"]["comment_mode"] == expected_mode
            if len(sys.argv) > 4:
                previous = next(
                    item for item in snapshots if item["schedule_version"] == expected_version - 1
                )
                assert previous["comment_policy"] == sys.argv[4]
                assert previous["decision_policy"]["comment_mode"] == sys.argv[4]
            print(json.dumps(snapshot, ensure_ascii=False))
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
