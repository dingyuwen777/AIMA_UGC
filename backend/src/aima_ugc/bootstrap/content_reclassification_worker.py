"""旧 Content 品牌车型重分类的正式 PostgreSQL Job 执行器。"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError

from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.content_reclassification import (
    PostgresContentReclassificationRepository,
)
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.modules.vehicles.brand_vehicle import BrandVehicleResolver, ResolverEvidence
from aima_ugc.modules.vehicles.content_reclassification import (
    ContentReclassificationJobPayload,
    ReclassificationBatchCounters,
)
from aima_ugc.modules.vehicles.models import ContentVehicleEvidence
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime


class PostgresContentReclassificationJobExecutor:
    """按冻结目录、Hash Shard 和 UUID Keyset 逐批重分类 Current Content。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        """绑定共享 Platform Runtime；每个批次自行持有短事务。"""

        self._runtime = runtime
        self._resolver = BrandVehicleResolver()

    def execute(
        self,
        *,
        payload: ContentReclassificationJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """重试从已提交检查点继续；证据与检查点始终在同一事务提交。"""

        try:
            while True:
                session = self._runtime.database.new_session()
                try:
                    with session.begin():
                        repository = PostgresContentReclassificationRepository(session)
                        run = repository.get(payload.run_id, for_update=True)
                        if run is None:
                            return JobHandlerResult.failed("reclassification_run_not_found")
                        batch = repository.load_next_batch(run)
                        if not batch:
                            return JobHandlerResult.succeeded(_result(run))

                        snapshot = run.catalog_snapshot
                        vehicle_by_id = {item.id: item for item in snapshot.vehicles}
                        brand_entries: list[
                            tuple[
                                UUID,
                                int,
                                tuple[ResolverEvidence, ...],
                            ]
                        ] = []
                        vehicle_entries: list[
                            tuple[UUID, int, tuple[ContentVehicleEvidence, ...]]
                        ] = []
                        matched_count = 0
                        conflict_count = 0
                        vehicle_locked_count = 0

                        for candidate in batch:
                            resolution = self._resolver.resolve(
                                snapshot,
                                title=candidate.title,
                                raw_text=candidate.text,
                                transcript_text=None,
                                manual_vehicle_ids=candidate.manual_vehicle_ids,
                            )
                            conflicts = list(resolution.conflicts)
                            brand_evidence = list(resolution.brand_evidence)
                            for vehicle_id in candidate.existing_vehicle_ids:
                                vehicle = vehicle_by_id.get(vehicle_id)
                                if vehicle is None or vehicle.brand_id is None:
                                    conflicts.append(
                                        f"existing_vehicle_outside_snapshot:{vehicle_id}"
                                    )
                                    continue
                                brand_evidence.append(
                                    ResolverEvidence(
                                        entity_id=vehicle.brand_id,
                                        source="vehicle_match",
                                        matched_text=None,
                                        source_field=None,
                                        derived_vehicle_model_id=vehicle.id,
                                    )
                                )
                            deduplicated_brand_evidence = _deduplicate_brand_evidence(
                                tuple(brand_evidence)
                            )
                            brand_entries.append(
                                (
                                    candidate.content_id,
                                    candidate.content_version,
                                    deduplicated_brand_evidence,
                                )
                            )
                            if deduplicated_brand_evidence or resolution.vehicle_matches:
                                matched_count += 1
                            conflict_count += len(set(conflicts))
                            if candidate.manual_vehicle_ids is not None:
                                vehicle_locked_count += 1
                            automatic_vehicle_evidence = tuple(
                                ContentVehicleEvidence(
                                    id=uuid4(),
                                    content_id=candidate.content_id,
                                    content_version=candidate.content_version,
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
                                for item in resolution.vehicle_evidence
                                if item.source == "alias_match"
                            )
                            vehicle_entries.append(
                                (
                                    candidate.content_id,
                                    candidate.content_version,
                                    automatic_vehicle_evidence,
                                )
                            )

                        vehicle_written, _ = PostgresVehicleCatalogRepository(
                            session
                        ).replace_automatic_alias_evidence_batch(
                            entries=tuple(vehicle_entries),
                        )
                        brand_written, brand_locked_count = PostgresBrandVehicleRepository(
                            session
                        ).replace_automatic_brand_evidence_batch(
                            entries=tuple(brand_entries),
                            catalog_snapshot=snapshot,
                        )
                        counters = ReclassificationBatchCounters(
                            processed_count=len(batch),
                            matched_count=matched_count,
                            unmatched_count=len(batch) - matched_count,
                            brand_evidence_count=brand_written,
                            vehicle_evidence_count=vehicle_written,
                            conflict_count=conflict_count,
                            brand_locked_count=brand_locked_count,
                            vehicle_locked_count=vehicle_locked_count,
                        )
                        run = repository.advance(
                            run_id=run.id,
                            checkpoint_content_id=batch[-1].content_id,
                            counters=counters,
                            fence=fence,
                        )
                finally:
                    session.close()

                context.heartbeat(
                    progress=min(99, int(run.processed_count * 100 / run.max_contents))
                )
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()
        except LeaseLostError:
            raise
        except SQLAlchemyError:
            return JobHandlerResult.retry("reclassification_database_error")
        except ValueError:
            return JobHandlerResult.failed("reclassification_snapshot_invalid")


def _deduplicate_brand_evidence(
    evidence: tuple[ResolverEvidence, ...],
) -> tuple[ResolverEvidence, ...]:
    """按持久唯一身份去重，优先保留 Resolver 携带的文本来源。"""

    deduplicated: dict[tuple[object, ...], ResolverEvidence] = {}
    for item in evidence:
        identity = (item.entity_id, item.source, item.derived_vehicle_model_id)
        current = deduplicated.get(identity)
        if current is None or (current.matched_text is None and item.matched_text is not None):
            deduplicated[identity] = item
    return tuple(deduplicated.values())


def _result(run) -> dict[str, object]:  # type: ignore[no-untyped-def]
    """生成不含正文或目录快照的安全终态统计。"""

    return {
        "run_id": str(run.id),
        "checkpoint_content_id": (
            None if run.checkpoint_content_id is None else str(run.checkpoint_content_id)
        ),
        "processed_count": run.processed_count,
        "matched_count": run.matched_count,
        "unmatched_count": run.unmatched_count,
        "brand_evidence_count": run.brand_evidence_count,
        "vehicle_evidence_count": run.vehicle_evidence_count,
        "conflict_count": run.conflict_count,
        "brand_locked_count": run.brand_locked_count,
        "vehicle_locked_count": run.vehicle_locked_count,
        "limit_reached": run.processed_count >= run.max_contents,
    }


__all__ = ["PostgresContentReclassificationJobExecutor"]
