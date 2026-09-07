---
schema: coding-change/v1
id: CHG-20260907-product-resource-lifecycle
title: 产品资源生命周期与业务可读性整改
level: L3
status: in_progress
owner: chatgpt
branch: feature/product-resource-lifecycle
created: 2026-09-07
updated: 2026-09-07
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - collection
  - system
  - administration
  - analysis
  - reporting
  - api
  - contracts
  - frontend
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/modules/collection/
  - backend/src/aima_ugc/modules/system/
  - backend/src/aima_ugc/modules/administration/
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/
  - migrations/versions/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/import-batches/
  - frontend/src/features/collection-strategy/
  - frontend/src/features/admin-configuration/
  - frontend/src/features/voice-plaza/
  - frontend/src/features/task-center/
  - tests/
  - docs/
contracts:
  - Data Import Campaign 撤销 Contract
  - Keyword Pack 生命周期 Contract
  - Collection Plan 生命周期 Contract
  - Provider Configuration 生命周期与连接测试 Contract
  - Analysis Scheme 草稿生命周期 Contract
  - Audit Event 用户可读投影
data_changes:
  - 导入来源贡献与撤销状态
  - Keyword Pack / Collection Plan / Provider Config 归档与引用门禁
---

# 背景、目标与边界

当前系统已经具备导入、采集、AI 分析和配置能力，但多个用户可创建资源缺少完整的“编辑—停用/归档—条件删除”生命周期，导入结果也缺少安全撤销路径；同时部分主业务页面直接暴露 Batch/Campaign/Job/Run/UUID/API 等工程实现术语。

本 Change 以 Issue #381 与本轮用户确认决定为上游：**保留首页“工作台”现状，其余按产品化评审整改。** 导入撤销必须基于来源贡献，不允许按批次粗暴删除共享 Content；历史运行、审计与已发布版本继续作为可追溯证据保留。

## 非目标

- 不删除、不重定向首页“工作台”；
- 不升级 Runtime、依赖、框架或数据库；
- 不新增复杂 RBAC、双人审批、通用文件管理器、万能 Job 页面；
- 不物理删除审计、已发布 Analysis Scheme、采集/AI 历史 Run；
- 不改变 Content 的平台 + external_content_id 稳定身份与 Current/Version/Metric/Coverage 分层。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 成功/部分成功的统一导入可预览影响并安全撤销，重复撤销幂等且不误删其他来源贡献 | Issue #381 AC1 | not_satisfied | 待实现与 PostgreSQL 证据 |
| R2 | local_upload / server_path 与 ingestion_policy 保持正交，切换来源不静默改策略 | Issue #381 AC2 | not_satisfied | 待前端回归 |
| R3 | Keyword Pack 具备编辑、关键词维护、复制、归档、未引用删除；历史快照不漂移 | Issue #381 AC3 | not_satisfied | 待 Contract/DB/UI 证据 |
| R4 | Collection Plan 支持编辑、复制、归档、仅无历史运行时删除 | Issue #381 AC4 | not_satisfied | 待 Contract/DB/Scheduler/UI 证据 |
| R5 | LLM/TikHub Provider 支持连接测试，基础/高级设置分层，Secret 边界不变 | Issue #381 AC5 | not_satisfied | 待 API/UI/安全测试 |
| R6 | Analysis Scheme 主路径结构化编辑，Prompt 下沉高级；未发布未使用草稿可删，已发布版本不可删 | Issue #381 AC6 | not_satisfied | 待 API/UI/历史引用测试 |
| R7 | 审计、导入/运行详情、声音广场主视图使用业务语言，工程 ID 下沉技术详情 | Issue #381 AC7 | not_satisfied | 待前端验收 |
| R8 | 声音广场高频筛选直达、低频筛选折叠，内容类型使用真实选项 | Issue #381 AC8 | not_satisfied | 待前端验收 |
| R9 | 首页工作台现有入口与行为保持不变 | Issue #381 AC9 | satisfied | 明确非目标；不修改 HomeView/routes 的工作台语义 |
| R10 | Contract→OpenAPI→generated client 一致；Schema 仅通过新 Migration 演进并有 PostgreSQL/前端证据 | Issue #381 AC10 | not_satisfied | 待生成链、Migration、CI |
| R11 | 受影响 Product/Blueprint/Appendix/模块 README 与最终实现一致 | Issue #381 AC11 | not_satisfied | 待 targeted Docs Review |
| R12 | PR 最新 HEAD 完成 Completion Audit、独立 Review、永久 CI 后才合并 main，并关闭 Issue/归档 Change | Issue #381 AC12 | not_satisfied | 待交付闭环 |

# 方案与兼容边界

1. 导入撤销采用来源 Contribution/Delta 记录与状态机：新导入从本版本起记录可逆贡献；预览只读，执行撤销由数据库事务和 Owner 协调。无法证明安全可逆的历史 Campaign 不伪装成可撤销。
2. 配置类资源统一采用 active/archived + 引用守卫：历史快照/运行引用继续可解释；只有从未被历史事实引用的资源允许物理删除。
3. 采集计划修改通过 schedule/version 递增保持历史运行可解释性，不改写已产生 Run 的冻结事实。
4. Provider “测试连接”只做有界、显式测试调用，不回显 Secret；普通回归不依赖真实外网。
5. UI 主层使用业务语义，技术标识保留在折叠的“技术详情”中，便于排障而不成为普通使用前置条件。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 撤销状态机、生命周期资格、幂等、前端交互 |
| 接口 / Contract | required | Pydantic→OpenAPI→generated client |
| Backend/API/PostgreSQL | required | Contribution/撤销事务、FK/引用门禁、Migration |
| Browser Mock Acceptance | required | 导入撤销、资源维护、审计可读、声音广场筛选 |
| Real Full-stack Golden Path | required | 导入→查看→预览撤销→撤销→重新查询；至少一个资源维护闭环 |
| External Provider Probe | not_applicable | 连接测试 API 用隔离 Fake/Mock 验证；本 Change 不要求真实第三方调用作为合并门禁 |
| Build / Runtime | required | 后端静态检查、前端 typecheck/build、Migration check |
| Docs / Governance / Other | required | Product/Blueprint/Appendix/README、Change completion、Review/CI |

# 实施计划

- [ ] 恢复现有 Contract/Schema/调用链和相关测试，建立失败测试。
- [ ] 实现 Data Import Campaign 撤销预览/执行、贡献账本与 Migration。
- [ ] 完善 Keyword Pack / Collection Plan 生命周期与引用守卫。
- [ ] 完善 Provider 连接测试和配置归档/删除；Analysis Scheme 草稿删除与 UI 分层。
- [ ] 产品化审计、运行详情、声音广场筛选与文案；保持工作台不变。
- [ ] 重新生成 OpenAPI/Orval Client，同步 targeted 文档。
- [ ] 执行 PostgreSQL/API/前端/Full-stack/Build 验证，修复发现问题。
- [ ] Completion Audit + 两阶段 Review + PR 最新 HEAD CI；合并、归档 Change、关闭 Issue。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 Issue #381、用户决定、Product/Blueprint、Contract/Schema 和最终实现。
- [ ] change_coverage：R1—R12 均取得 satisfied / 明确 not_applicable / 正式 deferred 证据，`not_satisfied` 清零。
- [ ] reverse_audit：执行“后端能力→前端入口”和“前端动作→后端真实支持”的反向审计。
- [ ] validation_matrix：所有 required 层均有与 PR 最新 HEAD 绑定的新鲜证据。
- [ ] unresolved_cleared：无未决数据删除/兼容/权限/Secret 风险。
