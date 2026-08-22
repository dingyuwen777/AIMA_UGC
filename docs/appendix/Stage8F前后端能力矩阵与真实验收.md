# Stage 8F 前后端能力矩阵与真实验收

本文记录公司内网 V1 上线前，当前首版业务动作从 Vue 到 FastAPI、PostgreSQL Job、Worker 和最终查询结果的对应关系，并说明页面可操作状态与后端业务守卫怎样保持一致、每类测试实际能证明什么。

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
→ 页面能从现有正式 API 获得的资格事实已用于 enabled/disabled
→ 后端仍保留最终业务守卫，不把安全和一致性责任转移给浏览器

测试分层
→ 说明当前是 Unit、Mock Browser、PostgreSQL Integration 还是 Real Full-stack

明确延期
→ 已批准不属于公司内网 V1 的能力
```

Mock Browser E2E 用于页面和交互回归，不能单独证明真实后端业务闭环。

---

## 2. App Shell 与导航

| 业务入口 | Router | App Shell | 当前状态 | 验证 |
| --- | --- | --- | --- | --- |
| 首页兼容入口 | `/` | `首页` 可导航 | 已完整闭环 | `frontend/tests/app-shell.spec.ts`、`frontend/tests/routes.spec.ts` |
| 声音广场 | `/voice-plaza` | 可导航 | 已完整闭环 | Routes / Voice Plaza Unit / Browser E2E |
| 采集运行中心 | `/collection-runtime` | 可导航 | 已完整闭环 | Routes / Runtime Unit / Browser E2E |
| 采集策略 | `/collection-strategy` | 可导航 | 已完整闭环 | Routes / Strategy Unit / Browser E2E |
| 智能洞察、销售漏斗、热点捕捉、管理员、帮助反馈 | 当前无正式 Route | 不显示为死按钮 | 明确不属于当前首版页面 | App Shell Unit |

`/` 继续是兼容入口并复用采集运行中心；当前不为了目录或路由美观再造独立 Dashboard。

---

## 3. 采集运行中心

| 业务动作 | FastAPI / Contract | 前端链 | 当前状态 | 主要验证 |
| --- | --- | --- | --- | --- |
| 浏览器选择并上传 Excel | `POST /api/v1/import-batches` | `ImportUploadDialog → store.upload → api.ts → generated client` | 已完整闭环 | API/Integration + Mock E2E + Real Full-stack |
| 创建 Import Batch + Job | 同一上传请求，业务父事实与 Job 同事务 | 上传完成后打开 Batch Detail | 已完整闭环 | `tests/integration/ingestion/` + Real Full-stack |
| Batch 列表/摘要/详情 | `GET /api/v1/import-batches*`、`GET /api/v1/jobs/{job_id}` | Runtime Store / Detail Drawer | 已完整闭环 | API/Integration + Unit/Mock E2E |
| queued/running/succeeded/failed/cancelled 展示 | `ImportBatchResponse` / `JobStatusResponse` | Store 5 秒轮询；详情同步刷新 | 已完整闭环 | Store Unit + Mock E2E + Real Full-stack 成功/失败终态 |
| Batch → 声音广场 | `GET /api/v1/contents?source_identifier=<batch_id>` | `查看入库内容 → /voice-plaza?source_identifier=<batch_id>` | 已完整闭环 | Content PostgreSQL Integration + Real Full-stack |
| TikHub 手工 Run | `GET /api/v1/collection-capabilities`、`POST /api/v1/collection-runs`、Run Detail | Runtime Page / Supplement Drawer / Store | 已完整闭环 | 前端 Mock E2E + Collection 后端 Fixture/Integration；普通 CI 不发送真实付费请求 |

Excel 和 TikHub 仍然拥有各自的父事实，不建立万能 Run 表：Excel 使用 Import Batch；TikHub 使用 Collection Run/Scope。

### 3.1 Import 失败/取消怎样展示阶段

Import 当前公开 Contract 会保存：

```text
最终 Job 状态
progress
error_code
Batch error_summary
当前 stage
开始/结束时间
统计
```

但它没有一份可审计的“所有历史阶段完成时间线”。因此：

- `queued/running/succeeded` 可以按当前 stage 展示阶段流水线；
- `failed/cancelled` 不把未知历史阶段全部伪装成“等待中”，也不猜“失败发生在哪一步”；
- 终态页面明确显示失败/取消，并引导用户查看 `Job 状态` 与 `错误记录`。

如果未来产品确实需要失败阶段历史，应先建立正式的可审计机器事实，而不是只在 Vue 中推断。

### 3.2 Batch Supplement 的前端资格

“基于已有批次补采”只对以下 Batch 提供：

```text
Import Batch status = succeeded
AND rows_ingested > 0
```

选择具体 Batch 后，前端复用正式 `GET /api/v1/contents`，对五个平台各做最多一次 `limit=1` 的存在性探测：

```text
source_identifier = batch_id
platforms = [目标 Content 平台]
limit = 1
```

因此不会为了资格判断扫描整批 Content，也不会仅凭 Excel 文件名猜平台。

平台按钮还必须同时满足当前 Provider Config 的正式 Capability：

```text
content_detail
+ comments（用户选择评论时）
+ sub_comments（用户选择二级回复时）
```

Discovery 模式还额外要求 `keyword_search`。

前端资格用于避免用户组成注定失败的任务；`PostgresCollectionHttpService.create_run()` 仍然重新解析 Provider、Relevance、Batch target 和 Capability，是最终业务守卫。

### 3.3 小红书 `xiaohongshu` / `xhs` 边界

当前两个领域使用的机器值不同：

```text
File Import / Content Canonical
→ xiaohongshu

