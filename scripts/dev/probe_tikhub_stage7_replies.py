"""Stage 7 TikHub 五平台二级评论/回复 endpoint 最小真实结构探针。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

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
_ID_KEYS = {
    "id",
    "idstr",
    "mid",
    "uid",
    "cid",
    "rid",
    "root",
    "rootid",
    "rootidstr",
    "aweme_id",
    "note_id",
    "photo_id",
    "comment_id",
    "user_id",
    "author_id",
    "sec_uid",
    "bvid",
    "aid",
    "rpid",
    "rpid_str",
    "parent",
    "parent_str",
    "dialog",
    "dialog_str",
}


class _Sanitizer:
    def __init__(self) -> None:
        self._strings: dict[str, str] = {}
        self._numbers: dict[str, int] = {}

    def value(self, value: object, *, key: str = "root") -> object:
        normalized = key.lower().replace("-", "_")
        if isinstance(value, dict):
            return {str(k): self.value(v, key=str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [self.value(v, key=key) for v in value[:_MAX_LIST_ITEMS]]
        if normalized in _ID_KEYS or normalized.endswith("_id"):
            return self._identifier(value)
        if isinstance(value, str):
            return "<redacted-string>"
        return value

    def _identifier(self, value: object) -> object:
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            raw = repr(value)
            if raw not in self._numbers:
                self._numbers[raw] = 100_000 + len(self._numbers) + 1
            return self._numbers[raw]
        raw = str(value)
        if raw not in self._strings:
            self._strings[raw] = f"id-{len(self._strings) + 1:04d}"
        return self._strings[raw]


def _token() -> str:
    value = os.environ.get("AIMA_TIKHUB_PROBE_TOKEN", "").strip()
    if not value:
        raise RuntimeError("AIMA_TIKHUB_PROBE_TOKEN 未设置")
    return value


def _output() -> Path:
    raw = os.environ.get("AIMA_TIKHUB_PROBE_OUTPUT_DIR", "").strip()
    if not raw:
        raise RuntimeError("AIMA_TIKHUB_PROBE_OUTPUT_DIR 未设置")
    output = Path(raw)
    output.mkdir(parents=True, exist_ok=True)
    return output


def _client() -> httpx.Client:
    token = _token()
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=httpx.Timeout(45.0),
        follow_redirects=False,
        trust_env=False,
    )


def _send(
    client: httpx.Client,
    *,
    label: str,
    method: str,
    path: str,
    params: dict[str, object],
    body: dict[str, object] | None,
    output: Path,
    manifest: list[dict[str, object]],
) -> dict[str, Any]:
    billing = load_tikhub_pricing().billing_for_endpoint(path)
    response = client.request(method, path, params=params, json=body)
    try:
        parsed = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{label} 返回非 JSON，HTTP {response.status_code}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{label} JSON 顶层不是对象")
    safe = _Sanitizer().value(parsed)
    (output / f"{label}.sanitized.json").write_text(
        json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest.append(
        {
            "label": label,
            "endpoint": path,
            "http_status": response.status_code,
            "planned_unit_price": str(billing.unit_price_snapshot),
        }
    )
    if response.status_code >= 400:
        raise RuntimeError(f"{label} HTTP {response.status_code}")
    return parsed


def _request_parts(request: Any) -> tuple[str, str, dict[str, object], dict[str, object] | None]:
    method = getattr(request, "method", "GET")
    body = getattr(request, "body", None)
    return method, str(request.path), dict(request.params), body


def _call_request(
    client: httpx.Client,
    request: Any,
    *,
    label: str,
    output: Path,
    manifest: list[dict[str, object]],
) -> dict[str, Any]:
    method, path, params, body = _request_parts(request)
    return _send(
        client,
        label=label,
        method=method,
        path=path,
        params=params,
        body=body,
        output=output,
        manifest=manifest,
    )


def _max_by(items: tuple[dict[str, Any], ...], value_fn: Any) -> dict[str, Any]:
    if not items:
        raise RuntimeError("真实搜索没有可用内容")
    return max(items, key=lambda item: int(value_fn(item) or 0))


def _xiaohongshu(client: httpx.Client, output: Path, manifest: list[dict[str, object]]) -> None:
    search = xiaohongshu.build_search_notes_request(
        keyword=KEYWORD,
        page=1,
        sort_type="comment_descending",
        time_filter="不限",
        note_type="普通笔记",
    )
    search_body = _call_request(
        client, search, label="xiaohongshu_search", output=output, manifest=manifest
    )
    items = xiaohongshu.extract_search_items(search_body)
    item = _max_by(
        items,
        lambda wrapped: (
            (wrapped.get("note") or {}).get("comments_count")
            if isinstance(wrapped.get("note"), dict)
            else 0
        ),
    )
    note = item.get("note")
    if not isinstance(note, dict):
        raise RuntimeError("小红书搜索 item 缺少 note")
    note_id = str(note["id"])
    comments_body = _call_request(
        client,
        xiaohongshu.build_note_comments_request(note_id=note_id),
        label="xiaohongshu_comments",
        output=output,
        manifest=manifest,
    )
    data = comments_body.get("data")
    data = data.get("data") if isinstance(data, dict) else None
    comments = data.get("comments") if isinstance(data, dict) else None
    if not isinstance(comments, list) or not comments:
        raise RuntimeError("小红书一级评论页为空，无法验证二级评论 endpoint")
    root = max(
        (item for item in comments if isinstance(item, dict)),
        key=lambda item: int(item.get("sub_comment_count") or 0),
    )
    comment_id = str(root["id"])
    _call_request(
        client,
        xiaohongshu.build_sub_comments_request(note_id=note_id, comment_id=comment_id),
        label="xiaohongshu_sub_comments",
        output=output,
        manifest=manifest,
    )


def _douyin(client: httpx.Client, output: Path, manifest: list[dict[str, object]]) -> None:
    search_body = _call_request(
        client,
        douyin.build_video_search_request(keyword=KEYWORD),
        label="douyin_search",
        output=output,
        manifest=manifest,
    )
    items = douyin.extract_search_items(search_body)
    item = _max_by(
        items,
        lambda wrapped: (
            ((wrapped.get("data") or {}).get("aweme_info") or {})
            .get("statistics", {})
            .get("comment_count")
            if isinstance(wrapped.get("data"), dict)
            else 0
        ),
    )
    data = item.get("data")
    aweme = data.get("aweme_info") if isinstance(data, dict) else None
    if not isinstance(aweme, dict):
        raise RuntimeError("抖音搜索 item 缺少 aweme_info")
    aweme_id = str(aweme["aweme_id"])
    comments_body = _call_request(
        client,
        douyin.build_video_comments_request(aweme_id=aweme_id),
        label="douyin_comments",
        output=output,
        manifest=manifest,
    )
    comments = comments_body.get("data", {}).get("comments")
    if not isinstance(comments, list) or not comments:
        raise RuntimeError("抖音一级评论页为空，无法验证回复 endpoint")
    root = max(
        (item for item in comments if isinstance(item, dict)),
        key=lambda item: int(item.get("reply_comment_total") or 0),
    )
    _call_request(
        client,
        douyin.build_video_comment_replies_request(
            item_id=aweme_id,
            comment_id=str(root["cid"]),
        ),
        label="douyin_replies",
        output=output,
        manifest=manifest,
    )


def _weibo(client: httpx.Client, output: Path, manifest: list[dict[str, object]]) -> None:
    search_body = _call_request(
        client,
        weibo.build_search_request(keyword=KEYWORD, search_mode="hot"),
        label="weibo_search",
        output=output,
        manifest=manifest,
    )
    items = weibo.extract_search_items(search_body)
    item = _max_by(
        items,
        lambda wrapped: (
            (wrapped.get("mblog") or {}).get("comments_count")
            if isinstance(wrapped.get("mblog"), dict)
            else 0
        ),
    )
    status = item.get("mblog")
    if not isinstance(status, dict):
        raise RuntimeError("微博搜索 item 缺少 mblog")
    status_id = str(status["id"])
    comments_body = _call_request(
        client,
        weibo.build_status_comments_request(status_id=status_id),
        label="weibo_comments",
        output=output,
        manifest=manifest,
    )
    items_raw = comments_body.get("data", {}).get("items")
    if not isinstance(items_raw, list) or not items_raw:
        raise RuntimeError("微博一级评论页为空，无法验证二级评论 endpoint")
    comments = [
        item["data"]
        for item in items_raw
        if isinstance(item, dict) and isinstance(item.get("data"), dict)
    ]
    root = max(comments, key=lambda item: int(item.get("total_number") or 0))
    root_id = str(root.get("idstr") or root["id"])
    _call_request(
        client,
        weibo.build_status_sub_comments_request(root_comment_id=root_id),
        label="weibo_sub_comments",
        output=output,
        manifest=manifest,
    )


def _bilibili(client: httpx.Client, output: Path, manifest: list[dict[str, object]]) -> None:
    search_body = _call_request(
        client,
        bilibili.build_search_request(keyword=KEYWORD),
        label="bilibili_search",
        output=output,
        manifest=manifest,
    )
    items = bilibili.extract_search_items(search_body)
    if not items:
        raise RuntimeError("B站搜索没有视频")
    selected: tuple[str, dict[str, Any]] | None = None
    for index, item in enumerate(items[:2]):
        av_id = str(item["param"])
        comments_body = _call_request(
            client,
            bilibili.build_video_comments_request(av_id=av_id, sort_mode="hot"),
            label=f"bilibili_comments_{index + 1}",
            output=output,
            manifest=manifest,
        )
        data = comments_body.get("data", {}).get("data")
        replies = data.get("replies") if isinstance(data, dict) else None
        if isinstance(replies, list) and replies:
            selected = (av_id, replies[0])
            break
    if selected is None:
        raise RuntimeError("B站最多两个候选评论页都为空，无法安全构造 reply_detail root")
    av_id, root = selected
    root_id = root.get("rpid_str") or root.get("rpid")
    if root_id is None:
        raise RuntimeError("B站真实一级评论缺少 rpid/rpid_str")
    _call_request(
        client,
        bilibili.build_reply_detail_request(root=str(root_id), av_id=av_id),
        label="bilibili_replies",
        output=output,
        manifest=manifest,
    )


def _kuaishou(client: httpx.Client, output: Path, manifest: list[dict[str, object]]) -> None:
    search_body = _call_request(
        client,
        kuaishou.build_search_request(keyword=KEYWORD),
        label="kuaishou_search",
        output=output,
        manifest=manifest,
    )
    items = kuaishou.extract_search_items(search_body)
    item = _max_by(
        items,
        lambda wrapped: (
            (wrapped.get("feed") or {}).get("comment_count")
            if isinstance(wrapped.get("feed"), dict)
            else 0
        ),
    )
    feed = item.get("feed")
    if not isinstance(feed, dict):
        raise RuntimeError("快手搜索 item 缺少 feed")
    photo_id = str(feed["photo_id"])
    comments_body = _call_request(
        client,
        kuaishou.build_video_comments_request(photo_id=photo_id),
        label="kuaishou_comments",
        output=output,
        manifest=manifest,
    )
    comments = comments_body.get("data", {}).get("rootComments")
    if not isinstance(comments, list) or not comments:
        raise RuntimeError("快手一级评论页为空，无法验证二级评论 endpoint")
    root = next(item for item in comments if isinstance(item, dict))
    _call_request(
        client,
        kuaishou.build_video_sub_comments_request(
            photo_id=photo_id,
            root_comment_id=str(root["comment_id"]),
        ),
        label="kuaishou_sub_comments",
        output=output,
        manifest=manifest,
    )


def main() -> None:
    output = _output()
    manifest: list[dict[str, object]] = []
    with _client() as client:
        _xiaohongshu(client, output, manifest)
        _douyin(client, output, manifest)
        _weibo(client, output, manifest)
        _bilibili(client, output, manifest)
        _kuaishou(client, output, manifest)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "stage7-tikhub-replies-probe.v1",
                "base_url": BASE_URL,
                "keyword": KEYWORD,
                "hidden_retries": 0,
                "request_count": len(manifest),
                "requests": manifest,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
