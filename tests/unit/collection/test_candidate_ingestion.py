"""Collection Candidate Ingestion 领域约束测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
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


def test_filtered_candidate_preserves_canonical_identity_without_content_target() -> None:
    repository = _CandidateRepository()
    service = CandidateIngestionService(repository)
    observed_at = datetime(2026, 8, 20, tzinfo=UTC)
    canonical = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="content-1",
        content_type="note",
        observed_at=observed_at,
        source=CanonicalSourceV1(
            provider_name="tikhub",
            operation="search",
            observed_at=observed_at,
        ),
        observed_fields=["content_type"],
    )

    service.record_ingestion(
        candidate_id=uuid4(),
        canonical=canonical,
        target_id=None,
        result="filtered",
    )

    assert repository.append_calls[0]["canonical_identity"] == "xiaohongshu:content-1"
    assert repository.append_calls[0]["target_type"] is None
    assert repository.append_calls[0]["target_id"] is None
