---
schema: coding-change/v1
id: CHG-20260928-172120-replay-rule-reconciliation
title: 历史重筛按最新品牌车型规则收敛有效结果
level: L3
status: proposed
owner: codex
branch: feature/649-replay-rule-reconciliation
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - vehicles
  - jobs
  - database
  - migration
  - contracts
  - frontend
  - documentation
  - performance
affected_paths:
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/bootstrap/canonical_replay_*.py
  - backend/src/aima_ugc/bootstrap/worker.py
  - backend/src/aima_ugc/contracts/
  - migrations/versions/
  - tests/integration/ingestion/
  - tests/integration/database/
  - tests/api/
  - tests/e2e/
  - docs/product/02_当前产品能力与用户流程.md
  - docs/blueprint/02_采集系统与数据标准化.md
  - docs/appendix/08_数据入口与统一入库实现.md
  - backend/src/aima_ugc/modules/ingestion/README.md
contracts:
  - Canonical Replay request lifecycle/status/result
  - Content business visibility
  - Durable Job payload and registry
data_changes:
  - PostgreSQL Schema and Alembic Migration
  - replay reconciliation checkpoint and reversible visibility ledger
---

# 变更摘要

- **要解决的问题**：当前全量历史重筛只处理新规则命中的 Canonical；未命中项被跳过，旧规则曾命中的 Content 仍处于业务有效集合。
- **拟议修改**：在全部子 Replay 成功后，用请求级命中身份并集执行独立、可恢复的批量对账；未命中 Content 退出业务有效数据，命中或后续新鲜写入可恢复。Raw、Canonical、Content Version 和审计历史不物理删除。
- **预期结果**：管理员修改品牌/车型规则并完成“重筛入库”后，声音广场、工作台、导出和后续业务任务只能消费服从该次冻结规则的有效结果；原 Canonical 读取、识别和批量入库热路径不降低吞吐。

# 背景、现状与问题

## 背景

Issue #649 固化了用户在 2026-09-28 的决定：全量“重筛入库”完成后，当前有效筛选结果必须完全服从最新冻结的品牌/车型规则，未命中结果应从当前业务有效数据中移除；同时不得降低现有数据处理速度。

## 当前现状

- `canonical_replay_worker.py` 对 `resolution.matched == false` 的行直接跳过，只累计 `rows_filtered_out`。
- `canonical_replay_seen_content` 已按 `(run_id, platform, external_content_id)` 保存命中身份，但作用域是单个子 Run。
- 一次全量请求可以拆成多个 Run/Shard；同一 Content 可能跨 Artifact 或子 Run 重复出现。
- Content 查询统一复用 `content_has_active_source` 判断来源可见性；该谓词当前不表达“最新成功全量重筛未命中”。
- 当前撤回账本可恢复 Replay 修改的 Current、自动 Brand/Vehicle Evidence 与 Replay 可见性归属，但未记录“规则对账导致退出/恢复”的可逆状态。
- 产品与模块文档明确写明当前 Replay 不实现规则收窄后的退出监测，这是本 Change 要改变的现状边界。

## 问题、根因或约束

根因不是单个 `continue`，而是全量重筛没有请求级的“命中集合发布”阶段：子 Run 只知道自己的输入和命中，无法在尚有其他子 Run 未完成时安全判断某个 Content 是否在整个请求中未命中。直接在逐行热路径删除会产生跨 Run 顺序错误、半完成可见状态，并破坏取消/撤回和性能边界。

## 不修改的后果

