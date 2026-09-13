"""小红书 Content 图片的安全、可重建 Artifact 缓存。"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import httpx

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
)
from aima_ugc.adapters.persistence.postgres.content_media_cache import (
    ContentMediaSource,
    PostgresContentMediaCacheRepository,
)
from aima_ugc.platform.logging import log_event, log_exception_event
from aima_ugc.platform.storage import ArtifactService
from aima_ugc.platform.storage.retention import MEDIA_CACHE_ITEM_MAX_BYTES
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

_ALLOWED_RASTER_TYPES = frozenset(
    {
        "image/avif",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)
_REFERER = "https://www.xiaohongshu.com/"
_USER_AGENT = "AIMA_UGC/1.0"
_REQUEST_HEADERS = {
    "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif,image/*;q=0.8",
    "Referer": _REFERER,
    "User-Agent": _USER_AGENT,
}
logger = logging.getLogger(__name__)


class ContentMediaCacheNotFound(RuntimeError):
    """请求位置不存在可缓存的小红书图片。"""


class ContentMediaCacheUnavailable(RuntimeError):
    """图片源当前无法安全获取或缓存。"""


@dataclass(frozen=True, slots=True)
class CachedContentMedia:
    """可直接返回给浏览器的缓存图片。"""

    data: bytes
    content_type: str


class XiaohongshuImageFetcher:
    """只访问小红书受信任图片 Origin 的有界 HTTP 客户端。"""

    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(20.0),
            follow_redirects=False,
            trust_env=False,
        )

    def close(self) -> None:
        """关闭服务自己创建的 HTTP Client。"""

        if self._owns_client:
            self._client.close()

    def fetch(self, source_url: str) -> tuple[str, bytes, str]:
        """校验 URL 后下载一张不超过 10 MiB 的栅格图片。"""

        normalized = normalize_xiaohongshu_image_url(source_url)
        try:
            with self._client.stream("GET", normalized, headers=_REQUEST_HEADERS) as response:
                if response.status_code != 200:
                    raise ContentMediaCacheUnavailable("图片源返回非成功状态")
                content_type = (
                    response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                )
                if content_type not in _ALLOWED_RASTER_TYPES:
                    raise ContentMediaCacheUnavailable("图片源响应类型不受支持")
                declared = response.headers.get("content-length")
                if declared is not None:
                    try:
                        if int(declared) > MEDIA_CACHE_ITEM_MAX_BYTES:
                            raise ContentMediaCacheUnavailable("图片源响应超过缓存上限")
                    except ValueError as exc:
                        raise ContentMediaCacheUnavailable("图片源 Content-Length 不合法") from exc
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MEDIA_CACHE_ITEM_MAX_BYTES:
                        raise ContentMediaCacheUnavailable("图片源响应超过缓存上限")
        except ContentMediaCacheUnavailable:
            raise
        except httpx.HTTPError as exc:
            raise ContentMediaCacheUnavailable("图片源网络请求失败") from exc
        return normalized, bytes(data), content_type


def normalize_xiaohongshu_image_url(source_url: str) -> str:
    """把允许的 XHS 图片 URL 规范为 HTTPS Origin，并拒绝任意代理目标。"""

    try:
        parsed = urlsplit(source_url.strip())
        port = parsed.port
    except ValueError as exc:
        raise ContentMediaCacheUnavailable("图片源 URL 不合法") from exc
    hostname = (parsed.hostname or "").lower()
    trusted_host = (
        hostname == "ci.xiaohongshu.com"
        or hostname == "xhscdn.com"
        or hostname.endswith(".xhscdn.com")
    )
    default_port = (parsed.scheme == "http" and port in (None, 80)) or (
        parsed.scheme == "https" and port in (None, 443)
    )
    if (
        parsed.scheme not in {"http", "https"}
        or not trusted_host
        or not default_port
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/")
    ):
        raise ContentMediaCacheUnavailable("图片源不在允许的小红书 Origin")
    return urlunsplit(("https", hostname, parsed.path, parsed.query, ""))


class PostgresContentMediaCacheService:
    """以 Content 媒体事实为源，按需读取或重建可丢弃图片缓存。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        fetcher: XiaohongshuImageFetcher | None = None,
    ) -> None:
        self._runtime = runtime
        self._repository = PostgresContentMediaCacheRepository(runtime.database.new_session)
        self._artifacts = ArtifactService(
            metadata=PostgresArtifactMetadataGateway(runtime.database.new_session),
            store=runtime.artifact_store,
        )
        self._fetcher = fetcher or XiaohongshuImageFetcher()
        self._owns_fetcher = fetcher is None

    def close(self) -> None:
        """释放服务自己创建的媒体 HTTP Client。"""

        if self._owns_fetcher:
            self._fetcher.close()

    def get_media(self, content_id: UUID, position: int) -> CachedContentMedia:
        """缓存命中直接读取；miss 时安全下载、落 Artifact、更新当前绑定。"""

        source = self._repository.get_source(content_id, position)
        if not _cacheable_source(source):
            raise ContentMediaCacheNotFound
        assert source is not None and source.source_url is not None
        normalized = normalize_xiaohongshu_image_url(source.source_url)
        source_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        binding = self._repository.get_binding(content_id, position)
        if (
            binding is not None
            and binding.source_url_hash == source_hash
            and binding.storage_status in {"stored", "linked"}
            and self._runtime.artifact_store.exists(binding.storage_key)
        ):
            return CachedContentMedia(
                data=self._runtime.artifact_store.read(binding.storage_key),
                content_type=binding.content_type,
            )

        normalized, data, content_type = self._fetcher.fetch(source.source_url)
        source_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        artifact = self._artifacts.store_bytes(
            kind="content-media-cache",
            content_type=content_type,
            retention_class="cache",
            data=data,
            storage_key=f"media-cache/{source_hash}/{uuid4().hex}",
        )
        self._repository.bind(
            content_id=content_id,
            position=position,
            source_url_hash=source_hash,
            artifact_id=artifact.id,
            cached_at=beijing_now(),
        )
        try:
            self._artifacts.link(artifact.id)
        except Exception as exc:
            log_exception_event(
                logger,
                logging.WARNING,
                "content_media_cache.link_failed",
                "媒体缓存绑定已建立，但 Artifact linked 状态更新失败。",
                exc,
                content_id=str(content_id),
                position=position,
            )
        return CachedContentMedia(data=data, content_type=content_type)

    def prefetch_content(self, content_id: UUID) -> None:
        """Best-effort 预热一个小红书 Content 的全部图片，不向调用方传播单图失败。"""

        for source in self._repository.list_sources(content_id):
            if not _cacheable_source(source):
                continue
            try:
                self.get_media(content_id, source.position)
            except Exception as exc:
                log_exception_event(
                    logger,
                    logging.WARNING,
                    "content_media_cache.prefetch_failed",
                    "小红书图片缓存预热失败；不影响内容与评论采集结果。",
                    exc,
                    content_id=str(content_id),
                    position=source.position,
                )
        log_event(
            logger,
            logging.INFO,
            "content_media_cache.prefetch_completed",
            "小红书图片缓存预热已完成。",
            content_id=str(content_id),
        )


def _cacheable_source(source: ContentMediaSource | None) -> bool:
    """只让小红书图文图片进入缓存链路。"""

    return bool(
        source is not None
        and source.platform == "xiaohongshu"
        and source.media_type == "image"
        and source.source_url
    )


__all__ = [
    "CachedContentMedia",
    "ContentMediaCacheNotFound",
    "ContentMediaCacheUnavailable",
    "PostgresContentMediaCacheService",
    "XiaohongshuImageFetcher",
    "normalize_xiaohongshu_image_url",
]
