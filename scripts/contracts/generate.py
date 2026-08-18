"""生成或校验仓库固定 Contract。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import (
    CanonicalCommentV1,
    CanonicalContentAggregateV1,
    CanonicalContentV1,
)
from aima_ugc.contracts.collection import (
    CollectionDecisionRequestV1,
    CollectionDecisionV1,
    ProviderConfigV1,
    ProviderPlatformCapabilityV1,
    ProviderPlatformRouteV1,
)
from aima_ugc.contracts.export import UnifiedDataExcelV1
from aima_ugc.contracts.provider import ProviderAttemptV1, ProviderRequestV1, RawEnvelopeV1
from aima_ugc.entrypoints.api_main import create_app

ROOT = Path(__file__).resolve().parents[2]
OPENAPI_TARGET = ROOT / "contracts" / "openapi" / "openapi.json"
ANALYSIS_DIR = ROOT / "contracts" / "analysis"
CANONICAL_DIR = ROOT / "contracts" / "canonical"
PROVIDER_DIR = ROOT / "contracts" / "provider"
COLLECTION_DIR = ROOT / "contracts" / "collection"
EXPORT_DIR = ROOT / "contracts" / "export"
ANALYSIS_MODELS = {
    "content-record.v1.schema.json": UnifiedContentRecordV1,
}
CANONICAL_MODELS = {
    "content.v1.schema.json": CanonicalContentV1,
    "comment.v1.schema.json": CanonicalCommentV1,
    "content.aggregate.v1.schema.json": CanonicalContentAggregateV1,
}
PROVIDER_MODELS = {
    "request.v1.schema.json": ProviderRequestV1,
    "attempt.v1.schema.json": ProviderAttemptV1,
    "raw-envelope.v1.schema.json": RawEnvelopeV1,
}
COLLECTION_MODELS = {
    "decision-request.v1.schema.json": CollectionDecisionRequestV1,
    "decision.v1.schema.json": CollectionDecisionV1,
    "provider-config.v1.schema.json": ProviderConfigV1,
    "provider-operations-capability.v1.schema.json": ProviderPlatformCapabilityV1,
    "provider-operations-route.v1.schema.json": ProviderPlatformRouteV1,
}
EXPORT_MODELS = {
    "unified-data-excel.v1.schema.json": UnifiedDataExcelV1,
}


def render_openapi() -> str:
    return (
        json.dumps(
            create_app().openapi(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def render_schema(model: type) -> str:
    return (
        json.dumps(
            model.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected: dict[Path, str] = {OPENAPI_TARGET: render_openapi()}
    expected.update(
        {
            ANALYSIS_DIR / filename: render_schema(model)
            for filename, model in ANALYSIS_MODELS.items()
        }
    )
    expected.update(
        {
            CANONICAL_DIR / filename: render_schema(model)
            for filename, model in CANONICAL_MODELS.items()
        }
    )
    expected.update(
        {
            PROVIDER_DIR / filename: render_schema(model)
            for filename, model in PROVIDER_MODELS.items()
        }
    )
    expected.update(
        {
            COLLECTION_DIR / filename: render_schema(model)
            for filename, model in COLLECTION_MODELS.items()
        }
    )
    expected.update(
        {EXPORT_DIR / filename: render_schema(model) for filename, model in EXPORT_MODELS.items()}
    )

    if args.check:
        stale = [
            path.relative_to(ROOT)
            for path, rendered in expected.items()
            if not path.exists() or path.read_text(encoding="utf-8") != rendered
        ]
        if stale:
            print("CONTRACT_STALE: " + ", ".join(str(path) for path in stale))
            return 1
        print("OpenAPI、Analysis、Canonical、Provider、Collection 与 Export Contract 已同步。")
        return 0

    for path, rendered in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        print(f"已生成 {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
