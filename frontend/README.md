# AIMA_UGC 前端开发入口

这篇 README 用来回答：

- 当前到底有哪些页面和路由；
- 页面数据从哪里来；
- 改一个页面应该先改 Page、Store、Feature API 还是后端 Contract；
- 哪些文件是生成物，不能手改；
- Figma 页面应该怎样落到当前 Vue 代码；
- 改完要跑哪些测试。

精确 HTTP 字段由后端 Pydantic Contract、[`contracts/openapi/openapi.json`](../contracts/openapi/openapi.json) 和 `src/generated/api/` 维护。本文解释当前前端怎么组织和怎么改，不复制第二套接口 Schema。

---

## 1. 当前技术栈

```text
Vue 3
TypeScript
Vite
Vue Router
Pinia
Element Plus
ECharts
OpenAPI / Orval generated client
```

程序入口：

```text
src/main.ts
→ Vue App
→ Pinia / Router
→ App.vue
→ RouterView
```

路由唯一事实源：

- [`src/app/routes.ts`](src/app/routes.ts)

不要从菜单、截图或历史 Stage 文档猜当前页面。

---

## 2. 当前真实路由

| 路径 | 页面 | 代码入口 |
| --- | --- | --- |
| `/` | 首页兼容入口 | [`src/views/HomeView.vue`](src/views/HomeView.vue)，复用 `CollectionRuntimePage` |
| `/collection-runtime` | 采集运行中心 | [`src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue`](src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue) |
| `/collection-strategy` | 采集策略 | [`src/features/collection-strategy/pages/CollectionStrategyPage/CollectionStrategyPage.vue`](src/features/collection-strategy/pages/CollectionStrategyPage/CollectionStrategyPage.vue) |
| `/voice-plaza` | 声音广场 | [`src/features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue`](src/features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue) |

注意：采集运行中心目前仍在：

```text
features/import-batches/
```

这是页面从 Excel Import Batch 演进到 Excel/TikHub 统一运行中心、再加入统一 Data Import Campaign 后留下的目录名。不要在无关任务里为了“看起来更漂亮”重命名；真正重构时需同步路由、测试、导入路径和文档。

当前没有独立：

```text
analysis/
reports/
jobs/
settings/
dashboard/
```

页面。Analysis Run 当前在声音广场，Data Import Campaign 当前在采集运行中心；后端有对应 API/表不等于应该新建独立路由。

---

## 3. 前端数据调用链

当前固定：

```text
Page / 页面私有组件
→ Pinia Store / local state
→ Feature api.ts
→ src/generated/api/
→ HTTP
→ FastAPI
```

目的：避免

```text
页面到处直接 fetch
Store 自己拼 URL
前端复制后端 Request/Response Type
```

---

## 4. Page / Store / API / Generated Client 分别负责什么

### Page / Component

负责：

- 布局和交互；
- 调用 Store action；
- Loading / Error / Empty / Data；
- Drawer、Dialog、表单、筛选、按钮。

不负责：

- 手写业务 URL；
- 复制后端类型；
- 直接理解数据库字段；
- 实现 Cursor 签名；
- 复制 AI/Provider/历史写入业务规则。

### Store

负责：

- 列表/筛选；
- 当前详情；
- Cursor；
- 页面轮询；
- 提交后的刷新；
- 多组件共享的 loading/error/Job 状态。

不把页面 CSS 塞进 Store，也不缓存服务端事实替代 PostgreSQL。

### Feature API

`api.ts` 是 Feature 与 generated client 的薄边界：

```text
页面语义函数
→ generated client
```

允许：

- 组合生成 Client；
- 收敛 Feature 错误；
- 提供更符合页面语义的函数名。

不允许重新定义 HTTP Contract 或在前端复制后端状态机。

### Generated Client

```text
src/generated/api/
```

生成链：

```text
Pydantic Request/Response
→ FastAPI OpenAPI
→ contracts/openapi/openapi.json
→ Orval
→ src/generated/api/
```

**禁止手工修改。**

如果前端类型不对：

```text
后端 Contract 错
→ 改 Pydantic / Route / API Test / OpenAPI / 重新生成

后端 Contract 对，页面用错
→ 改 Feature api.ts / Store / Page
```

