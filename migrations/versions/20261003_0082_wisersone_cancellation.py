"""持久取消传播期间单独展示 cancelling，子执行结清后才进入终态。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0082"
down_revision: str | Sequence[str] | None = "20261003_0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAME = "ck_ingestion_wisersone_downloads_status_allowed"
_TABLE = "ingestion_wisersone_downloads"
_BEFORE = (
    "status in ('queued','submitting','waiting','downloading','preflight','importing',"
    "'succeeded','partial_failed','failed','cancelled','attention')"
)


def upgrade() -> None:
    op.drop_constraint(op.f(_NAME), _TABLE, type_="check")
    op.create_check_constraint(op.f(_NAME), _TABLE, _BEFORE[:-1] + ",'cancelling')")


def downgrade() -> None:
    if op.get_bind().scalar(sa.text(f"SELECT count(*) FROM {_TABLE} WHERE status='cancelling'")):
        raise RuntimeError("仍有 WisersOne 取消传播任务，不能回退状态约束。")
    op.drop_constraint(op.f(_NAME), _TABLE, type_="check")
    op.create_check_constraint(op.f(_NAME), _TABLE, _BEFORE)
