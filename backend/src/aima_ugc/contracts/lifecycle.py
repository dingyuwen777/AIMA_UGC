"""业务资源生命周期的公共 HTTP Contract。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from aima_ugc.contracts.base import AimaHttpModel as BaseModel

DataImportRevocationIneligibleReason = Literal[
    "campaign_not_completed",
    "reversible_evidence_missing",
]


class DataImportRevocationImpactResponse(BaseModel):
    """撤销一次数据导入对当前业务可见内容的影响。"""

    model_config = ConfigDict(extra="forbid")

    affected_content_count: int = Field(ge=0)
    hidden_content_count: int = Field(ge=0)
    retained_shared_content_count: int = Field(ge=0)
    unreversible_content_count: int = Field(default=0, ge=0)


class DataImportRevocationPreviewResponse(BaseModel):
    """执行撤销前的只读影响预览。"""

    model_config = ConfigDict(extra="forbid")

    campaign_id: UUID
    eligible: bool
    already_revoked: bool
    ineligible_reason: DataImportRevocationIneligibleReason | None = None
    impact: DataImportRevocationImpactResponse


class DataImportRevokeRequest(BaseModel):
    """执行撤销时允许记录一段非敏感原因。"""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        """空白原因按未填写处理，避免持久化无意义空字符串。"""

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class DataImportRevocationResponse(BaseModel):
    """已经提交的不可变撤销事实。"""

    model_config = ConfigDict(extra="forbid")

    campaign_id: UUID
    already_revoked: bool
    impact: DataImportRevocationImpactResponse
    revoked_at: datetime


__all__ = [
    "DataImportRevokeRequest",
    "DataImportRevocationImpactResponse",
    "DataImportRevocationIneligibleReason",
    "DataImportRevocationPreviewResponse",
    "DataImportRevocationResponse",
]