管理员收窄或修正别名后，旧规则曾命中的 Content 仍会出现在业务页面、统计和导出中；“重筛入库”无法成为当前有效结果的权威快照，规则维护与数据库实际结果持续漂移。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 未命中 Canonical 当前只被跳过 | `backend/src/aima_ugc/bootstrap/canonical_replay_worker.py` 的 `_commit_batch` | 不能把现有行为误认为已删除 |
| E2 | 全量 Replay 按最多 100 Artifact 拆分 Run，并可继续拆分 Shard | `PostgresCanonicalReplayRepository`、Replay Worker 与正式文档 | “任一命中保留”必须在请求级收敛 |
| E3 | 已有持久 `canonical_replay_seen_content` 保存每个 Run 的命中身份 | `canonical_replay_tables.py`、0051 Migration | 可以复用当前热路径事实，避免新增逐行命中写入 |
| E4 | Content 业务可见性统一由来源谓词消费 | `adapters/persistence/postgres/content_visibility.py` 及调用点 | 退出有效库应进入统一读边界，不能逐页面打补丁 |
| E5 | Replay 支持取消、成功后撤回、重试、接管和贡献账本 | `canonical_replay_reversal_worker.py`、0059/0067/0068 Migration、集成测试 | 新对账必须可逆并服从后续新鲜写入 |
| E6 | 多个业务/分析/审计表通过 FK 引用 `contents.id`，多数不级联删除 | 当前 SQLAlchemy Tables 与 Migration | 物理删除 Content 会破坏审计与回滚，不是最小充分方案 |
| E7 | 用户明确要求不影响数据处理速度 | 当前会话与 Issue #649 / AC6 | 不得给逐行热路径增加数据库往返；需要基线和对照证据 |

## 推断与待确认

- 合理推断：用户所说“从数据库中删除”指从当前业务有效结果中退出，而不是销毁 Raw、Canonical、Version 和审计历史；Issue #649 已将这一边界写成稳定验收条件。该解释与项目可追溯、可撤回的长期规则一致，不阻塞施工。
- 待确认：修改前后精确吞吐与新增对账速率需要在同一 PostgreSQL 环境、同一 Fixture 和资源条件下实测；未取得证据前不能宣称性能无回归。

# 目标、成功标准与非目标

## 目标

让一次成功的全量 Canonical Replay 原子发布最新规则快照，使业务有效 Content 完全由该请求的命中身份并集约束，并保持可恢复、可重试和可追溯。

## 成功标准

- [ ] 全量请求成功后，未被任何子 Run 命中的 Content 退出所有统一业务读取；任一子 Run 命中即保留。
- [ ] 失败、取消或仍在运行的请求不发布半完成对账；成功后撤回恢复请求前状态，后续新鲜写入优先。
- [ ] 后续符合当前规则的正式写入或更新重筛能恢复 Content，不产生永久“墓碑”。
- [ ] Raw、Canonical、Version、来源与审计事实保留，公共 Contract/Schema/生成物保持一致。
- [ ] 原 Replay 处理热路径没有按行新增 SQL 往返，修改前后同环境基准证明吞吐无有意义退化；新增对账阶段有独立批次性能证据。
- [ ] 相关自动测试、Migration、文档、Review、required CI、合并后 main-fresh 与 Change 归档闭环完成。

## 范围

- 请求级 Replay 命中集合发布和未命中业务退出。
- 可逆状态、持久 checkpoint、Job/Fencing/取消/接管。
- 统一业务可见性消费方、必要的 Contract/统计/前端文案。
- Migration、测试、性能基准和长期文档同步。

## 非目标

- 不物理删除 Raw、Canonical、Content Version、来源或审计记录。
- 不请求 TikHub、不重新上传 Excel、不自动触发 AI。
- 不升级依赖、Runtime、框架或更换持久 Job 架构。
- 不执行生产 Migration、生产数据清理、Release 或 Deploy。

## 必须保持不变

