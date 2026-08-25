"""Full-stack Provider Config 种子脚本的隔离边界测试。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_seed_script_requires_explicit_isolated_runtime_opt_in() -> None:
    """未显式确认隔离环境时，种子脚本必须在连接数据库前拒绝执行。"""

    root = Path(__file__).resolve().parents[3]
    environ = dict(os.environ)
    environ.pop("AIMA_FULLSTACK_SEED", None)
    environ["AIMA_DB_PORT"] = "1"

    completed = subprocess.run(
        [sys.executable, "tests/fullstack/seed_collection_plan_provider.py"],
        cwd=root,
        env=environ,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "AIMA_FULLSTACK_SEED=1" in completed.stderr
