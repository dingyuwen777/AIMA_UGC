---
schema: rvc-change/v1
id: CHG-20260820-stage8a-unified-manual-ingestion
title: Stage 8A Unified Manual Ingestion Foundation
level: L3
status: in_progress
owner: AI coding agent
branch: feature/stage8a-unified-manual-ingestion
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - ingestion
  - provenance
  - postgres
  - debug-entrypoints
  - documentation
affected_paths:
  - changes/active/CHG-20260820-stage8a-unified-manual-ingestion/
  - backend/src/aima_ugc/modules/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/providers/imports_test/
  - backend/src/aima_ugc/adapters/providers/tikhub_test/
  - backend/src/aima_ugc/contracts/provider/
  - backend/alembic/
  - tests/
  - docs/blueprint/
  - docs/测试与调试说明.md
contracts:
  - CanonicalContentV1
  - CanonicalCommentV1
  - ProviderRequestV1
  - ProviderAttemptV1
data_changes:
  - ProcessingImportBatch
  - provider_requests
---

# Stage 8A：Unified Manual Ingestion Foundation

## 1. 背景与当前机器事实

Stage 1—7 与临时 P1 已闭环，Stage 8 是当前正式开发阶段。本 Change 只处理 Stage 8A，不进入 Stage 8B/8C，也不开发正式前端。

开始时从 `main@09ff597f6dc28d06c36017c3c9a8af062fe1e425` 重新读取当前仓库后确认：

1. `PostgresContentRepository` 对持久化 Canonical 强制要求真实 `provider_attempt_id` 与 `raw_artifact_id`，并校验 Raw Artifact 确实属于该 Attempt；不能为 Excel 伪造 ID，也不能删除这层校验。
2. `ProviderAttemptV1` Contract 本身允许非 HTTP 执行事实；`http_status` 等 HTTP 字段并非所有成功 Attempt 都必须存在。
3. 当前 PostgreSQL `provider_requests.scope_id` 为非空 FK，固定指向 `collection_scopes`；因此任何现有 Provider Request 都被迫属于 Collection Run/Scope。
4. Excel 手工导入如果为了复用 Attempt 而制造虚假的 Collection Run/Scope，会把“文件导入”错误记录为“外部采集运行”，污染 Collection 语义。
5. `contents` 已有 `(platform, external_content_id)` 唯一约束；正式 Content Repository 已负责 Current、Observation、Version、Metric 与来源历史收敛，不应新增 Excel/TikHub 私有 Writer。
6. `imports_test` 与 `tikhub_test` 当前默认 file-only 行为必须保持；Stage 8A 的数据库模式必须是显式可选能力。

## 2. 已批准的上游决策

以下决定继承 Blueprint 17 与用户本轮明确批准，不重新讨论：

- Excel 是首版主要数据入口，TikHub 是辅助发现、补漏和补充详情/评论入口。
- PostgreSQL 是唯一业务事实库；Excel 文件不是数据库。
- 所有来源必须在 Mapper 前后收敛为 `CanonicalContentV1 / CanonicalCommentV1`，Canonical 之后统一走 `ContentIngestionService -> PostgresContentRepository -> PostgreSQL`。
- 禁止 Excel/TikHub/debug 私有 Repository、私有 DB Writer 和直接 SQL 绕过 Owner Repository。
- 采用 Processing / Import Batch 作为一次 Excel 业务处理的最小父事实；它不复制 Content/Comment 业务字段。
- `imports_test`、`tikhub_test` 永久保留；默认 file-only，显式数据库模式才访问 PostgreSQL。
- 数据库模式只连接已经由开发者启动的 PostgreSQL 18；不管理 Docker，不自动执行 Migration。
- 文件阶段成功而数据库阶段失败时保留文件并明确失败；允许幂等重试。
- 最终 Content 去重键保持 `(platform, external_content_id)`；跨 Excel/TikHub 的同一内容收敛为一个 Current Content，同时保留合法的新 Observation/Version/Metric/来源历史。

## 3. 目标与可观察成功标准

本 Change 建立唯一、真实、可审计、可重放的手工文件来源链：

```text
Excel Source
→ Input Artifact
→ ProcessingImportBatch
→ Provider Request / Attempt（File Import 合法父级）
→ Raw Artifact / Candidate
→ existing Excel Mapper
→ CanonicalContentV1 / CanonicalCommentV1
→ ContentIngestionService
→ PostgresContentRepository
→ PostgreSQL
```

成功标准：

1. file import 不制造 Collection Run/Scope，不伪造 Attempt/Raw ID；
2. imports_test 与 tikhub_test 默认仍不要求数据库，既有文件产物兼容；
3. 显式 DB 模式使用正式来源链和正式 Ingestion；
4. DB 不可用或 Schema 不匹配时显式失败，文件产物保留；
5. 同一 Excel 重试与 Excel/TikHub 跨来源重复最终只有一个 Current Content；
6. 合法更晚 Observation 仍产生/更新正式历史；
7. PostgreSQL 18 集成、Migration、Contract、Unit 和相关质量门禁有本轮新鲜证据。

