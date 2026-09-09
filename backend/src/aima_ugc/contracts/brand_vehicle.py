"""Stage 2 Brand/Vehicle 管理与冻结过滤快照 HTTP Contract。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from aima_ugc.contracts.base import AimaHttpModel as BaseModel

BrandRole = Literal["owned", "competitor", "other"]
BrandStatus = Literal["active", "deprecated"]
BrandFilterScope = Literal["all_active", "selected"]
VehicleStatus = Literal["active", "deprecated", "merged"]


def _normalize_aliases(value: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = tuple(item.strip() for item in value)
    if any(not item for item in cleaned):
        raise ValueError("品牌识别词不能为空")
    normalized = tuple(" ".join(item.split()).casefold() for item in cleaned)
    if len(normalized) != len(set(normalized)):
        raise ValueError("同一品牌的识别词不能重复")
    return cleaned


class BrandCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    display_name: str = Field(min_length=1, max_length=200)
    role: BrandRole
    aliases: tuple[str, ...] = Field(default=(), max_length=100)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _normalize_aliases(value)


class BrandUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: BrandRole | None = None
    status: BrandStatus | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_change(self) -> BrandUpdateRequest:
        if self.display_name is None and self.role is None and self.status is None:
            raise ValueError("品牌更新必须至少包含一个字段")
        return self


class BrandAliasCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=200)

    @field_validator("text", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class BrandAliasResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    brand_id: UUID
    text: str
    normalized_text: str
    created_at: datetime


class BrandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    code: str
    display_name: str
    role: BrandRole
    status: BrandStatus
    version: int = Field(gt=0)
    catalog_version: int = Field(gt=0)
    aliases: tuple[BrandAliasResponse, ...] = ()
    created_at: datetime
    updated_at: datetime


class BrandListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[BrandResponse, ...]
    total: int = Field(ge=0)
    catalog_version: int = Field(gt=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


class VehicleBrandAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brand_id: UUID | None


class VehicleBrandAssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_model_id: UUID
    brand_id: UUID | None
    version: int = Field(gt=0)
    catalog_version: int = Field(gt=0)


class CatalogBrandSnapshotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    code: str
    display_name: str
    role: BrandRole
    version: int = Field(gt=0)
    catalog_version: int = Field(gt=0)


class CatalogBrandAliasSnapshotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    brand_id: UUID
    text: str
    normalized_text: str


class CatalogVehicleSnapshotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    code: str
    display_name: str
    brand_id: UUID
    status: VehicleStatus
    version: int = Field(gt=0)
    catalog_version: int = Field(gt=0)


class CatalogVehicleAliasSnapshotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    vehicle_model_id: UUID
    text: str
    normalized_text: str


class BrandVehicleCatalogSnapshotResponse(BaseModel):
    """冻结的 Filter Scope；selected Brand 自动包含其全部 active Vehicle。"""

    model_config = ConfigDict(extra="forbid")
    catalog_version: int = Field(gt=0)
    filter_scope: BrandFilterScope
    selected_brand_ids: tuple[UUID, ...]
    brands: tuple[CatalogBrandSnapshotItem, ...]
    brand_aliases: tuple[CatalogBrandAliasSnapshotItem, ...]
    vehicles: tuple[CatalogVehicleSnapshotItem, ...]
    vehicle_aliases: tuple[CatalogVehicleAliasSnapshotItem, ...]
    ambiguous_brand_aliases: tuple[str, ...]
    ambiguous_vehicle_aliases: tuple[str, ...]
    unresolved_active_vehicle_ids: tuple[UUID, ...]


class BrandVehicleCatalogReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ready: bool
    catalog_version: int = Field(gt=0)
    unresolved_active_vehicle_ids: tuple[UUID, ...]


__all__ = [
    "BrandAliasCreateRequest",
    "BrandAliasResponse",
    "BrandCreateRequest",
    "BrandFilterScope",
    "BrandListResponse",
    "BrandResponse",
    "BrandRole",
    "BrandStatus",
    "BrandUpdateRequest",
    "BrandVehicleCatalogReadinessResponse",
    "BrandVehicleCatalogSnapshotResponse",
    "CatalogBrandAliasSnapshotItem",
    "CatalogBrandSnapshotItem",
    "CatalogVehicleAliasSnapshotItem",
    "CatalogVehicleSnapshotItem",
    "VehicleBrandAssignmentRequest",
    "VehicleBrandAssignmentResponse",
]
