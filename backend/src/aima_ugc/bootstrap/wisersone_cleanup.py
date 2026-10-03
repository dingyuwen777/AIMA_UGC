"""只清理已终结七天的系统受管下载文件，保留认证与历史 Canonical。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import and_, or_, select

from aima_ugc.adapters.persistence.postgres.historical_import import (
    PostgresHistoricalImportRepository,
)
from aima_ugc.adapters.persistence.postgres.wisersone import PostgresWisersOneRepository
from aima_ugc.modules.ingestion.wisersone_jobs import WISERSONE_TERMINAL
from aima_ugc.modules.ingestion.wisersone_tables import wisersone_downloads_table as table
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime
from .wisersone_http import managed_input_root


def cleanup_wisersone_files(
    runtime: PlatformRuntime, *, now: datetime | None = None, limit: int = 100
) -> int:
    """先认领删除意图以阻止重入，再删文件；失败的意图保留给下次 housekeeping。"""
    observed = now or beijing_now()
    if observed.utcoffset() is None:
        raise ValueError("WisersOne cleanup 时间必须带时区。")
    cutoff = observed - timedelta(days=7)
    claimed: list[UUID] = []
    with runtime.database.new_session() as session, session.begin():
        repo = PostgresWisersOneRepository(session)
        rows = (
            session.execute(
                select(table)
                .where(
                    table.c.file_deleted_at.is_(None),
                    or_(
                        table.c.file_delete_pending_at.is_not(None),
                        and_(table.c.status.in_(WISERSONE_TERMINAL), table.c.finished_at <= cutoff),
                    ),
                )
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        for row in rows:
            campaign_id = cast(UUID | None, row["campaign_id"])
            if campaign_id is not None:
                campaign = PostgresHistoricalImportRepository(session).get_campaign(campaign_id)
                if (
                    campaign is None
                    or campaign["finished_at"] is None
                    or campaign["finished_at"] > cutoff
                    or campaign["status"]
                    not in {"succeeded", "partial_failed", "failed", "cancelled", "revoked"}
                ):
                    continue
            download_id = cast(UUID, row["id"])
            repo.update(download_id, file_delete_pending_at=observed)
            claimed.append(download_id)
    if not claimed:
        return 0
    root = managed_input_root(runtime).resolve()
    deleted = 0
    for download_id in claimed:
        for folder in (root / str(download_id), root / ".staging" / str(download_id)):
            if folder.is_symlink() or not folder.resolve().is_relative_to(root):
                raise RuntimeError("WisersOne 清理目标越过受管目录。")
            for filename in ("wisersone_last24h.xlsx", "wisersone_last24h.xlsx.part"):
                file = folder / filename
                if file.is_symlink() or not file.resolve().is_relative_to(root):
                    raise RuntimeError("WisersOne 清理文件越过受管目录。")
                file.unlink(missing_ok=True)
            if folder.exists():
                # 只移除空的任务目录，不递归删除未知用户文件。
                try:
                    folder.rmdir()
                except OSError:
                    pass
        with runtime.database.new_session() as session, session.begin():
            PostgresWisersOneRepository(session).update(
                download_id, file_deleted_at=observed, file_delete_pending_at=None
            )
        deleted += 1
    return deleted
