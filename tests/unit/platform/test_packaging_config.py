"""Python 分发包边界回归测试。"""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_runtime_outputs_and_local_env_are_excluded_from_distributions() -> None:
    root = Path(__file__).resolve().parents[3]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    excluded = set(pyproject["tool"]["uv"]["build-backend"]["source-exclude"])

    assert {".env", "output"} <= excluded
