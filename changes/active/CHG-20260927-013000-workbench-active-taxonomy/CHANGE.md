---
schema: coding-change/v1
id: CHG-20260927-013000-workbench-active-taxonomy
title: 工作台按 active Analysis Scheme 落地
level: L3
status: proposed
owner: codex
branch: feature/626-workbench-active-taxonomy
created: 2026-09-27
updated: 2026-09-27
completion_gate: required
depends_on: []
affected_areas:
  - workbench
  - content
  - analysis
  - identity
  - frontend
  - database
affected_paths:
  - backend/src/aima_ugc/contracts/
  - backend/src/aima_ugc/modules/workbench/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions/
  - contracts/openapi/openapi.json
  - frontend/src/features/workbench/
  - frontend/src/features/voice-plaza/
  - frontend/src/views/HomeView.vue
  - frontend/src/generated/api/client.ts
  - tests/
  - docs/
contracts:
  - Workbench HTTP Contract
data_changes:
  - 用户级工作台布局持久化
---

# 变更摘要

- **要解决的问题**：当前 `/` 仍是工作台占位图；Figma 已完成正式业务口径，但仓库没有工作台聚合 Contract、active Scheme Version 专用统计或用户布局持久化。
- **拟议修改**：基于当前 Content/Analysis/Identity 事实新增 Workbench Read Model 与用户布局，走 Pydantic → OpenAPI → generated client，按已确认 Figma 正式状态实现 Vue 工作台；不新增采集链、不新增 LLM、不引入新基础设施。
- **预期结果**：用户进入 `/` 可查看声音流、active Taxonomy 驱动的品牌用户心智与 UGC 趋势，分析任务有新结果时自动刷新，并可显式编辑、保存或取消个人工作台布局。

# 背景、现状与问题

## 背景

Issue #626 已冻结本轮工作台的业务口径。Figma Page `3433:834` 已同步为 active Taxonomy、active Scheme Version、显式编辑草稿和真实 Contract-first 设计。

## 当前现状

- `frontend/src/views/HomeView.vue` 只展示 `workbench-placeholder.png`。
- 当前 OpenAPI 没有 Workbench 聚合与布局资源。
- active Analysis Scheme Version 已由数据库唯一 active 指针持有；每个 Analysis Run 冻结 `analysis_scheme_version_id`。
- 当前声音广场 projection 的 AI 字段取最新 Analysis Result，并不保证属于当前 active Scheme Version，因此不能直接作为工作台 AI 指标事实源。
- `accounts` 已以 `(platform, external_account_id)` 唯一约束提供用户去重身份；`identity_principals.id` 是用户级配置可用的稳定 Principal。
- 当前前端已具备 Analysis Run 轮询、任务中心、消息中心、ECharts 和 generated fetch client。

## 问题、根因或约束

工作台需要“当前 active Scheme Version”口径，而现有声音广场为兼容历史筛选保留“最新结果 + historical values”语义；直接复用其 AI projection 会在 Scheme 切换后混算旧结果。布局编辑又需要新的用户级持久事实，不能只放浏览器本地。

## 不修改的后果

工作台继续是占位图；即使只做前端拼装，也会出现固定 Taxonomy、旧 Scheme 混算、布局不可恢复或假 Contract 等错误。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | `/` 当前仅展示占位图 | `frontend/src/views/HomeView.vue` | 必须实现真实 Workbench Feature |
| E2 | AI Run 冻结 `analysis_scheme_version_id`，active Version 可由 Analysis Scheme Repository 读取 | Analysis tables / `active_analysis_configuration()` | 工作台 AI 指标按 active Version 过滤 |
| E3 | Voice Plaza projection AI 结果是“最新 Run”，未按 active Version 过滤 | `content_queries.py` / projection refresh SQL | 不直接把 projection AI 字段当工作台指标事实 |
| E4 | `accounts` 唯一约束为 `(platform, external_account_id)` | `modules/content/tables.py` | 心智用户按该身份去重 |
| E5 | Principal 使用稳定内部 `principal_id` | `modules/identity/tables.py` | 用户布局以 Principal 为 Owner |
| E6 | HTTP 类型链固定为 Pydantic → OpenAPI → Orval | `docs/blueprint/04_后端任务API与前端.md` | 不手写第二套前端 Contract |
| E7 | Figma 已完成 active Taxonomy/编辑草稿/上期口径收口 | Figma `3433:834` | 作为 UI/交互 Requirement Baseline |

## 推断与待确认

- 工作台大规模聚合是否需要预聚合 Read Model，必须由真实 PostgreSQL 查询计划/基准决定；在证据出现前不引入 Redis/Kafka/第二套实时系统。

# 目标、成功标准与非目标

## 目标

