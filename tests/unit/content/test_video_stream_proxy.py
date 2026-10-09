"""同源视频代理的地址、Range 与资源所有权边界。"""

from __future__ import annotations

import socket

import httpx
import pytest
from aima_ugc.adapters.providers.video_stream import (
    VideoStreamError,
    VideoStreamProxy,
    normalize_video_url,
    validate_video_range,
)
from starlette.requests import ClientDisconnect


@pytest.mark.parametrize("host", ["sns-v11.rednotecdn.com", "sns-v27.rednotecdn.com"])
def test_only_verified_video_origins_can_upgrade_http(host: str) -> None:
    assert normalize_video_url(f"http://{host}/synthetic.mp4?sign=test") == (
        f"https://{host}/synthetic.mp4?sign=test"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a.mp4",
        "https://sns-v11.rednotecdn.com.evil.test/a",
        "https://user:pass@sns-v11.rednotecdn.com/a",
        "https://127.0.0.1/a",
        "https://sns-v11.rednotecdn.com:444/a",
        "https://sns-v11.rednotecdn.com/a#fragment",
        "https://sns-v11.rednotecdn.com/a\r\nInjected: yes",
        "https://sns-v11.rednotecdn.com\\@evil.test/a",
    ],
)
def test_untrusted_urls_are_rejected(url: str) -> None:
    with pytest.raises(VideoStreamError, match="invalid_source"):
        normalize_video_url(url)


@pytest.mark.parametrize("value", [None, "bytes=0-65535", "bytes=65536-", "bytes=-1024"])
def test_valid_single_range_is_preserved(value: str | None) -> None:
    assert validate_video_range(value) == value


@pytest.mark.parametrize(
    "value", ["items=0-1", "bytes=1-0", "bytes=0-1,3-4", "bytes=-", "bytes=-0"]
)
def test_invalid_ranges_are_rejected(value: str) -> None:
    with pytest.raises(VideoStreamError, match="invalid_range"):
        validate_video_range(value)


def _dns(*addresses: str):
    return lambda _host, _port, **_kwargs: [
        (
            socket.AF_INET6 if ":" in address else socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            (address, 443),
        )
        for address in addresses
    ]


def test_every_dns_answer_must_be_public() -> None:
    requests: list[httpx.Request] = []
    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8", "127.0.0.1"),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(lambda req: requests.append(req))
        ),
    )
    with pytest.raises(VideoStreamError, match="invalid_source"):
        proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")
    assert requests == []


@pytest.mark.parametrize("address", ["224.0.0.1", "ff0e::1", "fec0::1"])
def test_multicast_or_site_local_dns_answers_are_not_public_destinations(address):
    proxy = VideoStreamProxy(resolve=_dns(address))
    with pytest.raises(VideoStreamError, match="invalid_source"):
        proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")
    assert proxy.active_count == 0


def test_connection_uses_fixed_ip_original_host_and_tls_name() -> None:
    requests: list[httpx.Request] = []
    clients: list[httpx.Client] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            206,
            headers={
                "Content-Type": "video/mp4",
                "Content-Range": "bytes 0-2/3",
                "Set-Cookie": "secret=never",
            },
            content=b"abc",
        )

    def client() -> httpx.Client:
        value = httpx.Client(transport=httpx.MockTransport(respond))
        clients.append(value)
        return value

    proxy = VideoStreamProxy(resolve=_dns("8.8.8.8"), client_factory=client)
    handle = proxy.open(
        "https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer", byte_range="bytes=0-2"
    )
    assert requests[0].url.host == "8.8.8.8"
    assert requests[0].headers["Host"] == "sns-v11.rednotecdn.com"
    assert requests[0].extensions["sni_hostname"] == "sns-v11.rednotecdn.com"
    assert requests[0].headers["range"] == "bytes=0-2"
    assert "cookie" not in requests[0].headers and "authorization" not in requests[0].headers
    assert "set-cookie" not in handle.headers
    assert handle.headers["Cache-Control"] == "private, no-store"
    assert b"".join(handle.iter_bytes()) == b"abc"
    assert handle.closed and clients[0].is_closed and proxy.active_count == 0


def test_redirect_revalidates_target_and_closes_resources() -> None:
    response = httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})
    client = httpx.Client(transport=httpx.MockTransport(lambda _request: response))
    proxy = VideoStreamProxy(resolve=_dns("8.8.8.8"), client_factory=lambda: client)
    with pytest.raises(VideoStreamError, match="invalid_source"):
        proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")
    assert response.is_closed and client.is_closed and proxy.active_count == 0


