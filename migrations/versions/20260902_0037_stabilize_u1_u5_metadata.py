"""稳定 U1—U5 约束名称并消除数据库元数据漂移。

Revision ID: 20260902_0037
Revises: 20260902_0036
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260902_0037"
down_revision: str | Sequence[str] | None = "20260902_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """把 PostgreSQL 截断后的约束名改为稳定且不超过 63 字节的名称。"""

    op.execute(
        "ALTER TABLE content_availability_observations "
        "RENAME CONSTRAINT "
        "ck_content_availability_observations_confirmed_requires_64fd "
        "TO ck_content_availability_observations_confirmed_evidence"
    )
    op.execute(
        "ALTER TABLE content_availability_observations "
        "RENAME CONSTRAINT "
        "ck_content_availability_observations_technical_failure__7278 "
        "TO ck_content_availability_observations_technical_status"
    )


def downgrade() -> None:
    """恢复此前由 SQLAlchemy 截断并加摘要的历史约束名称。"""

    op.execute(
        "ALTER TABLE content_availability_observations "
        "RENAME CONSTRAINT "
        "ck_content_availability_observations_technical_status "
        "TO ck_content_availability_observations_technical_failure__7278"
    )
    op.execute(
        "ALTER TABLE content_availability_observations "
        "RENAME CONSTRAINT "
        "ck_content_availability_observations_confirmed_evidence "
        "TO ck_content_availability_observations_confirmed_requires_64fd"
    )
