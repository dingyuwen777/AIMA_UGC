"""TikHub 同平台 API family 受限真实 A/B Probe。

用途：
- 对同一业务输入的主 endpoint 与候选 endpoint 做单页真实对照；
- 先通过官方 get_endpoint_info 取得逐 endpoint 精确单价，再受硬费用上限保护；
- 只输出数量、稳定 ID 集合重合指标、结构路径相似度和价格，不落真实业务正文/账号/ID。

约束：
- Secret 只从环境变量读取；
- 请求构造复用生产 Operation builder；
- 不做隐藏重试；
- 候选接口只用于 Probe，不进入默认 Capability 或自动 fallback。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import httpx

from aima_ugc.adapters.providers.tikhub.api_family_compare import compare_stable_ids
from aima_ugc.adapters.providers.tikhub.operations.bilibili import (
    build_search_request as build_bilibili_search_request,
    build_web_search_candidate_request as build_bilibili_web_search_candidate_request,
)
from aima_ugc.adapters.providers.tikhub.operations.douyin import (
    build_video_search_request as build_douyin_search_request,
    build_video_search_v1_candidate_request as build_douyin_search_v1_candidate_request,
)
from aima_ugc.adapters.providers.tikhub.operations.kuaishou import (
    build_comprehensive_search_candidate_request as build_kuaishou_comprehensive_candidate_request,
    build_search_request as build_kuaishou_search_request,
)
from aima_ugc.adapters.providers.tikhub.operations.weibo import (
    build_app_search_candidate_request as build_weibo_app_search_candidate_request,
    build_search_request as build_weibo_search_request,
)

BASE_URL = "https://api.tikhub.io"
ENDPOINT_INFO_PATH = "/api/v1/tikhub/user/get_endpoint_info"
KEYWORD = "爱玛"
MAX_ESTIMATED_BUSINESS_COST_USD = Decimal("0.100000")


@dataclass(frozen=True, slots=True)
class ProbeRequest:
    """一次不含 Secret 的真实 A/B 请求描述。"""

    method: Literal["GET", "POST"]
    path: str
    params: dict[str, object]
    body: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ProbeCase:
    """一组同平台主/候选 endpoint 对照。"""

    name: str
    platform: Literal["douyin", "weibo", "bilibili", "kuaishou"]
    semantic_relation: Literal["same_business", "broader_candidate"]
    primary: ProbeRequest
    candidate: ProbeRequest


def _cases() -> tuple[ProbeCase, ...]:
    douyin_primary = build_douyin_search_request(
        keyword=KEYWORD,
        cursor=0,
        sort_mode="latest",
        published_within="7d",
        duration="all",
        content_type="video",
    )
    douyin_candidate = build_douyin_search_v1_candidate_request(
        keyword=KEYWORD,
        cursor=0,
        sort_mode="latest",
        published_within="7d",
        duration="all",
        content_type="video",
    )
    weibo_primary = build_weibo_search_request(
        keyword=KEYWORD,
        page=1,
        search_mode="latest",
        time_scope="all",
    )
    weibo_candidate = build_weibo_app_search_candidate_request(
        keyword=KEYWORD,
        page=1,
        search_mode="latest",
    )
    bilibili_primary = build_bilibili_search_request(
        keyword=KEYWORD,
        sort_mode="latest",
        search_type="video",
    )
    bilibili_candidate = build_bilibili_web_search_candidate_request(
        keyword=KEYWORD,
        page=1,
        page_size=20,
        sort_mode="latest",
    )
    kuaishou_primary = build_kuaishou_search_request(keyword=KEYWORD, pcursor="")
    kuaishou_candidate = build_kuaishou_comprehensive_candidate_request(
        keyword=KEYWORD,
        pcursor="",
        sort_mode="latest",
        publish_time="week",
        duration="all",
    )
    return (
        ProbeCase(
            name="douyin_video_search_v2_vs_v1",
            platform="douyin",
            semantic_relation="same_business",
            primary=ProbeRequest(
                douyin_primary.method,
                douyin_primary.path,
                dict(douyin_primary.params),
                None if douyin_primary.body is None else dict(douyin_primary.body),
            ),
            candidate=ProbeRequest(
                douyin_candidate.method,
                douyin_candidate.path,
                dict(douyin_candidate.params),
                None if douyin_candidate.body is None else dict(douyin_candidate.body),
            ),
        ),
        ProbeCase(
            name="weibo_web_search_vs_app_search_all",
            platform="weibo",
            semantic_relation="same_business",
            primary=ProbeRequest(
                weibo_primary.method, weibo_primary.path, dict(weibo_primary.params)
            ),
            candidate=ProbeRequest(
                weibo_candidate.method,
                weibo_candidate.path,
                dict(weibo_candidate.params),
            ),
        ),
        ProbeCase(
            name="bilibili_app_search_vs_web_search",
            platform="bilibili",
            semantic_relation="same_business",
            primary=ProbeRequest(
                bilibili_primary.method,
                bilibili_primary.path,
                dict(bilibili_primary.params),
            ),
            candidate=ProbeRequest(
                bilibili_candidate.method,
                bilibili_candidate.path,
                dict(bilibili_candidate.params),
            ),
        ),
        ProbeCase(
            name="kuaishou_video_search_vs_comprehensive_video_subset",
            platform="kuaishou",
            semantic_relation="broader_candidate",
            primary=ProbeRequest(
                kuaishou_primary.method,
                kuaishou_primary.path,
                dict(kuaishou_primary.params),
            ),
            candidate=ProbeRequest(
                kuaishou_candidate.method,
                kuaishou_candidate.path,
                dict(kuaishou_candidate.params),
            ),
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
            "User-Agent": "AIMA_UGC-stage7-api-family-probe/1.0",
        },
        timeout=httpx.Timeout(45.0),
        follow_redirects=False,
        trust_env=False,
    )


def _request_json(client: httpx.Client, request: ProbeRequest) -> tuple[int, dict[str, Any]]:
    response = client.request(
        request.method,
        request.path,
        params=request.params,
        json=request.body,
    )
    try:
        parsed = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"TikHub {request.path} 返回非 JSON，HTTP {response.status_code}"
        ) from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"TikHub {request.path} 响应根节点不是 object")
    return response.status_code, parsed


def _endpoint_cost(client: httpx.Client, path: str) -> Decimal:
    response = client.get(ENDPOINT_INFO_PATH, params={"endpoint": path})
    try:
        parsed: Any = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"TikHub endpoint-info 返回非 JSON，HTTP {response.status_code}"
        ) from exc
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


def _extract_ids(platform: str, body: dict[str, Any]) -> tuple[str, ...]:
    if platform == "douyin":
        return tuple(_douyin_ids(body))
    if platform == "weibo":
        return tuple(_weibo_ids(body))
    if platform == "bilibili":
        return tuple(_bilibili_ids(body))
    if platform == "kuaishou":
        return tuple(_kuaishou_ids(body))
    raise ValueError(f"不支持的平台: {platform}")


def _douyin_ids(value: object) -> list[str]:
    ids: list[str] = []
    if isinstance(value, dict):
        aweme_info = value.get("aweme_info")
        if isinstance(aweme_info, dict) and aweme_info.get("aweme_id") is not None:
            ids.append(str(aweme_info["aweme_id"]))
            return ids
        if value.get("aweme_id") is not None and (
            "statistics" in value or "video" in value or "desc" in value
        ):
            ids.append(str(value["aweme_id"]))
            return ids
        for child in value.values():
            ids.extend(_douyin_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.extend(_douyin_ids(child))
    return ids


def _weibo_ids(value: object) -> list[str]:
    ids: list[str] = []
    if isinstance(value, dict):
        mblog = value.get("mblog")
        if isinstance(mblog, dict):
            identifier = mblog.get("idstr") or mblog.get("id")
            if identifier is not None:
                ids.append(str(identifier))
                return ids
        identifier = value.get("idstr") or value.get("mblogid")
        if (
            identifier is not None
            and "user" in value
            and ("text" in value or "created_at" in value)
        ):
            ids.append(str(identifier))
            return ids
        for child in value.values():
            ids.extend(_weibo_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.extend(_weibo_ids(child))
    return ids


def _bilibili_ids(value: object) -> list[str]:
    ids: list[str] = []
    if isinstance(value, dict):
        av = value.get("av")
        if isinstance(av, dict):
            identifier = av.get("bvid") or av.get("aid")
            if identifier is not None:
                ids.append(str(identifier))
                return ids
        identifier = value.get("bvid")
        if identifier is not None and (
            "title" in value or "author" in value or "play" in value or "arcurl" in value
        ):
            ids.append(str(identifier))
            return ids
        for child in value.values():
            ids.extend(_bilibili_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.extend(_bilibili_ids(child))
    return ids


def _kuaishou_ids(value: object) -> list[str]:
    ids: list[str] = []
    if isinstance(value, dict):
        feed = value.get("feed")
        if isinstance(feed, dict) and feed.get("photo_id") is not None:
            ids.append(str(feed["photo_id"]))
            return ids
        identifier = value.get("photo_id")
        if identifier is not None and (
            "caption" in value
            or "author" in value
            or "view_count" in value
            or "like_count" in value
        ):
            ids.append(str(identifier))
            return ids
        for child in value.values():
            ids.extend(_kuaishou_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.extend(_kuaishou_ids(child))
    return ids


def _shape_paths(value: object, *, prefix: str = "$", depth: int = 0) -> set[str]:
    if depth > 7:
        return set()
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            paths.add(child_path)
            paths.update(_shape_paths(child, prefix=child_path, depth=depth + 1))
    elif isinstance(value, list):
        list_path = f"{prefix}[]"
        paths.add(list_path)
        for child in value[:3]:
            paths.update(_shape_paths(child, prefix=list_path, depth=depth + 1))
    return paths


def _shape_summary(primary: dict[str, Any], candidate: dict[str, Any]) -> dict[str, object]:
    primary_paths = _shape_paths(primary)
    candidate_paths = _shape_paths(candidate)
    shared = primary_paths & candidate_paths
    union = primary_paths | candidate_paths
    return {
        "primary_path_count": len(primary_paths),
        "candidate_path_count": len(candidate_paths),
        "shared_path_count": len(shared),
        "primary_only_path_count": len(primary_paths - candidate_paths),
        "candidate_only_path_count": len(candidate_paths - primary_paths),
        "shape_jaccard": (len(shared) / len(union)) if union else None,
    }


def _provider_code(body: dict[str, Any]) -> object:
    return body.get("code")


def run_probe() -> None:
    if os.environ.get("AIMA_TIKHUB_API_FAMILY_PROBE_APPROVED") != "yes":
        raise RuntimeError("真实 API family Probe 必须显式放行")

    output = _output_dir()
    token = _required_token()
    cases = _cases()
    endpoint_prices: dict[str, Decimal] = {}

    with _client(token) as client:
        for case in cases:
            for request in (case.primary, case.candidate):
                if request.path not in endpoint_prices:
                    endpoint_prices[request.path] = _endpoint_cost(client, request.path)

        estimated_business_cost = sum(
            endpoint_prices[request.path]
            for case in cases
            for request in (case.primary, case.candidate)
        )
        if estimated_business_cost > MAX_ESTIMATED_BUSINESS_COST_USD:
            raise RuntimeError(
                "TikHub API family Probe 预计业务请求费用超过硬上限: "
                f"{estimated_business_cost} > {MAX_ESTIMATED_BUSINESS_COST_USD}"
            )

        results: list[dict[str, object]] = []
        for case in cases:
            primary_status, primary_body = _request_json(client, case.primary)
            candidate_status, candidate_body = _request_json(client, case.candidate)
            primary_ids = _extract_ids(case.platform, primary_body)
            candidate_ids = _extract_ids(case.platform, candidate_body)
            comparison = compare_stable_ids(
                primary_ids=primary_ids,
                candidate_ids=candidate_ids,
            )
            comparison_payload = asdict(comparison)
            comparison_payload.pop("shared_ids", None)
            comparison_payload.pop("primary_only_ids", None)
            comparison_payload.pop("candidate_only_ids", None)
            results.append(
                {
                    "name": case.name,
                    "platform": case.platform,
                    "semantic_relation": case.semantic_relation,
                    "keyword": KEYWORD,
                    "primary_endpoint": case.primary.path,
                    "candidate_endpoint": case.candidate.path,
                    "primary_price_usd": str(endpoint_prices[case.primary.path]),
                    "candidate_price_usd": str(endpoint_prices[case.candidate.path]),
                    "primary_http_status": primary_status,
                    "candidate_http_status": candidate_status,
                    "primary_provider_code": _provider_code(primary_body),
                    "candidate_provider_code": _provider_code(candidate_body),
                    "id_comparison": comparison_payload,
                    "shape_comparison": _shape_summary(primary_body, candidate_body),
                }
            )

    report = {
        "schema_version": "stage7-tikhub-api-family-probe.v1",
        "base_url": BASE_URL,
        "keyword": KEYWORD,
        "case_count": len(cases),
        "business_request_count": len(cases) * 2,
        "endpoint_info_request_count": len(endpoint_prices),
        "hidden_retries": 0,
        "estimated_business_cost_usd": str(estimated_business_cost),
        "max_estimated_business_cost_usd": str(MAX_ESTIMATED_BUSINESS_COST_USD),
        "results": results,
    }
    (output / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    run_probe()


if __name__ == "__main__":
    main()
