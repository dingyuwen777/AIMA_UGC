---
schema: coding-change/v1
id: CHG-20260909-admin-configuration-figma
title: 管理员配置 Figma 与代码增量同步
level: L2
status: in_progress
owner: codex
branch: feature/admin-configuration-figma-20260909
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - administration
affected_paths:
  - frontend/src/features/admin-configuration/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - frontend/tests/
  - frontend/README.md
  - docs/product/
contracts: []
data_changes: []
---

# 背景、目标与不变项

依据Issue #395与用户逐页完整交付授权。采集策略PR #394已合并并归档，本页从main 28d3c1c601c94e9e9d38522c828b3cbd0e37ddb5开始。正式Figma Page3957:2有六个标签页、宽窄规格和行为说明；当前Vue页面已有所有管理能力，AI模型/TikHub测试连接也已接入后端，但Figma主画板缺入口。目标是增量对齐布局、状态和交互，保留总体页面及公共复用。

范围为六个标签页、Provider测试连接与草稿状态、表格滚动及相应Figma状态。优先复用现有AdminConfigurationPage、ProviderConfigurationPanel、AnalysisLabelsEditor、VehicleMultiSelect、Aima公共UI与生成Client。不得新增平行API/Store或业务规则，不新增认证、全库审计搜索、付费Probe、依赖、Schema/Migration或生产部署。原有docs/guides/01_Figma与前端设计开发工作流.md修改不属于本次提交。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 六个标签页对照与公共组件复用 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC1 | not_satisfied | 已定位正式画板及Feature Owner，待实际几何与交互核对 |
| R2 | 已保存配置测试连接及完整结果状态 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC2 | not_satisfied | 已确认既有前后端入口，待草稿/旧结果回归与Figma补齐 |
| R3 | Provider生命周期、Secret与草稿保护 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC3 | not_satisfied | 现有保存、归档和条件删除继续复用，待验收 |
| R4 | 车型、关联、操作记录和长表格可达 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC4 | not_satisfied | 当前车型表缺专用滚动区，操作记录滚动包含整张卡片，待复现 |
| R5 | 分析规则完整能力与历史语义 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC5 | not_satisfied | 结构化编辑及草稿/发布/恢复现有入口已读取，待验收 |
| R6 | 状态、宽窄布局、设计同步及真实能力边界 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC6 | not_satisfied | Figma高级参数和审计搜索与当前实现存在差异，按正式产品事实修正 |
| R7 | 分层验收、独立Review、完成审查 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC7 | not_satisfied | 按Validation Matrix取得实际证据 |
| R8 | 当前提交正式CI | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC7 | explicitly_deferred | 仅按AGENTS提交→push→CI顺序后置，合并前必须通过，不豁免 |
| R9 | main合并后验证、归档和清理 | https://github.com/dingyuwen777/AIMA_UGC/issues/395 / AC8 | explicitly_deferred | 用户已授权完整交付；合并后执行，最终交付前必须完成，不延期至其他迭代 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit / Component | required | 管理页面、Provider参数与结构化标签既有单元回归 |
| Browser Mock Acceptance | required | 六个标签、长数据、宽窄、旧响应、测试连接、草稿及失败恢复 |
| Backend/API/PostgreSQL Integration | required | 复用既有Provider/车型/规则生命周期测试，不以Mock代替服务器边界 |
| Real Full-stack Golden Path | required | 复用真实管理员产品能力路径；连接测试采用本地Fake或服务器受控失败验证，不调用真实计费服务 |
| External Provider Probe | not_applicable | 不修改Provider协议，无需真实账户或计费调用 |
| Build / Runtime | required | lint、类型检查、正式构建、实际浏览器截图 |
| Docs / Governance / Design | required | 产品文档定向同步、Figma结构/截图/原型、两阶段独立Review、Ready与CI |

# 实施计划

1. 正式Figma、当前页面与公共样式 → 逐标签核对真实差异 → Browser实际几何、状态和API请求验收，先复现缺陷。
2. AdminConfigurationPage、ProviderConfigurationPanel及必要私有组件 → 最小布局/状态修正 → 测试连接和保存草稿/并发返回回归，保持Contract与后端业务限制。
3. 对应正式Figma Owner与状态画板 → 同步已有能力及合理体验修正 → 小范围结构读取、截图和原型验证，不用截图冒充可编辑结构。
4. 测试、产品文档、Change与PR → 分层验收和独立审查 → 当前head CI、受SHA保护合并、main复验、自动归档、Issue及分支清理。

# 兼容、部署与回滚

保持Route、生成Client、Provider连接测试Contract、数据库、身份/授权、Secret处理、Scheme发布和历史冻结语义。前端静态资源按现有方式发布；回滚本次前端代码与静态资源即可。无数据迁移、配置或依赖变化。Figma示例不是生产事实，开发测试不代表生产已部署。

# Completion Audit

- [ ] upstream_re_read：Ready前重新读取用户决定、Issue及正式Figma，独立重建完成定义。
- [ ] change_coverage：从上游逐项核对Change、实现、测试和文档。
- [ ] reverse_audit：后端管理能力→前端入口，前端动作→真实接口，当前保存→历史任务不变。
- [ ] unresolved_cleared：实现阻断清零，CI/合并时序门禁最终实际执行。

# 当前状态

已建立本地任务分支和上游Issue，尚未修改生产代码；正在准备失败复现、设计对照及早期PR。
