"""生成或校验仓库固定 Contract。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aima_ugc.contracts.canonical import (
    CanonicalCommentV1,
    CanonicalContentAggregateV1,
    CanonicalContentV1,
)
from aima_ugc.entrypoints.api_main import create_app

ROOT = Path(__file__).resolve().parents[2]
OPENAPI_TARGET = ROOT / "contracts" / "openapi" / "openapi.json"
CANONICAL_DIR = ROOT / "contracts" / "canonical"
CANONICAL_MODELS = {
    "content.v1.schema.json": CanonicalContentV1,
    "comment.v1.schema.json": CanonicalCommentV1,
    "content.aggregate.v1.schema.json": CanonicalContentAggregateV1,
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


def render_canonical(model: type) -> str:
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
            CANONICAL_DIR / filename: render_canonical(model)
            for filename, model in CANONICAL_MODELS.items()
        }
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
        print("OpenAPI 与 Canonical Contract 已同步。")
        return 0

    for path, rendered in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        print(f"已生成 {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
