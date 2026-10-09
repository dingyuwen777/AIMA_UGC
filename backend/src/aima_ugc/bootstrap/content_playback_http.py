"""视频播放的鉴权入口与站内流响应；外部地址只由数据库服务读取。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from threading import Lock
from typing import Annotated, Any, Protocol, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response

from aima_ugc.adapters.providers.video_stream import VideoStreamError, VideoStreamHandle
from aima_ugc.contracts.content_playback import (
    ContentMediaPlaybackPrepareRequest,
    ContentMediaPlaybackResponse,
)
from aima_ugc.contracts.http import HttpErrorResponse
from aima_ugc.modules.content.content_cursor import InvalidContentCursor
from aima_ugc.modules.content.http import ContentResourceNotFound
from aima_ugc.modules.identity import IdentityResolver, Principal

from .content_playback_session_http import (
    PLAYBACK_SESSION_STATE_KEY,
    PlaybackSessionRedactingMiddleware,
)
from .content_playback_stream_http import ContentVideoStreamingResponse
from .runtime import PlatformRuntime, create_platform_runtime


class ContentPlaybackHttpService(Protocol):
    """路由只委托正式服务；测试注入 Fake 不替换鉴权或流响应实现。"""

    def prepare(
        self,
        content_id: UUID,
        position: int,
        body: ContentMediaPlaybackPrepareRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ContentMediaPlaybackResponse: ...

    def stream(
        self,
        content_id: UUID,
        position: int,
        *,
        session: str,
        byte_range: str | None,
        principal: Principal,
    ) -> VideoStreamHandle: ...


def install_content_playback_routes(
    application: FastAPI,
    *,
    identity_resolver: IdentityResolver,
    service: ContentPlaybackHttpService | None = None,
) -> None:
    """准备入口进入生成 Contract；GET/Range 永远不创建收费请求。"""
    runtime: PlatformRuntime | None = None
    application.add_middleware(PlaybackSessionRedactingMiddleware)
    resolved_service = service
    service_lock = Lock()

    def current_service() -> ContentPlaybackHttpService:
        nonlocal runtime, resolved_service
        with service_lock:
            if resolved_service is None:
                from .content_playback_service import PostgresContentPlaybackHttpService

                runtime = create_platform_runtime("api-video-playback")
                resolved_service = PostgresContentPlaybackHttpService(runtime)
        return resolved_service

    if service is None:
        router = cast(Any, application.router)
        original_lifespan = router.lifespan_context

        @asynccontextmanager
        async def playback_lifespan(app: FastAPI) -> AsyncIterator[None]:
            async with original_lifespan(app):
                try:
                    yield
                finally:
                    if runtime is not None:
                        runtime.close()

        router.lifespan_context = playback_lifespan

    @application.post(
        "/api/v1/contents/{content_id}/media/{position}/playback/prepare",
        operation_id="prepareContentMediaPlayback",
        response_model=ContentMediaPlaybackResponse,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}},
        tags=["contents"],
    )
    def prepare_content_media_playback(
        content_id: UUID,
        position: Annotated[int, Path(ge=0)],
        body: ContentMediaPlaybackPrepareRequest,
        request: Request,
        response: Response,
    ) -> ContentMediaPlaybackResponse:
        principal = identity_resolver.resolve(request)
        response.headers["Cache-Control"] = "private, no-store"
        try:
            return current_service().prepare(
                content_id,
                position,
                body,
                principal=principal,
                request_id=str(getattr(request.state, "request_id", None) or uuid4()),
            )
        except ContentResourceNotFound:
            raise HTTPException(404, "media not found") from None

    @application.get(
        "/api/v1/contents/{content_id}/media/{position}/playback/stream",
        operation_id="streamContentMediaPlayback",
        response_class=Response,
        responses={
            200: {"content": {"video/mp4": {"schema": {"type": "string", "format": "binary"}}}},
            206: {"content": {"video/mp4": {"schema": {"type": "string", "format": "binary"}}}},
            416: {"description": "Unsatisfied byte range"},
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            429: {"model": HttpErrorResponse},
            502: {"model": HttpErrorResponse},
            504: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def stream_content_media_playback(
        content_id: UUID,
        position: Annotated[int, Path(ge=0)],
        request: Request,
        session: Annotated[str, Query(min_length=1, max_length=4096)],
    ) -> Response:
        principal = identity_resolver.resolve(request)
        real_session = str(getattr(request.state, PLAYBACK_SESSION_STATE_KEY, session))
        if not 1 <= len(real_session) <= 4096:
            # 访问日志替换 query 后仍须对真实内存参数执行 Contract 的长度限制。
            raise HTTPException(403, "playback session invalid or expired")
        try:
            handle = current_service().stream(
                content_id,
                position,
                session=real_session,
                byte_range=request.headers.get("Range"),
                principal=principal,
            )
        except ContentResourceNotFound:
            raise HTTPException(404, "media not found") from None
        except InvalidContentCursor:
            raise HTTPException(403, "playback session invalid or expired") from None
        except VideoStreamError as exc:
            code = exc.code
            status = (
                416
                if code == "invalid_range"
                else 429
                if code in {"busy", "cdn_rate_limited"}
                else 504
                if code == "cdn_timeout"
                else 502
            )
            raise HTTPException(
                status,
                code,
                headers={"Cache-Control": "private, no-store", "X-AIMA-Media-Failure": code},
            ) from None
        return ContentVideoStreamingResponse(handle)