## 4. 范围

- Processing / Import Batch 的 Stage 8A 最小机器结构、Repository/Service 与状态流转；
- File Import 合法 Provider Request/Attempt/Artifact/Candidate 来源链；
- 复用现有 Excel Reader、Mapper、关键词清洗、稳定身份去重；
- 复用 `ContentIngestionService` 与 `PostgresContentRepository`；
- imports_test 可选 PostgreSQL 模式；
- tikhub_test 可选 PostgreSQL 模式，优先复用正式 Collection 链；
- 正式 PostgreSQL 配置、连通性和 Schema 前置检查；
- 跨来源去重、历史保留与失败重试验证；
- 只同步真实受影响的 Blueprint/README/测试说明。

## 5. 非目标

不实现 Stage 8B 上传 HTTP API、Stage 8C 采集运行中心、Vue/Figma 正式页面、KPI/Cursor/Content Center、TikHub 补采按钮、Keyword Pack/Collection Plan 页面、完整 Analysis 数据库页面、认证权限、预算系统、Redis/Kafka/RabbitMQ，也不升级无关依赖或做无关重构。

## 6. 来源链方案比较

### 方案 A：制造 Collection Run/Scope，完全复用现有 Provider Request

做法：Excel 导入先建立一个 Collection Run/Scope，再创建现有 Provider Request/Attempt。

优点：Schema 改动最少。

缺点：Collection 当前表达外部数据采集计划/范围；Excel 本地文件读取不是采集 Scope。该方案会制造虚假 Collection 业务事实，使 Collection 页面、审计、统计和未来调度语义混淆。

结论：不采用。

### 方案 B：最小一般化 Provider Request 的父级（推荐）

做法：新增最小 `processing_import_batches` 父事实；`provider_requests` 从“只能属于 collection_scope”一般化为“恰好属于 collection_scope 或 import_batch 之一”。`provider_request_attempts`、Raw Artifact、Candidate、Canonical Source 和 Content 历史来源 FK 全部保持不变。

预期 Schema 约束：

```text
provider_requests.scope_id       NULLABLE FK collection_scopes(id)
provider_requests.import_batch_id NULLABLE FK processing_import_batches(id)
CHECK exactly_one(scope_id, import_batch_id)
```

优点：

- 不伪造 Collection；
- 不增加第二套 Attempt/Artifact 来源体系；
- Content Repository 的严格来源校验和历史 FK 无需弱化；
- 现有 Collection Request 仍保留 scope_id，兼容既有数据；
- File 与 HTTP Provider 在 Attempt 之后共用同一来源链，审计和重放边界清楚。

代价：Provider Request Contract/Repository 需要做向后兼容的一般化，并需要 forward Migration。

结论：采用，前提是后续代码核查未发现更窄且语义正确的现有 Owner API。

### 方案 C：新增 FileAttempt/FileArtifact 专用来源体系

做法：为 File Import 新建独立执行表，并修改 Canonical/Content Source 使其同时能指向 Provider Attempt 或 File Attempt。

优点：文件语义完全独立。

缺点：复制 Attempt/Artifact 概念；Content/Observation/Version/Metric 的来源 FK、校验、Contract 和 Repository 都要扩大；迁移与兼容范围显著大于当前需求。

结论：除非真实 Schema 证明方案 B 不成立，否则不采用。

## 7. Schema / Migration 与兼容策略

预计需要一个新的 forward Alembic Revision：

1. 建立 Stage 8A 最小 `processing_import_batches`；
2. 为 `provider_requests` 增加可空 `import_batch_id` FK；
3. 将 `scope_id` 改为可空；
4. 增加恰好一个父级存在的 CHECK；
5. 保持所有现有 Collection 数据 `scope_id != NULL, import_batch_id = NULL`，不重写历史；
6. Provider Attempt、Raw Artifact、Candidate、Content 来源 FK 保持原表和原 ID 语义。

Migration 必须验证 base→head、上一正式 revision→head、downgrade/re-upgrade、`alembic check`，并检查 FK/Unique/Check/Index。

公共兼容原则：现有 Collection 调用仍可用原来的 scope/run 语义；新字段只用于合法 File Import。不得用默认值让无父级 Provider Request 偷渡通过。

## 8. Processing / Import Batch 最小边界

只保存一次处理需要的父事实，不复制 contents/comments：

- 批次稳定 ID；
- 对应 Job；
- 输入 Artifact；
- 状态；
- 最小计数/错误摘要（仅实现实际执行需要的统计）；
- 创建/更新时间；
- 只有 Stage 8A 实际用到时才增加可选 Collection Run 关联。

