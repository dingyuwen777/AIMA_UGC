"""历史一致性修复的跨 Owner 短事务编排，不访问 Provider 或模型。"""

from collections import Counter

from sqlalchemy.exc import SQLAlchemyError

from aima_ugc.adapters.persistence.postgres.analysis_reuse import PostgresAnalysisReuseRepository
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.brand_vehicle_classification import (
    converge_current_brand_vehicle_batch,
)
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.adapters.persistence.postgres.content_consistency_repair import (
    PostgresContentConsistencyRepairRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.adapters.persistence.postgres.voice_plaza_projection import (
    defer_voice_plaza_projection,
    flush_deferred_voice_plaza_projection,
)
from aima_ugc.modules.content.consistency_repair import (
    ContentConsistencyRepairPayload,
    ContentConsistencyRepairRun,
)
from aima_ugc.modules.vehicles.brand_vehicle import BrandVehicleResolver
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, LeaseLostError
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

from .runtime import PlatformRuntime


class PostgresContentConsistencyRepairExecutor:
    """每批只处理冻结目标页，业务事实与检查点同事务提交。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        """绑定共享平台设施与唯一生产 Resolver。"""
        self._runtime = runtime
        self._resolver = BrandVehicleResolver()

    def execute(
        self,
        *,
        payload: ContentConsistencyRepairPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """按已提交 Keyset 恢复；取消和失效 Fence 不允许产生下一批业务事实。"""
        try:
            while True:
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()
                with self._runtime.database.new_session() as session, session.begin():
                    # 全部写链统一先 Job，再 Run，再 UUID 排序的 Content，避免锁序反转。
                    PostgresJobRepository(session).lock_current_execution(fence)
                    repository = PostgresContentConsistencyRepairRepository(session)
                    run = repository.get(payload.run_id, for_update=True)
                    if run is None:
                        return JobHandlerResult.failed("consistency_repair_run_not_found")
                    if run.job_id != fence.job_id:
                        raise LeaseLostError("修复 Fence 不属于此 Run")
                    ids = repository.load_next_target_ids(run)
                    if not ids:
                        if run.processed_count != run.target_count:
                            return JobHandlerResult.failed("consistency_repair_target_missing")
                        return JobHandlerResult.succeeded(repair_run_progress(run))
                    inputs = PostgresCompleteContentRepository(
                        session
                    ).lock_current_classification_inputs(content_ids=ids)
                    if len(inputs) != len(ids):
                        raise ValueError("修复冻结目标已缺失")
                    pairs = tuple((item.content_id, item.content_version) for item in inputs)
                    analysis_repository = PostgresAnalysisReuseRepository(session)
                    plans = analysis_repository.plan_reuses(pairs)
                    brand_candidates = repository.brand_candidate_ids(pairs)
                    candidates = brand_candidates | {
                        plan.content_id
                        for plan in plans
                        if plan.reason not in ("direct", "no_success", "target_missing")
                    }
                    selected = tuple(item for item in inputs if item.content_id in candidates)
                    classification_inputs = tuple(
                        item for item in selected if item.content_id in brand_candidates
                    )
                    classification_pairs = tuple(
                        (item.content_id, item.content_version) for item in classification_inputs
                    )
                    selected_pairs = tuple(
                        (item.content_id, item.content_version) for item in selected
                    )
                    # 已有完整证据的 AI 候选只维护复用关系，避免重复刷新 Evidence 时间。
                    before = repository.evidence_state(classification_pairs)
                    vehicle = PostgresVehicleCatalogRepository(session)
                    brand = PostgresBrandVehicleRepository(session)
                    vehicle_carry, brand_carry = repository.manual_carry_sources(
                        classification_pairs
                    )
                    review_pairs = tuple(
                        sorted(
                            {
                                *classification_pairs,
                                *((item[0], item[1]) for item in vehicle_carry),
                                *((item[0], item[1]) for item in brand_carry),
                            }
                        )
                    )
                    # 两个人工维度的源版本各自独立；当前 unlocked 墓碑优先于旧锁。
                    vehicle.load_locked_manual_vehicle_ids_batch(review_pairs)
                    brand.load_locked_manual_brand_ids_batch(review_pairs)
                    defer_voice_plaza_projection(session)
                    vehicle.carry_manual_review_batch(vehicle_carry)
                    brand.carry_manual_brand_review_batch(brand_carry)
                    resolutions = converge_current_brand_vehicle_batch(
                        snapshot=run.catalog_snapshot,
                        inputs=classification_inputs,
                        vehicle_repository=vehicle,
                        brand_repository=brand,
                        resolver=self._resolver,
                    )
                    outcomes = analysis_repository.converge_reuses(selected_pairs)
                    after = repository.evidence_state(classification_pairs)
                    changed = {item for item in before if before[item] != after[item]}
                    reused = {
                        item.plan.content_id for item in outcomes if item.status == "inserted"
                    }
                    flush_deferred_voice_plaza_projection(session, tuple(sorted(changed | reused)))
                    run = repository.advance(
                        run=run,
                        checkpoint_content_id=ids[-1],
                        processed_count=len(ids),
                        counters={
                            "candidate_count": len(candidates),
                            "brand_changed_count": len(changed),
                            "reused_count": len(reused),
                            "existing_reuse_count": sum(
                                item.status == "existing" for item in outcomes
                            ),
                            "unmatched_count": sum(
                                not item.matched for item in resolutions.values()
                            ),
                        },
                        analysis_reasons=dict(Counter(item.reason for item in plans)),
                        fence=fence,
                    )
                context.heartbeat(
                    progress=min(99, run.processed_count * 100 // max(1, run.target_count))
                )
        except LeaseLostError:
            raise
        except SQLAlchemyError:
            return JobHandlerResult.retry("consistency_repair_database_error")
        except ValueError:
            return JobHandlerResult.failed("consistency_repair_input_invalid")


def repair_run_progress(run: ContentConsistencyRepairRun) -> dict[str, object]:
    """安全的运维输出只包含范围身份、目录版本和统计，不含正文或别名快照。"""
    return {
        "run_id": str(run.id),
        "job_id": str(run.job_id),
        "source_collection_run_id": (
            None if run.source_collection_run_id is None else str(run.source_collection_run_id)
        ),
        "catalog_version": run.catalog_snapshot.catalog_version,
        "checkpoint_content_id": (
            None if run.checkpoint_content_id is None else str(run.checkpoint_content_id)
        ),
        "batch_size": run.batch_size,
        "max_contents": run.max_contents,
        "target_count": run.target_count,
        "processed_count": run.processed_count,
        "candidate_count": run.candidate_count,
        "brand_changed_count": run.brand_changed_count,
        "reused_count": run.reused_count,
        "existing_reuse_count": run.existing_reuse_count,
        "unmatched_count": run.unmatched_count,
        "analysis_reasons": run.analysis_reasons,
        "created_by": run.created_by,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }
