"""复用纯 Resolver，将已稳定的 Current 与人工选择装配成分类输入。"""

from uuid import UUID

from aima_ugc.modules.vehicles.brand_vehicle import (
    BrandVehicleCatalogSnapshot,
    BrandVehicleResolution,
    BrandVehicleResolver,
)

from .brand_vehicle import PostgresBrandVehicleRepository
from .content_complete import PostgresContentClassificationInput
from .vehicles import PostgresVehicleCatalogRepository


def resolve_current_brand_vehicle_batch(
    *,
    snapshot: BrandVehicleCatalogSnapshot,
    inputs: tuple[PostgresContentClassificationInput, ...],
    vehicle_repository: PostgresVehicleCatalogRepository,
    brand_repository: PostgresBrandVehicleRepository,
    resolver: BrandVehicleResolver,
    review_carry: tuple[tuple[UUID, int, int], ...] = (),
) -> dict[tuple[UUID, int], BrandVehicleResolution]:
    """按统一锁顺序读取人工事实，所有来源继续调用同一个生产 Resolver。"""

    pairs = tuple((item.content_id, item.content_version) for item in inputs)
    if review_carry:
        review_pairs = tuple(
            {
                (content_id, version)
                for content_id, source, target in review_carry
                for version in (source, target)
            }
        )
        vehicle_repository.load_locked_manual_vehicle_ids_batch(review_pairs)
        brand_repository.load_locked_manual_brand_ids_batch(review_pairs)
        vehicle_repository.carry_manual_review_batch(review_carry)
        brand_repository.carry_manual_brand_review_batch(review_carry)
    manual_vehicles = vehicle_repository.load_locked_manual_vehicle_ids_batch(pairs)
    manual_brands = brand_repository.load_locked_manual_brand_ids_batch(pairs)
    return {
        (item.content_id, item.content_version): resolver.resolve(
            snapshot,
            title=item.title,
            raw_text=item.text,
            transcript_text=None,
            manual_brand_ids=manual_brands.get((item.content_id, item.content_version)),
            manual_vehicle_ids=manual_vehicles.get((item.content_id, item.content_version)),
        )
        for item in inputs
    }