@pytest.mark.parametrize(
    "status,code",
    [
        (403, "cdn_forbidden"),
        (404, "cdn_not_found"),
        (410, "cdn_gone"),
        (429, "cdn_rate_limited"),
        (503, "cdn_unavailable"),
    ],
)
def test_cdn_failures_are_classified_and_closed(status: int, code: str) -> None:
    response = httpx.Response(status)
    client = httpx.Client(transport=httpx.MockTransport(lambda _request: response))
    proxy = VideoStreamProxy(resolve=_dns("8.8.8.8"), client_factory=lambda: client)
    with pytest.raises(VideoStreamError) as failure:
        proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")
    assert failure.value.code == code
    assert response.is_closed and client.is_closed and proxy.active_count == 0


def test_416_preserves_unsatisfied_range_without_caching() -> None:
    response = httpx.Response(416, headers={"Content-Range": "bytes */3"})
    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(lambda _req: response)),
    )
    handle = proxy.open(
        "https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer", byte_range="bytes=10-"
    )
    assert handle.status_code == 416 and handle.headers["Content-Range"] == "bytes */3"
    handle.close()
    handle.close()
    assert response.is_closed and proxy.active_count == 0


def test_close_releases_limit_without_canceling_other_viewers() -> None:
    proxy = VideoStreamProxy(
        max_connections=2,
        per_principal_connections=1,
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda _req: httpx.Response(
                    200, headers={"Content-Type": "video/mp4"}, content=b"a"
                )
            )
        ),
    )
    first = proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="one")
    with pytest.raises(VideoStreamError, match="busy"):
        proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="one")
    second = proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="two")
    first.close()
    assert not second.closed and proxy.active_count == 1
    second.close()
    assert proxy.active_count == 0


def test_trusted_redirect_resolves_again_and_does_not_forward_cookies() -> None:
    requests: list[httpx.Request] = []
    hosts: list[str] = []

    def resolve(host: str, port: int, **kwargs):
        hosts.append(host)
        return _dns("8.8.8.8" if len(hosts) == 1 else "1.1.1.1")(host, port, **kwargs)

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                302,
                headers={
                    "Location": "https://sns-v27.rednotecdn.com/backup",
                    "Set-Cookie": "session=secret; Domain=rednotecdn.com; Path=/",
                },
            )
        return httpx.Response(200, headers={"Content-Type": "video/mp4"}, content=b"ok")

    proxy = VideoStreamProxy(
        resolve=resolve, client_factory=lambda: httpx.Client(transport=httpx.MockTransport(respond))
    )
    handle = proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")
    assert hosts == ["sns-v11.rednotecdn.com", "sns-v27.rednotecdn.com"]
    assert requests[-1].url.host == "1.1.1.1"
    assert "cookie" not in requests[-1].headers
    handle.close()


def test_connect_timeout_is_classified_and_releases_capacity() -> None:
    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("synthetic timeout")

    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(timeout)),
    )
    failures: list[str] = []
    with pytest.raises(VideoStreamError, match="cdn_timeout"):
        proxy.open(
            "https://sns-v11.rednotecdn.com/synthetic",
            principal_id="viewer",
            failure=failures.append,
        )
    assert failures == ["cdn_timeout"] and proxy.active_count == 0


@pytest.mark.parametrize("value", ["text/html", "image/jpeg", "application/octet-stream"])
def test_unsupported_mime_never_yields_bytes(value: str) -> None:
    response = httpx.Response(200, headers={"Content-Type": value}, content=b"never video")
    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(lambda _request: response)
        ),
    )
    with pytest.raises(VideoStreamError, match="unsupported_format"):
        proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")
    assert response.is_closed and proxy.active_count == 0


