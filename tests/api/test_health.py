import asyncio

from aima_ugc.entrypoints.api_main import create_app
from httpx import ASGITransport, AsyncClient, Response


async def request_health(path: str) -> Response:
    """通过真实 ASGI 调用链请求健康检查。"""
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_health_live() -> None:
    response = asyncio.run(request_health("/health/live"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_exists_and_fails_closed_without_dependencies() -> None:
    response = asyncio.run(request_health("/health/ready"))

    assert response.status_code == 503
    assert response.json()["status"] == "error"
