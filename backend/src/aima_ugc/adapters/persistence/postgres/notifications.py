"""Notification Owner 的 Principal Inbox Repository。"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult, RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.notification.tables import (
    notification_events_table,
    notification_inbox_items_table,
)
from aima_ugc.platform.time import beijing_now


class PostgresNotificationRepository:
    def __init__(self, session: Session) -> None:
        """绑定调用方事务中的 PostgreSQL Session。"""

        self._session = session

    def publish_to_principal(
        self,
        *,
        deduplication_key: str,
        principal_id: str,
        event_type: str,
        title: str,
        message: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        safe_detail: dict[str, object] | None = None,
    ) -> UUID:
        """幂等创建安全事件，并投递给指定 Principal。"""

        event_id = uuid4()
        now = beijing_now()
        event_id = cast(
            UUID,
            self._session.scalar(
                pg_insert(notification_events_table)
                .values(
                    id=event_id,
                    deduplication_key=deduplication_key,
                    event_type=event_type,
                    title=title,
                    message=message,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    safe_detail=safe_detail or {},
                    created_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[notification_events_table.c.deduplication_key],
                    set_={"deduplication_key": deduplication_key},
                )
                .returning(notification_events_table.c.id)
            ),
        )
        self._session.execute(
            pg_insert(notification_inbox_items_table)
            .values(
                id=uuid4(),
                event_id=event_id,
                principal_id=principal_id,
                is_read=False,
                created_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    notification_inbox_items_table.c.event_id,
                    notification_inbox_items_table.c.principal_id,
                ]
            )
        )
        return event_id

    def list_for_principal(
        self, principal_id: str, *, limit: int
    ) -> tuple[tuple[RowMapping, ...], int]:
        """读取指定 Principal 的最近通知及全量未读数。"""

        rows = tuple(
            self._session.execute(
                select(
                    notification_inbox_items_table,
                    notification_events_table.c.event_type,
                    notification_events_table.c.title,
                    notification_events_table.c.message,
                    notification_events_table.c.resource_type,
                    notification_events_table.c.resource_id,
                )
                .join(
                    notification_events_table,
                    notification_events_table.c.id == notification_inbox_items_table.c.event_id,
                )
                .where(notification_inbox_items_table.c.principal_id == principal_id)
                .order_by(
                    notification_inbox_items_table.c.created_at.desc(),
                    notification_inbox_items_table.c.id.desc(),
                )
                .limit(limit)
            ).mappings()
        )
        unread = int(
            self._session.scalar(
                select(func.count())
                .select_from(notification_inbox_items_table)
                .where(
                    notification_inbox_items_table.c.principal_id == principal_id,
                    notification_inbox_items_table.c.is_read.is_(False),
                )
            )
            or 0
        )
        return rows, unread

    def mark_read(self, principal_id: str, item_ids: tuple[UUID, ...]) -> int:
        """仅把当前 Principal 自己尚未读的 Inbox Item 标记为已读。"""

        now = beijing_now()
        result = cast(
            CursorResult[Any],
            self._session.execute(
                update(notification_inbox_items_table)
                .where(
                    notification_inbox_items_table.c.id.in_(item_ids),
                    notification_inbox_items_table.c.principal_id == principal_id,
                    notification_inbox_items_table.c.is_read.is_(False),
                )
                .values(is_read=True, read_at=now)
            ),
        )
        return int(result.rowcount or 0)


__all__ = ["PostgresNotificationRepository"]
