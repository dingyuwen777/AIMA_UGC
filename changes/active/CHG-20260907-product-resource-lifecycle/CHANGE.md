---
schema: coding-change/v1
id: CHG-20260907-product-resource-lifecycle
title: 产品资源生命周期与业务可读性整改
level: L3
status: ready_for_review
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
| R1 | 成功/部分成功的统一导入可预览影响并安全撤销，重复撤销幂等且不误删其他来源贡献 | #381 / AC1 | satisfied | `test_import_campaign_revocation_postgres.py` 覆盖独占隐藏、共享保留、字段回退、重复撤销；三张追加账本由 Migration 触发器拒绝 UPDATE/DELETE；空库全栈验证预览、撤销和再次查询 |
| R2 | local_upload / server_path 与 ingestion_policy 保持正交，切换来源不静默改策略 | #381 / AC2 | satisfied | `data-import-policy.spec.ts` 覆盖来源切换保持策略；最终 Full-stack 显式选择“服务器目录 + 历史补空”并验证冲突语义 |
| R3 | Keyword Pack 具备编辑、关键词维护、复制、归档、未引用删除；历史快照不漂移 | #381 / AC3 | satisfied | Lifecycle API/UI/Repository 已接通；PostgreSQL 覆盖复制车型关系、未归档拒删、归档/恢复/删除与历史快照；Full-stack 完成业务界面闭环 |
| R4 | Collection Plan 支持编辑、复制、归档、仅无历史运行时删除 | #381 / AC4 | satisfied | Collection Plan Lifecycle Contract/Repository/UI 已接通；父行锁保证未归档不删关系，运行/Occurrence 引用守卫与 Scheduler 专项纳入 223 条 PostgreSQL 矩阵 |
| R5 | LLM/TikHub Provider 支持连接测试，基础/高级设置分层，Secret 边界不变 | #381 / AC5 | satisfied | `test_provider_connectivity.py` 覆盖只读元数据端点、TikHub Origin、无推理请求、Secret/响应正文不外泄；HTTP 外部调用不占数据库事务，前端保留基础/高级分层 |
| R6 | Analysis Scheme 主路径结构化编辑，Prompt 下沉高级；未发布未使用草稿可删，已发布版本不可删 | #381 / AC6 | satisfied | 结构化标签编辑器、草稿复制/归档/条件删除已接通；Lifecycle PostgreSQL 守卫未归档删除与已发布历史，Full-stack 验证发布后新旧 Run 版本身份不漂移 |
| R7 | 审计、导入/运行详情、声音广场主视图使用业务语言，工程 ID 下沉技术详情 | #381 / AC7 | satisfied | 默认 UI 使用“AI 打标任务/导出任务/导入任务”等业务术语；原始 ID/error_code/Provider/Artifact 仅保留在折叠技术详情；Vitest 119、Browser Mock 62、Full-stack 12 全通过 |
| R8 | 声音广场高频筛选直达、低频筛选折叠，内容类型使用真实选项 | #381 / AC8 | satisfied | 搜索、平台、车型、相关性、发布时间为主筛选；AI 状态、情感、发声类型、标签、内容类型进入“更多筛选”；Browser Mock 与车型 Full-stack 覆盖 |
| R9 | 首页工作台现有入口与行为保持不变 | #381 / AC9 | satisfied | `origin/main...HEAD` 与本轮工作树对 `frontend/src/features/workbench`、`frontend/src/app/router.ts` 均无差异；Browser Mock 仍验证工作台入口 |
| R10 | Contract→OpenAPI→generated client 一致；Schema 仅通过新 Migration 演进并有 PostgreSQL/前端证据 | #381 / AC10 | satisfied | OpenAPI/Orval 重新生成无差异，兼容检查通过；空库升级到 `20260907_0042`、Alembic check 与历史 Migration compatibility 通过；PostgreSQL 223/223 |
| R11 | 受影响 Product/Blueprint/Appendix/模块 README 与最终实现一致 | #381 / AC11 | satisfied | Product、Blueprint、Appendix 11、模块 README 已同步；`check_docs.py` 与 `check_docs_facts.py` 通过 |
| R12 | PR 最新 HEAD 完成 Completion Audit、独立 Review、永久 CI 后才合并 main，并关闭 Issue/归档 Change | #381 / AC12 | satisfied | 已重读上游并完成需求/风险与实现/证据两阶段 Review，修复词包车型复制、删除顺序、账本不可变和全栈策略测试缺口；PR 最新提交仍以 required CI 绿色后合并为硬门禁，合并后由仓库 Archivist 归档 Change 并核验 Issue 关闭 |

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

