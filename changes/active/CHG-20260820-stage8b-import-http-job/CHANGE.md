---
schema: rvc-change/v1
id: "CHG-20260820-stage8b-import-http-job"
title: "Stage 8B Import HTTP / Job 与统一 Relevance Productization"
level: L3
status: blocked
owner: "AI coding agent"
branch: "feature/stage8b-import-http-job"
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - "ingestion"
  - "collection"
  - "analysis-relevance"
  - "http-api"
  - "job-runtime"
  - "system-keyword-catalog"
  - "openapi-orval"
affected_paths:
  - "backend/src/aima_ugc/modules/ingestion/"
  - "backend/src/aima_ugc/modules/collection/"
  - "backend/src/aima_ugc/modules/analysis/"
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
固定 OpenAPI 与 Orval Client；同时把现有 Excel 相关性判定提取为所有来源共用的 Canonical
Relevance 准入能力，并接入当前正式 Excel/TikHub 数据链；不复制 Reader、Mapper、Filter、Dedup、
Content Ingestion、Artifact Store 或 Job Runtime。

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
  词包不能静默复用该调试文件。
- 用户已确认正式相关性 Filter 的关键词必须能够从前端配置并写入 PostgreSQL 保存；因此不采用
  “上传请求临时携带关键词”或“继续读取本地 `keyword_pack.txt`”作为正式事实源。当前仓库已有
  System Owner 的 `keyword_packs`、`keywords`、`keyword_pack_items` 及 PostgreSQL Repository，
  但尚无关键词 HTTP Contract/API，也没有冻结 Discovery / Relevance 的业务角色关系。
- 用户进一步澄清：Discovery 是 TikHub 等 Provider 的搜索关键词；Relevance 是所有数据采集渠道在
  Raw 经 Mapper 形成 Canonical 后、写入统一 Content 前执行的共同过滤清洗。TikHub 搜索结果也必须
  经过 Relevance，而不是因为由关键词搜索得到就自动视为相关。
- 当前 TikHub 生产链在 Search Raw/Candidate/Mapper 后直接进入决策、详情/评论与 fenced Content
  Ingestion，没有正式 Relevance 门禁；当前 `collection_candidate_ingestions.result` 也没有
  `filtered` 终态。Excel 的正式可复用实现目前是 `offline_content.py` 的 JSONL 文件包装，尚未提取成
  可被 Collection 与 Import 共同调用的 Provider-neutral 单条 Canonical Relevance Service。

# 成功标准

- [ ] HTTP 上传/登记只接受经批准的 Excel 输入，并通过统一 ArtifactService 保存 Source Artifact。
- [ ] 单个上传 `.xlsx`（文件本身即 ZIP 压缩包）最大 500 MiB；API 必须流式计数和落盘，不能把整个
  上传或 Artifact 读入内存，超过限制返回统一 `413`。
- [ ] 创建请求在同一 PostgreSQL 业务边界建立 Processing Import Batch 与持久化 Import Job，
  返回 `202 Accepted`、Batch ID、Job ID 和 queued 状态；Router 不执行长文件处理。
- [ ] Import Job 使用版本化 Pydantic Payload，由现有 Job Runtime/Worker 认领、接管、重试、
  Fencing、取消和终态转换；未知 Worker 不会认领该类型。
- [ ] Worker 调用生产 Excel Reader/Mapper、生产相关性 Filter/稳定身份 Dedup 和 Stage 8A 正式
  File Import/Content Ingestion，不调用 `imports_test` 作为生产实现。
- [ ] PostgreSQL 只允许零或一条 System Owner 的全局 Relevance 配置，并用真实外键引用一个现有
  Keyword Pack；未配置、Pack 停用或没有有效关键词时，正式 Import/Collection 必须 fail closed。
- [ ] 关键词 HTTP 写入只接受原始 `text`，后端以 `trim → NFKC → casefold` 生成数据库唯一身份；内部
  空白和 `-/_/·` 在数据库身份中保留，而 Relevance 匹配继续忽略它们。
- [ ] Import Job 与 Collection Run 创建时冻结同一全局 Pack 的 ID、版本和实际有效关键词快照；排队/运行
  期间修改全局配置或词包不会改变本次执行。
- [ ] Excel/Import 与 TikHub Collection 调用同一个 Provider-neutral Canonical Relevance Service；
  TikHub Search 未命中时必须通过现有 Provider Runtime 最多请求一次 Detail 再终判；最终未通过者保留
  Raw/Candidate 与 `filtered` 账本事实，不写 Content，也不继续 Comment/Reply 等后续付费动作。
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
- 复用现有 System Keyword Catalog 的最小 Pydantic 写入/读取 HTTP Contract，并建立全局唯一
  Relevance 配置 HTTP Contract，使未来前端能够配置和保存正式过滤关键词。
