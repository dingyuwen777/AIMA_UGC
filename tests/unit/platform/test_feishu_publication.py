"""飞书发布 Payload、权限输入和 Job Handler 的单元回归。"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.feishu_publication_http import (
    FeishuPublicationInvalidFile,
    FeishuPublicationInvalidRequest,
    _parse_date_range,
    _validate_filename,
)
from aima_ugc.modules.administration.feishu_publication_jobs import (
    FEISHU_REPORT_PUBLICATION_JOB_TYPE,
    FEISHU_REPRESENTATIVE_SELECTION_JOB_TYPE,
    FeishuReportPublicationJobHandler,
    FeishuReportPublicationJobPayload,
    FeishuRepresentativeSelectionJobHandler,
    FeishuRepresentativeSelectionJobPayload,
    register_feishu_publication_jobs,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRegistry


def test_report_date_range_is_required_and_uses_extended_iso_format() -> None:
    assert _parse_date_range(" 2026-09-01 ", "2026-09-09") == (
        date(2026, 9, 1),
        date(2026, 9, 9),
    )

    with pytest.raises(FeishuPublicationInvalidRequest, match="必须填写"):
        _parse_date_range("", "2026-09-09")
    with pytest.raises(FeishuPublicationInvalidRequest, match="YYYY-MM-DD"):
        _parse_date_range("20260901", "2026-09-09")
    with pytest.raises(FeishuPublicationInvalidRequest, match="不能晚于"):
        _parse_date_range("2026-09-10", "2026-09-09")


def test_publication_filename_rejects_paths_and_non_xlsx() -> None:
    assert _validate_filename("labeled.xlsx") == "labeled.xlsx"
    with pytest.raises(FeishuPublicationInvalidFile):
        _validate_filename(r"C:\tmp\labeled.xlsx")
    with pytest.raises(FeishuPublicationInvalidFile):
        _validate_filename("labeled.xls")


class _FakeExecutor:
    def __init__(self) -> None:
        self.report_payload: FeishuReportPublicationJobPayload | None = None
        self.selection_payload: FeishuRepresentativeSelectionJobPayload | None = None

    def execute_report(self, *, payload, fence, context):  # type: ignore[no-untyped-def]
        del fence, context
        self.report_payload = payload
        return JobHandlerResult.succeeded({"kind": "report"})

    def execute_representative_selection(
        self,
        *,
        payload,
        fence,
        context,
    ):  # type: ignore[no-untyped-def]
        del fence, context
        self.selection_payload = payload
        return JobHandlerResult.succeeded({"kind": "representative_selection"})


class _Context:
    def __init__(self, *, cancelled: bool = False) -> None:
        self.fence = JobExecutionFence(job_id=uuid4(), lease_token="token")
        self._cancelled = cancelled

    def heartbeat(self, *, progress: int) -> None:
        del progress

    def cancel_requested(self) -> bool:
        return self._cancelled


def test_two_handlers_delegate_independent_payloads_and_honor_cancel() -> None:
    executor = _FakeExecutor()
    report_payload = FeishuReportPublicationJobPayload(
        input_artifact_id=uuid4(),
        previous_input_artifact_id=uuid4(),
        input_filename="current.xlsx",
        previous_input_filename="previous.xlsx",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 9),
    )
    selection_payload = FeishuRepresentativeSelectionJobPayload(
        input_artifact_id=uuid4(),
        input_filename="labeled.xlsx",
    )

    report_result = FeishuReportPublicationJobHandler(executor)(
        report_payload,
        _Context(),
    )
    selection_result = FeishuRepresentativeSelectionJobHandler(executor)(
        selection_payload,
        _Context(),
    )

    assert report_result.outcome == "succeeded"
    assert selection_result.outcome == "succeeded"
    assert executor.report_payload == report_payload
    assert executor.selection_payload == selection_payload
    assert FeishuReportPublicationJobHandler(executor)(
        report_payload,
        _Context(cancelled=True),
    ).outcome == "cancelled"


def test_job_registry_contains_only_the_two_new_publication_types() -> None:
    registry = JobRegistry()
    register_feishu_publication_jobs(registry, _FakeExecutor())

    assert registry.supported_types == (
        FEISHU_REPORT_PUBLICATION_JOB_TYPE,
        FEISHU_REPRESENTATIVE_SELECTION_JOB_TYPE,
    )
