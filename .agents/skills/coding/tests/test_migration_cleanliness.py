from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SKILL_ROOT = ROOT / ".agents" / "skills" / "coding"
REFERENCES = SKILL_ROOT / "references"
CODING_CLI = SKILL_ROOT / "scripts" / "coding.py"
THIS_FILE = Path(__file__).resolve()


class CodingMigrationCleanlinessTest(unittest.TestCase):
    def _read(self, path: Path) -> str:
        """读取迁移完整性测试需要检查的 UTF-8 文本文件。"""
        return path.read_text(encoding="utf-8")

    def _live_text_files(self) -> list[Path]:
        """返回当前 Coding Skill 中需要保持无旧迁移标识的文本文件。"""
        suffixes = {".md", ".yaml", ".yml", ".py"}
        return [
            path
            for path in sorted(SKILL_ROOT.rglob("*"))
            if path.is_file() and path.suffix in suffixes and path.resolve() != THIS_FILE
        ]

    def test_live_skill_contains_no_legacy_migration_identifiers(self) -> None:
        """当前 live Skill 不得保留旧品牌、旧目录、旧 CLI 或旧 reference 文件名。"""
        legacy_identifiers = [
            "Reliable" + " Vibe Coding",
            "reliable-" + "vibe-coding",
            "scripts/" + "rvc.py",
            "project-" + "discovery.md",
            "change-" + "management.md",
            "completion-" + "gate.md",
            "development-" + "workflows.md",
            "repository-" + "constraints.md",
            "testing-" + "strategy.md",
            "collaboration" + ".md",
            "verification-" + "review.md",
        ]

        for path in self._live_text_files():
            content = self._read(path)
            relative = path.relative_to(ROOT)
            for identifier in legacy_identifiers:
                self.assertNotIn(identifier, content, f"{relative}: {identifier}")

        self.assertFalse((ROOT / ".agents" / "skills" / ("reliable-" + "vibe-coding")).exists())

    def test_current_guidance_uses_coding_cli(self) -> None:
        """当前使用指引必须引用真实存在的 coding.py 与 Ready Check 路径。"""
        collaboration = self._read(REFERENCES / "09_多人和多智能体并行协作.md")
        template = self._read(SKILL_ROOT / "assets" / "CHANGE.template.md")

        self.assertIn("python <skill>/scripts/coding.py conflicts --root <repo> --json", collaboration)
        self.assertIn(
            "python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready",
            template,
        )

        for command in ("discover", "status", "conflicts"):
            result = subprocess.run(
                [sys.executable, str(CODING_CLI), command, "--help"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preservation_map_uses_only_current_canonical_locations(self) -> None:
        """规则保留映射只描述当前 canonical 路径与命令，不保留迁移前标识。"""
        preservation = self._read(REFERENCES / "12_规则保留映射.md")

        self.assertTrue(preservation.startswith("# Coding 规则保留映射\n"))
        self.assertIn(".agents/project-context.json", preservation)
        self.assertIn("python <skill>/scripts/coding.py discover --root <repo>", preservation)
        self.assertIn("python <skill>/scripts/coding.py status --root <repo> --json", preservation)
        self.assertIn(
            ".agents/skills/coding/references/08_分层测试与验收策略.md",
            preservation,
        )

    def test_change_schema_compatibility_identifier_is_preserved(self) -> None:
        """本次只清理 Skill 迁移标识，不改变仍在使用的 Change schema 标识。"""
        template = self._read(SKILL_ROOT / "assets" / "CHANGE.template.md")
        self.assertIn("schema: rvc-change/v1", template)


if __name__ == "__main__":
    unittest.main()