状态以 Blueprint 17 为上限，只实现代码真实需要的状态转换，不提前为页面堆字段。

## 9. TDD 实施任务

1. **来源 Schema Red** → 新增失败测试证明：File Import 不能在不伪造 Collection Scope 的情况下建立合法 Provider Request/Attempt；现有 Collection Request 必须继续合法。
2. **Migration Green** → 实现 ProcessingImportBatch 与 Provider Request XOR 父级；运行 PostgreSQL 18 Migration 往返门禁。
3. **File Import Red** → 用失败测试表达 Input Artifact → Batch → Attempt/Raw → Mapper → Canonical → Ingestion 的完整来源要求及失败重试语义。
4. **File Import Green** → 只增加最小正式 Service/Repository，复用现有 Reader/Mapper/Ingestion。
5. **imports_test Red/Green** → 默认 file-only 零 DB 依赖；显式 DB 模式保留文件再调用正式 File Import；DB 失败显式返回失败。
6. **tikhub_test Red/Green** → 默认行为不变；DB 模式只调用现有 Collection/Ingestion，不从导出 JSONL 建平行 Writer。
7. **PostgreSQL Integration** → 重复 Excel、Excel+TikHub 同 ID、更晚 Observation、数据库失败后重试四类真实 PG18 场景。
8. **Refactor/Review** → 需求符合性后再做代码质量复核，不扩大范围。
9. **Docs** → 代码事实验证后才把 Stage 8A “目标未实现”更新为真实当前行为。

## 10. 数据库与调试运行门禁

- `WRITE_TO_DATABASE=False` 或等价显式配置必须为默认值；默认路径不得连接 PostgreSQL。
- DB 模式读取仓库正式连接配置并验证 PostgreSQL 可访问与 Schema 已迁到代码需要的 revision；不执行 Docker 或 Alembic 管理动作。
- DB 阶段失败不能静默降级为成功的 file-only；文件阶段产物不可删除。
- 所有 PostgreSQL Integration 使用真实 PostgreSQL 18，不用 SQLite 替代。
- Stage 8A 普通验证使用 Fake/Fixture，不发真实 TikHub 付费请求。

## 11. 风险与控制

- **历史兼容**：`scope_id` 可空后由 XOR CHECK 保证旧 Collection 与新 Import 二选一，防止无父级/双父级脏数据。
- **来源审计**：不改变 Content 的 provider_attempt/raw_artifact 严格校验；File Import 也必须先真实创建 Attempt 与 Raw Artifact。
- **重复写入**：依赖正式 `(platform, external_content_id)` Unique/Owner Repository，不用批次内去重替代数据库最终约束。
- **部分失败**：文件与数据库阶段分离记录；DB 失败允许同一业务输入重试而不制造第二 Current Content。
- **运维**：调试入口绝不管理 PostgreSQL 容器/Migration；Schema 不满足时尽早失败并给出可诊断错误。
- **性能**：不为 Stage 8A 引入新队列/缓存；90k Excel 读取继续复用 P1 已验证的流式实现。

## 12. 回滚与部署顺序

部署顺序：先停止新 File Import DB 模式使用 → 备份/确认数据库 → 应用 forward Migration → 部署兼容代码 → 验证 Schema/来源链 → 才允许打开调试 DB 模式。

回滚使用普通 Git revert 与 Alembic downgrade，不改写历史 Revision。若新 Import 数据已存在，downgrade 前必须先停止 File Import，并明确处理引用 `import_batch_id` 的新数据；不得直接删除仍被来源链引用的 Batch/Request/Attempt。

## 13. 验证计划与本轮证据

计划命令以仓库实际工作流/依赖文件为准，至少包含：

- `rvc.py` Active Change 校验/冲突检查；
- Stage 8A Unit/Contract；
- PostgreSQL 18 Integration；
- Alembic base→head、previous→head、downgrade/re-upgrade、`alembic check`；
- Ruff format/check、mypy（按受影响范围）；
- Architecture/Table Ownership/Secret/Docs 门禁；
- PR CI。

本节只记录本轮实际执行的命令、Run/Job、退出码和通过/失败数量；未执行前不写“通过”。

## 14. 文档影响

代码完成并验证后，仅按真实影响同步：Blueprint 17/02/03/04/06/13、imports_test/tikhub_test README、`docs/测试与调试说明.md`。Blueprint 15 只有 Analysis Contract 真的受影响才改；否则记录“不受影响”的依据。

## 15. Commit / PR / 发布状态

- 开始 main：`09ff597f6dc28d06c36017c3c9a8af062fe1e425`
- 开发分支：`feature/stage8a-unified-manual-ingestion`
- Change：本文件
- PR：尚未创建
- CI：尚未产生 Stage 8A 新鲜证据
- 发布/合并：未发生
