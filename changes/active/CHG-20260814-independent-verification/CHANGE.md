---
schema: rvc-change/v1
id: CHG-20260814-independent-verification
title: 固化独立可验证能力与测试说明规范
level: L2
status: ready_for_review
owner: dingyuwen777
branch: docs/independent-verification
created: 2026-08-14
updated: 2026-08-14
depends_on: []
affected_areas: [development-workflow, testing, documentation, blueprint]
affected_paths: [.agents/skills/reliable-vibe-coding/SKILL.md, .agents/skills/reliable-vibe-coding/references/development-workflows.md, docs/blueprint/README.md, docs/测试与调试说明.md]
contracts: []
data_changes: []
---

# 目标

把独立可验证能力的测试闭环固化为通用 Skill 规则，并在 AIMA_UGC Blueprint 中明确项目级落地方式。

# 可观察成功标准

- [x] Skill 主入口增加通用独立验证原则，不包含 AIMA/TikHub/PostgreSQL 等项目私有实现规则。
- [x] Skill 开发工作流说明测试入口、Fixture/Fake/Probe、隔离依赖、运行方式和成功判据的设计方法。
- [x] 明确测试粒度由行为边界、风险、依赖和失败模式决定，不机械要求“一模块一个测试文件”或“一功能一个测试文档”。
- [x] Blueprint README 把独立验证闭环固化为项目级长期规则，并把 `docs/测试与调试说明.md` 设为人类可读统一入口。
- [x] 新增 `docs/测试与调试说明.md`，具体说明 AIMA 的 Provider、Mapper、Raw/Artifact、Ingestion、Repository/Query、Job、API、Frontend、Renderer 等边界如何独立验证。
- [x] 保留 Blueprint 06 现有测试分层、模块 README、生产逻辑复用和 CI 门禁作为既有事实，不在 06 与测试指南之间复制第二套详细测试规则。
- [x] 不改变业务 Contract、Schema、Migration、依赖或 Stage 3/4 及后续阶段顺序。
- [ ] PR/CI 通过并合并到 main。

# 范围

- Reliable Vibe Coding Skill 的通用独立验证原则和开发工作流；
- AIMA Blueprint 的项目级独立验证硬规则与测试说明导航；
- AIMA 人类可读测试与调试说明入口。

# 非目标

- 不新增尚未实现功能的测试代码；
- 不修改业务代码、Contract、Schema、Migration、依赖或 CI 能力；
- 不重写 Blueprint 06 已经存在的测试分层和阶段计划；
- 不要求每个函数、每个文件或每个模块机械创建独立测试文件/文档。

# 必须保持不变

现有测试分层、项目技术路线、阶段顺序，以及调试/Probe/测试复用生产实现的原则。

# 关键决策

- 通用 Skill 只描述可迁移到任意项目的“独立可验证能力”原则和方法，不写 AIMA 私有名词。
- AIMA 项目具体测试方式放在 `docs/测试与调试说明.md`；Blueprint README 只维护硬规则和导航。
- Blueprint 06 已经负责 TDD、测试分层、模块 README 和 CI，本次不重复一份详细测试说明，避免长期出现两个测试事实源。
- 测试代码、Contract、Fixture、Migration、本轮执行结果和 CI 是验证事实；Markdown 负责解释和导航。

# 已完成任务

1. 更新 Skill 主入口，加入独立可验证能力通用不变量和规划/实施要求。
2. 更新 `development-workflows.md`，增加独立验证单元判定、闭环要素、Fixture/Fake/Probe 规则。
3. 新增 `docs/测试与调试说明.md`。
4. 更新 Blueprint README，增加统一测试说明入口和项目级维护规则。

# 验证计划

- PR diff 只包含本 Change 预期文件；
- 检查 Skill 新规则无 AIMA 项目私有实现语义；
- 检查测试说明与 Blueprint 06 的测试分层一致且不复制第二套机器断言；
- 由仓库 CI 执行文档、Skill、质量和既有回归门禁；
- 合并后再次检查 main CI。

# 文档影响

见 `affected_paths`。

# Git / PR

- 基线：`main@817726ac9669ba7c23e91550b6e336cd9ad3d5ef`
- 分支：`docs/independent-verification`
- 当前提交：`6a8c5425cfdd2977277f8a2e53c0046a41becd72` 之后含本 Change 更新
- PR：待创建
- CI：待执行/确认
- 合并：待完成
