"""Stage 7 Business Decision Probe 只准备输入并调用正式决策。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "dev" / "probe_collection_decision.py"


def _run_probe(tmp_path: Path, payload: dict[str, object]) -> dict[str, object]:
    input_path = tmp_path / "decision.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(input_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, dict)
    return parsed


def test_probe_defaults_to_current_xhs_capability_and_returns_explainable_decision(
    tmp_path: Path,
) -> None:
    decision = _run_probe(
        tmp_path,
        {
            "current": {"comment_count": 35, "comments_available": True},
            "previous": {"comment_count": 35},
        },
    )

    assert decision["detail_action"] == "skip"
    assert decision["detail_reason"] == "unchanged"
    assert decision["comment_action"] == "skip"
    assert decision["comment_reason"] == "comment_count_unchanged"


def test_probe_zero_comment_keeps_zero_semantics(tmp_path: Path) -> None:
    decision = _run_probe(tmp_path, {"current": {"comment_count": 0}})

    assert decision["detail_action"] == "fetch"
    assert decision["comment_action"] == "skip"
    assert decision["comment_reason"] == "provider_reported_zero"
