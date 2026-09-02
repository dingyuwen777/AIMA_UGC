"""以更窄的 Audit Repository 锚点执行一次性 CHG-314 补丁。"""

from __future__ import annotations

import apply_chg314 as patch


def patch_audit_repository_and_service() -> None:
    path = "backend/src/aima_ugc/adapters/persistence/postgres/system.py"
    patch.replace_once(
        path,
        '''    def list_recent(self, *, limit: int) -> tuple[AuditEvent, ...]:
        """按时间倒序返回有界审计事件，不提供任意正文搜索。"""

        rows = self._session.execute(
            select(audit_events_table)
            .order_by(audit_events_table.c.created_at.desc(), audit_events_table.c.id.desc())
            .limit(limit)
        ).mappings()
        return tuple(
            AuditEvent(
                id=row["id"],
                actor_kind=row["actor_kind"],
                actor_ref=row["actor_ref"],
                event_type=row["event_type"],
                object_type=row["object_type"],
                object_id=row["object_id"],
                request_id=row["request_id"],
                safe_detail=row["safe_detail"],
                created_at=row["created_at"],
            )
            for row in rows
        )
''',
        '''    def list_page(self, *, offset: int, limit: int) -> tuple[AuditEvent, ...]:
        """按时间倒序分页读取审计事件，不提供任意正文搜索。"""

        rows = self._session.execute(
            select(audit_events_table)
            .order_by(audit_events_table.c.created_at.desc(), audit_events_table.c.id.desc())
            .offset(offset)
            .limit(limit)
        ).mappings()
        return tuple(
            AuditEvent(
                id=row["id"],
                actor_kind=row["actor_kind"],
                actor_ref=row["actor_ref"],
                event_type=row["event_type"],
                object_type=row["object_type"],
                object_id=row["object_id"],
                request_id=row["request_id"],
                safe_detail=row["safe_detail"],
                created_at=row["created_at"],
            )
            for row in rows
        )

    def list_recent(self, *, limit: int) -> tuple[AuditEvent, ...]:
        """兼容旧内部调用，等价于读取第一页。"""

        return self.list_page(offset=0, limit=limit)

    def count(self) -> int:
        """返回完整审计事件数量，供稳定分页使用。"""

        return int(self._session.scalar(select(func.count()).select_from(audit_events_table)) or 0)
''',
    )

    path = "backend/src/aima_ugc/bootstrap/administration_http.py"
    patch.replace_once(
        path,
        '''    def list_audit_events(self, *, limit: int) -> AuditEventListResponse:
        """管理员读取最近审计记录。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                events = PostgresAuditRepository(session).list_recent(limit=limit)
                return AuditEventListResponse(
                    items=tuple(
                        AuditEventResponse(
                            id=event.id,
                            actor_ref=event.actor_ref,
                            event_type=event.event_type,
                            object_type=event.object_type,
                            object_id=event.object_id,
                            request_id=event.request_id,
                            safe_detail=cast(dict[str, object], event.safe_detail),
                            created_at=event.created_at,
                        )
                        for event in events
                    )
                )
        finally:
            session.close()
''',
        '''    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:
        """管理员分页读取完整审计历史。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAuditRepository(session)
                events = repository.list_page(offset=offset, limit=limit)
                return AuditEventListResponse(
                    items=tuple(
                        AuditEventResponse(
                            id=event.id,
                            actor_ref=event.actor_ref,
                            event_type=event.event_type,
                            object_type=event.object_type,
                            object_id=event.object_id,
                            request_id=event.request_id,
                            safe_detail=cast(dict[str, object], event.safe_detail),
                            created_at=event.created_at,
                        )
                        for event in events
                    ),
                    total=repository.count(),
                    offset=offset,
                    limit=limit,
                )
        finally:
            session.close()
''',
    )

    path = "backend/src/aima_ugc/modules/administration/http.py"
    patch.replace_once(
        path,
        '''    def list_audit_events(self, *, limit: int) -> AuditEventListResponse:
        """读取最近管理员安全审计摘要。"""

        ...
''',
        '''    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:
        """分页读取管理员安全审计摘要。"""

        ...
''',
    )


def main() -> None:
    patch.patch_keyword_contract()
    patch.patch_keyword_service()
    patch.patch_audit_contract()
    patch_audit_repository_and_service()
    patch.patch_audit_route()
    patch.patch_historical_retry_fact()
    patch.patch_frontend_consumers()


if __name__ == "__main__":
    main()
