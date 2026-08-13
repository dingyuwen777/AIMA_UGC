import asyncio

from aima_ugc.entrypoints.api_main import create_app
from aima_ugc.platform.health import ReadinessReport
from httpx import ASGITransport, AsyncClient, Response


async def request_health(path: str, report: ReadinessReport | None = None) -> Response:
    """通过真实 ASGI 调用链请求健康检查。"""
    readiness_check = None if report is None else lambda: report
    transport = ASGITransport(app=create_app(readiness_check=readiness_check))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_health_live() -> None:
    response = asyncio.run(request_health("/health/live"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_fails_closed_without_details() -> None:
    response = asyncio.run(
        request_health(
            "/health/ready",
            ReadinessReport(
                database="error",
                artifact_store="ok",
                log_directory="ok",
            ),
        )
    )

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "checks": {
            "database": "error",
            "artifact_store": "ok",
            "log_directory": "ok",
        },
    }


def test_health_ready_returns_200_when_dependencies_are_ready() -> None:
    response = asyncio.run(
        request_health(
            "/health/ready",
            ReadinessReport(
                database="ok",
                artifact_store="ok",
                log_directory="ok",
            ),
        )
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "database": "ok",
            "artifact_store": "ok",
            "log_directory": "ok",
        },
    }
