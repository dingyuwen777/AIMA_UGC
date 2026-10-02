"""Content Owner 的评论完整度读模型，从已有Coverage事实推导，不维护平行状态表。"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from aima_ugc.modules.content.extended_tables import comment_thread_coverage_observations_table
from aima_ugc.modules.content.tables import comment_coverage_observations_table, comments_table


@dataclass(frozen=True, slots=True)
class CommentThreadCaptureState:
    """一个线程最近一次实际请求的结果；未请求记录不覆盖既有请求事实。"""

    reported_total: int | None = None
    complete: bool = False


class PostgresContentCoverageReader:
    """按同一数据库快照聚合一级分页与每个必要线程的最新实际采集事实。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def thread_states(self, content_id: UUID) -> dict[str, CommentThreadCaptureState]:
        table = comment_thread_coverage_observations_table
        rows = self._session.execute(
            select(table)
            .where(table.c.content_id == content_id, table.c.coverage != "not_requested")
            .distinct(table.c.root_comment_id)
            .order_by(table.c.root_comment_id, table.c.observed_at.desc(), table.c.id.desc())
        ).mappings()
        return {
            row["root_comment_id"]: CommentThreadCaptureState(
                reported_total=row["reported_total"],
                complete=row["coverage"] == "complete",
            )
            for row in rows
        }

    def necessary_threads_complete(self, content_id: UUID) -> bool:
        states = self.thread_states(content_id)
        roots = self._session.execute(
            select(
                comments_table.c.external_comment_id, comments_table.c.current_reply_count
            ).where(
                comments_table.c.content_id == content_id,
                or_(
                    comments_table.c.root_comment_id.is_(None),
                    comments_table.c.root_comment_id == comments_table.c.external_comment_id,
                ),
            )
        ).all()
        for root_id, reply_count in roots:
            if reply_count == 0:
                continue
            state = states.get(root_id)
            if state is None or not state.complete:
                return False
            if reply_count is not None and reply_count != state.reported_total:
                return False
        return True

    def full_capture_complete(self, content_id: UUID, *, comment_count: int | None) -> bool:
        table = comment_coverage_observations_table
        root = (
            self._session.execute(
                select(table)
                .where(table.c.content_id == content_id, table.c.coverage != "not_requested")
                .order_by(table.c.observed_at.desc(), table.c.id.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if root is None or root["coverage"] != "complete":
            return False
        if comment_count is not None and root["reported_total"] != comment_count:
            return False
        return self.necessary_threads_complete(content_id)
