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

    def test_figma_canvas_readability_guidance_is_routed_and_actionable(self) -> None:
        routing = self._read(".agents/skills/coding/references/02_跨项目研发任务路由.md")
        figma = self._read(".agents/skills/coding/references/13_Figma设计画布与可读性规则.md")
        guide = self._read("docs/guides/01_Figma与前端设计开发工作流.md")

        self.assertIn("13_Figma设计画布与可读性规则.md", routing)
        self.assertIn("Figma 创建 / 修改 / 整理", routing)
        self.assertIn("项目已经规定间距时，必须使用项目规则", figma)
        self.assertIn("24–32px", figma)
        self.assertIn("64–80px", figma)
        self.assertIn("Canvas-level Review", figma)
        self.assertIn("zoom-out", figma)
        self.assertIn("不得声明 Figma 修改完成", figma)
        self.assertIn("Spacing", guide)
        self.assertIn("视觉核对", guide)

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
