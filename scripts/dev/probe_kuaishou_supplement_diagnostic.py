"""临时快手真实补采诊断；最终合并前删除。"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from aima_ugc.adapters.providers.imports import convert_excel_to_canonical_jsonl
from aima_ugc.adapters.providers.tikhub.probe import TikHubOperationProbe, TikHubProbeLimits
from aima_ugc.adapters.providers.tikhub.runtime import (
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
from openpyxl import Workbook
from pydantic import SecretStr

_HEADERS = (
    "文章编号",
    "媒体名称（中文）",
    "标题",
    "内文",
    "作者",
    "出版日期",
    "原文链接",
)


def _business_code(body: object) -> object:
    return body.get("code") if isinstance(body, dict) else "non_json"


def _mapping_context(*, operation: str, external_content_id: str):  # type: ignore[no-untyped-def]
    return mapping_context(
        provider_request_id=str(uuid4()),
        provider_attempt_id=str(uuid4()),
        raw_artifact_id=uuid4(),
        operation=operation,
        source_type="real_excel_probe",
        source_value=external_content_id,
        observed_at=datetime.now(UTC),
        external_content_id=external_content_id,
    )


def _roundtrip_excel(sample: dict[str, object]) -> CanonicalContentV1:
    with TemporaryDirectory(prefix="aima-kuaishou-diagnostic-") as temp_dir:
        root = Path(temp_dir)
        source = root / "probe.xlsx"
        output = root / "contents.jsonl"
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "文章"
        worksheet.append(_HEADERS)
        worksheet.append(
            (
                sample["article_id"],
                "快手",
                "Kuaishou Excel Probe",
                "真实 Excel URL 的受控 TikHub 补采验证",
                "probe",
                datetime.now(UTC).replace(tzinfo=None),
                sample["url"],
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
            raise RuntimeError("Excel Parser 未生成唯一 Content")
        return CanonicalContentV1.model_validate_json(output.read_text(encoding="utf-8").strip())


def main() -> int:
    key = os.environ.get("TIKHUB_API_KEY", "").strip()
    if not key:
        raise RuntimeError("TikHub Probe 凭据未安全注入")
    payload = json.loads(
        Path("tests/fixtures/imports/excel_provider_lookup_samples.json").read_text(encoding="utf-8")
    )
    samples = payload["platforms"]["kuaishou"]
    with TikHubHttpTransport(base_url="https://api.tikhub.io") as transport:
        probe = TikHubOperationProbe(
            transport=transport,
            credential=SecretStr(key),
            limits=TikHubProbeLimits(max_requests=12, max_estimated_cost=Decimal("0.10")),
        )
        for sample in samples:
            row = sample["row"]
            try:
                imported = _roundtrip_excel(sample)
            except Exception as exc:
                print(f"row={row} stage=excel result={type(exc).__name__}")
                continue

            try:
                detail_call = build_detail_call("kuaishou", imported)
                detail_response = probe.execute(detail_call).response
                print(
                    f"row={row} stage=detail_http http={detail_response.status_code} "
                    f"business_code={_business_code(detail_response.body)}"
                )
                if not isinstance(detail_response.body, dict):
                    continue
                detail_items = extract_detail_items("kuaishou", detail_response.body)
                print(f"row={row} stage=detail_extract item_count={len(detail_items)}")
                if not detail_items:
                    continue
                detail = map_content(
                    platform="kuaishou",
                    raw=detail_items[0],
                    context=_mapping_context(
                        operation=detail_call.operation,
                        external_content_id=imported.external_content_id,
                    ),
                    item_locator="diagnostic-detail:0",
                )
                print(f"row={row} stage=detail_map result=ok")
            except Exception as exc:
                print(f"row={row} stage=detail result={type(exc).__name__}")
                continue

            try:
                comments_call = build_comments_call(
                    platform="kuaishou",
                    external_content_id=detail.external_content_id,
                    state=None,
                )
                comments_response = probe.execute(comments_call).response
                print(
                    f"row={row} stage=comments_http http={comments_response.status_code} "
                    f"business_code={_business_code(comments_response.body)}"
                )
                if not isinstance(comments_response.body, dict):
                    continue
                comments = extract_comment_items("kuaishou", comments_response.body)
                print(f"row={row} stage=comments_extract item_count={len(comments)}")
                if not comments:
                    continue
                first = comments[0]
                print(
                    f"row={row} stage=comment_shape keys={','.join(sorted(str(key) for key in first))}"
                )
                mapped = map_comment(
                    platform="kuaishou",
                    raw=first,
                    context=_mapping_context(
                        operation=comments_call.operation,
                        external_content_id=detail.external_content_id,
                    ),
                    item_locator="diagnostic-comment:0",
                    is_root=True,
                )
                same_content = mapped.external_content_id == detail.external_content_id
                print(
                    f"row={row} stage=comment_map result=ok same_content={str(same_content).lower()} "
                    f"comment_id_present={str(bool(mapped.external_comment_id)).lower()}"
                )
            except Exception as exc:
                print(f"row={row} stage=comments result={type(exc).__name__}")
    print(f"request_count={probe.request_count} planned_cost_usd={probe.cumulative_planned_cost}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
