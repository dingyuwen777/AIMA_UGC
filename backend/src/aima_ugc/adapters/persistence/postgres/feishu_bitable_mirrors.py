"""飞书独立 Base 与文档内嵌 Base 的双向镜像 Repository。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.administration.feishu_mirror_tables import (
    feishu_bitable_mirrors_table,
)


@dataclass(frozen=True, slots=True)
class FeishuBitableMirrorRecord:
    id: UUID
    publication_job_id: UUID | None
    document_token: str
    document_url: str
    external_app_token: str
    external_table_id: str
    embedded_app_token: str
    embedded_table_id: str
    status: str
    known_key_hashes: tuple[str, ...]
    last_synced_at: datetime | None
    next_sync_at: datetime
    consecutive_failures: int
    last_error_code: str | None


class PostgresFeishuBitableMirrorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def register(
        self,
        *,
        publication_job_id: UUID | None,
        document_token: str,
        document_url: str,
        external_app_token: str,
        external_table_id: str,
        embedded_app_token: str,
        embedded_table_id: str,
    ) -> FeishuBitableMirrorRecord:
        existing_row = (
            self._session.execute(
                select(feishu_bitable_mirrors_table).where(
                    feishu_bitable_mirrors_table.c.document_token == document_token
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing_row is not None:
            existing = _row_to_mirror(existing_row)
            expected = (
                external_app_token,
                external_table_id,
                embedded_app_token,
                embedded_table_id,
            )
            actual = (
                existing.external_app_token,
                existing.external_table_id,
                existing.embedded_app_token,
                existing.embedded_table_id,
            )
            if actual != expected:
                raise ValueError("同一飞书文档已注册不同的双向镜像表")
            return existing
        values: dict[str, Any] = {
            "id": uuid4(),
            "publication_job_id": publication_job_id,
            "document_token": document_token,
            "document_url": document_url,
            "external_app_token": external_app_token,
            "external_table_id": external_table_id,
            "embedded_app_token": embedded_app_token,
            "embedded_table_id": embedded_table_id,
            "status": "active",
            "known_key_hashes": [],
            "next_sync_at": func.clock_timestamp(),
            "consecutive_failures": 0,
            "created_at": func.clock_timestamp(),
            "updated_at": func.clock_timestamp(),
        }
        row = (
            self._session.execute(
                insert(feishu_bitable_mirrors_table)
                .values(**values)
                .returning(*feishu_bitable_mirrors_table.c)
            )
            .mappings()
            .one()
        )
        return _row_to_mirror(row)

    def list_due(self, *, limit: int = 20) -> tuple[FeishuBitableMirrorRecord, ...]:
        if limit < 1:
            raise ValueError("镜像扫描数量必须大于 0")
        rows = self._session.execute(
            select(feishu_bitable_mirrors_table)
            .where(
                feishu_bitable_mirrors_table.c.status == "active",
                feishu_bitable_mirrors_table.c.next_sync_at <= func.clock_timestamp(),
            )
            .order_by(feishu_bitable_mirrors_table.c.next_sync_at)
            .limit(limit)
        ).mappings()
        return tuple(_row_to_mirror(row) for row in rows)

    def mark_succeeded(
        self,
        mirror_id: UUID,
        *,
        known_key_hashes: tuple[str, ...],
        synced_at: datetime,
        next_sync_at: datetime,
    ) -> None:
        self._session.execute(
            update(feishu_bitable_mirrors_table)
            .where(feishu_bitable_mirrors_table.c.id == mirror_id)
            .values(
                known_key_hashes=list(known_key_hashes),
                last_synced_at=synced_at,
                next_sync_at=next_sync_at,
                consecutive_failures=0,
                last_error_code=None,
                updated_at=func.clock_timestamp(),
            )
        )

    def mark_failed(
        self,
        mirror_id: UUID,
        *,
        error_code: str,
        next_sync_at: datetime,
    ) -> None:
        self._session.execute(
            update(feishu_bitable_mirrors_table)
            .where(feishu_bitable_mirrors_table.c.id == mirror_id)
            .values(
                next_sync_at=next_sync_at,
                consecutive_failures=(feishu_bitable_mirrors_table.c.consecutive_failures + 1),
                last_error_code=error_code[:128],
                updated_at=func.clock_timestamp(),
            )
        )


def _row_to_mirror(row: RowMapping) -> FeishuBitableMirrorRecord:
    raw_hashes = row["known_key_hashes"]
    if not isinstance(raw_hashes, list) or any(not isinstance(item, str) for item in raw_hashes):
        raise ValueError("飞书镜像 known_key_hashes 数据损坏")
    return FeishuBitableMirrorRecord(
        id=cast(UUID, row["id"]),
        publication_job_id=cast(UUID | None, row["publication_job_id"]),
        document_token=cast(str, row["document_token"]),
        document_url=cast(str, row["document_url"]),
        external_app_token=cast(str, row["external_app_token"]),
        external_table_id=cast(str, row["external_table_id"]),
        embedded_app_token=cast(str, row["embedded_app_token"]),
        embedded_table_id=cast(str, row["embedded_table_id"]),
        status=cast(str, row["status"]),
        known_key_hashes=tuple(raw_hashes),
        last_synced_at=cast(datetime | None, row["last_synced_at"]),
        next_sync_at=cast(datetime, row["next_sync_at"]),
        consecutive_failures=cast(int, row["consecutive_failures"]),
        last_error_code=cast(str | None, row["last_error_code"]),
    )


__all__ = [
    "FeishuBitableMirrorRecord",
    "PostgresFeishuBitableMirrorRepository",
]
