from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
READY_CHECK = REPO_ROOT / ".agents/skills/reliable-vibe-coding/scripts/ready_check.py"
TEMPLATE = REPO_ROOT / ".agents/skills/reliable-vibe-coding/assets/CHANGE.template.md"


def _change_document(
    *,
    status: str = "ready_for_review",
    requirement_status: str = "satisfied",
    source: str = "AGENTS.md",
    evidence: str = "tests: ready-check",
    audit_checked: bool = True,
    completion_gate: bool = True,
) -> str:
    gate = "completion_gate: required\n" if completion_gate else ""
    checked = "x" if audit_checked else " "
    return f"""---
schema: rvc-change/v1
id: CHG-20260823-ready-check-fixture
title: Ready Check Fixture
level: L2
status: {status}
owner: test
branch: test/ready-check
created: 2026-08-23
updated: 2026-08-23
{gate}depends_on: []
affected_areas: []
affected_paths: []
contracts: []
data_changes: []
---

# 目标

测试 Completion Gate。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 必须满足上游要求 | {source} | {requirement_status} | {evidence} |

# Completion Audit

- [{checked}] upstream_re_read：已重新读取所有上游正式事实源，并从它们独立重建完成定义。
- [{checked}] change_coverage：已确认当前 Change 覆盖全部上游要求，没有把 Change 自身当作需求全集。
- [{checked}] reverse_audit：已执行适用的反向能力/边界审计；不适用项已有明确依据。
- [{checked}] unresolved_cleared：所有 not_satisfied 已清零；延期/不适用项均有正式依据。
"""


class ReadyCheckTest(unittest.TestCase):
    def _run(self, root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(READY_CHECK), "--root", str(root), *extra],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    @staticmethod
    def _write_change(root: Path, document: str, *, archive: bool = False) -> Path:
        if archive:
            path = (
                root
                / "changes/archive/2026-08/CHG-20260823-ready-check-fixture/CHANGE.md"
            )
        else:
            path = root / "changes/active/CHG-20260823-ready-check-fixture/CHANGE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document, encoding="utf-8")
        return path

    def test_template_enables_completion_gate(self) -> None:
        content = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("completion_gate: required", content)
        self.assertIn("# Requirement Traceability", content)
        self.assertIn("# Completion Audit", content)

    def test_complete_ready_change_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            self._write_change(root, _change_document())
            result = self._run(root, "--require-active-ready")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_legacy_change_remains_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_change(root, _change_document(completion_gate=False))
            result = self._run(root, "--require-active-ready")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("legacy", result.stdout.casefold())

    def test_malformed_legacy_change_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_change(
                root,
                "---\nid: CHG-20260823-ready-check-fixture\nstatus: done\n---\nlegacy\n",
                archive=True,
            )
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("legacy=1", result.stdout)

    def test_not_satisfied_blocks_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            self._write_change(root, _change_document(requirement_status="not_satisfied"))
            result = self._run(root, "--require-active-ready")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not_satisfied", result.stdout + result.stderr)

    def test_unchecked_completion_audit_blocks_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            self._write_change(root, _change_document(audit_checked=False))
            result = self._run(root, "--require-active-ready")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Completion Audit", result.stdout + result.stderr)

    def test_missing_repository_requirement_source_blocks_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_change(root, _change_document(source="docs/missing.md"))
            result = self._run(root, "--require-active-ready")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("docs/missing.md", result.stdout + result.stderr)

    def test_current_change_cannot_be_its_own_requirement_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "changes/active/CHG-20260823-ready-check-fixture/CHANGE.md"
            self._write_change(root, _change_document(source=source))
            result = self._run(root, "--require-active-ready")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("不能把自身作为 Requirement Source", result.stdout + result.stderr)

    def test_placeholder_evidence_blocks_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            self._write_change(root, _change_document(evidence="TBD"))
            result = self._run(root, "--require-active-ready")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("TBD", result.stdout + result.stderr)

    def test_archived_completion_gate_requires_done(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            self._write_change(root, _change_document(status="ready_for_review"), archive=True)
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("done", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
