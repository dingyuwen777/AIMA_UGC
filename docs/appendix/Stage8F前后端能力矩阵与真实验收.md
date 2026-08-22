# Stage 8F 前后端能力矩阵与真实验收

本文记录公司内网 V1 上线前，当前首版业务动作从 Vue 到 FastAPI、PostgreSQL Job、Worker 和最终查询结果的对应关系，并说明每类测试实际能证明什么。

精确字段、枚举和 Schema 不在本文复制第二份，分别以以下机器事实为准：

```text
backend/src/aima_ugc/contracts/http.py
backend/src/aima_ugc/bootstrap/api.py
contracts/openapi/openapi.json
frontend/src/generated/api/
backend/src/aima_ugc/modules/*/tables.py
migrations/versions/
```

## 1. 状态口径

本文使用：

```text
已完整闭环
→ 当前 Route / Contract / generated client / Feature / 页面入口和结果链一致

测试分层
→ 说明当前是 Unit、Mock Browser、PostgreSQL Integration 还是 Real Full-stack

明确延期
→ 已批准不属于公司内网 V1 的能力
```

Mock Browser E2E 用于页面和交互回归，不能单独证明真实后端业务闭环。

## 2. App Shell 与导航

| 业务入口 | Router | App Shell | 当前状态 | 验证 |
| --- | --- | --- | --- | --- |
| 首页兼容入口 | `/` | `首页` 可导航 | 已完整闭环 | `frontend/tests/app-shell.spec.ts`、`frontend/tests/routes.spec.ts` |
| 声音广场 | `/voice-plaza` | 可导航 | 已完整闭环 | Routes / Voice Plaza Unit / Browser E2E |
| 采集运行中心 | `/collection-runtime` | 可导航 | 已完整闭环 | Routes / Runtime Unit / Browser E2E |
| 采集策略 | `/collection-strategy` | 可导航 | 已完整闭环 | Routes / Strategy Unit / Browser E2E |
| 智能洞察、销售漏斗、热点捕捉、管理员、帮助反馈 | 当前无正式 Route | 不显示为死按钮 | 明确不属于当前首版页面 | App Shell Unit |

`/` 继续是兼容入口并复用采集运行中心；本阶段不为了目录或路由美观再造独立 Dashboard。

## 3. 采集运行中心

| 业务动作 | FastAPI / Contract | 前端链 | 当前状态 | 主要验证 |
| --- | --- | --- | --- | --- |
| 浏览器选择并上传 Excel | `POST /api/v1/import-batches` | `ImportUploadDialog → store.upload → api.ts → generated client` | 已完整闭环 | API/Integration + Mock E2E + Stage 8F Real Full-stack |
| 创建 Import Batch + Job | 同一上传请求，业务父事实与 Job 同事务 | 上传完成后打开 Batch Detail | 已完整闭环 | `tests/integration/ingestion/` + Real Full-stack |
| Batch 列表/摘要/详情 | `GET /api/v1/import-batches*`、`GET /api/v1/jobs/{job_id}` | Runtime Store / Detail Drawer | 已完整闭环 | API/Integration + Unit/Mock E2E |
| queued/running/succeeded/failed 展示 | `ImportBatchResponse` / `JobStatusResponse` | Store 5 秒轮询；详情同步刷新 | 已完整闭环 | Store Unit + Mock E2E + Real Full-stack 成功终态 |
| Batch → 声音广场 | `GET /api/v1/contents?source_identifier=<batch_id>` | `查看入库内容 → /voice-plaza?source_identifier=<batch_id>` | 已完整闭环 | Content PostgreSQL Integration + Stage 8F Real Full-stack |
| TikHub 手工 Run | `GET /api/v1/collection-capabilities`、`POST /api/v1/collection-runs`、Run Detail | Runtime Page / Supplement Drawer / Store | 已完整闭环 | 前端 Mock E2E + Collection 后端 Fixture/Integration；普通 CI 不发送真实付费请求 |

Excel 和 TikHub 仍然拥有各自的父事实，不建立万能 Run 表：Excel 使用 Import Batch；TikHub 使用 Collection Run/Scope。

## 4. 采集策略

| 业务动作 | FastAPI | 前端链 | 当前状态 | 验证 |
| --- | --- | --- | --- | --- |
| Keyword Pack 创建/查看 | `POST/GET /api/v1/keyword-packs*` | Strategy Store / `api.ts` / generated client | 已完整闭环 | Backend + Strategy Unit/Mock E2E |
| 添加关键词 | `POST /api/v1/keyword-packs/{pack_id}/keywords` | Strategy Page | 已完整闭环 | Backend + Strategy Unit/Mock E2E |
| 词包启停 | `PUT /api/v1/keyword-packs/{pack_id}/enabled` | Strategy Page | 已完整闭环 | Backend + Strategy Unit/Mock E2E |
| 全局规则相关性 | `GET/PUT /api/v1/relevance-config` | Strategy Store / Page | 已完整闭环 | Backend + Strategy Unit/Mock E2E |
| Collection Plan 创建/查看/启停 | `POST/GET/PUT /api/v1/collection-plans*` | Strategy Store / Page | 已完整闭环 | Backend + Strategy Unit/Mock E2E |

