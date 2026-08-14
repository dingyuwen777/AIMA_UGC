---
schema: rvc-change/v1
id: "CHG-20260814-stage5d-provider-dispatch-recovery"
title: "Stage 5D Provider Dispatch 与恢复"
level: L3
status: ready_for_review
owner: "dingyuwen777"
branch: "feature/stage5d-provider-dispatch"
created: 2026-08-14
updated: 2026-08-14
depends_on:
  - "CHG-20260814-stage5c-provider-persistence-foundation"
affected_areas:
  - "collection"
  - "provider"
  - "jobs"
  - "artifact"
  - "database"
  - "migration"
  - "testing"
  - "ci"
  - "blueprint"
affected_paths:
  - "backend/src/aima_ugc/modules/collection/"
  - "backend/src/aima_ugc/platform/jobs/"
  - "backend/src/aima_ugc/adapters/persistence/postgres/"
  - "backend/src/aima_ugc/modules/collection/tables.py"
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
  - "RawEnvelopeV1"
data_changes:
  - "provider_requests"
  - "provider_request_attempts"
  - "artifacts"
---

# 目标

建立 Stage 5D Provider-neutral 非计费执行与恢复纵切：让一个已持久化的 `reserved`
Provider Attempt 在当前 Job Fencing 约束下进入 `dispatching`，通过既有一次发送
`ProviderClient` 执行 Fake/明确非计费 Transport，保存并验证不可变 Raw，在短事务内
一次性绑定 Attempt→Artifact 并推进 Artifact `stored → linked`。对 CAS、Provider、Raw
和结果事务各崩溃边界提供 Reconciler，已存在且通过完整性校验的 Raw 优先恢复，
否则保守收敛为 `unknown`；旧 Job Token 不得提交可见结果。

# 成功标准

- [ ] 只有当前 `running` Job 的正确 Token，且 Lease/Deadline 未过期时，才能以 CAS 将
  `reserved → dispatching`；伪造、旧或过期 Token 均关闭失败。
- [x] 每个进入 `dispatching` 的 Attempt 最多执行一次正式 `ProviderClient.dispatch`；
  Transport 明确报告未发送时记为 `not_sent`，有确定响应时记为 `completed`，
  发送后结果不可确定时记为 `unknown`。
- [ ] `completed/unknown` 在进程存活时使用正式
  `RawArtifactService → ArtifactService → LocalArtifactStore` 保存 gzip Raw；数据库元数据的
  `pending/stored` 和最终 `linked` 使用真实 PostgreSQL Owner 入口。
- [ ] Attempt 终态、Raw 外键、Provider Request 当前汇总状态/费用和 Artifact `linked`
  在同一短事务提交；该事务提交前再次校验当前 Job Fencing。
- [ ] Reconciler 在 Lease 丢失、Deadline 到达、Job 终态或新 Token 接管时处理遗留
  `dispatching` Attempt：已校验 `stored` Raw 只做恢复和关联，无可用 Raw 则记为
  `unknown + billing_status=unknown + potential_duplicate_charge=true`，绝不复发原 Attempt。
- [ ] 第五条 Revision 不改写 `20260814_0004`；它将 Provider Request 状态收紧为
  `pending/dispatching/completed/not_sent/unknown`，并把 Attempt 来源 Trigger 改为“终态可从
  `null` 一次绑定 Raw，绑定后不可替换或清空”。
- [ ] 真实 PostgreSQL 18.4 集成测试覆盖并发 CAS、旧/新 Token、socket 前后失败、
  Raw 落盘后崩溃、结果事务回滚、Reconciler 和第五条 Migration 双升级路径。
- [x] Stage 1–5C 既有 Contract/Schema、Job Runtime、Artifact、Migration、依赖与公共 HTTP
  行为保持兼容；独立 Stage 5D CI 和受影响文档与实现同步。

# 范围

- `platform/jobs`：新增仅存于 Worker 内存的只读 `JobExecutionFence`，不进 Payload、日志或业务表。
- `modules/collection`：Provider Dispatch Service/Port、终态结果和 Reconciler 生产入口。
- PostgreSQL Adapter：Fencing 验证、Attempt/Request CAS 和汇总、Artifact 短事务元数据
  Gateway、Raw 恢复查询及同事务终态关联。
- 第五条 Migration：Request 状态 Check 与 Raw 一次性绑定 Trigger 修正；不新建业务表。
- Unit、真实 PostgreSQL/Local ArtifactStore Integration、Migration 与独立 CI。
- Collection README、Blueprint 导航/领域/门禁、统一测试说明和根 README 的当前事实。
- `.reliable-vibe-coding/project-context.json` 导航索引随本 Change 提交并在候选事实源
  变化后刷新。

# 非目标

- 不调用 TikHub/官方 API/Apify 或其他付费真实 Provider，不创建 Token/Secret/Probe。
- 不创建临时预算表；global/run/content_comments 预算 Ledger 继续等待 Content 父事实和
  已批准的费用语义。
