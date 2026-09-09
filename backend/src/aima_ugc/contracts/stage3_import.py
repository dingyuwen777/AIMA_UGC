"""Stage 3 Excel/Historical Brand Scope 创建请求契约。"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from aima_ugc.contracts.base import AimaHttpModel as BaseModel
from aima_ugc.contracts.http import DataImportIngestionPolicy, LocalDataImportFileManifest


class HistoricalCampaignCreateRequest(BaseModel):
    """服务端历史目录 Campaign；Keyword Pack/Search 与 Excel Filter 在此明确解耦。"""

    model_config = ConfigDict(extra="forbid")

    client_idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    relative_paths: tuple[str, ...] = Field(min_length=1, max_length=1000)
    recursive: bool = False
    brand_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    profile: Literal["aima-monitoring-excel.v1"] = "aima-monitoring-excel.v1"
    ingestion_policy: DataImportIngestionPolicy = "historical_fill_only"

    @field_validator("relative_paths")
    @classmethod
    def validate_relative_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """把目录输入规范为无歧义 POSIX 相对路径并拒绝重复。"""

        normalized = tuple(_historical_relative_path(item) for item in value)
        if len(set(normalized)) != len(normalized):
            raise ValueError("relative_paths 不能重复")
        return normalized

    @field_validator("brand_ids")
    @classmethod
    def validate_brand_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        """selected Brand Scope 不允许重复；空集合表示 all_active。"""

        if len(value) != len(set(value)):
            raise ValueError("brand_ids 不能重复")
        return value


class LocalDataImportCampaignCreateRequest(BaseModel):
    """本地文件暂存 Campaign；过滤仅由 Brand Scope 决定。"""

    model_config = ConfigDict(extra="forbid")

    client_idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    files: tuple[LocalDataImportFileManifest, ...] = Field(min_length=1, max_length=1000)
    brand_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    profile: Literal["aima-monitoring-excel.v1"] = "aima-monitoring-excel.v1"
    ingestion_policy: DataImportIngestionPolicy = "standard_observation"

    @field_validator("brand_ids")
    @classmethod
    def validate_brand_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        """selected Brand Scope 不允许重复；空集合表示 all_active。"""

        if len(value) != len(set(value)):
            raise ValueError("brand_ids 不能重复")
        return value


def _historical_relative_path(value: str) -> str:
    """保持既有 Historical Contract 的批准根目录相对路径约束。"""

    if "\x00" in value or "\\" in value or ":" in value or value.startswith("//"):
        raise ValueError("历史路径必须是无歧义的 POSIX 相对路径")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("历史路径必须位于批准根目录内")
    normalized = path.as_posix()
    if not normalized:
        raise ValueError("历史路径不能为空")
    return normalized


__all__ = [
    "HistoricalCampaignCreateRequest",
    "LocalDataImportCampaignCreateRequest",
]
