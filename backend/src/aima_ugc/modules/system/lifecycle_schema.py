"""System Owner 业务资源归档列的 SQLAlchemy 注册。"""

from sqlalchemy import CheckConstraint, Column, DateTime

from .tables import keyword_packs_table, provider_configs_table


def register_system_lifecycle_schema() -> None:
    """为 Provider Config 与 Keyword Pack 追加可归档生命周期字段。"""

    if "archived_at" not in provider_configs_table.c:
        provider_configs_table.append_column(Column("archived_at", DateTime(timezone=True)))
        provider_configs_table.append_constraint(
            CheckConstraint(
                "archived_at is null or (not enabled and not is_default)",
                name="archived_provider_inactive",
            )
        )
    if "archived_at" not in keyword_packs_table.c:
        keyword_packs_table.append_column(Column("archived_at", DateTime(timezone=True)))
        keyword_packs_table.append_constraint(
            CheckConstraint(
                "archived_at is null or not enabled",
                name="archived_keyword_pack_disabled",
            )
        )


__all__ = ["register_system_lifecycle_schema"]
