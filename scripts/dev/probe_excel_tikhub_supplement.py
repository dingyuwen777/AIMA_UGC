"""用五个平台各一条已验证 Excel 公共链接复核 TikHub Detail + 一级评论补采。

该脚本只用于显式受控 Probe：
- API Key 只从环境变量读取，不写文件、不打印；
- 固定样本来自 ``tests/fixtures/imports/excel_provider_lookup_samples.json``；
- fixture 必须且只能为五个平台各一条链接，禁止运行时搜索或候选遍历；
- 每条链接必须先经过生产 Excel Converter/identity parser，再进入正式 TikHub Runtime；
- 请求经过生产 Operation / TikHubOperationProbe / Transport / Extractor / Mapper；
- 一次完整 Probe 最多 10 次请求：每个平台恰好 Detail + 一级评论各一次；
- 固定样本若失效则明确失败，后续通过独立维护动作替换该平台样本；
- 不写 PostgreSQL，不保存 Provider Raw Response。
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from uuid import uuid4

from aima_ugc.adapters.providers.imports import convert_excel_to_canonical_jsonl
from aima_ugc.adapters.providers.tikhub.probe import TikHubOperationProbe, TikHubProbeLimits
from aima_ugc.adapters.providers.tikhub.runtime import (
    TikHubOperationCall,
    TikHubPlatform,
    build_comments_call,
    build_detail_call,
    extract_comment_items,
    extract_detail_items,
    map_comment,
    map_content,
    mapping_context,
)
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.modules.collection.providers.transport import ProviderTransportResponse
from openpyxl import Workbook
from pydantic import SecretStr

_PLATFORMS: tuple[TikHubPlatform, ...] = (
    "xiaohongshu",
    "douyin",
    "weibo",
    "bilibili",
    "kuaishou",
)
_MEDIA_NAMES: dict[TikHubPlatform, str] = {
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "weibo": "新浪微博",
    "bilibili": "哔哩哔哩",
    "kuaishou": "快手",
}
_LOOKUP_TYPES: dict[TikHubPlatform, tuple[str, ...]] = {
    "xiaohongshu": ("note_id",),
    "douyin": ("aweme_id",),
    "weibo": ("status_id",),
    "bilibili": ("av_id", "bv_id"),
    "kuaishou": ("photo_id",),
}
_HEADERS = (
    "文章编号",
    "媒体名称（中文）",
    "标题",
    "内文",
    "作者",
    "出版日期",
    "原文链接",
)
_DEFAULT_SAMPLES = Path("tests/fixtures/imports/excel_provider_lookup_samples.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="验证固定五平台 Excel 链接 → TikHub 详情/评论补采")
    parser.add_argument("--samples", type=Path, default=_DEFAULT_SAMPLES)
    parser.add_argument("--output", type=Path, default=Path("tikhub-excel-supplement-probe.json"))
    args = parser.parse_args()

    api_key = os.environ.get("TIKHUB_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("TikHub Probe 凭据未安全注入")
    base_url = os.environ.get("TIKHUB_BASE_URL", "https://api.tikhub.io").strip()
    samples = _load_samples(args.samples)

    # 五个平台各固定 Detail + Comments 两次请求；预算硬上限只服务显式 Probe。
    limits = TikHubProbeLimits(max_requests=10, max_estimated_cost=Decimal("0.10"))
    results: list[dict[str, object]] = []
    with TikHubHttpTransport(base_url=base_url) as transport:
        probe = TikHubOperationProbe(
            transport=transport,
            credential=SecretStr(api_key),
            limits=limits,
        )
        for platform in _PLATFORMS:
            sample = cast(list[dict[str, object]], samples["platforms"][platform])[0]
            results.append(_probe_platform(probe=probe, platform=platform, sample=sample))

    if probe.request_count != 10:
        raise RuntimeError(f"固定五平台 Probe 预期 10 次请求，实际 {probe.request_count} 次")
    payload = {
        "verified_at": datetime.now(UTC).isoformat(),
        "source": samples["source"],
        "source_sha256": samples["source_sha256"],
        "request_count": probe.request_count,
        "cumulative_planned_cost_usd": str(probe.cumulative_planned_cost),
        "platforms": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # 只输出非敏感验收摘要；不输出 URL、API Key、Comment ID 或 Raw Response。
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _load_samples(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Excel Probe 样本必须是 JSON Object")
    platforms = payload.get("platforms")
    if not isinstance(platforms, dict) or set(platforms) != set(_PLATFORMS):
        raise ValueError("Excel Probe 样本必须且只能包含五个平台")
    if not isinstance(payload.get("source"), str) or not isinstance(payload.get("source_sha256"), str):
        raise ValueError("Excel Probe 样本缺少源文件名或 SHA-256")
    for platform in _PLATFORMS:
        items = platforms.get(platform)
        if not isinstance(items, list) or len(items) != 1:
            raise ValueError(f"{platform}: 固定 Excel Probe 样本必须恰好一条")
        item = items[0]
        if not isinstance(item, dict):
            raise ValueError(f"{platform}: Excel Probe 样本项类型非法")
        if not isinstance(item.get("url"), str) or not isinstance(item.get("article_id"), str):
            raise ValueError(f"{platform}: Excel Probe 样本缺少公开 URL/文章编号")
        if not isinstance(item.get("row"), int):
            raise ValueError(f"{platform}: Excel Probe 样本缺少来源行号")
    return cast(dict[str, Any], payload)


def _probe_platform(
    *,
    probe: TikHubOperationProbe,
    platform: TikHubPlatform,
    sample: dict[str, object],
) -> dict[str, object]:
    try:
        imported = _roundtrip_excel(platform=platform, sample=sample)
        lookup_types = _assert_lookup_identity(platform, imported)
        detail = _probe_detail(probe=probe, platform=platform, imported=imported)
        _probe_comments(probe=probe, platform=platform, detail=detail)
    except Exception as exc:
        raise RuntimeError(
            f"{platform}: 固定 Excel Probe 样本已失效或 Provider 链路失败；"
            "请先通过显式维护验证替换该平台单条样本"
        ) from exc
    return {
        "platform": platform,
        "source_row": sample["row"],
        "lookup_types": lookup_types,
        "detail": "ok",
        "comments": "ok",
    }


def _roundtrip_excel(
    *,
    platform: TikHubPlatform,
    sample: dict[str, object],
) -> CanonicalContentV1:
    article_id = cast(str, sample["article_id"])
    url = cast(str, sample["url"])
    with TemporaryDirectory(prefix=f"aima-{platform}-excel-probe-") as temp_dir:
        root = Path(temp_dir)
        source = root / "probe.xlsx"
        output = root / "contents.jsonl"
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "文章"
        worksheet.append(_HEADERS)
        worksheet.append(
            (
                article_id,
                _MEDIA_NAMES[platform],
                f"{platform} Excel Probe",
                "固定真实 Excel URL 的受控 TikHub 补采验证",
                "probe",
                datetime.now(UTC).replace(tzinfo=None),
                url,
            )
        )
        workbook.save(source)
        workbook.close()
        summary = convert_excel_to_canonical_jsonl(
            input_path=source,
            output_path=output,
            profile_name="aima-monitoring-excel.v1",
            sheet_name="文章",
            observed_at=datetime.now(UTC),
        )
        if summary.rows_written != 1:
            raise RuntimeError(f"{platform}: Excel Parser 未生成唯一 Content")
        imported = CanonicalContentV1.model_validate_json(
            output.read_text(encoding="utf-8").strip()
        )
        if imported.alternate_ids.get("source_article_id") != article_id:
            raise RuntimeError(f"{platform}: Excel 来源文章编号未保留")
        return imported


def _probe_detail(
    *,
    probe: TikHubOperationProbe,
    platform: TikHubPlatform,
    imported: CanonicalContentV1,
) -> CanonicalContentV1:
    call = build_detail_call(platform, imported)
    response = _execute(probe, call)
    body = _response_body(response)
    items = extract_detail_items(platform, body)
    if not items:
        raise RuntimeError(f"{platform}: Detail 无可映射内容")
    detail = map_content(
        platform=platform,
        raw=items[0],
        context=_mapping_context(
            operation=call.operation,
            source_value=imported.external_content_id,
            external_content_id=imported.external_content_id,
        ),
        item_locator="probe-detail:0",
    )
    if detail.external_content_id != imported.external_content_id:
        raise RuntimeError(f"{platform}: Excel 与 Detail 内容身份不一致")
    return detail


def _probe_comments(
    *,
    probe: TikHubOperationProbe,
    platform: TikHubPlatform,
    detail: CanonicalContentV1,
) -> None:
    call = build_comments_call(
        platform=platform,
        external_content_id=detail.external_content_id,
        state=None,
    )
    response = _execute(probe, call)
    body = _response_body(response)
    items = extract_comment_items(platform, body)
    if not items:
        raise RuntimeError(f"{platform}: 一级评论响应为空")
    comment = map_comment(
        platform=platform,
        raw=items[0],
        context=_mapping_context(
            operation=call.operation,
            source_value=detail.external_content_id,
            external_content_id=detail.external_content_id,
        ),
        item_locator="probe-comment:0",
        is_root=True,
    )
    if comment.external_content_id != detail.external_content_id:
        raise RuntimeError(f"{platform}: Comment 与 Content 身份不一致")
    if not comment.external_comment_id:
        raise RuntimeError(f"{platform}: Comment 缺少 Provider comment ID")


def _execute(probe: TikHubOperationProbe, call: TikHubOperationCall) -> ProviderTransportResponse:
    response = probe.execute(call).response
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError("TikHub HTTP 响应非成功状态")
    return response


def _assert_lookup_identity(platform: TikHubPlatform, content: CanonicalContentV1) -> list[str]:
    lookup_types = [key for key in _LOOKUP_TYPES[platform] if content.alternate_ids.get(key)]
    if not lookup_types:
        raise RuntimeError(f"{platform}: Excel URL 未生成 typed Provider lookup identity")
    return lookup_types


def _mapping_context(
    *,
    operation: str,
    source_value: str,
    external_content_id: str | None = None,
):  # type: ignore[no-untyped-def]
    return mapping_context(
        provider_request_id=str(uuid4()),
        provider_attempt_id=str(uuid4()),
        raw_artifact_id=uuid4(),
        operation=operation,
        source_type="real_excel_probe",
        source_value=source_value,
        observed_at=datetime.now(UTC),
        external_content_id=external_content_id,
    )


def _response_body(response: ProviderTransportResponse) -> dict[str, Any]:
    value = response.body
    if not isinstance(value, dict):
        raise RuntimeError("TikHub 响应不是 JSON Object")
    status = value.get("code")
    if status not in {None, 200, "200"}:
        raise RuntimeError("TikHub 业务响应非成功状态")
    return {str(key): item for key, item in value.items()}


if __name__ == "__main__":
    raise SystemExit(main())
