from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


class DevelopmentGuidanceTest(unittest.TestCase):
    def _read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_skill_exposes_internal_comment_and_observability_rules(self) -> None:
        skill = self._read(".agents/skills/reliable-vibe-coding/SKILL.md")
        self.assertIn("内部/private/helper 函数", skill)
        self.assertIn("重要功能可观测性", skill)
        self.assertIn("禁止打印 Secret/Token/密码", skill)

    def test_development_workflow_contains_actionable_guidance(self) -> None:
        workflow = self._read(
            ".agents/skills/reliable-vibe-coding/references/development-workflows.md"
        )
        self.assertIn("## 代码注释", workflow)
        self.assertIn("内部/private/helper 函数包含非显然业务规则", workflow)
        self.assertIn("## 可观测性与日志", workflow)
        self.assertIn("同一异常优先在真正拥有处理/终止责任的边界记录一次", workflow)

    def test_review_and_aima_blueprints_consume_the_rules(self) -> None:
        review = self._read(
            ".agents/skills/reliable-vibe-coding/references/verification-review.md"
        )
        blueprint05 = self._read("docs/blueprint/05_日志安全部署与运维.md")
        blueprint06 = self._read("docs/blueprint/06_开发约束与分阶段实施.md")
        self.assertIn("非显然内部/private/helper", review)
        self.assertIn("最小充分可观测性", review)
        self.assertIn("功能开发时怎样选择日志观测点", blueprint05)
        self.assertIn("代码注释与关键日志也属于实现质量", blueprint06)


if __name__ == "__main__":
    unittest.main()
