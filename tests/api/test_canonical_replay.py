from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.http import (
    CanonicalReplayCreatedResponse,
    CanonicalReplayCreateRequest,
    CanonicalReplayRunResponse,
    CanonicalReplayStatsResponse,
    JobStatusResponse,
)
from aima_ugc.modules.identity import DevelopmentIdentityResolver
from aima_ugc.modules.ingestion.canonical_replay_http import (
    CanonicalReplayConflict,
    CanonicalReplayInputInvalid,
    CanonicalReplayResourceNotFound,
)
from fastapi.testclient import TestClient

_RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
_JOB_ID = UUID("22222222-2222-4222-8222-222222222222")
_ARTIFACT_ID = UUID("33333333-3333-4333-8333-333333333333")
_BRAND_ID = UUID("44444444-4444-4444-8444-444444444444")
_NOW = datetime(2026, 9, 11, 8, 0, tzinfo=UTC)


def _run_response(*, status: str = "running") -> CanonicalReplayRunResponse:
    return CanonicalReplayRunResponse(
        id=_RUN_ID,
        artifact_ids=(_ARTIFACT_ID,),
        filter_scope="selected",
        brand_ids=(_BRAND_ID,),
        catalog_version=9,
        artifact_count=1,
        checkpoint_artifact_ordinal=0,
        checkpoint_row_number=3,
        batch_size=100,
        stats=CanonicalReplayStatsResponse(
            rows_seen=3,
            rows_matched=2,
            rows_filtered_out=1,
            duplicates_removed=0,
            rows_ingested=1,
            existing_convergence=1,
        ),
        job=JobStatusResponse(
            id=_JOB_ID,
            job_type="ingestion.canonical-replay.v1",
            status=status,  # type: ignore[arg-type]
            attempt=1,
            max_attempts=10,
            progress=25,
            created_at=_NOW,
            started_at=_NOW,
        ),
        created_by="replay-admin",
        created_at=_NOW,
        updated_at=_NOW,
    )


class _ReplayService:
    def __init__(self) -> None:
        self.created: tuple[CanonicalReplayCreateRequest, str, str] | None = None
        self.cancelled: tuple[UUID, str, str] | None = None
        self.error: Exception | None = None

    def create_replay(
        self,
        body: CanonicalReplayCreateRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayCreatedResponse:
        if self.error is not None:
            raise self.error
        self.created = (body, actor_ref, request_id)
        return CanonicalReplayCreatedResponse(run_id=_RUN_ID, job_id=_JOB_ID, status="queued")

    def get_replay(self, run_id: UUID) -> CanonicalReplayRunResponse:
        if self.error is not None:
            raise self.error
        assert run_id == _RUN_ID
        return _run_response()

    def cancel_replay(
        self,
        run_id: UUID,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayRunResponse:
        if self.error is not None:
            raise self.error
        self.cancelled = (run_id, actor_ref, request_id)
        return _run_response(status="cancelled")


def _body() -> dict[str, object]:
    return {
        "idempotency_key": " replay-stage4 ",
        "artifact_ids": [str(_ARTIFACT_ID)],
        "brand_ids": [str(_BRAND_ID)],
        "batch_size": 100,
    }


def test_admin_can_create_query_and_cancel_replay() -> None:
    service = _ReplayService()
    client = TestClient(
        create_app(
            canonical_replay_service=service,
            identity_resolver=DevelopmentIdentityResolver(principal_id="replay-admin"),
        )
    )

    created = client.post("/api/v1/canonical-replays", json=_body())
    queried = client.get(f"/api/v1/canonical-replays/{_RUN_ID}")
    cancelled = client.post(f"/api/v1/canonical-replays/{_RUN_ID}/cancel")

    assert created.status_code == 202
    assert created.json() == {
        "run_id": str(_RUN_ID),
        "job_id": str(_JOB_ID),
        "status": "queued",
    }
    assert queried.status_code == 200
    assert queried.json()["stats"] == {
        "rows_seen": 3,
        "rows_matched": 2,
        "rows_filtered_out": 1,
        "duplicates_removed": 0,
        "rows_ingested": 1,
        "existing_convergence": 1,
        "invalid_artifact_rows": 0,
    }
    assert cancelled.status_code == 200
    assert cancelled.json()["job"]["status"] == "cancelled"
    assert service.created is not None
    assert service.created[0].idempotency_key == "replay-stage4"
    assert service.created[1] == "replay-admin"
    assert service.created[2] == created.headers["x-request-id"]
    assert service.cancelled == (
        _RUN_ID,
        "replay-admin",
        cancelled.headers["x-request-id"],
    )


def test_replay_routes_require_administrator_before_calling_service() -> None:
    service = _ReplayService()
    client = TestClient(
        create_app(
            canonical_replay_service=service,
            identity_resolver=DevelopmentIdentityResolver(role="user"),
        ),
        raise_server_exceptions=False,
    )

    responses = (
        client.post("/api/v1/canonical-replays", json=_body()),
        client.get(f"/api/v1/canonical-replays/{_RUN_ID}"),
        client.post(f"/api/v1/canonical-replays/{_RUN_ID}/cancel"),
    )

    assert all(response.status_code == 403 for response in responses)
    assert all(
        response.json()["errors"][0]["code"] == "administrator_required" for response in responses
    )
    assert service.created is None
    assert service.cancelled is None


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (
            CanonicalReplayResourceNotFound("secret-internal-detail"),
            404,
            "canonical_replay_not_found",
        ),
        (
            CanonicalReplayConflict("secret-internal-detail"),
            409,
            "canonical_replay_conflict",
        ),
        (
            CanonicalReplayInputInvalid("secret-internal-detail"),
            422,
            "canonical_replay_input_invalid",
        ),
    ],
)
def test_replay_domain_errors_use_safe_stable_http_contract(
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    service = _ReplayService()
    service.error = error
    response = TestClient(
        create_app(canonical_replay_service=service),
        raise_server_exceptions=False,
    ).post("/api/v1/canonical-replays", json=_body())

    assert response.status_code == status_code
    assert response.json()["errors"][0]["code"] == code
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert str(error) not in response.text


@pytest.mark.parametrize(
    "body",
    [
        {**_body(), "artifact_ids": [str(_ARTIFACT_ID), str(_ARTIFACT_ID)]},
        {**_body(), "brand_ids": [str(_BRAND_ID), str(_BRAND_ID)]},
        {**_body(), "idempotency_key": "   "},
    ],
)
def test_replay_request_rejects_ambiguous_selection_before_service(body: dict[str, object]) -> None:
    service = _ReplayService()
    response = TestClient(create_app(canonical_replay_service=service)).post(
        "/api/v1/canonical-replays",
        json=body,
    )

    assert response.status_code == 422
    assert service.created is None
