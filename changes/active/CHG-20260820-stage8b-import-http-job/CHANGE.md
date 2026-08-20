---
schema: rvc-change/v1
id: "CHG-20260820-stage8b-import-http-job"
title: "Stage 8B Import HTTP / Job Productization"
level: L3
status: blocked
owner: "AI coding agent"
branch: "feature/stage8b-import-http-job"
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - "ingestion"
  - "http-api"
  - "job-runtime"
  - "openapi-orval"
affected_paths:
  - "backend/src/aima_ugc/modules/ingestion/"
  - "backend/src/aima_ugc/bootstrap/"
  - "backend/src/aima_ugc/platform/jobs/"
  - "backend/src/aima_ugc/adapters/persistence/postgres/"
  - "tests/"
  - "contracts/openapi/"
  - "frontend/src/generated/api/"
  - "docs/"
contracts: []
data_changes: []
---

# 目标

把 Stage 8A 已存在的正式 Excel File Import 产品化为浏览器和未来 Vue 前端可稳定调用的
HTTP Contract、Source Artifact、Processing Import Batch、持久化 Import Job、Worker、状态查询、
固定 OpenAPI 与 Orval Client；不复制 Reader、Mapper、Filter、Dedup、Content Ingestion、
Artifact Store 或 Job Runtime。

# 背景与当前事实

- 当前 GitHub `main`、本地 `main` 与 `origin/main` 均为
  `43a0bdcebc7abc7f7c796f255c2af6e53b0fb8ea`；任务开始时工作区干净。
- `changes/active` 原为空；GitHub 当前没有开放 PR。
- Stage 8A 实现 PR `#88` 与归档 PR `#89` 已合并，归档 Change 为
  `changes/archive/2026-08/CHG-20260820-stage8a-unified-manual-ingestion/CHANGE.md`。
- 当前 Alembic 代码 Head 是 `20260820_0019`；本机缺少
  `.runtime/secrets/postgres_password`，因此尚不能读取本地数据库 `alembic current` 或运行本地
  PostgreSQL 集成测试。本轮 Stage 8A Unit/Contract 目标测试为 `8 passed`。
- 机器事实已存在：`processing_import_batches`、可空唯一 `job_id`、Import Batch 父级
  Provider Request/non-billable Attempt、Input Artifact 与统一 Content Ingestion。
- 当前公开 OpenAPI 只有 `/health/live` 与 `/health/ready`；Stage 8B Route、统一 HTTP 错误层、
  Import Job Payload/Handler 和查询 API 均不存在。
- `imports_test/keyword_pack.txt` 被正式文档明确限定为本地人工入口配置；正式 Import 的相关性
  词包来源和角色尚未批准，不能静默复用该调试文件。

# 成功标准

- [ ] HTTP 上传/登记只接受经批准的 Excel 输入，并通过统一 ArtifactService 保存 Source Artifact。
- [ ] 创建请求在同一 PostgreSQL 业务边界建立 Processing Import Batch 与持久化 Import Job，
  返回 `202 Accepted`、Batch ID、Job ID 和 queued 状态；Router 不执行长文件处理。
- [ ] Import Job 使用版本化 Pydantic Payload，由现有 Job Runtime/Worker 认领、接管、重试、
  Fencing、取消和终态转换；未知 Worker 不会认领该类型。
- [ ] Worker 调用生产 Excel Reader/Mapper、生产相关性 Filter/稳定身份 Dedup 和 Stage 8A 正式
  File Import/Content Ingestion，不调用 `imports_test` 作为生产实现。
- [ ] Batch 查询返回稳定 status、stage、stats、error summary、时间和关联 Job 快照；Job 查询不复制
  第二套状态真相。
- [ ] 正常、非法 Excel、错误 Artifact/Batch/Job、失败/重试与未处理异常均返回统一错误 Contract，
  含 request_id 且不泄露路径、SQL、Secret 或堆栈。
- [ ] Job 重放、Lease takeover 和终态后重入不产生重复 Current Content，并保留合法来源历史。
- [ ] 固定 OpenAPI 无漂移，Orval Client 由生成流程产生并通过前端 lint、双 typecheck、test、build。
- [ ] API/Contract/Job/Worker/PostgreSQL 18 测试、两阶段 Review、全部适用本地门禁与最终 PR CI 通过。
- [ ] PR 正常合并，合并后 main 获得新鲜验证，Change 标记 done 并归档；Stage 8C 未开始。

# 范围