---

## 5. 当前三个业务 Feature

### 5.1 `features/import-batches`：采集运行中心 + 统一数据导入

主要文件：

```text
src/features/import-batches/
├─ api.ts
├─ format.ts
├─ store.ts
└─ pages/CollectionRuntimePage/
   └─ components/DataImportDialog.vue
```

当前承接：

- Excel Import Batch 兼容列表/历史状态；
- Excel/TikHub 统一运行列表与运行摘要；
- 一次性 TikHub Discovery；
- Import Batch 补采；
- Run/Batch 详情和状态；
- **单一“导入数据”入口**；
- 本地电脑显式多文件/文件夹选择；
- 管理员批准服务器目录浏览；
- Data Import Campaign 创建、预检、启动、进度、取消、失败重试与冲突查看；
- `source_kind=local_upload / server_path` 与 `ingestion_policy=standard_observation / historical_fill_only` 两维独立选择；
- Campaign 来源进入 Voice Plaza 的查询闭环。

当前页面主导入工作流调用 `/api/v1/data-import-*`；旧 `/api/v1/import-batches` 和 `/api/v1/historical-import-*` 由后端保留兼容，不在页面建立第二套入口。页面不实现 Historical Fill-Only 业务规则，只展示后端 Contract/状态并把用户选择提交给 Campaign。

TikHub Run 详情会读取生成 Client 中既有的 `scopes[].stop_reason`。当 Worker 返回 `provider_secret_unavailable` 时，页面显示固定的“Provider Secret 不可用，请联系管理员检查运行配置”提示；未知错误值保留机器原文以便结合 Run ID、Job ID 排障。页面不接收或展示 `secret_ref`、Secret 路径和 Secret 内容。

修改导航：

| 需求 | 先看 |
| --- | --- |
| 运行中心布局/按钮/Drawer | `pages/CollectionRuntimePage/` |
| 导入来源/策略/Campaign UI | [`pages/CollectionRuntimePage/components/DataImportDialog.vue`](src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue) + `api.ts` |
| 筛选、轮询、分页、详情状态 | `store.ts` |
| 后端接口调用 | `api.ts` |
| 时间/状态格式 | `format.ts` |
| API 字段/业务语义 | 后端 Pydantic Contract / Service |
| Historical Fill-Only/Chunk/账本 | 后端 Ingestion/Content Owner，前端不得复制 |

### 5.2 `features/collection-strategy`：采集策略

```text
src/features/collection-strategy/
├─ api.ts
├─ eligibility.ts
├─ presentation.ts
├─ store.ts
└─ pages/CollectionStrategyPage/
   ├─ CollectionStrategyPage.vue
   └─ components/
```

当前负责：

- 后端分页的 Keyword Pack 列表，以及供跨页配置引用的完整只读目录；
- 系统唯一的全局 Relevance Config；
- 周期 Collection Plan 的筛选、分页、创建、详情和启停；
- Capability 驱动的逐平台 Provider/Search Config，不在页面写死平台参数；
- 历史 Plan 空 Search Config 的兼容说明。

页面不直接运行 TikHub。保存 Plan/词包是修改配置事实，真正执行由 Scheduler 生成 Occurrence/Run/Job。

页面调用链保持为：

```text
CollectionStrategyPage / Feature Components
→ collection-strategy/store.ts
→ collection-strategy/api.ts
→ generated/api/client.ts
→ 当前后端 API
```

[`eligibility.ts`](src/features/collection-strategy/eligibility.ts) 是计划创建/重新启用资格的唯一前端 Owner；[`shared/collectionSearchConfig.ts`](src/shared/collectionSearchConfig.ts) 与 [`CollectionSearchConfigFields.vue`](src/shared/CollectionSearchConfigFields.vue) 是动态搜索字段和历史摘要的唯一 Owner。周期选择在 UI 中使用批准的受控预设，提交时仍转换为当前 Contract 的 `schedule_expr`；周期、平台和北京时间展示映射由 [`presentation.ts`](src/features/collection-strategy/presentation.ts) 维护，文档不复制第二套列表。

