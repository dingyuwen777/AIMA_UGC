from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SKILL_ROOT = ROOT / ".agents" / "skills" / "coding"
REFERENCES = SKILL_ROOT / "references"
CODING_CLI = SKILL_ROOT / "scripts" / "coding.py"


class CodingMigrationCleanlinessTest(unittest.TestCase):
    def _read(self, path: Path) -> str:
        """读取迁移完整性测试需要检查的 UTF-8 文本文件。"""
        return path.read_text(encoding="utf-8")

    def test_current_live_skill_surfaces_do_not_use_legacy_brand_or_path(self) -> None:
        """当前 live Skill 表面不得继续使用旧品牌或旧 canonical 路径。"""
        legacy_brand = "Reliable Vibe Coding"
        legacy_path = ".agents/skills/" + "reliable-vibe-coding/"
        current_surfaces = [
            SKILL_ROOT / "SKILL.md",
            SKILL_ROOT / "agents" / "openai.yaml",
            SKILL_ROOT / "assets" / "CHANGE.template.md",
            *sorted(REFERENCES.glob("0[1-9]_*.md")),
            *sorted(REFERENCES.glob("1[01]_*.md")),
        ]

        for path in current_surfaces:
            content = self._read(path)
            relative = path.relative_to(ROOT)
            self.assertNotIn(legacy_brand, content, str(relative))
            self.assertNotIn(legacy_path, content, str(relative))

        self.assertFalse((ROOT / ".agents" / "skills" / "reliable-vibe-coding").exists())

    def test_current_guidance_uses_coding_cli(self) -> None:
        """当前使用指引必须引用真实存在的 coding.py 与 Ready Check 路径。"""
        collaboration = self._read(REFERENCES / "09_多人和多智能体并行协作.md")
        template = self._read(SKILL_ROOT / "assets" / "CHANGE.template.md")

        self.assertNotIn("scripts/rvc.py", collaboration)
        self.assertIn("python <skill>/scripts/coding.py conflicts --root <repo> --json", collaboration)
        self.assertNotIn("reliable-vibe-coding/scripts/ready_check.py", template)
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

    def test_preservation_map_marks_legacy_cli_as_history_and_points_to_current_cli(self) -> None:
        """规则保留映射必须同时准确保留迁移前事实和当前 canonical 指向。"""
        preservation = self._read(REFERENCES / "12_规则保留映射.md")

        self.assertTrue(preservation.startswith("# Coding 规则保留映射\n"))
        self.assertIn("迁移前原路径为：", preservation)
        self.assertGreaterEqual(preservation.count("迁移前原命令为："), 2)
        self.assertIn(".reliable-vibe-coding/project-context.json", preservation)
        self.assertIn(".agents/project-context.json", preservation)
        self.assertIn("python <skill>/scripts/rvc.py discover --root <repo>", preservation)
        self.assertIn("python <skill>/scripts/rvc.py status --root <repo> --json", preservation)
        self.assertIn("python <skill>/scripts/coding.py discover --root <repo>", preservation)
        self.assertIn("python <skill>/scripts/coding.py status --root <repo> --json", preservation)
        self.assertNotIn(
            ".agents/skills/reliable-vibe-coding/references/08_分层测试与验收策略.md",
            preservation,
        )
        self.assertIn(
            ".agents/skills/coding/references/08_分层测试与验收策略.md",
            preservation,
        )

    def test_change_schema_compatibility_identifier_is_preserved(self) -> None:
        """迁移清理不得修改仍受支持的 rvc-change/v1 兼容标识。"""
        template = self._read(SKILL_ROOT / "assets" / "CHANGE.template.md")
        self.assertIn("schema: rvc-change/v1", template)


if __name__ == "__main__":
    unittest.main()