def test_asgi_send_failure_releases_upstream_without_generator_iteration() -> None:
    import asyncio

    from aima_ugc.bootstrap.content_playback_stream_http import ContentVideoStreamingResponse

    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200, headers={"Content-Type": "video/mp4"}, content=b"abc"
                )
            )
        ),
    )
    handle = proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")

    async def send(_message):
        raise OSError("browser disconnected")

    async def receive():
        return {"type": "http.disconnect"}

    with pytest.raises(ClientDisconnect):
        asyncio.run(
            ContentVideoStreamingResponse(handle)(
                {"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send
            )
        )
    assert handle.closed and proxy.active_count == 0


def test_416_empty_response_does_not_forward_upstream_body_length() -> None:
    import asyncio

    from aima_ugc.bootstrap.content_playback_stream_http import ContentVideoStreamingResponse

    upstream = httpx.Response(
        416, headers={"Content-Range": "bytes */3", "Content-Length": "8"}, content=b"rejected"
    )
    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(lambda _: upstream)),
    )
    handle = proxy.open(
        "https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer", byte_range="bytes=10-"
    )
    messages = []

    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.disconnect"}

    asyncio.run(
        ContentVideoStreamingResponse(handle)(
            {"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send
        )
    )
    headers = dict(messages[0]["headers"])
    assert headers.get(b"content-length", b"0") == b"0"
    assert b"".join(message.get("body", b"") for message in messages) == b""
    assert handle.closed and upstream.is_closed and proxy.active_count == 0


@pytest.mark.parametrize(
    "status,headers,body,byte_range",
    [
        (200, {"Content-Encoding": "gzip"}, b"encoded", None),
        (206, {"Content-Range": "bytes 9-1/3"}, b"abc", "bytes=0-2"),
        (206, {"Content-Range": "bytes 4-6/10"}, b"abc", "bytes=0-2"),
        (206, {"Content-Range": "bytes 0-9/10"}, b"abc", "bytes=0-9"),
        (200, {"Content-Range": "bytes 0-2/10"}, b"abc", None),
    ],
)
def test_inconsistent_representation_or_range_is_rejected_before_response(
    status, headers, body, byte_range
):
    # gzip 内容由 HTTPX 真正解码，必须在复制压缩长度前拒绝。
    import gzip

    if headers.get("Content-Encoding") == "gzip":
        body = gzip.compress(b"a" * 1000)
    upstream = httpx.Response(
        status, headers={"Content-Type": "video/mp4", **headers}, content=body
    )
    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(lambda _: upstream)),
    )
    with pytest.raises(VideoStreamError, match="cdn_invalid_response"):
        proxy.open(
            "https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer", byte_range=byte_range
        )
    assert upstream.is_closed and proxy.active_count == 0


def test_standard_nonrange_200_is_forwarded_truthfully() -> None:
    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    headers={"Content-Type": "video/mp4", "Accept-Ranges": "none"},
                    content=b"abc",
                )
            )
        ),
    )
    handle = proxy.open(
        "https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer", byte_range="bytes=0-2"
    )
    assert handle.status_code == 200 and handle.headers["Accept-Ranges"] == "none"
    assert b"".join(handle.iter_bytes()) == b"abc"


def test_dns_and_whole_open_have_bounded_waits_without_unbounded_background_work() -> None:
    import threading
    import time

    entered, release = threading.Event(), threading.Event()

    def blocked_dns(*args, **kwargs):
        entered.set()
        release.wait(2)
        return _dns("8.8.8.8")(*args, **kwargs)

    proxy = VideoStreamProxy(
        resolve=blocked_dns, dns_timeout_seconds=0.05, open_timeout_seconds=0.1
    )
    started = time.monotonic()
    try:
        with pytest.raises(VideoStreamError, match="cdn_timeout"):
            proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")
        assert entered.is_set() and time.monotonic() - started < 0.5
        assert proxy.active_count == 0
    finally:
        release.set()


