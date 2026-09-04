"""显式 Analysis Job 复用正式 Job Registry。"""

from uuid import uuid4

from aima_ugc.bootstrap.analysis_concurrent_worker import _progress_after_processed
from aima_ugc.modules.analysis.content_analysis_job import (
    CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
    CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
    CONTENT_ANALYSIS_JOB_TYPE,
    ContentAnalysisJobHandler,
    ContentAnalysisJobPayload,
    register_content_analysis_job,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRegistry


class _Executor:
    def execute(self, *, payload, fence, context):  # type: ignore[no-untyped-def]
        return JobHandlerResult.succeeded(
            {"request_id": str(payload.request_id), "succeeded": 2, "failed": 0, "stale": 0}
        )


class _Context:
    fence = JobExecutionFence(job_id=uuid4(), lease_token="lease")

    def cancel_requested(self) -> bool:
        return False


def test_content_analysis_job_contract_and_registration() -> None:
    registry = JobRegistry()
    register_content_analysis_job(registry, ContentAnalysisJobHandler(_Executor()))
    definition = registry.get(CONTENT_ANALYSIS_JOB_TYPE)
    payload = ContentAnalysisJobPayload(request_id=uuid4())

    result = definition.handler(payload, _Context())

    assert CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS == 1800
    assert CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS == 3
    assert definition.retry_on_timeout is True
    assert result.outcome == "succeeded"
    assert result.result is not None
    assert result.result["request_id"] == str(payload.request_id)


def test_analysis_batch_progress_does_not_count_the_current_batch_twice() -> None:
    assert (
        _progress_after_processed(
            {"pending": 2, "succeeded": 0, "failed": 0, "stale": 0},
            processed_count=2,
        )
        == 99
    )
