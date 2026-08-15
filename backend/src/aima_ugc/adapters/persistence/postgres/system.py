"""System Settings、Provider Config 与 Audit PostgreSQL Repository。"""

from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.system.models import AuditEvent, ProviderConfig, SystemSetting
from aima_ugc.modules.system.tables import (
    audit_events_table,
    provider_configs_table,
    system_settings_table,
)


def _setting_from_row(row: RowMapping) -> SystemSetting:
    return SystemSetting(
        key=row["key"],
        value=row["value"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _provider_config_from_row(row: RowMapping) -> ProviderConfig:
    return ProviderConfig(
        id=row["id"],
        provider=row["provider"],
        display_name=row["display_name"],
        base_url=row["base_url"],
        secret_ref=row["secret_ref"],
        enabled=row["enabled"],
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
        insert_statement = pg_insert(system_settings_table).values(
            key=key,
            value=value,
            version=1,
            created_at=now,
            updated_at=now,
        )
        upsert_statement = insert_statement.on_conflict_do_update(
            index_elements=[system_settings_table.c.key],
            set_={
                "value": insert_statement.excluded.value,
                "version": system_settings_table.c.version + 1,
                "updated_at": func.clock_timestamp(),
            },
        ).returning(system_settings_table)
        row = self._session.execute(upsert_statement).mappings().one()
        return _setting_from_row(row)


class PostgresProviderConfigRepository:
    """Provider Config 的 System Owner Repository；Provider 类型与稳定 UUID 不可原地改写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, config_id: UUID) -> ProviderConfig | None:
        row = (
            self._session.execute(
                select(provider_configs_table).where(provider_configs_table.c.id == config_id)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _provider_config_from_row(row)

    def create(self, config: ProviderConfig) -> ProviderConfig:
        now = func.clock_timestamp()
        row = (
            self._session.execute(
                insert(provider_configs_table)
                .values(
                    id=config.id,
                    provider=config.provider,
                    display_name=config.display_name,
                    base_url=config.base_url,
                    secret_ref=config.secret_ref,
                    enabled=config.enabled,
                    created_at=now,
                    updated_at=now,
                )
                .returning(provider_configs_table)
            )
            .mappings()
            .one()
        )
        return _provider_config_from_row(row)

    def update_settings(
        self,
        config_id: UUID,
        *,
        display_name: str,
        base_url: str,
        secret_ref: str,
        enabled: bool,
    ) -> ProviderConfig:
        current = self.get(config_id)
        if current is None:
            raise KeyError(f"Provider Config 不存在: {config_id}")
        validated = ProviderConfig(
            id=current.id,
            provider=current.provider,
            display_name=display_name,
            base_url=base_url,
            secret_ref=secret_ref,
            enabled=enabled,
        )
        row = (
            self._session.execute(
                update(provider_configs_table)
                .where(provider_configs_table.c.id == config_id)
                .values(
                    display_name=validated.display_name,
                    base_url=validated.base_url,
                    secret_ref=validated.secret_ref,
                    enabled=validated.enabled,
                    updated_at=func.clock_timestamp(),
                )
                .returning(provider_configs_table)
            )
            .mappings()
            .one()
        )
        return _provider_config_from_row(row)


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