### 5.3 `features/voice-plaza`：声音广场 + 手动 Analysis Run

```text
src/features/voice-plaza/
├─ api.ts
├─ format.ts
├─ store.ts
└─ pages/VoicePlazaPage/
```

当前组合：

- Content 列表/详情；
- 平台/文本/时间/来源/Analysis 筛选；
- Analysis current/stale/pending；
- 显式选择内容并做 Analysis Run Preview；
- 创建手动 Analysis Run；
- 查看 Run 历史、真实进度、成功/失败/取消状态并取消活动 Run；
- 同一 Content Version 多轮 Analysis 结果的当前投影；
- 查看 AI 原判与查询层 `effective_relevance / relevance_source`；
- 对当前 Content Version 提交人工相关性复核/撤销复核；
- 创建正式 Excel Export；
- 查询 Export 状态、真实进度和下载 Artifact。

当前新版 Analysis Run 只开放显式选择 1—1000 条内容；query scope Run 没有作为当前页面能力开放。页面不负责 Planner/Shard/Current 选择规则，这些由后端 Analysis Domain、PostgreSQL 和 generated Contract 决定。

人工相关性复核通过 generated Client 调当前正式 API；Feature `api.ts` 只提供页面语义薄封装，不在前端复制 `relevant / irrelevant / inherit_ai` 的后端状态机或数据库规则。完整业务语义看 Analysis README 与后端 Contract。

注意三条不同能力：

```text
声音广场 Analysis Run
→ analysis.content-run-plan.v1
→ analysis.content-label.v1 Shard

声音广场 Excel Export
→ reporting.content-export-excel.v1

离线 Markdown / Word Report
→ backend/src/aima_ugc/platform/reporting/
→ 当前没有独立报告中心页面
```

---

## 6. App Shell、Shared 和全局样式

应用级：

```text
src/app/router.ts
src/app/routes.ts
src/app/layouts/
src/views/HomeView.vue
src/shared/
```

当前 App Shell 只展示已经有真实路由的入口：

```text
首页
声音广场
采集运行中心
采集策略
```

未来能力如果还没有正式页面，不以 disabled 或无效按钮占位；等真实能力形成后，再按“Feature → Page → Route → App Shell → Test”同步加入。

全局样式只放真正跨页面 Token/reset。当前 `src/shared/ui/` 提供页面头、按钮、代码内 SVG 图标和反馈 Banner；采集策略 KPI、表格、弹窗、抽屉和业务表单仍留在 Feature 内，不把业务规则塞进万能公共组件。

页面私有视觉优先留在 Page/Component，避免改一处全局 CSS 把多个页面一起破坏。

新增页面：

```text
确认产品/后端能力
→ 新建或扩展 Feature
→ Page
→ routes.ts
→ App Layout 导航（需要时）
→ Unit / Routes / E2E
```

只在菜单加一行不算完成页面能力。

---

## 7. Figma 与代码的边界

Figma 负责：

- 信息层级；
- 布局；
- 组件状态；
- 交互；
- 字号、间距、颜色等视觉 Token。

Figma 不负责：

- API 字段；
- Schema；
- Analysis taxonomy；
- Job 状态；
- Provider Capability；
- 权限/安全语义。

如果设计需要 Contract 没有的数据，必须回到后端确认正式能力变更，不长期保留 Mock 字段。

完整当前工作流：

[`../docs/guides/01_Figma与前端设计开发工作流.md`](../docs/guides/01_Figma与前端设计开发工作流.md)

---

## 8. 当前视觉基线

正式 Figma 设计资产正在逐步成为当前 AIMA 前端设计事实源；代码业务语义仍以当前 Contract/实现为准。早期已批准视觉参考的尺寸、哈希和采用原因仍保存在对应归档 Change 中；相关一次性二进制参考已于 2026-08-27 经用户授权从当前仓库删除，不再作为现行可访问资产。

Figma 正式接管某个页面/组件后，需要明确：

```text
Figma 负责哪些视觉/交互事实
Vue 哪些业务语义必须保持
组件/Token 哪些可以复用到后续页面
旧参考是否只保留历史证据
```

