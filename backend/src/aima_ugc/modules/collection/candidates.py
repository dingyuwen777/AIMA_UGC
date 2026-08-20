"""Collection Candidate 与 Ingestion 追加账本领域入口。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1

CandidateKind = Literal["content", "comment"]
IngestionStatus = Literal[
    "ingested",
    "duplicate",
    "filtered",
    "invalid",
    "unsupported",
    "failed",
]


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    id: UUID
    provider_request_attempt_id: UUID
    item_kind: CandidateKind
    external_item_id: str | None
    item_locator: str
    discovered_at: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CandidateIngestionRecord:
    id: UUID
    candidate_id: UUID
    ingestion_no: int
    canonical_version: str | None
    canonical_identity: str | None
    observed_fields: tuple[str, ...]
    target_type: CandidateKind | None
    content_id: UUID | None
    comment_id: UUID | None
    result: IngestionStatus
    error_code: str | None
    error_detail: str | None
    processed_at: datetime


class CandidateRepository(Protocol):
    def get_or_create_candidate(
        self,
        *,
        provider_request_attempt_id: UUID,
        item_kind: CandidateKind,
        external_item_id: str | None,
        item_locator: str,
        discovered_at: datetime,
    ) -> CandidateRecord: ...

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
    ) -> CandidateIngestionRecord: ...


class CandidateIngestionService:
    """Candidate 账本唯一业务入口；不读取 Raw、不执行 Mapper、不写 Content 表。"""

    def __init__(self, repository: CandidateRepository) -> None:
        self._repository = repository

    def discover(
        self,
        *,
        provider_request_attempt_id: UUID,
        item_kind: CandidateKind,
        external_item_id: str | None,
        item_locator: str,
        discovered_at: datetime,
    ) -> CandidateRecord:
        if not item_locator.strip():
            raise ValueError("Candidate item_locator 不能为空")
        return self._repository.get_or_create_candidate(
            provider_request_attempt_id=provider_request_attempt_id,
            item_kind=item_kind,
            external_item_id=external_item_id,
            item_locator=item_locator,
            discovered_at=discovered_at,
        )

    def record_ingestion(
        self,
        *,
        candidate_id: UUID,
        canonical: CanonicalContentV1 | CanonicalCommentV1 | None,
        target_id: UUID | None,
        result: IngestionStatus,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> CandidateIngestionRecord:
        if result in {"ingested", "duplicate"} and (canonical is None or target_id is None):
            raise ValueError("成功的 Candidate Ingestion 必须提供 Canonical 和目标 ID")
        if canonical is None:
            return self._repository.append_ingestion(
                candidate_id=candidate_id,
                canonical_version=None,
                canonical_identity=None,
                observed_fields=(),
                target_type=None,
                target_id=None,
                result=result,
                error_code=error_code,
                error_detail=error_detail,
            )
        if isinstance(canonical, CanonicalContentV1):
            target_type: CandidateKind | None = "content"
            identity = f"{canonical.platform}:{canonical.external_content_id}"
        else:
            target_type = "comment"
            identity = (
                f"{canonical.platform}:{canonical.external_content_id}:"
                f"{canonical.external_comment_id}"
            )
        if result == "filtered":
            target_type = None
        if target_id is None and result != "filtered":
            raise ValueError("成功映射的 Candidate Ingestion 必须提供目标 ID")
        return self._repository.append_ingestion(
            candidate_id=candidate_id,
            canonical_version=canonical.schema_version,
            canonical_identity=identity,
            observed_fields=tuple(canonical.observed_fields),
            target_type=target_type,
            target_id=target_id,
            result=result,
            error_code=error_code,
            error_detail=error_detail,
        )
