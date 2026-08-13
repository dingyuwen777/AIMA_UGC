"""Stage 1 OpenAPI 基线结构检查。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "contracts" / "openapi" / "openapi.json"


def main() -> int:
    if not TARGET.exists():
        print("CONTRACT_MISSING: contracts/openapi/openapi.json 不存在")
        return 1

    spec = json.loads(TARGET.read_text(encoding="utf-8"))
    paths = spec.get("paths", {})
    operation_ids: list[str] = []
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if operation_id is not None:
                operation_ids.append(operation_id)

    if len(operation_ids) != len(set(operation_ids)):
        print("CONTRACT_OPERATION_ID_DUPLICATE: operationId 必须全局唯一")
        return 1

    health = paths.get("/health/live", {}).get("get", {})
    if health.get("operationId") != "healthLive":
        print("CONTRACT_HEALTH_MISSING: /health/live 必须使用 operationId=healthLive")
        return 1

    print("Stage 1 OpenAPI 基线结构检查通过；历史兼容比较尚不适用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