- 不注册具体 Collection Job Payload/Handler；Stage 6 在首个平台 Operation/Fixture 批准后组装。
- 不创建 Mapper、Candidate/Ingestion、Content/Comment、Plan/Occurrence/Scheduler、HTTP API、前端或认证授权。
- 不实现 Artifact 保留/删除、生产备份、容量、SLO/RPO/RTO 或真实外部平台验收。
- 不新增或升级依赖，不修改公开 HTTP/OpenAPI/前端 Client。

# 必须保持不变

- 仓库根是唯一 Python/uv 工程；Python 3.14、PostgreSQL 18 和锁文件版本不变。
- `ProviderRequestV1/ProviderAttemptV1/RawEnvelopeV1` 与固定 JSON Schema 不改；现有
  `ProviderClient` 一次发送和 Raw 路径/脱敏/完整性语义不变。
- Stage 4 Job Claim/Lease/Deadline/Fencing 和 Platform Owner 不变；新 Fence 只是当前上下文的
  内存能力，不持久原 Token。
- Collection 只写 `collection_*`/`provider_*`，Platform Artifact Repository 仍是 `artifacts`
  唯一 Owner 写入口；终态协调仅在同一 Session 组合两个 Owner Repository。
- 外部 I/O 不放在数据库事务；`pending/stored/linked` 和 `reserved/dispatching/终态`
  的崩溃边界保持可对账。
- 第二至第四条 Revision 不改写；Scope/Request/Attempt 已建最终外键和来源链不变。

# 关键决策

## 方案比较与用户决定

1. **方案 A（已批准）**：完成非计费 Provider-neutral 纵切，建立 Fencing/CAS、一次执行、
   Raw/Artifact 终态事务和 Reconciler，但不注册暂无稳定 Operation 的临时 Job Handler。
2. 方案 B：只做数据库状态机与 Reconciler。范围更小，但 ProviderClient→Raw→Artifact 未连通，
   Stage 5 仍未完成，Stage 6 继续 No-Go。
3. 方案 C：同时注册通用 Collection Job Handler。纵切更长，但会在无已批准 Operation
   Adapter/Payload 时建立必然迁移的临时 Contract。

用户于 2026-08-14 明确批准方案 A。

## 状态、Fencing 与恢复

- Provider Request 状态表示最新 Attempt 快照：新建/新预留为 `pending`，CAS 后为
  `dispatching`，终态为 `completed/not_sent/unknown`。新 Attempt 可将旧终态 Request
  重新置为 `pending`；所有历史仍保留在 Attempt 表。
- Request 累计已知 Attempt `estimated_cost/actual_cost`；币种/单位冲突关闭失败，
  `unknown` 仍由 Attempt 的 billing 与 `potential_duplicate_charge` 表达，不伪造实际金额。
- `JobExecutionFence` 只包含 Job ID 和不可回显的当前 Lease Token；每个可见短事务在
  开始并持有 Job 行锁时验证状态、Token、Lease、Deadline 和取消状态。
- CAS 是“允许开始执行”的持久化边界。Transport 在进程存活时能确定请求从未
  进入外部发送边界，允许终态记为 `not_sent` 并按 Contract 清空发送时间；无法取得
  该明确结果的崩溃一律保守记为 `unknown`。
- 恢复时先用确定性 storage key 定位 `stored` Raw，重新校验 SHA-256/大小/gzip/
  `RawEnvelopeV1`。校验成功则恢复原终态并链接；不存在或校验失败则不删除证据，
  Attempt 保守记为 `unknown`。

## Migration、部署与回滚

- 新增 `20260814_0005`，`down_revision=20260814_0004`；表数与字段不变，只新增 Request
  状态 Check 并替换 Attempt 来源 Trigger 函数。
- 无历史状态回填：Stage 5C 只可能有 `pending/reserved`，直接满足新 Check。
- 部署顺序：先停止 Worker/调用方，再 `alembic upgrade head`，然后部署 Stage 5D 代码；
  本 Change 不启用具体平台 Handler，合并后不自动开始采集。
- 回滚前先停调用方并备份。降级到 `0004` 会移除 Request 状态 Check 并恢复旧 Trigger；
  已一次绑定的 Raw 数据不删除，但旧 Trigger 不允许其后续修改。

## 风险与控制

- 本阶段没有费用预留父事实，因此不注册可达的付费 Handler；Fake 可模拟费用快照以
  验证持久化，不得冒充真实扣费验收。
- Raw 落盘与数据库终态不能原子提交；使用 `stored` 状态和 Reconciler 建立可恢复
  中间态，不删除孤儿证据制造通过。
- 终态事务锁 Job 后才写 Attempt/Request/Artifact，且不持锁等待网络/文件 I/O；
  集成测试验证与 Heartbeat/Claim 的并发关系。

# 任务

- [x] 调查最新 main、Active Change、Stage 5 Blueprint、Stage 5C Migration/Repository、
  Job Fencing、Artifact 生命周期、ProviderClient/Raw 和测试/CI 事实。