实现可生产使用的工作台：真实数据库聚合、active Scheme 一致性、动态 Taxonomy、用户布局、自动刷新、声音广场深链，并与当前 Figma 一致。

## 成功标准

- [ ] #626 / AC1–AC11 全部满足并有当前 revision 证据。
- [ ] required CI、独立 Review、Figma Conformance、merge 后 main-fresh 与 Change Archive/Issue Closure 完成。

## 范围

Issue #626 明确范围，以及完成这些 AC 所需的 Contract、Migration、Read Model、前端 Feature、深链、测试和 targeted 文档/Figma 回填。

## 非目标

不改 TikHub；不新增工作台 LLM；不引入 Redis/Kafka/WebSocket；不升级依赖/Runtime；不改写历史 Analysis Result 审计事实。

## 必须保持不变

声音广场现有历史筛选与人工纠正 effective_* 语义；现有模块化单体、PostgreSQL、FastAPI/Pydantic/OpenAPI/Orval、Vue/Pinia、Durable Job、权限/安全与 CI 门禁。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Workbench 新 Read/Preference Owner；复用 Analysis/Content/Identity 事实 | E1–E7 / #626 | 不改变采集或历史审计 Owner |
| 接口与契约 | 新 Workbench API 先 Pydantic，再生成 OpenAPI/Client | E6 / #626 AC10 | Contract 兼容与生成门禁 required |
| 数据与迁移 | 仅新增用户工作台布局事实；AI 聚合实时读当前事实，先不建预聚合 | E2–E5 / #626 AC11 | 需要 0071 Migration；预聚合由性能证据决定 |
| 错误与失败语义 | 模块独立失败；布局 CAS 冲突显式 409；active Taxonomy 不可用按现有 503 语义收口 | Figma / 项目 HTTP 规则 | 不静默覆盖或伪造空数据 |
| 兼容性 | 保留 `/` Route；不改变声音广场既有 API 语义 | #626 / E1 | Workbench 使用专用 Contract |
| 部署与回滚 | 应用与 0071 Schema 一起升级；回滚先旧应用再降级布局表 | 当前 Migration 策略 | 不涉及生产部署授权 |

# 修改方案与决策依据

## 最小充分方案

1. **Contract/Schema Red**
   → 新 Workbench Pydantic Contract、布局表与 0071 Migration；新增失败测试。
   → 验证 Contract/Schema 先失败，再实现。
2. **Backend Read Model**
   → Workbench Repository 以可见 Content 为基线，AI 结果只选 active Scheme Version 的当前 Content Version；叠加当前 manual/relevance effective 语义。
   → 实现声音流、趋势、心智、上期比较与布局 CAS。
3. **HTTP / Generated Client**
   → 在现有 API 装配 Workbench Service/Routes，生成 OpenAPI 与 Orval Client，不手写第二套类型。
4. **Frontend**
   → 新 `features/workbench/`，HomeView 只作入口；复用 AppShell、Task Center、Notification、ECharts；实现动态 Taxonomy、自动刷新、显式编辑草稿与保存/取消。
5. **Voice Plaza Deep Link**
   → 从 Route Query 恢复现有可表达的筛选，使工作台“查看原声/当天内容”落到真实声音广场。
6. **性能与验收**
   → PostgreSQL Integration + EXPLAIN/代表性数据；若当前方案满足则停止，不引入预聚合；否则只做证据驱动的最小索引/Read Model 优化。
7. **Figma/Docs/Delivery**
   → 最终 Contract 回填 Figma Annotation，targeted 文档同步，Completion Audit、Review、CI、PR、merge、main-fresh、Archive/Closure。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 Workbench 独立 active-Scheme 查询 | E2/E3 | 避免改变 Voice Plaza 兼容历史语义且防旧 Scheme 混算 |
| D2 布局用 Principal 持久化 + revision CAS | E5 / #626 AC7 | 跨浏览器恢复且不静默覆盖 |
| D3 不先建预聚合 | #626 AC11 | 正确性先闭环，复杂度由真实性能证据触发 |
| D4 前端复用任务轮询 | E7 + 当前 task-center | 满足自动刷新且避免单条结果触发高频全页请求 |

## 备选方案与取舍

