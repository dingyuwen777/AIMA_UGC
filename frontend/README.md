# AIMA_UGC 前端开发入口

这篇 README 的目标不是介绍 Vue 是什么，而是让第一次进入前端代码的人能快速回答：

- 当前到底有哪些页面和路由；
- 页面数据从哪里来；
- 改一个页面应该先改 Page、Store、Feature API 还是后端 Contract；
- 哪些文件是生成物，不能手改；
- 改完要跑哪些测试。

精确 HTTP 字段由后端 Pydantic Contract、`contracts/openapi/openapi.json` 和 `src/generated/api/` 维护。本文负责解释当前代码怎么组织和怎么改，不复制第二套接口 Schema。

## 1. 当前技术栈和启动入口

当前前端是：

```text
Vue 3
+ TypeScript
+ Vite
+ Vue Router
+ Pinia
+ OpenAPI / Orval 生成 Client
```

程序入口：

```text
src/main.ts
→ 创建 Vue App
→ 安装 Pinia / Router
→ App.vue
→ RouterView / 当前页面
```

路由事实源：

```text
src/app/routes.ts
```

不要从菜单文案、截图或历史 Stage 文档猜当前有哪些页面。

## 2. 当前真实路由

`src/app/routes.ts` 当前只注册四个路由：

| 路径 | 页面 | 真实代码入口 |
| --- | --- | --- |
| `/` | 首页兼容入口 | `src/views/HomeView.vue`，内部直接复用 `CollectionRuntimePage` |
| `/collection-runtime` | 采集运行中心 | `src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue` |
| `/collection-strategy` | 采集策略 | `src/features/collection-strategy/pages/CollectionStrategyPage/CollectionStrategyPage.vue` |
| `/voice-plaza` | 声音广场 | `src/features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue` |

这里有一个容易误解的历史目录名：**采集运行中心当前仍位于 `features/import-batches/`**。这是因为页面最早从 Excel Import Batch 演进而来，后续已经扩展为 Excel/TikHub 统一运行中心。不要为了“目录看起来更漂亮”在无关任务里随手重命名；如果未来确实要改 Feature 名，需要同步路由、测试、导入路径和文档，并按独立重构处理。

当前代码没有独立的 `analysis`、`reports`、`jobs`、`settings`、`dashboard` 页面目录。后端存在 Analysis/Export/Job API，不等于前端已经为每一种能力建立独立页面。

## 3. 先理解前端的数据调用链

当前业务页面遵循：

```text
Page / 页面私有组件
→ Pinia Store
→ Feature api.ts
→ src/generated/api/
→ HTTP
→ FastAPI
```

职责分开是为了避免三种常见问题：

```text
页面里到处直接 fetch
Store 自己拼 URL
前端手写一套和后端不同的 Request/Response Type
```

### 3.1 Page / Component

负责：

- 页面布局和交互；
- 调用 Store action；
- 展示 loading / error / empty / data；
- Drawer、表单、筛选、按钮等用户行为。

不负责：

- 手写 `/api/v1/...` URL；
- 复制后端类型；
- 解析数据库字段；
- 自己实现 Cursor 签名或后端业务规则。

### 3.2 Store

每个 Feature 的 `store.ts` 负责页面状态和业务交互编排，例如：

- 当前列表和筛选条件；
- 当前详情；
- 下一页 Cursor；
- 页面轮询；
- 提交后的刷新；
- loading/error 状态。

Store 不应该复制生成 Client，也不应该把页面 CSS/布局逻辑塞进状态层。

### 3.3 Feature API

每个 Feature 的 `api.ts` 是页面与生成 Client 之间的薄边界：

```text
Feature 业务调用
→ api.ts
→ generated client
```

这里可以做：

- 组合生成 Client 调用；
- 把生成层异常收敛成 Feature 能处理的错误；
- 提供更符合当前页面语义的函数名。

这里不能重新定义 HTTP Contract。

### 3.4 Generated Client

目录：

```text
src/generated/api/
```

它来自：

```text
后端 Pydantic Request/Response
→ FastAPI OpenAPI
→ contracts/openapi/openapi.json
→ Orval
→ src/generated/api/
```

**禁止手工修改生成目录。**

如果前端类型“不对”，先判断：

