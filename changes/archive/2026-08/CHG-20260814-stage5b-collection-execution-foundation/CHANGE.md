---
schema: rvc-change/v1
id: "CHG-20260814-stage5b-collection-execution-foundation"
title: "Stage 5B Collection Run/Scope 父事实"
level: L3
status: done
owner: "dingyuwen777"
branch: "feature/stage5b-collection-execution-foundation"
created: 2026-08-14
updated: 2026-08-14
depends_on:
  - "CHG-20260814-stage4-job-runtime"
  - "CHG-20260814-stage5a-provider-raw-foundation"
affected_areas:
  - "collection"
  - "database"
  - "migration"
  - "testing"
  - "ci"
  - "blueprint"
affected_paths:
  - "backend/src/aima_ugc/modules/collection/"
  - "backend/src/aima_ugc/adapters/persistence/postgres/"
  - "backend/src/aima_ugc/database_schema.py"
  - "migrations/versions/"
  - "tests/unit/collection/"
  - "tests/integration/collection/"
  - "scripts/quality/"
  - "docs/blueprint/"
  - "README.md"
  - ".github/workflows/"
contracts: []
data_changes:
  - "collection_runs"
  - "collection_scopes"
---

# 目标

建立 Stage 5B Collection 执行父事实：用第三条 Alembic Revision 创建
`collection_runs` 与 `collection_scopes`，以真实外键把每个 Run 绑定到唯一 Job，并提供事务由调用方
持有的唯一 Collection Repository 和最小创建 Service。该来源链为后续按最终外键建立
`provider_requests.scope_id → collection_scopes.id` 提供稳定父表。

# 成功标准

- [x] `collection_runs.job_id` 是 `jobs.id` 的非空唯一外键，不接受不存在的 Job。
- [x] 本阶段 Run 只接受 `manual/api/backfill`；`scheduled` 在 Plan/Occurrence 父事实建立前关闭失败。
- [x] `collection_runs` 保存冻结配置、六种既定状态、计数、错误与时间字段；计数受非负约束。
- [x] `collection_scopes` 保存 Blueprint 既定身份、状态、分页、进度、统计和时间字段，并以
  `(run_id, platform, source_type, source_value, operation_group)` 唯一约束防止重复 Scope。
- [x] Collection Service 在一个调用中创建 queued Run 与其 queued Scopes；重复 Scope 身份在写库前
  返回稳定领域错误，数据库仍保留最终唯一约束。
- [x] 两张表只有 `collection` Owner，Router、Provider 和其他模块不能直接写表。
- [x] PostgreSQL 18 集成测试覆盖真实 FK、唯一约束、JSONB/default、Repository 读取和事务回滚。
- [x] 第三条 Revision 覆盖 `base → head`、`20260814_0002 → head` 及两种 downgrade/re-upgrade。
- [x] Stage 1–5A 既有 Contract、Schema、Migration、接口、依赖、锁文件和合法行为不变。
- [x] 独立 Stage 5B CI、Blueprint、模块 README 和测试说明与实现同步。

# 范围

- `modules/collection`：Run/Scope 稳定记录、创建输入、Repository Port、领域错误和最小创建 Service。
- `adapters/persistence/postgres`：事务由调用方持有的唯一 Collection 写入/查询 Repository。
- `database_schema.py`：注册 Collection Owner 表。
- `migrations/versions/20260814_0003_*`：只新增 `collection_runs`、`collection_scopes`、约束和索引。
- Unit 与真实 PostgreSQL 18 Integration 测试、独立 CI。
- Stage 5 当前事实、测试入口、后续依赖和阶段边界的最小文档同步。

# 非目标

- 不创建 `collection_plans`、`collection_schedule_occurrences`、`manual_plan_id` 或 `occurrence_id`；
  不支持 `scheduled` Run，不实现 Scheduler/misfire/Occurrence 防重。
