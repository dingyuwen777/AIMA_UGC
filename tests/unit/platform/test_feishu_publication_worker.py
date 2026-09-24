"""飞书发布 Worker 的 Artifact 读取、委托和错误分类回归。"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.adapters.feishu import FeishuAPIError, FeishuApiError
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
        "publish_all_report_to_feishu",
        lambda **kwargs: (
            calls.append((kwargs["input_path"], kwargs["previous_input_path"]))
            or SimpleNamespace(
                report=SimpleNamespace(content_rows=3, label_rows=2, comment_rows=1),
                publication=None,
                representative_sync=None,
                representative_count=2,
                dry_run=True,
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
        "dry_run": True,
        "native_document_url": None,
        "editable_chart_sheet_url": None,
        "representative_table_url": None,
        "representative_table_name": None,
        "representative_count": 2,
        "representative_created_count": 0,
        "representative_updated_count": 0,
        "representative_verified_count": 0,
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


def test_report_worker_logs_specific_feishu_endpoint_and_error_details(
    executor: PostgresFeishuPublicationJobExecutor,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(worker_module, "validate_xlsx_archive", lambda path: None)
    monkeypatch.setattr(
        worker_module,
        "publish_all_report_to_feishu",
        lambda **kwargs: (_ for _ in ()).throw(
            FeishuApiError(
                "在飞书原生文档中添加报告交付入口失败：HTTP 403, code=99991672, msg=Access denied",
                status_code=403,
                api_code=99991672,
                http_method="POST",
                endpoint="/open-apis/docx/v1/documents/doc/blocks/doc/children",
            )
        ),
    )
    payload = FeishuReportPublicationJobPayload(
        input_artifact_id=uuid4(),
        previous_input_artifact_id=uuid4(),
        input_filename="current.xlsx",
        previous_input_filename="previous.xlsx",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 9),
    )
    context = _Context()

    with caplog.at_level(logging.ERROR, logger=worker_module.logger.name):
        result = executor.execute_report(payload=payload, fence=context.fence, context=context)

    assert result.outcome == "failed"
    assert result.error_code == "feishu_report_api_failed"
    record = next(record for record in caplog.records if record.event == "feishu.api_error")
    assert record.job_id == str(context.fence.job_id)
    assert record.publication_kind == "report"
    assert record.http_method == "POST"
    assert record.endpoint == "/open-apis/docx/v1/documents/doc/blocks/doc/children"
    assert record.status_code == 403
    assert record.api_code == 99991672
    assert "添加报告交付入口" in record.error_message
    assert "Access denied" in record.error_message
