---
schema: rvc-change/v1
id: "CHG-20260821-stage8e-tikhub-supplement"
title: "Stage 8E TikHub 辅助补采与统一运行中心"
level: L3
status: done
owner: "codex"
branch: "feature/stage8e-tikhub-supplement"
created: 2026-08-21
updated: 2026-08-21
depends_on: []
affected_areas:
  - "collection"
  - "ingestion"
  - "api"
  - "frontend"
  - "contracts"
  - "docs"
affected_paths:
  - "backend/src/aima_ugc/modules/collection"
  - "backend/src/aima_ugc/modules/ingestion"
  - "backend/src/aima_ugc/adapters/persistence/postgres"
  - "backend/src/aima_ugc/bootstrap"
  - "backend/src/aima_ugc/contracts/http.py"
  - "migrations"
  - "contracts/openapi/openapi.json"
  - "frontend"
  - "tests"
  - "docs"
contracts:
  - "HTTP Pydantic → OpenAPI → Orval：统一运行列表、TikHub 补采创建与 Run 查询"
  - "现有 collection.run.v1 Job Payload 与 Provider Capability"
data_changes:
  - "collection_runs.import_batch_id（可空外键；一个 Import Batch 可关联多个补采 Run）"
---

# 背景与当前事实

- 本 Change 从最新 `main` `7e529df056d9237edbc90d620921103574691489` 创建；远端没有开放 PR，
  该 Head 的最新 GitHub `main` workflows 全部成功。
- Stage 8C 已有 Excel Import Batch 列表、三个 KPI、详情与上传；Stage 8D 已有渠道无关的“声音广场”。
- 正式 TikHub 五平台关键词发现、详情、评论、二级回复、Raw、Mapper、全局 Relevance、
  `ContentIngestionService` 与 `collection.run.v1` Worker 已存在，但当前没有网页创建/查询 Collection Run
  的 HTTP Contract；正式 Scope Runtime 当前只执行 `keyword_search/content_discovery`。
- `collection_runs` 与 `processing_import_batches` 当前没有外键关联；Import Batch 列表只读取 Excel Job，
  不能提供跨 Import/Collection 的稳定统一分页。
- 仓库没有 `openspec/`；本任务按唯一 L3 Active Change 管理。

# 目标

把 TikHub 正式采集能力产品化为采集运行中心内的辅助来源：用户可以用一次性 Discovery 关键词主动从
五个平台发现新帖子，也可以从已有 Excel Import Batch 发起内容详情/评论补采；所有 Excel Batch 与
TikHub Collection Run 在同一“全部运行”列表集中查询，同时后端继续保持 Batch/Run/Job 各自 Owner。

# 成功标准

- [x] `POST /api/v1/collection-runs` 只创建持久化 Collection Run/Scopes 与既有 `collection.run.v1` Job，
  Router 不发送 TikHub 请求、不执行长任务。
- [x] `discovery` 模式接收一次性关键词并冻结到 Run/Scope，不写 `keyword_packs`，不创建 Plan；每个平台
  显式选择已启用且 Registry/Capability 支持的 `provider_config_id`。
- [x] `batch_supplement` 模式只接受存在的 Import Batch，并为该 Batch 实际来源账本关联的当前 Content
  建立 `content/content_enrichment` Scope；Batch 与 Run 通过真实可空外键关联，一个 Batch 可有多个 Run。
- [x] 两种模式都复用正式 Provider Request/Attempt、Raw、Mapper、全局 Relevance、Candidate、
  Fenced Ingestion 与 PostgreSQL Content Owner；不新建平行 TikHub Writer/Mapper/Job。
- [x] Capability HTTP 只返回 Provider Config 的稳定 ID/显示名与业务能力，不返回 Secret、Base URL、
  endpoint、cursor、page、search_id 或 Pricing 私有事实。
