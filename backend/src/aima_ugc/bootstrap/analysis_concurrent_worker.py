"""Provider 驱动的正式 Analysis 有界并发执行器。"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Event
from time import monotonic
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
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
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
from aima_ugc.modules.analysis.content_labeling import ContentLabelingStopped
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
_ANALYSIS_FLUSH_SECONDS = 1.0
_ANALYSIS_CONTROL_SECONDS = 0.25
_REQUEST_CONTEXT: ContextVar[dict[str, str] | None] = ContextVar(
    "analysis_request_context",
    default=None,
)


@dataclass(frozen=True, slots=True)
class _AnalysisServiceRuntime:
    """一个 Analysis Shard 冻结后的 LLM 执行资源与容量。"""

    service: ContentLabelingService
    close: Callable[[], None]
    validation_retries: int
    max_concurrency: int
    metrics: Callable[[], dict[str, int]] | None = None


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
        """持续补充一个 Shard 的请求；独立轮询控制状态并按数量或时间提交结果。"""

        started = monotonic()
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        try:
            execution = self._create_service_runtime(payload.run_id)
        except OSError, SecretFileError, ValueError:
            return JobHandlerResult.failed("analysis_configuration_unavailable")

        setup_seconds = monotonic() - started
        stop_event = Event()
        cancelled = False
        last_control = 0.0
        buffered_at = 0.0
        database_seconds = 0.0
        persisted_count = 0
        remaining_work_count = 0
        scan_exhausted = False
        peak_in_flight: int | None = None
        fatal_error: OpenAICompatibleLLMError | None = None
        persistence_buffer: list[
            ConcurrentTaskOutcome[AnalysisWorkItem, ContentLabelingBatchResult]
        ] = []

        def check_control(*, force: bool = False) -> bool:
            """即使所有模型都在等待，也能发现取消、Lease 丢失和 Attempt Deadline。"""

            nonlocal last_control, cancelled, database_seconds
            now = monotonic()
            if not cancelled and (force or now - last_control >= _ANALYSIS_CONTROL_SECONDS):
                last_control = now
                before = monotonic()
                try:
                    if context.cancel_requested():
                        cancelled = True
                        stop_event.set()
                finally:
                    database_seconds += monotonic() - before
            return cancelled

        def flush(*, force: bool = False) -> None:
            """只提交已完成结果，不等待慢请求；进度来自提交后的数据库事实。"""

            nonlocal buffered_at, database_seconds, persisted_count
            check_control()
            if cancelled:
                persistence_buffer.clear()
                return
            if not persistence_buffer or (
                not force
                and len(persistence_buffer) < _ANALYSIS_DB_WRITE_BATCH_SIZE
                and monotonic() - buffered_at < _ANALYSIS_FLUSH_SECONDS
                and not (scan_exhausted and remaining_work_count <= execution.max_concurrency)
            ):
                return
            if check_control(force=True):
                persistence_buffer.clear()
                return
            chunk = tuple(persistence_buffer)
            before = monotonic()
            self._persist_outcomes(fence=fence, outcomes=chunk)
            persisted_count += len(chunk)
            persistence_buffer.clear()
            stats = self._request_stats(payload.request_id)
            context.heartbeat(progress=_progress_after_processed(stats, processed_count=0))
            database_seconds += monotonic() - before

        def tick() -> None:
            check_control()
            flush()

        def work_items() -> Iterator[AnalysisWorkItem]:
            """沿冻结 ordinal 持续翻页，空有效页不等于扫描结束。"""

            nonlocal database_seconds, remaining_work_count, scan_exhausted
            cursor = -1
            while not stop_event.is_set():
                check_control(force=True)
                if stop_event.is_set():
                    return
                before = monotonic()
                session = self._runtime.database.new_session()
                try:
                    with session.begin():
                        PostgresJobRepository(session).lock_current_execution(fence)
                        repository = PostgresAnalysisRepository(session)
                        page = repository.load_pending_page(
                            payload.request_id,
                            limit=_work_window_size(execution.max_concurrency),
                            after_ordinal=cursor,
                        )
                        if page.items:
                            repository.mark_run_running(page.items[0].analysis_run_id)
                finally:
                    session.close()
                    database_seconds += monotonic() - before
                cursor = page.last_ordinal
                remaining_work_count += len(page.items)
                scan_exhausted = page.exhausted
                for work_item in page.items:
                    if not _matches_frozen_configuration(work_item, execution.service):
                        raise AnalysisRunConfigurationChanged
                    yield work_item
                if page.exhausted:
                    return
                tick()

        def label_one(work_item: AnalysisWorkItem) -> ContentLabelingBatchResult:
            """保持单内容请求和原有 Validator；停止信号同时约束所有重试层。"""

            token = _REQUEST_CONTEXT.set(
                {
                    "run_id": str(payload.run_id),
                    "job_id": str(fence.job_id),
                    "request_id": str(payload.request_id),
                    "content_id": str(work_item.content_id),
                }
            )
            try:
                batch = execution.service.label_contents(
                    [work_item.content],
                    max_validation_retries=execution.validation_retries,
                    stop_event=stop_event,
                )
            except OpenAICompatibleLLMError as exc:
                if _is_systemic_error(exc):
                    stop_event.set()
                raise
            finally:
                _REQUEST_CONTEXT.reset(token)
            if len(batch.items) != 1 or batch.items[0].item_no != 1:
                raise RuntimeError("正式单条 Analysis 必须且只能返回 item_no=1")
            return batch

        def persist_completed(
            outcomes: Sequence[ConcurrentTaskOutcome[AnalysisWorkItem, ContentLabelingBatchResult]],
        ) -> None:
            """取消不写成内容失败；系统错误停止补充，保留同批有效结果。"""

            nonlocal buffered_at, fatal_error, remaining_work_count
            # 小任务和大任务尾部无需等待凑批；只计尚未完成的冻结工作项。
            remaining_work_count -= len(outcomes)
            unexpected_error: BaseException | None = None
            for outcome in outcomes:
                error = outcome.error
                if isinstance(error, ContentLabelingStopped):
                    continue
                if isinstance(error, OpenAICompatibleLLMError) and _is_systemic_error(error):
                    fatal_error = fatal_error or error
                    stop_event.set()
                    continue
                if error is not None and not isinstance(error, OpenAICompatibleLLMError):
                    unexpected_error = unexpected_error or error
                    continue
                if not persistence_buffer:
                    buffered_at = monotonic()
                persistence_buffer.append(outcome)
            flush(force=unexpected_error is not None)
            if unexpected_error is not None:
                raise unexpected_error

        try:
            summary = run_bounded_concurrently(
                work_items(),
                task=label_one,
                max_concurrency=execution.max_concurrency,
                on_completed=persist_completed,
                fail_fast=False,
                stop_requested=stop_event.is_set,
                request_stop=stop_event.set,
                on_tick=tick,
            )
            peak_in_flight = summary.peak_in_flight
            check_control(force=True)
            if cancelled:
                return JobHandlerResult.cancelled()
            flush(force=True)
            if fatal_error is not None:
                return JobHandlerResult.failed(f"llm_{fatal_error.error_code}")
            before = monotonic()
            final_stats = self._request_stats(payload.request_id)
            database_seconds += monotonic() - before
            if final_stats["pending"]:
                raise RuntimeError("Analysis 扫描结束后仍存在 pending 条目")
            return JobHandlerResult.succeeded(
                {
                    "request_id": str(payload.request_id),
                    "succeeded": final_stats["succeeded"],
                    "failed": final_stats["failed"],
                    "stale": final_stats["stale"],
                }
            )
        except AnalysisRunConfigurationChanged:
            flush(force=True)
            return JobHandlerResult.failed("analysis_run_configuration_changed")
        except LeaseLostError:
            # 取消与提交可能竞争；只有仍持有执行身份且明确取消，才能报告取消。
            if context.cancel_requested():
                return JobHandlerResult.cancelled()
            raise
        except BaseException as error:
            # 已收割的合法结果应保留供接管恢复；提交失败也不得掩盖原始异常。
            try:
                flush(force=True)
            except BaseException as cleanup_error:
                raise error from cleanup_error
            raise
        finally:
            stop_event.set()
            execution.close()
            log_event(
                self._runtime.logger,
                logging.INFO,
                "analysis.execution_completed",
                "Analysis 执行收尾。",
                job_id=str(fence.job_id),
                run_id=str(payload.run_id),
                request_id=str(payload.request_id),
                elapsed_ms=round((monotonic() - started) * 1000),
                setup_ms=round(setup_seconds * 1000),
                database_ms=round(database_seconds * 1000),
                persisted_count=persisted_count,
                scheduler_peak_in_flight=peak_in_flight,
                cancelled=cancelled,
                **(execution.metrics() if execution.metrics is not None else {}),
            )

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
        rate_limited: RateLimitedContentLabelingLLM | None = None
        if max_rps is not None:
            rate_limited = RateLimitedContentLabelingLLM(inner=llm, max_rps=max_rps)
            llm = rate_limited
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
            metrics=lambda: {
                **adapter.request_metrics(),
                **retrying_llm.request_metrics(),
                **(rate_limited.request_metrics() if rate_limited is not None else {}),
            },
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
            logical_request_id=audit.logical_request_id,
            http_request_id=audit.http_request_id,
            elapsed_ms=round((audit.completed_at - audit.started_at).total_seconds() * 1000),
            **(_REQUEST_CONTEXT.get() or {}),
        )


def _is_systemic_error(error: OpenAICompatibleLLMError) -> bool:
    """认证、额度、权限、地址或模型不存在影响整批，不继续逐条放大。"""

    return error.status_code in {401, 402, 403, 404}


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
