"""Analysis 成功结果的持久化领域模型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aima_ugc.contracts.analysis import ContentLabelAnalysisV2
from aima_ugc.contracts.canonical import CanonicalContentV1


@dataclass(frozen=True, slots=True)
class AnalysisConfigurationIdentity:
    """确定 current Analysis 的当前 Prompt/Taxonomy/Provider/Model 身份。"""

    prompt_version: str
    prompt_sha256: str
    taxonomy_sha256: str
    model_provider: str
    model: str


@dataclass(frozen=True, slots=True)
class AnalysisLabelPair:
    ordinal: int
    primary_label: str
    secondary_label: str


@dataclass(frozen=True, slots=True)
class AnalysisContentResult:
    id: UUID
    content_id: UUID
    content_version: int
    job_id: UUID
    schema_version: str
    sentiment: str
    prompt_version: str
    prompt_sha256: str
    taxonomy_sha256: str
    model_provider: str
    model: str
    input_hash: str
    analyzed_at: datetime
    labels: tuple[AnalysisLabelPair, ...]

    @classmethod
    def from_analysis(
        cls,
        *,
        result_id: UUID,
        content_id: UUID,
        content_version: int,
        job_id: UUID,
        analysis: ContentLabelAnalysisV2,
    ) -> AnalysisContentResult:
        if content_version < 1:
            raise ValueError("content_version 必须大于等于 1")
        return cls(
            id=result_id,
            content_id=content_id,
            content_version=content_version,
            job_id=job_id,
            schema_version=analysis.schema_version,
            sentiment=analysis.sentiment,
            prompt_version=analysis.prompt_version,
            prompt_sha256=analysis.prompt_sha256,
            taxonomy_sha256=analysis.taxonomy_sha256,
            model_provider=analysis.model_provider,
            model=analysis.model,
            input_hash=analysis.input_hash,
            analyzed_at=analysis.analyzed_at,
            labels=tuple(
                AnalysisLabelPair(
                    ordinal=ordinal,
                    primary_label=pair.primary_label,
                    secondary_label=pair.secondary_label,
                )
                for ordinal, pair in enumerate(analysis.labels)
            ),
        )


@dataclass(frozen=True, slots=True)
class AnalysisWorkItem:
    request_id: UUID
    ordinal: int
    content_id: UUID
    content_version: int
    content: CanonicalContentV1


__all__ = [
    "AnalysisConfigurationIdentity",
    "AnalysisContentResult",
    "AnalysisLabelPair",
    "AnalysisWorkItem",
]
