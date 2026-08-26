from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
CLASSIFIER_PATH = ROOT / "scripts" / "quality" / "classify_ci_scope.py"


class DocsCiFastPathTest(unittest.TestCase):
    def _read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def _load_classifier(self):
        self.assertTrue(CLASSIFIER_PATH.exists(), "缺少 CI changed-scope classifier")
        spec = importlib.util.spec_from_file_location("classify_ci_scope", CLASSIFIER_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_coding_skill_requires_documentation_governance_fast_path(self) -> None:
        skill = self._read(".agents/skills/coding/SKILL.md")
        validation = self._read(".agents/skills/coding/references/07_通用验证与证据策略.md")

        self.assertIn("永久 CI/Workflow 优化必须证据守恒", skill)
        self.assertIn("07_通用验证与证据策略.md", skill)
        self.assertIn("Documentation / Governance Fast Path", validation)
        self.assertIn("纯文档", validation)
        self.assertIn("不得为了形式机械运行完整产品 CI", validation)
        self.assertIn("Prompt", validation)
        self.assertIn("未知路径", validation)
        self.assertIn("docs_only", validation)
        self.assertIn("governance_only", validation)
        self.assertIn("full", validation)

    def test_scope_classifier_is_conservative(self) -> None:
        classifier = self._load_classifier()

        self.assertEqual(classifier.classify_paths(["docs/blueprint/README.md"]), "docs_only")
        self.assertEqual(classifier.classify_paths(["README.md", "backend/src/aima_ugc/modules/system/README.md"]), "docs_only")
        self.assertEqual(classifier.classify_paths(["changes/archive/2026-08/example/CHANGE.md"]), "governance_only")
        self.assertEqual(classifier.classify_paths(["AGENTS.md", ".agents/skills/coding/README.md"]), "governance_only")
        self.assertEqual(
            classifier.classify_paths(["backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md"]),
            "full",
        )
        self.assertEqual(classifier.classify_paths(["backend/src/aima_ugc/modules/analysis/service.py"]), "full")
        self.assertEqual(classifier.classify_paths(["unknown-notes.md"]), "full")
        self.assertEqual(classifier.classify_paths([]), "full")

    def test_ci_keeps_ci_gate_and_routes_lightweight_profiles(self) -> None:
        ci = self._read(".github/workflows/ci.yml")

        self.assertIn("name: CI Scope", ci)
        self.assertIn("classify_ci_scope.py", ci)
        self.assertIn("name: Docs and Governance", ci)
        self.assertIn("needs.scope.outputs.profile != 'full'", ci)
        self.assertIn("needs.scope.outputs.profile == 'full'", ci)
        self.assertIn("name: Repository Quality", ci)
        self.assertIn("name: PostgreSQL Integration", ci)
        self.assertIn("name: CI Gate", ci)
        self.assertIn("if: always()", ci)
        self.assertIn("check_docs.py", ci)
        self.assertIn("scan_secrets.py", ci)

    def test_fullstack_and_blueprint_follow_same_fast_path_boundary(self) -> None:
        fullstack = self._read(".github/workflows/fullstack.yml")
        blueprint = self._read("docs/blueprint/06_开发约束与分阶段实施.md")

        self.assertIn('      - ".agents/**"', fullstack)
        self.assertIn('      - "AGENTS.md"', fullstack)
        self.assertIn('      - "README.md"', fullstack)
        self.assertIn('      - "**/README.md"', fullstack)
        self.assertNotIn("prompts/**", fullstack)

        self.assertIn("风险相关 required CI profile", blueprint)
        self.assertIn("docs_only", blueprint)
        self.assertIn("governance_only", blueprint)
        self.assertIn("Prompt", blueprint)

    def test_governance_secret_scan_covers_agents(self) -> None:
        secret_scan = self._read("scripts/quality/scan_secrets.py")
        self.assertIn('ROOT / ".agents"', secret_scan)


if __name__ == "__main__":
    unittest.main()
