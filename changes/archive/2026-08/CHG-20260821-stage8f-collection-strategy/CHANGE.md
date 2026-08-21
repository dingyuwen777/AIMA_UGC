---
schema: rvc-change/v1
id: "CHG-20260821-stage8f-collection-strategy"
title: "Stage 8F 采集策略配置与整体集成"
level: L3
status: done
owner: "codex"
branch: "feature/stage8f-collection-strategy"
created: 2026-08-21
updated: 2026-08-21
depends_on: []
affected_areas:
  - "system"
  - "collection"
  - "api"
  - "frontend"
  - "contracts"
  - "docs"
affected_paths:
  - "backend/src/aima_ugc/modules/system"
  - "backend/src/aima_ugc/modules/collection"
  - "backend/src/aima_ugc/adapters/persistence/postgres"
  - "backend/src/aima_ugc/bootstrap"
  - "backend/src/aima_ugc/contracts/http.py"
  - "contracts/openapi/openapi.json"
  - "frontend"
  - "tests"
  - "docs"
contracts:
  - "HTTP Pydantic → OpenAPI → Orval：Keyword Pack、全局 Relevance、Collection Plan"
data_changes:
  - "无 Schema 变化；复用 keyword_packs/global_relevance_config/collection_plans 现有表"
---

# 目标

把 Stage 7 已有的 Keyword Pack、系统全局 Relevance、Collection Plan 与 Scheduler 机器能力产品化为
`/collection-strategy` 业务工作台。用户可保存 Discovery 词包、切换全局唯一 Relevance、创建和查询
周期采集 Plan；前端只调用 Pydantic → OpenAPI → Orval 生成 Client，Plan 继续由既有 Scheduler/Worker
执行，不建立平行配置、Job 或 Provider 调用链。

# 成功标准

- [x] `采集策略` 作为一级业务导航进入 App Shell，不归入“管理员页面”，保持现有页面路由兼容。
- [x] Keyword Pack 支持列表、创建、详情、增补关键词和启停；不硬删除历史引用，不发明 Alias 关系。
- [x] 系统全局 Relevance 继续只有一份配置，只能引用已启用且至少有一个有效关键词的 Pack；Plan 无覆盖字段。
- [x] Collection Plan 支持列表、详情、创建和启停；平台必须选择既有启用 Provider Config，业务参数只接受
  当前 Capability/首版固定策略可表达的字段，不接受任意 Provider JSON、Secret 或私有分页状态。
- [x] Plan 启停与 Scheduler 并发使用数据库条件更新；失效调度 cursor 不会产生旧版本 Occurrence。
- [x] 页面 KPI、三个配置页签、Loading/Empty/Error、Plan 新建抽屉和详情均来自真实 HTTP 数据。
- [x] Pydantic HTTP Contract、固定 OpenAPI、Orval Client、Feature API/Pinia/Vue、Contract/API/PostgreSQL/
  Frontend/E2E 测试和文档形成同一闭环。
- [x] 当前 `20260821_0022` Schema 已足够时不制造 Migration；若实现事实推翻该判断，必须先重新过数据门禁。
- [x] 两阶段 Review、最终 Head 全部门禁、PR、正常合并、归档及合并后 main 新鲜验证完成。

# 范围

- System Keyword Catalog 的页面所需查询/启停写入口。
- 全局 Relevance 查询/切换页面，复用现有单例配置与冻结规则。
- Collection Plan 的列表/详情/创建/启停 Application Service 与 HTTP Contract。
- 既有 Provider Capability/Config 只读选择；不增加 Provider Config 写入口。
- `/collection-strategy` Feature API、Pinia Store、Vue SFC、App Shell 一级导航与跨页面 E2E。
- OpenAPI/Orval 生成物、受影响 Blueprint/API/测试说明和本 Change 的一次性 PNG 视觉基线。

# 非目标

- 不进入 Stage 9，不新增正式洞察、报告、认证、Release 或其他业务页面。
- 不实现 Provider Config/Secret 写入、轮换或明文读取；不把 Provider 私有 endpoint/cursor/page/search_id 暴露给前端。
- 不实现请求/金额 Budget、Cost Guard、ETA、自动 fallback 或真实付费 Provider Probe。
- 不实现 Discovery/Relevance Alias、同义词、排除词或 Plan 级 Relevance 覆盖。
- 不硬删除 Keyword Pack、Keyword、Plan、Occurrence 或历史 Run；不改写已发布 Migration。
- 不允许任意原地编辑已建 Plan 的平台、词包、Cron 或策略；本次只创建和启停，后续如需编辑必须单独
  冻结 `schedule_version`、并发、Occurrence 和历史展示语义。
- 不开发与批准视觉基线无关的管理页，不引入新 CSS 框架或手写平行 HTTP Client。

# 必须保持不变