- Provider-neutral 单条 Canonical Relevance Service、既有 JSONL Filter 包装复用，以及正式
  Excel/TikHub 当前生产链接入。
- 全局 Relevance 配置与 Collection Candidate `filtered` 终态的必要 Schema/Migration。
- Processing Import Batch 创建/详情查询和关联 Job 状态查询。
- `file.import.v1` 等最终确认名称的版本化 Job Payload、Handler 和 Worker Registry 注册。
- 统一 HTTP 错误 Contract、request_id 中间件与 FastAPI/Starlette 异常转换。
- 复用现有生产 Reader/Mapper/Filter/Dedup、Artifact、Job、Content Ingestion/PostgreSQL 来源链。
- API、Contract、Job/Worker、PostgreSQL Integration 与必要安全边界测试。
- 固定 OpenAPI、Orval Client和真正受影响的 Blueprint/API/测试说明。

# 非目标

- 不实现 Stage 8C 采集运行中心 Vue/Figma 页面、列表/KPI/Cursor Query Read Model。
- 不实现 Keyword Pack Vue 配置页面；该页面仍按 Blueprint 留在 Stage 8F，Stage 8B 只生成可供其
  复用的 Orval Client。
- 不实现 Content Center、TikHub 补采页面、Stage 8D—8F 的其他能力、Analysis Persistence 或正式报告页面。
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

## 已确认：正式相关性 Filter 的关键词事实源

- 用户确认关键词应由前端页面配置并写入数据库，以便配置和保存。
- 结合当前单一 Owner/不得新建平行 Repository 的约束，正式实现应复用 System Owner 已有的
  `keyword_packs`、`keywords`、`keyword_pack_items`，而不是新建 Import 专用关键词表。
- Import 创建不允许调用方临时覆盖正式关键词；Service 必须读取全局配置，并在持久化 Job 中冻结足以
  重放和审计的 Pack 身份、版本及实际执行关键词快照，不能让排队中的 Job 因词包随后编辑而静默改变语义。
- `imports_test/keyword_pack.txt` 继续只服务本地调试入口，不成为 HTTP/Worker 生产事实源。

## 已确认：关键词配置页面的 Stage 范围

- 用户确认采用推荐方案：Stage 8B 交付最小 Keyword Pack 写入/读取 HTTP Contract、Import 对 Pack 的
  选择/快照和生成 Orval Client；实际 Vue 配置页面保留到 Stage 8F。
- 本决定保持 Stage 8B 的 HTTP / Job Productization 边界；不得借关键词管理 API 提前实现页面、App
  Shell、Store、E2E 或视觉验收。

## 已确认：Discovery / Relevance 业务定义

- Discovery 只负责向 TikHub 等 Provider 发起搜索、发现候选数据。
- Relevance 是来源无关的 Canonical 内容准入规则；Excel、TikHub 以及未来其他采集渠道都必须执行。
- 正式顺序应是 `Raw/Source Artifact → Candidate（适用时）→ Mapper → Canonical → Relevance →
  Dedup/Decision → Content Ingestion`。Raw/Source Artifact 必须保留，Mapper 保持纯映射，未通过
  Relevance 的内容不得写入 Content。
- 对 TikHub，Relevance 还必须位于不必要的 Detail/Comment/Reply 付费动作之前；但 Search 摘要字段
  不完整或未命中时不能仅凭摘要直接过滤。

## 已确认：TikHub Search 未命中的 Detail 终判策略

- 用户选择召回优先方案：只要 TikHub Search Canonical 没有命中全局 Relevance 关键词，无论是否已观察到
  非空 `title`/`text`，都必须通过现有 Provider Request/Attempt/Raw Runtime 最多请求一次 Detail，重新
  Mapper 为 Canonical 后再执行最终 Relevance 判定。
- Search 已命中时不为了 Relevance 额外请求 Detail，后续是否因现有采集决策需要 Detail 仍遵循既有
  `detail_policy=on_change` 语义。
- Detail 命中后必须复用该次 Detail Canonical 和请求结果继续既有采集决策，不能再发第二次相同 Detail；
  Detail 最终未命中或仍无可匹配文本时记为 `filtered`，保留 Search/Detail Raw 与 Candidate，不写 Content，
  不请求 Comment/Reply。
- Detail 请求或映射发生技术失败时沿用现有 Provider/Job 分类重试与审计语义，不能把技术失败伪装为
  `filtered`。该方案明确以增加未命中候选的 Detail 成本换取更低的相关内容漏失风险。

## 已确认：Relevance 配置作用域

- 用户确认 Relevance 词包是系统全局唯一配置；Collection Plan、Import Request 和其他来源不能分别
  覆盖或绕过它。
