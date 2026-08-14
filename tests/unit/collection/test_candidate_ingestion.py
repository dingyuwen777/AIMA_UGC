"""Collection Candidate Ingestion 领域约束测试。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from aima_ugc.modules.collection.candidates import (
    CandidateIngestionRecord,
    CandidateIngestionService,
    CandidateKind,
    CandidateRecord,
    IngestionStatus,
)


class _CandidateRepository:
    def __init__(self) -> None:
        self.append_calls: list[dict[str, object]] = []

    def get_or_create_candidate(
        self,
        *,
        provider_request_attempt_id: UUID,
        item_kind: CandidateKind,
        external_item_id: str | None,
        item_locator: str,
        discovered_at: datetime,
    ) -> CandidateRecord:
        raise AssertionError("本测试不应创建 Candidate")

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
        self.append_calls.append(
            {
                "candidate_id": candidate_id,
                "canonical_version": canonical_version,
                "canonical_identity": canonical_identity,
                "observed_fields": observed_fields,
                "target_type": target_type,
                "target_id": target_id,
                "result": result,
                "error_code": error_code,
                "error_detail": error_detail,
            }
        )
        return cast(CandidateIngestionRecord, object())


@pytest.mark.parametrize("result", ["ingested", "duplicate"])
def test_successful_ingestion_requires_canonical_and_target(
    result: IngestionStatus,
) -> None:
    repository = _CandidateRepository()
    service = CandidateIngestionService(repository)

    with pytest.raises(ValueError, match="成功的 Candidate Ingestion"):
        service.record_ingestion(
            candidate_id=uuid4(),
            canonical=None,
            target_id=None,
            result=result,
        )

    assert repository.append_calls == []