- Content 身份、Mapper/Canonical/Owner 边界、人工锁和后续新鲜写入优先级。
- Durable Job 的 Lease、Fencing、Heartbeat、Attempt Deadline、取消、重试和进度语义。
- 全量 Replay 现有批处理、分片、自适应批次和后台资源槽；不得降低原热路径吞吐。
- Raw/Canonical/Audit 保留与现有成功后撤回能力。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Ingestion 编排请求级对账，Content Owner 提供统一可见性/状态写入，Vehicles 继续拥有 Evidence | E2、E4、E5 | 不让 Router、页面或 Replay 直接写其他 Owner 的表 |
| 接口与契约 | 复用现有“重筛入库”入口；仅在用户需要观察对账状态/计数时扩展兼容字段 | #649 / AC1、AC5 | 必须同步 Pydantic/OpenAPI/生成 Client |
| 数据与迁移 | 新增可逆规则退出状态、请求级对账 checkpoint/统计与必要索引；保留历史事实 | E3、E5、E6 | 新 Alembic Migration，需 upgrade/downgrade 验证 |
| 错误与失败语义 | 所有子 Replay 成功后才发布；对账作为持久后台阶段失败可重试，不能把半完成状态报告为成功 | E2、#649 / AC3 | 聚合状态必须包含对账阶段 |
| 兼容性 | 旧请求按旧语义保留；新请求只在具备完整对账元数据时启用新语义 | E5、E6 | Migration 不猜测历史请求命中全集 |
| 部署与回滚 | 普通应用发布需先应用 Migration；代码回滚必须与 Migration/新状态兼容，生产执行不在本任务授权范围 | 项目长期门禁 | 在运维文档记录版本边界，不执行生产操作 |

# 修改方案与决策依据

## 最小充分方案

1. 建立失败测试与修改前性能基线
   → 修改范围：Replay/Content PostgreSQL Integration、API/工作流测试与性能 Fixture
   → 预期结果：当前版本明确重现未命中仍可见，并得到原热路径 SQL 数/吞吐基线
   → 验证方式：目标 pytest 与同环境基准命令

2. 增加请求级、可逆的业务有效性对账状态
   → 修改范围：Content/Ingestion Table、Migration、Repository
   → 预期结果：命中身份可恢复有效，未命中身份可批量退出；每次变更记录请求前状态
   → 验证方式：Migration upgrade/downgrade、Repository Integration、约束/索引检查

3. 在全部子 Replay 成功后排队独立对账 Job
   → 修改范围：Replay lifecycle、Job payload/registry/worker、聚合状态
   → 预期结果：不在逐行热路径做全库差集；批量 checkpoint/fencing 可重试，运行/失败不发布伪成功
   → 验证方式：Worker/并发/接管/取消/分片 Integration 与 API 聚合测试

4. 将统一业务读取和后续新鲜写入接到同一规则状态
   → 修改范围：Content Owner/visibility predicate 及必要投影刷新
   → 预期结果：所有消费方一致排除未命中结果；合法新写入可恢复，不逐页面复制过滤
   → 验证方式：内容查询、工作台、导出/任务选择和 Real Full-stack 关键 Journey

5. 同步 Contract、文档和性能证据
   → 修改范围：Pydantic/OpenAPI/Generated Client（若 Contract 改变）、Product/Blueprint/Appendix/模块 README、Change
   → 预期结果：用户语义、机器事实、实现与验收一致
   → 验证方式：生成一致性、docs checks、Completion Audit、Review、CI

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：请求成功后再做请求级对账 | E1、E2、E3 | 只有请求级并集能正确处理跨 Artifact/Run 的“任一命中保留”，并避免运行中半快照 |
| D2：业务退出而非物理销毁 Content 历史 | E5、E6 | 保留审计与撤回，避免级联破坏；统一读取仍能达到用户观察到的删除结果 |
| D3：独立后台批量 Job | E2、E7 | 必要对账不占逐行热路径，不在 HTTP 或终态回调中执行长事务 |
| D4：统一可见性边界一次接入 | E4 | 声音广场、工作台、导出等现有消费者共同服从，不产生遗漏和第二套规则 |

## 备选方案与取舍

