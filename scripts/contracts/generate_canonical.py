"""生成或校验固定 Canonical V1 JSON Schema。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aima_ugc.contracts.canonical import (
    CanonicalCommentV1,
    CanonicalContentAggregateV1,
    CanonicalContentV1,
)

ROOT = Path(__file__).resolve().parents[2]
TARGET_DIR = ROOT / "contracts" / "canonical"
MODELS = {
    "content.v1.schema.json": CanonicalContentV1,
    "comment.v1.schema.json": CanonicalCommentV1,
    "content.aggregate.v1.schema.json": CanonicalContentAggregateV1,
}


def render_schema(model: type) -> str:
    return json.dumps(
        model.model_json_schema(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"


def sync_canonical(*, check: bool) -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    stale: list[str] = []
    for filename, model in MODELS.items():
        target = TARGET_DIR / filename
        rendered = render_schema(model)
        if check:
            if not target.exists() or target.read_text(encoding="utf-8") != rendered:
                stale.append(filename)
        else:
            target.write_text(rendered, encoding="utf-8")

    if stale:
        print("CANONICAL_SCHEMA_STALE: " + ", ".join(stale))
        return 1
    print("Canonical JSON Schema 已同步。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return sync_canonical(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
