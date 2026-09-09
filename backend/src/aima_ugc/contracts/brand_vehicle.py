"""Stage 2 品牌 / 车型管理 HTTP Contract。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from aima_ugc.contracts.base import AimaHttpModel as BaseModel

BrandRole = Literal["owned", "competitor", "other"]
BrandStatus = Literal["active", "deprecated"]
VehicleStatus = Literal["active", "deprecated", "merged"]
CatalogFilterMode = Literal["all_active", "selected"]


def _normalized_identity(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _validated_aliases(value: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = tuple(item.strip() for item in value)
    if any(not item for item in cleaned):
        raise ValueError("品牌别名不能为空")
    identities = tuple(_normalized_identity(item) for item in cleaned)
    if len(identities) != len(set(identities)):
        raise ValueError("同一品牌的别名不能重复")
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
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validated_aliases(value)


class BrandUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: BrandRole | None = None
    status: BrandStatus | None = None
    aliases: tuple[str, ...] | None = Field(default=None, max_length=100)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        return None if value is None else _validated_aliases(value)

    @model_validator(mode="after")
    def require_change(self) -> BrandUpdateRequest:
        if (
            self.display_name is None
            and self.role is None
            and self.status is None
            and self.aliases is None
        ):
            raise ValueError("品牌更新必须至少包含一个字段")
        return self


class BrandAliasResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    text: str
    normalized_text: str


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
    referenced: bool = False
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
    """显式设置 / 清除车型品牌归属；active 车型由 Repository fail closed。"""

    model_config = ConfigDict(extra="forbid")
    brand_id: UUID | None


class VehicleBrandAssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_model_id: UUID
    brand_id: UUID | None
    vehicle_status: VehicleStatus
    vehicle_version: int = Field(gt=0)
    catalog_version: int = Field(gt=0)


class ActiveVehicleBrandIntegrityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_complete: bool
    missing_brand_vehicle_model_ids: tuple[UUID, ...]
    catalog_version: int = Field(gt=0)


class BrandVehicleCatalogSnapshotQuery(BaseModel):
    """冻结全部 active Brand，或显式选择一组 active Brand。"""

    model_config = ConfigDict(extra="forbid")
    mode: CatalogFilterMode = "all_active"
    brand_ids: tuple[UUID, ...] = Field(default=(), max_length=200)

    @model_validator(mode="after")
    def validate_scope(self) -> BrandVehicleCatalogSnapshotQuery:
        if len(self.brand_ids) != len(set(self.brand_ids)):
            raise ValueError("brand_ids 不能重复")
        if self.mode == "selected" and not self.brand_ids:
            raise ValueError("selected 模式必须至少选择一个 brand_id")
        if self.mode == "all_active" and self.brand_ids:
            raise ValueError("all_active 模式不能同时传 brand_ids")
        return self


class CatalogVehicleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    code: str
    display_name: str
    brand_id: UUID | None
    status: VehicleStatus
    version: int = Field(gt=0)


class CatalogVehicleAliasResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_model_id: UUID
    text: str
    normalized_text: str


class CatalogBrandAliasResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brand_id: UUID
    text: str
    normalized_text: str


class BrandVehicleCatalogSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_version: int = Field(gt=0)
    filter_mode: CatalogFilterMode
    selected_brand_ids: tuple[UUID, ...]
    brands: tuple[BrandResponse, ...]
    brand_aliases: tuple[CatalogBrandAliasResponse, ...]
    vehicles: tuple[CatalogVehicleResponse, ...]
    vehicle_aliases: tuple[CatalogVehicleAliasResponse, ...]


__all__ = [
    "ActiveVehicleBrandIntegrityResponse",
    "BrandAliasResponse",
    "BrandCreateRequest",
    "BrandListResponse",
    "BrandResponse",
    "BrandRole",
    "BrandStatus",
    "BrandUpdateRequest",
    "BrandVehicleCatalogSnapshotQuery",
    "BrandVehicleCatalogSnapshotResponse",
    "CatalogBrandAliasResponse",
    "CatalogFilterMode",
    "CatalogVehicleAliasResponse",
    "CatalogVehicleResponse",
    "VehicleBrandAssignmentRequest",
    "VehicleBrandAssignmentResponse",
]
