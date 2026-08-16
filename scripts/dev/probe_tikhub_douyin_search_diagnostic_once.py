"""Stage 7 抖音 Search V2 参数组合最小真实诊断。

只用于解释当前生产默认 Search 在真实 TikHub 返回 HTTP 400 的原因。
不保存业务正文/账号/真实内容 ID；每个 case 只请求一次，无隐藏重试。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from aima_ugc.adapters.providers.tikhub.operations import douyin

BASE_URL = "https://api.tikhub.io"
ENDPOINT_INFO_PATH = "/api/v1/tikhub/user/get_endpoint_info"
ENDPOINT = "/api/v1/douyin/search/fetch_video_search_v2"
KEYWORD = "爱玛"
MAX_BUSINESS_COST_USD = Decimal("0.040000")


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    body: dict[str, object]


def _token() -> str:
    value = os.environ.get("AIMA_TIKHUB_PROBE_TOKEN", "").strip()
    if not value:
        raise RuntimeError("AIMA_TIKHUB_PROBE_TOKEN 未设置")
    return value


def _output() -> Path:
    raw = os.environ.get("AIMA_TIKHUB_PROBE_OUTPUT_DIR", "").strip()
    if not raw:
        raise RuntimeError("AIMA_TIKHUB_PROBE_OUTPUT_DIR 未设置")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cases() -> tuple[Case, ...]:
    default_request = douyin.build_video_search_request(keyword=KEYWORD)
    known_good_request = douyin.build_video_search_request(
        keyword=KEYWORD,
        sort_mode="latest",
        published_within="7d",
        duration="all",
        content_type="video",
    )
    if default_request.body is None or known_good_request.body is None:
        raise RuntimeError("抖音 Search V2 必须使用 JSON body")

    default_body = dict(default_request.body)
    default_without_session = dict(default_body)
    default_without_session.pop("search_id", None)
    default_without_session.pop("backtrace", None)

    known_good_body = dict(known_good_request.body)
    known_good_without_session = dict(known_good_body)
    known_good_without_session.pop("search_id", None)
    known_good_without_session.pop("backtrace", None)

    return (
        Case("current_default", default_body),
        Case("current_default_without_empty_session", default_without_session),
        Case("latest_7d_video", known_good_body),
        Case("latest_7d_video_without_empty_session", known_good_without_session),
    )


def _find_first(value: object, keys: tuple[str, ...]) -> object | None:
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                return value[key]
        for child in value.values():
            found = _find_first(child, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value[:3]:
            found = _find_first(child, keys)
            if found is not None:
                return found
    return None


def _safe_message(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:500]


def _endpoint_cost(client: httpx.Client) -> Decimal:
    response = client.get(ENDPOINT_INFO_PATH, params={"endpoint": ENDPOINT})
    response.raise_for_status()
    body: Any = response.json()
    raw = _find_first(body, ("endpoint_cost",))
    if raw is None:
        raise RuntimeError("endpoint-info 缺少 endpoint_cost")
    cost = Decimal(str(raw))
    if not cost.is_finite() or cost <= 0:
        raise RuntimeError("endpoint_cost 无效")
    return cost


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run() -> None:
    if os.environ.get("AIMA_TIKHUB_DOUYIN_DIAGNOSTIC_APPROVED") != "yes":
        raise RuntimeError("抖音真实诊断必须显式放行")

    cases = _cases()
    output = _output()
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/json",
        "User-Agent": "AIMA_UGC-stage7-douyin-search-diagnostic/1.0",
    }
    results: list[dict[str, object]] = []

    with httpx.Client(
        base_url=BASE_URL,
        headers=headers,
        timeout=httpx.Timeout(45.0),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        price = _endpoint_cost(client)
        estimated = price * len(cases)
        if estimated > MAX_BUSINESS_COST_USD:
            raise RuntimeError(f"预计业务费用超过硬上限: {estimated} > {MAX_BUSINESS_COST_USD}")

        for case in cases:
            response = client.post(ENDPOINT, json=case.body)
            try:
                parsed: Any = response.json()
            except ValueError as exc:
                raise RuntimeError(f"{case.name} 返回非 JSON，HTTP {response.status_code}") from exc
            if not isinstance(parsed, dict):
                raise RuntimeError(f"{case.name} JSON 根节点不是 object")
            item_count = len(douyin.extract_search_items(parsed))
            results.append(
                {
                    "name": case.name,
                    "request": {
                        "method": "POST",
                        "path": ENDPOINT,
                        "body": case.body,
                        "authorization": "Bearer <redacted-secret>",
                    },
                    "response": {
                        "http_status": response.status_code,
                        "provider_code": _find_first(parsed, ("code", "status_code")),
                        "message": _safe_message(
                            _find_first(parsed, ("message_zh", "message", "detail"))
                        ),
                        "top_level_keys": sorted(str(key) for key in parsed),
                        "search_item_count": item_count,
                    },
                    "unit_price_usd": str(price),
                }
            )

    _write(
        output / "summary.json",
        {
            "schema_version": "stage7-douyin-search-diagnostic.v1",
            "base_url": BASE_URL,
            "keyword": KEYWORD,
            "hidden_retries": 0,
            "business_request_count": len(cases),
            "max_business_cost_usd": str(MAX_BUSINESS_COST_USD),
            "results": results,
        },
    )


if __name__ == "__main__":
    run()