- 直接修改 Voice Plaza projection 只保留 active Scheme：会破坏其历史值/兼容筛选语义，不采用。
- 前端重复调用 Content Count 拼趋势：会制造多次大聚合和口径漂移，不采用。
- 直接新增预聚合/Redis/WebSocket：当前无性能或实时性证据要求，不采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | `/` 实现真实 Figma 工作台 | #626 / AC1 | not_satisfied | 待实现 |
| R2 | 工作台 AI 选项来自 active Taxonomy | #626 / AC2 | not_satisfied | 待实现 |
| R3 | AI 指标只统计 active Scheme Version | #626 / AC3 | not_satisfied | 待实现 |
| R4 | relevant 范围按“正面”计算正向率 | #626 / AC4 | not_satisfied | 待实现 |
| R5 | 一级心智/用户去重/多标签占比规则 | #626 / AC5 | not_satisfied | 待实现 |
| R6 | 紧邻等长北京时间上期 | #626 / AC6 | not_satisfied | 待实现 |
| R7 | 显式编辑草稿/保存取消/CAS | #626 / AC7 | not_satisfied | 待实现 |
| R8 | Analysis Run 进展驱动合并刷新 | #626 / AC8 | not_satisfied | 待实现 |
| R9 | Workbench → Voice Plaza 深链恢复 | #626 / AC9 | not_satisfied | 待实现 |
| R10 | Contract/Migration/测试/Figma/Docs/CI | #626 / AC10 | not_satisfied | 待实现 |
| R11 | PostgreSQL 性能证据后再决定预聚合 | #626 / AC11 | not_satisfied | 待实现 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Workbench Contract / Service / Repository | 聚合与布局 API | 真实后端能力 | R2–R8 |
| Migration / Schema | 用户布局表与必要索引 | 跨会话持久化 | R7 |
| OpenAPI / generated client | 生成公共消费者 | 单一 Contract 链 | R10 |
| Workbench Vue Feature / HomeView | 页面、图表、编辑和自动刷新 | 用户入口 | R1–R9 |
| Voice Plaza route hydration | 深链筛选恢复 | 跨页面闭环 | R9 |
| Tests / Docs / Figma | 分层证据与事实同步 | 可交付闭环 | R10–R11 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 上期计算、正向率、心智占比、布局草稿/Store/UI |
| 接口 / 契约 | required | Pydantic/OpenAPI/Orval 与兼容检查 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL active-Scheme 聚合、布局 CAS、Migration |
| 用户 / 工作流验收 | required | 默认工作台、筛选、深链、保存/取消、自动刷新 |
| 跨组件关键路径 | required | Analysis → Workbench → Vue；Workbench → Voice Plaza |
| 外部依赖 / 供应方探测 | not_applicable | 本任务不需要 TikHub/LLM 外部 Probe |
| 构建 / 打包 / 运行 | required | Python gates、Frontend lint/typecheck/build、stack/fullstack |
| 文档 / 治理 / 其他 | required | Change、targeted Docs、Figma Conformance、CI/Review |

## 验证计划

- 目标测试：Workbench domain/repository/API/component/store。
- 相关回归：Content/Analysis/Identity、Voice Plaza、frontend browser mock。
- 静态检查或构建：ruff/mypy、contract generator/compatibility、npm lint/typecheck/build。
- 专项真实边界：PostgreSQL Migration/Integration、代表性聚合 EXPLAIN/benchmark、Full-stack Golden Path。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready` 及仓库当前 CI。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | active Scheme 切换时旧结果混算、标签 JSONB/distinct user 聚合开销、布局并发覆盖 | active Version 条件、真实 PG 证据、revision CAS |
| 兼容性 | 新增 API/表；保留既有 Route 与 Voice Plaza API | 不删除/重释已有 Contract |
| 数据 / Migration | 新增用户布局表；无需改写历史 Analysis | 0071 可逆 |
| 部署 / 运行 | 需要先升级 Schema 再运行新应用 | 当前 Migration 模式 |
| 回滚 / 恢复 | 先回滚应用，再降级 0071；用户布局可丢弃但 Content/Analysis 事实不受影响 | 新表不拥有既有业务事实 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 同步工作台真实数据流/页面开发基线；不复制 API 字段全集。
- **依赖 / Runtime**：不新增、不升级。
- **配置 / Secret**：无新增。
- **部署 / Release**：有 0071 Migration；本任务授权 merge，不授权生产 Deploy。
- **兼容 / 消费方通知**：Frontend generated client 与 Figma Annotation 随真实 Contract 同步。

# 完成审计

- [ ] upstream_re_read：Ready 前重读 #626、当前 Figma、Contract/Schema/代码。
- [ ] change_coverage：逐条核 AC1–AC11。
- [ ] reverse_audit：后端能力→页面入口；页面动作→真实后端；Migration→读写 Owner；Analysis Run→自动刷新。
- [ ] unresolved_cleared：所有 not_satisfied 清零。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 待填写 | 待填写 | 待填写 | 待填写 |

## 未验证内容与剩余风险

当前尚未开始生产实现与测试。

## 交付状态

- 提交：仅 Change 初始化待创建。
- 拉取请求：待创建。
- CI：待执行。
- 合并：待执行。
- Change 归档：待合并后验证。
- 发布 / 部署：生产 Deploy 未授权，不在本任务执行。

## 备注

Figma Page `3433:834` 已按本 Issue 的业务口径同步；最终 Contract 生成后还需 targeted 回填 Annotation。