- PostgreSQL 是 Keyword/Relevance/Plan 唯一业务事实；词包文件和前端状态不成为运行时事实源。
- Discovery 只决定搜索输入；全局 Relevance 决定所有来源 Mapper 后的准入，Run 创建时冻结配置快照。
- `Scheduler → collection.run.v1 Job → Worker → Provider Request/Attempt → Raw → Mapper → Relevance →
  ContentIngestionService` 是唯一周期采集生产链。
- Plan 继续绑定稳定 `provider_config_id` 与真实 Keyword Pack FK；Secret 不进 Contract、Plan config、Job、日志或响应。
- 现有 `/collection-runtime`、`/voice-plaza`、Stage 8B Keyword/Relevance API 与生成 Client 的合法行为保持兼容。
- Vue 继续使用现有 SFC scoped style、设计 Token、Feature API/Pinia/Orval 边界；未来 Figma 重做只替换视觉层。
- Windows 本地开发与未来 Linux 部署使用同一 Contract、Cron/时区语义和路径无关实现。

# 关键决策

## 用户已确认

1. `采集策略` 是一级业务工作台，不属于“管理员页面”。
2. Stage 8F 保存可复用 Discovery 词包并由 Plan 引用；Stage 8E 一次性 Discovery 关键词仍只冻结到单次 Run。
3. Relevance 为系统全局唯一配置，适用于 Excel、TikHub 及以后所有采集来源；Plan 不允许覆盖。
4. 用户于 2026-08-21 批准 `docs/assets/stage8f/collection-strategy-prototype.png` 作为一次性 PNG 视觉基线，
   原图尺寸 `1585×992`，SHA-256 `6C80AE8235F5EEE91DB94E7FE738683D91C8493EBB5B81A24801A4859D61609B`。
   这是对 Blueprint 16 Figma-first 的 Change 级例外；未来 Figma 重新生成前端代码时，只替换组件/样式，
   保持 route、Pydantic/Orval Contract、Feature API/Store、三个页签和业务语义兼容。
5. Stage 8F 首版只支持周期 Cron Plan；原型中的“单次运行”移除。一次性主动发现继续由 Stage 8E
   `discovery` 模式承担，避免“保存配置”产生意外 TikHub 费用或建立重复入口。

## L3 方案比较与采用方案

- 方案 A（采用）：复用现有表和 Owner Repository，补列表/启停/创建 Application Service；不做硬删除或任意
  Plan 编辑。优点是历史 Run/Occurrence 与词包版本可审计、无需 Migration、风险最小。
- 方案 B（不采用）：为页面新建配置表或第二套 Scheduler/Job。会制造双事实源和重复运行链，违反 Blueprint。
- 方案 C（延期）：允许原地编辑 Plan 并递增 `schedule_version`。需要明确编辑并发、旧 cursor、已生成 Occurrence、
  审计与 UI 提示；当前批准原型没有编辑操作，不为未来可能需要而扩大 Contract。

## Migration、部署与回滚

- 当前结论：复用 `keyword_packs/keywords/keyword_pack_items/global_relevance_config/collection_plans` 及关联表，
  Migration Head 保持 `20260821_0022`；不为形式新增 Revision。
- 部署：应用与生成前端静态资源按现有顺序部署；既有 API/Worker/Scheduler 均需使用同一最终镜像版本。
- 回滚：回滚应用/前端 Commit 即可；新增配置数据继续是旧代码可读的既有表事实。回滚不删除用户已保存的 Pack/Plan。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败测试或说明测试例外
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得最终 Head、本地验证、PR/CI、正常合并及合并后 `main` 新鲜验证证据

# 验证

## 计划

- [Contract Red] → `contracts/http.py`、Contract/API 测试 → 固定 Pack/Relevance/Plan 请求响应和统一错误。
- [PostgreSQL Red] → Keyword/Planning Repository 集成测试 → 证明列表、启停、并发/版本与 FK 校验。
- [Backend Green] → Owner Repository + Stage 8F Application Service + Router → 短事务配置，不执行 Provider/Job。
- [Generation Green] → OpenAPI/Orval → 生成 TypeScript Client，无手工生成物差异。
- [Frontend Red/Green] → App Shell + Feature API/Store/Vue/Vitest/Playwright → 真实三个页签与创建/查询行为。
- [Review/门禁] → 需求符合性、代码质量、PostgreSQL 18、全仓适用 CI、PR 与 main 验证。

## 新鲜证据

- 初始基线为 `b0c658061303294d3124b34bde028791c6464c72`；报告视觉变更合并后，本分支已安全快进到
  `38ea961a5f3dfbd84f5f4e6fa9aeb5153b8f1018`，该 `main` 无开放 PR 且现有 workflow 全部成功。
- `rvc status` 初始无 Active Change；实施期间只建立本 L3 Change，归档前再次确认进行中 Change 为 0。
- 实施时 Migration Head 文件为 `20260821_0022_stage8e_collection_run_batch.py`；最终已用 PostgreSQL 18.4
  完成 Migration 生命周期验证，未使用历史 CI 替代。
