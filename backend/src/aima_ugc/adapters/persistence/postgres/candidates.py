"""Collection Candidate/Ingestion PostgreSQL 追加仓储。"""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.candidates import (
    CandidateIngestionRecord,
    CandidateKind,
    CandidateRecord,
    IngestionStatus,
)


class PostgresCandidateRepository:
    """Collection Candidate/Ingestion 表唯一写入口；事务由调用方持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create_candidate(
        self,
        *,
        provider_request_attempt_id: UUID,
        item_kind: CandidateKind,
        external_item_id: str | None,
        item_locator: str,
        discovered_at,
    ) -> CandidateRecord:
        candidate_id = uuid4()
        created = self._session.execute(
            pg_insert(collection_candidates_table)
            .values(
                id=candidate_id,
                provider_request_attempt_id=provider_request_attempt_id,
                item_kind=item_kind,
                external_item_id=external_item_id,
                item_locator=item_locator,
                discovered_at=discovered_at,
                created_at=func.clock_timestamp(),
            )
            .on_conflict_do_nothing(
                index_elements=[
                    collection_candidates_table.c.provider_request_attempt_id,
                    collection_candidates_table.c.item_locator,
                ]
            )
            .returning(*collection_candidates_table.c)
        ).mappings().one_or_none()
        if created is not None:
            return _candidate_from_row(created)
        row = self._session.execute(
            select(collection_candidates_table).where(
                collection_candidates_table.c.provider_request_attempt_id
                == provider_request_attempt_id,
                collection_candidates_table.c.item_locator == item_locator,
            )
        ).mappings().one()
        if row["item_kind"] != item_kind or row["external_item_id"] != external_item_id:
            raise ValueError("同一 Attempt/item_locator 的 Candidate 身份发生冲突")
        return _candidate_from_row(row)

    def append_ingestion(
        self,
        *,
        candidate_id: UUID,
        canonical_version: str | None,
        canonical_identity: str | None,
        observed_fields: tuple[str, ...],
        target_type: CandidateKind | None,
        target_id: UUID | None,
        result: IngestionStatus,
        error_code: str | None,
        error_detail: str | None,
    ) -> CandidateIngestionRecord:
        self._session.execute(
            select(collection_candidates_table.c.id)
            .where(collection_candidates_table.c.id == candidate_id)
            .with_for_update()
        ).scalar_one()
        current_no = self._session.execute(
            select(func.coalesce(func.max(collection_candidate_ingestions_table.c.ingestion_no), 0))
            .where(collection_candidate_ingestions_table.c.candidate_id == candidate_id)
        ).scalar_one()
        values = {
            "id": uuid4(),
            "candidate_id": candidate_id,
            "ingestion_no": int(current_no) + 1,
            "canonical_version": canonical_version,
            "canonical_identity": canonical_identity,
            "observed_fields": list(observed_fields),
            "target_type": target_type,
            "content_id": target_id if target_type == "content" else None,
            "comment_id": target_id if target_type == "comment" else None,
            "result": result,
            "error_code": error_code,
            "error_detail": error_detail,
            "processed_at": func.clock_timestamp(),
        }
        row = self._session.execute(
            pg_insert(collection_candidate_ingestions_table)
            .values(**values)
            .returning(*collection_candidate_ingestions_table.c)
        ).mappings().one()
        return _ingestion_from_row(row)


def _candidate_from_row(row: RowMapping) -> CandidateRecord:
    return CandidateRecord(
        id=cast(UUID, row["id"]),
        provider_request_attempt_id=cast(UUID, row["provider_request_attempt_id"]),
        item_kind=cast(CandidateKind, row["item_kind"]),
        external_item_id=cast(str | None, row["external_item_id"]),
        item_locator=cast(str, row["item_locator"]),
        discovered_at=row["discovered_at"],
        created_at=row["created_at"],
    )


def _ingestion_from_row(row: RowMapping) -> CandidateIngestionRecord:
    return CandidateIngestionRecord(
        id=cast(UUID, row["id"]),
        candidate_id=cast(UUID, row["candidate_id"]),
        ingestion_no=cast(int, row["ingestion_no"]),
        canonical_version=cast(str | None, row["canonical_version"]),
        canonical_identity=cast(str | None, row["canonical_identity"]),
        observed_fields=tuple(cast(list[str], row["observed_fields"])),
        target_type=cast(CandidateKind | None, row["target_type"]),
        content_id=cast(UUID | None, row["content_id"]),
        comment_id=cast(UUID | None, row["comment_id"]),
        result=cast(IngestionStatus, row["result"]),
        error_code=cast(str | None, row["error_code"]),
        error_detail=cast(str | None, row["error_detail"]),
        processed_at=row["processed_at"],
    )
