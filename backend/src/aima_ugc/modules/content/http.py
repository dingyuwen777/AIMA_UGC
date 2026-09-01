"""Stage 8D 声音广场 HTTP Application Service 边界。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.http import (
    AnalysisContentRunCreatedResponse,
    AnalysisContentRunCreateRequest,
    AnalysisContentRunListResponse,
    AnalysisContentRunPreviewRequest,
    AnalysisContentRunPreviewResponse,
    AnalysisContentRunResponse,
    ContentAnalysisCreatedResponse,
    ContentAnalysisSubmitRequest,
    ContentAnalysisTaxonomyResponse,
    ContentDetailResponse,
    ContentListQuery,
    ContentListResponse,
    JobStatusResponse,
)
from aima_ugc.contracts.product import (
    ContentAnalysisManualReviewRequest,
    ContentAnalysisManualReviewResponse,
    ContentVehicleReviewRequest,
    ContentVehicleReviewResponse,
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


class ContentAnalysisUnavailable(RuntimeError):
    pass


class ContentAnalysisTargetChanged(RuntimeError):
    pass


class ContentAnalysisRunConflict(RuntimeError):
    pass


class ContentHttpService(Protocol):
    def list_contents(self, query: ContentListQuery) -> ContentListResponse: ...

    def get_content(self, content_id: UUID) -> ContentDetailResponse: ...

    def review_vehicles(
        self,
        content_id: UUID,
        request: ContentVehicleReviewRequest,
        *,
        request_id: str,
        actor_ref: str,
    ) -> ContentVehicleReviewResponse:
        """人工确认当前内容版本的 0..N 个车型。"""

        ...

    def review_analysis(
        self,
        content_id: UUID,
        request: ContentAnalysisManualReviewRequest,
        *,
        request_id: str,
        actor_ref: str,
    ) -> ContentAnalysisManualReviewResponse:
        """人工纠正或解锁当前内容版本的分析维度。"""

        ...

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

    def preview_analysis_run(
        self,
        request: AnalysisContentRunPreviewRequest,
    ) -> AnalysisContentRunPreviewResponse: ...

    def create_analysis_run(
        self,
        request: AnalysisContentRunCreateRequest,
        *,
        request_id: str,
    ) -> AnalysisContentRunCreatedResponse: ...

    def list_analysis_runs(self) -> AnalysisContentRunListResponse: ...

    def get_analysis_run(self, run_id: UUID) -> AnalysisContentRunResponse: ...

    def cancel_analysis_run(
        self,
        run_id: UUID,
        *,
        request_id: str,
    ) -> AnalysisContentRunResponse: ...

    def get_analysis_taxonomy(self) -> ContentAnalysisTaxonomyResponse:
        """读取 active Scheme 的安全 Taxonomy 投影。"""

        ...


__all__ = [
    "ContentCursorUnavailable",
    "ContentAnalysisRunConflict",
    "ContentAnalysisTargetChanged",
    "ContentAnalysisUnavailable",
    "ContentHttpService",
    "ContentResourceNotFound",
    "ContentSelectionEmpty",
    "InvalidContentCursor",
]
