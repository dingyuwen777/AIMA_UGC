from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


class NetworkAndWorkflowGovernanceTest(unittest.TestCase):
    def _read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_coding_skill_hard_routes_network_sources_and_workflow_audit(self) -> None:
        skill = self._read(".agents/skills/coding/SKILL.md")

        self.assertIn("网络下载源与镜像选择必须感知执行环境", skill)
        self.assertIn("中国大陆", skill)
        self.assertIn("联网核验", skill)
        self.assertIn("03_编程语言与工具链适配规则.md", skill)

        self.assertIn("永久 CI/Workflow 优化必须证据守恒", skill)
        self.assertIn("Workflow Responsibility Audit", skill)
        self.assertIn("Evidence Preservation Mapping", skill)
        self.assertIn("07_通用验证与证据策略.md", skill)
        self.assertIn("08_分层测试与验收策略.md", skill)

    def test_toolchain_reference_keeps_network_source_selection_safe_and_current(self) -> None:
        guidance = self._read(".agents/skills/coding/references/03_编程语言与工具链适配规则.md")

        self.assertIn("## 网络下载源与镜像选择", guidance)
        self.assertIn("目标执行环境", guidance)
        self.assertIn("中国大陆", guidance)
        self.assertIn("联网核验", guidance)
        self.assertIn("官方帮助", guidance)
        self.assertIn("同步状态", guidance)
        self.assertIn("阿里云", guidance)
        self.assertIn("清华 TUNA", guidance)
        self.assertIn("中科大 USTC", guidance)
        self.assertIn("npmmirror", guidance)
        self.assertIn("不是永久白名单", guidance)
        self.assertIn("canonical", guidance)
        self.assertIn("checksum", guidance)
        self.assertIn("hash", guidance)
        self.assertIn("digest", guidance)
        self.assertIn("fallback", guidance)
        self.assertIn("锁文件", guidance)
        self.assertIn("安全更新", guidance)

    def test_validation_reference_requires_evidence_preserving_workflow_audit(self) -> None:
        validation = self._read(".agents/skills/coding/references/07_通用验证与证据策略.md")

        self.assertIn("## CI / Workflow Responsibility Audit", validation)
        self.assertIn("Evidence Preservation Mapping", validation)
        self.assertIn("原证明责任", validation)
        self.assertIn("新位置", validation)
        self.assertIn("path", validation)
        self.assertIn("fast path", validation)
        self.assertIn("缓存", validation)
        self.assertIn("artifact", validation)
        self.assertIn("check name", validation)
        self.assertIn("Branch Protection", validation)
        self.assertIn("较弱", validation)
        self.assertIn("独立风险", validation)

    def test_web_testing_reference_reduces_cost_without_collapsing_evidence_layers(self) -> None:
        layered = self._read(".agents/skills/coding/references/08_分层测试与验收策略.md")

        self.assertIn("## 10. CI / Workflow 成本控制", layered)
        self.assertIn("Browser Mock", layered)
        self.assertIn("Backend / API / PostgreSQL Integration", layered)
        self.assertIn("Real Full-stack Golden Path", layered)
        self.assertIn("Real Provider Probe", layered)
        self.assertIn("状态空间", layered)
        self.assertIn("无关触发", layered)
        self.assertIn("重复", layered)
        self.assertIn("证据", layered)

    def test_preservation_map_and_readme_keep_new_rules_discoverable(self) -> None:
        preservation = self._read(".agents/skills/coding/references/12_规则保留映射.md")
        readme = self._read(".agents/skills/coding/README.md")

        self.assertIn("网络下载源与镜像选择", preservation)
        self.assertIn("Workflow Responsibility Audit", preservation)
        self.assertIn("03_编程语言与工具链适配规则.md", preservation)
        self.assertIn("07_通用验证与证据策略.md", preservation)
        self.assertIn("08_分层测试与验收策略.md", preservation)

        self.assertIn("中国大陆网络", readme)
        self.assertIn("实时核验", readme)
        self.assertIn("Workflow Responsibility Audit", readme)
        self.assertIn("证据守恒", readme)

    def test_existing_review_docs_and_core_coding_rules_remain_present(self) -> None:
        skill = self._read(".agents/skills/coding/SKILL.md")

        self.assertIn("内容守恒优先于篇幅精简", skill)
        self.assertIn("Red\n→ Verify Red", skill)
        self.assertIn("#### Review Skill 强制路由（仓库存在时）", skill)
        self.assertIn(".agents/skills/review/SKILL.md", skill)
        self.assertIn("Docs Skill 按需路由", skill)
        self.assertIn(".agents/skills/docs/SKILL.md", skill)
        self.assertIn("Git 提交信息统一中文", skill)
        self.assertIn("所有时间相关默认采用北京时间", skill)
        self.assertIn("强制其他序列化形式", skill)


if __name__ == "__main__":
    unittest.main()