保存 Collection Plan 只修改调度配置。真正执行仍然是：

```text
Plan
→ Scheduler Occurrence
→ Run + Job
→ Worker
```

页面不把“保存计划”表达成“立即采集”。

## 5. 声音广场

| 业务动作 | FastAPI / 查询事实 | 前端链 | 当前状态 | 验证 |
| --- | --- | --- | --- | --- |
| Content 列表/详情 | `GET /api/v1/contents`、`GET /api/v1/contents/{id}` | Voice Store / `api.ts` / generated client | 已完整闭环 | Content PostgreSQL Integration + Unit/Mock E2E |
| 文本/平台/内容类型/时间筛选 | `ContentListQuery` | Filters → Store → generated client | 已完整闭环 | Unit + Backend Query Integration |
| 五平台筛选 | 小红书、抖音、微博、B站、快手；另有 `file` | Filters | 已完整闭环 | `frontend/tests/voice-plaza.spec.ts` |
| Batch / Run 来源筛选 | 后端 `source_identifier` 沿 Content Version → Provider Request/Attempt → Import Batch 或 Collection Run 查询 | Route query / Filters → API | 已完整闭环 | `tests/integration/content/test_stage8d_voice_plaza_runtime.py` + Real Full-stack Batch 链 |
| Analysis pending/stale/completed | Content Query 投影当前匹配 Analysis | Store / Table / Detail | 已完整闭环 | Backend Integration + Unit/Mock E2E |
| AI Analysis Request / Job | `POST /api/v1/content-analysis-requests`、`GET /api/v1/content-analysis-jobs/{job_id}` | Voice Page / Store | 已完整闭环 | Backend Fake/Fixture +前端 Mock；普通 CI 不调用付费 LLM |
| Excel Export | `POST/GET /api/v1/data-exports*` | Voice Page / Export Dialog | 已完整闭环 | Reporting Backend +前端 Unit/Mock E2E |
| Artifact Download | `GET /api/v1/data-exports/{export_id}/download` | Export Dialog | 已完整闭环；未就绪不允许下载 | Backend 409/Artifact Test +前端 Unit/Mock E2E |

Vue 不维护第二套 Content 业务筛选。筛选条件必须继续下传到正式后端查询。

## 6. Stage 8F Real Full-stack Acceptance

永久测试入口：

```text
.github/workflows/stage8f-fullstack.yml
frontend/playwright.fullstack.config.ts
frontend/e2e-fullstack/excel-import.spec.ts
tests/fullstack/create_stage8f_excel_fixture.py
tests/fullstack/run_stage8f_worker.py
```

真实链固定为：

```text
确定性 Excel fixture
→ 浏览器真实 file input
→ Vue Feature / generated client
→ FastAPI
→ Input Artifact
→ Import Batch + PostgreSQL Job
→ 正式 Job Worker
→ Excel Reader / Mapper
→ Canonical / Relevance
→ ContentIngestionService
→ PostgreSQL Content
→ Runtime Detail 变为 succeeded
→ 点击“查看入库内容”
→ /voice-plaza?source_identifier=<batch_id>
→ 后端来源链查询
→ 浏览器显示该 Batch 导入 Content
```

这条测试明确：

- 不使用 `page.route('**/api/v1/**')` 或等价 API Mock；
- PostgreSQL 使用 CI 隔离实例；
- 空库先 Alembic migrate 到 head；
- Worker harness 只循环调用生产 `JobWorker.run_once()`，不复制 Import 逻辑；
- Excel fixture 只准备输入，生产 Reader/Mapper/Ingestion 不复制；
- 不创建 TikHub Collection Run，不调用真实 TikHub；
- 不创建 Analysis Request，不调用真实付费 LLM；
- 测试结束停止 API/Worker，并 TRUNCATE 隔离业务数据后核对 Content/Import Batch 已清空。

## 7. Mock E2E 与真实 E2E 的职责

```text
npm --prefix frontend run test:e2e
→ Mock API
→ 快速验证按钮、Dialog/Drawer、状态和常见错误

npm --prefix frontend run test:e2e:fullstack
→ 真实 API + PostgreSQL + Worker
→ 验证 Excel 核心业务链
```

两者不能互相替代。

## 8. 当前明确延期

公司内网 V1 当前不实现：

```text
登录 / Authentication
Role / Permission / 权限隔离
旧历史数据迁移
独立 Analysis 管理中心
独立 Export 管理中心
正式 Word Report Center
Monitoring / Alert / VOC / Ticket
```

这些延期不代表完整 Production 已达到安全、灾备或治理标准；后续仍按 `docs/roadmap/生产上线实施路线.md` 推进。
