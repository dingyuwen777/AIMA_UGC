"""Stage 7 Scheduler 对 Collection Plan 表追加的已批准策略约束。"""

from sqlalchemy import CheckConstraint

from aima_ugc.modules.collection.tables import collection_plans_table


def register_scheduler_schema() -> None:
    """把已批准的 Scheduler 策略约束注册到共享 SQLAlchemy metadata。"""
    existing_names = {constraint.name for constraint in collection_plans_table.constraints}
    if "ck_collection_plans_misfire_policy_latest_only" not in existing_names:
        collection_plans_table.append_constraint(
            CheckConstraint(
                "misfire_policy = 'latest_only'",
                name="misfire_policy_latest_only",
            )
        )
    if "ck_collection_plans_max_catch_up_runs_first_release" not in existing_names:
        collection_plans_table.append_constraint(
            CheckConstraint(
                "max_catch_up_runs = 0",
                name="max_catch_up_runs_first_release",
            )
        )


__all__ = ["register_scheduler_schema"]
