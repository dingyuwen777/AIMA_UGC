---
schema: rvc-change/v1
id: "CHG-20260814-stage5c-provider-persistence-foundation"
title: "Stage 5C Provider 持久化基础"
level: L3
status: in_progress
owner: "dingyuwen777"
branch: "feature/stage5c-provider-persistence-foundation"
created: 2026-08-14
updated: 2026-08-14
depends_on:
  - "CHG-20260814-stage5a-provider-raw-foundation"
  - "CHG-20260814-stage5b-collection-execution-foundation"
affected_areas:
  - "collection"
  - "provider"
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
  - "docs/测试与调试说明.md"
  - "README.md"
  - ".github/workflows/"
contracts:
  - "ProviderRequestV1"
  - "ProviderAttemptV1"
data_changes:
  - "provider_requests"
  - "provider_request_attempts"
---

# 目标

建立 Stage 5C Provider 持久化基础：用第四条 Alembic Revision 按 Blueprint 最终字段创建
`provider_requests` 与 `provider_request_attempts`，通过真实外键把逻辑 Request 绑定到
`collection_scopes`、把 Attempt 的可选 Raw 引用绑定到 `artifacts`，并提供事务由调用方持有的
幂等 Request 与非计费 `reserved` Attempt 创建入口。该单元只建立来源链和后续 Dispatcher 所需
持久化父事实，不提前实现 Stage 5D 的发送状态机。

# 成功标准

- [ ] `provider_requests.scope_id` 是 `collection_scopes.id` 的非空外键，数据库不重复保存
  `run_id/platform`，Repository 根据 Scope→Run 事实校验 `ProviderRequestV1` 的来源一致性。
- [ ] `provider_requests` 使用 `(scope_id, request_fingerprint)` 唯一约束实现逻辑请求幂等；同一
  Contract 重放返回原记录，冲突 ID、Provider 或稳定请求内容关闭失败。
- [ ] `provider_request_attempts` 具有最终 `provider_request_id/raw_artifact_id` 外键、
  `(provider_request_id, attempt_no)` 与 `(id, provider_request_id)` 唯一约束，以及 Blueprint 的
  Dispatch/Billing/时间/金额一致性约束。
- [ ] 本阶段 Request 只以 `pending` 创建且数据库暂不增加完整状态白名单；创建入口只原子建立
  `not_billable + reserved` Attempt，并同步递增 Request `attempt_count`。
- [ ] 数据库 Trigger 禁止已有 Request 的 Scope 身份被改写、已有 Attempt 的 Request 来源身份被
  改写，并在 Attempt 离开 `reserved` 后冻结其 Request/Raw 来源引用。
- [ ] 两张表唯一写 Owner 为 `collection`；Repository 不提交事务，不执行网络或文件 I/O。
- [ ] PostgreSQL 18 集成测试覆盖最终 FK/Unique/Check、幂等与冲突、并发 Attempt 序号、来源冻结和
  caller rollback；第四条 Revision 覆盖 `base → head`、`20260814_0003 → head` 及双向重建。
- [ ] Stage 1–5B 既有 Contract、JSON Schema、Artifact/Job 行为、依赖和锁文件保持兼容，独立
  Stage 5C CI、README、Blueprint 和测试说明与实现同步。

# 范围

- `modules/collection`：Provider 持久化记录、Port、稳定领域错误和最小 Service；Collection Owner
  Table 定义扩展到 Provider Request/Attempt。
- `adapters/persistence/postgres`：caller-owned transaction 的 Provider Request/Attempt Repository。
- `database_schema.py`：注册两张新表。
- `migrations/versions/20260814_0004_*`：新增两表、最终外键/约束/索引和来源身份 Trigger。
- Unit 与真实 PostgreSQL 18 Integration 测试、独立 Stage 5C CI。
- Stage 5 当前事实、生产/测试入口、后续 Stage 5D 边界的最小文档同步。

# 非目标

- 不实现 `reserved → dispatching → completed/not_sent/unknown` 状态转换、Job Fencing/CAS、
  Attempt Reconciler、Raw 关联写入或 Artifact `stored → linked`；这些属于 Stage 5D。
- 不执行 Provider Client/Transport、网络、SDK 或文件读取，不接 TikHub 或其他真实 Provider，
  不注册 Collection Job Payload/Handler/Worker。
- 不创建预算账户/Reservation Ledger、`collection_run_cost_totals`、Candidate/Ingestion、Content、
  Plan/Occurrence/Scheduler、HTTP API、前端页面或认证授权。
