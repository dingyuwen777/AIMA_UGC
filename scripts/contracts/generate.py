"""生成或校验固定 OpenAPI 文件。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aima_ugc.entrypoints.api_main import create_app

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "contracts" / "openapi" / "openapi.json"


def render_openapi() -> str:
    """返回确定性 OpenAPI JSON。"""
    return (
        json.dumps(
            create_app().openapi(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rendered = render_openapi()
    if args.check:
        if not TARGET.exists():
            print(f"OPENAPI_MISSING: {TARGET.relative_to(ROOT)} 不存在")
            return 1
        if TARGET.read_text(encoding="utf-8") != rendered:
            print("OPENAPI_STALE: 固定 OpenAPI 与当前 FastAPI Contract 不一致")
            return 1
        print("OpenAPI 已同步。")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(rendered, encoding="utf-8")
    print(f"已生成 {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
