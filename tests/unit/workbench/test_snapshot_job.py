"""工作台快照持久 Job 的 Payload 与 Registry 回归。"""

from datetime import date
from uuid import UUID

from aima_ugc.contracts.workbench import WorkbenchQuery
from aima_ugc.modules.workbench.jobs import (
    WORKBENCH_SNAPSHOT_JOB_PAYLOAD_VERSION,
    WORKBENCH_SNAPSHOT_JOB_TYPE,
    WorkbenchSnapshotJobHandler,
    WorkbenchSnapshotJobPayload,
    register_workbench_snapshot_job,
)
from aima_ugc.platform.jobs import JobHandlerResult
from aima_ugc.platform.jobs.registry import JobRegistry


class _Executor:
    def execute(self, *, payload, fence, context):  # type: ignore[no-untyped-def]
        return JobHandlerResult.succeeded({"module": payload.module})


def test_snapshot_job_registers_versioned_query_and_refresh_fence() -> None:
    registry = JobRegistry()
    register_workbench_snapshot_job(
        registry,
        WorkbenchSnapshotJobHandler(_Executor()),
        terminal_callback=lambda _session, _job: None,
    )
    payload = WorkbenchSnapshotJobPayload(
        module="mind",
        query_hash="a" * 64,
        query=WorkbenchQuery(date_from=date(2026, 9, 1), date_to=date(2026, 9, 30)),
        source_revision=23,
        refresh_generation=4,
        analysis_scheme_version_id=UUID("11111111-1111-4111-8111-111111111111"),
    )

    validated = registry.validate_payload(
        job_type=WORKBENCH_SNAPSHOT_JOB_TYPE,
        payload_version=WORKBENCH_SNAPSHOT_JOB_PAYLOAD_VERSION,
        payload=payload.model_dump(mode="json"),
    )

    assert isinstance(validated, WorkbenchSnapshotJobPayload)
    assert validated.source_revision == 23
    assert validated.refresh_generation == 4
    assert validated.query.date_from == date(2026, 9, 1)