- 不创建 `provider_requests`、`provider_request_attempts`、Candidate/Ingestion、预算账户或费用 Ledger。
- 不注册 Collection Job Payload/Handler，不实现 Worker 执行、Run/Scope 状态转换或分页状态机。
- 不接真实 Provider/网络，不改变 Stage 5A Provider Contract、Raw 路径或 Artifact 生命周期。
- 不新增 HTTP API、前端页面、认证授权、依赖、配置、数据回填或生产部署。
- 不自行冻结 Blueprint 尚未批准的 Scope 完整状态枚举；本阶段创建入口只写 `queued`。

# 必须保持不变

- 仓库根是唯一 Python/uv 工程；Python 3.14、PostgreSQL 18 和锁定依赖版本不变。
- 模块化单体与 `Router → Service → Port → Repository`、`Provider → Raw → Mapper → Canonical →
  Ingestion` 方向不变。
- Stage 4 Job Runtime 的 Payload、Claim/Lease/Fencing/Deadline/事件语义与 Platform Owner 不变。
- Stage 5A Provider/Raw Contract、一次发送 Transport、Fake 与 Artifact 语义不变。
- 公共 HTTP、OpenAPI、Canonical、Provider JSON Schema 和前端生成 Client 不变。
- 外部 HTTP 不进入数据库事务；本 Change 本身不执行外部 I/O。
- 不提交 Secret，不削弱现有架构、Owner、Secret、文档或 Contract 门禁。

# 关键决策

## 方案比较与用户决定

1. **方案 A（已批准）**：Stage 5B 只建立 Collection Run/Scope 父事实；仅支持
   `manual/api/backfill`，省略尚无真实父表的 Plan/Occurrence 外键列。后续父表到位时以附加
   Migration 增加最终外键。
2. 方案 B：同一 Change 同时建立 Run/Scope 与 Provider Request/Attempt 四表。能一次贯通来源链，
   但会把两个独立 Owner/状态机和更多崩溃边界压入单个 L3，评审与回滚面过大。
3. 方案 C：优先实现真实 HTTP Transport。它不解决 Provider 持久化依赖的父表缺口，也不能在预算
   CAS/Fencing 完成前安全启用真实付费发送。

用户于 2026-08-14 明确批准方案 A。Stage 5B 完成后 Stage 5 仍为进行中；下一独立 L3 才可建立
Provider Request/Attempt 持久化和 `scope_id` 最终外键。

## 数据与接口

- `collection_runs` 采用 Blueprint 5.6 的字段子集，只省略本阶段没有真实父表可引用的
  `manual_plan_id/occurrence_id`；禁止保留无外键 UUID 作为占位。
- `collection_runs.job_id` 以数据库 FK + unique 表达一 Job 一 Run；Handler 未来通过反向关系取 Run，
  不把不可约束的 Run ID 塞入 Job Payload 作为事实源。
- Run 保留 Blueprint 已冻结的 `queued/running/partial_success/succeeded/failed/cancelled` 状态约束。
- Blueprint 尚未冻结 Scope 完整状态枚举；本 Change 不增加白名单，只由创建入口写 `queued`，避免
  静默决定后续执行语义。
- Scope 身份唯一性同时由 Service 预检和 PostgreSQL Unique Constraint 保证；Repository 不提交事务，
  使 Job/Run/Scope 可由上层在同一事务编排。
- 不新增公共 Pydantic/HTTP/Job Contract；内部 dataclass/Protocol 不生成外部 Schema。

## Migration、部署与回滚

- 新增第三条 Revision，`down_revision=20260814_0002`；无历史数据回填、无依赖升级。
- 部署前必须先执行 `alembic upgrade head`，再启用未来会创建 Collection Run 的调用方；本 Change
  不注册生产调用方，因此合并本身不会开始采集。
- 无后续外键依赖且确认无须保留 Run/Scope 数据时，可 downgrade 到 `20260814_0002` 并回退代码；
  已产生真实数据时 downgrade 会删除两表，必须先停相关调用方、备份并由 Owner 明确批准。
- 本 Change 不处理未来 Plan/Occurrence 列的回滚；它们将属于独立附加 Migration。

## 风险与控制

