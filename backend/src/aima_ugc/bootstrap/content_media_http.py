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

_MEDIA_UNAVAILABLE_PLACEHOLDER = """<svg xmlns="http://www.w3.org/2000/svg" width="1124" height="672" viewBox="0 0 1124 672" role="img" aria-label="图片暂不可用">
<rect width="1124" height="672" rx="28" fill="#F8FAFC"/>
<rect x="1" y="1" width="1122" height="670" rx="27" fill="none" stroke="#E6EAF0" stroke-width="2"/>
<g transform="translate(512 252)" fill="none" stroke="#A8B0BF" stroke-width="8" stroke-linecap="round" stroke-linejoin="round">
<rect x="0" y="0" width="100" height="82" rx="12"/>
<circle cx="31" cy="26" r="9"/>
<path d="M14 68 38 45l18 17 14-13 16 19"/>
</g>
<text x="562" y="378" text-anchor="middle" font-family="Noto Sans SC, Microsoft YaHei, sans-serif" font-size="30" font-weight="600" fill="#6B778C">图片暂不可用</text>
<text x="562" y="421" text-anchor="middle" font-family="Noto Sans SC, Microsoft YaHei, sans-serif" font-size="22" fill="#A8B0BF">帖子正文与评论信息仍可正常查看</text>
</svg>""".encode("utf-8")


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
        except ContentMediaCacheUnavailable:
            return Response(
                content=_MEDIA_UNAVAILABLE_PLACEHOLDER,
                media_type="image/svg+xml",
                headers={
                    "Cache-Control": "private, max-age=60",
                    "X-AIMA-Media-State": "unavailable",
                    "X-Content-Type-Options": "nosniff",
                },
            )
        return Response(
            content=media.data,
            media_type=media.content_type,
            headers={
                "Cache-Control": "private, max-age=3600",
                "X-AIMA-Media-State": "available",
                "X-Content-Type-Options": "nosniff",
            },
        )


__all__ = ["ContentMediaReader", "install_content_media_routes"]