```text
后端 Contract 本身不对？
→ 改后端 Pydantic + API Test + OpenAPI，再重新生成

后端 Contract 正确，只是页面使用方式不对？
→ 改 Feature api.ts / store.ts / Page
```

## 4. 三个当前业务 Feature

### 4.1 `features/import-batches`：采集运行中心

当前主要文件：

```text
src/features/import-batches/
├─ api.ts
├─ format.ts
├─ store.ts
└─ pages/CollectionRuntimePage/
```

它当前不只是 Excel Import 页面，而是承接：

- Excel Import Batch 列表和上传；
- Excel/TikHub 统一运行列表；
- 运行摘要；
- 一次性 TikHub Discovery；
- Import Batch 补采；
- Run/Batch 详情和状态展示。

对应后端主要接口见 `docs/API接口说明.md` 的 Import Batch、Collection Run、Collection Runtime 部分。

常见修改：

| 要改什么 | 先看 |
| --- | --- |
| 页面布局/按钮/Drawer | `pages/CollectionRuntimePage/` |
| 筛选、轮询、分页、详情状态 | `store.ts` |
| 调用哪个后端接口 | `api.ts` |
| 时间、状态等展示格式 | `format.ts` |
| API 字段/业务语义 | 后端 Contract / Route，不在前端私造字段 |

### 4.2 `features/collection-strategy`：采集策略

当前主要文件：

```text
src/features/collection-strategy/
├─ api.ts
├─ store.ts
└─ pages/CollectionStrategyPage/
```

页面负责当前已经落地的：

- Keyword Pack；
- 全局 Relevance Config；
- 周期 Collection Plan；
- Plan 启停和当前配置展示。

它不直接运行 TikHub。保存 Plan/词包只是修改配置事实；真正执行由 Scheduler 到期创建 Occurrence/Run/Job。

常见修改：

| 要改什么 | 先看 |
| --- | --- |
| 页面区域、表单、交互 | `pages/CollectionStrategyPage/` |
| 配置加载/保存状态 | `store.ts` |
| Keyword Pack/Relevance/Plan HTTP 调用 | `api.ts` |
| 增加新的 Plan 业务字段 | 先改后端 Contract/领域规则，再重新生成 Client |

### 4.3 `features/voice-plaza`：声音广场

当前主要文件：

```text
src/features/voice-plaza/
├─ api.ts
├─ format.ts
├─ store.ts
└─ pages/VoicePlazaPage/
```

当前页面组合：

- Content 列表和详情；
- 平台/文本/时间/Analysis 等筛选；
- 当前 Analysis 状态展示；
- 用户显式提交 AI Analysis；
- 创建正式 Excel Export；
- 查询 Export 状态并下载 Artifact。

这里要特别区分：

```text
“声音广场导出 Excel”
→ 正式 reporting.content-export-excel.v1 Job

“离线 Word 舆情报告”
→ backend/src/aima_ugc/platform/reporting/
→ 当前不是声音广场里的独立报告页面
```

常见修改：

| 要改什么 | 先看 |
| --- | --- |
| 列表/详情布局 | `pages/VoicePlazaPage/` |
| 过滤、选择、Analysis/Export 状态 | `store.ts` |
| Content/Analysis/Export HTTP | `api.ts` |
| 展示格式 | `format.ts` |
| Analysis 分类规则 | 后端 Prompt/Analysis，不在 Vue 里复制 taxonomy |

## 5. App Shell、路由和全局样式

应用级代码：

```text
src/app/router.ts        创建 Router
src/app/routes.ts        路由表事实源
src/app/layouts/         应用级布局
src/views/HomeView.vue   根路由兼容入口
src/shared/              跨 Feature 的真正共享代码
```

全局样式只放真正跨页面的 Token/reset。页面私有视觉优先留在对应 Page/Component 中，避免一个全局 CSS 修改把三个业务页面同时破坏。

如果新增页面：

```text
先确认后端/产品能力已经存在
→ 新建或扩展 Feature
→ 增加页面
→ 在 routes.ts 注册
→ 如需导航，在 App Layout 同步入口
→ 补 routes/unit/E2E
```

不要只在左侧菜单加一行就认为页面能力已经完成。

## 6. Figma / 截图与代码的边界

