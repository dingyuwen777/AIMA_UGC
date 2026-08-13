from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from aima_ugc.adapters.persistence.postgres.system import (
    PostgresAuditRepository,
    PostgresSystemSettingsRepository,
)
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.modules.system.tables import audit_events_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime


def test_settings_version_and_provider_neutral_audit() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    key = f"stage3a.test.{uuid4()}"
    event_id = uuid4()
    try:
        settings = PostgresSystemSettingsRepository(session)
        audit = PostgresAuditRepository(session)
        with session.begin():
            first = settings.put(key, {"enabled": True})
        with session.begin():
            second = settings.put(key, {"enabled": False})
            loaded = settings.get(key)
        with session.begin():
            audit.append(
                AuditEvent(
                    id=event_id,
                    actor_kind="system",
                    actor_ref=None,
                    event_type="stage3a.integration.verified",
                    object_type="system_setting",
                    object_id=key,
                    request_id=None,
                    safe_detail={"version": second.version},
                    created_at=datetime.now(UTC),
                )
            )
        with session.begin():
            actor_kind = session.execute(
                select(audit_events_table.c.actor_kind).where(
                    audit_events_table.c.id == event_id
                )
            ).scalar_one()
        assert first.version == 1
        assert second.version == 2
        assert loaded == second
        assert actor_kind == "system"
    finally:
        session.close()
        runtime.dispose()