- 不冻结 Blueprint 尚未批准的完整 Provider Request/Scope 状态机；`pending` 只是本阶段唯一创建值。
- 不修改 Stage 5A Provider Pydantic/JSON Schema，不新增依赖、配置、数据回填或生产部署入口。

# 必须保持不变

- 仓库根是唯一 Python/uv 工程；Python 3.14、PostgreSQL 18 和全部锁定依赖版本不变。
- 模块化单体及 `Service → Port → Repository`、`Provider → Raw → Mapper → Canonical →
  Ingestion` 方向不变；两张新表 Owner 固定为 `collection`。
- `ProviderRequestV1/ProviderAttemptV1`、固定 Provider JSON Schema、一次发送 Transport/Fake 与 Raw
  Envelope/路径/脱敏语义不变。
- Stage 4 Job Runtime 的 Claim/Lease/Fencing/Deadline 与 Platform Owner 不变；本 Change 只保存
  后续 Fencing 所需来源链，不读取或更新 Job Lease。
- Stage 5B Run/Scope Schema、创建语义和 `manual/api/backfill` 边界不变；禁止改写第三条 Revision。
- Artifact ID/元数据/生命周期继续由 `ArtifactService`/Platform Owner 管理；本 Change 只建立可空 FK，
  不调用 `mark_linked`。
- 公共 HTTP/OpenAPI、Canonical、前端生成 Client、Secret 边界和外部 I/O 事务边界不变。

# 关键决策

## 方案比较与用户决定

1. **方案 A（已批准）**：Stage 5C 只建立最终 Provider 两表、幂等 Request、非计费 reserved Attempt
   和来源身份约束；Stage 5D 再实现 Dispatcher/Fencing/Raw 生命周期。范围最小、可逆，不在重试策略
   尚未建立时猜测完整 Request 状态机。
2. 方案 B：在一个 L3 同时完成 Provider Schema、Dispatcher、Job Fencing、Raw/Artifact 协调和
   Reconciler。可以一次关闭 Stage 5，但跨数据库/文件/网络崩溃边界和评审面过大。
3. 方案 C：只创建 `provider_requests`。改动更小，但无法形成 Attempt→Raw 父链，独立价值不足且会
   增加一条低价值 Migration。

用户于 2026-08-14 明确批准方案 A。本 Change 完成后 Stage 5 仍为进行中，不能宣称 Provider
Dispatcher、费用预算、Raw 关联或真实平台已经完成。

## 数据与兼容

- 两表字段采用 Blueprint 03 第 5.8/5.9 节最终列；`run_id/platform` 只通过 Scope 推导。
- 逻辑幂等键固定为 `(scope_id, request_fingerprint)`；Request ID 冲突、同指纹不同 Provider/稳定
  内容视为数据冲突，不静默复用。
- Repository 创建 Request 时使用 `ProviderRequestV1` 事实源，但返回内部持久化 Record；不创建新的
 公共 Contract 或生成 Schema。
- `attempt_count` 同时充当下一个 Attempt 序号分配事实；原子更新 Request 后插入 `reserved`
  Attempt，事务失败整体回滚。本阶段创建值固定为 `billing_status=not_billable` 且费用为零。
- Request `status` 保持 Blueprint 的 `text not null`，本阶段只写 `pending` 且暂不加枚举 Check；
  Stage 5D 冻结完整状态后以附加 Migration 收紧，不能重写第四条 Revision。
- Scope/Request/Attempt 来源冻结由数据库 Trigger 兜底；未来 Candidate 表建立后再附加“已有
  Candidate”约束，不预造不存在的表。

## Migration、部署与回滚

- 新增第四条 Revision，`down_revision=20260814_0003`；只创建空表/函数/Trigger，无历史回填。
- 部署顺序为先 `alembic upgrade head`，再部署可能调用 Stage 5C Repository 的代码；当前没有生产
  调用方，合并不会启动采集。
- 在没有下游 FK 且确认不保留 Provider 数据时，可 downgrade 到 `20260814_0003` 后回退代码；若已
  产生数据，downgrade 会删除两表，必须先停调用方、备份并由 Owner 明确批准。
- Stage 5D 只能追加新 Revision，不得改写第四条 Revision。

## 风险与控制

