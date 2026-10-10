"""播放契约和 HTTP 入口保持站内 URL、Principal 与 Range 的明确边界。"""

from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from aima_ugc.adapters.providers.video_stream import VideoStreamProxy
from aima_ugc.bootstrap.content_playback_http import install_content_playback_routes
from aima_ugc.contracts.content_playback import ContentMediaPlaybackResponse
from aima_ugc.modules.identity import DevelopmentIdentityResolver
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_playback_prepare_and_stream_contract_resolve_principal_and_preserve_range():
    content_id = uuid4()
    seen = []

    def prepare(actual_id, position, body, **kwargs):
        seen.append(("prepare", actual_id, position, body.failed_source_revision, kwargs))
        return ContentMediaPlaybackResponse(
            content_id=content_id,
            position=0,
            status="ready",
            generation=1,
            source_revision="a" * 64,
            stream_url=f"/api/v1/contents/{content_id}/media/0/playback/stream?session=signed",
        )

    proxy = VideoStreamProxy(
        resolve=lambda *_args, **_kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))],
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    206,
                    headers={"Content-Type": "video/mp4", "Content-Range": "bytes 0-2/3"},
                    content=b"abc",
                )
            )
        ),
    )

    def stream(actual_id, position, **kwargs):
        seen.append(("stream", actual_id, position, kwargs))
        return proxy.open(
            "https://sns-v11.rednotecdn.com/synthetic",
            principal_id=kwargs["principal"].principal_id,
            byte_range=kwargs["byte_range"],
        )

    app = FastAPI()
    install_content_playback_routes(
        app,
        identity_resolver=DevelopmentIdentityResolver(principal_id="viewer"),
        service=SimpleNamespace(prepare=prepare, stream=stream),
    )
    with TestClient(app) as client:
        response = client.post(f"/api/v1/contents/{content_id}/media/0/playback/prepare", json={})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        data = response.json()
        assert data["status"] == "ready" and data["stream_url"].startswith("/api/")
        assert "rednotecdn" not in response.text
        response = client.get(data["stream_url"], headers={"Range": "bytes=0-2"})
        assert response.status_code == 206 and response.content == b"abc"
        assert response.headers["content-range"] == "bytes 0-2/3"
        assert proxy.active_count == 0
        response = client.get(
            data["stream_url"].replace("/stream?", "/stream/?"),
            headers={"Range": "bytes=0-2"},
            follow_redirects=False,
        )
        assert response.status_code == 206 and response.content == b"abc"
        assert "location" not in response.headers
        assert (
            client.post(
                f"/api/v1/contents/{content_id}/media/0/playback/prepare",
                json={"url": "https://evil.test"},
            ).status_code
            == 422
        )
        assert client.get(data["stream_url"].replace("signed", "x" * 4097)).status_code == 403
    assert seen[0][4]["principal"].principal_id == "viewer"
    assert seen[1][3]["session"] == "signed" and seen[1][3]["byte_range"] == "bytes=0-2"
    assert seen[1][3]["principal"].principal_id == "viewer"
    schema = app.openapi()
    assert (
        schema["paths"]["/api/v1/contents/{content_id}/media/{position}/playback/prepare"]["post"][
            "operationId"
        ]
        == "prepareContentMediaPlayback"
    )


@pytest.mark.parametrize("suffix", ["", "/", "//"])
def test_stream_access_log_scope_redacts_session_but_memory_verification_receives_real_value(
    suffix,
):
    import asyncio

    from aima_ugc.bootstrap.content_playback_session_http import (
        PLAYBACK_SESSION_STATE_KEY,
        PlaybackSessionRedactingMiddleware,
    )
    from aima_ugc.modules.content.media_playback import ContentPlaybackSessionCodec

    content_id = uuid4()
    codec = ContentPlaybackSessionCodec(secret=b"playback-test-signing-secret-32bytes")
    binding = dict(
        principal_id="viewer",
        content_id=content_id,
        position=0,
        identity_token="identity",
        source_revision="a" * 64,
    )
    token = codec.issue(**binding)
    scope = {
        "type": "http",
        "path": f"/api/v1/contents/{content_id}/media/0/playback/stream{suffix}",
        "query_string": f"session={token}&other=ok".encode(),
    }

    async def endpoint(actual, _receive, _send):
        assert actual["path"] == f"/api/v1/contents/{content_id}/media/0/playback/stream"
        assert token.encode() not in actual["query_string"]
        assert actual["query_string"] == b"session=hidden&other=ok"
        codec.verify(actual["state"][PLAYBACK_SESSION_STATE_KEY], **binding)

    async def unused():
        return {}

    asyncio.run(PlaybackSessionRedactingMiddleware(endpoint)(scope, unused, unused))
    assert token.encode() not in scope["query_string"]


def test_stream_session_redaction_keeps_ordinary_api_query_logging_unchanged():
    """普通 API 的同名查询参数不属于播放能力令牌，不扩大日志改写范围。"""
    import asyncio

    from aima_ugc.bootstrap.content_playback_session_http import (
        PLAYBACK_SESSION_STATE_KEY,
        PlaybackSessionRedactingMiddleware,
    )

    scope = {"type": "http", "path": "/api/v1/jobs/", "query_string": b"session=ordinary"}

    async def endpoint(actual, _receive, _send):
        assert actual["query_string"] == b"session=ordinary"
        assert PLAYBACK_SESSION_STATE_KEY not in actual.get("state", {})

    async def unused():
        return {}

    asyncio.run(PlaybackSessionRedactingMiddleware(endpoint)(scope, unused, unused))