- 采用零或一条 System Owner 全局配置记录，并通过 `keyword_pack_id` 外键引用现有 Keyword Pack；不用
  无外键的 `system_settings` JSON UUID，也不给每个 Plan 增加重复关联。
- Migration 不伪造默认词包或关键词。配置记录不存在时，所有正式数据执行 fail closed；部署顺序必须是
  `Migration → 通过正式 API 配置全局 Relevance Pack → 启动/恢复 Scheduler 与 Worker`。
- 每个 Import Job / Collection Run 仍冻结 Pack ID、Pack Version 与实际有效关键词快照；全局唯一不等于
  运行时反复读取可变配置。

## 已确认：关键词数据库身份与 Relevance 匹配规范化

- 用户选择兼容性优先方案：HTTP 只接收关键词原始 `text`，后端先去除首尾空白，再以 Unicode NFKC 与
  `casefold` 生成 `keywords.normalized_text`；前端和其他 HTTP 调用方不能提交或覆盖该字段。
- 数据库身份保留内部空白和 `-/_/·`，因此 `爱 玛` / `爱玛`、`AIMA-500` / `AIMA500` 可以作为不同
  Keyword 父事实保存；`ＡＩＭＡ` / `aima` 仍属于同一数据库身份。
- Relevance 匹配保持既有更强规则：NFKC、casefold 后删除全部空白及 `-/_/·`。同一 Pack 中多个数据库
  Keyword 如果收敛为同一匹配文本，按 Pack 的稳定优先级/顺序保留第一个有效匹配项，避免重复执行；
  数据库和管理 API 仍保留各自词条。
- Stage 8B 不新增 Alias/同义词关系表；业务别名可以作为独立关键词加入全局 Relevance Pack。正式 Alias
  关系语义继续留给 Stage 8F 的独立业务门禁。
- 新 Migration 按批准算法重算已有 `normalized_text`；如果历史数据发生唯一身份冲突，Migration 必须
  fail closed 并报告冲突，由运维/业务人工合并，不能静默删除关键词或自动改写 Pack 关系。

## 已确认：Excel 压缩文件上传上限

- 用户确认单个 `.xlsx` 文件最大为 500 MiB；这里的“压缩文件”就是浏览器实际上传的 Excel 文件本身，
  不是另行上传 `.zip`，也不代表解压后 XML 上限。
- 处理耗时不能只按上传字节估算，还受解压后 XML 总量、有效单元格/行数、共享字符串、样式、磁盘和
  PostgreSQL 写入影响；Batch/Job API 只承诺可查询阶段/进度/统计，不在缺少容量基准时承诺 ETA。
- 仓库当前最大已跟踪 Excel 样例约 14.4 MiB、131,320 输入行，ZIP 解压后约 100.6 MiB，整体约 7 倍，
  最大单成员压缩比约 10.7:1；该样例只是校准证据，不是 500 MiB 文件的性能承诺。
- 为避免 500 MiB 上传同时导致 API/Worker 读取 500 MiB 内存，正式实现必须增量扩展现有
  ArtifactService/ArtifactStore 为有界流式写入和读取，不能新建平行文件存储体系。

## 已确认：Import Job Attempt Deadline 与重试恢复语义

- 用户选择保持当前 Job Runtime 的标准全量重试语义：Import Job 单次 Attempt Deadline 固定为
  30 分钟（`timeout_seconds=1800`），最大 Attempt 固定为 10（`max_attempts=10`）。
- 每个新 Attempt 都从冻结的 Source Artifact 和 Relevance 快照重新执行完整 Reader/Mapper/Filter/Dedup/
  Ingestion 链，不把多次 Attempt 的运行时间或处理中间进度累计为一个 5 小时工作窗口。
- 500 MiB 是 HTTP 接受的单文件上限，不是 30 分钟内完成的容量或 SLO 承诺；若同一输入每次都稳定超过
  Deadline，Job 在第 10 次超时后终态失败。API/文档不得承诺 ETA。
- 每次失败的业务事务必须回滚；重试依靠稳定内容身份和数据库约束幂等收敛。所有 Batch/Content 等业务
  可见提交必须在同一事务验证当前 Job Fence，使已超时的旧 Token 不能与下一 Attempt 并发提交。
- Stage 8B 不新增跨 Attempt 分段检查点。未来可把“阶段/分块检查点 + 中间 Artifact + 断点续跑”作为
  独立 L3 优化方向，但必须先基于真实容量证据重新冻结公共 Contract、Schema/Migration、分块事务、
  部分数据可见性、Artifact 保留/清理、Fencing 与回滚，不能在本阶段预埋 dormant 实现。

