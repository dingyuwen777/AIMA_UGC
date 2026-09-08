---
schema: coding-change/v1
id: CHG-20260909-collection-strategy-figma
title: 采集策略 Figma 与代码增量同步
level: L2
status: implementing
owner: codex
branch: feature/collection-strategy-figma-20260909
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - collection
affected_paths:
  - frontend/src/features/collection-strategy/
  - frontend/src/shared/
  - frontend/e2e/
  - frontend/tests/
  - frontend/README.md
  - docs/product/
contracts: []
data_changes: []
---

# 目标、范围和不变项

依据 Issue #393 和用户逐页完整交付授权，先核对采集策略正式 Figma，再在现有页面/子组件内增量实现，保持总体布局和业务能力，复用已有公共组件，合理可用性修正同步回设计。基线 main：3a2d578ea300a30520b473ae42de5b8939b2ae2e。

范围包括词包、全局相关性、采集计划、创建/编辑/详情、状态与响应式。保留 Route、Vue/Pinia、生成 Client、现有 Contract、Scheduler 和历史配置语义。无依赖升级、Schema/Migration、生产部署或真实付费 Provider 调用。用户原有 docs/guides/01_Figma与前端设计开发工作流.md 修改不属于本次提交。管理员配置是下一独立页面任务，本 Change 不混入。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Figma 完整状态与真实能力核对 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC1 | not_satisfied | 已定位 Page 4627:13214 和正式主页面4627:13216 |
| R2 | 代码增量对齐并复用公共组件 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC2 | not_satisfied | 已读取公共标题 Design Context 和现有 Feature Owner |
| R3 | 词包与全局相关性完整操作保留 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC3 | not_satisfied | 当前 API/Store/页面事实核对中 |
| R4 | 计划完整操作、车型、Capability和历史配置保留 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC4 | not_satisfied | 当前 PlanCreateDrawer 已复用车型和搜索参数组件 |
| R5 | 响应式、长数据、异步、错误和产品文案 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC5 | not_satisfied | 目标基线和实际截图核验中 |
| R6 | 本地分层验收、设计对照和两阶段复核 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC6 | not_satisfied | 依下方矩阵取得新鲜证据 |
| R7 | 当前提交正式 CI | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC6 | explicitly_deferred | 仅按 AGENTS 提交→push→CI 的顺序延至实现提交后，合并前必须通过，不豁免 |
| R8 | 合并 main 后验证、归档和清理 | https://github.com/dingyuwen777/AIMA_UGC/issues/393 / AC7 | explicitly_deferred | 仅按用户及 AGENTS 授权流程在CI通过后执行；最终交付前必须完成，不延期到其他迭代 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 策略Store、资格和表单状态 |
| 接口 / Contract | required | 生成消费者无漂移，合法创建/更新请求保留 |
| Backend/API/PostgreSQL | required | 既有词包/全局相关性/周期计划服务器边界 |
| Browser Mock Acceptance | required | 词包、相关性、计划流程，响应式、异步和失败 |
| Real Full-stack Golden Path | required | 复用现有真实策略/管理接线用例，隔离PostgreSQL，无付费调用 |
| External Provider Probe | not_applicable | 不修改Adapter或外部协议，不需要真实计费请求 |
| Build / Runtime | required | lint、TS7/Vue类型检查、正式build与实际截图 |
| Docs / Governance / Other | required | 定向文档、Figma状态、需求/完成审查、Ready及CI |

# 实施计划

1. 正式Figma/公共组件与现有Contract→确定差异并补齐必要画板→结构、状态、原型及截图核对。
2. Page/私有组件/Store→增量修复和复用→先复现缺陷，再执行目标回归。
3. 真实跨层接线和正式构建→确认保留业务能力→使用现有隔离测试，不创建平行实现。
4. 产品文档/审查/CI→完成当前页面交付→受SHA保护合并、main复验、自动归档、Issue同步和分支清理。

# 兼容、部署与回滚

仅修改既有前端消费者、状态和布局；不改变公共后端协议、数据库和锁定依赖。无需数据迁移；回滚本次前端提交即可恢复旧界面。开发环境和Figma示例不代表生产已部署。

# Completion Audit

- [ ] upstream_re_read：Ready前重新读取Issue、用户决定和正式Figma。
- [ ] change_coverage：逐项从上游重建完成定义，不以本Change自证。
- [ ] reverse_audit：后端能力→前端入口、前端动作→真实支持、编辑→历史配置与结果完整。
- [ ] unresolved_cleared：无未满足实现要求，时序门禁有明确依据且最终实际执行。

# 当前状态

首个提交只建立追溯和早期PR，尚未就绪。已读取当前规则、Blueprint、Figma指南、关键实现和现有测试；主页面大型Design Context调用传输超时，改用公共标题小节点成功取得正式上下文，继续按实际组件边界核对。