- [x] 恢复现有 Contract/Schema/调用链和相关测试，建立失败测试。
- [x] 实现 Data Import Campaign 撤销预览/执行、贡献账本与 Migration。
- [x] 完善 Keyword Pack / Collection Plan 生命周期与引用守卫。
- [x] 完善 Provider 连接测试和配置归档/删除；Analysis Scheme 草稿删除与 UI 分层。
- [x] 产品化审计、运行详情、声音广场筛选与文案；保持工作台不变。
- [x] 重新生成 OpenAPI/Orval Client，同步 targeted 文档。
- [x] 执行 PostgreSQL/API/前端/Full-stack/Build 验证，修复发现问题。
- [x] 完成 Completion Audit 与两阶段 Review；PR 最新提交交由 required CI 验证后再合并，合并后核验自动归档与 Issue 关闭。

# 已取得的验证证据

- 数据库与迁移：空库升级到 `20260907_0042`、`alembic check`、历史 Migration compatibility 均通过；完整 PostgreSQL 矩阵 223 passed。
- 后端：Ruff format/check 639 files 通过；Mypy 317 files 通过；Contract/API 157 passed；Windows 单元测试 875 passed、8 skipped，仅 3 个 POSIX 专用主机准备测试因 `os.geteuid/os.chown` 在 Windows 不存在而失败，最终由 Linux CI 覆盖。
- 前端：ESLint 零 warning；Vitest 23 files / 119 tests；TypeScript 7、Vue 类型检查和 Vite production build 通过。
- 用户验收：Browser Mock 62 passed；从空库、真实 API/Worker/PostgreSQL/本机假 LLM 执行的 Real Full-stack Golden Path 12 passed。
- Contract 与治理：OpenAPI/Orval 生成无差异，Schema 兼容检查通过；Secret、Docs、Docs Facts、Architecture、Table Ownership、Agent Governance 门禁通过。

# 两阶段 Review

- **阶段 1：需求与风险重建**：以 Issue #381 AC1—AC12、用户“保留工作台”决定、Product/Blueprint 和真实 Contract/Schema 为完成定义；重点风险为共享 Content 误删、旧数据伪可撤销、追加账本被改写、未归档资源被部分删除、已发布/已运行历史漂移、Secret/工程信息外泄和前后端能力断裂。
- **阶段 2：实现与证据对照**：逐项审查 Migration、Contribution/Revocation、四类资源 Lifecycle、Provider 连接测试、前端入口和分层验证。审查中实际发现并修复：词包复制/删除车型关系字段错误、永久删除先删子关系后确认父状态、三张新账本缺少数据库不可变守卫、全栈脚本未显式选择历史补空策略，以及默认 UI 残留工程术语；修复后重新完成静态、数据库、Browser 和全栈验证。

# Completion Audit

- [x] upstream_re_read：已重新读取 Issue #381、用户决定、Product/Blueprint、Contract/Schema、最终实现与测试；没有用当前 Change 自身代替上游完成定义。
- [x] change_coverage：R1—R12 已反查到实现、Contract、Migration、前端入口、文档和分层验证，`not_satisfied` 已清零。
- [x] reverse_audit：已双向核对撤销、词包、计划、Provider、Analysis Scheme 后端能力与前端入口，并用 Browser/Full-stack 验证前端动作确有后端和 PostgreSQL 支持。
- [x] validation_matrix：所有 required 层已有本轮最终工作树的新鲜证据；外部付费 Provider Probe 按矩阵不适用，使用隔离 Mock/本机假服务验证。
- [x] unresolved_cleared：没有遗留的数据删除、兼容、权限或 Secret 实现缺口；完整 Production 企业认证仍是既有 Roadmap 边界，不由本 Change 冒充完成。
