# Stage 8 数据入口、统一入库与业务前端：当前实现导航

这篇文件继续保留原来的 `17-...` 路径，原因是仓库内已经有大量历史 Change、README 和开发导航引用它。但它现在的职责调整为：

> **告诉开发者 Stage 8 设计目前已经落到哪些真实代码，以及旧 Stage 8 详细实施记录应该怎样阅读。**

原文中数万字的 Stage 8 方案、A—F 实施顺序、当时的能力矩阵和边界说明没有删除，完整保存在：

[`17-Stage8实施设计与阶段快照.md`](17-Stage8实施设计与阶段快照.md)

旧文档里的“当前机器事实”“PLANNED”“下一阶段”等措辞是**当时 Stage 切片的快照**，不能直接当作 2026-08-22 当前实现。需要判断今天的事实时，以本页列出的当前代码入口、Contract、Migration、测试以及新的专题文档为准。

---

## 1. 为什么不能直接删除旧 Stage 8 文档

Stage 8 不只是一次页面开发，它把前面已经存在的底层能力真正接成了业务入口，其中包含很多仍然有价值的设计理由：

- 为什么 Excel 是第一版主要业务数据入口，而 TikHub 是辅助发现/补采；
- 为什么 Excel 与 TikHub 在 Canonical 后必须复用同一个 Content Owner；
- 为什么 `imports_test` / `tikhub_test` 永久保留 file-only 调试模式，同时允许显式写库；
- 为什么 File Import 使用 Import Batch，而不是伪造 Collection Run/Scope；
- 为什么浏览器长任务要进入 PostgreSQL durable Job；
- 为什么页面能力要先映射后端 Capability，再做 Contract-First Vertical Slice；
- 为什么不同页面不能通过一个“万能业务表”绕过 Collection/Content/Analysis/Reporting Owner。

这些原则仍然会影响后续开发，所以完整原文保留；只是其中阶段状态已经随代码继续演进。

---

## 2. 当前 Stage 8 相关机器事实

下面只写当前仓库能够直接证明的事实。

### 2.1 Excel 正式导入已经是 durable Job

当前链路：

```text
HTTP Excel Upload
→ Input Artifact
→ processing_import_batches
→ ingestion.import-excel.v1
→ Import Worker
→ Excel Reader / Mapper
→ Canonical
→ Relevance
→ ContentIngestionService
→ PostgreSQL Content Owner
```

主要代码：

```text
backend/src/aima_ugc/bootstrap/import_http.py
backend/src/aima_ugc/bootstrap/import_worker.py
backend/src/aima_ugc/bootstrap/manual_ingestion.py
backend/src/aima_ugc/modules/ingestion/
backend/src/aima_ugc/modules/content/ingestion.py
```

所以旧实施记录中“正式 Import HTTP/Job 仍待产品化”的阶段描述已经是历史快照。

### 2.2 TikHub/Excel 仍然在 Canonical 后汇合

TikHub：

```text
Provider Request/Attempt
→ Raw Artifact
→ Candidate-before-Mapper
→ TikHub Mapper
→ Canonical
```

Excel：

```text
Input Artifact
→ Import Batch
→ Excel Reader/Mapper
→ Canonical
```

之后都进入：

```text
Relevance
→ ContentIngestionService
→ Content Owner Repository
→ PostgreSQL Current / Version / Metric / Coverage
```

详细当前实现：

