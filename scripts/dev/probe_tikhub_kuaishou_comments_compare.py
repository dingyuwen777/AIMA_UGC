"""TikHub 快手 Web/App 评论链最小 A/B 实证探针。

只用于确认当前首版评论 Operation 是否选型正确：
- 先核验 Web/App 评论与二级评论 endpoint 的实时 endpoint_cost；
- 单页搜索“爱玛”，最多检查两个高评论量作品；
- 同一 photo_id 分别请求 Web/App 一级评论；
- 只有找到带正向回复证据的 root_comment_id 才各请求一次 Web/App 二级评论；
- 不翻全量、不隐藏重试、不打印 Secret，输出只保存脱敏结构证据。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
from aima_ugc.adapters.providers.tikhub.operations.kuaishou import (
    build_app_video_comments_request,
    build_app_video_sub_comments_request,
    build_search_request,
    build_video_comments_request,
    build_video_sub_comments_request,
    extract_search_items,
)
from aima_ugc.adapters.providers.tikhub.pricing import load_tikhub_pricing

from scripts.dev.probe_tikhub_stage7_search import _nonempty_list_paths, sanitize_json

BASE_URL = "https://api.tikhub.io"
KEYWORD = "爱玛"
ENDPOINT_INFO_PATH = "/api/v1/tikhub/user/get_endpoint_info"
APP_COMMENTS_PATH = "/api/v1/kuaishou/app/fetch_video_comment"
APP_SUB_COMMENTS_PATH = "/api/v1/kuaishou/app/fetch_video_sub_comments"
WEB_COMMENTS_PATH = "/api/v1/kuaishou/web/fetch_one_video_comment"
WEB_SUB_COMMENTS_PATH = "/api/v1/kuaishou/web/fetch_one_video_sub_comment"
MAX_CONTENT_CANDIDATES = 2
MAX_ESTIMATED_BUSINESS_COST_USD = Decimal("0.060000")


@dataclass(frozen=True, slots=True)
class RootCandidate:
    comment_id: str
    score: int
    evidence_keys: tuple[str, ...]


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
            "User-Agent": "AIMA_UGC-kuaishou-comment-compare/1.0",
        },
        timeout=httpx.Timeout(45.0),
        follow_redirects=False,
        trust_env=False,
    )


def _request_json(
    client: httpx.Client,
    *,
    path: str,
    params: dict[str, object],
) -> tuple[int, dict[str, Any]]:
    response = client.get(path, params=params)
    try:
        parsed = response.json()
    except ValueError as exc:
        raise RuntimeError(f"TikHub {path} 返回非 JSON，HTTP {response.status_code}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"TikHub {path} 顶层不是 JSON object")
    return response.status_code, parsed


def _find_key(value: object, target: str) -> object | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) == target:
                return child
            found = _find_key(child, target)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_key(child, target)
            if found is not None:
                return found
    return None


def _endpoint_cost(body: dict[str, Any], path: str) -> Decimal:
    raw = _find_key(body, "endpoint_cost")
    if raw is None:
        raise RuntimeError(f"{path} 的 endpoint_info 缺少 endpoint_cost，关闭失败")
    try:
        cost = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise RuntimeError(f"{path} endpoint_cost 无法解析") from exc
    if cost < 0:
        raise RuntimeError(f"{path} endpoint_cost 不能为负数")
    return cost


def _pricing_cost_for_search() -> Decimal:
    catalog = load_tikhub_pricing()
    endpoint = catalog.require_endpoint("/api/v1/kuaishou/app/search_video_v2")
    if endpoint.verification_status != "verified":
        raise RuntimeError("快手 Search V2 Pricing 未 verified，关闭失败")
    return endpoint.base_price


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _normalized(key: object) -> str:
    return str(key).strip().lower().replace("-", "_")


def _comment_id(item: dict[str, Any]) -> str | None:
    for key in ("commentId", "comment_id", "commentid"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _reply_evidence(item: dict[str, Any]) -> tuple[int, tuple[str, ...]]:
    score = 0
    evidence: list[str] = []
    for key, value in item.items():
        normalized = _normalized(key)
        if not any(part in normalized for part in ("reply", "subcomment", "sub_comment", "child")):
            continue
        positive = False
        if isinstance(value, bool):
            positive = value
        elif isinstance(value, (int, float)):
            positive = value > 0
        elif isinstance(value, (list, dict, str)):
            positive = bool(value)
        if positive:
            score += 1
            evidence.append(str(key))
    return score, tuple(sorted(evidence))


def _root_candidates(value: object) -> tuple[RootCandidate, ...]:
    found: dict[str, RootCandidate] = {}

    def visit(node: object) -> None:
        if isinstance(node, dict):
            comment_id = _comment_id(node)
            if comment_id is not None:
                score, evidence = _reply_evidence(node)
                current = found.get(comment_id)
                candidate = RootCandidate(comment_id, score, evidence)
                if current is None or candidate.score > current.score:
                    found[comment_id] = candidate
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return tuple(sorted(found.values(), key=lambda item: (-item.score, item.comment_id)))


def _content_comment_count(item: dict[str, Any]) -> int:
    feed = item.get("feed")
    candidate = feed if isinstance(feed, dict) else item
    for key in ("comment_count", "commentCount"):
        value = candidate.get(key)
        if isinstance(value, bool):
            continue
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return 0


def _content_photo_id(item: dict[str, Any]) -> str | None:
    feed = item.get("feed")
    candidate = feed if isinstance(feed, dict) else item
    for key in ("photo_id", "photoId"):
        value = candidate.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def main() -> None:
    token = _required_token()
    output = _output_dir()
    pricing_paths = (
        WEB_COMMENTS_PATH,
        WEB_SUB_COMMENTS_PATH,
        APP_COMMENTS_PATH,
        APP_SUB_COMMENTS_PATH,
    )
    endpoint_costs: dict[str, Decimal] = {}
    endpoint_info_manifest: list[dict[str, object]] = []

    with _client(token) as client:
        for path in pricing_paths:
            status, body = _request_json(
                client,
                path=ENDPOINT_INFO_PATH,
                params={"endpoint": path},
            )
            if status != 200:
                raise RuntimeError(f"endpoint_info 查询失败: {path}, HTTP {status}")
            cost = _endpoint_cost(body, path)
            endpoint_costs[path] = cost
            _write_json(
                output / "pricing" / f"{path.rsplit('/', 1)[-1]}.sanitized.json",
                sanitize_json(body),
            )
            endpoint_info_manifest.append(
                {"endpoint": path, "http_status": status, "endpoint_cost_usd": str(cost)}
            )

        max_business_cost = (
            _pricing_cost_for_search()
            + MAX_CONTENT_CANDIDATES
            * (endpoint_costs[WEB_COMMENTS_PATH] + endpoint_costs[APP_COMMENTS_PATH])
            + endpoint_costs[WEB_SUB_COMMENTS_PATH]
            + endpoint_costs[APP_SUB_COMMENTS_PATH]
        )
        if max_business_cost > MAX_ESTIMATED_BUSINESS_COST_USD:
            raise RuntimeError(
                "快手 Web/App A/B Probe 最大估算成本超过硬上限: "
                f"{max_business_cost} > {MAX_ESTIMATED_BUSINESS_COST_USD} USD"
            )

        search = build_search_request(keyword=KEYWORD)
        search_status, search_body = _request_json(client, path=search.path, params=search.params)
        if search_status != 200:
            raise RuntimeError(f"快手 Search V2 失败，HTTP {search_status}")
        _write_json(output / "search.sanitized.json", sanitize_json(search_body))
        items = extract_search_items(search_body)
        ranked = sorted(
            (
                (item, _content_comment_count(item), _content_photo_id(item))
                for item in items
            ),
            key=lambda row: row[1],
            reverse=True,
        )
        candidates = [row for row in ranked if row[1] > 0 and row[2] is not None][
            :MAX_CONTENT_CANDIDATES
        ]
        if not candidates:
            raise RuntimeError("快手单页 Search 没有找到 comment_count > 0 的可用作品")

        selected_photo_id: str | None = None
        selected_root: RootCandidate | None = None
        selected_index: int | None = None
        comment_evidence: list[dict[str, object]] = []

        for index, (_, comment_count, photo_id) in enumerate(candidates, start=1):
            assert photo_id is not None
            web_request = build_video_comments_request(photo_id=photo_id)
            app_request = build_app_video_comments_request(photo_id=photo_id)
            web_status, web_body = _request_json(
                client, path=web_request.path, params=web_request.params
            )
            app_status, app_body = _request_json(
                client, path=app_request.path, params=app_request.params
            )
            _write_json(output / f"candidate_{index}" / "web_comments.sanitized.json", sanitize_json(web_body))
            _write_json(output / f"candidate_{index}" / "app_comments.sanitized.json", sanitize_json(app_body))

            roots = _root_candidates(web_body) + _root_candidates(app_body)
            best_by_id: dict[str, RootCandidate] = {}
            for root in roots:
                current = best_by_id.get(root.comment_id)
                if current is None or root.score > current.score:
                    best_by_id[root.comment_id] = root
            ranked_roots = sorted(
                best_by_id.values(), key=lambda item: (-item.score, item.comment_id)
            )
            best = ranked_roots[0] if ranked_roots else None
            comment_evidence.append(
                {
                    "candidate_index": index,
                    "search_comment_count": comment_count,
                    "web_http_status": web_status,
                    "app_http_status": app_status,
                    "web_nonempty_list_paths": _nonempty_list_paths(sanitize_json(web_body)),
                    "app_nonempty_list_paths": _nonempty_list_paths(sanitize_json(app_body)),
                    "root_candidates": len(ranked_roots),
                    "best_root_reply_score": None if best is None else best.score,
                    "best_root_evidence_keys": [] if best is None else list(best.evidence_keys),
                }
            )
            if best is not None and best.score > 0:
                selected_photo_id = photo_id
                selected_root = best
                selected_index = index
                break

        subcomment_evidence: dict[str, object]
        if selected_photo_id is None or selected_root is None:
            subcomment_evidence = {
                "executed": False,
                "reason": "bounded_comment_pages_have_no_positive_reply_indicator",
            }
        else:
            web_sub = build_video_sub_comments_request(
                photo_id=selected_photo_id,
                root_comment_id=selected_root.comment_id,
            )
            app_sub = build_app_video_sub_comments_request(
                photo_id=selected_photo_id,
                root_comment_id=selected_root.comment_id,
            )
            web_sub_status, web_sub_body = _request_json(
                client, path=web_sub.path, params=web_sub.params
            )
            app_sub_status, app_sub_body = _request_json(
                client, path=app_sub.path, params=app_sub.params
            )
            safe_web_sub = sanitize_json(web_sub_body)
            safe_app_sub = sanitize_json(app_sub_body)
            _write_json(output / "selected" / "web_sub_comments.sanitized.json", safe_web_sub)
            _write_json(output / "selected" / "app_sub_comments.sanitized.json", safe_app_sub)
            subcomment_evidence = {
                "executed": True,
                "candidate_index": selected_index,
                "root_reply_score": selected_root.score,
                "root_evidence_keys": list(selected_root.evidence_keys),
                "web_http_status": web_sub_status,
                "app_http_status": app_sub_status,
                "web_nonempty_list_paths": _nonempty_list_paths(safe_web_sub),
                "app_nonempty_list_paths": _nonempty_list_paths(safe_app_sub),
            }

    _write_json(
        output / "manifest.json",
        {
            "schema_version": "stage7-kuaishou-comment-api-compare.v1",
            "base_url": BASE_URL,
            "keyword": KEYWORD,
            "hidden_retries": 0,
            "max_search_pages": 1,
            "max_content_candidates": MAX_CONTENT_CANDIDATES,
            "max_estimated_business_cost_usd": str(MAX_ESTIMATED_BUSINESS_COST_USD),
            "endpoint_info": endpoint_info_manifest,
            "comment_evidence": comment_evidence,
            "subcomment_evidence": subcomment_evidence,
        },
    )


if __name__ == "__main__":
    main()
