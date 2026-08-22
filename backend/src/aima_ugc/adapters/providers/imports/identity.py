"""Excel 内容稳定身份、Provider lookup identity 与 URL 规范化。"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from .models import ExcelImportRowError


@dataclass(frozen=True, slots=True)
class ContentIdentity:
    """Canonical 主身份、来源备用身份、Provider lookup identity 及已校验 URL。"""

    external_content_id: str
    alternate_ids: dict[str, str]
    normalized_url: str | None


_HOST_SUFFIXES = {
    "xiaohongshu": ("xiaohongshu.com", "xhslink.com", "xhslink.cn"),
    "douyin": ("douyin.com",),
    "weibo": ("weibo.com", "weibo.cn"),
    "bilibili": ("bilibili.com", "b23.tv"),
    "kuaishou": ("kuaishou.com",),
}
_NATIVE_PATH_PATTERNS = {
    "xiaohongshu": (
        re.compile(r"^/explore/([^/?#]+)", re.IGNORECASE),
        re.compile(r"^/discovery/item/([^/?#]+)", re.IGNORECASE),
    ),
    "douyin": (re.compile(r"^/(?:video|note)/(\d+)", re.IGNORECASE),),
    "weibo": (
        re.compile(r"^/(?:status|detail)/([A-Za-z0-9]+)", re.IGNORECASE),
        re.compile(r"^/\d+/([A-Za-z0-9]+)", re.IGNORECASE),
    ),
    "bilibili": (
        re.compile(r"^/video/((?:BV[A-Za-z0-9]+)|(?:av\d+))", re.IGNORECASE),
        re.compile(r"^/opus/(\d+)", re.IGNORECASE),
        re.compile(r"^/read/(cv\d+)", re.IGNORECASE),
    ),
    "kuaishou": (re.compile(r"^/short-video/([^/?#]+)", re.IGNORECASE),),
}


def resolve_content_identity(
    *,
    platform: str,
    canonical_url: object,
    source_article_id: object,
) -> ContentIdentity:
    """按 native ID → 文章编号 → normalized URL SHA-256 的顺序解析稳定身份。

    Provider 可直接消费的 ID/分享链接只写入 typed ``alternate_ids``；无法证明可用于
    Provider lookup 的 URL 仍可作为数据库稳定身份来源，但不会因此获得补采资格。
    """

    article_id = _identifier_text(source_article_id)
    normalized_url = normalize_http_url(canonical_url)
    native_id = _native_content_id(platform=platform, normalized_url=normalized_url)
    lookup_ids = _provider_lookup_ids(
        platform=platform,
        normalized_url=normalized_url,
        native_id=native_id,
    )
    alternate_ids = dict(lookup_ids)
    if article_id is not None:
        alternate_ids["source_article_id"] = article_id

    if native_id is not None:
        external_content_id = _normalize_native_external_id(platform, native_id)
        return ContentIdentity(external_content_id, alternate_ids, normalized_url)
    if article_id is not None:
        return ContentIdentity(article_id, alternate_ids, normalized_url)
    if normalized_url is not None:
        digest = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
        return ContentIdentity(f"url_sha256:{digest}", alternate_ids, normalized_url)
    raise ExcelImportRowError(
        "content_identity_missing",
        "无法从平台原生 URL、文章编号或规范化 URL 构造稳定内容身份",
    )


def normalize_http_url(value: object) -> str | None:
    """验证 HTTP(S) URL，移除 fragment，并稳定 scheme/host/default port。"""

    text = _optional_text(value)
    if text is None:
        return None
    try:
        parts = urlsplit(text)
        scheme = parts.scheme.casefold()
        hostname = parts.hostname.casefold() if parts.hostname is not None else None
        port = parts.port
    except ValueError as exc:
        raise ExcelImportRowError("canonical_url_invalid", "原文链接不是合法 HTTP(S) URL") from exc
    if scheme not in {"http", "https"} or hostname is None:
        raise ExcelImportRowError("canonical_url_invalid", "原文链接不是合法 HTTP(S) URL")
    if parts.username is not None or parts.password is not None:
        raise ExcelImportRowError("canonical_url_invalid", "原文链接不得包含用户凭据")

    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    return urlunsplit((scheme, netloc, parts.path, parts.query, ""))


def _native_content_id(*, platform: str, normalized_url: str | None) -> str | None:
    if normalized_url is None:
        return None
    suffixes = _HOST_SUFFIXES.get(platform)
    patterns = _NATIVE_PATH_PATTERNS.get(platform)
    if suffixes is None or patterns is None:
        return None
    parts = urlsplit(normalized_url)
    hostname = (parts.hostname or "").casefold()
    if not _host_matches(hostname, suffixes):
        return None
    for pattern in patterns:
        match = pattern.match(parts.path)
        if match is not None:
            return match.group(1)
    return None


def _provider_lookup_ids(
    *,
    platform: str,
    normalized_url: str | None,
    native_id: str | None,
) -> dict[str, str]:
    """返回已经能证明可供当前 TikHub 入口消费的 typed lookup identity。"""

    if native_id is not None:
        if platform == "xiaohongshu":
            return {"note_id": native_id}
        if platform == "douyin" and native_id.isdigit():
            return {"aweme_id": native_id}
        if platform == "weibo" and native_id.isdigit():
            return {"status_id": native_id}
        if platform == "bilibili":
            lowered = native_id.casefold()
            if lowered.startswith("bv"):
                return {"bv_id": native_id}
            if lowered.startswith("av") and native_id[2:].isdigit():
                return {"av_id": native_id[2:]}
        if platform == "kuaishou":
            return {"photo_id": native_id}

    if normalized_url is None:
        return {}
    parts = urlsplit(normalized_url)
    hostname = (parts.hostname or "").casefold()

    # TikHub 小红书 App V2 Detail/Comments 原生支持 share_text，短链无需先付费解析 ID。
    if platform == "xiaohongshu" and _host_matches(
        hostname, ("xhslink.com", "xhslink.cn")
    ):
        return {"share_text": normalized_url}

    # 其余平台的分享链接先保留类型，只有对应 Runtime 已验证后才会成为付费补采资格。
    if platform == "douyin" and hostname == "v.douyin.com":
        return {"douyin_share_url": normalized_url}
    if platform == "bilibili" and hostname == "b23.tv":
        return {"bilibili_share_url": normalized_url}
    if platform == "kuaishou" and hostname == "v.kuaishou.com":
        return {"kuaishou_share_url": normalized_url}
    return {}


def _normalize_native_external_id(platform: str, native_id: str) -> str:
    if platform == "bilibili" and native_id.casefold().startswith("av") and native_id[2:].isdigit():
        return native_id[2:]
    return native_id


def _host_matches(hostname: str, suffixes: tuple[str, ...]) -> bool:
    return any(hostname == suffix or hostname.endswith(f".{suffix}") for suffix in suffixes)


def _identifier_text(value: object) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return str(int(value)) if value.is_integer() else format(value, ".15g")
    return _optional_text(value)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
