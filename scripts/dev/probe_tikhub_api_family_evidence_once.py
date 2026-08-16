"""Stage 7 TikHub API family 一次性真实证据 Probe。

该脚本只用于当前 Stage 7 的受限真实 A/B：
- 搜索：抖音 V2/V1、微博 Web/App、B站 App/Web、快手视频/综合搜索；
- 评论：微博 App/Web V2、B站 App/Web；
- 回复：B站 App/Web。

真实请求只在 GitHub-hosted Runner 执行。输出在写入仓库前完成脱敏；同一平台
共享 ID 假名映射，以便后续核对跨接口身份与集合重合。脚本不注册 Capability、
不改变生产主链，也不实现自动 fallback。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import httpx

import probe_tikhub_api_families as base
from aima_ugc.adapters.providers.tikhub.api_family_compare import compare_stable_ids
from aima_ugc.adapters.providers.tikhub.operations.bilibili import (
    build_reply_detail_request as build_bilibili_reply_request,
    build_video_comments_request as build_bilibili_comments_request,
    build_web_reply_candidate_request as build_bilibili_web_reply_request,
    build_web_video_comments_candidate_request as build_bilibili_web_comments_request,
    extract_comment_items as extract_bilibili_comment_items,
)
from aima_ugc.adapters.providers.tikhub.operations.weibo import (
    build_status_comments_request as build_weibo_comments_request,
    build_web_status_comments_candidate_request as build_weibo_web_comments_request,
    extract_comment_items as extract_weibo_comment_items,
)

BASE_URL = "https://api.tikhub.io"
ENDPOINT_INFO_PATH = "/api/v1/tikhub/user/get_endpoint_info"
MAX_ESTIMATED_BUSINESS_COST_USD = Decimal("0.120000")
MAX_LIST_ITEMS = 3

_SECRET_PARTS = ("authorization", "cookie", "password", "secret", "signature", "token", "xsec")
_TEXT_KEYS = {
    "author",
    "bio",
    "caption",
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
    "idstr",
    "mid",
    "mblogid",
    "note_id",
    "photo_id",
    "request_id",
    "root",
    "root_comment_id",
    "rpid",
    "sec_uid",
    "status_id",
    "uid",
    "user_id",
    "userid",
}
_TIME_PARTS = ("create_time", "created_at", "publish_time", "timestamp", "time_stamp", "update_time")
_SAFE_STRING_KEYS = {
    "code",
    "content_type",
    "currency",
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
    "unit",
}
_ASCII_ENUM = re.compile(r"^[A-Za-z0-9_.:/ -]{1,80}$")


@dataclass(frozen=True, slots=True)
class RequestSpec:
    method: Literal["GET", "POST"]
    path: str
    params: dict[str, object]
    body: dict[str, object] | None = None


class Pseudonymizer:
    """同一平台内稳定替换真实 ID，并尽量保持原始标量类型。"""

    def __init__(self) -> None:
        self._strings: dict[str, str] = {}
        self._numbers: dict[str, int] = {}

    def identifier(self, value: object) -> object:
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            key = repr(value)
            if key not in self._numbers:
                self._numbers[key] = 100_000 + len(self._numbers) + 1
            return self._numbers[key]
        text = str(value)
        if text not in self._strings:
            self._strings[text] = f"id-{len(self._strings) + 1:04d}"
        return self._strings[text]


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
            "User-Agent": "AIMA_UGC-stage7-api-family-evidence/1.0",
        },
        timeout=httpx.Timeout(45.0),
        follow_redirects=False,
        trust_env=False,
    )


def _request_json(client: httpx.Client, request: RequestSpec) -> tuple[int, dict[str, Any]]:
    response = client.request(
        request.method,
        request.path,
        params=request.params,
        json=request.body,
    )
    try:
        parsed: Any = response.json()
    except ValueError as exc:
        raise RuntimeError(f"TikHub {request.path} 返回非 JSON，HTTP {response.status_code}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"TikHub {request.path} 响应根节点不是 object")
    return response.status_code, parsed


def _endpoint_cost(client: httpx.Client, path: str) -> Decimal:
    response = client.get(ENDPOINT_INFO_PATH, params={"endpoint": path})
    try:
        parsed: Any = response.json()
    except ValueError as exc:
        raise RuntimeError(f"TikHub endpoint-info 返回非 JSON，HTTP {response.status_code}") from exc
    if response.status_code != 200:
        raise RuntimeError(f"TikHub endpoint-info HTTP {response.status_code}: {path}")
    raw_cost = _find_key(parsed, "endpoint_cost")
    if raw_cost is None:
        raise RuntimeError(f"TikHub endpoint-info 缺少 endpoint_cost: {path}")
    try:
        cost = Decimal(str(raw_cost))
    except (InvalidOperation, ValueError) as exc:
        raise RuntimeError(f"TikHub endpoint_cost 无法解析: {path}") from exc
    if not cost.is_finite() or cost <= 0:
        raise RuntimeError(f"TikHub endpoint_cost 必须为正数: {path}")
    return cost


def _find_key(value: object, target: str) -> object | None:
    if isinstance(value, dict):
        if target in value:
            return value[target]
        for child in value.values():
            found = _find_key(child, target)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_key(child, target)
            if found is not None:
                return found
    return None


def _normalized_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _is_identifier_key(key: str) -> bool:
    normalized = _normalized_key(key)
    return normalized in _ID_KEYS or normalized.endswith("_id") or normalized.endswith("id_str")


def _is_time_key(key: str) -> bool:
    normalized = _normalized_key(key)
    if normalized in {"time_zone", "timezone"}:
        return False
    return any(part in normalized for part in _TIME_PARTS)


def _sanitize_scalar(key: str, value: object, pseudonyms: Pseudonymizer) -> object:
    normalized = _normalized_key(key)
    if any(part in normalized for part in _SECRET_PARTS):
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
        if value == base.KEYWORD:
            return value
        if value.startswith(("http://", "https://")):
            return "https://example.invalid/redacted"
        if normalized in _TEXT_KEYS:
            return "<redacted-text>"
        if normalized in _SAFE_STRING_KEYS and len(value) <= 160:
            return value
        if _ASCII_ENUM.fullmatch(value) and normalized not in {"location", "region"}:
            return value
        return "<redacted-text>"
    return value


def sanitize_json(
    value: object,
    *,
    key: str = "root",
    pseudonyms: Pseudonymizer,
) -> object:
    """保留字段、层级和标量类型；移除 Secret/直接标识，并限制代表数组大小。"""
    if isinstance(value, dict):
        return {
            str(child_key): sanitize_json(
                child_value,
                key=str(child_key),
                pseudonyms=pseudonyms,
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            sanitize_json(item, key=key, pseudonyms=pseudonyms)
            for item in value[:MAX_LIST_ITEMS]
        ]
    return _sanitize_scalar(key, value, pseudonyms)


def _request_from(value: object) -> RequestSpec:
    method = getattr(value, "method")
    path = getattr(value, "path")
    params = getattr(value, "params")
    body = getattr(value, "body", None)
    if method not in {"GET", "POST"}:
        raise ValueError(f"不支持的 method: {method}")
    if not isinstance(path, str) or not isinstance(params, dict):
        raise TypeError("Operation request 结构无效")
    normalized_body = dict(body) if isinstance(body, dict) else None
    return RequestSpec(method, path, dict(params), normalized_body)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sanitized_request(request: RequestSpec, pseudonyms: Pseudonymizer) -> dict[str, object]:
    return {
        "method": request.method,
        "path": request.path,
        "params": sanitize_json(request.params, key="params", pseudonyms=pseudonyms),
        "body": None
        if request.body is None
        else sanitize_json(request.body, key="body", pseudonyms=pseudonyms),
        "authorization": "Bearer <redacted-secret>",
    }


def _record_pair(
    *,
    output: Path,
    client: httpx.Client,
    prices: dict[str, Decimal],
    name: str,
    platform: str,
    relation: str,
    primary: RequestSpec,
    candidate: RequestSpec,
    primary_ids: tuple[str, ...] | None = None,
    candidate_ids: tuple[str, ...] | None = None,
    pseudonyms: Pseudonymizer,
) -> tuple[dict[str, object], dict[str, Any], dict[str, Any]]:
    primary_status, primary_body = _request_json(client, primary)
    candidate_status, candidate_body = _request_json(client, candidate)
    resolved_primary_ids = primary_ids if primary_ids is not None else base._extract_ids(platform, primary_body)
    resolved_candidate_ids = (
        candidate_ids if candidate_ids is not None else base._extract_ids(platform, candidate_body)
    )
    comparison = asdict(
        compare_stable_ids(
            primary_ids=resolved_primary_ids,
            candidate_ids=resolved_candidate_ids,
        )
    )
    comparison.pop("shared_ids", None)
    comparison.pop("primary_only_ids", None)
    comparison.pop("candidate_only_ids", None)
    case_dir = output / name
    _write_json(
        case_dir / "primary.request.sanitized.json",
        _sanitized_request(primary, pseudonyms),
    )
    _write_json(
        case_dir / "primary.response.sanitized.json",
        sanitize_json(primary_body, pseudonyms=pseudonyms),
    )
    _write_json(
        case_dir / "candidate.request.sanitized.json",
        _sanitized_request(candidate, pseudonyms),
    )
    _write_json(
        case_dir / "candidate.response.sanitized.json",
        sanitize_json(candidate_body, pseudonyms=pseudonyms),
    )
    summary = {
        "name": name,
        "platform": platform,
        "semantic_relation": relation,
        "keyword": base.KEYWORD,
        "primary_endpoint": primary.path,
        "candidate_endpoint": candidate.path,
        "primary_price_usd": str(prices[primary.path]),
        "candidate_price_usd": str(prices[candidate.path]),
        "primary_http_status": primary_status,
        "candidate_http_status": candidate_status,
        "primary_provider_code": primary_body.get("code"),
        "candidate_provider_code": candidate_body.get("code"),
        "id_comparison": comparison,
        "shape_comparison": base._shape_summary(primary_body, candidate_body),
        "evidence_files": {
            "primary_request": f"{name}/primary.request.sanitized.json",
            "primary_response": f"{name}/primary.response.sanitized.json",
            "candidate_request": f"{name}/candidate.request.sanitized.json",
            "candidate_response": f"{name}/candidate.response.sanitized.json",
        },
    }
    return summary, primary_body, candidate_body


def _weibo_comment_ids(body: dict[str, Any]) -> tuple[str, ...]:
    primary_items = extract_weibo_comment_items(body)
    if primary_items:
        return tuple(
            str(item.get("idstr") or item.get("id"))
            for item in primary_items
            if item.get("idstr") is not None or item.get("id") is not None
        )
    ids: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            identifier = value.get("idstr") or value.get("id")
            if identifier is not None and "user" in value and ("text" in value or "created_at" in value):
                ids.append(str(identifier))
                return
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(body)
    return tuple(ids)


def _bilibili_comment_ids(body: dict[str, Any]) -> tuple[str, ...]:
    ids: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            identifier = value.get("rpid") or value.get("rpid_str")
            if identifier is not None and ("content" in value or "member" in value or "ctime" in value):
                ids.append(str(identifier))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(body)
    return tuple(ids)


def _pick_bilibili_root(body: dict[str, Any]) -> str | None:
    items = extract_bilibili_comment_items(body)
    if not items:
        return None
    for item in items:
        reply_count = item.get("rcount") or item.get("count") or 0
        try:
            has_replies = int(reply_count) > 0
        except (TypeError, ValueError):
            has_replies = False
        identifier = item.get("rpid") or item.get("rpid_str")
        if has_replies and identifier is not None:
            return str(identifier)
    first = items[0]
    identifier = first.get("rpid") or first.get("rpid_str")
    return str(identifier) if identifier is not None else None


def _planned_requests(search_cases: tuple[base.ProbeCase, ...]) -> tuple[RequestSpec, ...]:
    requests: list[RequestSpec] = []
    for case in search_cases:
        requests.extend((_request_from(case.primary), _request_from(case.candidate)))
    return tuple(requests)


def run_probe() -> None:
    if os.environ.get("AIMA_TIKHUB_API_FAMILY_EVIDENCE_APPROVED") != "yes":
        raise RuntimeError("真实 API family Evidence Probe 必须显式放行")
    output = _output_dir()
    token = _required_token()
    search_cases = base._cases()
    prices: dict[str, Decimal] = {}
    platform_pseudonyms = {case.platform: Pseudonymizer() for case in search_cases}

    with _client(token) as client:
        initial_requests = list(_planned_requests(search_cases))
        for request in initial_requests:
            prices.setdefault(request.path, _endpoint_cost(client, request.path))

        results: list[dict[str, object]] = []
        search_primary_bodies: dict[str, dict[str, Any]] = {}
        for case in search_cases:
            summary, primary_body, _ = _record_pair(
                output=output,
                client=client,
                prices=prices,
                name=case.name,
                platform=case.platform,
                relation=case.semantic_relation,
                primary=_request_from(case.primary),
                candidate=_request_from(case.candidate),
                pseudonyms=platform_pseudonyms[case.platform],
            )
            results.append(summary)
            search_primary_bodies[case.platform] = primary_body

        weibo_ids = base._extract_ids("weibo", search_primary_bodies["weibo"])
        if weibo_ids:
            status_id = weibo_ids[0]
            weibo_primary = _request_from(
                build_weibo_comments_request(status_id=status_id, sort_mode="latest")
            )
            weibo_candidate = _request_from(
                build_weibo_web_comments_request(status_id=status_id, max_id="", count=10)
            )
            for request in (weibo_primary, weibo_candidate):
                prices.setdefault(request.path, _endpoint_cost(client, request.path))
            primary_status, primary_body = _request_json(client, weibo_primary)
            candidate_status, candidate_body = _request_json(client, weibo_candidate)
            primary_ids = _weibo_comment_ids(primary_body)
            candidate_ids = _weibo_comment_ids(candidate_body)
            case_name = "weibo_app_comments_vs_web_v2_comments"
            case_dir = output / case_name
            pseudo = platform_pseudonyms["weibo"]
            _write_json(case_dir / "primary.request.sanitized.json", _sanitized_request(weibo_primary, pseudo))
            _write_json(case_dir / "primary.response.sanitized.json", sanitize_json(primary_body, pseudonyms=pseudo))
            _write_json(case_dir / "candidate.request.sanitized.json", _sanitized_request(weibo_candidate, pseudo))
            _write_json(case_dir / "candidate.response.sanitized.json", sanitize_json(candidate_body, pseudonyms=pseudo))
            comparison = asdict(compare_stable_ids(primary_ids=primary_ids, candidate_ids=candidate_ids))
            for key in ("shared_ids", "primary_only_ids", "candidate_only_ids"):
                comparison.pop(key, None)
            results.append(
                {
                    "name": case_name,
                    "platform": "weibo",
                    "semantic_relation": "same_business",
                    "primary_endpoint": weibo_primary.path,
                    "candidate_endpoint": weibo_candidate.path,
                    "primary_price_usd": str(prices[weibo_primary.path]),
                    "candidate_price_usd": str(prices[weibo_candidate.path]),
                    "primary_http_status": primary_status,
                    "candidate_http_status": candidate_status,
                    "primary_provider_code": primary_body.get("code"),
                    "candidate_provider_code": candidate_body.get("code"),
                    "id_comparison": comparison,
                    "shape_comparison": base._shape_summary(primary_body, candidate_body),
                    "evidence_files": {
                        "primary_request": f"{case_name}/primary.request.sanitized.json",
                        "primary_response": f"{case_name}/primary.response.sanitized.json",
                        "candidate_request": f"{case_name}/candidate.request.sanitized.json",
                        "candidate_response": f"{case_name}/candidate.response.sanitized.json",
                    },
                }
            )

        bilibili_ids = base._extract_ids("bilibili", search_primary_bodies["bilibili"])
        if bilibili_ids:
            bv_id = bilibili_ids[0]
            bili_primary_comments = _request_from(
                build_bilibili_comments_request(bv_id=bv_id, sort_mode="latest")
            )
            bili_candidate_comments = _request_from(
                build_bilibili_web_comments_request(bv_id=bv_id, page=1)
            )
            for request in (bili_primary_comments, bili_candidate_comments):
                prices.setdefault(request.path, _endpoint_cost(client, request.path))
            primary_status, primary_comments_body = _request_json(client, bili_primary_comments)
            candidate_status, candidate_comments_body = _request_json(client, bili_candidate_comments)
            primary_comment_ids = _bilibili_comment_ids(primary_comments_body)
            candidate_comment_ids = _bilibili_comment_ids(candidate_comments_body)
            case_name = "bilibili_app_comments_vs_web_comments"
            case_dir = output / case_name
            pseudo = platform_pseudonyms["bilibili"]
            _write_json(case_dir / "primary.request.sanitized.json", _sanitized_request(bili_primary_comments, pseudo))
            _write_json(case_dir / "primary.response.sanitized.json", sanitize_json(primary_comments_body, pseudonyms=pseudo))
            _write_json(case_dir / "candidate.request.sanitized.json", _sanitized_request(bili_candidate_comments, pseudo))
            _write_json(case_dir / "candidate.response.sanitized.json", sanitize_json(candidate_comments_body, pseudonyms=pseudo))
            comparison = asdict(
                compare_stable_ids(
                    primary_ids=primary_comment_ids,
                    candidate_ids=candidate_comment_ids,
                )
            )
            for key in ("shared_ids", "primary_only_ids", "candidate_only_ids"):
                comparison.pop(key, None)
            results.append(
                {
                    "name": case_name,
                    "platform": "bilibili",
                    "semantic_relation": "same_business",
                    "primary_endpoint": bili_primary_comments.path,
                    "candidate_endpoint": bili_candidate_comments.path,
                    "primary_price_usd": str(prices[bili_primary_comments.path]),
                    "candidate_price_usd": str(prices[bili_candidate_comments.path]),
                    "primary_http_status": primary_status,
                    "candidate_http_status": candidate_status,
                    "primary_provider_code": primary_comments_body.get("code"),
                    "candidate_provider_code": candidate_comments_body.get("code"),
                    "id_comparison": comparison,
                    "shape_comparison": base._shape_summary(primary_comments_body, candidate_comments_body),
                    "evidence_files": {
                        "primary_request": f"{case_name}/primary.request.sanitized.json",
                        "primary_response": f"{case_name}/primary.response.sanitized.json",
                        "candidate_request": f"{case_name}/candidate.request.sanitized.json",
                        "candidate_response": f"{case_name}/candidate.response.sanitized.json",
                    },
                }
            )

            root = _pick_bilibili_root(primary_comments_body)
            if root is not None:
                bili_primary_reply = _request_from(
                    build_bilibili_reply_request(root=root, bv_id=bv_id)
                )
                bili_candidate_reply = _request_from(
                    build_bilibili_web_reply_request(bv_id=bv_id, root=root, page=1)
                )
                for request in (bili_primary_reply, bili_candidate_reply):
                    prices.setdefault(request.path, _endpoint_cost(client, request.path))
                reply_primary_status, reply_primary_body = _request_json(client, bili_primary_reply)
                reply_candidate_status, reply_candidate_body = _request_json(client, bili_candidate_reply)
                reply_primary_ids = _bilibili_comment_ids(reply_primary_body)
                reply_candidate_ids = _bilibili_comment_ids(reply_candidate_body)
                reply_case_name = "bilibili_app_replies_vs_web_replies"
                reply_dir = output / reply_case_name
                _write_json(reply_dir / "primary.request.sanitized.json", _sanitized_request(bili_primary_reply, pseudo))
                _write_json(reply_dir / "primary.response.sanitized.json", sanitize_json(reply_primary_body, pseudonyms=pseudo))
                _write_json(reply_dir / "candidate.request.sanitized.json", _sanitized_request(bili_candidate_reply, pseudo))
                _write_json(reply_dir / "candidate.response.sanitized.json", sanitize_json(reply_candidate_body, pseudonyms=pseudo))
                reply_comparison = asdict(
                    compare_stable_ids(
                        primary_ids=reply_primary_ids,
                        candidate_ids=reply_candidate_ids,
                    )
                )
                for key in ("shared_ids", "primary_only_ids", "candidate_only_ids"):
                    reply_comparison.pop(key, None)
                results.append(
                    {
                        "name": reply_case_name,
                        "platform": "bilibili",
                        "semantic_relation": "same_business",
                        "primary_endpoint": bili_primary_reply.path,
                        "candidate_endpoint": bili_candidate_reply.path,
                        "primary_price_usd": str(prices[bili_primary_reply.path]),
                        "candidate_price_usd": str(prices[bili_candidate_reply.path]),
                        "primary_http_status": reply_primary_status,
                        "candidate_http_status": reply_candidate_status,
                        "primary_provider_code": reply_primary_body.get("code"),
                        "candidate_provider_code": reply_candidate_body.get("code"),
                        "id_comparison": reply_comparison,
                        "shape_comparison": base._shape_summary(reply_primary_body, reply_candidate_body),
                        "evidence_files": {
                            "primary_request": f"{reply_case_name}/primary.request.sanitized.json",
                            "primary_response": (
                                f"{reply_case_name}/primary.response.sanitized.json"
                            ),
                            "candidate_request": (
                                f"{reply_case_name}/candidate.request.sanitized.json"
                            ),
                            "candidate_response": (
                                f"{reply_case_name}/candidate.response.sanitized.json"
                            ),
                        },
                    }
                )

        estimated_business_cost = sum(
            prices[result["primary_endpoint"]] + prices[result["candidate_endpoint"]]
            for result in results
        )
        if estimated_business_cost > MAX_ESTIMATED_BUSINESS_COST_USD:
            raise RuntimeError(
                "TikHub Evidence Probe 业务费用超过硬上限: "
                f"{estimated_business_cost} > {MAX_ESTIMATED_BUSINESS_COST_USD}"
            )

    report = {
        "schema_version": "stage7-tikhub-api-family-evidence.v1",
        "captured_at": datetime.now(UTC).isoformat(),
        "base_url": BASE_URL,
        "keyword": base.KEYWORD,
        "business_pair_count": len(results),
        "business_request_count": len(results) * 2,
        "hidden_retries": 0,
        "estimated_business_cost_usd": str(estimated_business_cost),
        "max_estimated_business_cost_usd": str(MAX_ESTIMATED_BUSINESS_COST_USD),
        "array_evidence_limit": MAX_LIST_ITEMS,
        "results": results,
    }
    _write_json(output / "summary.json", report)


def main() -> None:
    run_probe()


if __name__ == "__main__":
    main()