- 工作区有用户未跟踪 `env.local`；本 Change 不读取、不修改、不暂存该文件。
- 初始 Backend Red：Contract/API 测试因缺少 `aima_ugc.modules.collection.strategy_http` 正确失败；
  初始 Frontend Red：缺少 Collection Strategy Feature API 与 `/collection-strategy` Route 正确失败。
- Review 回归 Red：PostgreSQL 测试分别证明 Plan UUID 搜索缺失、响应掩盖异常持久化策略；Vitest 证明
  offset Contract 尚未形成页面翻页。Green 后 PostgreSQL 4/4、目标 Frontend 9/9，失败测试均保留。
- 最终 Backend：Ruff 426 files、mypy 229 source files；Unit 527 passed/2 skipped、Contract 54 passed、
  API 27 passed；OpenAPI generation/compatibility、Architecture、Table Owner、Secret、Docs 全部通过。
- 最终 PostgreSQL 18.4：Collection/Content/Keyword/Provider 相关 Integration 107 passed；
  `20260821_0021 → head`、`base → head`、两次 `alembic current/check` 通过；往返后 Stage 8F 4 passed。
- 最终 Frontend：Orval 8.24.0 重新生成；ESLint、TS7、vue-tsc、22 Vitest、production build 与全部
  8 Playwright E2E 通过。视觉基线文件已检查为 `1585×992`、1,187,411 bytes。
- PR `#110` 最终 Head `9d7d1f9453ebf4ffbb2a17d5ae9ec0232178d275` 的 24/24 GitHub check-run 全部成功，
  无 Review 意见，GitHub 判定 `MERGEABLE / CLEAN`；PR 已于 2026-08-21 正常合并。
- Merge Commit `d5573f7e3114ffbdc2a5ebe0fcea701a7b7c44c7` 的合并后本地验证：Contract/API 8 passed，
  OpenAPI Drift、Architecture、Table Ownership、Secret、Docs、Frontend ESLint/TS7/vue-tsc、22 Vitest 与 build 通过。
- 同一 Merge Commit 在 `main` 新触发的 10 个 GitHub workflow、23 个 check-run 全部成功，包含 PostgreSQL 18、
  Windows、Unit、Quality 与 Contract/Platform 门禁；本地 `main` 与 `origin/main` 均指向该提交。

# 两阶段 Review

## 需求符合性

- 成功标准逐项满足；只实现保存 Discovery Pack、系统全局 Relevance 与周期 Collection Plan。
- 没有实现 Stage 8C/8E 的重复入口或 Stage 9；没有“单次运行”、Plan 级 Relevance、Provider Secret
  写入、Budget/Cost Guard、自动 Provider 调用或平行 Job/Repository/Client。
- 保存配置只写既有 PostgreSQL 父事实；Stage 8E 一次性 Discovery 与既有 Scheduler/Worker 链保持唯一。
- Pydantic、固定 OpenAPI、Orval、Feature API/Pinia/Vue 和长期文档保持一致；Migration Head 不变。

## 代码质量

- 修复 E2E 非唯一文本定位，避免视觉区域重复文案造成伪失败。
- 修复 PostgreSQL 测试遗漏 `collection_plans` 清理造成的跨用例污染。
- 补 Plan 名称/UUID 一致搜索与前端 offset 分页，避免 UI 承诺与 Repository 行为不一致。
- 响应不再硬编码并掩盖数据库 Plan 策略；持久化事实违反首版策略时统一 500 fail closed。
- Pack/Relevance/Plan 更新使用父行锁与 `schedule_version` fencing；重启调度不补跑停用区间。
- Router 无 SQL/Provider 调用，Service 使用短事务，Secret 不进 Contract/Plan/Job/日志/响应。
- 严重/重要问题已清零；未引入依赖、Schema、Migration 或无关重构。

# 文档影响

- Blueprint 17：Stage 8F 当前实现与 Stage 8 总体收口。
- Blueprint 04/08：只同步新增公开配置 Contract、Plan/Scheduler 当前产品化边界。
- Blueprint 16：长期 Figma 规则不改；PNG 例外只记录于本 Change，并由 Stage 8F 当前事实引用。
- `docs/API接口说明.md`、测试/部署说明：只同步实际新增端点、受信部署边界和验证命令。

# 交付

- Commit：`481424cb97015a51f93d4c1bcc9b56cbd04324c1`（正式实现）、
  `9d7d1f9453ebf4ffbb2a17d5ae9ec0232178d275`（最终交付记录）
- PR：`#110` `https://github.com/dingyuwen777/AIMA_UGC/pull/110`（已正常合并）
- Merge Commit：`d5573f7e3114ffbdc2a5ebe0fcea701a7b7c44c7`
- 发布：不操作外部生产；交付仓库代码、生成物、部署/回滚说明和验证证据。
