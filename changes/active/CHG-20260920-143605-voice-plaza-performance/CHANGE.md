---
schema: coding-change/v1
id: CHG-20260920-143605-voice-plaza-performance
title: 优化声音广场首屏、筛选与详情加载
level: L3
status: ready_for_review
owner: codex
branch: fix/voice-plaza-observability
created: 2026-09-20
updated: 2026-09-20
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - content
  - api
  - database
  - observability
affected_paths:
  - frontend/src/features/voice-plaza/
  - frontend/e2e/voice-plaza.spec.ts
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/content/tables.py
  - backend/src/aima_ugc/modules/analysis/tables.py
  - migrations/versions/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - tests/
  - docs/
contracts:
  - GET /api/v1/contents
  - GET /api/v1/contents/{content_id}
  - GET /api/v1/contents/{content_id}/comments
  - GET /api/v1/content-filter-options
data_changes:
  - 只增加查询索引，不修改业务数据、字段或约束语义
---

# 变更摘要

- **要解决的问题**：声音广场首次进入时先等待筛选目录，导致必须等待甚至像是需要手工点击“查询”；动态筛选目录失败时平台也被错误禁用；返回页面后已选筛选条件缺少持久恢复边界；详情一次打开会重复读取内嵌评论，并为每个一级评论并发加载回复，放大数据库请求。
- **拟议修改**：让最新倒序第一页成为首屏唯一阻塞请求；稳定筛选与动态目录解耦并持久恢复已应用条件；详情只读取轻量主体和一级评论，回复按需加载；为筛选、详情存在性、评论分页和最新分析读取补最小查询优化及慢请求日志。
- **预期结果**：无筛选首次进入自动显示最新 20 条；筛选目录慢或失败不阻塞列表且平台始终可选；离开再返回恢复已应用筛选；详情请求量有界，服务端慢/错接口可通过 request_id、path、status、duration 定位。

# 背景、现状与问题

## 已确认事实

1. `VoicePlazaPage.refreshPage()` 当前先 `await refreshFilterOptions()`，随后才请求列表；筛选目录成为首屏前置条件。
2. Store 已默认 `sort_by=published_at`、`sort_direction=desc`、`limit=20`，但首屏调度没有保证这条请求最先完成并展示。
3. 平台、相关性和分析状态是稳定 Contract 值，但 `VoicePlazaFilters` 在 `filterOptions` 整体失败时把它们与动态情感/标签一起禁用。
4. 详情响应兼容内嵌最多 100 条评论，页面又单独请求评论分页；一级评论页返回后还会为每个有回复的根评论并发请求首个回复页。
5. 评论列表检查内容存在性时会执行完整详情 Read Model；筛选目录也复用完整列表投影，包含对目录计算无用的字段和关系。
6. 现有 API 日志缺少通用慢请求和 5xx 响应耗时事件，当前提供的最新日志只有进程启动，不能还原慢请求路径。

## 根因与约束

- 首屏慢不是单一网络问题，而是主列表被非关键目录串行阻塞、进入后并发资源过多、详情请求放大与数据库热路径共同造成。
- 平台不可用是前端可用性边界错误：稳定 Contract 被动态目录故障连带禁用。
- 性能修复必须保持现有 Cursor、默认 irrelevant 排除、全量服务器排序、active source 可见性、人工复核、导出和 Analysis 语义；不能用前端本页排序或放宽查询规则换速度。

# 目标、成功标准与非目标

## 成功标准

- [x] 无筛选首次进入立即请求 `limit=20&sort_by=published_at&sort_direction=desc`，收到后立刻展示，不等待筛选目录、统计、任务或导出接口。
- [x] 已应用筛选条件在离开声音广场再返回时恢复，并参与返回后的最新倒序第一页请求；“查询”仍是草稿条件生效边界。
- [x] 平台、相关性、分析状态等稳定筛选不因动态筛选目录加载中或失败而禁用；动态项失败保留上次成功目录并提供可重试诊断。
- [x] 内容详情不再重复传输旧内嵌评论；打开详情只并行读取主体和一级评论，线程回复由用户展开时按需读取。
- [x] 筛选目录和评论分页不再为存在性/目录计算执行完整详情投影；新增索引与迁移覆盖最新倒序、评论线程和当前分析热路径。
- [x] API 5xx 与超过阈值的慢请求记录脱敏的 request_id、method、path、status_code、duration_ms。
- [x] Browser、API/Contract、PostgreSQL Migration/Integration、生成 Client、构建和治理门禁均有本轮新鲜分支证据；完成两阶段 Review 后才进入 PR required checks 与受控合并。

## 范围

