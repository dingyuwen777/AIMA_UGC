"""Stage 7 TikHub 五平台 Search 真实 Fixture 获取探针。

本脚本只用于显式人工兼容性验证：
- Secret 只从环境变量读取，不写日志、请求快照或输出文件；
- 请求结构复用生产 TikHub Operation builder；
- 不做隐藏重试；
- 真实响应只在内存中存在，落盘前必须递归脱敏；
- pricing 与 search 分两阶段运行，search 需要外部显式放行。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
from aima_ugc.adapters.providers.tikhub.operations.bilibili import (
    build_search_request as build_bilibili_search_request,
)
from aima_ugc.adapters.providers.tikhub.operations.douyin import build_video_search_request
from aima_ugc.adapters.providers.tikhub.operations.kuaishou import (
    build_search_request as build_kuaishou_search_request,
)
from aima_ugc.adapters.providers.tikhub.operations.weibo import (
    build_search_request as build_weibo_search_request,
)
from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import build_search_notes_request

BASE_URL = "https://api.tikhub.io"
KEYWORD = "爱玛"
ENDPOINT_INFO_PATH = "/api/v1/tikhub/user/get_endpoint_info"
CALCULATE_PRICE_PATH = "/api/v1/tikhub/user/calculate_price"

_SECRET_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "signature",
    "token",
    "xsec",
)
_TEXT_KEYS = {
    "author",
    "bio",
    "content",
    "desc",
    "description",
    "name",
    "nick_name",
    "nickname",
    "remark",
    "signature",
    "text",
    "title",
    "user_name",
    "username",
}
_ID_KEYS = {
    "aid",
    "aweme_id",
    "bvid",
    "cid",
    "comment_id",
    "id",
    "mid",
    "note_id",
    "photo_id",
    "sec_uid",
    "uid",
    "user_id",
    "userid",
}
_ID_KEY_SUFFIXES = ("_id", "id_str")
_TIME_KEY_PARTS = ("create_time", "publish_time", "timestamp", "time_stamp", "update_time")
_SAFE_SHORT_STRING_KEYS = {
    "code",
    "content_type",
    "format",
    "has_more",
    "message",
    "message_zh",
    "method",
    "mode",
    "platform",
    "router",
    "schema_version",
    "search_type",
    "status",
    "status_code",
    "time_zone",
    "type",
}
_ASCII_ENUM = re.compile(r"^[A-Za-z0-9_.:/ -]{1,80}$")


@dataclass(frozen=True, slots=True)
class SearchProbeRequest:
    """由生产 Operation builder 生成的单页 Search 请求。"""

    platform: str
    method: Literal["GET", "POST"]
    path: str
    params: dict[str, object]
    body: dict[str, object] | None = None


class _Pseudonymizer:
    """在单个响应内稳定替换 ID，不保留真实值。"""

    def __init__(self) -> None:
        self._string_ids: dict[str, str] = {}
        self._number_ids: dict[str, int] = {}

    def identifier(self, value: object) -> object:
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, int):
            key = str(value)
            if key not in self._number_ids:
                self._number_ids[key] = 100_000 + len(self._number_ids) + 1
            return self._number_ids[key]
        if isinstance(value, float):
            key = repr(value)
            if key not in self._number_ids:
                self._number_ids[key] = 100_000 + len(self._number_ids) + 1
            return self._number_ids[key]
        text = str(value)
        if text not in self._string_ids:
            self._string_ids[text] = f"id-{len(self._string_ids) + 1:04d}"
        return self._string_ids[text]


def _search_requests() -> tuple[SearchProbeRequest, ...]:
    xhs = build_search_notes_request(
        keyword=KEYWORD,
        page=1,
        sort_type="general",
        time_filter="不限",
    )
    douyin = build_video_search_request(keyword=KEYWORD)
    weibo = build_weibo_search_request(keyword=KEYWORD, page=1, search_mode="latest")
    bilibili = build_bilibili_search_request(keyword=KEYWORD)
    kuaishou = build_kuaishou_search_request(keyword=KEYWORD)
    return (
        SearchProbeRequest("xhs", "GET", xhs.path, dict(xhs.params)),
        SearchProbeRequest(
            "douyin",
            douyin.method,
            douyin.path,
            dict(douyin.params),
            None if douyin.body is None else dict(douyin.body),
        ),
        SearchProbeRequest(
            "weibo",
            weibo.method,
            weibo.path,
            dict(weibo.params),
            None if weibo.body is None else dict(weibo.body),
        ),
        SearchProbeRequest(
            "bilibili",
            bilibili.method,
            bilibili.path,
            dict(bilibili.params),
            None if bilibili.body is None else dict(bilibili.body),
        ),
        SearchProbeRequest(
            "kuaishou",
            kuaishou.method,
            kuaishou.path,
            dict(kuaishou.params),
            None if kuaishou.body is None else dict(kuaishou.body),
        ),
    )


def _required_token() -> str:
    token = os.environ.get("AIMA_TIKHUB_PROBE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("AIMA_TIKHUB_PROBE_TOKEN 未设置")
    return token


def _output_dir() -> Path:
    raw = os.environ.get("AIMA_TIKHUB_PROBE_OUTPUT_DIR", "").strip()
    if not raw:
        raise RuntimeError("AIMA_TIKHUB_PROBE_OUTPUT_DIR 未设置")
    output = Path(raw)
    output.mkdir(parents=True, exist_ok=True)
    return output


def _client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "AIMA_UGC-stage7-fixture-probe/1.0",
        },
        timeout=httpx.Timeout(45.0),
        follow_redirects=False,
        trust_env=False,
    )


def _request_json(
    client: httpx.Client,
    *,
    method: str,
    path: str,
    params: dict[str, object] | None = None,
    body: dict[str, object] | None = None,
) -> tuple[int, Any]:
    response = client.request(method, path, params=params, json=body)
    try:
        parsed: Any = response.json()
    except ValueError as exc:
        raise RuntimeError(f"TikHub {path} 返回非 JSON 响应，HTTP {response.status_code}") from exc
    return response.status_code, parsed


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _normalized_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _is_identifier_key(key: str) -> bool:
    normalized = _normalized_key(key)
    return normalized in _ID_KEYS or normalized.endswith(_ID_KEY_SUFFIXES)


def _is_time_key(key: str) -> bool:
    normalized = _normalized_key(key)
    if normalized in {"time_zone", "timezone"}:
        return False
    return any(part in normalized for part in _TIME_KEY_PARTS)


def _sanitize_scalar(key: str, value: object, pseudonyms: _Pseudonymizer) -> object:
    normalized = _normalized_key(key)
    if any(part in normalized for part in _SECRET_KEY_PARTS):
        return "<redacted-secret>"
    if _is_identifier_key(key):
        return pseudonyms.identifier(value)
    if _is_time_key(key):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return 1_720_000_000
        if isinstance(value, str):
            return "2026-08-16T00:00:00Z"
        return value
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            return "https://example.invalid/redacted"
        if normalized in _TEXT_KEYS:
            return "<redacted-text>"
        if normalized in _SAFE_SHORT_STRING_KEYS and len(value) <= 160:
            return value
        if _ASCII_ENUM.fullmatch(value):
            return value
        if value == KEYWORD:
            return value
        return "<redacted-text>"
    return value


def sanitize_json(
    value: object, *, key: str = "root", pseudonyms: _Pseudonymizer | None = None
) -> object:
    """保留 JSON 字段、容器形状和非识别数值，删除 Secret/PII/URL/真实 ID。"""
    active = pseudonyms or _Pseudonymizer()
    if isinstance(value, dict):
        return {
            str(child_key): sanitize_json(child_value, key=str(child_key), pseudonyms=active)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_json(item, key=key, pseudonyms=active) for item in value]
    return _sanitize_scalar(key, value, active)


def _nonempty_list_paths(value: object, *, prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            paths.extend(_nonempty_list_paths(child, prefix=f"{prefix}.{key}"))
    elif isinstance(value, list):
        if value:
            paths.append(prefix)
        for index, child in enumerate(value[:3]):
            paths.extend(_nonempty_list_paths(child, prefix=f"{prefix}[{index}]"))
    return paths


def run_pricing_probe() -> None:
    """获取五个 Search endpoint 的 endpoint-info 与单请求查价，不执行平台搜索。"""
    output = _output_dir()
    token = _required_token()
    manifest: list[dict[str, object]] = []
    with _client(token) as client:
        for request in _search_requests():
            info_status, info_body = _request_json(
                client,
                method="GET",
                path=ENDPOINT_INFO_PATH,
                params={"endpoint": request.path},
            )
            price_status, price_body = _request_json(
                client,
                method="GET",
                path=CALCULATE_PRICE_PATH,
                params={"endpoint": request.path, "request_per_day": 1},
            )
            safe_info = sanitize_json(info_body)
            safe_price = sanitize_json(price_body)
            _write_json(output / request.platform / "endpoint_info.sanitized.json", safe_info)
            _write_json(output / request.platform / "price_for_one.sanitized.json", safe_price)
            manifest.append(
                {
                    "platform": request.platform,
                    "endpoint": request.path,
                    "endpoint_info_http_status": info_status,
                    "calculate_price_http_status": price_status,
                }
            )
    _write_json(
        output / "manifest.json",
        {
            "schema_version": "stage7-tikhub-pricing-probe.v1",
            "base_url": BASE_URL,
            "keyword": KEYWORD,
            "requests": manifest,
        },
    )


def run_search_probe() -> None:
    """在外部已核验查价并显式放行后，各执行一次真实 Search 请求。"""
    if os.environ.get("AIMA_TIKHUB_PROBE_PRICING_APPROVED") != "yes":
        raise RuntimeError("真实 Search Probe 必须在 pricing 证据人工核验后显式放行")
    output = _output_dir()
    token = _required_token()
    manifest: list[dict[str, object]] = []
    with _client(token) as client:
        for request in _search_requests():
            status, body = _request_json(
                client,
                method=request.method,
                path=request.path,
                params=request.params,
                body=request.body,
            )
            safe_body = sanitize_json(body)
            _write_json(output / request.platform / "search_page1.sanitized.json", safe_body)
            manifest.append(
                {
                    "platform": request.platform,
                    "method": request.method,
                    "endpoint": request.path,
                    "http_status": status,
                    "nonempty_list_paths": _nonempty_list_paths(safe_body),
                }
            )
    _write_json(
        output / "manifest.json",
        {
            "schema_version": "stage7-tikhub-search-probe.v1",
            "base_url": BASE_URL,
            "keyword": KEYWORD,
            "max_search_requests": len(_search_requests()),
            "hidden_retries": 0,
            "requests": manifest,
        },
    )


def main() -> None:
    mode = os.environ.get("AIMA_TIKHUB_PROBE_MODE", "").strip()
    if mode == "pricing":
        run_pricing_probe()
        return
    if mode == "search":
        run_search_probe()
        return
    raise RuntimeError("AIMA_TIKHUB_PROBE_MODE 只允许 pricing 或 search")


if __name__ == "__main__":
    main()
