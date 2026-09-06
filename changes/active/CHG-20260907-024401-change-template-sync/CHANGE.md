---
schema: coding-change/v1
id: CHG-20260907-024401-change-template-sync
title: 同步固定第一性原理 Change 模板
level: L2
status: proposed
owner: dingyuwen777
branch: chore/change-template-sync
created: 2026-09-07
updated: 2026-09-07
completion_gate: required
depends_on: []
affected_areas:
  - governance
  - documentation
  - managed-project-payload
affected_paths:
  - .agents/skills/coding/assets/CHANGE.template.md
contracts:
  - coding-change/v1
  - AIMA Change carrier compatibility
data_changes: []
---

# 背景与目标

AIMA_UGC 的正式 Change carrier 是顶层 `changes/`；通用 Change 模板由 Agent_Skills canonical Source 拥有，项目中的 `.agents/skills/coding/assets/CHANGE.template.md` 是安装/升级维护的受管投影，不是第二个 canonical Owner。当前任务要求两个仓库同步固定同一套 Change 文档骨架，因此 AIMA 只同步该受管模板，不复制一份项目自有通用治理模板，也不改变项目的 Change carrier、validator、CI 或归档机制。

目标是让 AIMA 后续新建 Change 直接获得与 Agent_Skills 当前 canonical 一致的第一性原理中文模板，同时保持 `coding-change/v1`、`changes/active` / `changes/archive`、`scripts/quality/check_change_completion.py` 和 repository-native Change Archive 现有行为不变。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | AIMA_UGC 后续 Change 使用固定的第一性原理模板，并包含背景、现状事实、问题、方案、证据等必要结构 | `user:当前会话#AC1` | not_satisfied | 待同步受管模板并验证 |
| R2 | 除 AIMA/Agent_Skills 仓库事实、专有名词和机器 Contract 外，人类可读正文统一使用中文 | `user:当前会话#AC2` | not_satisfied | 待完成模板文本审查 |
| R3 | 不新增 AIMA 自有的第二套通用模板 Owner，只同步 Agent_Skills canonical 模板的受管投影 | `user:当前会话#AC3` | not_satisfied | 待完成跨仓内容一致性验证 |
| R4 | 不改变 AIMA 现有 Change validator、CI、归档、测试或业务运行流程 | `user:当前会话#AC4` | not_satisfied | 待完成 Change Ready、required CI 与差异审查 |
| R5 | 变更按 AIMA 当前仓库门禁合并到 `main` | `user:当前会话#AC5` | not_satisfied | 待完成 PR、CI、guarded merge 与 main-fresh 验证 |

# Validation Matrix

| 验证层 | 是否要求 | Scope / Evidence |
| --- | --- | --- |
| 行为 / 单元 / 组件 | not_applicable | 不修改 AIMA 业务代码、组件或业务测试；模板行为由 Agent_Skills canonical 回归负责 |
| 接口 / 契约 | required | `coding-change/v1`、AIMA Change carrier、Ready validator 输入结构保持兼容 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不涉及 PostgreSQL、文件业务语义、队列或外部运行依赖 |
| 用户 / 工作流验收 | required | AIMA `scripts/quality/check_change_completion.py` 能继续消费当前 active Change 与同步模板语义 |
| 跨组件关键路径 | required | Agent_Skills canonical template → AIMA managed projection 内容一致 |
| 外部依赖 / 供应方探测 | not_applicable | 不涉及 TikHub 或其他外部 Provider |
| 构建 / 打包 / 运行 | not_applicable | 不改变 Docker、构建、Release、运行配置或依赖 |
| 文档 / 治理 / 其他 | required | 受管投影、Change carrier、项目文档 Owner 和 CI/归档边界保持一致 |

# Completion Audit

- [ ] upstream_re_read: 合并前重新读取用户要求、AIMA 项目 Overlay、Agent_Skills canonical template 与当前 PR head。
- [ ] change_coverage: 确认只同步受管模板和当前施工记录，不建立第二套通用治理 Owner。
- [ ] reverse_audit: 反查模板投影、AIMA Change validator、CI/Archive 接线与跨仓内容一致性；未受影响业务层有明确依据。
- [ ] unresolved_cleared: 所有 `not_satisfied` 清零，并取得当前 head required CI 与 main-fresh 证据。

# 回滚

本变更只同步受管 Markdown 模板。若出现兼容问题，回滚对应 PR 即可；不涉及依赖、数据库、Migration、业务数据、部署或生产运行状态。