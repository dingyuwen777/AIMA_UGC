"""Stage 8D Content Analysis Job 的 PostgreSQL/LLM 正式执行器。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.llm import (
    OpenAICompatibleContentLabelingLLM,
    OpenAICompatibleLLMError,
    load_llm_pricing,
)
from aima_ugc.adapters.llm.request_audit import LLMHTTPRequestAudit
from aima_ugc.adapters.persistence.postgres.analysis import (
    AnalysisRunConfigurationChanged,
    PostgresAnalysisRepository,
)
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.adapters.persistence.postgres.content_queries import (
    PostgresContentQueryRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.contracts.analysis import ContentLabelAnalysisV3
from aima_ugc.contracts.http import ContentFilterSnapshot
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingService,
    FrozenPromptTaxonomyLoader,
    PromptTaxonomyLoader,
)
from aima_ugc.modules.analysis.content_analysis_job import (
    CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
    CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
    CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
    CONTENT_ANALYSIS_JOB_TYPE,
    CONTENT_ANALYSIS_PLAN_JOB_TYPE,
    ContentAnalysisJobPayload,
    ContentAnalysisPlanJobPayload,
    is_analysis_all_scope_filter_snapshot,
)
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity, AnalysisWorkItem
from aima_ugc.modules.analysis.schemes import prompt_taxonomy_from_version
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord, LeaseLostError
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.security import SecretFileError, read_secret_file

from .analysis_identity import current_analysis_generation_config
from .runtime import PlatformRuntime

_LOGGER = logging.getLogger("aima_ugc")
_ANALYSIS_ALL_FREEZE_BATCH_SIZE = 10_000


class PostgresContentAnalysisJobExecutor:
    """分批调用正式 ContentLabelingService，并以当前 Fence 提交每条结果。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        service_factory: Callable[[], tuple[ContentLabelingService, Callable[[], None]]]
        | None = None,
    ) -> None:
        self._runtime = runtime
        self._service_factory = service_factory

    def execute(
        self,
        *,
        payload: ContentAnalysisJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        service: ContentLabelingService | None = None

        def close_service() -> None:
            return None

        try:
            while True:
                session = self._runtime.database.new_session()
                try:
                    with session.begin():
                        repository = PostgresAnalysisRepository(session)
                        work = repository.load_pending(
                            payload.request_id,
                            limit=self._runtime.settings.analysis_batch_size,
                        )
                        stats = repository.stats(payload.request_id)
                        if work:
                            repository.mark_run_running(work[0].analysis_run_id)
                finally:
                    session.close()
                if not work:
                    return JobHandlerResult.succeeded(
                        {
                            "request_id": str(payload.request_id),
                            "succeeded": stats["succeeded"],
                            "failed": stats["failed"],
                            "stale": stats["stale"],
                        }
                    )
                if service is None:
                    try:
                        if self._service_factory is None:
                            service, close_service = self._default_service(work[0].analysis_run_id)
                        else:
                            service, close_service = self._service_factory()
                    except OSError, SecretFileError, ValueError:
                        return JobHandlerResult.failed("analysis_configuration_unavailable")
                if not _matches_frozen_configuration(work[0], service):
                    return JobHandlerResult.failed("analysis_run_configuration_changed")
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()

                try:
                    batch = service.label_contents(
                        tuple(item.content for item in work),
                        max_validation_retries=self._runtime.settings.llm_validation_retries,
                    )
                except OpenAICompatibleLLMError as exc:
                    return (
                        JobHandlerResult.retry(f"llm_{exc.error_code}")
                        if exc.retryable
                        else JobHandlerResult.failed(f"llm_{exc.error_code}")
                    )

                by_item_no = {item.item_no: item for item in batch.items}
                for item_no, work_item in enumerate(work, start=1):
                    result = by_item_no[item_no]
                    session = self._runtime.database.new_session()
                    try:
                        with session.begin():
                            repository = PostgresAnalysisRepository(session)
                            if result.analysis_status == "succeeded" and isinstance(
                                result.analysis, ContentLabelAnalysisV3
                            ):
                                repository.persist_success(
                                    fence=fence,
                                    work_item=work_item,
                                    analysis=result.analysis,
                                )
                            else:
                                repository.mark_failed(
                                    fence=fence,
                                    request_id=payload.request_id,
                                    content_id=work_item.content_id,
                                    error_code=(
                                        result.validation_error_codes[0]
                                        if result.validation_error_codes
                                        else "validation_failed"
                                    ),
                                )
                    except LeaseLostError:
                        raise
                    except AnalysisRunConfigurationChanged:
                        return JobHandlerResult.failed("analysis_run_configuration_changed")
                    finally:
                        session.close()

                context.heartbeat(progress=_progress_after_batch(stats, processed_count=len(work)))
        finally:
            close_service()

    def _default_service(
        self,
        analysis_run_id: UUID,
    ) -> tuple[ContentLabelingService, Callable[[], None]]:
        settings = self._runtime.settings
        if settings.llm_base_url is None or settings.llm_model is None:
            raise ValueError("正式 Analysis 缺少 LLM base URL 或 model")
        api_key = read_secret_file(
            settings.llm_api_key_file,
            root=settings.external_secret_root,
        )
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                run = PostgresAnalysisRepository(session).get_run(analysis_run_id)
                if run is None:
                    raise ValueError("Analysis Run 不存在")
                scheme_version_id = cast(UUID | None, run["analysis_scheme_version_id"])
                prompt_snapshot = cast(str | None, run["prompt_text_snapshot"])
                if scheme_version_id is None or prompt_snapshot is None:
                    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
                else:
                    version = PostgresAnalysisSchemeRepository(session).get_version(
                        scheme_version_id
                    )
                    if version is None:
                        raise ValueError("Analysis Scheme Version 不存在")
                    taxonomy = prompt_taxonomy_from_version(version)
                    if taxonomy.prompt_text != prompt_snapshot:
                        raise ValueError("Analysis Run Prompt 快照与 Scheme Version 不一致")
                if (
                    taxonomy.prompt_version != run["prompt_version"]
                    or taxonomy.prompt_sha256 != run["prompt_sha256"]
                    or taxonomy.taxonomy_sha256 != run["taxonomy_sha256"]
                ):
                    raise ValueError("Analysis Run 冻结身份与 Prompt 快照不一致")
        finally:
            session.close()
        adapter = OpenAICompatibleContentLabelingLLM(
            base_url=settings.llm_base_url,
            api_key=api_key,
            model=settings.llm_model,
            provider_name=settings.llm_provider_name,
            timeout_seconds=settings.llm_timeout_seconds,
            max_connections=settings.llm_max_connections,
            pricing_catalog=load_llm_pricing(),
            request_audit=self._record_audit,
        )
        return (
            ContentLabelingService(
                prompt_loader=FrozenPromptTaxonomyLoader(taxonomy),
                llm=adapter,
            ),
            adapter.close,
        )

    def _record_audit(self, audit: LLMHTTPRequestAudit) -> None:
        log_event(
            self._runtime.logger,
            logging.INFO,
            "analysis.llm_request_completed",
            "Analysis LLM 请求已完成。",
            provider=audit.provider,
            model=audit.model,
            status=audit.status,
            status_code=audit.status_code,
            error_code=audit.error_code,
            input_tokens=audit.input_tokens,
            output_tokens=audit.output_tokens,
            cost_amount=str(audit.cost_amount) if audit.cost_amount is not None else None,
            cost_currency=audit.cost_currency,
        )


class PostgresContentAnalysisPlanJobExecutor:
    """冻结 Run Target；公开 all 使用可续跑的短事务批次，再启动 Shard。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        freeze_batch_size: int = _ANALYSIS_ALL_FREEZE_BATCH_SIZE,
    ) -> None:
        if freeze_batch_size <= 0:
            raise ValueError("freeze_batch_size 必须大于 0")
        self._runtime = runtime
        self._freeze_batch_size = freeze_batch_size

    def execute_plan(
        self,
        *,
        payload: ContentAnalysisPlanJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        while True:
            progress: int | None = None
            session = self._runtime.database.new_session()
            try:
                try:
                    with session.begin():
                        jobs = PostgresJobRepository(session)
                        jobs.lock_current_execution(fence)
                        repository = PostgresAnalysisRepository(session)
                        run = repository.get_run(payload.run_id, for_update=True)
                        if run is None:
                            return JobHandlerResult.failed("analysis_run_not_found")
                        all_scope = is_analysis_all_scope_filter_snapshot(run["filter_snapshot"])
                        if run["cancel_requested_at"] is not None:
                            if all_scope:
                                repository.clear_run_targets(payload.run_id)
                            return JobHandlerResult.cancelled()

                        expected_target_count = cast(int, run["target_count"])
                        frozen_count = repository.frozen_target_count(payload.run_id)
                        if not all_scope:
                            if frozen_count == 0:
                                frozen_count = repository.freeze_run_targets(
                                    run_id=payload.run_id,
                                    target_statement=_target_statement_from_run(session, run),
                                )
                            if frozen_count != expected_target_count:
                                raise _AnalysisTargetSelectionChanged
                            created = schedule_analysis_run_shards(
                                session,
                                run_id=payload.run_id,
                                max_in_flight=(
                                    self._runtime.settings.analysis_run_max_in_flight_jobs
                                ),
                                request_id=None,
                            )
                            jobs.lock_current_execution(fence)
                            return JobHandlerResult.succeeded(
                                {
                                    "run_id": str(payload.run_id),
                                    "frozen_target_count": frozen_count,
                                    "scheduled_shards": created,
                                }
                            )

                        content_repository = PostgresContentQueryRepository(
                            session,
                            analysis_identity=None,
                        )
                        batch = content_repository.list_all_analysis_targets(
                            after_content_id=repository.last_frozen_content_id(payload.run_id),
                            limit=self._freeze_batch_size,
                        )
                        if not batch:
                            current_target_count = content_repository.count_all_analysis_targets()
                            if (
                                frozen_count != expected_target_count
                                or current_target_count != expected_target_count
                            ):
                                repository.clear_run_targets(payload.run_id)
                                jobs.lock_current_execution(fence)
                                return JobHandlerResult.failed("content_analysis_target_changed")
                            created = schedule_analysis_run_shards(
                                session,
                                run_id=payload.run_id,
                                max_in_flight=(
                                    self._runtime.settings.analysis_run_max_in_flight_jobs
                                ),
                                request_id=None,
                            )
                            jobs.lock_current_execution(fence)
                            return JobHandlerResult.succeeded(
                                {
                                    "run_id": str(payload.run_id),
                                    "frozen_target_count": frozen_count,
                                    "scheduled_shards": created,
                                }
                            )

                        next_count = frozen_count + len(batch)
                        if next_count > expected_target_count:
                            repository.clear_run_targets(payload.run_id)
                            jobs.lock_current_execution(fence)
                            return JobHandlerResult.failed("content_analysis_target_changed")
                        repository.append_run_targets(
                            run_id=payload.run_id,
                            start_ordinal=frozen_count,
                            targets=batch,
                        )
                        jobs.lock_current_execution(fence)
                        progress = min(
                            99,
                            int(next_count * 100 / max(expected_target_count, 1)),
                        )
                except _AnalysisTargetSelectionChanged:
                    return JobHandlerResult.failed("content_analysis_target_changed")
            finally:
                session.close()

            if progress is not None:
                context.heartbeat(progress=progress)


class _AnalysisTargetSelectionChanged(RuntimeError):
    """Preview 后目标数量变化；抛出异常以回滚整次冻结事务。"""


def _target_statement_from_run(session: Session, run: RowMapping) -> object:
    """按 Run 中冻结的筛选与 Analysis 身份重建集合式目标查询。"""

    repository = PostgresContentQueryRepository(
        session,
        analysis_identity=AnalysisConfigurationIdentity(
            prompt_version=cast(str, run["prompt_version"]),
            prompt_sha256=cast(str, run["prompt_sha256"]),
            taxonomy_sha256=cast(str, run["taxonomy_sha256"]),
            model_provider=cast(str, run["model_provider"]),
            model=cast(str, run["model"]),
        ),
    )
    if is_analysis_all_scope_filter_snapshot(run["filter_snapshot"]):
        raise ValueError("all Scope 必须走有界 Planner Target 冻结")
    if run["scope"] == "query":
        return repository.freeze_target_statement(
            filters=ContentFilterSnapshot.model_validate(run["filter_snapshot"])
        )
    snapshot = cast(dict[str, object], run["filter_snapshot"])
    content_ids = tuple(UUID(str(value)) for value in cast(list[object], snapshot["content_ids"]))
    return repository.freeze_target_statement(content_ids=content_ids)


def schedule_analysis_run_shards(
    session: Session,
    *,
    run_id: UUID,
    max_in_flight: int,
    request_id: str | None,
) -> int:
    """填满 Run 的有界在途窗口；每个 Job 与对应 Shard 在同一事务创建。"""

    repository = PostgresAnalysisRepository(session)
    available = max(max_in_flight - repository.active_shard_count(run_id), 0)
    shard_numbers = repository.next_unscheduled_shards(run_id, limit=available)
    jobs = PostgresJobRepository(session)
    for shard_no in shard_numbers:
        analysis_request_id = uuid4()
        job = jobs.enqueue(
            job_type=CONTENT_ANALYSIS_JOB_TYPE,
            payload_version=CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
            payload=ContentAnalysisJobPayload(
                request_id=analysis_request_id,
                run_id=run_id,
                shard_no=shard_no,
            ).model_dump(mode="json"),
            internal_idempotency_key=f"content-analysis-run:{run_id}:shard:{shard_no}",
            request_id=request_id,
            priority=0,
            max_attempts=CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
            timeout_seconds=CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
        )
        repository.create_run_shard(
            run_id=run_id,
            request_id=analysis_request_id,
            job_id=job.id,
            shard_no=shard_no,
        )
    return len(shard_numbers)


def create_analysis_job_terminal_callback(
    runtime: PlatformRuntime,
) -> Callable[[Session, JobRecord], None]:
    """构造同时处理 Planner 与 Shard 的 Run 终态回调。"""

    def callback(session: Session, job: JobRecord) -> None:
        repository = PostgresAnalysisRepository(session)
        if job.job_type == CONTENT_ANALYSIS_PLAN_JOB_TYPE:
            planner_payload = ContentAnalysisPlanJobPayload.model_validate(job.payload)
            repository.complete_plan_terminal(
                run_id=planner_payload.run_id,
                job_status=job.status,
                error_code=job.error_code,
            )
            return

        shard_payload = ContentAnalysisJobPayload.model_validate(job.payload)
        run_id = repository.complete_request_terminal(
            request_id=shard_payload.request_id,
            job_status=job.status,
            error_code=job.error_code,
        )
        schedule_analysis_run_shards(
            session,
            run_id=run_id,
            max_in_flight=runtime.settings.analysis_run_max_in_flight_jobs,
            request_id=job.request_id,
        )
        repository.refresh_run(run_id)

    return callback


def analysis_job_terminal_callback(session: Session, job: JobRecord) -> None:
    """兼容旧测试 Registry：只收敛 Shard，不继续扩大调度窗口。"""

    payload = ContentAnalysisJobPayload.model_validate(job.payload)
    PostgresAnalysisRepository(session).complete_request_terminal(
        request_id=payload.request_id,
        job_status=job.status,
        error_code=job.error_code,
    )


def _progress_after_batch(stats: dict[str, int], *, processed_count: int) -> int:
    completed_before = stats["succeeded"] + stats["failed"] + stats["stale"]
    total = completed_before + stats["pending"]
    completed_after = completed_before + min(max(processed_count, 0), stats["pending"])
    return min(99, int(completed_after * 100 / max(total, 1)))


def _matches_frozen_configuration(
    work_item: AnalysisWorkItem,
    service: ContentLabelingService,
) -> bool:
    """防止部署或重启后的配置漂移污染已经冻结身份的 Run。"""

    if not work_item.configuration_enforced:
        return True
    _, generation_config_hash = current_analysis_generation_config()
    return (
        work_item.configuration_identity == service.configuration_identity
        and work_item.generation_config_hash == generation_config_hash
    )


__all__ = [
    "PostgresContentAnalysisJobExecutor",
    "PostgresContentAnalysisPlanJobExecutor",
    "analysis_job_terminal_callback",
    "create_analysis_job_terminal_callback",
    "schedule_analysis_run_shards",
]
