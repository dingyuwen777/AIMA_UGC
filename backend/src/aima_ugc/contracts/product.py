"""U5 Count、第三方可用状态、导出列和站内通知 Contract。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from aima_ugc.contracts.base import AimaHttpModel as BaseModel

ContentAvailabilityStatus = Literal[
    "available",
    "unavailable_confirmed",
    "unavailable_suspected",
    "unknown",
]
ContentCountMode = Literal["none", "exact", "estimated"]
AnalysisManualDimension = Literal["voice_type", "sentiment", "labels"]


class AnalysisManualLabelRequest(BaseModel):
    """一个人工确认的一级/二级标签对。"""

    model_config = ConfigDict(extra="forbid")
    primary_label: str = Field(min_length=1, max_length=200)
    secondary_label: str = Field(min_length=1, max_length=200)


class ContentAnalysisManualReviewRequest(BaseModel):
    """人工纠正分析维度；已锁定维度修改前必须显式解锁。"""

    model_config = ConfigDict(extra="forbid")
    content_version: int = Field(gt=0)
    voice_type: str | None = Field(default=None, min_length=1, max_length=200)
    sentiment: str | None = Field(default=None, min_length=1, max_length=200)
    labels: tuple[AnalysisManualLabelRequest, ...] | None = Field(
        default=None, min_length=1, max_length=100
    )
    unlock_dimensions: tuple[AnalysisManualDimension, ...] = Field(default=(), max_length=3)

    @model_validator(mode="after")
    def validate_changes(self) -> ContentAnalysisManualReviewRequest:
        """要求至少一个修改或解锁动作，并拒绝重复维度或标签。"""

        if (
            self.voice_type is None
            and self.sentiment is None
            and self.labels is None
            and not self.unlock_dimensions
        ):
            raise ValueError("人工分析复核至少需要修改或解锁一个维度")
        if len(self.unlock_dimensions) != len(set(self.unlock_dimensions)):
            raise ValueError("unlock_dimensions 不能重复")
        if self.labels is not None:
            identities = tuple(
                (item.primary_label, item.secondary_label) for item in self.labels
            )
            if len(identities) != len(set(identities)):
                raise ValueError("labels 不能重复")
        return self


class ContentAnalysisManualReviewResponse(BaseModel):
    """人工纠正后的当前锁定状态。"""

    model_config = ConfigDict(extra="forbid")
    content_id: UUID
    content_version: int = Field(gt=0)
    voice_type: str | None = None
    sentiment: str | None = None
    labels: tuple[AnalysisManualLabelRequest, ...] = ()
    locked_dimensions: tuple[AnalysisManualDimension, ...]


class ContentCountQuery(BaseModel):
    """独立 Count 查询策略；不改变 Cursor 分页。"""

    model_config = ConfigDict(extra="forbid")
    count_mode: ContentCountMode = "none"
    exact_limit: int | None = Field(default=None, ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_mode(self) -> ContentCountQuery:
        """只有 exact 模式允许提交有界扫描上限。"""

        if self.count_mode != "exact" and self.exact_limit is not None:
            raise ValueError("只有 exact count_mode 可以设置 exact_limit")
        return self


class ContentCountResponse(BaseModel):
    """Count 结果带种类和时间，不伪装事务级实时总数。"""

    model_config = ConfigDict(extra="forbid")
    count_mode: ContentCountMode
    count: int | None = Field(default=None, ge=0)
    count_kind: Literal["none", "exact", "estimated"]
    as_of: datetime
    truncated: bool = False

    @model_validator(mode="after")
    def validate_result_kind(self) -> ContentCountResponse:
        """没有可靠数字时明确返回 none；截断扫描不能伪装精确总数。"""

        if self.count_kind == "none" and self.count is not None:
            raise ValueError("count_kind=none 时 count 必须为空")
        if self.count_kind != "none" and self.count is None:
            raise ValueError("exact/estimated 结果必须包含 count")
        if self.truncated and (self.count_kind != "none" or self.count is not None):
            raise ValueError("截断结果不能声明精确或估算总数")
        return self


class ContentAvailabilityObservationRequest(BaseModel):
    """追加一条 Provider-neutral 可用状态观察。"""

    model_config = ConfigDict(extra="forbid")
    content_id: UUID
    status: ContentAvailabilityStatus
    reason_code: str = Field(min_length=1, max_length=100)
    evidence_kind: Literal["provider_explicit", "technical_failure", "manual_review"]
    provider_attempt_id: UUID | None = None
    raw_artifact_id: UUID | None = None
    safe_summary: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_evidence(self) -> ContentAvailabilityObservationRequest:
        """确认下架只接受 Provider 明确信号，技术失败只表达未知或疑似。"""

        if self.status == "unavailable_confirmed" and self.evidence_kind != "provider_explicit":
            raise ValueError("unavailable_confirmed 必须来自 Provider 明确证据")
        if (
            self.evidence_kind == "provider_explicit"
            and self.provider_attempt_id is None
            and self.raw_artifact_id is None
        ):
            raise ValueError("Provider 明确证据必须关联 Attempt 或 Raw Artifact")
        if self.evidence_kind == "technical_failure" and self.status not in {
            "unknown",
            "unavailable_suspected",
        }:
            raise ValueError("技术失败只能标记 unknown 或 unavailable_suspected")
        return self


class ContentAvailabilityResponse(BaseModel):
    """内容当前可用状态及最新证据投影。"""

    model_config = ConfigDict(extra="forbid")
    status: ContentAvailabilityStatus
    reason_code: str
    evidence_kind: str
    observed_at: datetime


class ContentVehicleReviewRequest(BaseModel):
    """人工确认内容车型；默认不允许覆盖已有人工锁定。"""

    model_config = ConfigDict(extra="forbid")
    content_version: int = Field(gt=0)
    vehicle_model_ids: tuple[UUID, ...] = Field(max_length=100)
    unlock_existing: bool = False

    @field_validator("vehicle_model_ids")
    @classmethod
    def validate_vehicle_model_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        """人工车型集合使用稳定且不重复的 ID。"""

        if len(value) != len(set(value)):
            raise ValueError("vehicle_model_ids 不能重复")
        return value


class ContentVehicleReviewResponse(BaseModel):
    """人工车型确认写入结果。"""

    model_config = ConfigDict(extra="forbid")
    content_id: UUID
    content_version: int = Field(gt=0)
    vehicle_model_ids: tuple[UUID, ...]
    manual_locked: bool = True


class ExportColumnResponse(BaseModel):
    """后端白名单中的一个安全导出列。"""

    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    sensitive: bool = False
    default_selected: bool = False


class ExportColumnCatalogResponse(BaseModel):
    """版本化导出列目录。"""

    model_config = ConfigDict(extra="forbid")
    version: int = Field(gt=0)
    columns: tuple[ExportColumnResponse, ...] = Field(min_length=1)


class NotificationItemResponse(BaseModel):
    """Principal Inbox 中的一个通知投影。"""

    model_config = ConfigDict(extra="forbid")
    id: UUID
    event_type: str
    title: str
    message: str
    resource_type: str | None = None
    resource_id: str | None = None
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None


class NotificationListResponse(BaseModel):
    """当前 Principal 的站内通知列表。"""

    model_config = ConfigDict(extra="forbid")
    items: tuple[NotificationItemResponse, ...]
    unread_count: int = Field(ge=0)


class NotificationMarkReadRequest(BaseModel):
    """批量标记当前 Principal 自己的通知已读。"""

    model_config = ConfigDict(extra="forbid")
    item_ids: tuple[UUID, ...] = Field(min_length=1, max_length=100)

    @field_validator("item_ids")
    @classmethod
    def validate_unique_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        """同一请求不得重复提交通知 ID。"""

        if len(value) != len(set(value)):
            raise ValueError("item_ids 不能重复")
        return value


class NotificationMarkReadResponse(BaseModel):
    """已读操作的幂等统计。"""

    model_config = ConfigDict(extra="forbid")
    requested_count: int = Field(ge=0)
    changed_count: int = Field(ge=0)


__all__ = [
    "AnalysisManualDimension",
    "AnalysisManualLabelRequest",
    "ContentAnalysisManualReviewRequest",
    "ContentAnalysisManualReviewResponse",
    "ContentAvailabilityObservationRequest",
    "ContentAvailabilityResponse",
    "ContentAvailabilityStatus",
    "ContentCountQuery",
    "ContentCountResponse",
    "ContentVehicleReviewRequest",
    "ContentVehicleReviewResponse",
    "ExportColumnCatalogResponse",
    "ExportColumnResponse",
    "NotificationItemResponse",
    "NotificationListResponse",
    "NotificationMarkReadRequest",
    "NotificationMarkReadResponse",
]