Collection / TikHub 公共 Contract
→ xhs
```

不修改 Content 持久身份，也不在全仓复制别名。兼容只放在 Collection 读取 Batch target 的边界：

```text
backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py
```

行为固定为：

```text
Collection 请求 xhs
→ 可匹配 Batch 中 stored platform = xhs 或 xiaohongshu
→ 返回 CollectionEnrichmentTarget.platform = xhs
```

真实 Excel Worker 入库后用 `platforms=("xhs",)` 读取补采目标的 PostgreSQL 集成测试固定验证这条兼容链。

---

## 4. 采集策略

| 业务动作 | FastAPI | 前端链 | 当前状态 | 验证 |
| --- | --- | --- | --- | --- |
| Keyword Pack 创建/查看 | `POST/GET /api/v1/keyword-packs*` | Strategy Store / `api.ts` / generated client | 已完整闭环 | Backend + Strategy Unit/Mock E2E |
| 添加关键词 | `POST /api/v1/keyword-packs/{pack_id}/keywords` | Strategy Page | 已完整闭环 | Backend + Strategy Unit/Mock E2E |
| 词包启停 | `PUT /api/v1/keyword-packs/{pack_id}/enabled` | Strategy Page | 已完整闭环；被 Global Relevance/启用 Plan 引用时前端禁用停用动作，后端继续最终校验 | Backend + Unit/Mock E2E |
| 全局规则相关性 | `GET/PUT /api/v1/relevance-config` | Strategy Store / Page | 已完整闭环 | Backend + Strategy Unit/Mock E2E |
| Collection Plan 创建/查看/启停 | `POST/GET/PUT /api/v1/collection-plans*` | Strategy Store / Page | 已完整闭环；创建/重新启用前按当前正式事实判断资格，后端继续最终校验 | Backend + Strategy Unit/Mock E2E |

保存 Collection Plan 只修改调度配置。真正执行仍然是：

```text
Plan
→ Scheduler Occurrence
→ Run + Job
→ Worker
```

页面不把“保存计划”表达成“立即采集”。

### 4.1 Keyword Pack 停用资格

后端当前拒绝：

```text
全局 Relevance 正在引用该 Pack
OR
启用中的 Collection Plan 正在引用该 Pack
```

前端通过现有：

```text
GET /api/v1/relevance-config
GET /api/v1/collection-plans?enabled=true
```

形成只读资格快照并禁用对应“停用”按钮；Store 同样在发请求前拒绝无效操作。后端守卫继续保留，避免并发或陈旧页面绕过一致性规则。

### 4.2 Collection Plan 创建/重新启用资格

前端按需读取所选 Pack detail，并使用现有 Capability/Relevance API 判断：

```text
所选 Discovery Pack 当前 enabled
+ 每个目标平台至少存在一条 enabled 且 platform=all/目标平台的关键词
+ 目标 Provider Config 当前存在
+ Provider/Platform 支持 keyword_search
+ 如果 Plan 要 enabled，则 Global Relevance 当前可用
```

页面“刷新数据”会失效 Pack detail 资格缓存，并按当前页重新读取所需详情，避免长期使用旧资格快照。

这些检查用于 enabled/disabled 和错误解释，不替代后端 `_validate_execution_surface()`。

---

## 5. 声音广场

| 业务动作 | FastAPI / 查询事实 | 前端链 | 当前状态 | 验证 |
| --- | --- | --- | --- | --- |
| Content 列表/详情 | `GET /api/v1/contents`、`GET /api/v1/contents/{id}` | Voice Store / `api.ts` / generated client | 已完整闭环 | Content PostgreSQL Integration + Unit/Mock E2E |
| 文本/平台/内容类型/时间筛选 | `ContentListQuery` | Filters → Store → generated client | 已完整闭环 | Unit + Backend Query Integration |
| 五平台筛选 | 小红书、抖音、微博、B站、快手；另有 `file` | Filters | 已完整闭环 | `frontend/tests/voice-plaza.spec.ts` |
| Batch / Run 来源筛选 | 后端 `source_identifier` 沿 Content Version → Provider Request/Attempt → Import Batch 或 Collection Run 查询 | Route query / Filters → API | 已完整闭环 | PostgreSQL Integration + Real Full-stack Batch 链 |
| Analysis pending/stale/completed | Content Query 投影当前匹配 Analysis | Store / Table / Detail | 已完整闭环 | Backend Integration + Unit/Mock E2E |
| AI Analysis Request / Job | `POST /api/v1/content-analysis-requests`、`GET /api/v1/content-analysis-jobs/{job_id}` | Voice Page / Store | 已完整闭环 | Backend Fake/Fixture + 前端 Mock；普通 CI 不调用付费 LLM |
| Excel Export | `POST/GET /api/v1/data-exports*` | Voice Page / Export Dialog | 已完整闭环；空 selected/page/query 不创建 Job | Reporting Backend + Unit/Mock E2E |
| Artifact Download | `GET /api/v1/data-exports/{export_id}/download` | Export Dialog | 已完整闭环；未就绪不允许下载 | Backend 409/Artifact Test + 前端 Unit/Mock E2E |

Vue 不维护第二套 Content 业务筛选。筛选条件必须继续下传到正式后端查询。

### 5.1 空结果 Export

当前声音广场已经取得的 `items` 为空时：

```text
AI 打标入口 disabled
当前页 Export disabled
全部查询结果 Export disabled
已选内容 Export disabled
```

Export Dialog 仍可打开，用于查看已有导出记录和下载已经成功的 Artifact；只是不能创建一个目标必为空的新 Export Job。

后端 `ContentSelectionEmpty` 守卫仍然保留。

---

## 6. Stage 8F Real Full-stack Acceptance

永久测试入口：

```text
.github/workflows/stage8f-fullstack.yml
frontend/playwright.fullstack.config.ts
frontend/e2e-fullstack/excel-import.spec.ts
tests/fullstack/create_stage8f_excel_fixture.py
tests/fullstack/run_stage8f_worker.py
```

真实验收不 Mock `/api/v1/**`，固定覆盖两条链。

### 6.1 成功链

```text
确定性合法 Excel fixture
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
→ Runtime Detail = succeeded
→ rows_ingested = 1
→ 点击“查看入库内容”
→ /voice-plaza?source_identifier=<batch_id>
→ 后端来源链查询
→ 浏览器显示该 Batch 导入 Content
```

### 6.2 真实 Worker 失败链

第二个 fixture 是结构合法的 OOXML，因此 HTTP 上传会真实创建 Import Batch + Job；但它故意缺少正式 Excel Profile 的必要字段：

```text
合法 XLSX
→ HTTP 202
→ Import Batch + Job
→ 正式 Worker
→ 生产 Reader/Mapper 校验失败
→ Job status = failed
→ error_code = invalid_import
→ Batch failed
→ “查看入库内容” disabled
→ 页面显示可审计失败终态
→ 不伪造未知阶段历史
```

### 6.3 隔离与费用边界

Full-stack Workflow 固定：

- PostgreSQL 使用 CI 隔离实例；
- 空库先 Alembic migrate 到 head；
- Worker harness 只循环调用生产 `JobWorker.run_once()`，不复制 Import 逻辑；
- Excel fixture 只准备输入，生产 Reader/Mapper/Ingestion 不复制；
- 不创建 TikHub Collection Run，不调用真实 TikHub；
- 不创建 Analysis Request，不调用真实付费 LLM；
- 测试结束停止 API/Worker，并 TRUNCATE 隔离业务数据后核对 Content/Import Batch 已清空。

---

## 7. Mock E2E 与真实 E2E 的职责

```text
npm --prefix frontend run test:e2e
→ Mock API
→ 快速验证按钮、Dialog/Drawer、enabled/disabled、状态和常见错误
→ 覆盖词包停用资格、Batch 补采资格、Import 失败终态、空 Export 等 UI 行为

npm --prefix frontend run test:e2e:fullstack
→ 真实 API + PostgreSQL + Worker
→ 验证 Excel 成功业务链 + Worker 失败业务链
```

两者不能互相替代。

---

## 8. Stage 8F 严格完成定义

Stage 8F 的正式完成口径是：

```text
首版前后端能力矩阵已建立
所有首版页面入口和导航有真实用途
不存在前端假按钮对应完全不存在的后端能力
不存在后端首版关键能力但用户完全没有入口的缺口
页面 enabled/disabled 与现有正式业务资格一致
异步 Job 的 queued/running/succeeded/failed/cancelled 可理解
Excel 上传真实可用
Excel Worker 真实处理成功
真实 Worker 失败终态可理解
导入 Content 可在声音广场显示
Batch → Voice Plaza source_identifier 真实可用
Batch Supplement 的 Batch/平台/Provider Capability 资格真实可用
AI/Export 首版能力与后端一致
Mock Browser E2E 通过
Real Full-stack Excel 成功/失败 Acceptance 通过
Frontend lint/typecheck/unit/build 通过
Backend API/Contract/受影响 Integration 通过
正式文档与机器事实同步
```

精确通过证据以当前 PR/main 对应 GitHub Actions 的最终 HEAD 为准，不用历史日志替代当前验证。

---

## 9. 当前明确延期

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
