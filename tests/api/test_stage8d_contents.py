"""Stage 8D 声音广场 Router/Contract/Error 集成。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.http import (
    ContentAnalysisCreatedResponse,
    ContentAnalysisResponse,
    ContentDetailResponse,
    ContentLabelPairResponse,
    ContentListItemResponse,
    ContentListResponse,
    ContentMetricsResponse,
    ContentSourceResponse,
    DataExportCreatedResponse,
    DataExportListResponse,
    DataExportResponse,
    DataExportStatsResponse,
    JobStatusResponse,
)
from aima_ugc.modules.content.content_cursor import InvalidContentCursor
from aima_ugc.modules.content.http import ContentResourceNotFound
from aima_ugc.modules.reporting.http import ArtifactDownload, DataExportNotReady
from aima_ugc.platform.health import ReadinessReport
from fastapi.testclient import TestClient


class _ContentService:
    def __init__(self) -> None:
        self.content_id = uuid4()
        self.job_id = uuid4()

    def _item(self) -> ContentListItemResponse:
        now = datetime(2026, 8, 21, tzinfo=UTC)
        return ContentListItemResponse(
            id=self.content_id,
            platform="xiaohongshu",
            external_content_id="note-1",
            content_type="note",
            title="续航体验",
            text="正文",
            published_at=now,
            last_seen_at=now,
            metrics=ContentMetricsResponse(like_count=3),
            analysis=ContentAnalysisResponse(
                status="completed",
                relevance="relevant",
                voice_type="user_voice",
                is_user_voice=True,
                sentiment="负面",
                labels=(
                    ContentLabelPairResponse(primary_label="产品体验", secondary_label="续航表现"),
                    ContentLabelPairResponse(primary_label="服务体验", secondary_label="门店服务"),
                ),
                analyzed_at=now,
            ),
            source=ContentSourceResponse(provider_name="file-import"),
        )

    def list_contents(self, query):  # type: ignore[no-untyped-def]
        if query.cursor == "tampered":
            raise InvalidContentCursor
        return ContentListResponse(items=(self._item(),), has_more=False)

    def get_content(self, content_id: UUID) -> ContentDetailResponse:
        if content_id != self.content_id:
            raise ContentResourceNotFound
        return ContentDetailResponse(**self._item().model_dump())

    def create_analysis(self, request, *, request_id):  # type: ignore[no-untyped-def]
        return ContentAnalysisCreatedResponse(
            request_id=uuid4(),
            job_id=self.job_id,
            target_count=len(request.targets.content_ids) or 1,
        )

    def get_analysis_job(self, job_id: UUID) -> JobStatusResponse:
        if job_id != self.job_id:
            raise ContentResourceNotFound
        return JobStatusResponse(
            id=job_id,
            job_type="analysis.content-label.v1",
            status="queued",
            attempt=0,
            max_attempts=3,
            progress=0,
            created_at=datetime(2026, 8, 21, tzinfo=UTC),
        )


class _ReportingService:
    def __init__(self) -> None:
        self.export_id = uuid4()
        self.job_id = uuid4()

    def create_export(self, request, *, request_id):  # type: ignore[no-untyped-def]
        return DataExportCreatedResponse(
            export_id=self.export_id,
            job_id=self.job_id,
            target_count=len(request.targets.content_ids) or 1,
        )

    def get_export(self, export_id: UUID) -> DataExportResponse:
        if export_id != self.export_id:
            raise DataExportNotReady
        return DataExportResponse(
            id=export_id,
            job=JobStatusResponse(
                id=self.job_id,
                job_type="reporting.content-export-excel.v1",
                status="succeeded",
                attempt=1,
                max_attempts=3,
                progress=100,
                created_at=datetime(2026, 8, 21, tzinfo=UTC),
            ),
            artifact_id=uuid4(),
            filename=f"aima-ugc-voice-plaza-{export_id}.xlsx",
            stats=DataExportStatsResponse(
                content_count=1,
                analyzed_count=1,
                unanalyzed_count=0,
                comment_count=0,
            ),
            created_at=datetime(2026, 8, 21, tzinfo=UTC),
        )

    def list_exports(self) -> DataExportListResponse:
        return DataExportListResponse(items=(self.get_export(self.export_id),))

    def download_export(self, export_id: UUID) -> ArtifactDownload:
        if export_id != self.export_id:
            raise DataExportNotReady
        return ArtifactDownload(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"aima-ugc-voice-plaza-{export_id}.xlsx",
            byte_size=4,
            chunks=iter((b"xlsx",)),
        )


def _client(
    service: _ContentService,
    reporting: _ReportingService | None = None,
) -> TestClient:
    return TestClient(
        create_app(
            readiness_check=lambda: ReadinessReport(
                database="ok", artifact_store="ok", log_directory="ok"
            ),
            content_service=service,
            reporting_service=reporting,
        ),
        raise_server_exceptions=False,
    )


def test_list_and_detail_return_every_ai_label_pair() -> None:
    service = _ContentService()
    client = _client(service)

    listed = client.get("/api/v1/contents")
    detailed = client.get(f"/api/v1/contents/{service.content_id}")

    assert listed.status_code == 200
    assert [
        item["secondary_label"] for item in listed.json()["items"][0]["analysis"]["labels"]
    ] == [
        "续航表现",
        "门店服务",
    ]
    assert detailed.status_code == 200
    assert len(detailed.json()["analysis"]["labels"]) == 2


def test_submit_analysis_and_query_job() -> None:
    service = _ContentService()
    client = _client(service)

    created = client.post(
        "/api/v1/content-analysis-requests",
        json={
            "targets": {
                "scope": "selected",
                "content_ids": [str(service.content_id)],
            }
        },
    )
    job = client.get(f"/api/v1/content-analysis-jobs/{service.job_id}")

    assert created.status_code == 202
    assert created.json()["target_count"] == 1
    assert job.status_code == 200
    assert job.json()["job_type"] == "analysis.content-label.v1"


def test_missing_content_uses_stable_error_and_request_id() -> None:
    client = _client(_ContentService())
    response = client.get(f"/api/v1/contents/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["type"].endswith("/content_resource_not_found")
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_invalid_content_cursor_uses_stable_error_and_request_id() -> None:
    response = _client(_ContentService()).get("/api/v1/contents?cursor=tampered")

    assert response.status_code == 400
    assert response.json()["type"].endswith("/invalid_content_cursor")
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_create_list_and_download_excel_export() -> None:
    content = _ContentService()
    reporting = _ReportingService()
    client = _client(content, reporting)

    created = client.post(
        "/api/v1/data-exports",
        json={
            "targets": {
                "scope": "selected",
                "content_ids": [str(content.content_id)],
            }
        },
    )
    listed = client.get("/api/v1/data-exports")
    downloaded = client.get(f"/api/v1/data-exports/{reporting.export_id}/download")

    assert created.status_code == 202
    assert created.json()["export_id"] == str(reporting.export_id)
    assert listed.json()["items"][0]["stats"]["analyzed_count"] == 1
    assert downloaded.status_code == 200
    assert downloaded.content == b"xlsx"
    assert downloaded.headers["x-content-type-options"] == "nosniff"
