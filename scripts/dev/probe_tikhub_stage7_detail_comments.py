"""Stage 7 TikHub 五平台 Detail/Comments 最小真实结构探针。

每个平台只取足够串起一次 Detail 与一级 Comments 的最小样本；小红书额外分别验证
图文和视频详情。真实内容、账号和 ID 只在 Runner 内存中使用，输出时字符串默认全部替换。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
from aima_ugc.adapters.providers.tikhub.operations import (
    bilibili,
    douyin,
    kuaishou,
    weibo,
    xiaohongshu,
)
from aima_ugc.adapters.providers.tikhub.pricing import load_tikhub_pricing

BASE_URL = "https://api.tikhub.io"
KEYWORD = "爱玛"
_MAX_LIST_ITEMS = 2


@dataclass(frozen=True, slots=True)
class ProbeRequest:
    label: str
    method: Literal["GET", "POST"]
    path: str
    params: dict[str, object]
    body: dict[str, object] | None = None


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
            "User-Agent": "AIMA_UGC-stage7-detail-comments-probe/1.0",
        },
        timeout=httpx.Timeout(45.0),
        follow_redirects=False,
        trust_env=False,
    )


def _sanitize(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _sanitize(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_sanitize(child) for child in value[:_MAX_LIST_ITEMS]]
    if isinstance(value, str):
        return "<redacted-string>"
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _send(
    client: httpx.Client,
    request: ProbeRequest,
    *,
    output: Path,
    manifest: list[dict[str, object]],
) -> Any:
    """单次发送；先由生产 Pricing Catalog 证明该 endpoint 已核验价格。"""
    billing = load_tikhub_pricing().billing_for_endpoint(request.path)
    response = client.request(
        request.method,
        request.path,
        params=request.params,
        json=request.body,
    )
    try:
        body: Any = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{request.label} 返回非 JSON，HTTP {response.status_code}") from exc
    _write_json(output / f"{request.label}.sanitized.json", _sanitize(body))
    manifest.append(
        {
            "label": request.label,
            "method": request.method,
            "endpoint": request.path,
            "http_status": response.status_code,
            "planned_unit_price": str(billing.unit_price_snapshot),
        }
    )
    if response.status_code >= 400:
        raise RuntimeError(f"{request.label} HTTP {response.status_code}")
    return body


def _get(path: str, params: dict[str, object], label: str) -> ProbeRequest:
    return ProbeRequest(label=label, method="GET", path=path, params=params)


def _from_request(request: Any, label: str) -> ProbeRequest:
    method = request.method
    if method not in {"GET", "POST"}:
        raise ValueError("Probe 只允许 GET/POST")
    return ProbeRequest(label, method, str(request.path), dict(request.params), request.body)


def _first_xhs_note(body: dict[str, Any]) -> dict[str, Any]:
    items = xiaohongshu.extract_search_items(body)
    if not items:
        raise RuntimeError("小红书搜索未取得非空 note")
    note = items[0].get("note")
    if not isinstance(note, dict):
        raise RuntimeError("小红书搜索 item 缺少 note")
    return note


def _first_douyin_aweme(body: dict[str, Any]) -> dict[str, Any]:
    items = douyin.extract_search_items(body)
    if not items:
        raise RuntimeError("抖音搜索未取得非空 aweme")
    data = items[0].get("data")
    aweme = data.get("aweme_info") if isinstance(data, dict) else None
    if not isinstance(aweme, dict):
        raise RuntimeError("抖音搜索 item 缺少 data.aweme_info")
    return aweme


def _first_weibo_status(body: dict[str, Any]) -> dict[str, Any]:
    items = weibo.extract_search_items(body)
    if not items:
        raise RuntimeError("微博搜索未取得非空 mblog")
    status = items[0].get("mblog")
    if not isinstance(status, dict):
        raise RuntimeError("微博搜索 card 缺少 mblog")
    return status


def _first_bilibili_item(body: dict[str, Any]) -> dict[str, Any]:
    items = bilibili.extract_search_items(body)
    if not items:
        raise RuntimeError("B站搜索未取得非空视频")
    return items[0]


def _first_kuaishou_feed(body: dict[str, Any]) -> dict[str, Any]:
    items = kuaishou.extract_search_items(body)
    if not items:
        raise RuntimeError("快手搜索未取得非空作品")
    feed = items[0].get("feed")
    if not isinstance(feed, dict):
        raise RuntimeError("快手搜索 item 缺少 feed")
    return feed


def run() -> None:
    output = _output_dir()
    manifest: list[dict[str, object]] = []
    with _client(_required_token()) as client:
        image_search = xiaohongshu.build_search_notes_request(
            keyword=KEYWORD,
            page=1,
            sort_type="comment_descending",
            time_filter="不限",
            note_type="普通笔记",
        )
        image_search_body = _send(
            client,
            _get(image_search.path, dict(image_search.params), "xhs_search_image"),
            output=output,
            manifest=manifest,
        )
        image_note_id = str(_first_xhs_note(image_search_body)["id"])
        image_detail = xiaohongshu.build_image_detail_request(note_id=image_note_id)
        _send(
            client,
            _get(image_detail.path, dict(image_detail.params), "xhs_image_detail"),
            output=output,
            manifest=manifest,
        )
        xhs_comments = xiaohongshu.build_note_comments_request(note_id=image_note_id)
        _send(
            client,
            _get(xhs_comments.path, dict(xhs_comments.params), "xhs_comments"),
            output=output,
            manifest=manifest,
        )

        video_search = xiaohongshu.build_search_notes_request(
            keyword=KEYWORD,
            page=1,
            sort_type="general",
            time_filter="不限",
            note_type="视频笔记",
        )
        video_search_body = _send(
            client,
            _get(video_search.path, dict(video_search.params), "xhs_search_video"),
            output=output,
            manifest=manifest,
        )
        video_note_id = str(_first_xhs_note(video_search_body)["id"])
        video_detail = xiaohongshu.build_video_detail_request(note_id=video_note_id)
        _send(
            client,
            _get(video_detail.path, dict(video_detail.params), "xhs_video_detail"),
            output=output,
            manifest=manifest,
        )

        douyin_search = douyin.build_video_search_request(keyword=KEYWORD)
        douyin_search_body = _send(
            client,
            _from_request(douyin_search, "douyin_search"),
            output=output,
            manifest=manifest,
        )
        aweme_id = str(_first_douyin_aweme(douyin_search_body)["aweme_id"])
        _send(
            client,
            _from_request(douyin.build_video_detail_request(aweme_id=aweme_id), "douyin_detail"),
            output=output,
            manifest=manifest,
        )
        _send(
            client,
            _from_request(
                douyin.build_video_comments_request(aweme_id=aweme_id), "douyin_comments"
            ),
            output=output,
            manifest=manifest,
        )

        weibo_search = weibo.build_search_request(keyword=KEYWORD, search_mode="hot")
        weibo_search_body = _send(
            client,
            _from_request(weibo_search, "weibo_search"),
            output=output,
            manifest=manifest,
        )
        status_id = str(_first_weibo_status(weibo_search_body)["id"])
        _send(
            client,
            _from_request(weibo.build_status_detail_request(status_id=status_id), "weibo_detail"),
            output=output,
            manifest=manifest,
        )
        _send(
            client,
            _from_request(
                weibo.build_status_comments_request(status_id=status_id), "weibo_comments"
            ),
            output=output,
            manifest=manifest,
        )

        bilibili_search = bilibili.build_search_request(keyword=KEYWORD)
        bilibili_search_body = _send(
            client,
            _from_request(bilibili_search, "bilibili_search"),
            output=output,
            manifest=manifest,
        )
        av_id = str(_first_bilibili_item(bilibili_search_body)["param"])
        _send(
            client,
            _from_request(bilibili.build_video_detail_request(av_id=av_id), "bilibili_detail"),
            output=output,
            manifest=manifest,
        )
        _send(
            client,
            _from_request(
                bilibili.build_video_comments_request(av_id=av_id), "bilibili_comments"
            ),
            output=output,
            manifest=manifest,
        )

        kuaishou_search = kuaishou.build_search_request(keyword=KEYWORD)
        kuaishou_search_body = _send(
            client,
            _from_request(kuaishou_search, "kuaishou_search"),
            output=output,
            manifest=manifest,
        )
        photo_id = str(_first_kuaishou_feed(kuaishou_search_body)["photo_id"])
        _send(
            client,
            _from_request(kuaishou.build_video_detail_request(photo_id=photo_id), "kuaishou_detail"),
            output=output,
            manifest=manifest,
        )
        _send(
            client,
            _from_request(
                kuaishou.build_video_comments_request(photo_id=photo_id), "kuaishou_comments"
            ),
            output=output,
            manifest=manifest,
        )

    _write_json(
        output / "manifest.json",
        {
            "schema_version": "stage7-tikhub-detail-comments-probe.v1",
            "base_url": BASE_URL,
            "keyword": KEYWORD,
            "hidden_retries": 0,
            "max_list_items_per_array": _MAX_LIST_ITEMS,
            "request_count": len(manifest),
            "requests": manifest,
        },
    )


if __name__ == "__main__":
    run()
