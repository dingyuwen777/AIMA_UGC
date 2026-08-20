"""统一 Excel Export Job 使用现有 Job Registry。"""

from uuid import uuid4

from aima_ugc.modules.reporting.data_export_job import (
    DATA_EXPORT_JOB_MAX_ATTEMPTS,
    DATA_EXPORT_JOB_TIMEOUT_SECONDS,
    DATA_EXPORT_JOB_TYPE,
    DataExportJobHandler,
    DataExportJobPayload,
    register_data_export_job,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRegistry


class _Executor:
    def execute(self, *, payload, fence, context):  # type: ignore[no-untyped-def]
        return JobHandlerResult.succeeded(
            {
                "export_id": str(payload.export_id),
                "artifact_id": str(uuid4()),
                "content_count": 2,
                "analyzed_count": 1,
                "unanalyzed_count": 1,
                "comment_count": 0,
            }
        )


class _Context:
    fence = JobExecutionFence(job_id=uuid4(), lease_token="lease")

    def cancel_requested(self) -> bool:
        return False


def test_data_export_job_contract_and_registration() -> None:
    registry = JobRegistry()
    register_data_export_job(registry, DataExportJobHandler(_Executor()))
    definition = registry.get(DATA_EXPORT_JOB_TYPE)
    payload = DataExportJobPayload(export_id=uuid4())

    result = definition.handler(payload, _Context())

    assert DATA_EXPORT_JOB_TIMEOUT_SECONDS == 1800
    assert DATA_EXPORT_JOB_MAX_ATTEMPTS == 3
    assert definition.retry_on_timeout is True
    assert result.outcome == "succeeded"
    assert result.result is not None
    assert result.result["content_count"] == 2
    assert result.result["unanalyzed_count"] == 1
