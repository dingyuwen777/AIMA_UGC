from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


class DocsSkillTest(unittest.TestCase):
    def _read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_docs_skill_exposes_required_principles(self) -> None:
        skill = self._read(".agents/skills/docs/SKILL.md")
        self.assertIn("name: docs", skill)
        self.assertIn("为什么存在、解决什么问题、数据怎么流、代码在哪实现", skill)
        self.assertIn("术语必须用白话解释", skill)
        self.assertIn("最小例子", skill)
        self.assertIn("不会制造第二套事实", skill)
        self.assertIn("not_applicable", skill)
        self.assertIn("targeted", skill)
        self.assertIn("full", skill)

    def test_docs_references_cover_fact_writing_review_and_coding_collaboration(self) -> None:
        facts = self._read(".agents/skills/docs/references/01_事实源与同步判断.md")
        writing = self._read(".agents/skills/docs/references/02_第一性原理技术写作.md")
        review = self._read(".agents/skills/docs/references/03_审查编写与修复流程.md")
        collaboration = self._read(".agents/skills/docs/references/04_与Coding协作.md")

        self.assertIn("机器事实", facts)
        self.assertIn("不能机械认为代码永远正确", facts)
        self.assertIn("先讲问题，再讲方案", writing)
        self.assertIn("术语后置", writing)
        self.assertIn("Review Only", review)
        self.assertIn("Write / Update", review)
        self.assertIn("targeted", review)
        self.assertIn("Docs Impact", collaboration)
        self.assertIn("返回 Coding", collaboration)

    def test_coding_routes_to_docs_without_replacing_existing_skill_rules(self) -> None:
        coding = self._read(".agents/skills/coding/SKILL.md")
        agent = self._read(".agents/skills/coding/agents/openai.yaml")

        # 这些断言保护当前 Coding 的既有高价值规则；本次不重写 Coding/SKILL.md 正文。
        self.assertIn("内容守恒优先于篇幅精简", coding)
        self.assertIn("### 4.12 同步当前事实和文档", coding)
        self.assertIn("文档与代码/Contract 尚未同步时，不得标记 Ready、完成、可合并或可发布", coding)
        self.assertIn("所有时间相关默认采用北京时间", coding)
        self.assertIn("Git 提交信息统一中文", coding)
        self.assertIn("Red\n→ Verify Red：实际确认因正确目标行为失败", coding)
        self.assertIn("→ Green：最少代码通过", coding)

        # Docs 路由只追加到很小的 Agent 默认提示，完整文档规则仍由独立 Docs Skill 维护。
        self.assertIn("Docs Impact", agent)
        self.assertIn(".agents/skills/docs/SKILL.md", agent)
        self.assertIn("targeted", agent)
        self.assertIn("not_applicable", agent)
        self.assertIn("without copying or summarizing Docs rules into Coding", agent)

    def test_existing_blueprint_already_matches_lightweight_docs_governance(self) -> None:
        blueprint = self._read("docs/blueprint/06_开发约束与分阶段实施.md")
        self.assertIn("# 16. 文档是交付门禁", blueprint)
        self.assertIn("但不是“每次改代码都全部重写文档”", blueprint)
        self.assertIn("# 17. 正式文档写作标准", blueprint)
        self.assertIn("为什么需要？", blueprint)
        self.assertIn("精确 Schema/Contract 不复制成第二套文档", blueprint)


if __name__ == "__main__":
    unittest.main()
