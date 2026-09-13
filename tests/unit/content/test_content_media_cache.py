import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from aima_ugc.adapters.persistence.postgres.content_media_cache import (
    ContentMediaCacheBinding,
    ContentMediaSource,
)
from aima_ugc.bootstrap.content_media_cache import (
    ContentMediaCacheUnavailable,
    PostgresContentMediaCacheService,
    XiaohongshuImageFetcher,
    normalize_xiaohongshu_image_url,
)
from aima_ugc.platform.storage.retention import MEDIA_CACHE_ITEM_MAX_BYTES


def test_normalize_xiaohongshu_image_url_accepts_only_trusted_origin() -> None:
    assert (
        normalize_xiaohongshu_image_url("http://sns-img-bd.xhscdn.com/abc?imageView2/2/w/1080")
        == "https://sns-img-bd.xhscdn.com/abc?imageView2/2/w/1080"
    )
    assert normalize_xiaohongshu_image_url("https://ci.xiaohongshu.com/abc") == (
        "https://ci.xiaohongshu.com/abc"
    )

    for url in (
        "https://example.com/image.jpg",
        "https://xhscdn.com.evil.example/image.jpg",
        "https://user@xhscdn.com/image.jpg",
        "https://sns-img-bd.xhscdn.com:80/image.jpg",
        "http://sns-img-bd.xhscdn.com:443/image.jpg",
    ):
        with pytest.raises(ContentMediaCacheUnavailable):
            normalize_xiaohongshu_image_url(url)


def test_xiaohongshu_image_fetcher_sends_required_headers_and_returns_raster() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.scheme == "https"
        assert request.headers["referer"] == "https://www.xiaohongshu.com/"
        assert request.headers["user-agent"] == "AIMA_UGC/1.0"
        return httpx.Response(200, headers={"content-type": "image/webp"}, content=b"image")

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    fetcher = XiaohongshuImageFetcher(client=client)
    try:
        normalized, data, content_type = fetcher.fetch("http://sns-img-bd.xhscdn.com/abc")
    finally:
        client.close()

    assert normalized == "https://sns-img-bd.xhscdn.com/abc"
    assert data == b"image"
    assert content_type == "image/webp"


@pytest.mark.parametrize(
    ("status_code", "content_type", "content_length"),
    [
        (302, "image/jpeg", None),
        (200, "image/svg+xml", None),
        (200, "image/jpeg", str(MEDIA_CACHE_ITEM_MAX_BYTES + 1)),
    ],
)
def test_xiaohongshu_image_fetcher_rejects_redirect_unsafe_type_and_oversize(
    status_code: int,
    content_type: str,
    content_length: str | None,
) -> None:
    headers = {"content-type": content_type}
    if content_length is not None:
        headers["content-length"] = content_length

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status_code, headers=headers, content=b"x")
        ),
        follow_redirects=False,
    )
    fetcher = XiaohongshuImageFetcher(client=client)
    try:
        with pytest.raises(ContentMediaCacheUnavailable):
            fetcher.fetch("https://sns-img-bd.xhscdn.com/abc")
    finally:
        client.close()


def test_media_cache_read_race_rebuilds_from_source_instead_of_failing() -> None:
    """Housekeeping 在绑定读取后删掉缓存字节时，应按 cache miss 重建。"""

    content_id = uuid4()
    old_artifact_id = uuid4()
    new_artifact_id = uuid4()
    source_url = "https://sns-img-bd.xhscdn.com/source"
    source_hash = hashlib.sha256(source_url.encode()).hexdigest()
    now = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)

    class Repository:
        def __init__(self) -> None:
            self.bound_artifact_id: UUID | None = None

        def get_source(self, requested_content_id: UUID, position: int) -> ContentMediaSource:
            assert requested_content_id == content_id
            assert position == 0
            return ContentMediaSource(
                content_id=content_id,
                position=0,
                platform="xiaohongshu",
                media_type="image",
                source_url=source_url,
            )

        def get_binding(
            self, requested_content_id: UUID, position: int
        ) -> ContentMediaCacheBinding:
            assert requested_content_id == content_id
            assert position == 0
            return ContentMediaCacheBinding(
                artifact_id=old_artifact_id,
                source_url_hash=source_hash,
                storage_key="media-cache/old/item",
                content_type="image/webp",
                storage_status="linked",
                byte_size=5,
                created_at=now,
                expires_at=now,
            )

        def bind(self, **kwargs: object) -> None:
            artifact_id = kwargs["artifact_id"]
            assert isinstance(artifact_id, UUID)
            self.bound_artifact_id = artifact_id

    class RaceStore:
        def read(self, _storage_key: str) -> bytes:
            raise FileNotFoundError("concurrent cleanup")

    class Fetcher:
        def fetch(self, requested_url: str) -> tuple[str, bytes, str]:
            assert requested_url == source_url
            return source_url, b"fresh", "image/webp"

    class Artifacts:
        def store_bytes(self, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(id=new_artifact_id)

        def link(self, artifact_id: UUID) -> None:
            assert artifact_id == new_artifact_id

    repository = Repository()
    service = object.__new__(PostgresContentMediaCacheService)
    service._runtime = SimpleNamespace(artifact_store=RaceStore())
    service._repository = repository
    service._fetcher = Fetcher()
    service._artifacts = Artifacts()

    media = service.get_media(content_id, 0)

    assert media.data == b"fresh"
    assert media.content_type == "image/webp"
    assert repository.bound_artifact_id == new_artifact_id
