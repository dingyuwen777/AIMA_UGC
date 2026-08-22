---
schema: rvc-change/v1
id: CHG-20260822-current-implementation-audit
title: 当前代码实现与文档一致性审计
level: L2
status: in_progress
owner: dingyuwen777
branch: docs/current-implementation-audit-20260822
created: 2026-08-22
updated: 2026-08-22
depends_on: []
affected_areas:
  - documentation
  - architecture_navigation
  - roadmap
  - module_readme
  - change_history
affected_paths:
  - README.md
  - AGENTS.md
  - docs
  - frontend/README.md
  - backend/src/aima_ugc
  - changes/active
  - changes/archive
contracts: []
data_changes: []
---

# 目标

基于当前 `main` 的代码、Contract、Migration、测试、依赖和已合并 PR 事实，系统检查仓库正式文档是否准确描述当前实现；修正文档中已经过期、互相冲突、指向不存在文件、遗漏关键业务/技术语义或把未来设计误写成当前事实的内容，并重新评估生产上线后续阶段是否仍然合理。

本 Change 只同步事实与阶段导航，不改变运行时代码、公共 Contract、Schema、Migration、依赖或业务行为。

# 可观察成功标准

- [ ] 当前模块、进程、Job、前端路由、数据入口、Analysis、Reporting、日志、部署边界等关键事实都由机器事实重新核对。
- [ ] Blueprint、Roadmap、Appendix、Guide、模块 README、根 README、API/测试/运行文档之间不存在已发现的实现冲突。
- [ ] 已合并但仍停留在 Active/`ready_for_review` 的历史 Change 被按真实 Git 状态收口，旧 Blueprint 路径引用被修正。
- [ ] 关键业务/逻辑方案如果代码已实现但正式文档未体现，在正确文档层补齐；不复制完整机器 Schema/Prompt。
- [ ] 已批准但未实现的生产目标仍只保留在 Roadmap/正式设计，不误写成当前机器事实。
- [ ] 后续阶段按当前代码重新评估，明确合理项、需要重排项、需要用户上游决策项和下一最小正式开发单元。
- [ ] 文档链接/结构检查、受影响测试与 GitHub CI 使用本轮新鲜 head 验证通过。

# 范围

- `AGENTS.md`、根 README、`docs/**`、前后端/模块 README 与历史 Change 中的当前事实同步。
- 读取与文档主张直接相关的实现、Contract、Migration、测试、锁文件和已合并 PR 作为证据。
- 修正旧文档路径、旧阶段状态、错误的“当前/未实现/已完成”描述。
- 评估 Roadmap 的阶段划分和顺序，但不实现未来阶段。

# 非目标

- 不新增业务功能。
- 不修改 API、Contract、Schema、Migration、依赖、Prompt 业务分类或运行时代码。
- 不因为文档审计顺手重构生产代码。
- 不恢复已经被正式后续决策替代的历史方案。

# 必须保持不变

- 当前代码和机器事实不因文档便利被改写。
- Blueprint 只维护长期架构和跨模块边界；Appendix/README 承载实现细节；Roadmap 承载未完成阶段。
- 完整 Taxonomy、数据库字段和 OpenAPI 继续以机器事实为唯一精确来源。
- CI、Branch Protection、PR 与质量门禁不绕过。

# 已确认关键决策

- 本轮冲突判断不是机械“代码优先”；先区分代码缺陷、文档过期、未来设计和已批准但未实现目标。
- 文档更新遵循“改变职责，不减少知识”；已有高价值实现/调试细节不能因结构整理被压缩丢失。
- 用户要求对后续设计阶段做合理性评估，本轮只更新 Roadmap/文档，不提前实现生产能力。

# 任务

- [x] 读取当前 `main` 的 `AGENTS.md`、Reliable Vibe Coding Skill、Blueprint 导航/门禁、Roadmap 和代码导航。
- [x] 检查 Active Change 与已合并 PR 状态，确认存在历史状态冲突。
- [ ] 复核当前机器事实与主要正式文档。
- [ ] 修正发现的文档冲突与遗漏。
- [ ] 更新 Roadmap 阶段评估与下一步建议。
- [ ] 运行/读取本轮新鲜验证与 CI。
- [ ] 通过 PR 交付并在满足归档门禁后归档本 Change。

# 验证计划

至少检查：

```text
scripts/quality/check_docs.py
相关文档事实测试
CI / architecture / table ownership / secret scan（由仓库工作流实际触发为准）
```

如果本轮只修改 Markdown/Change 而没有运行时代码变化，不制造无关业务测试；但所有受影响的文档路径/事实源测试必须保持通过。

# 文档影响

本 Change 的目标就是同步正式文档；最终记录实际修改文件、冲突和仍未实现阶段。

# Git / PR / 发布

- 分支：`docs/current-implementation-audit-20260822`
- PR：待创建
- Merge：仅在本轮 head 的质量门禁通过后执行
- 发布/生产部署：不属于本 Change
