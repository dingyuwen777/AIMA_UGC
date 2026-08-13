from fastapi.testclient import TestClient

from aima_ugc.entrypoints.api_main import create_app


def test_health_live() -> None:
    client = TestClient(create_app())

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