- 声音广场首次加载、筛选草稿/已应用状态、稳定筛选可用性、动态目录降级。
- Content 列表/详情/评论/筛选目录的查询热路径与兼容扩展。
- 最小数据库索引 Migration、API 慢/错日志及对应回归。

## 非目标

- 不引入 Redis、搜索引擎、物化视图、第二套前端数据缓存框架或新依赖。
- 不改变 Provider、采集、AI 模型调用、预算或生产部署拓扑。
- 不在没有生产 `EXPLAIN ANALYZE` 与容量数据时调整数据库连接池或宣称达到具体毫秒 SLO。
- 不预取全部分页、不在浏览器对当前页做伪“全量最新排序”。

## 必须保持不变

- PostgreSQL 继续承担全量排序和筛选；默认按发布时间降序，发布时间缺失的既有兼容语义不被破坏。
- Cursor 继续绑定筛选与排序；切换已应用条件或排序从第一页开始。
- Filter Options 的动态历史值仍来自 active Taxonomy 与当前可见 Content，前端不维护业务分类枚举。
- 详情内嵌 `comments` 字段保持向后兼容，旧调用默认行为不变；声音广场显式选择轻量读取。

# 方案比较与决策

| 方案 | 能解决什么 | 主要代价 / 缺口 | 决定 |
| --- | --- | --- | --- |
| 仅调整前端等待顺序 | 首屏能更早发起列表 | 平台仍被动态目录故障连带禁用，详情请求放大和数据库热路径不变 | 不采用为完整方案 |
| 新建物化 Read Model / 缓存服务 | 大数据量下可进一步降低复杂查询成本 | 需要失效、刷新、Schema 和运维机制；当前缺少生产执行计划证明必要性 | 本次不采用 |
| 首屏关键路径解耦 + 稳定/动态筛选分层 + 轻量详情/查询 + 针对性索引与日志 | 同时切断已确认阻塞、请求放大和热点查询，保持现有架构与 Contract | 需要兼容 Contract 扩展、Migration 和跨前后端验证 | 采用 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 无筛选首次进入自动展示最新数据第一页，按发布时间倒序且不等待筛选目录 | #547 / AC1 | satisfied | Browser 回归确认首个列表请求为第一页、20 条、`published_at desc`，慢筛选目录未阻塞首屏；API 排序回归通过 |
| R2 | 选定筛选后离开页面再返回，恢复之前已应用条件并据此自动查询 | #547 / AC2 | satisfied | Browser 回归确认已应用平台条件写入会话、离开并重新进入后自动恢复并查询 |
| R3 | 平台筛选可用，动态筛选目录慢/失败不阻塞列表或连带禁用稳定筛选 | #547 / AC3 | satisfied | Browser 回归覆盖动态目录慢、失败和手工 taxonomy 失败，平台/相关性/分析状态保持可用 |
| R4 | 系统性降低列表、筛选目录和详情加载开销，评论回复按需加载 | #547 / AC4 | satisfied | 轻量详情 `include_comments=false`、轻量存在性/目录投影、按需回复及索引回归通过；Migration 在隔离 PostgreSQL 完成 upgrade/current/check |
| R5 | 增加足够日志定位慢请求与 5xx，不记录筛选值、正文或 Secret | #547 / AC5 | satisfied | API observability 回归确认慢请求、已处理 5xx 和未处理异常事件字段；日志只记录 path，不记录 query 值或异常原文 |
| R6 | Browser Mock、真实 Browser→Vue→FastAPI→PostgreSQL、Contract/generated client、Migration、相关集成、构建与两阶段 Review 完成 | #547 / AC6 | satisfied | Playwright 129/129、Vitest 164/164、真实评论 Full-stack、API/索引目标回归、PostgreSQL Migration/Integration、Contract/client、构建及两阶段 Review 均通过；当前无未解决 finding |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Store 草稿/已应用条件、默认最新倒序、迟到请求与日志分类目标回归 |
| 接口 / Contract | required | 详情轻量读取的向后兼容 Query 扩展、OpenAPI 与 generated client 零漂移 |
| Backend/API/PostgreSQL Integration | required | 内容存在性、筛选目录、评论分页、索引 Migration upgrade/check 与真实 PostgreSQL 查询行为 |
| Browser Mock Acceptance | required | 首屏慢目录不阻塞、默认最新倒序、平台可用、筛选离开返回恢复、回复按需加载 |
| Real Full-stack Golden Path | required | Browser → Vue → FastAPI → PostgreSQL 的声音广场列表和详情关键链 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub/LLM endpoint、字段、分页或费用边界，不调用真实 Provider |
| Build / Package / Runtime | required | 前端 lint/typecheck/build、Python Ruff/mypy、迁移链与必要启动/运行检查 |
| Docs / Governance / Other | required | 当前产品/前端/Content/API 文档、Change Completion、两阶段 Review 与 Git 交付状态 |

