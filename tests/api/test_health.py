import asyncio

from aima_ugc.entrypoints.api_main import create_app
from httpx import ASGITransport, AsyncClient, Response


async def request_health() -> Response:
    """通过真实 ASGI 调用链请求存活检查。"""
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/health/live")


def test_health_live() -> None:
    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