- Job 与 Run/Scope 需要同事务创建时，上层必须共用 SQLAlchemy Session；Repository 的 caller-owned
  transaction 语义由测试固定。
- 仅有父事实不等于执行闭环；未实现 Worker 状态机前不能把 queued Run 宣称为可运行采集。
- Scope 状态白名单延期是明确边界，不代表任意状态已获业务批准；后续状态机 Change 必须先固化枚举
  与转换，再添加数据库约束。

# 任务

- [x] 调查当前 Schema、Stage 4/5A 实现、Blueprint 父表依赖、状态事实和迁移/CI 模式。
- [x] 用户确认方案 A、范围、非目标和后续拆分。
- [x] Red：先建立 Service/Table/Repository/真实 PostgreSQL 行为测试，并确认因生产入口缺失失败。
- [x] Green：完成模型、Port、Service、Table、Repository、Schema 注册和第三条 Migration 的最小实现。
- [x] Refactor：全绿后只整理重复与公共导出，不扩大状态机或 Provider 范围。
- [x] 同步 Collection README、Blueprint 导航/阶段门禁、统一测试说明和独立 Stage 5B CI。
- [x] 执行需求符合性与代码质量两阶段复核，修复严重/重要问题。
- [x] 取得本地/CI/PR/合并后 main 新鲜证据并归档 Change。

# 验证

## 计划

- Red/目标 Unit：`uv run pytest tests/unit/collection/test_collection_execution.py -q`。
- PostgreSQL Integration：`uv run pytest tests/integration/collection/test_collection_repository.py -q`。
- Collection 相关回归：`uv run pytest tests/unit/collection tests/integration/collection
  tests/contracts/test_provider_v1.py -q`。
- Migration：空库 `base → head`、`head → base → head`、`head → 20260814_0002 → head`、
  `alembic current`、`alembic check` 和目标表/FK/Unique/Index 检查。
- 静态/质量：Ruff format/check、mypy、架构、Table Owner、Secret、文档门禁。
- Contract/兼容：Contract 生成漂移和兼容检查，确认 OpenAPI/Canonical/Provider Schema 未变化。
- 构建/完整回归：Wheel、仓库通用 CI 与 Stage 5B PostgreSQL 18 独立 CI。

## 新鲜证据

- 初始 Red：锁定 Python 3.14 环境从仓库根直接导入 `aima_ugc` 成功，SQLAlchemy 为锁定的
  2.0.52；`pytest tests/unit/collection/test_collection_execution.py -q` 在生产实现尚未创建时因
  `ModuleNotFoundError: aima_ugc.modules.collection.execution` 收集失败，退出码 1。此前缺失 pytest
  与受控环境拒绝临时注入源码路径均属于环境准备，不计作 Red；环境已通过 `uv sync --offline
  --locked` 从现有缓存恢复，未修改 `pyproject.toml` 或 `uv.lock`。
- 本地 Green：`pytest tests/unit/collection tests/integration/collection/test_raw_artifact.py
  tests/contracts/test_provider_v1.py -q` 退出码 0，22 passed；无跳过。
- Ruff format/check、mypy（72 个源码文件）、架构、Table Owner、Secret、文档和 Contract
  生成/兼容门禁均退出码 0；两张新表 Owner=`collection`，OpenAPI/Canonical/Provider Schema 无漂移。
- 本地 PostgreSQL Integration 首次执行在 Fixture 建连前因默认
  `.runtime/secrets/postgres_password` 不存在产生 3 个 setup error；没有删除或跳过测试。宿主 Docker
  无响应，仓库又明确禁止 SQLite 替代；真实 PostgreSQL 18.4、Migration 和数据库约束证据等待
  Stage 5B CI。
- Alembic offline SQL 生成按仓库 `migrations/env.py` 的既有 online-only 门禁被明确拒绝，不计作
  Migration 验证；不会修改门禁绕过。Migration 的 upgrade/downgrade 与 `alembic check` 等待 CI。
- `uv lock --check --offline` 与 `uv build --wheel --offline` 退出码 0；Wheel 大小 78,659 bytes，
  ZIP 清单实际包含 Collection execution/tables 和 PostgreSQL collection Repository。