不要让旧 PNG、Figma 和代码长期成为三套平行视觉事实；也不要让 Figma 覆盖后端 Contract/业务规则。

---

## 9. Element Plus / TypeScript 当前兼容边界

当前锁定依赖以 [`package.json`](package.json) / lock 为准，不在本文长期复制可能漂移的精确版本号；需要版本事实时直接读取：

- [`frontend/package.json`](package.json)
- [`frontend/package-lock.json`](package-lock.json)
- [`.node-version`](../.node-version)

当前 `tsconfig` / typecheck 策略也以仓库文件为准。历史上 Stage 8C 曾暴露 Element Plus 类型声明与当时 TypeScript 工具链的兼容问题，因此普通页面任务禁止通过以下方式规避：

```text
静默升级依赖
skipLibCheck = true
降低 typecheck
```

这不等于永久禁止 Element Plus。后续确需调整依赖时走独立技术 Change，并重新验证 typecheck/unit/build/E2E。

---

## 10. HTTP Contract 变化流程

从仓库根：

```bash
uv run python scripts/contracts/generate.py
npm --prefix frontend run generate:api
uv run python scripts/contracts/generate.py --check
```

典型链：

```text
Pydantic Request/Response
→ FastAPI Route/Service
→ API/Contract Test
→ OpenAPI
→ Orval Client
→ Feature api.ts / Store / Page
→ Unit / E2E
```

检查 generated diff 是否符合预期，不能把大量意外生成差异直接提交。

---

## 11. Figma → Vue 推荐 Vertical Slice

```text
业务目标
→ 当前 Capability/Contract 调查
→ 页面信息结构 / Figma
→ 需要变化时先冻结 HTTP Contract
→ API/Contract Test
→ OpenAPI / generated Client
→ 后端与前端并行
→ Feature API / Store
→ Vue Page
→ Unit / E2E
→ 浏览器视觉验收
```

不采用：

```text
一次性生成全部未来页面
→ 再追着补后端
```

也不采用：

```text
先实现全部未来 API
→ 再决定页面怎么用
```

每次完成一个可以独立验收的纵切。

---

## 12. 本地运行

标准源码开发入口看仓库根 [`scripts/dev/frontend.py`](../scripts/dev/frontend.py) 与 [`../docs/02_环境运行与部署.md`](../docs/02_环境运行与部署.md)。直接执行 Vite 时仍可使用：

```bash
npm --prefix frontend run dev
```

Vite 当前监听/代理等精确配置看 [`vite.config.ts`](vite.config.ts)；不要在 README 复制容易漂移的端口/Host 作为唯一事实。

页面能打开不等于 PostgreSQL/Worker/异步 Job 正常。

---

## 13. 常见问题怎么定位

### 只改页面样式

```text
Page / Component
→ 必要时 shared token
→ Unit / E2E / 视觉核对
```

不要改 generated Client 或后端业务语义。

### 按钮提交数据不对

```text
Feature api.ts
→ generated Request Type
→ backend Pydantic Contract
```

Contract 不支持时走完整后端 Change。

### Data Import 卡住或进度异常

```text
DataImportDialog
→ Feature api.ts
→ generated data-import client
→ Campaign status/progress
→ historical discover/snapshot/import-chunk Job
→ Worker / Ingestion Repository
```

不要在前端根据文件数量/行数自行伪造百分比；发现阶段未知总量时允许不确定进度。

### 页面筛选结果不对

```text
Page input
→ Store filter
→ Feature api.ts
→ generated Client
→ API doc
→ 后端 Query Service / Repository
```

不要先在 Vue 做第二套业务过滤掩盖后端错误。

### AI 相关性与人工状态看起来不一致

```text
Content 当前版本
→ current Analysis Identity / AI 原判
→ effective_relevance / relevance_source
→ 人工相关性复核 API
→ 后端 relevance_reviews / Content Query
```

不要从当前页面筛选条件反推人工复核状态，也不要在前端自行计算一套“最终相关性”。

### Analysis Run / Export 一直处理中

```text
HTTP
→ Run / Export 父事实
→ Planner/Shard/Export jobs
→ Worker
→ 对应模块 README / PostgreSQL Appendix
```

---

