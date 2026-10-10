"""Reporting 个人导出字段的乐观并发持久化。"""

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Insert, Update

from aima_ugc.modules.reporting.http import ExportColumnDefaultConflict
from aima_ugc.modules.reporting.tables import (
    reporting_user_export_column_defaults_table as defaults,
)
from aima_ugc.platform.time import beijing_now


class PostgresExportColumnDefaultRepository:
    """每 Principal 一行；恢复默认保留修订号，初次并发由主键裁决。"""

    def __init__(self, session: Session) -> None:
        """复用业务事务。"""
        self._session = session

    def get(self, principal_id: str) -> RowMapping | None:
        """仅查询当前可信身份，不做读取时修复。"""
        return (
            self._session.execute(select(defaults).where(defaults.c.principal_id == principal_id))
            .mappings()
            .first()
        )

    def save(
        self,
        principal_id: str,
        *,
        revision: int,
        columns: tuple[str, ...] | None,
        catalog_version: int,
    ) -> RowMapping:
        """用数据库原子比较修订号；冲突不覆盖另一设备的记录。"""
        now = beijing_now()
        values = dict(
            selected_columns=list(columns) if columns is not None else None,
            saved_catalog_version=catalog_version,
            updated_at=now,
        )
        statement: Insert | Update
        if revision == 0:
            statement = (
                insert(defaults)
                .values(
                    principal_id=principal_id,
                    schema_version=1,
                    revision=1,
                    created_at=now,
                    **values,
                )
                .on_conflict_do_nothing(index_elements=[defaults.c.principal_id])
            )
        else:
            statement = (
                update(defaults)
                .where(
                    defaults.c.principal_id == principal_id,
                    defaults.c.revision == revision,
                )
                .values(revision=revision + 1, **values)
            )
        row = self._session.execute(statement.returning(defaults)).mappings().first()
        if row is None:
            raise ExportColumnDefaultConflict
        return row
