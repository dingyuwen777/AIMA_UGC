from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


class DevelopmentGuidanceTest(unittest.TestCase):
    def _read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_skill_exposes_internal_comment_and_observability_rules(self) -> None:
        skill = self._read(".agents/skills/coding/SKILL.md")
        self.assertIn("内部/private/helper 函数", skill)
        self.assertIn("重要功能可观测性", skill)
        self.assertIn("禁止打印 Secret/Token/密码", skill)
        self.assertIn("所有时间相关默认采用北京时间", skill)
        self.assertIn("[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message", skill)

    def test_development_workflow_contains_actionable_guidance(self) -> None:
        workflow = self._read(".agents/skills/coding/references/05_设计实施与根因调试.md")
        self.assertIn("## 代码注释", workflow)
        self.assertIn("内部/private/helper 函数包含非显然业务规则", workflow)
        self.assertIn("## 时间基准", workflow)
        self.assertIn("## 可观测性与日志", workflow)
        self.assertIn("同一异常优先在真正拥有处理/终止责任的边界记录一次", workflow)
        self.assertIn("[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message", workflow)

    def test_figma_canvas_readability_guidance_is_owned_by_figma_skill(self) -> None:
        routing = self._read(".agents/skills/coding/references/02_跨项目研发任务路由.md")
        figma_skill = self._read(".agents/skills/figma/SKILL.md")
        layout = self._read(".agents/skills/figma/references/07_页面布局与真实可用性审计.md")
        preservation = self._read(".agents/skills/coding/references/12_规则保留映射.md")
        legacy = ROOT / ".agents/skills/coding/references/13_Figma设计画布与可读性规则.md"

        self.assertIn(".agents/skills/figma/SKILL.md", routing)
        self.assertIn("Coding 不维护第二套 Figma", routing)
        self.assertNotIn("13_Figma设计画布与可读性规则.md", routing)
        self.assertFalse(legacy.exists())

        self.assertIn("07_页面布局与真实可用性审计.md", figma_skill)
        self.assertIn("Canvas-level Review", figma_skill)
        self.assertIn("项目已经规定间距时，必须使用项目规则", layout)
        self.assertIn("24–32px", layout)
        self.assertIn("40–64px", layout)
        self.assertIn("64–80px", layout)
        self.assertIn("96–160px", layout)
        self.assertIn("Canvas-level Review", layout)
        self.assertIn("zoom-out", layout)
        self.assertIn("不得声明 Figma 修改完成", layout)

        self.assertIn(
            ".agents/skills/figma/references/07_页面布局与真实可用性审计.md",
            preservation,
        )
        self.assertIn("不得在 Coding references 下恢复第二套 Figma 设计规则", preservation)

    def test_review_and_aima_blueprints_consume_the_rules(self) -> None:
        review = self._read(".agents/skills/coding/references/11_两阶段复核与完成前验证.md")
        blueprint05 = self._read("docs/blueprint/05_日志安全部署与运维.md")
        blueprint06 = self._read("docs/blueprint/06_开发约束与分阶段实施.md")
        self.assertIn("非显然内部/private/helper", review)
        self.assertIn("最小充分可观测性", review)
        self.assertIn("功能开发时怎样选择日志观测点", blueprint05)
        self.assertIn("代码注释与关键日志也属于实现质量", blueprint06)


if __name__ == "__main__":
    unittest.main()
