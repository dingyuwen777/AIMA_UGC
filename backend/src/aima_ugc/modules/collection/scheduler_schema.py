"""Stage 7 Scheduler 对 Collection Plan 表追加的已批准策略约束。"""

from sqlalchemy import CheckConstraint

from aima_ugc.modules.collection.tables import collection_plans_table

collection_plans_table.append_constraint(
    CheckConstraint(
        "misfire_policy = 'latest_only'",
        name="misfire_policy_latest_only",
    )
)
collection_plans_table.append_constraint(
    CheckConstraint(
        "max_catch_up_runs = 0",
        name="max_catch_up_runs_first_release",
    )
)

__all__ = []
