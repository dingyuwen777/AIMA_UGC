# AIMA_UGC 前端开发入口

这篇 README 用来回答：

- 当前到底有哪些页面和路由；
- 页面数据从哪里来；
- 改一个页面应该先改 Page、Store、Feature API 还是后端 Contract；
- 哪些文件是生成物，不能手改；
- Figma 页面应该怎样落到当前 Vue 代码；
- 改完要跑哪些测试。

精确 HTTP 字段由后端 Pydantic Contract、`contracts/openapi/openapi.json` 和 `src/generated/api/` 维护。本文解释当前前端怎么组织和怎么改，不复制第二套接口 Schema。

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

```text
src/app/routes.ts
```

不要从菜单、截图或历史 Stage 文档猜当前页面。

---

## 2. 当前真实路由

| 路径 | 页面 | 代码入口 |
| --- | --- | --- |
| `/` | 首页兼容入口 | `src/views/HomeView.vue`，复用 `CollectionRuntimePage` |
| `/collection-runtime` | 采集运行中心 | `src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue` |
| `/collection-strategy` | 采集策略 | `src/features/collection-strategy/pages/CollectionStrategyPage/CollectionStrategyPage.vue` |
| `/voice-plaza` | 声音广场 | `src/features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue` |

注意：采集运行中心目前仍在：

```text
features/import-batches/
```

这是页面从 Excel Import Batch 演进到 Excel/TikHub 统一运行中心留下的目录名。不要在无关任务里为了“看起来更漂亮”重命名；真正重构时需同步路由、测试、导入路径和文档。

当前没有独立：

```text
analysis/
reports/
jobs/
settings/
dashboard/
```

页面。后端有对应 API/表，不等于已经有独立前端页面。

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
- Drawer、表单、筛选、按钮。

不负责：

- 手写业务 URL；
- 复制后端类型；
- 直接理解数据库字段；
- 实现 Cursor 签名；
- 复制 AI/Provider 业务规则。

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

不允许重新定义 HTTP Contract。

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

### 5.1 `features/import-batches`：采集运行中心

主要文件：

```text
src/features/import-batches/
├─ api.ts
├─ format.ts
├─ store.ts
└─ pages/CollectionRuntimePage/
```

当前承接：

- Excel Import Batch 列表和上传；
- Excel/TikHub 统一运行列表；
- 运行摘要；
- 一次性 TikHub Discovery；
- Import Batch 补采；
- Run/Batch 详情和状态。

修改导航：

| 需求 | 先看 |
| --- | --- |
| 页面布局/按钮/Drawer | `pages/CollectionRuntimePage/` |
| 筛选、轮询、分页、详情状态 | `store.ts` |
| 后端接口调用 | `api.ts` |
| 时间/状态格式 | `format.ts` |
| API 字段/业务语义 | 后端 Contract / Service |

### 5.2 `features/collection-strategy`：采集策略

```text
src/features/collection-strategy/
├─ api.ts
├─ store.ts
└─ pages/CollectionStrategyPage/
```

当前负责：

- Keyword Pack；
- 全局 Relevance Config；
- 周期 Collection Plan；
- Plan 启停和配置展示。

页面不直接运行 TikHub。保存 Plan/词包是修改配置事实，真正执行由 Scheduler 生成 Occurrence/Run/Job。

### 5.3 `features/voice-plaza`：声音广场

```text
src/features/voice-plaza/
├─ api.ts
├─ format.ts
├─ store.ts
└─ pages/VoicePlazaPage/
```

当前组合：

- Content 列表/详情；
- 平台/文本/时间/Analysis 筛选；
- Analysis current/stale/pending；
- 显式提交 AI Analysis；
- 创建正式 Excel Export；
- 查询 Export 状态和下载 Artifact。

注意两条不同能力：

```text
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

当前 App Shell 只展示已经有真实路由且属于公司内网 V1 的入口：

```text
首页
声音广场
采集运行中心
采集策略
```

未来能力如果还没有正式页面，不以 disabled 或无效按钮占位；等真实能力形成后，再按“Feature → Page → Route → App Shell → Test”同步加入。

全局样式只放真正跨页面 Token/reset。

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

正式 Figma 设计资产尚未完全替代早期已批准视觉参考，仓库当前仍保留：

```text
docs/assets/stage8c/collection-runtime-center-prototype.png

