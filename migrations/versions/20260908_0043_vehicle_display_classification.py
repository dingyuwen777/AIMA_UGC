"""为已有车型目录增加可空系列和类别展示字段。

Revision ID: 20260908_0043
Revises: 20260907_0042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0043"
down_revision: str | Sequence[str] | None = "20260907_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """保留旧车型身份和数据，由管理员逐步补充展示分类。"""
    for field in ("series_name", "category_name"):
        op.add_column("vehicle_models", sa.Column(field, sa.Text(), nullable=True))
        op.create_check_constraint(
            op.f(f"ck_vehicle_models_{field}_valid"),
            "vehicle_models",
            f"{field} is null or char_length(trim({field})) between 1 and 200",
        )


def downgrade() -> None:
    """删除新增展示分类；执行前须导出已录入的系列和类别。"""
    for field in ("category_name", "series_name"):
        op.drop_constraint(
            op.f(f"ck_vehicle_models_{field}_valid"), "vehicle_models", type_="check"
        )
        op.drop_column("vehicle_models", field)