- PostgreSQL dialect 对已注册完整 metadata 的两张新表 DDL 编译成功，长 Scope Unique 名按
  SQLAlchemy/PostgreSQL 规则确定性截断；这只证明 DDL 可编译，不代替真实 Migration。
- 全量 Unit/Contract/API 本地运行有 33 passed、17 setup error；错误均发生在 pytest 读取宿主或
  workspace 临时目录时返回 `WinError 5`，没有测试断言失败。尝试使用仓库内独立 basetemp 仍被
  同一 ACL 拒绝；保留原测试，等待通用 Linux CI 复验。
- 首轮 PR CI：通用 CI、Stage 4 和 Stage 5B 均通过；Stage 5A 原工作流因扫描整个
  `tests/integration/collection` 而误收集新增 PostgreSQL 测试，在未配置 Secret 的 Stage 5A 环境
  产生 4 个 setup error（其余 22 passed）。失败日志确认不是断言或生产代码错误。修复将 Stage 5A
  测试入口精确收窄到原有 Provider Client、Raw Artifact 和 Provider Contract 文件；Stage 5B
  PostgreSQL 测试继续只由配置真实 PostgreSQL 18.4 的新工作流执行，未删除或跳过任何测试。
- PR #21 最终 head `e0138631edce10622be173b8febf83995e1b2576`：通用 CI
  `31775146007`、Stage 4 `31775146003`、Stage 5A `31775146022`、Stage 5B
  `31775146048` 全部 completed/success；PR 状态 CLEAN/MERGEABLE。
- PR #21 squash 合并到 main，merge commit
  `755291ff39e486d584e2b6e5e303b8a97f1240c1`。远端实现分支已删除，本地 main 与 origin/main
  均指向该提交且工作区干净。
- 合并后 main 通用 CI `31775286324` completed/success：Backend/Repository 34+13+3 passed，
  Ruff/mypy/Contract/Wheel、前端 lint/type/test/build、Windows bootstrap、Stage 2/3A PostgreSQL
  门禁全部成功。
- 合并后 main Stage 5B `31775286224` completed/success：Collection Unit/Provider Contract
  19 passed，真实 PostgreSQL Collection Integration 7 passed；`base → head → base → head`、
  `20260814_0002 → head → 20260814_0002 → head` 与每次 `alembic check` 均通过；真实
  Job FK、Run/Scope Unique 和目标索引检查通过。
- 合并后 main Stage 4 `31775286278`、Stage 5A `31775286330` 均 completed/success；Stage 5A
  测试边界修正后既有 Provider/Raw 门禁保持通过。

# 文档影响

- `modules/collection/README.md`：补充 Run/Scope 生产入口、事务边界和当前限制。
- `docs/blueprint/README.md`、`06`、`07`：固化用户批准的 Stage 5B 边界、已完成事实和下一 L3。
- `docs/测试与调试说明.md`：补充真实 PostgreSQL 18 目标测试与未覆盖项。
- `README.md`：仅当当前阶段摘要/验证入口受影响时做最小同步。
- Blueprint 02/03/04 的长期最终语义不改写；只在实现与现有事实冲突时最小修正。

# 交付

- 基线 main：`236e07c063efce58af5416a6f08adcd736f8785c`。
- 实现分支：`feature/stage5b-collection-execution-foundation`。
- 实现 Commit：`d2056f9`（`建立 Stage 5B Collection 执行父事实`）、`e013863`
  （`修正 Stage 5A 测试边界`）。
- 实现 PR：[PR #21](https://github.com/dingyuwen777/AIMA_UGC/pull/21)，squash merge commit
  `755291ff39e486d584e2b6e5e303b8a97f1240c1`。
- Change 收尾分支：`chore/archive-stage5b-collection-execution-foundation-change`。
- Change 状态：done，归档至
  `changes/archive/2026-08/CHG-20260814-stage5b-collection-execution-foundation/`。
- 发布：未部署；本 Change 只建立数据库与库级入口。
