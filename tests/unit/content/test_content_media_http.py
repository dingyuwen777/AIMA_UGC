from uuid import uuid4

from aima_ugc.bootstrap.content_media_cache import CachedContentMedia, ContentMediaCacheNotFound
from aima_ugc.bootstrap.content_media_http import install_content_media_routes
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeMediaReader:
    """媒体路由单测使用的最小 Reader。"""

    def get_media(self, content_id, position):  # type: ignore[no-untyped-def]
        if position != 0:
            raise ContentMediaCacheNotFound
        return CachedContentMedia(data=b"image-bytes", content_type="image/webp")


def test_content_media_route_returns_same_origin_bytes_and_stays_out_of_openapi() -> None:
    app = FastAPI()
    install_content_media_routes(app, media_reader=_FakeMediaReader())
    content_id = uuid4()

    response = TestClient(app).get(f"/api/v1/contents/{content_id}/media/0")

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "/api/v1/contents/{content_id}/media/{position}" not in app.openapi()["paths"]


def test_content_media_route_returns_404_for_missing_position() -> None:
    app = FastAPI()
    install_content_media_routes(app, media_reader=_FakeMediaReader())

    response = TestClient(app).get(f"/api/v1/contents/{uuid4()}/media/1")

    assert response.status_code == 404
