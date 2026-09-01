"""车型目录与内容车型证据领域对象。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

VehicleStatus = Literal["active", "deprecated", "merged"]
VehicleEvidenceSource = Literal["alias_match", "ai_candidate", "manual_review", "import"]


def normalize_vehicle_text(value: str) -> str:
    """形成大小写不敏感、合并空白的车型文本身份。"""

    normalized = " ".join(value.strip().split()).casefold()
    if not normalized:
        raise ValueError("车型文本不能为空")
    return normalized


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


@dataclass(frozen=True, slots=True)
class VehicleCatalogSnapshot:
    """任务冻结的车型选择和解析后别名。"""

    catalog_version: int
    vehicle_model_ids: tuple[UUID, ...]
    resolved_aliases: tuple[str, ...]
    vehicle_versions: tuple[tuple[UUID, int], ...] = ()
    alias_bindings: tuple[tuple[UUID, str], ...] = ()


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


__all__ = [
    "ContentVehicleEvidence",
    "VehicleAlias",
    "VehicleCatalogSnapshot",
    "VehicleEvidenceSource",
    "VehicleModel",
    "VehicleStatus",
    "normalize_vehicle_text",
]