## 后续仍需按顺序冻结的技术/安全边界

- Excel HTTP 传输形态，以及 500 MiB 对应的最大解压总量/单成员/成员数/压缩比仍待冻结。
- 当前认证已正式延期；本 Stage 不把受控环境 API 描述为公网生产就绪。

## Migration、部署与回滚

- 本阶段需要新增正式 Revision：建立零或一条全局 Relevance 配置及 Keyword Pack 外键，并扩展
  Collection Candidate Ingestion 的稳定 `filtered` 终态，同时按已批准算法重算已有关键词身份；不修改
  历史 Revision，不为现有数据库伪造词包，历史规范化冲突时拒绝升级而不自动合并数据。
- 部署前数据库必须升级到最终 Head；先通过正式 API 完成全局配置，再同时启动/恢复 API、Worker、
  Scheduler，并共享同一 PostgreSQL 与 ArtifactStore。
- 回滚先停止新导入并等待/处置已有 Import Job，再回退 API/Worker/Contract 代码；若最终没有新 Migration，
  现有 Batch/Job/Artifact/Content 数据无需回填或 downgrade。
- 主要风险是上传资源耗尽、XLSX Zip Bomb、Worker 崩溃窗口、Batch/Job 终态漂移、错误泄露和重放重复；
  必须分别由大小/压缩边界、Artifact 完整性、Fencing/幂等、组合查询和统一异常测试证明。

# 任务

- [x] 调查当前实现和事实源
- [x] 取得正式相关性 Filter 关键词必须由前端配置并写入 PostgreSQL 的用户决定
- [x] 确认 Stage 8B 只交付关键词后端 Contract/API 与 Orval，Vue 页面留在 Stage 8F
- [x] 冻结 Discovery 与跨渠道 Relevance 的业务定义及共同 Canonical 边界
- [x] 冻结 Relevance 词包为系统全局唯一配置，并确定执行快照与 fail-closed 部署边界
- [x] 冻结 TikHub Search 未命中时先请求一次 Detail 再终判的召回优先策略
- [x] 冻结正式关键词数据库身份与 Relevance 匹配的两级规范化语义
- [x] 冻结 Import Job 为 30 分钟、最大 10 次的全量重试，并把断点续跑留作未来独立 L3 优化方向
- [ ] 完整冻结 Excel HTTP 传输、已确认 500 MiB 压缩文件对应的解压边界与 Job Deadline
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
- [Relevance Red] → 修改范围：Provider-neutral Relevance Service、全局配置快照、Excel/TikHub 入口与
  Candidate `filtered` 账本测试
  → 预期结果：同一 Canonical/关键词在所有来源得到同一判定；TikHub Search 未命中只请求一次 Detail
  并复用其 Canonical 终判，最终未命中不写 Content/不请求 Comment/Reply；配置缺失与失效 fail closed
  → 验证方式：目标 Unit + Collection/Import PostgreSQL Integration。
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
- `uv run python scripts/quality/check_docs.py`：退出码 0，Import Job 全量重试与未来断点续跑方向的
  Blueprint/Change 文档入口和本地链接检查通过。
- GitHub 连接器确认 PR `#88/#89` 已合并、当前无开放 PR；当前 main push workflow/status 接口未返回
  可见记录，历史 CI 不替代本 Stage 最终 Head CI。
- Head `f697bc5` 的 CI、Stage 6 XHS、Stage 7 Keyword Packs、Provider Config、Plan Snapshot 与
  Scheduler Runtime 六个 GitHub workflows 均成功；PR Review 线程为 0。该文档 Head 的成功不替代
  后续实现最终 Head CI。

# 文档影响

- 实现后必须同步 Blueprint 04 的 HTTP/Error/Job 当前事实、Blueprint 17 的 Stage 8B 状态、
  Blueprint README 下一阶段、`docs/API接口说明.md` 与 `docs/测试与调试说明.md`。
- Blueprint 02/08/17 与 System/Analysis/Collection README 必须同步跨来源 Relevance 当前边界；
  Blueprint 03 同步全局配置、Candidate `filtered` 终态和 Migration Head。
- Excel Workbook/Exporter、AI Analysis、Provider Operation 没有变化时不修改 Blueprint 13/15/平台文档。

# 交付

- Commit：`a12eac4`（记录 Stage 8B 开发门禁）；后续实现继续使用中文提交。
- PR：Draft PR `#97`（`feature/stage8b-import-http-job → main`）已创建；当前因 500 MiB 上传对应的
  解压安全边界待决定而保持 blocked/draft，最终 CI/Review
  完成后才转 Ready 并正常合并。
- 发布：不部署生产；只交付仓库代码、Migration 状态说明、生成物、测试与合并后 main 证据。
