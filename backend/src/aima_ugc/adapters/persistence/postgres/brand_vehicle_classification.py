"""复用纯 Resolver，将已稳定的 Current 与人工选择装配成分类输入。"""

from uuid import UUID, uuid4

from aima_ugc.modules.vehicles.brand_vehicle import (
    BrandVehicleCatalogSnapshot,
    BrandVehicleResolution,
    BrandVehicleResolver,
)
from aima_ugc.modules.vehicles.models import ContentVehicleEvidence
from aima_ugc.platform.time import beijing_now

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


def converge_current_brand_vehicle_batch(
    *,
    snapshot: BrandVehicleCatalogSnapshot,
    inputs: tuple[PostgresContentClassificationInput, ...],
    vehicle_repository: PostgresVehicleCatalogRepository,
    brand_repository: PostgresBrandVehicleRepository,
    resolver: BrandVehicleResolver,
    review_carry: tuple[tuple[UUID, int, int], ...] = (),
) -> dict[tuple[UUID, int], BrandVehicleResolution]:
    """对已锁定完整 Current 原子收敛 v2 证据；补采与有界历史修复共用此入口。"""

    if snapshot.resolver_semantics != "brand_scoped_vehicle_v2":
        raise ValueError("完整 Current 分类收敛只接受冻结 v2 目录")
    resolutions = resolve_current_brand_vehicle_batch(
        snapshot=snapshot,
        inputs=inputs,
        vehicle_repository=vehicle_repository,
        brand_repository=brand_repository,
        resolver=resolver,
        review_carry=review_carry,
    )
    pairs = tuple((item.content_id, item.content_version) for item in inputs)
    vehicle_repository.converge_automatic_alias_evidence_for_replay(
        entries=tuple(
            (
                content_id,
                version,
                tuple(
                    ContentVehicleEvidence(
                        id=uuid4(),
                        content_id=content_id,
                        content_version=version,
                        vehicle_model_id=item.entity_id,
                        source="alias_match",
                        matched_text=item.matched_text,
                        source_field=item.source_field,
                        catalog_version=snapshot.catalog_version,
                        confidence=1.0,
                        is_manual_locked=False,
                        is_active=True,
                        created_at=beijing_now(),
                    )
                    for item in resolutions[(content_id, version)].vehicle_evidence
                    if item.source == "alias_match"
                ),
            )
            for content_id, version in pairs
        ),
        source_pairs=pairs,
        replace_existing=snapshot.filter_scope == "all_active",
        include_import_text_matches=True,
        replace_vehicle_model_ids=snapshot.automatic_evidence_vehicle_ids,
    )
    brand_repository.converge_automatic_brand_evidence_for_replay(
        entries=tuple(
            (
                content_id,
                version,
                tuple(
                    item
                    for item in resolutions[(content_id, version)].brand_evidence
                    if item.source != "manual_review"
                ),
            )
            for content_id, version in pairs
        ),
        source_pairs=pairs,
        catalog_snapshot=snapshot,
        preserve_unconfirmed=False,
    )
    return resolutions
