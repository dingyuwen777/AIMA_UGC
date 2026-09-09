"""品牌 / 车型目录、统一快照与内容证据领域对象。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

BrandRole = Literal["owned", "competitor", "other"]
BrandStatus = Literal["active", "deprecated"]
BrandEvidenceSource = Literal["alias_match", "vehicle_match", "manual_review", "import"]
VehicleStatus = Literal["active", "deprecated", "merged"]
VehicleEvidenceSource = Literal["alias_match", "ai_candidate", "manual_review", "import"]
CatalogFilterMode = Literal["all_active", "selected"]
ResolutionKind = Literal["brand", "vehicle"]
ResolutionSourceField = Literal["title", "text"]


def normalize_vehicle_text(value: str) -> str:
    """形成大小写不敏感、合并空白的品牌 / 车型文本身份。"""

    normalized = " ".join(value.strip().split()).casefold()
    if not normalized:
        raise ValueError("品牌 / 车型文本不能为空")
    return normalized


@dataclass(frozen=True, slots=True)
class BrandAlias:
    """品牌当前有效别名。"""

    id: UUID
    brand_id: UUID
    text: str
    normalized_text: str


@dataclass(frozen=True, slots=True)
class Brand:
    """稳定品牌概念；role 表达自有 / 竞品 / 其他业务角色。"""

    id: UUID
    code: str
    display_name: str
    role: BrandRole
    status: BrandStatus
    version: int
    catalog_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class VehicleAlias:
    """车型当前有效别名。"""

    id: UUID
    vehicle_model_id: UUID
    text: str
    normalized_text: str


@dataclass(frozen=True, slots=True)
class VehicleModel:
    """稳定车型概念；code 不随显示名变化。"""

    id: UUID
    code: str
    display_name: str
    status: VehicleStatus
    version: int
    catalog_version: int
    merged_into_id: UUID | None
    created_at: datetime
    updated_at: datetime
    series_name: str | None = None
    category_name: str | None = None
    brand_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class VehicleCatalogSnapshot:
    """既有 Collection 任务冻结的车型选择和解析后别名。"""

    catalog_version: int
    vehicle_model_ids: tuple[UUID, ...]
    resolved_aliases: tuple[str, ...]
    vehicle_versions: tuple[tuple[UUID, int], ...] = ()
    alias_bindings: tuple[tuple[UUID, str], ...] = ()


@dataclass(frozen=True, slots=True)
class CatalogSnapshot:
    """BrandVehicleResolver 使用的统一只读目录快照。"""

    catalog_version: int
    brands: tuple[Brand, ...]
    brand_aliases: tuple[BrandAlias, ...]
    vehicles: tuple[VehicleModel, ...]
    vehicle_aliases: tuple[VehicleAlias, ...]
    filter_mode: CatalogFilterMode = "all_active"
    selected_brand_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ContentVehicleEvidence:
    """内容与车型之间可追溯、可人工锁定的证据。"""

    id: UUID
    content_id: UUID
    content_version: int
    vehicle_model_id: UUID
    source: VehicleEvidenceSource
    matched_text: str | None
    source_field: str | None
    catalog_version: int
    confidence: float | None
    is_manual_locked: bool
    is_active: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ContentBrandEvidence:
    """内容与品牌之间可追溯、可人工锁定的证据。"""

    id: UUID
    content_id: UUID
    content_version: int
    brand_id: UUID
    source: BrandEvidenceSource
    matched_text: str | None
    source_field: str | None
    derived_vehicle_model_id: UUID | None
    catalog_version: int
    confidence: float | None
    is_manual_locked: bool
    is_active: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResolutionEvidence:
    """Resolver 产生的、尚未绑定 content identity 的确定性证据。"""

    kind: ResolutionKind
    target_id: UUID
    source: Literal["alias_match", "vehicle_match"]
    matched_text: str
    source_field: ResolutionSourceField
    derived_vehicle_model_id: UUID | None = None
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class ResolutionConflict:
    """单个别名无法确定唯一实体时保留的可观察冲突。"""

    kind: ResolutionKind
    normalized_text: str
    candidate_ids: tuple[UUID, ...]
    source_field: ResolutionSourceField


@dataclass(frozen=True, slots=True)
class BrandVehicleResolution:
    """Resolver 的确定性输出；冲突不会被折叠成猜测结论。"""

    catalog_version: int
    matched: bool
    brand_matches: tuple[ResolutionEvidence, ...]
    vehicle_matches: tuple[ResolutionEvidence, ...]
    effective_brand_ids: tuple[UUID, ...]
    effective_vehicle_model_ids: tuple[UUID, ...]
    conflicts: tuple[ResolutionConflict, ...]

    @property
    def brand_evidence(self) -> tuple[ResolutionEvidence, ...]:
        """兼容 Stage 2 早期内部命名；正式结果字段为 brand_matches。"""

        return self.brand_matches

    @property
    def vehicle_evidence(self) -> tuple[ResolutionEvidence, ...]:
        """兼容 Stage 2 早期内部命名；正式结果字段为 vehicle_matches。"""

        return self.vehicle_matches


__all__ = [
    "Brand",
    "BrandAlias",
    "BrandEvidenceSource",
    "BrandRole",
    "BrandStatus",
    "BrandVehicleResolution",
    "CatalogFilterMode",
    "CatalogSnapshot",
    "ContentBrandEvidence",
    "ContentVehicleEvidence",
    "ResolutionConflict",
    "ResolutionEvidence",
    "ResolutionKind",
    "ResolutionSourceField",
    "VehicleAlias",
    "VehicleCatalogSnapshot",
    "VehicleEvidenceSource",
    "VehicleModel",
    "VehicleStatus",
    "normalize_vehicle_text",
]