- Excel Source Artifact 的一个正式 HTTP 入口。
- Processing Import Batch 创建/详情查询和关联 Job 状态查询。
- `file.import.v1` 等最终确认名称的版本化 Job Payload、Handler 和 Worker Registry 注册。
- 统一 HTTP 错误 Contract、request_id 中间件与 FastAPI/Starlette 异常转换。
- 复用现有生产 Reader/Mapper/Filter/Dedup、Artifact、Job、Content Ingestion/PostgreSQL 来源链。
- API、Contract、Job/Worker、PostgreSQL Integration 与必要安全边界测试。
- 固定 OpenAPI、Orval Client和真正受影响的 Blueprint/API/测试说明。

# 非目标

- 不实现 Stage 8C 采集运行中心 Vue/Figma 页面、列表/KPI/Cursor Query Read Model。
- 不实现 Content Center、TikHub 补采页面、Stage 8D—8F、Analysis Persistence 或正式报告页面。
- 不新增平行 Excel Writer/Mapper/Repository/Client/Job Runtime，不让 Router 直接 SQL 或处理整份 Excel。
- 不改变 Excel Workbook Export Contract、AI Prompt/Taxonomy、Collection Operation 或 Provider 费用语义。
- 不实现第三方认证、本地账号、Session、CSRF、RBAC 或 HTTP actor 幂等；未认证写 API 只用于受控环境，
  不宣称具备公网生产认证能力。
- 不自动启动 PostgreSQL、不自动执行 Migration、不升级依赖。

# 必须保持不变

- `imports_test` / `tikhub_test` 默认 file-only 与显式数据库模式的既有入口和输出。
- Stage 8A `Input Artifact → Import Batch → Request/Attempt → Content Ingestion` 来源约束。
- Collection Request 的 `scope_id` 父级、Provider Config 不可变、Attempt/Raw 复合来源和 Content Owner。
- `processing_import_batches` 当前表结构及 `20260820_0019` 历史 Revision；没有事实证明需要时不新增 Migration。
- Job Runtime 的内部幂等、Lease、Deadline、Fencing、重试、取消、Reaper 与事件语义。
- Pydantic → FastAPI OpenAPI → 固定 JSON → Orval Fetch Client 单一 Contract 链。
- Python/Node/PostgreSQL/Orval 等锁定版本与根目录唯一工程结构。

# 关键决策

## 已确认

- 采用 Stage 8A 既有 Processing Import Batch、Artifact、Provider Request/Attempt 与 Content Ingestion，
  不新建 FileAttempt/FileStore/ExcelDatabaseWriter。
- HTTP 只创建资源并返回 202；Worker 执行长文件处理。
- 状态查询以 Batch + 现有 Job 快照组合，不能建立平行 Job 状态表。
- 当前 Schema 的 `stats jsonb` 可承载最小阶段/计数快照；优先不制造 Migration。若实现证据证明现有
  Schema 无法保证正确性，必须先重新完成 L3 Schema 门禁，不能静默加列。
- OpenSpec 目录当前不存在，本 Change 是当前仓库的唯一 Active Change 协议。

## 待用户决定：正式相关性 Filter 的关键词来源

方案 A（推荐）：上传请求显式携带本次 `keywords`，Job Payload 持久化经校验的规范化列表；
`profile` 固定为当前正式 Profile，`sheet_name` 只作为可选精确选择。它不复用调试词包，也不把
Collection Keyword Pack 的角色误当 Import Relevance，Schema/Migration 为零，未来 UI 可明确展示
本次输入。代价是调用方必须提交关键词。

方案 B：请求携带现有 PostgreSQL `keyword_pack_id`，Worker 读取该 Pack。它能复用数据库配置，
但仓库尚未批准“采集发现词包 = 导入相关性清洗词包”，会把两个业务角色静默合并，并增加
对象存在/状态/快照/后续变更语义。

方案 C：Stage 8B 不做相关性过滤，所有合法 Canonical 行直接去重入库。Contract 最小，但改变
Stage 8A 既有处理语义，也不满足 Blueprint 17 和本任务给出的 Reader → Mapper → Filter → Dedup 链。

在用户决定前，不实现 HTTP Request、Job Payload、Handler 或依赖该语义的测试。

## 后续仍需按顺序冻结的技术/安全边界

- Excel HTTP 传输形态与最大压缩/解压大小；仓库只要求限制扩展名、MIME、大小和 Zip Bomb，尚无数值。
  解决关键词来源后，再一次只提出这个上游问题。
- 当前认证已正式延期；本 Stage 不把受控环境 API 描述为公网生产就绪。

## Migration、部署与回滚

- 计划不新增 Schema/Migration；部署前数据库必须已在 `20260820_0019`，API 与 Worker 应同时升级，
  并共享同一 PostgreSQL 与 ArtifactStore。
