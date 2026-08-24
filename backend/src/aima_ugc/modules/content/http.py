"""Stage 8D 声音广场 HTTP Application Service 边界。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.http import (
    ContentAnalysisCreatedResponse,
    ContentAnalysisSubmitRequest,
    ContentDetailResponse,
    ContentListQuery,
    ContentListResponse,
    JobStatusResponse,
)
from aima_ugc.contracts.relevance_review import (
    ContentRelevanceReviewRequest,
    ContentRelevanceReviewResponse,
)

from .content_cursor import InvalidContentCursor


class ContentResourceNotFound(LookupError):
    pass


class ContentSelectionEmpty(ValueError):
    pass


class ContentCursorUnavailable(RuntimeError):
    pass


class ContentHttpService(Protocol):
    def list_contents(self, query: ContentListQuery) -> ContentListResponse: ...

    def get_content(self, content_id: UUID) -> ContentDetailResponse: ...

    def create_analysis(
        self,
        request: ContentAnalysisSubmitRequest,
        *,
        request_id: str,
    ) -> ContentAnalysisCreatedResponse: ...

    def review_relevance(
        self,
        request: ContentRelevanceReviewRequest,
        *,
        request_id: str,
    ) -> ContentRelevanceReviewResponse: ...

    def get_analysis_job(self, job_id: UUID) -> JobStatusResponse: ...


__all__ = [
    "ContentCursorUnavailable",
    "ContentHttpService",
    "ContentResourceNotFound",
    "ContentSelectionEmpty",
    "InvalidContentCursor",
]
