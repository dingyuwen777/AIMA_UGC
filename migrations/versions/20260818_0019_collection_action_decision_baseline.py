"""为 Collection 内容动作补齐首次 Decision 的 previous-state 基线。

Revision ID: 20260818_0019
Revises: 20260818_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_0019"
down_revision: str | Sequence[str] | None = "20260818_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collection_content_actions",
        sa.Column("previous_exists", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "collection_content_actions",
        sa.Column("previous_comment_count", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "collection_content_actions",
        sa.Column(
            "initial_business_changed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_check_constraint(
        op.f("ck_collection_content_actions_previous_comment_count_nonnegative"),
        "collection_content_actions",
        "previous_comment_count is null or previous_comment_count >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_collection_content_actions_previous_comment_count_nonnegative"),
        "collection_content_actions",
        type_="check",
    )
    op.drop_column("collection_content_actions", "initial_business_changed")
    op.drop_column("collection_content_actions", "previous_comment_count")
    op.drop_column("collection_content_actions", "previous_exists")
