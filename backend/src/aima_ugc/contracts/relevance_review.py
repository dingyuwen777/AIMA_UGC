"""人工相关性复核公共 HTTP Contract。"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ContentRelevanceReviewDecision = Literal["relevant", "irrelevant", "inherit_ai"]


class ContentRelevanceReviewRequest(BaseModel):
    """单条和批量复用同一请求，显式声明人工覆盖或撤销决定。"""

    model_config = ConfigDict(extra="forbid")

    content_ids: tuple[UUID, ...] = Field(min_length=1, max_length=1000)
    decision: ContentRelevanceReviewDecision

    @field_validator("content_ids")
    @classmethod
    def content_ids_must_be_unique(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(value) != len(set(value)):
            raise ValueError("人工相关性复核的 Content ID 不得重复")
        return value


class ContentRelevanceReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_count: int = Field(ge=1)
    changed_count: int = Field(ge=0)
    unchanged_count: int = Field(ge=0)


__all__ = [
    "ContentRelevanceReviewDecision",
    "ContentRelevanceReviewRequest",
    "ContentRelevanceReviewResponse",
]
