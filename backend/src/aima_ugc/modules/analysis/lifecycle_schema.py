"""Analysis Owner 分析方案归档与管理视图删除列的 SQLAlchemy 注册。"""

from sqlalchemy import CheckConstraint, Column, DateTime, Index

from .scheme_tables import analysis_schemes_table


def register_analysis_lifecycle_schema() -> None:
    """为 Analysis Scheme 注册归档与管理视图删除状态。"""

    if "archived_at" not in analysis_schemes_table.c:
        analysis_schemes_table.append_column(Column("archived_at", DateTime(timezone=True)))
        analysis_schemes_table.append_constraint(
            CheckConstraint(
                "archived_at is null or not is_active",
                name="archived_analysis_scheme_inactive",
            )
        )

    if "deleted_at" in analysis_schemes_table.c:
        return

    analysis_schemes_table.append_column(Column("deleted_at", DateTime(timezone=True)))
    analysis_schemes_table.append_constraint(
        CheckConstraint(
            "deleted_at is null or (archived_at is not null and not is_active)",
            name="deleted_analysis_scheme_archived_inactive",
        )
    )
    Index(
        "uq_analysis_schemes_live_name",
        analysis_schemes_table.c.name,
        unique=True,
        postgresql_where=analysis_schemes_table.c.deleted_at.is_(None),
    )


__all__ = ["register_analysis_lifecycle_schema"]
