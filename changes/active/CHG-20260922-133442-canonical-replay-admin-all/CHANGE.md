---
schema: coding-change/v1
id: CHG-20260922-133442-canonical-replay-admin-all
title: 管理员页面支持全量 Canonical 重筛入库
level: L3
status: ready_for_review
owner: codex
branch: feat/canonical-replay-admin-all
created: 2026-09-22
updated: 2026-09-22
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - administration
  - frontend
  - contracts
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/adapters/persistence/postgres/canonical_replay.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_http.py
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/contracts/http.py
  - frontend/src/features/admin-configuration/
  - frontend/e2e/admin-configuration-figma.spec.ts
  - tests/api/test_canonical_replay.py
  - tests/integration/database/test_canonical_replay_repository.py
  - tests/integration/database/test_migration_data_lifecycle.py
  - migrations/versions/20260922_0058_canonical_replay_all_requests.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - docs/product/02_当前产品能力与用户流程.md
  - docs/03_API接口说明.md
  - docs/blueprint/03_数据库与文件存储.md
  - docs/blueprint/04_后端任务API与前端.md
  - backend/src/aima_ugc/modules/ingestion/README.md
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/operations/02_4000万历史迁移与Analysis Run运行手册.md
contracts:
  - POST /api/v1/canonical-replays/all
data_changes:
  - 新增 canonical_replay_all_requests，并为 canonical_replay_runs 增加可空父请求与序号
  - 自动选择全部受支持的 linked canonical-content.v1 并拆分为多个既有 Replay Run/Job
---

# 变更摘要

- **要解决的问题**：管理员修改 Brand、Vehicle 或 Alias 后，现有 Replay 只能由调用方知道并提交 1—100 个 Canonical Artifact ID；管理页面没有入口，也没有面向“全部历史 Canonical”的安全编排。
- **拟议修改**：新增管理员级全量 Replay 创建 Contract，由后端在一个短事务中稳定选择全部合法 Canonical，按 100 个 Artifact 一组创建既有持久 Replay Run/Job；品牌与车型页面在“新增品牌”左侧增加带确认的“重筛入库”按钮，使用最大受支持行批次 1000。
- **预期结果**：管理员一次确认即可把全部历史 Canonical 排队重筛；每个 Job 继续受既有 Artifact、Fencing、Checkpoint、幂等和 Content Owner 边界保护，可由多个 Worker 并行领取。

# 背景、现状与问题

## 背景

Issue #560 固化了用户对“全部历史 Canonical”和“尽可能快”的决定。用户明确要求实现、验证并合并主分支。

## 当前现状

- `POST /api/v1/canonical-replays` 要求显式传入 1—100 个 `artifact_ids`，这一上限限制的是单个 Replay Run 的文件数量，不是内容行数。
- Worker 对 Run 内 Artifact 连续流式读取，并以 `batch_size` 1—1000 分批提交 Content/Evidence；现有管理前端没有获取 Artifact ID 或发起 Replay 的入口。
- 后端已经能对 Excel v2、Data Import Pure Canonical Chunk v2 和 TikHub Discovery Search Attempt 三类来源做 fail-closed 分类。

## 问题、根因或约束

只在前端增加按钮无法构造合法请求；把数据库 Artifact ID 或目录扫描规则复制到浏览器会破坏 Owner 和安全边界。最小充分方案必须由后端负责选择、冻结、分组和原子排队，前端只表达管理员确认。

# 目标、成功标准与非目标

## 目标

为管理员提供一次性触发全部历史 Canonical 重筛入库的正式入口，并在现有安全上限内尽量提高可并行处理能力。

## 成功标准

- [x] “重筛入库”位于“新增品牌”左侧，提交前明确说明范围、耗时和不触发 Provider/AI。
- [x] 后端稳定选择全部受支持的 linked `canonical-content.v1`，按每组最多 100 个 Artifact 创建多个 Replay Run/Job，批大小固定为 1000。
- [x] 同一客户端幂等键和同一冻结输入返回原批次；输入集合、参数或创建者漂移时失败关闭。
- [x] 空历史集合安全返回零任务；页面给出准确反馈且不伪造成功。
- [x] 现有显式 Artifact Replay API、Job 类型、Content Owner、来源追溯和错误语义保持兼容。
- [x] Contract/API、真实 PostgreSQL、前端用户工作流、生成物、文档和独立 Review 取得本轮证据；当前 PR required checks 作为合并硬门禁。

## 非目标

- 不提高单 Run 的 100 Artifact 安全上限，不让一个 Job 无界加载全部 Artifact。
- 不在浏览器读取 Artifact 存储目录或拼装数据库 lineage。
- 不重新读取 Excel、不请求 TikHub、不自动触发 AI、Export 或 Report。
- 不部署生产环境，不执行生产数据操作。

## 必须保持不变

