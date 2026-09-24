"""飞书独立 Base 与文档内嵌 Base 的双向镜像 Repository。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import CursorResult, RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.administration.feishu_mirror_tables import (
    feishu_bitable_mirrors_table,
)
from aima_ugc.platform.jobs.models import LeaseLostError


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
    claim_owner: str | None
    claim_token: str | None
    claim_expires_at: datetime | None


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

    def claim_due(
        self,
        *,
        worker_id: str,
        limit: int = 20,
        lease_seconds: int = 60,
    ) -> tuple[FeishuBitableMirrorRecord, ...]:
        """原子认领到期镜像，避免多个常驻实例重复同步。"""

        if not worker_id.strip():
            raise ValueError("镜像 worker_id 不能为空")
        if limit < 1:
            raise ValueError("镜像扫描数量必须大于 0")
        if lease_seconds <= 0:
            raise ValueError("镜像 lease_seconds 必须大于 0")
        claim_token = uuid4().hex
        rows = self._session.execute(
            text(
                """
                WITH mirror_clock AS MATERIALIZED (
                    SELECT clock_timestamp() AS now_at
                ), candidates AS (
                    SELECT m.id
                    FROM feishu_bitable_mirrors AS m, mirror_clock AS c
                    WHERE m.status = 'active'
                      AND m.next_sync_at <= c.now_at
                      AND (
                          m.claim_expires_at IS NULL
                          OR m.claim_expires_at <= c.now_at
                      )
                    ORDER BY m.next_sync_at, m.id
                    FOR UPDATE OF m SKIP LOCKED
                    LIMIT :limit
                )
                UPDATE feishu_bitable_mirrors AS m
                SET claim_owner = :worker_id,
                    claim_token = :claim_token,
                    claim_expires_at = c.now_at + make_interval(secs => :lease_seconds),
                    updated_at = c.now_at
                FROM candidates, mirror_clock AS c
                WHERE m.id = candidates.id
                RETURNING m.*
                """
            ),
            {
                "worker_id": worker_id,
                "claim_token": claim_token,
                "lease_seconds": lease_seconds,
                "limit": limit,
            },
        ).mappings()
        return tuple(_row_to_mirror(row) for row in rows)

    def mark_succeeded(
        self,
        mirror_id: UUID,
        *,
        known_key_hashes: tuple[str, ...],
        synced_at: datetime,
        next_sync_at: datetime,
        claim_token: str,
    ) -> None:
        result = cast(CursorResult[Any], self._session.execute(
            update(feishu_bitable_mirrors_table)
            .where(
                feishu_bitable_mirrors_table.c.id == mirror_id,
                feishu_bitable_mirrors_table.c.claim_token == claim_token,
                feishu_bitable_mirrors_table.c.claim_expires_at > func.clock_timestamp(),
            )
            .values(
                known_key_hashes=list(known_key_hashes),
                last_synced_at=synced_at,
                next_sync_at=next_sync_at,
                consecutive_failures=0,
                last_error_code=None,
                claim_owner=None,
                claim_token=None,
                claim_expires_at=None,
                updated_at=func.clock_timestamp(),
            )
        ))
        if result.rowcount != 1:
            raise LeaseLostError("飞书镜像 claim 已失效")

    def mark_failed(
        self,
        mirror_id: UUID,
        *,
        error_code: str,
        next_sync_at: datetime,
        claim_token: str,
    ) -> None:
        result = cast(CursorResult[Any], self._session.execute(
            update(feishu_bitable_mirrors_table)
            .where(
                feishu_bitable_mirrors_table.c.id == mirror_id,
                feishu_bitable_mirrors_table.c.claim_token == claim_token,
                feishu_bitable_mirrors_table.c.claim_expires_at > func.clock_timestamp(),
            )
            .values(
                next_sync_at=next_sync_at,
                consecutive_failures=(feishu_bitable_mirrors_table.c.consecutive_failures + 1),
                last_error_code=error_code[:128],
                claim_owner=None,
                claim_token=None,
                claim_expires_at=None,
                updated_at=func.clock_timestamp(),
            )
        ))
        if result.rowcount != 1:
            raise LeaseLostError("飞书镜像 claim 已失效")


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
        claim_owner=cast(str | None, row["claim_owner"]),
        claim_token=cast(str | None, row["claim_token"]),
        claim_expires_at=cast(datetime | None, row["claim_expires_at"]),
    )


__all__ = [
    "FeishuBitableMirrorRecord",
    "PostgresFeishuBitableMirrorRepository",
]