- [x] `GET /api/v1/collection-runtime/runs` 使用稳定签名 Cursor 集中返回 Excel Import 与 TikHub Run；
  `GET /api/v1/collection-runtime/summary` 的三个 KPI 聚合两类运行，不由前端拼页计算。
- [x] `GET /api/v1/collection-runs/{run_id}` 返回 Run、Scope、关联 Batch 与 Job 的固定状态/进度/统计/
  安全错误摘要；不存在、非法请求、无可执行目标和 Provider Config 冲突使用统一 Error Contract/request_id。
- [x] Pydantic → OpenAPI → Orval → Feature API/Pinia/Vue 完整闭环；页面默认“全部运行”，并提供
  `Excel 导入`、`TikHub 辅助补采` 过滤和两种 TikHub 创建模式。
- [x] Job claim/takeover、Fencing、Retry、Deadline、Raw 恢复与 Content 幂等在真实 PostgreSQL 18 上验证；
  普通 CI 使用 Fake Transport，不产生真实 TikHub 费用。
- [x] Migration 多路径、前后端质量门禁、两阶段 Review、最终 PR Head CI、正常合并、归档及合并后
  `main` 新鲜验证全部完成。

# 范围

- Collection Run 创建/查询、Provider Capability 只读 HTTP Contract 与 Application Service。
- 一次性 Discovery 关键词规范化、Run/Provider/Relevance/策略快照与 durable Job 创建事务。
- Import Batch → Collection Run 可空外键和 Batch Content 补采目标 Query。
- 正式 Scope Runtime 增加已有 Content 的详情/评论补采分支；保留关键词发现原路径。
- Import + Collection 的统一只读运行列表、Summary、签名 Cursor 和详情状态。
- 固定 OpenAPI、Orval 生成 Client、采集运行中心 Feature API/Store/Vue/E2E。
- 本次确认的 PNG 视觉基线、真正受影响的 Blueprint/API/测试/部署说明。

# 非目标

- 不在声音广场显示 TikHub 来源专属入口、状态或徽标；声音广场继续只显示统一 Content。
- 不保存/管理 Discovery Keyword Pack，不实现 Collection Plan、Scheduler 配置或 Stage 8F Relevance 页面。
- 不实现 Provider Config/Secret 写入、轮换或明文读取；Stage 8E 只选择既有启用配置。
- 不实现 Provider 私有分页、endpoint/API family、Pricing、预算/Cost Guard、请求金额上限或 ETA。
- 不实现其他 Provider、新平台、TikHub 自动 fallback、认证授权或公网生产开放声明。
- 不自动触发 AI Analysis，不改变声音广场/导出 Contract，不升级依赖，不重构无关模块。

# 必须保持不变

- `Collection Run → JobWorker → TikHub Operation → Raw → Mapper → Relevance → Ingestion` 是唯一生产链；
  `collection.run.v1` Payload 继续不放 Run ID/Secret，由当前 Job ID 反查 Run。
- 已发布 Import Batch、Job、Content、Analysis、Export HTTP Contract 与既有 Cursor 继续兼容；统一运行列表
  是新增 Read Model，不把原端点改成含义不同的万能模型。
- `processing_import_batches` 仍由 Ingestion Owner 写，`collection_runs/scopes` 仍由 Collection Owner 写，
  `contents/comments` 仍只由 Content Owner Repository 写。
- Secret 不进 HTTP Response、Job Payload、Run Snapshot 值、日志、Raw 或数据库明文；Snapshot 只冻结
  `secret_ref` 身份，Worker 仍从既有安全边界解析。
- Discovery 与 Relevance 保持分离：一次性 Discovery 关键词决定搜索输入，全局唯一 Relevance 快照决定
  所有来源 Mapper 后的内容准入。
- Windows 本地与 Linux 部署使用相同 Contract/路径无关行为；页面继续使用 Vue SFC、现有 Token、
  Feature API/Pinia 与生成 Client，不引入平行 CSS 框架或手写请求 Client。

# 关键决策

## 用户已确认