- **逐条 Canonical 未命中立即删除**：未采用。跨 Run 后续可能命中，处理顺序会改变结果；还会在热路径增加删除/查询，无法原子发布。
- **直接物理删除 `contents` 及所有依赖**：未采用。大量审计/分析/来源 FK 不级联，且会破坏 Raw→Canonical→Content 追溯和成功后撤回；代价远高于当前目标。
- **只在声音广场查询临时过滤**：未采用。工作台、导出、AI 任务和其他消费者会继续看到旧结果，无法满足“当前有效结果完全服从”。
- **请求级独立批量对账**：采用。复用已持久命中身份，以最少新增热路径工作得到一致、可恢复的全局结果。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 成功全量重筛后所有当前业务读取排除全请求未命中 Content | #649 / AC1 | not_satisfied | 待实现与验证 |
| R2 | 跨 Artifact/Run 任一命中保留，全部未命中才退出 | #649 / AC2 | not_satisfied | 待实现与验证 |
| R3 | 运行/失败/取消不发布半快照；撤回恢复且后续写入优先 | #649 / AC3 | not_satisfied | 待实现与验证 |
| R4 | 后续合法写入可恢复；重试、接管、分片保持幂等 | #649 / AC4 | not_satisfied | 待实现与验证 |
| R5 | Raw/Canonical/Version/审计保留，Contract/Generated Client 同步 | #649 / AC5 | not_satisfied | 待实现与验证 |
| R6 | 原热路径无按行新增 SQL，吞吐无有意义退化；新增对账批量执行并有性能证据 | #649 / AC6 | not_satisfied | 修改前 101 条已有 Content 重筛基线：测试调用 2.62s、总计 3.74s、SQL `<150`；待实现后同环境对照 |
| R7 | 相关自动测试、Migration、Full-stack、静态/文档/CI 全绿 | #649 / AC7 | not_satisfied | 待验证 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `modules/ingestion/canonical_replay*`、Migration | 请求级对账状态、checkpoint、可逆账本 | 持久恢复与 Schema 约束 | R1-R5 / E2-E6 |
| `bootstrap/canonical_replay_*`、`bootstrap/worker.py` | 排队并执行独立对账 Job | 原子完成与后台批量性能 | R1-R4、R6 / E2、E7 |
| Content Owner/visibility repository | 统一退出/恢复和读取谓词 | 所有消费者一致服从 | R1、R3、R4 / E4 |
| Replay/Content/API/E2E tests | Red→Green、恢复/并发/工作流 | 防止误删、半快照与回归 | R1-R7 |
| Product/Blueprint/Appendix/模块 README | 同步当前用户语义、数据流、失败/恢复与性能边界 | 文档不再描述旧行为 | R5-R7 |
| Change/Issue/PR Evidence | 追溯、性能、Review、CI 与交付闭环 | L3 完成门禁 | R1-R7 |

- [x] 调查当前实现和事实源；新建项目则确认现有资料、目标和硬约束
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据或说明测试例外
- [ ] 完成最小实现，不静默扩大范围
- [ ] 同步受影响的长期文档或明确不适用依据
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 命中并集、状态转换、payload 校验、批次调谐和统计 |
| 接口 / 契约 | required | 请求聚合状态/结果、OpenAPI/生成 Client（若字段变化）与兼容性 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 18 的 FK、索引、事务、Fencing、checkpoint、Migration upgrade/downgrade |
| 用户 / 工作流验收 | required | 管理员点击重筛→运行中心终态→声音广场/工作台看不到未命中内容→撤回恢复 |
| 跨组件关键路径 | required | API→Planner→Replay Run/Shard→Reconciliation→Content visibility→UI/API consumer |
| 外部依赖 / 供应方探测 | not_applicable | Replay 只消费现有 Canonical，不需要请求 TikHub 或其他当前外部事实 |
| 构建 / 打包 / 运行 | required | 后端静态检查、前端 typecheck/build（若生成 Client/页面变化）、Worker Registry 启动装配 |
| 文档 / 治理 / 其他 | required | 文档事实、Change completion、两阶段 Review、required CI、性能基线/对照 |

## 验证计划