# 实施步骤

- [x] Red：把首屏、默认排序、稳定筛选、筛选恢复和详情回复请求扇出写入 Browser 回归并确认旧实现失败。
- [x] Red：为详情轻量 Contract、内容存在性和查询索引建立 API/数据库回归并确认缺口。
- [x] Green：实现首屏优先、草稿/已应用筛选恢复、稳定筛选解耦和目录 last-known-good。
- [x] Green：实现轻量详情、一级评论/回复按需加载、轻量目录/存在性查询与索引 Migration。
- [x] Refactor：收敛请求身份、注释、错误降级和无关重复逻辑；同步当前文档与生成物。
- [x] 执行目标测试、相关回归、PostgreSQL/Contract/Browser/Full-stack/Build 门禁。
- [x] 完成 Completion Audit 与两阶段 Review，进入 PR current-head required checks。
- [ ] 完成 PR current-head required checks、受控合并、implementation main-fresh、Change 自动归档、Issue Closure Audit 与分支清理；这些是 Ready 后的平台交付门禁，不在合并前伪造完成。

# Completion Audit

- [x] upstream_re_read：完成前重新读取用户 AC、产品/Blueprint、Contract、实现和适用项目规则，独立重建完成定义。
- [x] change_coverage：逐条比较 R1—R6 与实现、测试、文档、Git 交付，确认没有遗漏或静默延期。
- [x] reverse_audit：从页面动作反查 generated Client → FastAPI → Repository → PostgreSQL，并从新增 Contract/索引反查真实消费者和部署顺序。
- [x] unresolved_cleared：R1—R6 无 `not_satisfied`，Review finding 已修复并复核；生产 `EXPLAIN ANALYZE` 与具体毫秒 SLO 未执行边界明确。PR CI、受控合并、main-fresh、自动归档与 Issue 关闭由平台真实状态持有，不伪造为 Ready 前已完成。

# 本轮验证与 Review 证据

- 前端静态与构建：ESLint、29 个 Vitest 文件共 164 项、TypeScript/Vite Build 全部通过。
- Browser Mock：Playwright 全量 129 项通过；覆盖首屏第一页最新倒序、慢/错动态目录、平台筛选可用、筛选恢复和回复按需加载。
- 真实 Full-stack：`comment-supplement.spec.ts` 通过，链路为 Browser → Vue → FastAPI → PostgreSQL，Provider 使用本地固定 Fixture，不产生外部费用。
- Backend：Ruff、mypy（346 个源码文件）、目标 API/observability/index 14 项、Content PostgreSQL Integration 8 项通过。
- Contract/Migration：OpenAPI 生成检查、兼容检查、架构/表 Owner 检查通过；隔离 PostgreSQL 升级至 `20260920_0053`，`alembic current` 和 `alembic check` 通过。
- 文档与治理：文档入口、事实一致性、Secret 扫描、项目治理接线和 `git diff --check` 通过。
- Review：标准 Review 与深度 Review 已完成；修复了未处理异常只记 WARNING 且缺少安全堆栈、Full Playwright 选择器碰撞两项发现；当前声音广场范围无未解决 finding。
- 较早的全量 Python 本地运行曾有 4 项镜像源断言基线失败；该独立问题已由 PR #550 修复并在 `main@c1472736` 通过 CI、PostgreSQL、真实 Full-stack、Runtime 与 Linux/Windows Tooling。当前分支已合并该 main，声音广场 PR 仍需以当前 HEAD 重新取得永久 CI 证据。
- 当前尚无生产数据量、`EXPLAIN ANALYZE` 或正式环境锁等待证据；本 Change 只宣称切断已确认的前端串行阻塞/请求放大并为已知查询补索引，不宣称具体生产毫秒 SLO。

# Ready 后交付边界

- Issue #547 AC6 中的 PR current-head CI、受控合并、implementation main-fresh、repository-native Change Archive、Issue Closure Audit 与分支清理是时序后置的平台门禁。
- 它们继续保持未完成，必须由 PR、Commit、Actions、Archive 与 Issue 的真实状态证明；本 Active Change 只声明施工范围达到 `ready_for_review`。

# 兼容、迁移、部署与回滚

- 详情 Query 只增加可选参数且默认保留原行为；旧客户端无需修改，声音广场使用轻量模式。
- Migration 只增加 B-tree/partial indexes，不回填、不修改业务行。部署顺序为先 Migration、后新代码；索引创建期间的锁/时长由正式环境变更窗口评估。
- 回滚代码不会要求回滚业务数据；索引可由 downgrade 删除。整体回滚会重新引入首屏阻塞、平台不可用和详情请求放大，只有新实现出现阻塞缺陷时才执行。
