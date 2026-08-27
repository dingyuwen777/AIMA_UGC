"""在隔离 Full-stack 数据库注入一个尚未执行业务写入的失败 Chunk。"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from uuid import UUID

from aima_ugc.bootstrap.runtime import create_platform_runtime
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
)
from sqlalchemy import func, select, update


def _require_fullstack_seed_opt_in(environ: Mapping[str, str]) -> None:
    """避免测试故障注入脚本误用于普通或生产运行环境。"""

    if environ.get("AIMA_FULLSTACK_SEED") != "1":
        raise RuntimeError(
            "拒绝注入 Historical Chunk 故障：请仅在隔离测试数据库中设置 AIMA_FULLSTACK_SEED=1。"
        )


def main() -> None:
    """把已预检 Campaign 的首个 ready Chunk 标成业务写入前失败。"""

    if len(sys.argv) != 2:
        raise SystemExit(
            "用法: python tests/fullstack/force_stage12_ready_chunk_failed.py <campaign-id>"
        )
    _require_fullstack_seed_opt_in(os.environ)
    campaign_id = UUID(sys.argv[1])
    runtime = create_platform_runtime("stage12-fullstack-fault")
    session = runtime.database.new_session()
    try:
        with session.begin():
            campaign_status = session.scalar(
                select(historical_import_campaigns_table.c.status)
                .where(historical_import_campaigns_table.c.id == campaign_id)
                .with_for_update()
            )
            if campaign_status != "ready":
                raise RuntimeError("故障注入只允许作用于已完成预检的 ready Campaign")
            chunk_ids = tuple(
                session.execute(
                    select(historical_import_campaign_items_table.c.id)
                    .where(
                        historical_import_campaign_items_table.c.campaign_id == campaign_id,
                        historical_import_campaign_items_table.c.item_kind == "chunk",
                        historical_import_campaign_items_table.c.status == "ready",
                    )
                    .order_by(historical_import_campaign_items_table.c.ordinal)
                    .with_for_update()
                ).scalars()
            )
            if len(chunk_ids) < 2:
                raise RuntimeError("Stage 12 Full-stack 恢复路径至少需要两个 Chunk")
            session.execute(
                update(historical_import_campaign_items_table)
                .where(historical_import_campaign_items_table.c.id == chunk_ids[0])
                .values(
                    status="failed",
                    error_code="fullstack_injected_prewrite_failure",
                    finished_at=func.clock_timestamp(),
                )
            )
    finally:
        session.close()
        runtime.close()


if __name__ == "__main__":
    main()