1. **页面位置**：TikHub 辅助补采只在“采集运行中心”产品化；声音广场不关心采集渠道，不增加专属显示。
2. **集中运行记录**：页面默认“全部运行”，集中显示所有 Excel Import Batch、TikHub 主动发现 Run 与
   基于 Batch 的补采 Run；后端不因此合并 Batch/Run/Job Owner。
3. **两种 TikHub 模式**：`discovery` 可独立主动获取新帖子；`batch_supplement` 面向已有 Batch 的 Content
   补充详情/评论。二者都创建正式 Collection Run/Job。
4. **一次性关键词**：Stage 8E 页面输入的一次性 Discovery 关键词只冻结到本次 Run，不写入 Discovery
   词包；可复用词包保存与 Plan 配置留到 Stage 8F。
5. **视觉基线**：用户于 2026-08-21 批准
   `docs/assets/stage8e/tikhub-supplement-centralized-runs-prototype.png` 作为一次性 PNG 视觉基线，尺寸
   `1586×992`，SHA-256 `343E61427D6E94F5DC814A9040925F6BCEF3D8E493B2A2AA95062D1BAEFDCCE5`。
   这是对 Blueprint 16 Figma-first 的 Change 级例外；未来 Figma 重新生成前端代码只替换视觉组件/样式，
   保持 route、Pydantic/Orval Contract、Feature API/Store、两种模式与统一运行列表语义兼容。

## L3 方案比较

- **选定：统一只读 UNION Read Model + `collection_runs.import_batch_id` 可空外键。** 独立发现 Run 的
  外键为空；Batch 补采 Run 引用一个 Batch，一个 Batch 可关联多个 Run。优点是关系可约束、查询简单、
  不新增万能父表；代价是一条向前 Migration 和 Collection→Ingestion 的显式跨域 FK。
- 未选：新建“万能采集批次”父表并让 Import/Collection 都迁入。会复制现有 Owner/状态机，迁移范围大，
  不符合 Stage 8E 最小增量。
- 未选：只把 Batch ID 塞入 `config_snapshot`。没有 FK，无法防悬空/错误关联，也不能可靠支持 Batch 查询。
- 未选：多对多关联表。当前一个补采 Run 只从一个业务上下文创建，多对多没有已观察需求；需要时另立
  Change，而不是提前增加关系复杂度。

## 创建与执行语义

- Provider Config 选择沿用 Blueprint 08：每个平台请求显式携带 `provider_config_id`；页面在仅一个合法
  配置时自动选择，多配置时显示稳定显示名供选择，后端最终通过 Registry/Capability 验证。
- Batch 补采按 Batch 全部可追溯当前 Content 建 Scope；平台筛选只缩小目标，不接受浏览器提交外部帖子
  ID 列表。Scope 保存内部 Content UUID，Worker 重读合法 Content 身份，避免浏览器伪造平台外部 ID。
- 补采内容详情是正式链的基础步骤；评论可选，二级回复只能在评论启用时选择。全局 Relevance 为满足
  Stage 8B 固定规则可能执行一次 Detail 终判，该技术前置不能被 UI 伪装为零 Provider 调用承诺。
- API/Worker 不提供真实费用预测或预算阻断；创建 UI 明确提示真实 TikHub 请求可能产生费用。普通自动化
  只使用 Fake Transport/固定 Fixture。
- 手工 API Run 的 Attempt Deadline 复用 Stage 7 Provider 技术执行窗口推导，最大 Attempt 复用正式
  Collection Job 当前值 `2`；Heartbeat 不延长 Deadline，旧 Fence 不能提交业务可见结果。

# 数据、Migration、部署与回滚

- Migration 在当前 `20260821_0021` 后新增 `collection_runs.import_batch_id` 可空 FK 与查询索引；既有
  scheduled/manual/api/backfill Run 自动保持 `NULL`，无数据回填。
