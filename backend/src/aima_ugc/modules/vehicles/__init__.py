"""车型目录、别名、词包引用与内容车型证据 Owner。"""

from .models import (
    ContentVehicleEvidence,
    VehicleAlias,
    VehicleCatalogSnapshot,
    VehicleModel,
    normalize_vehicle_text,
)

__all__ = [
    "ContentVehicleEvidence",
    "VehicleAlias",
    "VehicleCatalogSnapshot",
    "VehicleModel",
    "normalize_vehicle_text",
]
