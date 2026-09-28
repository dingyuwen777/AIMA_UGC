"""管理员飞书发布 API 的权限、multipart 形状和 Contract 回归。"""

from __future__ import annotations

from io import BytesIO
from typing import Literal
from uuid import UUID, uuid4

from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.feishu_publication import (
    FeishuPublicationCreatedResponse,
    FeishuPublicationJobResponse,
)
from aima_ugc.modules.identity import DevelopmentIdentityResolver
from fastapi.testclient import TestClient


class _RecordingFeishuPublicationService:
    def __init__(self) -> None:
        self.report_calls: list[dict[str, object]] = []
        self.selection_calls: list[dict[str, object]] = []
        self.job_id = uuid4()

    def create_report_publication(self, **kwargs: object) -> FeishuPublicationCreatedResponse:
        self.report_calls.append(kwargs)
        return FeishuPublicationCreatedResponse(job_id=self.job_id, kind="report")

    def create_representative_selection(
        self,
        **kwargs: object,
    ) -> FeishuPublicationCreatedResponse:
        self.selection_calls.append(kwargs)
        return FeishuPublicationCreatedResponse(
            job_id=self.job_id,
            kind="representative_selection",
        )

    def get_job(self, job_id: UUID) -> FeishuPublicationJobResponse:
        raise AssertionError(f"unexpected job query: {job_id}")


def _client(
    service: _RecordingFeishuPublicationService,
    *,
    role: Literal["administrator", "user"] = "administrator",
) -> TestClient:
    return TestClient(
        create_app(
            feishu_publication_service=service,  # type: ignore[arg-type]
            identity_resolver=DevelopmentIdentityResolver(role=role),
        ),
        raise_server_exceptions=False,
    )


def test_report_publication_forwards_two_files_and_required_date_range() -> None:
    service = _RecordingFeishuPublicationService()
    client = _client(service)

    response = client.post(
        "/api/v1/admin/feishu-report-publications",
        files={
            "current_file": (
                "current.xlsx",
                BytesIO(b"current"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            "previous_file": (
                "previous.xlsx",
                BytesIO(b"previous"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
        data={"start_date": "2026-09-01", "end_date": "2026-09-09"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "job_id": str(service.job_id),
        "kind": "report",
        "status": "queued",
    }
    assert len(service.report_calls) == 1
    assert service.report_calls[0]["current_filename"] == "current.xlsx"
    assert service.report_calls[0]["previous_filename"] == "previous.xlsx"
    assert service.report_calls[0]["start_date"] == "2026-09-01"
    assert service.report_calls[0]["end_date"] == "2026-09-09"


def test_representative_selection_accepts_one_file() -> None:
    service = _RecordingFeishuPublicationService()
    client = _client(service)

    response = client.post(
        "/api/v1/admin/feishu-representative-selections",
        files={"file": ("labeled.xlsx", b"xlsx", "application/octet-stream")},
    )

    assert response.status_code == 202
    assert response.json()["kind"] == "representative_selection"
    assert service.selection_calls[0]["filename"] == "labeled.xlsx"


def test_ordinary_user_cannot_start_either_publication() -> None:
    service = _RecordingFeishuPublicationService()
    client = _client(service, role="user")

    response = client.post(
        "/api/v1/admin/feishu-representative-selections",
        files={"file": ("labeled.xlsx", b"xlsx")},
    )

    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "administrator_required"
    assert service.selection_calls == []


def test_report_requires_both_dates() -> None:
    service = _RecordingFeishuPublicationService()
    client = _client(service)

    response = client.post(
        "/api/v1/admin/feishu-report-publications",
        files={
            "current_file": ("current.xlsx", b"current"),
            "previous_file": ("previous.xlsx", b"previous"),
        },
        data={"start_date": "2026-09-01"},
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "missing"
    assert service.report_calls == []


def test_publication_multipart_rejects_extra_fields() -> None:
    service = _RecordingFeishuPublicationService()
    client = _client(service)

    response = client.post(
        "/api/v1/admin/feishu-representative-selections",
        files={"file": ("labeled.xlsx", b"xlsx")},
        data={"unexpected": "value"},
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "value_error"
    assert service.selection_calls == []


def test_publication_routes_are_in_openapi() -> None:
    document = create_app().openapi()

    assert "/api/v1/admin/feishu-report-publications" in document["paths"]
    assert "/api/v1/admin/feishu-representative-selections" in document["paths"]
    assert "/api/v1/admin/feishu-publication-jobs/{job_id}" in document["paths"]