- `POST /api/v1/canonical-replays` 的请求/响应兼容。
- 只有管理员可以创建 Replay；Audit、Job、Catalog Snapshot、Fencing、Checkpoint 与 Content Owner 继续生效。
- 每个 Canonical Artifact 在一次全量请求中至多出现一次，并保持确定性顺序。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 数据范围 | 全部符合当前 Replay 来源规则的历史 Canonical | 用户决定、Issue #560 | 后端负责选择，不要求管理员输入 ID |
| 性能 | 100 Artifact/Run + 1000 rows/transaction，所有 Run 一次排队 | 用户“尽可能快”要求、既有 Contract 上限 | 多 Worker 可并行；单 Worker仍顺序执行 |
| 幂等 | 一次全量请求冻结选择摘要并派生多个子 Run 幂等键 | 既有 Replay 幂等规则 | 网络重试不重复创建，输入漂移 409 |
| 兼容 | 新增独立全量创建路由 | 既有显式选择 API 已有调用方 | 不改变旧 Contract |
| 回滚 | 回滚前后端入口并按正式流程 downgrade 新 Migration | 新父记录表与子 Run 归属字段 | 已排队 Job 应先完成或取消，再评估 downgrade |

# 修改方案与决策依据

1. Repository 用一条确定性 SQL 查询覆盖三类合法 lineage，返回按 `created_at, id` 排序的 Artifact ID/来源类型。
2. Repository 在同一事务内冻结全量选择、选择摘要与目录快照，按 100 个分组复用既有 Run/Job 创建边界；父请求持久化幂等事实，请求重复时返回原摘要，选择漂移则拒绝。
3. 新增 `POST /api/v1/canonical-replays/all` 请求/响应 Contract 并重新生成 OpenAPI/TypeScript Client。
4. 管理页面增加确认弹窗和按钮，薄 API 只提交幂等键；提交期间禁用重复操作，成功反馈 Artifact/任务数量，空集单独说明。
5. 同步当前产品、API/前端与 Ingestion 文档，移除“尚无前端入口”的过时事实。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 新增品牌左侧提供手动全量重筛按钮 | #560 / AC1 | satisfied | `CatalogConfigurationPanel.vue`；Playwright 校验按钮水平位置、确认与反馈，25/25 通过 |
| R2 | 全部历史 Canonical 自动选择并按 100 个分组排队 | #560 / AC2 | satisfied | PostgreSQL 覆盖三类来源与 101 Artifact → 2 Run，Replay Repository 6/6 通过 |
| R3 | 在现有安全边界内尽可能快 | #560 / AC2 | satisfied | 每个 Run 固定 `batch_size=1000`、全部子 Job 同事务入队；文档明确多 Worker 并行与单 Worker 顺序边界 |
| R4 | 幂等、空集合、权限和错误失败关闭 | #560 / AC3 | satisfied | 父表保存选择摘要；非空/空集漂移均 409；API 管理员校验和前端同键重试回归通过 |
| R5 | 旧 API 与 Provider/AI/Content Owner 边界保持不变 | #560 / AC4 | satisfied | 旧路由测试继续通过；Worker/Job type 未改，选择只读 PostgreSQL 来源账本，不新增 Provider/AI 调用 |
| R6 | 验证、文档、PR、CI 和 main 合并闭环 | #560 / AC5 | explicitly_deferred | 目标 API/PostgreSQL/Migration/Browser、生成物、构建、文档与 Review 已通过；current-head required checks、受保护 merge、main-fresh 与归档属于 Ready 后的真实交付门禁，不能预先伪造 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 分组、摘要、空集和页面提交状态 |
| 接口 / 契约 | required | 新路由 Pydantic/OpenAPI/generated client；旧 API 兼容 |
| 集成 / 持久化 / 运行依赖 | required | 真实 PostgreSQL 三类来源选择、101+ 分组、幂等/漂移/事务 |
| 用户 / 工作流验收 | required | 管理员按钮位置、确认、成功/空集/失败、重复点击 |
| 跨组件关键路径 | required | Browser → FastAPI → PostgreSQL durable Jobs；Worker 既有路径回归 |
| 外部依赖 / 供应方探测 | not_applicable | Replay 不调用外部 Provider |
| 构建 / 打包 / 运行 | required | 前端 typecheck/build、后端静态检查与相关测试 |
| 文档 / 治理 / 其他 | required | targeted docs、Change completion、独立 Review、PR CI、merge/main-fresh |

# 风险、兼容性与回滚

| 项目 | 结论 | 处理方式 |
| --- | --- | --- |
| 主要风险 | 一次排队任务过多、选择规则漂移、网络重试重复创建 | 保留 100/Run、稳定排序/摘要、同事务与幂等冲突检查 |
| 兼容性 | 向后兼容新增 Contract | 旧显式 Replay 路由和类型不变 |
| 数据 / Migration | 新增全量请求父表和子 Run 归属字段；实际操作会新增持久 Run/Job 与业务入库结果 | Migration 可逆；所有业务写入复用既有 Owner/Job；生产执行由管理员确认 |
| 部署 / 运行 | Worker 数量决定实际并发 | 不在 API 内执行重筛，不隐藏无限并发 |
| 回滚 / 恢复 | 源码回滚移除入口；已建任务先按既有 API/Job 取消或完成，再按正式流程 downgrade | Migration 提供 downgrade；不得在仍有待处理子 Run 时直接回退 |

