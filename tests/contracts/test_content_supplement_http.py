from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from aima_ugc.contracts.http import ContentSupplementStatusResponse


def test_content_supplement_status_exposes_business_state_without_provider_details() -> None:
    status = ContentSupplementStatusResponse(
        run_id=uuid4(),
        status="failed",
        stop_reason="provider_http_500",
        updated_at=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
    )

    payload = status.model_dump(mode="json")
    assert payload["status"] == "failed"
    assert payload["stop_reason"] == "provider_http_500"
    assert "provider" not in payload
    assert "error_detail" not in payload
