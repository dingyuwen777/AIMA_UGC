"""声音广场人工相关性复核 HTTP Contract 回归。"""

from __future__ import annotations

from uuid import UUID

import pytest
from aima_ugc.bootstrap.api import create_app
from fastapi.testclient import TestClient

_CONTENT_ID = UUID("42345678-1234-5678-1234-567812345678")


class _ReviewContentService:
    def __init__(self) -> None:
        self.received_content_ids: tuple[UUID, ...] = ()
        self.received_decision: str | None = None
        self.received_request_id: str | None = None

    def review_relevance(self, request, *, request_id: str):  # type: ignore[no-untyped-def]
        self.received_content_ids = tuple(request.content_ids)
        self.received_decision = request.decision
        self.received_request_id = request_id
        return {
            "requested_count": len(request.content_ids),
            "changed_count": len(request.content_ids),
            "unchanged_count": 0,
        }


@pytest.mark.parametrize("decision", ["relevant", "irrelevant", "inherit_ai"])
def test_content_relevance_review_routes_all_decisions_through_one_contract(decision: str) -> None:
    service = _ReviewContentService()
    client = TestClient(
        create_app(
            content_service=service,  # type: ignore[arg-type]
            readiness_check=lambda: None,  # type: ignore[arg-type,return-value]
        )
    )

    response = client.post(
        "/api/v1/content-relevance-reviews",
        json={"content_ids": [str(_CONTENT_ID)], "decision": decision},
    )

    assert response.status_code == 200
    assert response.json() == {
        "requested_count": 1,
        "changed_count": 1,
        "unchanged_count": 0,
    }
    assert service.received_content_ids == (_CONTENT_ID,)
    assert service.received_decision == decision
    assert service.received_request_id