- SHA-256 指纹冲突或同键异 Provider/参数关闭失败，并保留数据库 Unique 作为并发最终防线。
- Request/Attempt 写入使用 caller-owned transaction，不把外部 HTTP 或 Artifact 文件操作放入事务。
- 本阶段的 `reserved` 不代表真实付费预算已预留；只允许创建 `not_billable` Attempt，真实 HTTP
  Attempt 仍必须等待最终预算/Fencing 门禁。
- 新表可能增长较快，但本阶段不宣称容量或性能目标成立；只建立 Blueprint 已列查询索引。

# 任务

- [x] 调查最新 main、Active Change、Stage 5 Blueprint、Provider Contract、Collection/Artifact/Job
  边界和现有 Migration/CI 模式。
- [x] 用户确认方案 A、范围、非目标和 Stage 5D 后续边界。
- [x] Red：建立 Service/Table/Repository/真实 PostgreSQL 行为测试并确认因生产入口缺失失败。
- [x] Green：完成模型、Port、Service、Table、Repository、Schema 注册、第四条 Migration 和 Trigger。
- [x] Refactor：全绿后只整理重复、映射和错误命名，不扩大状态机或外部 I/O 范围。
- [x] 同步 Collection README、Blueprint 导航/阶段门禁、统一测试说明和独立 Stage 5C CI。
- [x] 执行需求符合性与代码质量两阶段复核，修复严重/重要问题。
- [ ] 取得本地/CI/PR/合并后 main 新鲜证据并归档 Change。

# 验证

## 计划

- 目标 Unit：`uv run pytest tests/unit/collection/test_provider_persistence.py -q`。
- PostgreSQL Integration：`uv run pytest tests/integration/collection/test_provider_repository.py -q`。
- Collection 回归：`uv run pytest tests/unit/collection tests/integration/collection
  tests/contracts/test_provider_v1.py -q`。
- Migration：空库 `base → head`、`head → base → head`、`head → 20260814_0003 → head`、
  `alembic current`、`alembic check` 及表/FK/Unique/Check/Index/Trigger 检查。
- 静态/质量：Ruff format/check、mypy、架构、Table Owner、Secret、文档和 Contract 漂移/兼容门禁。
- 构建/回归：Wheel、仓库通用 CI 与 Stage 4/5A/5B/5C 独立 CI。

## 新鲜证据

- Red：`.venv\Scripts\python.exe -m pytest -p no:cacheprovider
  tests/unit/collection/test_provider_persistence.py -q` 在生产模块尚不存在时以
  `ModuleNotFoundError: aima_ugc.modules.collection.provider_persistence` 失败；不是环境失败。
- Green/回归：同一目标命令 `2 passed`；Collection Unit + Provider Contract `21 passed`；Collection
  Unit + 全部 Contract + API `30 passed`。
- 静态与质量：Ruff format/check、mypy（74 个源码文件）、架构、9 表 Owner、Secret、文档、Contract
  生成漂移与兼容检查均退出 0；`uv lock --check` 退出 0。
- Wheel：构建 `aima_ugc-0.1.0-py3-none-any.whl`（103 entries，84801 bytes），检查不含
  `.runtime`，在隔离 venv `pip --no-deps` 安装后直接导入输出 `0.1.0`。
- 本地限制：真实 PostgreSQL 目标测试共 8 项均在 setup 因缺少
  `.runtime/secrets/postgres_password` 停止，Docker daemon 查询超时；等待 Stage 5C Linux/PostgreSQL
  18.4 CI 提供 Migration、触发器和并发证据。
- 完整 Windows Unit 共 `35 passed, 1 failed`；唯一失败为系统未授予创建目录符号链接权限
  `WinError 1314`，未跳过或修改测试，等待 Linux 通用 CI 复核。

# 文档影响

- `README.md`：Stage 5C 当前能力、限制和下一 Stage 5D。
- `modules/collection/README.md`：Provider 持久化生产入口、事务语义和测试方式。
- `docs/blueprint/README.md`、`06`、`07`：固化用户批准的 5C/5D 切分与当前阶段事实。
- `docs/测试与调试说明.md`：新增 PostgreSQL 18 目标测试和未覆盖边界。
- Blueprint 02/03 的最终业务/Schema 语义不改写；只在实现需要澄清阶段落点时做最小同步。

# 交付

- 基线 main：`bdc1e2895e3336edc9b3c2c3b29d3df95ed6b718`。
- 实现分支：`feature/stage5c-provider-persistence-foundation`。
- Commit：尚未创建。
- PR：尚未创建。
- 发布：未部署；本 Change 只建立数据库和库级入口。
