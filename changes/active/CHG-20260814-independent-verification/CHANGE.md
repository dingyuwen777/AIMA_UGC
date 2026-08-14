---
schema: rvc-change/v1
id: CHG-20260814-independent-verification
title: 固化独立可验证能力与测试说明规范
level: L2
status: in_progress
owner: dingyuwen777
branch: docs/independent-verification
created: 2026-08-14
updated: 2026-08-14
depends_on: []
affected_areas: [development-workflow, testing, documentation, blueprint]
affected_paths: [.agents/skills/reliable-vibe-coding/SKILL.md, .agents/skills/reliable-vibe-coding/references/development-workflows.md, docs/blueprint/README.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/测试与调试说明.md]
contracts: []
data_changes: []
---

# 目标

把独立可验证能力的测试闭环固化为通用 Skill 规则，并在 AIMA_UGC Blueprint 中明确项目级落地方式。

# 可观察成功标准

- [ ] Skill 主入口增加通用独立验证原则。
- [ ] Skill 开发工作流说明测试入口、Fixture/Fake、依赖和验证说明的设计方法。
- [ ] Blueprint 06 明确 AIMA 的独立验证闭环与模块 README 要求。
- [ ] 新增 `docs/测试与调试说明.md` 作为人类可读测试入口。
- [ ] Blueprint README 增加导航和维护规则。
- [ ] 不改变业务 Contract、Schema、Migration、依赖或阶段顺序。
- [ ] PR/CI 通过并合并到 main。

# 范围

仅修改 Skill、测试/调试文档和 Blueprint 规则。

# 非目标

不新增尚未实现功能的测试代码，不修改业务代码、Contract、Schema、Migration 或依赖。

# 必须保持不变

现有测试分层、项目技术路线、阶段顺序，以及调试/Probe/测试复用生产实现的原则。

# 任务

1. 更新 Skill 主入口与 development workflow。
2. 更新 Blueprint 06 与 Blueprint README。
3. 新增人类可读测试与调试说明。
4. Review、CI、合并并记录证据。

# 验证计划

检查文档一致性、Skill 通用性、PR diff 和最终 CI。

# 文档影响

见 affected_paths。

# Git / PR

- 基线：`main@817726ac9669ba7c23e91550b6e336cd9ad3d5ef`
- 分支：`docs/independent-verification`
- PR：待创建
- CI：待执行
- 合并：待完成
