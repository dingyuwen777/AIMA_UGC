"""声音广场同源 Content Media Cache 字节路由。"""

from __future__ import annotations

import atexit
from functools import lru_cache
from typing import Protocol
from uuid import UUID

from fastapi import FastAPI, HTTPException, Response

from .content_media_cache import (
    CachedContentMedia,
    ContentMediaCacheNotFound,
    ContentMediaCacheUnavailable,
    PostgresContentMediaCacheService,
)
from .runtime import create_platform_runtime


class ContentMediaReader(Protocol):
    """媒体路由依赖的最小读取边界。"""

    def get_media(self, content_id: UUID, position: int) -> CachedContentMedia: ...


@lru_cache(maxsize=1)
def _default_media_service() -> PostgresContentMediaCacheService:
    """为 API 进程复用单一媒体缓存 Runtime，避免逐图片建立连接池。"""

    runtime = create_platform_runtime("api-media")
    service = PostgresContentMediaCacheService(runtime)

    def close() -> None:
        service.close()
        runtime.close()

    atexit.register(close)
    return service


def install_content_media_routes(
    application: FastAPI,
    *,
    media_reader: ContentMediaReader | None = None,
) -> None:
    """安装不进入 OpenAPI/generated-client 的内部同源图片字节路由。"""

    def current_reader() -> ContentMediaReader:
        return media_reader or _default_media_service()

    @application.get(
        "/api/v1/contents/{content_id}/media/{position}",
        include_in_schema=False,
        tags=["contents"],
    )
    def get_content_media(content_id: UUID, position: int) -> Response:
        if position < 0:
            raise HTTPException(status_code=404, detail="media not found")
        try:
            media = current_reader().get_media(content_id, position)
        except ContentMediaCacheNotFound as exc:
            raise HTTPException(status_code=404, detail="media not found") from exc
        except ContentMediaCacheUnavailable as exc:
            raise HTTPException(status_code=502, detail="media temporarily unavailable") from exc
        return Response(
            content=media.data,
            media_type=media.content_type,
            headers={
                "Cache-Control": "private, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )


__all__ = ["ContentMediaReader", "install_content_media_routes"]