- [x] 比较数据库分步、Provider-neutral 纵切和临时 Job Handler 三个方案，由用户确认方案 A。
- [x] Red：建立 Dispatch Service 状态语义 Unit Test，并确认因生产入口缺失而失败。
- [x] Red：建立 PostgreSQL Fencing/CAS、Raw 终态、Reconciler 和 Migration 行为测试，
  并确认因 Stage 5D 行为未实现失败。
- [x] Green：新增 Job Fence、Dispatch Service/Port、PostgreSQL 事务 Gateway/Repository、
  Raw 恢复与第五条 Migration。
- [x] Refactor：目标单元测试全绿后只整理状态映射、来源查询和错误语义，不扩大到具体 Provider/Handler。
- [x] 同步 Collection README、Blueprint 导航/02/03/04/06/07、统一测试说明、根 README、
  质量入口和独立 Stage 5D CI。
- [ ] 执行需求符合性与代码质量两阶段复核，取得本地/CI/PR/合并后 main 新鲜证据并归档。

# 验证

## 计划

- Unit：`uv run pytest tests/unit/collection/test_provider_dispatch.py tests/unit/jobs -q`。
- PostgreSQL/Artifact Integration：`uv run pytest tests/integration/collection/test_provider_dispatch.py -q`。
- Collection/Job 回归：`uv run pytest tests/unit/collection tests/integration/collection tests/unit/jobs
  tests/integration/jobs tests/contracts/test_provider_v1.py -q`。
- Migration：空库 `base → head`、`head → base → head`、`20260814_0004 → head`、
  `head → 20260814_0004 → head`、`alembic current/check`及 Check/Trigger 检查。
- 静态/质量：Ruff format/check、mypy、架构、Table Owner、Secret、文档和 Contract 漂移/兼容门禁。
- 构建/回归：Wheel、仓库通用 CI 与 Stage 4/5A/5B/5C/5D 独立 CI。

## 新鲜证据

- Red：`tests/unit/collection/test_provider_dispatch.py` 首次运行因生产模块不存在而
  `ModuleNotFoundError`；PostgreSQL 纵切测试首次运行因正式
  `PostgresArtifactMetadataGateway` 不存在而失败，均在实现对应生产入口后转绿。
- 质量复核新增“stored 元数据对应文件缺失”回归测试，先稳定复现未包装的
  `FileNotFoundError`，再由 `RawArtifactService` 统一转换为 `RawArtifactIntegrityError`；
  Reconciler 因而能保守收敛为 `unknown`，未知编程异常仍继续传播。
- `python -m pytest -p no:cacheprovider tests/unit/collection/test_provider_dispatch.py
  tests/unit/collection/test_provider_recovery.py -q`：退出码 0，`6 passed`。
- `python -m pytest -p no:cacheprovider tests/unit/collection tests/unit/jobs
  tests/contracts/test_provider_v1.py -q`：退出码 0，`31 passed`。
- `python -m pytest -p no:cacheprovider --basetemp=.runtime/pytest-stage5d-raw
  tests/integration/collection/test_raw_artifact.py -q`：修改前退出码 0，`3 passed`；新增文件缺失
  回归后与 Recovery Unit 合并复验退出码 0，`7 passed`。
- `ruff format --check backend tests scripts 20260814_0005`、`ruff check`、
  `mypy backend/src/aima_ugc`：退出码 0；114 个文件格式通过、Ruff 无问题、Mypy 对
  77 个源码文件无问题。
- 架构、Table Owner、Secret、文档、Contract 生成与兼容门禁：全部退出码 0；固定
  OpenAPI/Canonical/Provider Schema 无漂移。
- `uv lock --check && uv build --wheel`：退出码 0；生成
  `dist/aima_ugc-0.1.0-py3-none-any.whl`，ZIP 清单包含 Stage 5D 新模块且无运行时缓存，
  当前环境直接 `import aima_ugc` 输出 `0.1.0`。
- 本机全量 Unit/Contract/Raw 尝试得到 `57 passed, 1 failed`；唯一失败是 Windows 未授予
  创建目录符号链接的 `WinError 1314`，失败发生在既有 Local Store 测试 fixture，非产品断言。
- 本地 PostgreSQL 18.4 容器已就绪，但 Windows 锁定环境中的 psycopg 在建立连接前报告
  `no pq wrapper available / libpq library not found`，因此本地 Stage 5D PostgreSQL、Migration
  和 Alembic 结论保持未验证，等待 Linux CI 新鲜证据；测试容器和临时目录已清理。
- 前端本地 Typecheck 在测试前因 `frontend/node_modules/@typescript/native` 未安装而失败；
  本 Change 不修改前端或依赖，完整 npm 门禁等待 CI 的 `npm ci` 环境。

# 文档影响

- 需同步 Stage 5D 已建能力、生产/测试入口、非计费边界、第五条 Migration、
  Raw 一次性绑定和 Stage 6 Go/No-Go。
- 无公开 HTTP API、OpenAPI 或前端行为变化，`docs/API接口说明.md` 和生成 Client 不受影响。

# 交付

- Commit：未创建。
- PR：未创建。
- 发布：本 Change 不启用真实 Provider 或具体 Collection Handler，不部署。
