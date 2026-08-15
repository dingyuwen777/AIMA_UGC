"""固定 Contract 的基础兼容与生成物检查。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI_TARGET = ROOT / "contracts" / "openapi" / "openapi.json"
CANONICAL_TARGETS = [
    "contracts/canonical/content.v1.schema.json",
    "contracts/canonical/comment.v1.schema.json",
    "contracts/canonical/content.aggregate.v1.schema.json",
]
PROVIDER_TARGETS = [
    "contracts/provider/request.v1.schema.json",
    "contracts/provider/attempt.v1.schema.json",
    "contracts/provider/raw-envelope.v1.schema.json",
]
COLLECTION_TARGETS = [
    "contracts/collection/decision-request.v1.schema.json",
    "contracts/collection/decision.v1.schema.json",
    "contracts/collection/provider-config.v1.schema.json",
    "contracts/collection/provider-platform-capability.v1.schema.json",
    "contracts/collection/provider-platform-route.v1.schema.json",
]


def main() -> int:
    if not OPENAPI_TARGET.exists():
        print("CONTRACT_MISSING: contracts/openapi/openapi.json 不存在")
        return 1

    spec = json.loads(OPENAPI_TARGET.read_text(encoding="utf-8"))
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

    diff = subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            "--",
            *CANONICAL_TARGETS,
            *PROVIDER_TARGETS,
            *COLLECTION_TARGETS,
        ],
        cwd=ROOT,
        check=False,
    )
    if diff.returncode != 0:
        print(
            "CONTRACT_SCHEMA_STALE: 生成后的 Canonical/Provider/Collection JSON Schema "
            "与提交版本不一致"
        )
        return 1

    print("OpenAPI 基线与 Canonical/Provider/Collection Schema 漂移检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
