"""System Settings 与 Audit PostgreSQL Repository。"""

from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from pydantic import JsonValue

from aima_ugc.modules.system.models import AuditEvent, SystemSetting
from aima_ugc.modules.system.tables import audit_events_table, system_settings_table


def _setting_from_row(row: RowMapping) -> SystemSetting:
    return SystemSetting(
        key=row["key"],
        value=row["value"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresSystemSettingsRepository:
    """调用方拥有事务；同 key 更新时递增版本。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> SystemSetting | None:
        row = (
            self._session.execute(
                select(system_settings_table).where(system_settings_table.c.key == key)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _setting_from_row(row)

    def put(self, key: str, value: JsonValue) -> SystemSetting:
        now = func.clock_timestamp()
        statement = pg_insert(system_settings_table).values(
            key=key,
            value=value,
            version=1,
            created_at=now,
            updated_at=now,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[system_settings_table.c.key],
            set_={
                "value": statement.excluded.value,
                "version": system_settings_table.c.version + 1,
                "updated_at": func.clock_timestamp(),
            },
        ).returning(system_settings_table)
        row = self._session.execute(statement).mappings().one()
        return _setting_from_row(row)


class PostgresAuditRepository:
    """审计记录只追加，不提供更新或删除能力。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> None:
        self._session.execute(
            insert(audit_events_table).values(
                id=event.id,
                actor_kind=event.actor_kind,
                actor_ref=event.actor_ref,
                event_type=event.event_type,
                object_type=event.object_type,
                object_id=event.object_id,
                request_id=event.request_id,
                safe_detail=event.safe_detail,
                created_at=event.created_at,
            )
        )
