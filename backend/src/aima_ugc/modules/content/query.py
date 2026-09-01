"""声音广场的 Provider-neutral 只读查询模型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aima_ugc.contracts.http import ContentFilterSnapshot
from aima_ugc.contracts.platform import PlatformName

from .content_cursor import ContentCursorPosition


@dataclass(frozen=True, slots=True)
class ContentTarget:
    content_id: UUID
    content_version: int


@dataclass(frozen=True, slots=True)
class ContentReadQuery:
    filters: ContentFilterSnapshot
    position: ContentCursorPosition | None
    limit: int


@dataclass(frozen=True, slots=True)
class ContentAnalysisRead:
    result_id: UUID | None
    status: str
    relevance: str | None
    voice_type: str | None
    sentiment: str | None
    labels: tuple[tuple[str, str], ...]
    analyzed_at: datetime | None
    model_provider: str | None
    model: str | None
    latest_run_id: UUID | None
    latest_run_status: str | None
    manual_locked_dimensions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContentSourceRead:
    provider_name: str
    provider_attempt_id: UUID | None
    raw_artifact_id: UUID | None
    import_batch_id: UUID | None
    collection_run_id: UUID | None


@dataclass(frozen=True, slots=True)
class ContentVehicleEvidenceRead:
    source: str
    matched_text: str | None
    source_field: str | None
    catalog_version: int
    confidence: float | None
    is_manual_locked: bool


@dataclass(frozen=True, slots=True)
class ContentVehicleRead:
    vehicle_model_id: UUID
    code: str
    display_name: str
    evidences: tuple[ContentVehicleEvidenceRead, ...]


@dataclass(frozen=True, slots=True)
class ContentAvailabilityRead:
    status: str
    reason_code: str
    evidence_kind: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ContentReadRecord:
    id: UUID
    current_version: int
    sort_at: datetime
    platform: PlatformName
    external_content_id: str
    content_type: str
    title: str | None
    text: str | None
    author_display_name: str | None
    published_at: datetime | None
    last_seen_at: datetime
    canonical_url: str | None
    share_url: str | None
    metrics: dict[str, int | None]
    analysis: ContentAnalysisRead
    effective_relevance: str | None
    relevance_source: str | None
    source: ContentSourceRead
    vehicles: tuple[ContentVehicleRead, ...] = ()
    availability: ContentAvailabilityRead | None = None


__all__ = [
    "ContentAnalysisRead",
    "ContentAvailabilityRead",
    "ContentReadQuery",
    "ContentReadRecord",
    "ContentSourceRead",
    "ContentVehicleEvidenceRead",
    "ContentVehicleRead",
    "ContentTarget",
]