def test_timed_out_dns_keeps_bounded_background_quota(monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    import aima_ugc.adapters.providers.video_stream as runtime

    release = threading.Event()
    entered = []

    def blocked_dns(*args, **kwargs):
        entered.append(1)
        release.wait(2)
        return _dns("8.8.8.8")(*args, **kwargs)

    with ThreadPoolExecutor(max_workers=4) as pool:
        monkeypatch.setattr(runtime, "_DNS_POOL", pool)
        monkeypatch.setattr(runtime, "_DNS_SLOTS", threading.BoundedSemaphore(4))
        proxy = VideoStreamProxy(resolve=blocked_dns, dns_timeout_seconds=0.01)
        try:
            for _ in range(4):
                with pytest.raises(VideoStreamError, match="cdn_timeout"):
                    proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")
            with pytest.raises(VideoStreamError, match="busy"):
                proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")
            assert len(entered) == 4 and proxy.active_count == 0
        finally:
            release.set()


def test_whole_open_budget_closes_late_upstream_response() -> None:
    import threading
    import time

    release, completed = threading.Event(), threading.Event()
    upstream = httpx.Response(200, headers={"Content-Type": "video/mp4"}, content=b"abc")

    def blocked_send(_request):
        release.wait(2)
        completed.set()
        return upstream

    client = httpx.Client(transport=httpx.MockTransport(blocked_send))
    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8"), client_factory=lambda: client, open_timeout_seconds=0.05
    )
    started = time.monotonic()
    try:
        with pytest.raises(VideoStreamError, match="cdn_timeout"):
            proxy.open("https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer")
        assert time.monotonic() - started < 0.5 and proxy.active_count == 0 and client.is_closed
    finally:
        release.set()
        assert completed.wait(1)
    for _ in range(100):
        if upstream.is_closed:
            break
        time.sleep(0.001)
    assert upstream.is_closed


def test_disconnect_during_blocked_upstream_read_releases_only_owned_stream() -> None:
    import asyncio
    import threading

    from aima_ugc.bootstrap.content_playback_stream_http import ContentVideoStreamingResponse

    first_sent, read_blocked, release = threading.Event(), threading.Event(), threading.Event()

    class Body(httpx.SyncByteStream):
        def __iter__(self):
            yield b"a" * (64 * 1024)
            read_blocked.set()
            release.wait(2)

        def close(self):
            release.set()

    upstream = httpx.Response(200, headers={"Content-Type": "video/mp4"}, stream=Body())
    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(lambda _: upstream)),
    )
    failures = []
    handle = proxy.open(
        "https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer", failure=failures.append
    )

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            first_sent.set()

    async def receive():
        await asyncio.to_thread(first_sent.wait, 1)
        await asyncio.to_thread(read_blocked.wait, 1)
        return {"type": "http.disconnect"}

    try:
        asyncio.run(
            ContentVideoStreamingResponse(handle)(
                {"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send
            )
        )
        assert first_sent.is_set() and read_blocked.is_set()
        assert handle.closed and upstream.is_closed and proxy.active_count == 0 and failures == []
    finally:
        release.set()
        handle.close()


def test_close_interrupts_bandwidth_wait_without_failure_or_video_persistence() -> None:
    import threading

    ready = threading.Event()

    class Body(httpx.SyncByteStream):
        def __iter__(self):
            ready.set()
            yield b"a" * (64 * 1024)

        def close(self):
            pass

    proxy = VideoStreamProxy(
        bytes_per_second=1,
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, headers={"Content-Type": "video/mp4"}, stream=Body())
            )
        ),
    )
    failures = []
    handle = proxy.open(
        "https://sns-v11.rednotecdn.com/synthetic", principal_id="viewer", failure=failures.append
    )
    output = []
    worker = threading.Thread(target=lambda: output.extend(handle.iter_bytes()))
    worker.start()
    assert ready.wait(1)
    handle.close()
    worker.join(1)
    assert not worker.is_alive() and output == [] and failures == [] and proxy.active_count == 0


@pytest.mark.parametrize("body", [b"abc", b"ab", b"abcd"])
def test_streamed_206_without_content_length_obeys_proven_range_and_closes(body):
    class ChunkedBody(httpx.SyncByteStream):
        def __iter__(self):
            for byte in body:
                yield bytes([byte])

    response = httpx.Response(
        206,
        headers={"Content-Type": "video/mp4", "Content-Range": "bytes 0-2/3"},
        stream=ChunkedBody(),
    )
    proxy = VideoStreamProxy(
        resolve=_dns("8.8.8.8"),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(lambda _: response)),
    )
    failures, output = [], []
    handle = proxy.open(
        "https://sns-v11.rednotecdn.com/synthetic",
        principal_id="viewer",
        byte_range="bytes=0-2",
        failure=failures.append,
    )
    assert "Content-Length" not in handle.headers
    if len(body) == 3:
        output.extend(handle.iter_bytes())
        assert b"".join(output) == body and failures == []
    else:
        with pytest.raises(VideoStreamError, match="cdn_invalid_response"):
            output.extend(handle.iter_bytes())
        assert len(b"".join(output)) <= 3
        assert failures == ["cdn_invalid_response"]
    assert handle.closed and response.is_closed and proxy.active_count == 0