Figma 负责视觉和交互设计，不是后端数据事实源。

设计稿可以决定：

- 信息层级；
- 布局；
- 组件状态；
- 交互；
- 字号、间距、颜色等视觉 Token。

设计稿不能自行决定：

- 新 API 字段；
- 数据库 Schema；
- Analysis taxonomy；
- Job 状态；
- Provider Capability；
- 权限/安全语义。

如果设计要求的新数据当前 Contract 没有，先回到后端事实确认是否需要正式能力变更，而不是在前端 Mock 一个字段后长期保留。

完整工作流见 `docs/guides/` 中的前端/Figma 指南。

## 7. 公共 HTTP Contract 变化后的正确流程

从仓库根执行：

```bash
uv run python scripts/contracts/generate.py
npm --prefix frontend run generate:api
uv run python scripts/contracts/generate.py --check
```

实际开发还需要检查生成差异是否符合预期，不能把“大量意外 generated diff”直接提交。

典型链路：

```text
改 Pydantic Request/Response
→ 改 FastAPI Route/Service
→ API/Contract 测试
→ 生成 OpenAPI
→ Orval 生成 Client
→ 修改 Feature api.ts/store/Page
→ 前端 Unit/E2E
```

## 8. 本地运行

后端在 `127.0.0.1:8090` 启动后，从仓库根执行：

```bash
npm --prefix frontend run dev
```

Vite 当前开发服务器监听 `127.0.0.1:5173`，并把 `/api` 与 `/health` 代理给后端。精确配置以 `frontend/vite.config.ts` 为准。

本地运行不能替代后端 PostgreSQL/Worker 集成验证；页面能打开也不等于异步 Job 已正确执行。

## 9. 改代码时怎么快速定位

### 改页面样式，但不改业务

```text
目标 Page / Component
→ 必要时 shared token
→ 对应 Vitest / Playwright
```

不要改 generated client、Store 业务语义或后端 Contract。

### 改一个按钮提交的数据

```text
先看 Feature api.ts
→ 看 generated client 的真实 Request Type
→ 回到 backend/src/aima_ugc/contracts/http.py 确认 Contract
→ 如果 Contract 不支持，走完整后端 Contract Change
```

### 页面筛选结果不对

```text
Page 当前输入
→ Store 保存的 filter
→ Feature api.ts 传参
→ generated client
→ docs/API接口说明.md
→ 后端 Query Service / Repository
```

不要先在页面做第二次业务过滤来掩盖后端查询错误。

### Analysis/Export 一直处理中

前端只展示 Job/业务状态。排障应继续到：

```text
HTTP API
→ PostgreSQL jobs / analysis_content_requests / reporting_data_exports
→ Worker
→ 对应模块 README / PostgreSQL 附录
```

## 10. 测试

当前前端 Unit 事实入口在 `frontend/tests/`：

```text
collection-runtime.spec.ts
collection-strategy.spec.ts
import-batches-api.spec.ts
import-batches-store.spec.ts
routes.spec.ts
voice-plaza.spec.ts
```

E2E 入口在 `frontend/e2e/`。

提交前执行：

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

这些测试证明前端逻辑和固定 HTTP Contract 的交互；它们不能替代后端 API、PostgreSQL、Worker、Fencing、Provider 或 Migration 集成测试。

## 11. 当前限制

当前前端已经有三类业务界面：采集运行中心、采集策略、声音广场；根 `/` 只是复用采集运行中心的兼容入口。

当前没有：

- 登录/认证页面；
- 独立 Analysis 管理中心；
- 独立 Job 管理中心；
- 独立 Excel Export 管理中心；
- 正式 Word 报告中心；
- Stage 9 Monitoring/Alert/Dashboard 页面。

不要根据后端已有表或 API 推导这些页面已经实现。

## 12. 继续阅读

- 当前前后端/API/Job 边界：`docs/blueprint/04-后端任务API与前端.md`
- 人类可读 API：`docs/API接口说明.md`
- 前端/Figma 工作流：`docs/guides/`
- 采集策略实现：`docs/blueprint/08-采集策略与平台能力.md`
- AI：`docs/appendix/AI舆情打标与分析实现.md`
- Excel Export：`docs/appendix/Excel统一数据导出与离线调试.md`
