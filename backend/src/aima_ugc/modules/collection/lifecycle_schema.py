"""Collection Owner 采集计划归档列的 SQLAlchemy 注册。"""

from sqlalchemy import CheckConstraint, Column, DateTime

from .tables import collection_plans_table


def register_collection_lifecycle_schema() -> None:
    """为 Collection Plan 追加独立于 enabled 的归档状态。"""

    if "archived_at" in collection_plans_table.c:
        return
    collection_plans_table.append_column(Column("archived_at", DateTime(timezone=True)))
    collection_plans_table.append_constraint(
        CheckConstraint(
            "archived_at is null or not enabled",
            name="archived_collection_plan_disabled",
        )
    )


__all__ = ["register_collection_lifecycle_schema"]
