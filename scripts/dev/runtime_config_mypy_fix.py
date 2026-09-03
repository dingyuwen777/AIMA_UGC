#!/usr/bin/env python3
"""Temporary one-shot type-fix helper for PR #318.

The companion workflow removes this file before committing the actual fix.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


def patch_runtime_config() -> None:
    path = "backend/src/aima_ugc/bootstrap/runtime_config.py"
    text = read(path)
    text = replace_once(
        text,
        '        model=data.get("model") if isinstance(data.get("model"), str) else None,\n',
        '        model=_optional_str(data, "model"),\n',
        label="runtime snapshot model",
    )
    text = replace_once(
        text,
        '\n\ndef _required_str(data: dict[str, object], key: str) -> str:\n',
        '\n\ndef _optional_str(data: dict[str, object], key: str) -> str | None:\n'
        '    value = data.get(key)\n'
        '    return value if isinstance(value, str) else None\n'
        '\n\ndef _required_str(data: dict[str, object], key: str) -> str:\n',
        label="runtime snapshot optional string helper",
    )
    write(path, text)


def patch_analysis_worker() -> None:
    path = "backend/src/aima_ugc/bootstrap/analysis_worker.py"
    text = read(path)
    text = replace_once(
        text,
        '                snapshot = run["runtime_config_snapshot"]\n'
        '                if isinstance(snapshot, dict) and snapshot:\n',
        '                snapshot = run["runtime_config_snapshot"]\n'
        '                base_url: str\n'
        '                model: str\n'
        '                provider_name: str | None\n'
        '                timeout_seconds: float\n'
        '                max_connections: int\n'
        '                validation_retries: int\n'
        '                if isinstance(snapshot, dict) and snapshot:\n',
        label="analysis worker frozen runtime variable types",
    )
    write(path, text)


def patch_collection_scope() -> None:
    path = "backend/src/aima_ugc/bootstrap/collection_scope.py"
    text = read(path)
    text = replace_once(
        text,
        'from pydantic import SecretStr\n',
        'from pydantic import JsonValue, SecretStr\n',
        label="collection scope JsonValue import",
    )
    text = replace_once(
        text,
        '                extra_config=runtime_config.extra_config or {},\n',
        '                extra_config=cast(\n'
        '                    dict[str, JsonValue], runtime_config.extra_config or {}\n'
        '                ),\n',
        label="collection scope extra_config type",
    )
    write(path, text)


def main() -> int:
    patch_runtime_config()
    patch_analysis_worker()
    patch_collection_scope()
    subprocess.run(
        [
            "uv",
            "run",
            "ruff",
            "format",
            "backend/src/aima_ugc/bootstrap/runtime_config.py",
            "backend/src/aima_ugc/bootstrap/analysis_worker.py",
            "backend/src/aima_ugc/bootstrap/collection_scope.py",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(["uv", "run", "mypy", "backend/src"], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