docs/assets/stage8d/voice-plaza-list-reference.jpg
docs/assets/stage8d/voice-plaza-detail-reference.jpg

docs/assets/stage8e/tikhub-supplement-centralized-runs-prototype.png
```

这些图片是页面视觉演进证据，不是长期 API/业务事实。

未来正式 Figma Frame 建立后，需要明确：

```text
Figma 接管哪些视觉/交互
Vue 哪些业务语义保持
旧 PNG 是否只作历史参考
```

不要让 PNG、Figma 和代码长期成为三套平行事实。

---

## 9. Element Plus / TypeScript 7 当前兼容边界

当前锁定依赖以 `package.json` / lock 为准，目前包括：

```text
element-plus = 2.14.4
@typescript/native = TypeScript 7.0.2
```

当前：

```text
skipLibCheck = false
```

Stage 8C 曾实际验证：在这组依赖下，直接使用部分 Element Plus 类型声明会暴露 TypeScript 7 兼容问题。

因此禁止为了页面任务：

```text
静默升级依赖
skipLibCheck = true
降低 typecheck
```

这不等于永久禁止 Element Plus。

如果后续页面确实需要系统性使用：

```text
独立技术 Change
→ 核对当时版本兼容性
→ 必要时更新 package + lock
→ typecheck / unit / build / E2E
→ 再扩展页面
```

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

后端在 `127.0.0.1:8090` 启动后：

```bash
npm --prefix frontend run dev
```

Vite 当前监听 `127.0.0.1:5173`，并代理 `/api`、`/health` 到后端。精确配置看 `vite.config.ts`。

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

### Analysis / Export 一直处理中

```text
HTTP
→ jobs
→ analysis_content_requests / reporting_data_exports
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

Stage 8F 真实 Full-stack Browser Acceptance：

```text
frontend/e2e-fullstack/
frontend/playwright.fullstack.config.ts
tests/fullstack/
.github/workflows/stage8f-fullstack.yml
```

它使用隔离 PostgreSQL、真实 FastAPI、正式 PostgreSQL Job Worker 和生产 Excel Reader/Mapper/Ingestion，不 Mock `/api/v1/**`。固定核心链是：

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

普通 CI 不为这条验收调用真实付费 TikHub 或 LLM。

提交前常规前端检查：

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

在已经准备好隔离 PostgreSQL、API、Worker、测试 Secret 和 Excel fixture 的完整测试环境中，可单独运行：

```bash
npm --prefix frontend run test:e2e:fullstack
```

永久 CI 会通过 `.github/workflows/stage8f-fullstack.yml` 自动建立上述隔离环境并执行这条真实链。完整能力矩阵和边界见：

[`../docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md`](../docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md)

这些前端测试仍不能替代 Job Fencing、Provider、Migration 或其他后端专项集成测试；各层验证应继续各自负责真实边界。

---

## 15. 当前未实现的前端能力

当前没有：

- 登录/认证闭环；
- 独立 Analysis 管理中心；
- 独立 Job 管理中心；
- 独立 Excel Export 管理中心；
- 正式 Word 报告中心；
- Monitoring/Alert/VOC/Ticket/Dashboard 页面。

后续是否实现、何时实现看：

[`../docs/roadmap/02_生产上线实施路线.md`](../docs/roadmap/02_生产上线实施路线.md)

---

## 16. 继续阅读

- API/Job/Frontend 长期边界：`docs/blueprint/04_后端任务API与前端.md`
- 人类可读 API：`docs/03_API接口说明.md`
- Figma/Design-to-Code：`docs/guides/01_Figma与前端设计开发工作流.md`
- Collection 策略：`docs/blueprint/08_采集策略与平台能力.md`
- AI：`docs/appendix/07_AI舆情打标与分析实现.md`
- Excel Export：`docs/appendix/06_Excel统一数据导出与离线调试.md`
- Stage 8F 能力矩阵与真实验收：`docs/appendix/09_Stage8F前后端能力矩阵与真实验收.md`
- 后续阶段/Production Go-Live：`docs/roadmap/02_生产上线实施路线.md`