# 实施与验证计划

- [x] 恢复当前 Contract、Repository、Worker、管理页面和测试事实
- [x] 创建 Issue、任务分支与本 Change
- [x] 先建立 API/PostgreSQL/Browser 失败回归
- [x] 实现全量选择、分组排队、Contract 与管理页面
- [x] 重新生成 OpenAPI 与 TypeScript Client
- [x] 同步受影响文档并执行分层验证
- [x] 完成 Requirement Traceability、Completion Audit 和独立 Review
- [ ] 推送 PR、等待 required checks、合并并归档 Change

# 完成审计

- [x] upstream_re_read：Ready 前重新读取 Issue #560、用户“全部历史 Canonical / 尽可能快”决定、当前 PR #561、产品/API/数据库/前端/Ingestion/运行文档与真实 Contract；五条 AC 无漂移。
- [x] change_coverage：从 Issue #560 独立重建按钮、全量选择、100/Run、1000 rows/batch、幂等/空集/权限、兼容与交付要求，并逐项映射到实现、测试和文档。
- [x] reverse_audit：从前端按钮反查 generated Client → 管理员 Route → Application Service → Repository → 父请求/子 Run/Job → 既有 Worker/Content Owner；从新表反查 Migration、metadata、Repository、测试与数据库文档；无孤立能力。
- [x] unresolved_cleared：R1—R5 均为 `satisfied`；R6 仅把 Ready 后才能发生的 CI/merge/main-fresh/归档按生命周期标为 `explicitly_deferred`，不豁免本轮交付。实际吞吐依赖 Worker、Artifact I/O 和 PostgreSQL/WAL，未虚构生产性能数值。

# 完成证据与状态

## 新鲜证据

| 证据 | 环境 / 命令 | 结果 | 证明了什么 |
| --- | --- | --- | --- |
| V1 | Red：API/PostgreSQL/Browser 新回归，提交 `0341780c` | API 因缺少新 Contract ImportError；新行为尚不存在 | 测试先于实现固定了新公共入口与用户工作流 |
| V2 | `.venv\\Scripts\\python -m pytest tests/api/test_canonical_replay.py -q` | 9 passed | 新旧 Replay HTTP 路由、管理员权限、规范化与委托行为正确 |
| V3 | 独立 PostgreSQL 18.4：`pytest tests/integration/database/test_canonical_replay_repository.py -q` | 6 passed | 三类来源、101→2 分组、1000 批次、Job 数、重复请求、非空/空集漂移与来源预检正确 |
| V4 | 独立 PostgreSQL 18.4：`test_0058_adds_all_replay_parent_without_breaking_existing_runs`；Alembic downgrade/upgrade/current/check | 1 passed；head `20260922_0058`；无待生成操作 | 既有 Run 可升级，新父事实可关联，downgrade 保留旧 Run，metadata 与 Migration 一致 |
| V5 | `npm --prefix frontend run lint`；`test -- --run`；`build`；管理员 Playwright spec | lint 通过；32 files / 227 tests；production build 通过；25/25 Browser 通过 | 前端类型/组件/构建及按钮位置、确认、成功、空集和同键重试成立 |
| V6 | Ruff changed scope、Mypy `backend/src`、Contract generate `--check`/compatibility、docs/docs-facts | Ruff clean；Mypy 364 files clean；Contract 与文档门禁通过 | Python 静态质量、生成物兼容、权威文档与机器事实一致 |
| V7 | Windows 扩大回归 `pytest tests/unit tests/contracts tests/api` | 1395 passed / 8 skipped / 10 failed | 失败限于既有 Windows/POSIX 专用用例、Windows 文档临时 Git 行为和 Git 忽略 Provider 原始输出；目标 API 9/9、干净 Linux PR CI 仍为合并硬门禁 |
| V8 | base `f3f7e9cf` → 当前工作树独立要求/实现反向审查 | `NO_FINDINGS_WITHIN_SCOPE` | Contract、Schema、Owner、幂等、并发边界、回滚与测试证据未发现阻塞 Finding |

## 未验证内容与剩余风险

- 未在真实生产数据规模和生产 Worker 数量下测量总耗时、P95、Artifact Store/临时盘吞吐或 WAL；本次只保证有界拆分与可并行领取，不承诺具体完成时长。
- 未执行生产 Migration、生产数据重筛、部署或 Release，均不在本次授权范围。

## 交付状态

- 分支：`feat/canonical-replay-admin-all`；PR #561；Requirement Source #560。
- 早期治理提交 `b962b5a0`、Red 提交 `0341780c`；实现与 Ready 提交待创建。
- 早期 PR 的 Completion 失败符合 `in_progress` 状态预期；当前 revision 推送后重新等待全部 required checks。
- 合并、Issue Closure、Change Archive、main-fresh 与分支清理待 PR checks 通过后执行。
