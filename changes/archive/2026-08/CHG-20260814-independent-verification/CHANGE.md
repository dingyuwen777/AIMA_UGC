---
schema: rvc-change/v1
id: CHG-20260814-independent-verification
title: 固化独立可验证能力与测试说明规范
level: L2
status: done
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

# 成功标准

- [x] Skill 主入口增加通用独立验证原则，不包含 AIMA/TikHub/PostgreSQL 等项目私有实现规则。
- [x] Skill 开发工作流说明测试入口、Fixture/Fake/Probe、隔离依赖、运行方式和成功判据的设计方法。
- [x] 明确测试粒度由行为边界、风险、依赖和失败模式决定，不机械要求“一模块一个测试文件”或“一功能一个测试文档”。
- [x] Blueprint README 固化项目级独立验证规则并导航到 `docs/测试与调试说明.md`。
- [x] 新增 AIMA 人类可读测试与调试说明，覆盖 Provider、Mapper、Raw/Artifact、Ingestion、Repository/Query、Job、API、Frontend、Renderer。
- [x] Blueprint 06 既有 TDD、测试分层、模块 README、生产逻辑复用和 CI 门禁保持不变，不复制第二套详细测试事实。
- [x] 不改变业务 Contract、Schema、Migration、依赖或阶段顺序。
- [x] PR #14 CI #200 成功并 squash 合并到 main。
- [x] 合并后 main `10080703f61f18df62502eb6390f5a2b31d30f7e` 的 CI #201 成功。

# 关键决策

- 通用 Skill 只维护可迁移到任意项目的独立验证原则和方法。
- AIMA 项目具体测试方式由 `docs/测试与调试说明.md` 解释，Blueprint README 维护硬规则和导航。
- 测试代码、Contract、Fixture、Migration、本轮执行结果和 CI 是验证事实；Markdown 只负责导航和解释。
- 不以文件数量代表测试粒度，不为每个小函数创建测试文档。

# 交付证据

- PR：#14 `固化独立可验证能力与测试说明规范`
- PR head：`0be6d878bf88ba5cf38b49fee3188011ae00c5b4`
- PR CI：run #200 / `31759040809`，success；Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全部成功。
- main 合并提交：`10080703f61f18df62502eb6390f5a2b31d30f7e`
- main CI：run #201 / `31759123735`，success。

# 兼容、依赖、Migration、部署和回滚

- 公共业务 Contract：无变化。
- Schema/Migration：无变化。
- 依赖/锁文件：无变化。
- 部署：无变化。
- 回滚：如需撤销，仅回滚本 Change 的 Skill/文档提交，不涉及数据迁移。
