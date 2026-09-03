"""System Settings、Provider Config 与 Audit PostgreSQL Repository。"""

from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.system.models import AuditEvent, ProviderConfig, ProviderKind, SystemSetting
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
        provider_kind=row["provider_kind"],
        display_name=row["display_name"],
        base_url=row["base_url"],
        model=row["model"],
        secret_ref=row["secret_ref"],
        timeout_seconds=row["timeout_seconds"],
        max_retries=row["max_retries"],
        max_concurrency=row["max_concurrency"],
        max_rps=row["max_rps"],
        extra_config=dict(row["extra_config"]),
        is_default=row["is_default"],
        revision=row["revision"],
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
    """System Owner Repository；稳定 UUID/Provider Kind 不允许原地改写。"""

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

    def list_all(self, *, provider_kind: ProviderKind | None = None) -> tuple[ProviderConfig, ...]:
        statement = select(provider_configs_table)
        if provider_kind is not None:
            statement = statement.where(provider_configs_table.c.provider_kind == provider_kind)
        rows = self._session.execute(
            statement.order_by(
                provider_configs_table.c.provider_kind,
                provider_configs_table.c.display_name,
                provider_configs_table.c.id,
            )
        ).mappings()
        return tuple(_provider_config_from_row(row) for row in rows)

    def list_enabled(self) -> tuple[ProviderConfig, ...]:
        rows = self._session.execute(
            select(provider_configs_table)
            .where(provider_configs_table.c.enabled.is_(True))
            .order_by(provider_configs_table.c.display_name, provider_configs_table.c.id)
        ).mappings()
        return tuple(_provider_config_from_row(row) for row in rows)

    def get_default(self, provider_kind: ProviderKind) -> ProviderConfig | None:
        row = (
            self._session.execute(
                select(provider_configs_table).where(
                    provider_configs_table.c.provider_kind == provider_kind,
                    provider_configs_table.c.enabled.is_(True),
                    provider_configs_table.c.is_default.is_(True),
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _provider_config_from_row(row)

    def clear_default(self, provider_kind: ProviderKind, *, except_id: UUID | None = None) -> None:
        statement = update(provider_configs_table).where(
            provider_configs_table.c.provider_kind == provider_kind,
            provider_configs_table.c.is_default.is_(True),
        )
        if except_id is not None:
            statement = statement.where(provider_configs_table.c.id != except_id)
        self._session.execute(
            statement.values(is_default=False, updated_at=func.clock_timestamp())
        )

    def create(self, config: ProviderConfig) -> ProviderConfig:
        if config.is_default:
            self.clear_default(config.provider_kind)
        now = func.clock_timestamp()
        row = (
            self._session.execute(
                insert(provider_configs_table)
                .values(
                    id=config.id,
                    provider=config.provider,
                    provider_kind=config.provider_kind,
                    display_name=config.display_name,
                    base_url=config.base_url,
                    model=config.model,
                    secret_ref=config.secret_ref,
                    timeout_seconds=config.timeout_seconds,
                    max_retries=config.max_retries,
                    max_concurrency=config.max_concurrency,
                    max_rps=config.max_rps,
                    extra_config=config.extra_config,
                    is_default=config.is_default,
                    revision=config.revision,
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
        model: str | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
        max_concurrency: int | None = None,
        max_rps: int | None = None,
        extra_config: dict[str, JsonValue] | None = None,
        is_default: bool | None = None,
    ) -> ProviderConfig:
        current = self.get(config_id)
        if current is None:
            raise KeyError(f"Provider Config 不存在: {config_id}")
        validated = ProviderConfig(
            id=current.id,
            provider=current.provider,
            provider_kind=current.provider_kind,
            display_name=display_name,
            base_url=base_url,
            model=current.model if model is None else model,
            secret_ref=secret_ref,
            timeout_seconds=(current.timeout_seconds if timeout_seconds is None else timeout_seconds),
            max_retries=current.max_retries if max_retries is None else max_retries,
            max_concurrency=(
                current.max_concurrency if max_concurrency is None else max_concurrency
            ),
            max_rps=max_rps,
            extra_config=current.extra_config if extra_config is None else extra_config,
            is_default=current.is_default if is_default is None else is_default,
            revision=current.revision + 1,
            enabled=enabled,
        )
        if validated.is_default:
            self.clear_default(validated.provider_kind, except_id=config_id)
        row = (
            self._session.execute(
                update(provider_configs_table)
                .where(provider_configs_table.c.id == config_id)
                .values(
                    display_name=validated.display_name,
                    base_url=validated.base_url,
                    model=validated.model,
                    secret_ref=validated.secret_ref,
                    timeout_seconds=validated.timeout_seconds,
                    max_retries=validated.max_retries,
                    max_concurrency=validated.max_concurrency,
                    max_rps=validated.max_rps,
                    extra_config=validated.extra_config,
                    is_default=validated.is_default,
                    revision=validated.revision,
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

    def list_page(self, *, offset: int, limit: int) -> tuple[AuditEvent, ...]:
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
        return self.list_page(offset=0, limit=limit)

    def count(self) -> int:
        return int(self._session.scalar(select(func.count()).select_from(audit_events_table)) or 0)