- 部署顺序：先 Migration，再部署已注册当前 `collection.run.v1` Handler 的 Worker/API，最后部署前端；
  新创建入口在 Worker 未升级时不得开放。
- 应用回滚：先停止创建新补采 Run，等待或取消在途新 Run，再回滚 API/Worker/Frontend；数据库列为新增
  可空字段，可先保留。执行 downgrade 会删除关联列，若已有 Batch→Run 业务事实必须先备份，不能自动做。
- 统一 Read Model 不写数据库；删除前端或 API 不影响既有 Import/Collection 执行与 Content 数据。

# 安全、兼容与运维风险

- 当前没有认证，补采写接口只适用于受信部署边界；文档不得宣称可直接公网开放。
- 查询参数绑定、UUID/枚举/关键词长度与数量有界；公开响应不返回 Raw、Secret、内部路径或 Provider 私有
  分页。错误只返回稳定 code/safe summary/request_id。
- 一个 Batch 可能产生大量 Content Scope 和付费请求；本阶段不发明业务数量/金额预算，页面在提交前显示
  费用警告，实际 Scope 数由服务端来源账本确定；运行仍受现有页数、Provider timeout、Job Deadline、
  取消与 Fencing 保护。
- 新接口/字段均为新增；原 Import、Content、Job 与 Vue route 行为保持兼容。

# 任务

- [x] 恢复最新 main、Active Change、Stage 8D 归档、PR/CI、Migration、Blueprint 与现有调用链事实
- [x] 确认两种 TikHub 模式、集中运行列表、Stage 8F 边界与 PNG 视觉基线
- [x] 先写 Pydantic/HTTP/OpenAPI、统一列表/Cursor/Capability 失败测试并确认 Red
- [x] 先写 PostgreSQL Schema/关联/Run 创建/Batch 目标/Job Fencing-Retry 失败测试并确认 Red
- [x] 实现 Migration、Collection HTTP Service、统一 Query Read Model 与 Batch 关联
- [x] 扩展正式 Scope Runtime 支持 content enrichment，复用详情/评论/Raw/Mapper/Ingestion
- [x] 固定 OpenAPI、生成 Orval Client，实现采集运行中心 Feature API/Store/Vue/E2E
- [x] 同步真正受影响的 Blueprint、API、测试与部署说明
- [x] 执行真实 PostgreSQL、Migration、后端/前端/生成物与安全质量门禁
- [x] 完成需求符合性 Review 与代码质量 Review，严重/重要问题清零
- [x] Commit、Draft PR、CI/Review、Ready、正常合并、main 验证与 Change 归档

# 验证

## 计划

- 目标测试：Stage 8E Contract/API、统一运行 Query/Cursor、Collection Run 创建、Batch 补采、Scope Worker。
- 相关测试：Stage 8B/8C Import、Stage 7 Collection/Provider/Worker、Stage 8D Content 来源过滤、Job Runtime。
- PostgreSQL：Artifact/Batch/Run/Scope/Job/Raw/Candidate/Content/Comment 纵切、事务回滚、幂等、Retry/Fencing；
  Migration base→head、previous→head、downgrade/re-upgrade、`alembic current/check`。
- 静态检查/构建：Ruff Format/Check、mypy、Architecture、Table Ownership、Secret、Docs、OpenAPI Drift/
  Compatibility、Orval、Frontend Lint/Type/Vitest/Build/Playwright、完整适用 CI。

## Red → Green 证据

- Contract/API 首轮：6 个测试因缺少 Stage 8E 路径、Pydantic Schema 与 `create_app` 注入边界失败；实现
  固定 Contract/Router 后 6 个通过，补充 Scope 响应用例先因模型缺失失败后共 7 个通过。
- Schema/Cursor：测试先因统一 Cursor 模块和 `collection_runs.import_batch_id` 缺失失败；实现签名
  Cursor、表声明与 Migration 后 6 个通过。
