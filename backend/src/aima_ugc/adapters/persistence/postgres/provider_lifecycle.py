"""Provider Config 归档、恢复与条件删除的 System Owner Repository。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from aima_ugc.modules.analysis.tables import analysis_content_runs_table
from aima_ugc.modules.collection.tables import (
    collection_plan_platforms_table,
    collection_plans_table,
    provider_requests_table,
)
from aima_ugc.modules.system.lifecycle_schema import register_system_lifecycle_schema
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.modules.system.tables import provider_configs_table

register_system_lifecycle_schema()


@dataclass(frozen=True, slots=True)
class ArchivedProviderConfigRecord:
    """已归档 Provider 的最小业务投影。"""

    id: UUID
    display_name: str
    archived_at: datetime


class PostgresProviderConfigLifecycleRepository:
    """Provider 生命周期写入 System Owner 表；跨 Owner 表仅用于引用守卫。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_update(self, provider_config_id: UUID) -> ProviderConfig | None:
        """锁定 Provider Config 并返回现有领域对象。"""

        row = (
            self._session.execute(
                select(provider_configs_table)
                .where(provider_configs_table.c.id == provider_config_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _provider(row)

    def archive_blockers(self, provider_config_id: UUID) -> tuple[str, ...]:
        """默认 Provider 或未归档计划当前引用时不能归档。"""

        row = self._session.execute(
            select(
                provider_configs_table.c.is_default,
                provider_configs_table.c.archived_at,
            ).where(provider_configs_table.c.id == provider_config_id)
        ).mappings().one_or_none()
        if row is None:
            return ("资源不存在",)
        blockers: list[str] = []
        if row["archived_at"] is not None:
            blockers.append("Provider 已归档")
        if row["is_default"]:
            blockers.append("默认 AI Provider 不能直接归档，请先切换默认配置")
        if self._session.scalar(
            select(collection_plan_platforms_table.c.plan_id)
            .join(
                collection_plans_table,
                collection_plans_table.c.id == collection_plan_platforms_table.c.plan_id,
            )
            .where(
                collection_plan_platforms_table.c.provider_config_id == provider_config_id,
                collection_plans_table.c.archived_at.is_(None),
            )
            .limit(1)
        ) is not None:
            blockers.append("未归档的采集计划仍在引用该 Provider")
        return tuple(blockers)

    def archive(self, provider_config_id: UUID, *, archived_at: datetime) -> ProviderConfig | None:
        """归档 Provider 并强制停用、取消默认标记。"""

        row = (
            self._session.execute(
                update(provider_configs_table)
                .where(
                    provider_configs_table.c.id == provider_config_id,
                    provider_configs_table.c.archived_at.is_(None),
                )
                .values(
                    enabled=False,
                    is_default=False,
                    archived_at=archived_at,
                    revision=provider_configs_table.c.revision + 1,
                    updated_at=func.clock_timestamp(),
                )
                .returning(provider_configs_table)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _provider(row)

    def restore(self, provider_config_id: UUID) -> ProviderConfig | None:
        """恢复归档 Provider；保持停用、非默认，必须显式重新配置运行状态。"""

        row = (
            self._session.execute(
                update(provider_configs_table)
                .where(
                    provider_configs_table.c.id == provider_config_id,
                    provider_configs_table.c.archived_at.is_not(None),
                )
                .values(
                    archived_at=None,
                    enabled=False,
                    is_default=False,
                    revision=provider_configs_table.c.revision + 1,
                    updated_at=func.clock_timestamp(),
                )
                .returning(provider_configs_table)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _provider(row)

    def list_archived(self) -> tuple[ArchivedProviderConfigRecord, ...]:
        """按最近归档顺序返回 Provider。"""

        rows = self._session.execute(
            select(
                provider_configs_table.c.id,
                provider_configs_table.c.display_name,
                provider_configs_table.c.archived_at,
            )
            .where(provider_configs_table.c.archived_at.is_not(None))
            .order_by(provider_configs_table.c.archived_at.desc(), provider_configs_table.c.id)
        ).mappings()
        return tuple(
            ArchivedProviderConfigRecord(
                id=cast(UUID, row["id"]),
                display_name=cast(str, row["display_name"]),
                archived_at=cast(datetime, row["archived_at"]),
            )
            for row in rows
        )

    def delete_blockers(self, provider_config_id: UUID) -> tuple[str, ...]:
        """Provider 一旦进入 Plan、Provider Request 或 AI Run 历史就永久保留配置事实。"""

        row = self._session.execute(
            select(provider_configs_table.c.id, provider_configs_table.c.archived_at).where(
                provider_configs_table.c.id == provider_config_id
            )
        ).mappings().one_or_none()
        if row is None:
            return ("资源不存在",)
        blockers: list[str] = []
        if row["archived_at"] is None:
            blockers.append("请先归档 Provider 再执行永久删除")
        if self._session.scalar(
            select(collection_plan_platforms_table.c.plan_id)
            .where(collection_plan_platforms_table.c.provider_config_id == provider_config_id)
            .limit(1)
        ) is not None:
            blockers.append("采集计划历史引用了该 Provider")
        if self._session.scalar(
            select(provider_requests_table.c.id)
            .where(provider_requests_table.c.provider_config_id == provider_config_id)
            .limit(1)
        ) is not None:
            blockers.append("Provider 请求历史引用了该配置")
        if self._session.scalar(
            select(analysis_content_runs_table.c.id)
            .where(
                analysis_content_runs_table.c.runtime_config_snapshot.contains(
                    {"provider_config_id": str(provider_config_id)}
                )
            )
            .limit(1)
        ) is not None:
            blockers.append("AI 分析运行历史引用了该 Provider")
        return tuple(dict.fromkeys(blockers))

    def delete_archived(self, provider_config_id: UUID) -> bool:
        """永久删除从未进入业务历史的归档 Provider Config。"""

        blockers = self.delete_blockers(provider_config_id)
        if blockers:
            raise RuntimeError("；".join(blockers))
        deleted = self._session.execute(
            delete(provider_configs_table)
            .where(
                provider_configs_table.c.id == provider_config_id,
                provider_configs_table.c.archived_at.is_not(None),
            )
            .returning(provider_configs_table.c.id)
        ).scalar_one_or_none()
        return deleted == provider_config_id


def _provider(row) -> ProviderConfig:
    """把 Provider 配置行映射为现有领域对象，不暴露 Secret 值。"""

    return ProviderConfig(
        id=cast(UUID, row["id"]),
        provider=cast(str, row["provider"]),
        provider_kind=cast(str, row["provider_kind"]),
        display_name=cast(str, row["display_name"]),
        base_url=cast(str, row["base_url"]),
        model=cast(str | None, row["model"]),
        secret_ref=cast(str, row["secret_ref"]),
        timeout_seconds=cast(int, row["timeout_seconds"]),
        max_retries=cast(int, row["max_retries"]),
        max_concurrency=cast(int, row["max_concurrency"]),
        max_rps=cast(int | None, row["max_rps"]),
        extra_config=cast(dict, row["extra_config"]),
        enabled=cast(bool, row["enabled"]),
        is_default=cast(bool, row["is_default"]),
        revision=cast(int, row["revision"]),
    )


__all__ = ["ArchivedProviderConfigRecord", "PostgresProviderConfigLifecycleRepository"]
