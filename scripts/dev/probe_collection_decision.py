"""使用显式 JSON 调用正式 Collection Decision Service。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aima_ugc.adapters.providers.tikhub.capabilities import XIAOHONGSHU_TIKHUB_CAPABILITY
from aima_ugc.contracts.collection import CollectionDecisionRequestV1
from aima_ugc.modules.collection import CollectionDecisionService


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """验证输入并返回正式生产 Decision；默认使用当前 xiaohongshu TikHub Capability。"""
    request_payload = dict(payload)
    request_payload.setdefault(
        "capability",
        XIAOHONGSHU_TIKHUB_CAPABILITY.model_dump(mode="json"),
    )
    request = CollectionDecisionRequestV1.model_validate(request_payload)
    decision = CollectionDecisionService().decide(request)
    return decision.model_dump(mode="json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="读取显式 JSON，调用正式 Stage 7 Collection Decision Service。"
    )
    parser.add_argument("input", type=Path, help="CollectionDecisionRequestV1 JSON 文件")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Decision Probe 输入顶层必须是 JSON object")

    print(json.dumps(evaluate_payload(payload), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