- PostgreSQL 创建/统一查询：测试先分别因 `bootstrap.collection_http` 缺失与统一 Query
  `NotImplementedError` 失败；实现短事务 Run/Job/Scope 创建、Batch FK、UNION Read Model 与 KPI 后通过。
- Worker：Batch 补采用例先观察到 Provider 调用数为 0、Scope 以 `scope_execution_failed` 失败，确认正式
  Executor 尚不支持 `content/content_enrichment`；最小扩展复用 Detail/Raw/Mapper/Relevance/Fenced
  Ingestion 后通过，并追加评论不抓二级回复、503 新 Attempt Retry 用例。
- Capability 安全 Review 新增回归断言后，测试明确因响应含 `provider_operations` 与分页策略而失败；改为
  只公开 `provider + platform + business operations` 后目标 PostgreSQL 测试 2/2 通过。
- Frontend 首轮 3 个 Vitest 因统一运行 Feature API/Store 不存在失败；实现 Orval-only API、Pinia、Vue
  组件后 3 个通过。随后补充 Playwright 的 Batch 补采提交 Contract，Stage 8E 四条浏览器流程 4/4 通过。

## 新鲜证据

- 最终非数据库后端：`tests/unit tests/contracts tests/api` 为 594 passed、1 skipped；跳过项为仓库既有条件
  性测试，不是本阶段关闭门禁。最终全部 PostgreSQL 集成 `tests/integration` 为 130 passed。
- 最终 Frontend：ESLint 零 warning、TypeScript 7 + `vue-tsc`、生产 Build 通过；Vitest 5 files / 17
  tests，Playwright 6/6（含 Stage 8E 两种创建模式与 Stage 8D 兼容流程）。
- Ruff Format/Check（CI 正式范围 `backend tests scripts`）、mypy 224 files、Architecture、Table Owner、
  Secret Scan、Docs Check、Wheel Build 与 Stage 8E 新模块打包内容检查全部通过。
- OpenAPI/全部 JSON Schema 已确定性生成，Orval Client 已重新生成；Contract `--check` 与 Compatibility
  通过。Capability 安全收窄后的前后端 Lint/Type/Test/Build 证据均为新鲜结果。
- PostgreSQL 18.4：`0022 → 0021 → head`、`head → base → head`、最终 `alembic current` 为
  `20260821_0022 (head)`，`alembic check` 无新操作；Database/Import/Collection/Content/Jobs/Platform
  均包含在最终 130 个集成测试中。
- 批准 PNG 的 SHA-256 重新核对为
  `343E61427D6E94F5DC814A9040925F6BCEF3D8E493B2A2AA95062D1BAEFDCCE5`；1600×1000 桌面实现截图已
  人工检查，完整 Playwright 重跑已清理条件性临时截图，工作树没有提交这些验证产物。
- PR #104 的最终 Head `f0c8ba62a98e7a7c9cdc795c840d7912f46385f2` 为 25/25 checks 成功，
  0 个未解决 Review Thread；PR 转 Ready 后以普通 merge commit 合并，没有绕过 Branch Protection。
- 合并提交 `2c978b117118745b4fb3ab6efef31e7d3b1812a1` 的 `main` push 事件适用 24/24 checks 成功；
  `Audit PostgreSQL Regression` 只在 PR 事件适用，已包含在前述 PR 25/25 中。
- 合并后本地 `main` 新鲜验证：非数据库后端 594 passed / 1 skipped，PostgreSQL Integration 130 passed，
  Frontend Vitest 5 files / 17 tests、Playwright 6/6，Lint、TypeScript 7、`vue-tsc`、Build、Ruff、mypy
  224 files、Architecture、Table Owner、Secret、Docs、OpenAPI/Orval drift/compatibility 全部退出码 0。
- 合并后 PostgreSQL 18.4 Migration 再次执行 `0022 → 0021 → head` 与 `head → base → head`，最终
  `alembic current` 为 `20260821_0022 (head)`，`alembic check` 无新操作。