- 回滚先停止新导入并等待/处置已有 Import Job，再回退 API/Worker/Contract 代码；若最终没有新 Migration，
  现有 Batch/Job/Artifact/Content 数据无需回填或 downgrade。
- 主要风险是上传资源耗尽、XLSX Zip Bomb、Worker 崩溃窗口、Batch/Job 终态漂移、错误泄露和重放重复；
  必须分别由大小/压缩边界、Artifact 完整性、Fencing/幂等、组合查询和统一异常测试证明。

# 任务

- [x] 调查当前实现和事实源
- [ ] 取得正式相关性 Filter 关键词来源的用户决定并同步本 Change/长期事实源
- [ ] 冻结 Excel HTTP 传输与压缩/解压大小边界
- [ ] 建立 HTTP Contract/Error/OpenAPI、API Service 和 Import Job/Worker 的失败测试并观察正确 Red
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 完成需求符合性 Review 与代码质量 Review，修复所有严重/重要问题
- [ ] 取得新鲜验证证据
- [ ] Draft PR → 最终 Head CI → Ready → 正常 Merge → 合并后 main 验证 → Change 归档

# 验证

## 计划

- [Contract/API Red] → 修改范围：HTTP Pydantic Contract、统一错误层、API 测试
  → 预期结果：新增上传/Batch/Job 查询和所有错误外形先因实现不存在而失败
  → 验证方式：`uv run pytest tests/contracts tests/api -q` 的目标选择。
- [Job/Worker Red] → 修改范围：Import Job Payload/Handler、Registry 与 Job 测试
  → 预期结果：证明创建、Claim/takeover、失败/重试/终态重入和取消边界
  → 验证方式：目标 Unit + `tests/integration/jobs`/Stage 8B PostgreSQL 测试。
- [最小 Green] → 修改范围：Ingestion Application Service、PostgreSQL Repository 增量、API/Worker bootstrap
  → 预期结果：202 创建 Batch/Job，Worker 复用正式 pipeline，查询返回组合状态
  → 验证方式：目标 API/Contract/Worker/PostgreSQL Integration。
- [生成物] → 修改范围：固定 OpenAPI、`frontend/src/generated/api/`
  → 预期结果：Orval 只由固定 Contract 生成且 TypeScript 可编译
  → 验证方式：Contract generate/check/compatibility、Orval、frontend lint/typecheck/test/build。
- [文档与复核] → 修改范围：Blueprint 03/04/17、Blueprint README、API/测试说明与 Change
  → 预期结果：长期文档只描述当前合并后能力，Change 保存取舍和证据
  → 验证方式：Docs gate、需求逐项核对、代码质量检查、`git diff --check`。
- [完整门禁] → 修改范围：全仓
  → 预期结果：Ruff、mypy、全部适用测试、Architecture、Table Ownership、Secret、Docs、Wheel、
  Migration 与前端/CI 全部基于最终 Head 通过
  → 验证方式：仓库 CI 当前真实命令及全部适用 GitHub workflows。

## 新鲜证据

- `python .../rvc.py discover --root . --json`：`cache_hit`；Active Change 初始为空。
- `uv run alembic heads`：退出码 0，`20260820_0019 (head)`。
- `uv run pytest tests/unit/database/test_stage8a_import_schema.py tests/contracts/test_stage8a_provider_request.py tests/unit/collection/test_manual_ingestion_multi.py -q`：退出码 0，`8 passed`。
- `uv run alembic current` / `alembic check` 与 Stage 8A PostgreSQL Integration：因本机缺少
  `.runtime/secrets/postgres_password` 未执行到数据库；保留原错误，不作为测试失败或成功证据。
- GitHub 连接器确认 PR `#88/#89` 已合并、当前无开放 PR；当前 main push workflow/status 接口未返回
  可见记录，历史 CI 不替代本 Stage 最终 Head CI。

# 文档影响

- 实现后必须同步 Blueprint 04 的 HTTP/Error/Job 当前事实、Blueprint 17 的 Stage 8B 状态、
  Blueprint README 下一阶段、`docs/API接口说明.md` 与 `docs/测试与调试说明.md`。
- 若 Schema 不变，Blueprint 03 只更新 Stage 8B Batch/Job 当前机器语义，不制造 Migration 叙事。
- Excel Workbook/Exporter、Analysis、Provider Operation 没有变化时不修改 Blueprint 13/15/平台文档。

# 交付

- Commit：尚未创建；用户已授权完成本 Stage 所需的中文提交。
- PR：尚未创建；后续只创建一个 Draft PR，最终 CI/Review 完成后转 Ready 并正常合并。
- 发布：不部署生产；只交付仓库代码、Migration 状态说明、生成物、测试与合并后 main 证据。