## 14. 测试

当前 Unit：

```text
frontend/tests/
```

快速 Browser E2E：

```text
frontend/e2e/
frontend/playwright.config.ts
```

这组测试会 Mock `/api/v1/**`，用于快速验证页面、按钮、Drawer/Dialog、前端状态和常见 HTTP 返回，不作为真实后端链证明。

真实 Full-stack Browser Acceptance 当前由永久 Workflow 维护：

```text
frontend/e2e-fullstack/
frontend/playwright.fullstack.config.ts
tests/fullstack/
.github/workflows/fullstack.yml
```

当前目录实际包含：

```text
excel-import.spec.ts
collection-plan-search-config.spec.ts
manual-relevance-review.spec.ts
stage12-historical-analysis.spec.ts
```

因此真实 Full-stack 已不只验证 Stage 8F 的旧单文件 Excel 链；Stage 12 还有统一历史导入/Analysis Run 的真实 Browser/API/PostgreSQL/Worker 覆盖。具体每条场景以当前 spec 为准，不在 README 复制第二套断言。

Stage 8F 兼容 Excel 核心链仍是：

```text
Excel fixture
→ Browser 上传
→ Vue / generated client
→ FastAPI
→ Import Batch + Job
→ Worker
→ PostgreSQL Content
→ 采集运行中心完成
→ 查看入库内容
→ Voice Plaza 显示本批数据
```

Stage 12 当前真实 Full-stack 入口：

- [`frontend/e2e-fullstack/stage12-historical-analysis.spec.ts`](e2e-fullstack/stage12-historical-analysis.spec.ts)

普通 CI 不为这些验收调用真实付费 TikHub 或 LLM。

提交前常规前端检查：

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

完整测试环境可运行：

```bash
npm --prefix frontend run test:e2e:fullstack
```

永久 CI 通过 [`.github/workflows/fullstack.yml`](../.github/workflows/fullstack.yml) 建立隔离环境并执行真实链。完整能力矩阵和边界见：

[`../docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md`](../docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md)

这些前端测试仍不能替代 Job Fencing、Provider、Migration、容量或其他后端专项集成测试；各层验证继续各自证明真实边界。

---

## 15. 当前未实现的前端能力

当前没有：

- 登录/认证闭环；
- 独立 Analysis 管理中心（现有 Run 在声音广场）；
- 独立 Job 管理中心；
- 独立 Excel Export 管理中心；
- 正式 Word 报告中心；
- Monitoring/Alert/VOC/Ticket/Dashboard 页面。

后续是否实现、何时实现看：

[`../docs/roadmap/02_生产上线实施路线.md`](../docs/roadmap/02_生产上线实施路线.md)

---

## 16. 继续阅读

- API/Job/Frontend 长期边界：[`docs/blueprint/04_后端任务API与前端.md`](../docs/blueprint/04_后端任务API与前端.md)
- 人类可读 API：[`docs/03_API接口说明.md`](../docs/03_API接口说明.md)
- Figma/Design-to-Code：[`docs/guides/01_Figma与前端设计开发工作流.md`](../docs/guides/01_Figma与前端设计开发工作流.md)
- Collection 策略：[`docs/blueprint/08_采集策略与平台能力.md`](../docs/blueprint/08_采集策略与平台能力.md)
- AI：[`docs/appendix/07_AI舆情打标与分析实现.md`](../docs/appendix/07_AI舆情打标与分析实现.md)
- Data Import：[`docs/appendix/08_数据入口与统一入库实现.md`](../docs/appendix/08_数据入口与统一入库实现.md)
- Stage 12 软件与生产门禁：[`docs/roadmap/03_4000万历史数据迁移实施方案.md`](../docs/roadmap/03_4000万历史数据迁移实施方案.md)
- Excel Export：[`docs/appendix/06_Excel统一数据导出与离线调试.md`](../docs/appendix/06_Excel统一数据导出与离线调试.md)
- Stage 8F 能力矩阵与真实验收：[`docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md`](../docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md)
- 后续阶段/Production Go-Live：[`docs/roadmap/02_生产上线实施路线.md`](../docs/roadmap/02_生产上线实施路线.md)
