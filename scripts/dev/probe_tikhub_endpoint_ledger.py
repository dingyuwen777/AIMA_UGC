"""五平台 TikHub 正式主链真实 Request/Response 证据采集。

本脚本只用于显式、受限的真实 Probe：
- 复用生产 Operation builder、TikHubOperationProbe、TikHubHttpTransport 与 Pricing；
- 关键词固定为“爱玛”，只取足够串起 Search → Detail → Comments → Replies 的最小样本；
- Raw 只存在于 Runner 内存；落盘前严格去标识化；
- 每个 endpoint 同时保存脱敏 request、脱敏 response 和完整 Raw 的 JSON 路径/类型清单。
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from aima_ugc.adapters.providers.tikhub.operations import (
    bilibili,
    douyin,
    kuaishou,
    weibo,
    xiaohongshu,
)
from aima_ugc.adapters.providers.tikhub.probe import (
    TikHubOperationProbe,
    TikHubProbeLimits,
)
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from pydantic import SecretStr

BASE_URL = "https://api.tikhub.io"
KEYWORD = "爱玛"
MAX_LIST_ITEMS = 3
MAX_REQUESTS = 25
MAX_ESTIMATED_COST = Decimal("0.150000")

_SAFE_ENUM_KEYS = {
    "code",
    "content_type",
    "currency",
    "format",
    "goto",
    "has_more",
    "method",
    "mode",
    "note_type",
    "operation",
    "platform",
    "result",
    "schema_version",
    "search_type",
    "sort_type",
    "status",
    "status_code",
    "time_filter",
    "time_zone",
    "type",
    "unit",
}
_ID_KEYS = {
    "aid",
    "author_id",
    "aweme_id",
    "bvid",
    "cid",
    "comment_id",
    "dialog",
    "dialog_str",
    "fid",
    "id",
    "id_str",
    "idstr",
    "mid",
    "note_id",
    "oid",
    "param",
    "parent",
    "parent_str",
    "photo_id",
    "rid",
    "root",
    "rootid",
    "rootidstr",
    "rpid",
    "rpid_str",
    "sec_uid",
    "short_id",
    "spread_id",
    "uid",
    "user_id",
}
_STATE_KEY_PARTS = (
    "backtrace",
    "cursor",
    "lfid",
    "llsid",
    "request_id",
    "search_id",
    "search_session_id",
    "search_ssid",
    "search_vsid",
    "seid",
    "session",
    "trace",
    "trackid",
)
_SECRET_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "signature",
    "token",
    "xsec",
)
_TIME_KEY_PARTS = (
    "create_time",
    "ctime",
    "publish_time",
    "pubdate",
    "ptime",
    "senddate",
    "timestamp",
    "time_stamp",
    "update_time",
)
_SAFE_ENUM_VALUE = re.compile(r"^[A-Za-z0-9_. -]{1,80}$")


class Pseudonymizer:
    """同一平台一次 Probe 内稳定替换字符串/数值标识。"""

    def __init__(self) -> None:
        self._strings: dict[str, str] = {}
        self._numbers: dict[str, int] = {}

    def identifier(self, value: object) -> object:
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


def _normalized_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _is_secret_key(key: str) -> bool:
    normalized = _normalized_key(key)
    return any(part in normalized for part in _SECRET_KEY_PARTS)


def _is_time_key(key: str) -> bool:
    normalized = _normalized_key(key)
    if normalized in {"time_zone", "timezone"}:
        return False
    return any(part in normalized for part in _TIME_KEY_PARTS)


def _is_identifier_key(key: str) -> bool:
    normalized = _normalized_key(key)
    if normalized in _ID_KEYS:
        return True
    if normalized.endswith(("_id", "_ids", "idstr", "_id_str")):
        return True
    return any(part in normalized for part in _STATE_KEY_PARTS)


def sanitize_response(
    value: object,
    *,
    key: str = "root",
    pseudonyms: Pseudonymizer,
) -> object:
    """字段/类型保留，直接标识、资源定位值、文本与技术状态值去标识化。"""
    if isinstance(value, dict):
        return {
            str(child_key): sanitize_response(
                child_value,
                key=str(child_key),
                pseudonyms=pseudonyms,
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            sanitize_response(item, key=key, pseudonyms=pseudonyms)
            for item in value[:MAX_LIST_ITEMS]
        ]
    if _is_secret_key(key):
        return "<redacted-secret>"
    if _is_time_key(key):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return 1_720_000_000
        if isinstance(value, str):
            return "<redacted-time>"
        return value
    if _is_identifier_key(key):
        return pseudonyms.identifier(value)
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and abs(value) >= 10_000_000_000
    ):
        return pseudonyms.identifier(value)
    if isinstance(value, str):
        if len(value) >= 11 and value.isdigit():
            return pseudonyms.identifier(value)
        if value == KEYWORD:
            return value
        normalized = _normalized_key(key)
        if normalized in {"router", "endpoint", "path"} and value.startswith("/api/"):
            return value
        if normalized in _SAFE_ENUM_KEYS and _SAFE_ENUM_VALUE.fullmatch(value):
            return value
        return "<redacted-string>"
    return value


def sanitize_request_value(
    value: object,
    *,
    key: str = "root",
    pseudonyms: Pseudonymizer,
) -> object:
    """请求业务枚举保留原值，动态身份/游标/会话/Secret 必须去标识化。"""
    if isinstance(value, dict):
        return {
            str(child_key): sanitize_request_value(
                child_value,
                key=str(child_key),
                pseudonyms=pseudonyms,
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            sanitize_request_value(item, key=key, pseudonyms=pseudonyms)
            for item in value[:MAX_LIST_ITEMS]
        ]
    if _is_secret_key(key):
        return "<redacted-secret>"
    if _is_identifier_key(key):
        return pseudonyms.identifier(value)
    return value


def observed_path_types(value: object) -> list[dict[str, object]]:
    """从完整 Raw 提取所有已观察 JSON 路径/类型，不保存对应值。"""
    observed: dict[str, set[str]] = {}

    def visit(current: object, path: str) -> None:
        observed.setdefault(path, set()).add(_json_type(current))
        if isinstance(current, dict):
            for child_key, child_value in current.items():
                visit(child_value, f"{path}.{child_key}")
        elif isinstance(current, list):
            for child in current:
                visit(child, f"{path}[]")

    visit(value, "$")
    return [{"path": path, "types": sorted(types)} for path, types in sorted(observed.items())]


def _json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} 未设置")
    return value


def _request_document(request: object, pseudonyms: Pseudonymizer) -> dict[str, object]:
    method = getattr(request, "method", "GET")
    path = getattr(request, "path", None)
    params = getattr(request, "params", None)
    body = getattr(request, "body", None)
    if method not in {"GET", "POST"} or not isinstance(path, str) or not isinstance(params, dict):
        raise ValueError("Operation Request 缺少合法 method/path/params")
    return {
        "method": method,
        "path": path,
        "params": sanitize_request_value(params, pseudonyms=pseudonyms),
        "body": sanitize_request_value(body, pseudonyms=pseudonyms),
        "authorization": "Bearer <redacted-secret>",
    }


def _capture(
    *,
    probe: TikHubOperationProbe,
    output: Path,
    platform: str,
    label: str,
    request: object,
    pseudonyms: Pseudonymizer,
    manifest: list[dict[str, object]],
) -> dict[str, Any]:
    request_doc = _request_document(request, pseudonyms)
    result = probe.execute(request)
    if result.response.status_code >= 400:
        raise RuntimeError(f"{platform}/{label} HTTP {result.response.status_code}")
    body = result.response.body
    if not isinstance(body, dict):
        raise RuntimeError(f"{platform}/{label} 响应顶层不是 JSON object")

    target = output / platform / label
    safe_response = sanitize_response(body, pseudonyms=pseudonyms)
    _write_json(target / "request.sanitized.json", request_doc)
    _write_json(target / "response.sanitized.json", safe_response)
    paths = observed_path_types(body)
    _write_json(target / "observed_paths.json", paths)
    manifest.append(
        {
            "platform": platform,
            "label": label,
            "method": request_doc["method"],
            "endpoint": result.path,
            "http_status": result.response.status_code,
            "request_no": result.request_no,
            "planned_cost_usd": str(result.planned_cost),
            "observed_path_count": len(paths),
            "evidence_dir": f"{platform}/{label}",
        }
    )
    return body


def _max_item(items: Iterable[dict[str, Any]], value_fn: Any) -> dict[str, Any]:
    values = tuple(items)
    if not values:
        raise RuntimeError("真实响应没有可用 item")
    return max(values, key=lambda item: int(value_fn(item) or 0))


def _xhs_note(wrapper: dict[str, Any]) -> dict[str, Any]:
    note = wrapper.get("note")
    if not isinstance(note, dict):
        raise RuntimeError("XHS Search item 缺少 note")
    return note


def _run_xhs(
    probe: TikHubOperationProbe,
    output: Path,
    pseudo: Pseudonymizer,
    manifest: list[dict[str, object]],
) -> None:
    search_body = _capture(
        probe=probe,
        output=output,
        platform="xhs",
        label="search_notes",
        request=xiaohongshu.build_search_notes_request(
            keyword=KEYWORD,
            page=1,
            sort_type="most_commented",
            time_filter="all",
            note_type="image",
        ),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    image_wrapper = _max_item(
        xiaohongshu.extract_search_items(search_body),
        lambda item: _xhs_note(item).get("comments_count") or 0,
    )
    image_note = _xhs_note(image_wrapper)
    image_note_id = str(image_note.get("id") or image_note.get("note_id") or "")
    if not image_note_id:
        raise RuntimeError("XHS 搜索缺少 note id")
    _capture(
        probe=probe,
        output=output,
        platform="xhs",
        label="image_detail",
        request=xiaohongshu.build_image_detail_request(note_id=image_note_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    comments_body = _capture(
        probe=probe,
        output=output,
        platform="xhs",
        label="comments",
        request=xiaohongshu.build_note_comments_request(note_id=image_note_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    root = _max_item(
        xiaohongshu.extract_comment_items(comments_body),
        lambda item: item.get("sub_comment_count") or len(item.get("sub_comments") or []),
    )
    root_id = str(root.get("id") or root.get("comment_id") or "")
    if not root_id:
        raise RuntimeError("XHS 一级评论缺少 id")
    _capture(
        probe=probe,
        output=output,
        platform="xhs",
        label="sub_comments",
        request=xiaohongshu.build_sub_comments_request(
            note_id=image_note_id,
            comment_id=root_id,
        ),
        pseudonyms=pseudo,
        manifest=manifest,
    )

    video_search = _capture(
        probe=probe,
        output=output,
        platform="xhs",
        label="search_notes_video_supporting",
        request=xiaohongshu.build_search_notes_request(
            keyword=KEYWORD,
            page=1,
            sort_type="general",
            time_filter="all",
            note_type="video",
        ),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    video_note = _xhs_note(_max_item(xiaohongshu.extract_search_items(video_search), lambda _: 0))
    video_note_id = str(video_note.get("id") or video_note.get("note_id") or "")
    if not video_note_id:
        raise RuntimeError("XHS 视频搜索缺少 note id")
    _capture(
        probe=probe,
        output=output,
        platform="xhs",
        label="video_detail",
        request=xiaohongshu.build_video_detail_request(note_id=video_note_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )


def _run_douyin(
    probe: TikHubOperationProbe,
    output: Path,
    pseudo: Pseudonymizer,
    manifest: list[dict[str, object]],
) -> None:
    search_body = _capture(
        probe=probe,
        output=output,
        platform="douyin",
        label="search",
        request=douyin.build_video_search_request(keyword=KEYWORD),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    wrapped = _max_item(
        douyin.extract_search_items(search_body),
        lambda item: (
            ((item.get("data") or {}).get("aweme_info") or {})
            .get("statistics", {})
            .get("comment_count", 0)
            if isinstance(item.get("data"), dict)
            else 0
        ),
    )
    data = wrapped.get("data")
    aweme = data.get("aweme_info") if isinstance(data, dict) else None
    if not isinstance(aweme, dict) or aweme.get("aweme_id") is None:
        raise RuntimeError("Douyin Search 缺少 aweme_id")
    aweme_id = str(aweme["aweme_id"])
    _capture(
        probe=probe,
        output=output,
        platform="douyin",
        label="detail",
        request=douyin.build_video_detail_request(aweme_id=aweme_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    comments_body = _capture(
        probe=probe,
        output=output,
        platform="douyin",
        label="comments",
        request=douyin.build_video_comments_request(aweme_id=aweme_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    root = _max_item(
        douyin.extract_comment_items(comments_body),
        lambda item: item.get("reply_comment_total") or 0,
    )
    comment_id = str(root.get("cid") or root.get("comment_id") or "")
    if not comment_id:
        raise RuntimeError("Douyin 一级评论缺少 cid")
    _capture(
        probe=probe,
        output=output,
        platform="douyin",
        label="replies",
        request=douyin.build_video_comment_replies_request(
            item_id=aweme_id,
            comment_id=comment_id,
        ),
        pseudonyms=pseudo,
        manifest=manifest,
    )


def _run_weibo(
    probe: TikHubOperationProbe,
    output: Path,
    pseudo: Pseudonymizer,
    manifest: list[dict[str, object]],
) -> None:
    search_body = _capture(
        probe=probe,
        output=output,
        platform="weibo",
        label="search",
        request=weibo.build_search_request(keyword=KEYWORD, search_mode="hot"),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    wrapped = _max_item(
        weibo.extract_search_items(search_body),
        lambda item: (
            (item.get("mblog") or {}).get("comments_count", 0)
            if isinstance(item.get("mblog"), dict)
            else 0
        ),
    )
    status = wrapped.get("mblog")
    if not isinstance(status, dict) or status.get("id") is None:
        raise RuntimeError("Weibo Search 缺少 status id")
    status_id = str(status["id"])
    _capture(
        probe=probe,
        output=output,
        platform="weibo",
        label="detail",
        request=weibo.build_status_detail_request(status_id=status_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    comments_body = _capture(
        probe=probe,
        output=output,
        platform="weibo",
        label="comments",
        request=weibo.build_status_comments_request(status_id=status_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    root = _max_item(
        weibo.extract_comment_items(comments_body),
        lambda item: item.get("total_number") or 0,
    )
    root_id = str(root.get("idstr") or root.get("id") or "")
    if not root_id:
        raise RuntimeError("Weibo 一级评论缺少 id")
    _capture(
        probe=probe,
        output=output,
        platform="weibo",
        label="sub_comments",
        request=weibo.build_status_sub_comments_request(root_comment_id=root_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )


def _run_bilibili(
    probe: TikHubOperationProbe,
    output: Path,
    pseudo: Pseudonymizer,
    manifest: list[dict[str, object]],
) -> None:
    search_body = _capture(
        probe=probe,
        output=output,
        platform="bilibili",
        label="search",
        request=bilibili.build_search_request(keyword=KEYWORD),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    items = bilibili.extract_search_items(search_body)
    if not items:
        raise RuntimeError("Bilibili Search 没有可用视频")
    selected: tuple[str, dict[str, Any]] | None = None
    for item in items[:3]:
        av_id_raw = item.get("param")
        if av_id_raw is None:
            continue
        av_id = str(av_id_raw)
        comments_body = _capture(
            probe=probe,
            output=output,
            platform="bilibili",
            label=f"comments_candidate_{len(manifest)}",
            request=bilibili.build_video_comments_request(av_id=av_id, sort_mode="hot"),
            pseudonyms=pseudo,
            manifest=manifest,
        )
        comments = bilibili.extract_comment_items(comments_body)
        if comments:
            selected = (av_id, comments[0])
            break
    if selected is None:
        raise RuntimeError("Bilibili 前三个搜索候选均没有一级评论")
    av_id, root = selected
    _capture(
        probe=probe,
        output=output,
        platform="bilibili",
        label="detail",
        request=bilibili.build_video_detail_request(av_id=av_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    root_id = str(root.get("rpid_str") or root.get("rpid") or "")
    if not root_id:
        raise RuntimeError("Bilibili 一级评论缺少 rpid")
    _capture(
        probe=probe,
        output=output,
        platform="bilibili",
        label="replies",
        request=bilibili.build_reply_detail_request(root=root_id, av_id=av_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )


def _run_kuaishou(
    probe: TikHubOperationProbe,
    output: Path,
    pseudo: Pseudonymizer,
    manifest: list[dict[str, object]],
) -> None:
    search_body = _capture(
        probe=probe,
        output=output,
        platform="kuaishou",
        label="search",
        request=kuaishou.build_search_request(keyword=KEYWORD),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    wrapped = _max_item(
        kuaishou.extract_search_items(search_body),
        lambda item: (
            (item.get("feed") or {}).get("comment_count", 0)
            if isinstance(item.get("feed"), dict)
            else 0
        ),
    )
    feed = wrapped.get("feed")
    if not isinstance(feed, dict) or feed.get("photo_id") is None:
        raise RuntimeError("Kuaishou Search 缺少 photo_id")
    photo_id = str(feed["photo_id"])
    _capture(
        probe=probe,
        output=output,
        platform="kuaishou",
        label="detail",
        request=kuaishou.build_video_detail_request(photo_id=photo_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    comments_body = _capture(
        probe=probe,
        output=output,
        platform="kuaishou",
        label="comments",
        request=kuaishou.build_video_comments_request(photo_id=photo_id),
        pseudonyms=pseudo,
        manifest=manifest,
    )
    comments = kuaishou.extract_comment_items(comments_body)
    root = _max_item(
        comments,
        lambda item: item.get("displaySubCommentCount") or item.get("subCommentCount") or 0,
    )
    root_id = str(root.get("comment_id") or root.get("id") or "")
    if not root_id:
        raise RuntimeError("Kuaishou 一级评论缺少 comment_id")
    _capture(
        probe=probe,
        output=output,
        platform="kuaishou",
        label="sub_comments",
        request=kuaishou.build_video_sub_comments_request(
            photo_id=photo_id,
            root_comment_id=root_id,
        ),
        pseudonyms=pseudo,
        manifest=manifest,
    )


def run() -> None:
    if os.environ.get("AIMA_TIKHUB_ENDPOINT_LEDGER_APPROVED") != "yes":
        raise RuntimeError("真实 Endpoint Ledger Probe 必须显式放行")
    output = Path(_required_env("AIMA_TIKHUB_PROBE_OUTPUT_DIR"))
    output.mkdir(parents=True, exist_ok=True)
    credential = SecretStr(_required_env("AIMA_TIKHUB_PROBE_TOKEN"))
    manifest: list[dict[str, object]] = []
    pseudonyms = {
        platform: Pseudonymizer() for platform in ("xhs", "douyin", "weibo", "bilibili", "kuaishou")
    }

    with TikHubHttpTransport(base_url=BASE_URL) as transport:
        probe = TikHubOperationProbe(
            transport=transport,
            credential=credential,
            limits=TikHubProbeLimits(
                max_requests=MAX_REQUESTS,
                max_estimated_cost=MAX_ESTIMATED_COST,
            ),
        )
        _run_xhs(probe, output, pseudonyms["xhs"], manifest)
        _run_douyin(probe, output, pseudonyms["douyin"], manifest)
        _run_weibo(probe, output, pseudonyms["weibo"], manifest)
        _run_bilibili(probe, output, pseudonyms["bilibili"], manifest)
        _run_kuaishou(probe, output, pseudonyms["kuaishou"], manifest)

        _write_json(
            output / "manifest.json",
            {
                "schema_version": "tikhub-endpoint-ledger.v1",
                "captured_at": datetime.now(UTC).isoformat(),
                "github_run_id": os.environ.get("GITHUB_RUN_ID"),
                "base_url": BASE_URL,
                "keyword": KEYWORD,
                "hidden_retries": 0,
                "max_requests": MAX_REQUESTS,
                "max_estimated_cost_usd": str(MAX_ESTIMATED_COST),
                "actual_probe_request_count": probe.request_count,
                "planned_cost_usd": str(probe.cumulative_planned_cost),
                "records": manifest,
            },
        )


if __name__ == "__main__":
    run()
