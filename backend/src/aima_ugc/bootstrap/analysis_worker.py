"""Stage 8D Content Analysis Job 的 PostgreSQL/LLM 正式执行器。"""

from __future__ import annotations

import logging
from collections.abc import Callable

from aima_ugc.adapters.llm import (
    OpenAICompatibleContentLabelingLLM,
    OpenAICompatibleLLMError,
    load_llm_pricing,
)
from aima_ugc.adapters.llm.request_audit import LLMHTTPRequestAudit
from aima_ugc.adapters.persistence.postgres.analysis import PostgresAnalysisRepository
from aima_ugc.contracts.analysis import ContentLabelAnalysisV3
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingService,
    FrozenPromptTaxonomyLoader,
    PromptTaxonomyLoader,
)
from aima_ugc.modules.analysis.content_analysis_job import ContentAnalysisJobPayload
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, LeaseLostError
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.security import SecretFileError, read_secret_file

from .runtime import PlatformRuntime

_LOGGER = logging.getLogger("aima_ugc")


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
        self._service_factory = service_factory or self._default_service

    def execute(
        self,
        *,
        payload: ContentAnalysisJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        try:
            service, close_service = self._service_factory()
        except OSError, SecretFileError, ValueError:
            return JobHandlerResult.failed("analysis_configuration_unavailable")

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
                    finally:
                        session.close()

                context.heartbeat(progress=_progress_after_batch(stats, processed_count=len(work)))
        finally:
            close_service()

    def _default_service(self) -> tuple[ContentLabelingService, Callable[[], None]]:
        settings = self._runtime.settings
        if settings.llm_base_url is None or settings.llm_model is None:
            raise ValueError("正式 Analysis 缺少 LLM base URL 或 model")
        api_key = read_secret_file(
            settings.llm_api_key_file,
            root=settings.secret_dir,
        )
        taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
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


def _progress_after_batch(stats: dict[str, int], *, processed_count: int) -> int:
    completed_before = stats["succeeded"] + stats["failed"] + stats["stale"]
    total = completed_before + stats["pending"]
    completed_after = completed_before + min(max(processed_count, 0), stats["pending"])
    return min(99, int(completed_after * 100 / max(total, 1)))


__all__ = ["PostgresContentAnalysisJobExecutor"]