## 两阶段 Review

### 需求符合性 Review

- Stage 8E 两种模式、Excel/TikHub 集中列表、Batch→Run 关联、状态详情、OpenAPI/Orval/Vue 与批准 PNG
  视觉基线逐项对应；声音广场保持渠道无关，没有新增 TikHub 徽标/入口。
- Discovery 关键词只冻结在 Run/Scope；代码、Contract 与数据库没有新增 Discovery Pack/Plan 写入或
  Stage 8F 页面。没有扩入 Content UI、Provider Config/Secret 管理、Budget、认证或 Release。
- Router 只调用 Application Service；Collection HTTP 创建短事务 Job/Run/Scope，Worker 继续复用既有
  Provider Request/Attempt、Raw、Mapper、全局 Relevance、Candidate 和 Fenced Content Owner。
- Pydantic 固定公共结构、统一 Error Contract/request_id、Migration/Schema 与 Blueprint/API/部署说明一致。

### 代码质量 Review

- **重要，已修复并回归：** Capability HTTP 最初直接嵌入内部 Capability，泄露 Provider Operation 与
  分页策略；新增 PostgreSQL Red 后收窄为 `provider/platform/business operations`。
- **重要，已修复并回归：** 统一列表最初把整个 Run Snapshot 作为搜索文本，可能通过命中结果推断
  `secret_ref`/Base URL；新增 PostgreSQL Red 后只搜索公开一次性关键词、文件名、Run/Job ID。
- **重要，已修复并回归：** 从超过最近 100 条的 Batch 行发起补采时，抽屉可能不显示当前 Batch；新增
  Vitest Red 后按 ID 追加读取当前选择，仍不建立第二套 Batch 查询或 Stage 8F 配置能力。
- **兼容，已修复：** 完整回归发现既有 Recording Repository 未接受新增可空 `import_batch_id`，5 个旧
  Collection Execution 用例失败；更新 Fake 并证明旧触发方式继续传 `None`，完整回归恢复绿色。
- **已核实无需生产修改：** 停用 Provider Config 已由 Registry 关闭失败；Batch Detail 身份不一致已在
  `_fetch_detail_candidates` 的 Content 写入前拒绝。新增回归分别固定这两个既有安全边界。
- 事务、Fencing、Retry 新 Attempt、Deadline、资源关闭、Batch 来源复核、Content 幂等、Migration
  downgrade、查询参数绑定、Secret/错误响应与重复 Owner/Client/Mapper/Writer 均已复核；严重/重要问题
  当前清零。

# 文档影响

- Blueprint 17：把 Stage 8E 从旧“Batch/Content 上下文”更新为已确认的“采集运行中心独立发现 +
  Batch 补采”，并固化一次性 Discovery 关键词/Stage 8F 保存边界与集中运行列表。
- Blueprint 02/03/04/08：仅同步实际形成的 Run/Scope、Batch FK、HTTP/Job/Capability 当前事实。
- Blueprint 16：长期 Figma 规则不改；本次 PNG 例外只保存在 Change，并在 Stage 8E 当前事实处引用。
- `docs/API接口说明.md`、测试/部署说明：同步新增公开端点、受信边界、Worker/Migration 部署顺序。

# 交付

- 实现 Branch：`feature/stage8e-tikhub-supplement`
- 实现 Commit：`f0c8ba62a98e7a7c9cdc795c840d7912f46385f2`（`实现 Stage 8E TikHub 辅助补采`）
- 实现 PR：[#104](https://github.com/dingyuwen777/AIMA_UGC/pull/104)，已于 2026-08-21 正常合并
- Merge Commit：`2c978b117118745b4fb3ab6efef31e7d3b1812a1`
- Change 归档：`changes/archive/2026-08/CHG-20260821-stage8e-tikhub-supplement/CHANGE.md`
- 发布：未执行外部生产部署；数据库与应用部署/回滚顺序已在本 Change 和正式部署文档固化。
