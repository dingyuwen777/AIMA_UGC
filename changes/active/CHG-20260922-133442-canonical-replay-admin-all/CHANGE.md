---
schema: coding-change/v1
id: CHG-20260922-133442-canonical-replay-admin-all
title: 管理员页面支持全量 Canonical 重筛入库
level: L3
status: in_progress
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
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - docs/product/02_当前产品能力与用户流程.md
  - docs/blueprint/04_后端任务API与前端.md
  - backend/src/aima_ugc/modules/ingestion/README.md
contracts:
  - POST /api/v1/canonical-replays/all
data_changes:
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

- [ ] “重筛入库”位于“新增品牌”左侧，提交前明确说明范围、耗时和不触发 Provider/AI。
- [ ] 后端稳定选择全部受支持的 linked `canonical-content.v1`，按每组最多 100 个 Artifact 创建多个 Replay Run/Job，批大小固定为 1000。
- [ ] 同一客户端幂等键和同一冻结输入返回原批次；输入集合、参数或创建者漂移时失败关闭。
- [ ] 空历史集合安全返回零任务；页面给出准确反馈且不伪造成功。
- [ ] 现有显式 Artifact Replay API、Job 类型、Content Owner、来源追溯和错误语义保持兼容。
- [ ] Contract/API、真实 PostgreSQL、前端用户工作流、生成物、文档、独立 Review 与当前 PR CI 通过后合并 `main`。

## 非目标

- 不提高单 Run 的 100 Artifact 安全上限，不让一个 Job 无界加载全部 Artifact。
- 不在浏览器读取 Artifact 存储目录或拼装数据库 lineage。
- 不重新读取 Excel、不请求 TikHub、不自动触发 AI、Export 或 Report。
- 不修改数据库 Schema，不部署生产环境，不执行生产数据操作。

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
| 回滚 | 回滚新增前后端入口即可 | 无 Schema/Migration | 已排队 Job 继续按既有语义完成或取消 |

# 修改方案与决策依据

1. Repository 用一条确定性 SQL 查询覆盖三类合法 lineage，返回按 `created_at, id` 排序的 Artifact ID/来源类型。
2. Application Service 在同一事务内冻结全量选择，计算选择摘要，按 100 个分组，复用现有 `enqueue` 创建多个持久 Run/Job；请求重复时逐组返回原记录，选择漂移则拒绝。
3. 新增 `POST /api/v1/canonical-replays/all` 请求/响应 Contract 并重新生成 OpenAPI/TypeScript Client。
4. 管理页面增加确认弹窗和按钮，薄 API 只提交幂等键；提交期间禁用重复操作，成功反馈 Artifact/任务数量，空集单独说明。
5. 同步当前产品、API/前端与 Ingestion 文档，移除“尚无前端入口”的过时事实。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 新增品牌左侧提供手动全量重筛按钮 | #560 / 用户决定 | not_satisfied | 待实现与 Browser 验收 |
| R2 | 全部历史 Canonical 自动选择并按 100 个分组排队 | #560 / 用户决定 | not_satisfied | 待 Repository/API/PostgreSQL 回归 |
| R3 | 在现有安全边界内尽可能快 | #560 / 用户决定 | not_satisfied | 待 1000 行批次、并行可领取 Job 断言与文档 |
| R4 | 幂等、空集合、权限和错误失败关闭 | #560 / AC1—AC4 | not_satisfied | 待 API/Integration/Browser 正反例 |
| R5 | 旧 API 与 Provider/AI/Content Owner 边界保持不变 | #560 / AC4 | not_satisfied | 待相关回归、Contract 兼容和 Review |
| R6 | 验证、文档、PR、CI 和 main 合并闭环 | #560 / AC5 | not_satisfied | 待完成 |

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
| 数据 / Migration | 无 Schema 变化，会新增持久 Run/Job 与业务入库结果 | 所有写入复用既有 Owner/Job；生产执行由管理员确认 |
| 部署 / 运行 | Worker 数量决定实际并发 | 不在 API 内执行重筛，不隐藏无限并发 |
| 回滚 / 恢复 | 源码回滚移除入口；已建任务可按既有 API/Job 取消或完成 | 无 Migration downgrade |

# 实施与验证计划

- [x] 恢复当前 Contract、Repository、Worker、管理页面和测试事实
- [x] 创建 Issue、任务分支与本 Change
- [ ] 先建立 API/PostgreSQL/Browser 失败回归
- [ ] 实现全量选择、分组排队、Contract 与管理页面
- [ ] 重新生成 OpenAPI 与 TypeScript Client
- [ ] 同步受影响文档并执行分层验证
- [ ] 完成 Requirement Traceability、Completion Audit 和独立 Review
- [ ] 推送 PR、等待 required checks、合并并归档 Change

# 完成审计

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 完成证据与状态

当前为施工中；验证证据、Review、CI、合并和 main-fresh 状态将在完成前补充。
