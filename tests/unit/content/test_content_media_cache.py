import httpx
import pytest
from aima_ugc.bootstrap.content_media_cache import (
    ContentMediaCacheUnavailable,
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
