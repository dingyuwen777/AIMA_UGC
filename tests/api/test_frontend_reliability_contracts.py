"""前端可靠性 Change 的公共 HTTP Contract 回归。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.administration import AuditEventListResponse
from aima_ugc.contracts.http import (
    HistoricalCampaignResponse,
    KeywordPackCreateRequest,
    KeywordPackResponse,
)
from fastapi.testclient import TestClient


class _RecordingKeywordService:
    """只记录词包创建 Request，验证 Router 不拆分初始关键词。"""

    def __init__(self) -> None:
        self.pack_id = uuid4()
        self.created_request: KeywordPackCreateRequest | None = None

    def create_keyword_pack(
        self,
        request: KeywordPackCreateRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> KeywordPackResponse:
        assert actor_ref == "local-administrator"
        assert request_id
        self.created_request = request
        return KeywordPackResponse(
            id=self.pack_id,
            name=request.name,
            description=request.description,
            enabled=True,
            version=1,
            keywords=(),
        )


class _PagedAuditService:
    """要求 Router 显式传入分页参数，避免固定 recent slice。"""

    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:
        assert offset == 100
        assert limit == 50
        return AuditEventListResponse(items=(), total=250, offset=offset, limit=limit)


def test_keyword_pack_create_accepts_initial_keywords_in_one_request() -> None:
    service = _RecordingKeywordService()
    client = TestClient(create_app(import_service=service))  # type: ignore[arg-type]

    response = client.post(
        "/api/v1/keyword-packs",
        json={
            "name": "原子词包",
            "description": "一次事务",
            "keywords": [
                {"text": "爱玛", "priority": 100, "enabled": True},
                {"text": "电动车", "priority": 80, "enabled": True},
            ],
        },
    )

    assert response.status_code == 201
    assert service.created_request is not None
    keywords = service.created_request.keywords
    assert [item.text for item in keywords] == ["爱玛", "电动车"]
    assert [item.priority for item in keywords] == [100, 80]


def test_audit_route_forwards_offset_and_returns_total() -> None:
    client = TestClient(
        create_app(administration_service=_PagedAuditService()),  # type: ignore[arg-type]
        raise_server_exceptions=False,
    )

    response = client.get("/api/v1/audit-events", params={"offset": 100, "limit": 50})

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 250,
        "offset": 100,
        "limit": 50,
    }


def test_historical_campaign_exposes_complete_failed_chunk_fact() -> None:
    campaign = HistoricalCampaignResponse(
        id=UUID("10000000-0000-0000-0000-000000000001"),
        status="partial_failed",
        source_kind="server_path",
        ingestion_policy="historical_fill_only",
        declared_file_count=1,
        root_relative_path="history",
        recursive=True,
        discovered_file_count=1,
        ready_item_count=1,
        total_rows=10,
        progress={
            "preflight_completed_file_count": 1,
            "preflight_percent": 100,
            "migration_completed_row_count": 10,
            "migration_percent": 100,
        },
        created_at=datetime(2026, 9, 3, tzinfo=UTC),
    )

    payload = campaign.model_dump(mode="json")

    assert "failed_chunk_count" in payload
    assert payload["failed_chunk_count"] == 0
