"""工作台公共 HTTP Contract。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from aima_ugc.contracts.base import AimaHttpModel as BaseModel
from aima_ugc.contracts.platform import PlatformName


class WorkbenchQuery(BaseModel):
    """工作台模块共用筛选；同维度 OR、跨维度 AND。"""

    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None
    platforms: tuple[PlatformName, ...] = Field(default=(), max_length=5)
    brand_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    vehicle_model_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    voice_types: tuple[str, ...] = Field(default=(), max_length=50)
    sentiments: tuple[str, ...] = Field(default=(), max_length=50)
    primary_labels: tuple[str, ...] = Field(default=(), max_length=100)
    secondary_labels: tuple[str, ...] = Field(default=(), max_length=200)

    @model_validator(mode="after")
    def validate_query(self) -> WorkbenchQuery:
        if self.date_from is not None and self.date_to is not None and self.date_from > self.date_to:
            raise ValueError("date_from 不能晚于 date_to")
        for field_name in (
            "platforms",
            "brand_ids",
            "vehicle_model_ids",
            "voice_types",
            "sentiments",
            "primary_labels",
            "secondary_labels",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} 不能重复")
        return self


class WorkbenchAnalysisIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_scheme_version_id: UUID
    taxonomy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    as_of: datetime


class WorkbenchLabelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_label: str
    secondary_label: str


class WorkbenchStreamItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_id: UUID
    platform: PlatformName
    author_display_name: str | None = None
    published_at: datetime | None = None
    title: str | None = None
    text: str | None = None
    sentiment: str | None = None
    voice_type: str | None = None
    labels: tuple[WorkbenchLabelResponse, ...] = ()
    analysis_current: bool
    vehicle_names: tuple[str, ...] = ()


class WorkbenchStreamResponse(WorkbenchAnalysisIdentityResponse):
    items: tuple[WorkbenchStreamItemResponse, ...]


class WorkbenchDailyPointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: date
    count: int = Field(ge=0)


class WorkbenchSentimentStatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentiment: str
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class WorkbenchTrendResponse(WorkbenchAnalysisIdentityResponse):
    date_from: date
    date_to: date
    previous_date_from: date
    previous_date_to: date
    total_count: int = Field(ge=0)
    daily_average: float = Field(ge=0)
    peak_day: date | None = None
    peak_count: int = Field(ge=0)
    period_change_rate: float | None = None
    positive_rate: float | None = Field(default=None, ge=0, le=1)
    positive_rate_change_pp: float | None = None
    analyzed_count: int = Field(ge=0)
    analysis_coverage_rate: float = Field(ge=0, le=1)
    daily: tuple[WorkbenchDailyPointResponse, ...]
    sentiments: tuple[WorkbenchSentimentStatResponse, ...]
    summary: str


class WorkbenchMindSecondaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secondary_label: str
    user_count: int = Field(ge=0)


class WorkbenchMindDimensionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_label: str
    user_count: int = Field(ge=0)
    user_share: float = Field(ge=0, le=1)
    positive_rate: float | None = Field(default=None, ge=0, le=1)
    user_share_change_pp: float | None = None
    secondary_labels: tuple[WorkbenchMindSecondaryResponse, ...]
    change_summary: str


class WorkbenchMindResponse(WorkbenchAnalysisIdentityResponse):
    date_from: date
    date_to: date
    previous_date_from: date
    previous_date_to: date
    identified_user_count: int = Field(ge=0)
    unidentified_content_count: int = Field(ge=0)
    analyzed_count: int = Field(ge=0)
    analysis_coverage_rate: float = Field(ge=0, le=1)
    dimensions: tuple[WorkbenchMindDimensionResponse, ...]


type WorkbenchModuleId = Literal["sound-stream", "brand-mind", "ugc-trend"]


class WorkbenchLayoutModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: WorkbenchModuleId
    visible: bool = True
    order: int = Field(ge=0, le=20)
    column_span: int = Field(ge=4, le=12)
    row_units: int = Field(ge=48, le=160)


class WorkbenchLayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    revision: int = Field(ge=0)
    modules: tuple[WorkbenchLayoutModule, ...] = Field(min_length=3, max_length=3)
    updated_at: datetime | None = None


class WorkbenchLayoutUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    modules: tuple[WorkbenchLayoutModule, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_modules(self) -> WorkbenchLayoutUpdateRequest:
        ids = tuple(item.module_id for item in self.modules)
        if len(set(ids)) != len(ids):
            raise ValueError("module_id 不能重复")
        if set(ids) != {"sound-stream", "brand-mind", "ugc-trend"}:
            raise ValueError("modules 必须完整包含三个工作台模块")
        orders = tuple(item.order for item in self.modules)
        if len(set(orders)) != len(orders):
            raise ValueError("order 不能重复")
        return self


__all__ = [
    "WorkbenchAnalysisIdentityResponse",
    "WorkbenchDailyPointResponse",
    "WorkbenchLabelResponse",
    "WorkbenchLayoutModule",
    "WorkbenchLayoutResponse",
    "WorkbenchLayoutUpdateRequest",
    "WorkbenchMindDimensionResponse",
    "WorkbenchMindResponse",
    "WorkbenchMindSecondaryResponse",
    "WorkbenchQuery",
    "WorkbenchSentimentStatResponse",
    "WorkbenchStreamItemResponse",
    "WorkbenchStreamResponse",
    "WorkbenchTrendResponse",
]
