"""飞书发布 Worker 的 Artifact 读取、委托和错误分类回归。"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.adapters.feishu import FeishuAPIError
from aima_ugc.bootstrap import feishu_publication_worker as worker_module
from aima_ugc.bootstrap.feishu_publication_worker import (
    PostgresFeishuPublicationJobExecutor,
)
from aima_ugc.modules.administration.feishu_publication_jobs import (
    FeishuReportPublicationJobPayload,
    FeishuRepresentativeSelectionJobPayload,
)
from aima_ugc.platform.jobs import JobExecutionFence


class _Context:
    def __init__(self) -> None:
        self.fence = JobExecutionFence(job_id=uuid4(), lease_token="token")
        self.progresses: list[int] = []

    def heartbeat(self, *, progress: int) -> None:
        self.progresses.append(progress)

    def cancel_requested(self) -> bool:
        return False


@pytest.fixture
def executor(tmp_path: Path) -> PostgresFeishuPublicationJobExecutor:
    runtime = SimpleNamespace(
        settings=SimpleNamespace(data_dir=tmp_path, llm_base_url="", llm_model=""),
        database=SimpleNamespace(),
        artifact_store=SimpleNamespace(backend_name="local"),
    )
    instance = PostgresFeishuPublicationJobExecutor(runtime)  # type: ignore[arg-type]

    def materialize(artifact_id, destination):  # type: ignore[no-untyped-def]
        del artifact_id
        destination.write_bytes(b"xlsx")
        return destination

    instance._materialize_artifact = materialize  # type: ignore[method-assign]
    return instance


def test_report_worker_reads_both_artifacts_and_returns_safe_result(
    executor: PostgresFeishuPublicationJobExecutor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, Path]] = []
    monkeypatch.setattr(worker_module, "validate_xlsx_archive", lambda path: None)
    monkeypatch.setattr(
        worker_module,
        "publish_report_to_feishu",
        lambda **kwargs: (
            calls.append((kwargs["input_path"], kwargs["previous_input_path"]))
            or SimpleNamespace(
                report=SimpleNamespace(content_rows=3, label_rows=2, comment_rows=1),
                publication=SimpleNamespace(
                    native_document_url="https://feishu.example/doc",
                    editable_chart_sheet_url=None,
                ),
            )
        ),
    )
    context = _Context()
    payload = FeishuReportPublicationJobPayload(
        input_artifact_id=uuid4(),
        previous_input_artifact_id=uuid4(),
        input_filename="current.xlsx",
        previous_input_filename="previous.xlsx",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 9),
    )

    result = executor.execute_report(payload=payload, fence=context.fence, context=context)

    assert result.outcome == "succeeded"
    assert result.result == {
        "kind": "report",
        "native_document_url": "https://feishu.example/doc",
        "editable_chart_sheet_url": None,
        "content_rows": 3,
        "label_rows": 2,
        "comment_rows": 1,
        "start_date": "2026-09-01",
        "end_date": "2026-09-09",
    }
    assert len(calls) == 1
    assert calls[0][0].name == "current.xlsx"
    assert calls[0][1].name == "previous.xlsx"


def test_representative_worker_delegates_and_maps_retryable_feishu_error(
    executor: PostgresFeishuPublicationJobExecutor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_module, "validate_xlsx_archive", lambda path: None)
    monkeypatch.setattr(
        worker_module,
        "publish_representative_selection_to_feishu",
        lambda **kwargs: SimpleNamespace(
            target_table_id="tbl-new",
            target_table_name="代表性内容",
            created_count=4,
            updated_count=0,
            verified_count=4,
            verification_errors=(),
        ),
    )
    context = _Context()
    payload = FeishuRepresentativeSelectionJobPayload(
        input_artifact_id=uuid4(),
        input_filename="labeled.xlsx",
    )

    result = executor.execute_representative_selection(
        payload=payload,
        fence=context.fence,
        context=context,
    )

    assert result.outcome == "succeeded"
    assert result.result == {
        "kind": "representative_selection",
        "target_table_id": "tbl-new",
        "target_table_name": "代表性内容",
        "created_count": 4,
        "updated_count": 0,
        "verified_count": 4,
        "verification_errors": [],
    }

    monkeypatch.setattr(
        worker_module,
        "publish_representative_selection_to_feishu",
        lambda **kwargs: (_ for _ in ()).throw(FeishuAPIError("temporary", retryable=True)),
    )
    retry = executor.execute_representative_selection(
        payload=payload,
        fence=context.fence,
        context=_Context(),
    )
    assert retry.outcome == "retry"
    assert retry.error_code == "feishu_bitable_api_retry"