- 目标测试：Replay Worker/Repository/Reversal/Reconciliation 的 PostgreSQL Integration；统一 Content visibility 查询；API 聚合状态；相关 Unit/Contract。
- 相关回归：`tests/integration/ingestion`、`tests/integration/database` 的精确目标，再按影响扩展 content/jobs/vehicles；管理员重筛 Real Full-stack Journey。
- 静态检查或构建：Ruff、Mypy、OpenAPI/Orval 一致性；若前端变化则 ESLint、Vitest、Typecheck、Build。
- 专项真实边界：同一 PostgreSQL/Fixture/资源环境记录修改前后 Replay 热路径 SQL 数、批次耗时和吞吐；记录新增对账批次速率与锁等待。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`，PR HEAD required CI，合并后 main-fresh 和 Change Archive Automation。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 高：误退出、跨 Run 顺序错误、半快照、并发覆盖、性能退化 | 请求级并集、终态屏障、Fencing/checkpoint、后续写入守卫、批量 SQL 与基准 |
| 兼容性 | 保持现有入口与合法普通写入；新请求获得新语义，历史请求不补猜 | 版本化 Payload/Schema；不从旧审计推断缺失快照 |
| 数据 / Migration | 需要新增状态/账本/checkpoint/索引，不物理删除历史事实 | 新 Alembic head；执行 upgrade/downgrade 与空库/已有数据验证 |
| 部署 / 运行 | 应用版本与 Migration 必须配套；新增后台任务受现有资源槽约束 | 不执行生产部署，文档记录运行和容量边界 |
| 回滚 / 恢复 | 用户成功后撤回复原请求前有效性；技术回滚需停止新 Job 并按版本兼容顺序处理 | 新状态保留 before/after 归属并受后续写入保护 |

# 文档、依赖、部署与发布影响

- **长期文档**：同步 Product 的“重筛入库”用户语义、Blueprint 的 Replay 数据流、Appendix/模块 README 的对账、恢复与性能边界。
- **依赖 / Runtime**：不新增、删除或升级依赖；沿用 Python/PostgreSQL/SQLAlchemy/Durable Job Runtime。
- **配置 / Secret**：不新增配置或 Secret；批次上限优先沿用项目现有资源检测/后台写槽。
- **部署 / Release**：需要在应用启动前应用新 Alembic Migration；本任务不授权 Release、Deploy 或生产 Migration。
- **兼容 / 消费方通知**：管理员可观察语义改变；若 Contract 新增状态/计数，生成 Client 和运行中心文案同步更新。

# 完成审计

- [ ] upstream_re_read：已重新读取所有上游正式事实源，并从它们独立重建完成定义。
- [ ] change_coverage：已确认当前变更覆盖全部上游要求，没有把变更自身当作需求全集。
- [ ] reverse_audit：已执行适用的反向能力或边界审计，并复核验证矩阵；不适用项已有明确依据。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；延期或不适用项均有正式依据。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 分支基线 `5d9108a9` / Windows / 本机开发 PostgreSQL | `pytest ...::test_all_replay_hides_content_not_matched_by_latest_rules_and_preserves_history` | 预期失败：`rows_filtered_out=1`，但 `content_has_active_source(...) is True`；整轮 2.88s | 当前实现没有让最新规则未命中项退出有效结果 |
| V2 | 分支基线 `5d9108a9` / Windows / 本机开发 PostgreSQL | `pytest ...::test_all_replay_batches_existing_convergence_without_per_row_sql --durations=1` | 通过；测试调用 2.62s，总计 3.74s，既有断言 SQL `<150` | 修改前 101 条已有 Content 重筛热路径基线 |

## 未验证内容与剩余风险

- 已建立 Red 失败证据和修改前热路径基线；尚未完成实现、Migration、同环境性能对照、完整集成/工作流验证、Review 或 CI。
- 仓库外生产数据量、锁竞争和目标服务器性能未验证；不得用本地基准冒充生产容量结论。

## 交付状态

- 提交：首个治理提交 `5d9108a9`；Red 测试提交待创建。
- 拉取请求：Draft PR #650 已创建，当前未 Ready。
- CI：早期 Draft PR CI 不构成交付证据；实现后按当前 HEAD 重新验证。
- 合并：尚未合并。
- Change 归档：等待合并后 Automation。
- 发布 / 部署：不适用；用户只授权开发、PR、合并和本地已合并分支清理，未授权 Release/Deploy/生产 Migration。

## 备注

- 当前工作区初始基线来自 2026-09-28 同步后的 `origin/main@bd56ddb8`。
