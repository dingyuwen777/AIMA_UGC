"""Analysis Owner 分析方案归档列的 SQLAlchemy 注册。"""

from sqlalchemy import CheckConstraint, Column, DateTime

from .scheme_tables import analysis_schemes_table


def register_analysis_lifecycle_schema() -> None:
    """为 Analysis Scheme 追加独立于 active 的归档状态。"""

    if "archived_at" in analysis_schemes_table.c:
        return
    analysis_schemes_table.append_column(Column("archived_at", DateTime(timezone=True)))
    analysis_schemes_table.append_constraint(
        CheckConstraint(
            "archived_at is null or not is_active",
            name="archived_analysis_scheme_inactive",
        )
    )


__all__ = ["register_analysis_lifecycle_schema"]
