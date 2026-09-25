---
schema: coding-change/v1
id: CHG-20260925-205525-docs-governance-cleanup
title: 收敛 AIMA 文档 Owner 与重复事实源
level: L2
status: in_progress
owner: yuwen.ding
branch: docs/605-docs-governance-cleanup
created: 2026-09-25T20:55:25+08:00
updated: 2026-09-25
completion_gate: required
depends_on: []
affected_areas:
  - docs
  - governance
  - developer-experience
affected_paths:
  - docs/README.md
  - docs/AGENTS.md
  - docs/02_环境运行与部署.md
  - docs/03_API接口说明.md
  - docs/blueprint/README.md
  - docs/blueprint/06_开发约束与分阶段实施.md
  - docs/appendix/README.md
  - docs/appendix/03_TikHub多接口验证与备用策略.md
  - docs/appendix/04_TikHub接口选型与真实验证台账.md
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/appendix/13_AI大规模打标与成本优化方案.md
  - docs/guides/README.md
  - docs/guides/01_Figma与前端设计开发工作流.md
  - docs/guides/05_多人协作与Change自动归档.md
  - docs/operations/README.md
  - docs/roadmap/README.md
contracts: []
data_changes: []
---

# 背景

Issue #605 要求对 AIMA_UGC 当前文档体系做一次系统整改。当前目录分层原则基本正确，但部分大文档已经发生 Owner 漂移：通用 Agent_Skills 治理、AIMA 项目接线、精确机器事实、长期架构、操作说明、历史与候选方案在多个 Markdown 中重复表达，导致维护同步成本和读者判断成本上升。

本任务不移除 Agent_Skills。Agent_Skills 继续是通用 Analysis/Coding/Testing/Review/Docs/Figma/Git/Delivery 的 canonical Owner；AIMA 只维护项目 Overlay、仓库接线、项目事实与读者任务。

# 目标与成功标准

1. 明确唯一 Owner：同一事实只在一个长期文档 Owner 中完整解释，其他位置只做必要摘要与导航。
2. 收缩当前最重的重复文档，不删除仍有效知识；删除前先证明其事实已有机器 Owner、长期 Owner 或新的专项承载。
3. 将 `docs/blueprint/06_开发约束与分阶段实施.md` 收敛为 AIMA 项目工程基线和 Agent_Skills 治理接线，不再复制通用研发方法。
4. 将 `docs/02_环境运行与部署.md` 收敛为运行入口；Windows、构建源、本地 Release 和 Production 专项回到 Guide/Operations。
5. 将 `docs/03_API接口说明.md` 收敛为 API 使用语义与调用指南；精确 Route/字段继续由 FastAPI/Pydantic/OpenAPI/Generated Client 持有。
6. 收敛 Appendix 08、Appendix 13、Figma Guide、多人协作 Guide 的职责边界。
7. TikHub 验证方法与验证台账只有在能证明知识守恒时才合并；否则保留两个 Owner 但消除重复。
8. 更新所有受影响入口/README/链接；不把未批准候选方向提升为 Active Roadmap。
9. 不改变产品行为、Contract、Schema/Migration、依赖、配置、Provider 语义或部署行为。
10. 完成文档/链接/Change 检查、独立 Review、PR required CI，并按用户授权合并 main。

# 非目标

- 修改 Agent_Skills canonical 源仓库。
- 修改产品或运行实现。
- 为减少文件数删除尚无替代 Owner 的知识。
- 把 AI 或其他候选优化建议自动转成 Roadmap / Backlog。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Agent_Skills 保持 AIMA 的通用治理 canonical Owner，AIMA 只维护项目 Overlay/接线/事实 | #605 | not_satisfied | 待整改 |
| R2 | 文档总入口和 docs 本地规则明确唯一 Owner 与生命周期 | #605 | not_satisfied | 待整改 |
| R3 | Blueprint 06 不再复制第二套通用研发治理 | #605 | not_satisfied | 待整改 |
| R4 | 环境运行文档变为入口，不重复专项运维手册 | #605 | not_satisfied | 待整改 |
| R5 | API 文档不再镜像完整 OpenAPI surface | #605 | not_satisfied | 待整改 |
| R6 | Appendix 08 收敛为入口差异与调试实现 | #605 | not_satisfied | 待整改 |
| R7 | Appendix 13 区分当前事实、评估与未批准候选 | #605 | not_satisfied | 待整改 |
| R8 | Figma/协作 Guide 只保留 AIMA 项目接线与项目事实 | #605 | not_satisfied | 待整改 |
| R9 | TikHub 文档职责去重且知识守恒 | #605 | not_satisfied | 待整改 |
| R10 | 所有受影响导航/链接/Owner 同步且无产品/Contract/Schema/依赖变化 | #605 | not_satisfied | 待整改 |
| R11 | Review、PR CI、merge、main-fresh 与 Change Archive/Issue Closure 完成 | #605 | not_satisfied | 待交付 |

# Validation Matrix

| 层 | 要求 | 计划证据 |
| --- | --- | --- |
| 文档结构与链接 | required | 仓库现有 docs/links/path 检查 + 自检受影响路径 |
| Change 完成门禁 | required | `python scripts/quality/check_change_completion.py --root . --require-active-ready` 对提交态/CI |
| 产品/Contract/Schema | not_applicable | 本任务不修改实现、Contract、Migration、依赖；diff 复核证明 |
| 文档知识守恒 | required | 修改前 Owner 映射 + 修改后逐项反查，未承载知识不删除 |
| Review | required | 独立重建 #605 AC，审查最终 diff 与证据 |
| CI / Git Delivery | required | PR 当前 Head required checks、merge 后 main-fresh 与 Change Archive |

# 实施原则

- 不以“文件数最少”作为目标，以“读者任务清楚 + 单一解释 Owner + 可定位真实事实”作为目标。
- 能由机器事实直接证明的精确字段/Route/Schema/版本，不在 Markdown 再维护完整镜像。
- Blueprint 解释长期边界与为什么；Operations/Guides 解释怎么操作；Appendix 解释专题实现/限制/调试；Roadmap 只承载已批准未完成事项；History 留在 changes/archive。
- 未批准候选可以作为明确标记的评估材料保留，但不能写成当前能力或 Active Roadmap。
