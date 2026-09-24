"""失败收敛时仍按当前 Worker 容量补充历史 Job。"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from aima_ugc.bootstrap import historical_import_worker as worker_module
from aima_ugc.modules.ingestion.historical_jobs import HISTORICAL_SNAPSHOT_JOB_TYPE
from aima_ugc.platform.capacity import ResourceSnapshot


def test_failed_snapshot_refills_using_current_worker_budget(monkeypatch) -> None:
    campaign_id = uuid4()
    item_id = uuid4()
    scheduled: list[int] = []

    class FakeRepository:
        def __init__(self, session: object) -> None:
            del session

        def get_item(self, selected_id: object, *, for_update: bool) -> dict[str, object]:
            assert selected_id == item_id and for_update
            return {"campaign_id": campaign_id}

        def fail_item(self, selected_id: object, *, error_code: str) -> None:
            assert selected_id == item_id and error_code == "source_changed"

        def get_campaign(self, selected_id: object) -> dict[str, object]:
            assert selected_id == campaign_id
            return {"status": "snapshotting", "profile_snapshot": {"max_in_flight_jobs": 1}}

        def schedule_snapshot_jobs(self, selected_id: object, *, max_in_flight: int) -> None:
            assert selected_id == campaign_id
            scheduled.append(max_in_flight)

        def finalize_preflight(self, selected_id: object) -> None:
            assert selected_id == campaign_id

    monkeypatch.setattr(worker_module, "PostgresHistoricalImportRepository", FakeRepository)
    monkeypatch.setattr(
        worker_module,
        "detect_resources",
        lambda: ResourceSnapshot(4.8, 12 * 1024**3, 11 * 1024**3, "cgroup_v2"),
    )
    job = SimpleNamespace(
        status="failed",
        job_type=HISTORICAL_SNAPSHOT_JOB_TYPE,
        payload={"campaign_item_id": str(item_id)},
        error_code="source_changed",
    )

    worker_module.historical_job_terminal_callback(object(), job)  # type: ignore[arg-type]

    assert scheduled == [3]
