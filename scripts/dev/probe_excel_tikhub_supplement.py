"""从真实 TikHub 搜索结果构造 Excel 链接，并验证 Detail + 一级评论补采。

该脚本只用于显式受控 Probe：
- API Key 只从环境变量读取，不写文件、不打印；
- 请求必须经过生产 Operation / TikHubOperationProbe / Transport；
- Excel 链接必须经过生产 imports Parser，再进入正式 Detail/Comments builder；
- 原帖删除、私密或 Provider 返回不可用时尝试下一个搜索候选；
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
from typing import Any
from uuid import uuid4

from openpyxl import Workbook
from pydantic import SecretStr

from aima_ugc.adapters.providers.imports import convert_excel_to_canonical_jsonl
from aima_ugc.adapters.providers.tikhub.probe import (
    TikHubOperationProbe,
    TikHubProbeLimits,
)
from aima_ugc.adapters.providers.tikhub.runtime import (
    TikHubPlatform,
    build_comments_call,
    build_detail_call,
    build_search_call,
    extract_comment_items,
    extract_detail_items,
    extract_search_items,
    map_comment,
    map_content,
    mapping_context,
)
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from aima_ugc.contracts.canonical import CanonicalContentV1

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
_REQUIRED_HEADERS = (
    "媒体名称（中文）",
    "标题",
    "内文",
    "作者",
    "出版日期",
    "原文链接",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 Excel 帖子链接 → TikHub 详情/评论补采")
    parser.add_argument("--keyword", default="爱玛")
    parser.add_argument("--max-candidates-per-platform", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("tikhub-excel-supplement-probe.json"))
    args = parser.parse_args()
    if args.max_candidates_per_platform < 1 or args.max_candidates_per_platform > 5:
        raise ValueError("max-candidates-per-platform 必须在 1..5")

    api_key = os.environ.get("TIKHUB_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GitHub Actions Secret TIKHUB_API_KEY 未配置")
    base_url = os.environ.get("TIKHUB_BASE_URL", "https://api.tikhub.io").strip()

    # 五个平台各 1 次 Search + 最多 3 组 Detail/Comments；0.30 USD 足够当前 verified 价格上界。
    limits = TikHubProbeLimits(max_requests=35, max_estimated_cost=Decimal("0.30"))
    results: list[dict[str, object]] = []
    with TikHubHttpTransport(base_url=base_url) as transport:
        probe = TikHubOperationProbe(
            transport=transport,
            credential=SecretStr(api_key),
            limits=limits,
        )
        for platform in _PLATFORMS:
            results.append(
                _probe_platform(
                    probe=probe,
                    platform=platform,
                    keyword=args.keyword,
                    max_candidates=args.max_candidates_per_platform,
                )
            )

    payload = {
        "verified_at": datetime.now(UTC).isoformat(),
        "keyword": args.keyword,
        "request_count": probe.request_count,
        "cumulative_planned_cost_usd": str(probe.cumulative_planned_cost),
        "platforms": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _probe_platform(
    *,
    probe: TikHubOperationProbe,
    platform: TikHubPlatform,
    keyword: str,
    max_candidates: int,
) -> dict[str, object]:
    search_call = build_search_call(platform=platform, keyword=keyword)
    search_response = probe.execute(search_call).response
    search_body = _response_body(search_response.body)
    candidates: list[CanonicalContentV1] = []
    for raw_item in extract_search_items(platform, search_body):
        try:
            content = map_content(
                platform=platform,
                raw=raw_item,
                context=_mapping_context(operation=search_call.operation, source_value=keyword),
                item_locator=f"probe-search:{len(candidates)}",
            )
        except Exception:
            continue
        if (content.metrics.comment_count or 0) <= 0:
            continue
        if _content_url(platform, content) is None:
            continue
        candidates.append(content)
        if len(candidates) >= max_candidates:
            break

    if not candidates:
        raise RuntimeError(f"{platform}: 搜索结果中没有可验证且声明存在评论的内容")

    failures: list[str] = []
    for candidate in candidates:
        url = _content_url(platform, candidate)
        assert url is not None
        try:
            imported = _roundtrip_excel(platform=platform, url=url, candidate=candidate)
            _assert_lookup_identity(platform, imported)
            detail = _probe_detail(probe=probe, platform=platform, imported=imported)
            comment_id = _probe_comments(probe=probe, platform=platform, detail=detail)
        except Exception as exc:
            failures.append(type(exc).__name__)
            continue
        return {
            "platform": platform,
            "url": url,
            "external_content_id": imported.external_content_id,
            "lookup_types": sorted(
                key for key in imported.alternate_ids if key in _LOOKUP_TYPES[platform]
            ),
            "detail": "ok",
            "comments": "ok",
            "sample_comment_id": comment_id,
            "failed_candidates_before_success": len(failures),
        }

    raise RuntimeError(
        f"{platform}: {len(candidates)} 个候选均无法完成 Excel→Detail→Comments；"
        f"失败类型={','.join(failures)}"
    )


def _roundtrip_excel(
    *,
    platform: TikHubPlatform,
    url: str,
    candidate: CanonicalContentV1,
) -> CanonicalContentV1:
    with TemporaryDirectory(prefix=f"aima-{platform}-probe-") as temp_dir:
        root = Path(temp_dir)
        source = root / "probe.xlsx"
        output = root / "contents.jsonl"
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "文章"
        worksheet.append(_REQUIRED_HEADERS)
        worksheet.append(
            (
                _MEDIA_NAMES[platform],
                candidate.title or f"{platform} probe",
                candidate.text or "TikHub Excel supplement probe",
                candidate.author.display_name if candidate.author is not None else "probe",
                _excel_datetime(candidate.published_at),
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
        return CanonicalContentV1.model_validate_json(output.read_text(encoding="utf-8").strip())


def _excel_datetime(value: datetime | None) -> datetime:
    """openpyxl 不接受带时区的 datetime；Excel 仅承载本次 Probe 的输入样本。"""

    if value is None:
        return datetime.now(UTC).replace(tzinfo=None)
    if value.tzinfo is None or value.utcoffset() is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _probe_detail(
    *,
    probe: TikHubOperationProbe,
    platform: TikHubPlatform,
    imported: CanonicalContentV1,
) -> CanonicalContentV1:
    call = build_detail_call(platform, imported)
    response = probe.execute(call).response
    body = _response_body(response.body)
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
) -> str:
    call = build_comments_call(
        platform=platform,
        external_content_id=detail.external_content_id,
        state=None,
    )
    response = probe.execute(call).response
    body = _response_body(response.body)
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
    return comment.external_comment_id


def _content_url(platform: TikHubPlatform, content: CanonicalContentV1) -> str | None:
    if platform == "xiaohongshu":
        return f"https://www.xiaohongshu.com/explore/{content.external_content_id}"
    if platform == "douyin":
        return f"https://www.douyin.com/video/{content.external_content_id}"
    if platform == "weibo":
        if not content.external_content_id.isdigit():
            return None
        return f"https://weibo.com/detail/{content.external_content_id}"
    if platform == "bilibili":
        bv_id = content.alternate_ids.get("bv_id") or content.alternate_ids.get("bvid")
        if bv_id:
            return f"https://www.bilibili.com/video/{bv_id}"
        av_id = content.alternate_ids.get("av_id") or content.external_content_id
        return f"https://www.bilibili.com/video/av{av_id.removeprefix('av')}"
    if platform == "kuaishou":
        return f"https://www.kuaishou.com/short-video/{content.external_content_id}"
    return None


def _assert_lookup_identity(platform: TikHubPlatform, content: CanonicalContentV1) -> None:
    if not any(content.alternate_ids.get(key) for key in _LOOKUP_TYPES[platform]):
        raise RuntimeError(f"{platform}: Excel URL 未生成 typed Provider lookup identity")


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
        source_type="real_probe",
        source_value=source_value,
        observed_at=datetime.now(UTC),
        external_content_id=external_content_id,
    )


def _response_body(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("TikHub 响应不是 JSON Object")
    status = value.get("code")
    if status not in {None, 200, "200"}:
        raise RuntimeError("TikHub 业务响应非成功状态")
    return {str(key): item for key, item in value.items()}


if __name__ == "__main__":
    raise SystemExit(main())
