"""临时快手真实补采诊断；最终合并前删除。"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

from aima_ugc.adapters.providers.tikhub.probe import TikHubOperationProbe, TikHubProbeLimits
from aima_ugc.adapters.providers.tikhub.runtime import (
    build_comments_call,
    build_detail_call,
    extract_comment_items,
    extract_detail_items,
    map_content,
)
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport
from pydantic import SecretStr

from scripts.dev.probe_excel_tikhub_supplement import (
    _mapping_context,
    _roundtrip_excel,
)


def _business_code(body: object) -> object:
    return body.get("code") if isinstance(body, dict) else "non_json"


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
                imported = _roundtrip_excel(platform="kuaishou", sample=sample)
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
                        source_value=imported.external_content_id,
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
            except Exception as exc:
                print(f"row={row} stage=comments result={type(exc).__name__}")
    print(f"request_count={probe.request_count} planned_cost_usd={probe.cumulative_planned_cost}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
