"""Provider 驱动的正式 Analysis 有界并发执行器。"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from aima_ugc.adapters.llm import (
    OpenAICompatibleContentLabelingLLM,
    OpenAICompatibleLLMError,
    RateLimitedContentLabelingLLM,
    RetryingContentLabelingLLM,
    load_llm_pricing,
)
from aima_ugc.adapters.llm.request_audit import LLMHTTPRequestAudit
from aima_ugc.adapters.persistence.postgres.analysis import (
    AnalysisRunConfigurationChanged,
    PostgresAnalysisRepository,
)
from aima_ugc.adapters.persistence.postgres.analysis_batch import (
    AnalysisFailureWrite,
    AnalysisSuccessWrite,
    PostgresAnalysisBatchRepository,
)
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.contracts.analysis import ContentLabelAnalysisV3
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingBatchResult,
    ContentLabelingLLMPort,
    ContentLabelingService,
    FrozenPromptTaxonomyLoader,
    PromptTaxonomyLoader,
)
from aima_ugc.modules.analysis.concurrent_labeling import (
    ConcurrentTaskOutcome,
    run_bounded_concurrently,
)
from aima_ugc.modules.analysis.content_analysis_job import ContentAnalysisJobPayload
from aima_ugc.modules.analysis.persistence import AnalysisWorkItem
from aima_ugc.modules.analysis.schemes import prompt_taxonomy_from_version
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, LeaseLostError
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.security import SecretFileError, read_secret_file

from .runtime import PlatformRuntime
from .runtime_config import provider_from_safe_snapshot, resolve_provider_secret

_ANALYSIS_DB_WRITE_BATCH_SIZE = 200
_ANALYSIS_WORK_WINDOW_MULTIPLIER = 2
_ANALYSIS_MAX_WORK_WINDOW = 10_000


@dataclass(frozen=True, slots=True)
class _AnalysisServiceRuntime:
    """一个 Analysis Shard 冻结后的 LLM 执行资源与容量。"""

    service: ContentLabelingService
    close: Callable[[], None]
    validation_retries: int
    max_concurrency: int


class ConcurrentPostgresContentAnalysisJobExecutor:
    """按 Run 冻结 Provider 容量并发调用 LLM，再由调度线程批量短事务落库。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        service_factory: Callable[[], tuple[ContentLabelingService, Callable[[], None], int, int]]
        | None = None,
    ) -> None:
        """创建正式执行器；测试可注入显式 Service/并发而不复制生产调度逻辑。"""

        self._runtime = runtime
        self._service_factory = service_factory

    def execute(
        self,
        *,
        payload: ContentAnalysisJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """执行一个 Shard；Canary 成功后才放大并发，模型调用期间不持有 DB 事务。"""

        try:
            execution = self._create_service_runtime(payload.run_id)
        except OSError, SecretFileError, ValueError:
            return JobHandlerResult.failed("analysis_configuration_unavailable")

        total_stats: dict[str, int] | None = None
        processed_after_baseline = 0
        use_canary = True
        try:
            while True:
                session = self._runtime.database.new_session()
                try:
                    with session.begin():
                        repository = PostgresAnalysisRepository(session)
                        work = repository.load_pending(
                            payload.request_id,
                            limit=_work_window_size(execution.max_concurrency),
                        )
                        if total_stats is None:
                            total_stats = PostgresAnalysisBatchRepository(session).stats(
                                payload.request_id
                            )
                        if work:
                            repository.mark_run_running(work[0].analysis_run_id)
                finally:
                    session.close()

                if not work:
                    final_stats = self._request_stats(payload.request_id)
                    return JobHandlerResult.succeeded(
                        {
                            "request_id": str(payload.request_id),
                            "succeeded": final_stats["succeeded"],
                            "failed": final_stats["failed"],
                            "stale": final_stats["stale"],
                        }
                    )
                if not _matches_frozen_configuration(work[0], execution.service):
                    return JobHandlerResult.failed("analysis_run_configuration_changed")
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()

                persistence_buffer: list[
                    ConcurrentTaskOutcome[AnalysisWorkItem, ContentLabelingBatchResult]
                ] = []
                cancel_state = [False]

                def stop_requested(cancel_state: list[bool] = cancel_state) -> bool:
                    return cancel_state[0]

                def label_one(work_item: AnalysisWorkItem) -> ContentLabelingBatchResult:
                    """保持一条 Content 一次独立逻辑模型请求。"""

                    batch = execution.service.label_contents(
                        [work_item.content],
                        max_validation_retries=execution.validation_retries,
                    )
                    if len(batch.items) != 1 or batch.items[0].item_no != 1:
                        raise RuntimeError("正式单条 Analysis 必须且只能返回 item_no=1")
                    return batch

                def persist_completed(
                    outcomes: Sequence[
                        ConcurrentTaskOutcome[AnalysisWorkItem, ContentLabelingBatchResult]
                    ],
                    persistence_buffer: list[
                        ConcurrentTaskOutcome[AnalysisWorkItem, ContentLabelingBatchResult]
                    ] = persistence_buffer,
                    cancel_state: list[bool] = cancel_state,
                ) -> None:
                    """在调度线程累积完成结果，达到阈值后短事务落库并形成自然背压。"""

                    persistence_buffer.extend(outcomes)
                    while len(persistence_buffer) >= _ANALYSIS_DB_WRITE_BATCH_SIZE:
                        chunk = tuple(persistence_buffer[:_ANALYSIS_DB_WRITE_BATCH_SIZE])
                        del persistence_buffer[:_ANALYSIS_DB_WRITE_BATCH_SIZE]
                        self._persist_outcomes(fence=fence, outcomes=chunk)
                        cancel_state[0] = context.cancel_requested()

                try:
                    summary = run_bounded_concurrently(
                        work,
                        task=label_one,
                        max_concurrency=execution.max_concurrency,
                        on_completed=persist_completed,
                        canary=use_canary,
                        fail_fast=False,
                        stop_requested=stop_requested,
                    )
                except OpenAICompatibleLLMError as exc:
                    # 只有 Canary 在并发放大前抛到这里；之后单条 Transport 错误由 Outcome 隔离。
                    return (
                        JobHandlerResult.retry(f"llm_{exc.error_code}")
                        if exc.retryable
                        else JobHandlerResult.failed(f"llm_{exc.error_code}")
                    )
                except AnalysisRunConfigurationChanged:
                    return JobHandlerResult.failed("analysis_run_configuration_changed")

                use_canary = False
                if persistence_buffer:
                    self._persist_outcomes(fence=fence, outcomes=tuple(persistence_buffer))
                    persistence_buffer.clear()
                processed_after_baseline += summary.completed
                if total_stats is not None:
                    context.heartbeat(
                        progress=_progress_after_processed(
                            total_stats,
                            processed_count=processed_after_baseline,
                        )
                    )
                if summary.stopped or context.cancel_requested():
                    return JobHandlerResult.cancelled()
        finally:
            execution.close()

    def _create_service_runtime(self, analysis_run_id: UUID | None) -> _AnalysisServiceRuntime:
        """从 Run 冻结 Provider/Scheme 装配共享 HTTP Client、RPS、Transport Retry 与并发容量。"""

        if self._service_factory is not None:
            service, close, validation_retries, max_concurrency = self._service_factory()
            return _AnalysisServiceRuntime(
                service=service,
                close=close,
                validation_retries=validation_retries,
                max_concurrency=max_concurrency,
            )

        if analysis_run_id is None:
            raise ValueError("Analysis Run ID 缺失")

        settings = self._runtime.settings
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                run = PostgresAnalysisRepository(session).get_run(analysis_run_id)
                if run is None:
                    raise ValueError("Analysis Run 不存在")
                snapshot = run["runtime_config_snapshot"]
                max_rps: int | None = None
                if isinstance(snapshot, dict) and snapshot:
                    provider = provider_from_safe_snapshot(snapshot)
                    if provider.provider_kind != "llm" or provider.model is None:
                        raise ValueError("Analysis Run LLM Provider 快照不合法")
                    base_url = provider.base_url
                    model = provider.model
                    provider_name: str | None = provider.provider
                    timeout_seconds = float(provider.timeout_seconds)
                    max_concurrency = provider.max_concurrency
                    max_rps = provider.max_rps
                    validation_retries = provider.max_retries
                    api_key = resolve_provider_secret(settings, provider)
                else:
                    # 迁移前 Run 没有 Provider Snapshot，只按原 env 身份保留兼容执行。
                    if settings.llm_base_url is None or settings.llm_model is None:
                        raise ValueError("旧 Analysis Run 缺少兼容 LLM 配置")
                    base_url = settings.llm_base_url
                    model = settings.llm_model
                    provider_name = settings.llm_provider_name
                    timeout_seconds = settings.llm_timeout_seconds
                    max_concurrency = settings.llm_max_connections
                    validation_retries = settings.llm_validation_retries
                    api_key = read_secret_file(
                        settings.llm_api_key_file,
                        root=settings.external_secret_root,
                    )

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
            base_url=base_url,
            api_key=api_key,
            model=model,
            provider_name=provider_name,
            timeout_seconds=timeout_seconds,
            max_connections=max_concurrency,
            pricing_catalog=load_llm_pricing(),
            request_audit=self._record_audit,
        )
        llm: ContentLabelingLLMPort = adapter
        if max_rps is not None:
            llm = RateLimitedContentLabelingLLM(inner=llm, max_rps=max_rps)
        # Retry 包在限流层外，确保每次物理 Retry 都重新取得 RPS 时隙。
        retrying_llm = RetryingContentLabelingLLM(inner=llm)
        service = ContentLabelingService(
            prompt_loader=FrozenPromptTaxonomyLoader(taxonomy),
            llm=retrying_llm,
        )
        return _AnalysisServiceRuntime(
            service=service,
            close=adapter.close,
            validation_retries=validation_retries,
            max_concurrency=max_concurrency,
        )

    def _persist_outcomes(
        self,
        *,
        fence: JobExecutionFence,
        outcomes: Sequence[ConcurrentTaskOutcome[AnalysisWorkItem, ContentLabelingBatchResult]],
    ) -> None:
        """一个短事务提交一组已完成模型结果；单条 Validation/Transport 失败彼此隔离。"""

        if not outcomes:
            return
        successes: list[AnalysisSuccessWrite] = []
        failures: list[AnalysisFailureWrite] = []
        unexpected_error: BaseException | None = None
        for outcome in outcomes:
            if outcome.error is not None:
                if isinstance(outcome.error, OpenAICompatibleLLMError):
                    failures.append(
                        AnalysisFailureWrite(
                            work_item=outcome.item,
                            error_code=f"llm_{outcome.error.error_code}",
                        )
                    )
                    continue
                unexpected_error = unexpected_error or outcome.error
                continue
            batch = outcome.result
            if batch is None or len(batch.items) != 1:
                raise RuntimeError("正式单条 Analysis Outcome 缺少唯一结果")
            result = batch.items[0]
            if result.analysis_status == "succeeded" and isinstance(
                result.analysis, ContentLabelAnalysisV3
            ):
                successes.append(
                    AnalysisSuccessWrite(work_item=outcome.item, analysis=result.analysis)
                )
            else:
                failures.append(
                    AnalysisFailureWrite(
                        work_item=outcome.item,
                        error_code=(
                            result.validation_error_codes[0]
                            if result.validation_error_codes
                            else "validation_failed"
                        ),
                    )
                )
        if unexpected_error is not None:
            raise unexpected_error

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresAnalysisBatchRepository(session).persist_batch(
                    fence=fence,
                    successes=successes,
                    failures=failures,
                )
        except LeaseLostError:
            raise
        finally:
            session.close()

    def _request_stats(self, request_id: UUID) -> dict[str, int]:
        """在独立短事务由 PostgreSQL 聚合一个 Shard 的最终统计。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                return PostgresAnalysisBatchRepository(session).stats(request_id)
        finally:
            session.close()

    def _record_audit(self, audit: LLMHTTPRequestAudit) -> None:
        """成功物理请求降为 DEBUG；错误保留 WARNING，避免高吞吐 INFO 日志成为热路径。"""

        level = logging.DEBUG if audit.status == "completed" else logging.WARNING
        log_event(
            self._runtime.logger,
            level,
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


def _work_window_size(max_concurrency: int) -> int:
    """一次只从 PostgreSQL 拉取约两轮请求，限制内存同时避免线程池断粮。"""

    return min(max_concurrency * _ANALYSIS_WORK_WINDOW_MULTIPLIER, _ANALYSIS_MAX_WORK_WINDOW)


def _matches_frozen_configuration(
    work_item: AnalysisWorkItem,
    service: ContentLabelingService,
) -> bool:
    """旧 Request 保留兼容；新 Run 必须与冻结 Prompt/Taxonomy/Provider/Model 身份一致。"""

    if not work_item.configuration_enforced:
        return True
    return work_item.configuration_identity == service.configuration_identity


def _progress_after_processed(stats: dict[str, int], *, processed_count: int) -> int:
    """基于初始 Request 状态与本次已收割条目生成 0—99 的 Job 进度。"""

    completed_before = stats["succeeded"] + stats["failed"] + stats["stale"]
    total = completed_before + stats["pending"]
    completed_after = completed_before + min(max(processed_count, 0), stats["pending"])
    return min(99, int(completed_after * 100 / max(total, 1)))


__all__ = ["ConcurrentPostgresContentAnalysisJobExecutor"]
