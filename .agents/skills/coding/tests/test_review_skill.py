from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


class ReviewSkillTest(unittest.TestCase):
    def _read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_review_skill_is_thin_independent_reviewer(self) -> None:
        skill = self._read(".agents/skills/review/SKILL.md")

        self.assertIn("name: review", skill)
        self.assertIn("review-only", skill)
        self.assertIn("review-and-test", skill)
        self.assertIn("review-and-fix", skill)
        self.assertIn("测试专家", skill)
        self.assertIn("Findings", skill)
        self.assertIn(".agents/skills/coding/SKILL.md", skill)
        self.assertIn("唯一研发规范源", skill)
        self.assertIn("不复制", skill)

    def test_review_references_cover_execution_findings_and_test_expertise(self) -> None:
        workflow = self._read(".agents/skills/review/references/01_审查执行流程.md")
        findings = self._read(".agents/skills/review/references/02_Findings与严重度.md")
        testing = self._read(".agents/skills/review/references/03_测试专家审查方法.md")

        self.assertIn("Review Target", workflow)
        self.assertIn("独立重建", workflow)
        self.assertIn("BLOCKER", findings)
        self.assertIn("HIGH", findings)
        self.assertIn("触发条件", findings)
        self.assertIn("测试缺口", findings)
        self.assertIn("Browser Mock Acceptance", testing)
        self.assertIn("Backend / API / PostgreSQL Integration", testing)
        self.assertIn("Contract / Generated Client", testing)
        self.assertIn("Real Full-stack Golden Path", testing)
        self.assertIn("Real Provider Probe", testing)
        self.assertIn("测试绿色", testing)

    def test_coding_hard_routes_explicit_and_completion_reviews(self) -> None:
        coding = self._read(".agents/skills/coding/SKILL.md")
        routing = self._read(".agents/skills/coding/references/02_跨项目研发任务路由.md")
        agent = self._read(".agents/skills/coding/agents/openai.yaml")

        self.assertIn("#### Review Skill 强制路由（仓库存在时）", coding)
        self.assertIn(".agents/skills/review/SKILL.md", coding)
        self.assertIn("显式 Code Review / Audit", coding)
        self.assertIn("任何 Coding 实现任务", coding)
        self.assertIn("完成前 Review", coding)
        self.assertIn("Review Skill 存在但无法读取", coding)
        self.assertIn("不得宣称 Review 完成", coding)

        self.assertIn("Code Review / Audit", routing)
        self.assertIn(".agents/skills/review/SKILL.md", routing)
        self.assertIn("立即切入 Review", routing)

        self.assertIn(".agents/skills/review/SKILL.md", agent)
        self.assertIn("completion review", agent.casefold())
        self.assertIn("explicit code review", agent.casefold())

    def test_review_routes_fixes_back_to_coding_and_re_reviews(self) -> None:
        review = self._read(".agents/skills/review/SKILL.md")
        workflow = self._read(".agents/skills/review/references/01_审查执行流程.md")

        self.assertIn("review-and-fix", review)
        self.assertIn("返回 Coding", review)
        self.assertIn("重新读取 `.agents/skills/coding/SKILL.md`", review)
        self.assertIn("re-review", review)
        self.assertIn("未经授权", review)
        self.assertIn("返回 Coding", workflow)
        self.assertIn("re-review", workflow)

    def test_review_readme_explains_usage_without_becoming_second_rulebook(self) -> None:
        readme = self._read(".agents/skills/review/README.md")

        self.assertIn("# Review Skill", readme)
        self.assertIn("定位", readme)
        self.assertIn("review-only", readme)
        self.assertIn("review-and-test", readme)
        self.assertIn("review-and-fix", readme)
        self.assertIn("Coding", readme)
        self.assertIn("Docs", readme)
        self.assertIn("Browser Mock Acceptance", readme)
        self.assertIn("不复制", readme)
        self.assertIn("SKILL.md", readme)

    def test_existing_coding_and_docs_core_rules_remain_present(self) -> None:
        coding = self._read(".agents/skills/coding/SKILL.md")
        docs = self._read(".agents/skills/docs/SKILL.md")

        self.assertIn("内容守恒优先于篇幅精简", coding)
        self.assertIn("Red\n→ Verify Red", coding)
        self.assertIn("Docs Skill 按需路由", coding)
        self.assertIn("所有时间相关默认采用北京时间", coding)
        self.assertIn("Git 提交信息统一中文", coding)
        self.assertIn("不会制造第二套事实", docs)
        self.assertIn("code_issue_detected", docs)


if __name__ == "__main__":
    unittest.main()