- [`../appendix/数据入口与统一入库实现.md`](../appendix/数据入口与统一入库实现.md)
- [`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md)
- [`../appendix/PostgreSQL查询与调试实战.md`](../appendix/PostgreSQL查询与调试实战.md)

### 2.3 Analysis PostgreSQL Persistence 已经存在

旧 Stage 8 实施记录中有多处把 Analysis Persistence 写成 `PLANNED`，那是当时的事实，不是现在的事实。

当前已经存在：

```text
analysis_content_results
analysis_content_requests
analysis_content_request_items
analysis_content_label_pairs
analysis.content-label.v1
```

Analysis 当前输出包含：

```text
relevance
voice_type
sentiment
labels
```

当前 Prompt/Taxonomy 唯一业务事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

当前实现说明：

- [`../appendix/AI舆情打标与分析实现.md`](../appendix/AI舆情打标与分析实现.md)
- [`../../backend/src/aima_ugc/modules/analysis/README.md`](../../backend/src/aima_ugc/modules/analysis/README.md)

### 2.4 正式 Excel Export 已经存在

当前正式数据库导出是：

```text
reporting_data_exports
reporting_data_export_items
reporting.content-export-excel.v1
```

它与离线 Markdown/Word 报告不是同一个 Owner。

详细：

- [`../appendix/Excel统一数据导出与离线调试.md`](../appendix/Excel统一数据导出与离线调试.md)
- [`../../backend/src/aima_ugc/modules/reporting/README.md`](../../backend/src/aima_ugc/modules/reporting/README.md)
- [`../appendix/Word舆情报告生成与排版实现.md`](../appendix/Word舆情报告生成与排版实现.md)

### 2.5 当前 Vue 页面已经存在

真实路由只以：

```text
frontend/src/app/routes.ts
```

为准。

当前路由：

```text
/
/collection-runtime
/collection-strategy
/voice-plaza
```

当前业务 Feature：

```text
frontend/src/features/import-batches/
frontend/src/features/collection-strategy/
frontend/src/features/voice-plaza/
```

因此旧实施记录中：

```text
“Stage 8B 没有 Vue 页面”
“Batch 列表/KPI/Cursor 仍属于未来 Stage 8C”
“声音广场仍未开始”
```

这类句子只能按**阶段历史**理解，不能用来判断今天是否已经实现。

当前前端开发入口：

- [`../../frontend/README.md`](../../frontend/README.md)
- [`../guides/Figma与前端设计开发工作流.md`](../guides/Figma与前端设计开发工作流.md)

---

## 3. 当前仍然保留的 Stage 8 长期设计原则

这些原则今天仍然有效。

### 3.1 Excel 是主要业务入口，TikHub 是补充入口

当前第一版产品的数据入口关系继续按：

```text
Excel 手工导入
→ 主要业务数据入口

TikHub
→ 辅助发现 / 补漏 / 详情与评论补充
```

这不表示 Excel 文件是业务数据库。最终业务事实仍然收敛到 PostgreSQL。

### 3.2 调试入口永久复用生产实现

```text
imports_test
→ 默认 file-only
→ 显式选择时复用正式 File Import / Content / Analysis / Export 能力

tikhub_test
→ 默认 file-only
→ 显式选择时复用正式 Collection / Provider / Raw / Candidate / Ingestion
```

不允许重新建立：

```text
ExcelDatabaseWriter
TikHubDatabaseWriter
第二套 Mapper
第二套 Excel Exporter
第二套 AI Service
```

### 3.3 不建立“万能业务父表”

用户在前端看到的是一个统一产品，但数据库 Owner 仍然分开：

```text
Excel Import
→ Ingestion / Import Batch

TikHub Collection
→ Collection Run / Scope / Request / Attempt

业务内容
→ Content

AI
→ Analysis

正式 Excel 导出
→ Reporting
```

前端可以聚合展示，后端不能为了页面方便把这些事实重新塞进一个万能表。

### 3.4 页面仍然遵循 Contract-First Vertical Slice

新增/修改页面时顺序仍然是：

```text
业务目标
→ 页面信息结构 / Figma
→ UI 需要的数据与行为
→ 当前 Capability 核对
→ Pydantic HTTP Contract（需要变化时）
→ API/Contract Test
→ OpenAPI
→ Orval Client
→ Vue Feature / Store / Page
→ 联调
→ E2E
→ 视觉验收
```

不要先把前端 Mock 字段做出来，再让后端长期追着 Mock 补事实。

---

## 4. 当前要修改 Stage 8 相关能力时去哪里

| 要改什么 | 先看 |
| --- | --- |
| Excel Import HTTP / Batch / Worker | `modules/ingestion/`、`bootstrap/import_http.py`、`bootstrap/import_worker.py` |
| Excel 文件映射/离线链 | `adapters/providers/imports_test/` + Excel Reader/Mapper 实现 |
| TikHub 调试/补采 | `adapters/providers/tikhub_test/` + 正式 TikHub Adapter |
| Canonical / Content 写入 | `contracts/canonical.py`、`modules/content/ingestion.py`、PostgreSQL Content Repository |
| 全局相关性清洗 | System/Collection 当前 Relevance 配置与生产 Service；再看统一入库附录 |
| AI relevance / voice_type / labels | 当前 Prompt、`modules/analysis/`、Analysis Repository |
| 采集运行中心 | `frontend/src/features/import-batches/` |
| 采集策略 | `frontend/src/features/collection-strategy/` |
| 声音广场 | `frontend/src/features/voice-plaza/` |
| 正式 Excel Export | `modules/reporting/` + `platform/export/excel.py` |
| 离线 Word Report | `platform/reporting/` |

如果涉及公共 API 字段，继续按：

```text
backend Pydantic Contract
→ FastAPI
→ OpenAPI
→ generated TypeScript Client
```

修改，不能手改 generated Client。

---

## 5. Stage 8 之后还要开发什么

Stage 8 的完成不等于系统已经可以生产上线。

当前后续正式路线以：

[`../roadmap/生产上线实施路线.md`](../roadmap/生产上线实施路线.md)

为准，重点剩余包括：

```text
企业认证 / 后端授权
Stage 11 Docker / Compose / Production Config
离线 Release Bundle
PostgreSQL + Artifact 协调 Backup/Restore
回滚和真实生产服务器验收
Stage 9 Monitoring / VOC / 工单（按产品优先级）
Stage 10 Word 报告产品化（如果需要）
Stage 12 旧数据迁移（如果需要）
```

不要因为 Stage 8 页面已经存在，就把 Production Release 当成已经完成。

---

## 6. 怎样阅读完整历史实施记录

完整原文：

[`17-Stage8实施设计与阶段快照.md`](17-Stage8实施设计与阶段快照.md)

适合用来理解：

- 为什么 Stage 8 当时拆成 A/B/C/D/E/F；
- 某个能力在进入代码前有哪些门禁；
- Import Batch、Relevance、页面 Capability Mapping 等设计是怎样形成的；
- 当时哪些能力还不存在，以及后续怎样逐步补齐。

阅读时遵循：

```text
历史记录里的阶段状态
→ 解释当时为什么这样开发

今天是否已经实现
→ 回到当前代码 / Contract / Migration / Test / 本页当前导航
```

这样既保留原技术设计，又不会让过去的“当前状态”污染今天的开发判断。
