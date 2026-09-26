---
schema: coding-change/v1
id: CHG-20260926-113720-admin-replay-latency
title: 收敛管理员品牌车型保存与全历史重筛交互卡顿
level: L3
status: in_progress
owner: yuwen.ding
branch: fix/614-admin-replay-latency
created: 2026-09-26T11:37:20+08:00
updated: 2026-09-26
completion_gate: required
depends_on: []
affected_areas:
  - administration
  - vehicles
  - ingestion
  - jobs
  - frontend
  - contracts
  - database
  - logging
affected_paths:
  - backend/src/aima_ugc/contracts/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/platform/jobs/
  - frontend/src/features/admin-configuration/
  - frontend/src/features/import-batches/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - migrations/versions/20260926_0066_canonical_replay_planning.py
  - tests/
  - docs/
contracts:
  - BrandUpdateRequest
  - CanonicalReplayAllCreatedResponse
  - ingestion.canonical-replay-plan.v1
data_changes:
  - canonical_replay_all_requests 增加 Planner 状态、Job 关联与受理边界
---

# 变更摘要

- **要解决的问题**：现场日志证明车型新增/编辑曾出现 18—126 秒等待，并与 Canonical Replay LeaseLost/事务回滚高度重合；当前 main 仍存在 Brand 过强行锁、品牌保存多事务+全目录刷新，以及 Replay all HTTP 同步扫描全部历史 Artifact 的机制。
- **拟议修改**：收敛 Brand 锁强度但保留并发不变量；品牌 aliases 与基础字段原子保存并局部更新 UI；全历史 Replay 采用 Durable Planner 快速受理；Replay 批事务低档起步、3 秒锁等待让路；LeaseLost 依赖 Fencing 安全放弃旧执行。
- **预期结果**：管理员保存不再被已确认的同步放大链拖慢；“确定重筛入库”快速受理；后台任务失败、取消、接管和撤回仍可恢复、可观察。

# 背景、现状与问题

## 背景

Issue #614 来自用户对真实服务器日志和当前 main 的联合排查，目标不是增加 loading 动画，而是切断造成管理员交互卡顿的数据库竞争和同步长任务机制。

## 当前现状

当前 main 已有 Replay 集合写、持久分片、自适应 Worker/批次和资源检测。仍存在：active Brand 校验使用会与 FK KEY SHARE 冲突的强锁；品牌编辑拆为基础字段与多个 Alias API 并在成功后读取全部品牌/车型；Replay all admission 在 HTTP 事务内同步枚举历史 Artifact、计算摘要并创建全部子 Run。

## 问题、根因或约束

日志中车型慢请求与旧 Replay LeaseLost/回滚释放资源在毫秒级时间线上相关；当前代码的 Brand FOR UPDATE 能与 Evidence 外键 KEY SHARE 形成不必要竞争。品牌保存和 Replay admission 还分别存在前端请求放大与同步规划。旧日志不能证明当前 main 仍会重复 243 次 LeaseLost，因此本变更只修当前代码仍存在的机制，并用新鲜 PostgreSQL/Job 证据闭环。

## 不修改的后果

后台重筛仍可能拖慢在线目录写；品牌保存仍会产生多事务和全目录刷新；全历史数据越多，确认重筛的 HTTP 受理成本继续随历史规模增长，且 LeaseLost 可放大 Worker 重启。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 用户日志中车型新增/编辑出现 18—126 秒等待，并与 Replay LeaseLost/回滚高度重合 | 用户提供 logs.zip 的 API/Worker 时间线 | 必须处理后台事务与在线写竞争 |
| E2 | active Brand 校验使用 FOR UPDATE；SQLAlchemy PostgreSQL key_share=True 对应 FOR NO KEY UPDATE | 当前 Brand/Vehicle Repository + SQLAlchemy 2 官方文档 | 使用最弱充分锁，不删除并发保护 |
| E3 | 品牌保存拆多请求并 await load() 重读全部品牌/车型 | CatalogConfigurationPanel.vue 当前 main 基线 | 改为单事务 + 响应局部 upsert |
| E4 | enqueue_all() 在 HTTP 内扫描全部可重筛 Artifact 并创建子 Run/Job | Canonical Replay Repository 当前 main 基线 | 把历史规划移到 Durable Job |
| E5 | 当前 Replay 已有正式 PostgreSQL Job Runtime、Fencing、持久分片和自适应容量机制 | Worker Registry、Replay Worker、capacity.py | 不新增第二套队列或运行时 |

## 推断与待确认

- 当前 main 在用户服务器上的绝对 p95 尚未部署实测；本任务不把本地/CI 耗时外推为生产固定数字。
- Brand 锁竞争的具体 PostgreSQL 锁矩阵机制将由本变更真实并发测试直接验证，未通过则不能进入 Ready。

# 目标、成功标准与非目标

## 目标

让管理员 Brand/Vehicle 写保持短事务；让品牌一次保存成为一个业务原子操作；让 Replay all 只快速受理并由后台 Planner 规划；让 Replay/Job 在锁竞争与 Lease 丢失时安全让路而不是放大故障。

## 成功标准

- [ ] #614 AC1—AC8 均有当前实现和直接测试证据。
- [ ] #614 AC9 的 PostgreSQL、Job、Contract、前端、Full-stack、静态、文档、Review、current-head CI 全部满足。
- [ ] #614 AC10 在 guarded merge 后完成 main-fresh、Change Archive、Closure Audit 与 Issue Closure。

## 范围

- Brand/Vehicle 锁、Contract、Service/Repository 与管理员配置前端。
- Replay all HTTP admission、Planner Job、运行中心状态、Replay 批事务与 Job LeaseLost 收敛。
- additive Migration 0066、生成 Contract、相关测试和 targeted 文档。

## 非目标

- 不修改 TikHub/LLM Provider。
- 不改变 Canonical Content、Content/Brand/Vehicle Evidence 或精确撤回业务语义。
- 不引入 Redis/Kafka/第二套队列，不升级依赖。
- 不执行 Release、生产部署、生产 Migration 或生产数据操作。

## 必须保持不变

- active Vehicle 只能绑定 active Brand；品牌停用/删除与车型创建/编辑的并发不变量必须保留。
- Replay Fencing、取消、接管、贡献账本、checkpoint、精确撤回与现有分片语义必须保持。
- 旧 Brand Alias API 保持兼容；公共 Contract 变化只允许 additive。
- PostgreSQL 是业务事实库，Schema 只通过 Alembic 演进。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 沿既有 Brand/Vehicle、Replay、Job Owner 修复 | E2—E5 | 不建立旁路写入 |
| 接口与契约 | BrandUpdate additive aliases；Replay admission additive planning_status | E3、E4 | 旧调用保持兼容，生成 OpenAPI/Client 同步 |
| 数据与迁移 | 0066 只给父 Replay Request 增加 accepted_before/planning_status/planner_job_id；旧行回填 planned | E4、可恢复性要求 | 不改写 Content/Evidence |
| 错误与失败语义 | Planner 失败/取消显式持久化；锁竞争走可恢复 retry；异常 LeaseLost 只在真实失去 Fence 时放弃 | E1、E5 | 不用延长 Lease 掩盖长事务 |
| 兼容性 | 保留内部同步 enqueue_all 原语；HTTP 使用独立快速受理入口 | E4 | 降低已有内部调用/测试破坏面 |
| 部署与回滚 | 部署需先 Migration 0066 再同版本 API/Worker；本任务不执行生产动作 | 项目 Migration 门禁 | 回滚保留 additive 列，不在活跃 Planner 时 downgrade |

# 修改方案与决策依据

## 最小充分方案

1. Brand/Vehicle 锁与保存：把 active Brand 只读校验收敛为 PostgreSQL FOR NO KEY UPDATE；BrandUpdate 在一个事务/一个 Catalog Version 中替换完整 aliases；前端用返回投影局部 upsert。
2. Replay admission：HTTP 冻结 click-time Catalog Snapshot 与数据库 accepted_before，只创建父请求和 canonical-replay-plan Job；Planner 只枚举 accepted_before 以内 Artifact，再原子生成子 Run/Job。
3. Planner 可恢复状态：0066 显式保存 queued/running/planned/failed/cancelled、planner_job_id 与 accepted_before；运行中心在规划阶段读取 Planner Job 的状态、进度和错误。
4. 后台让路：Replay 批次按冻结上限从低档开始逐级试探，事务超过 3 秒反馈降档；数据库 lock_timeout=3s，锁竞争回滚当前批并走 Job retry。
5. LeaseLost：只有数据库证明当前 Fence 已失效时才安全放弃旧执行；仍持有有效 Lease 的内部 LeaseLost 继续作为异常暴露。
6. 完成 Contract/Docs/测试/Review/CI，再 guarded merge 和 post-merge 收尾。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 最弱充分 Brand 锁 | E1、E2 | 切断 FK KEY SHARE 冲突同时保留品牌写互斥 |
| D2 Brand 原子更新 | E3 | 直接消除 N 个 Alias 事务和保存后全目录读取 |
| D3 Durable Planner | E4、E5 | HTTP 成本不再承担全历史扫描，且复用现有 Job 恢复能力 |
| D4 低档批次+锁让路 | E1、E5 | 限制后台事务持锁墙钟，不把 Lease 当性能预算 |
| D5 显式 Planner 状态 | E4、#614 AC5 | 仅用摘要哨兵不能可靠表达 failed/cancelled，持久状态才能恢复与展示 |

<!-- governance:required-for=L3 -->
## 备选方案与取舍

- 只增加 loading 或延长 Lease：症状仍存在且会隐藏长事务，拒绝。
- 删除 Brand 锁：会破坏 active Vehicle→active Brand 并发不变量，拒绝。
- 仅提高 Worker 数：可能放大数据库 CPU/WAL/锁竞争，历史实验也证明并行收益非单调，拒绝作为根因修复。
- 新建 Redis/Kafka 或第二套队列：与现有 Durable Job Runtime 重复且扩大架构，拒绝。
- 最终采用现有 Owner 内的最小充分修改，并为 Planner 增加最小 additive 状态列。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Replay/FK 并发时车型保存不被 Brand 校验强锁长期阻塞，停用/删除互斥仍成立 | #614 / AC1 | not_satisfied | 已建立 KEY SHARE 并发 Green 候选；待 CI 与反向互斥补证 |
| R2 | 新增/编辑车型均有安全阶段耗时 | #614 / AC2 | not_satisfied | 新增 create 分段日志实现已落分支；待 CI |
| R3 | Brand 基础字段+aliases 原子更新，前端局部更新且不全目录刷新 | #614 / AC3 | not_satisfied | Contract/Repository/UI 已实现；生成 Contract 已同步；待 CI |
| R4 | Replay all HTTP 只创建父请求+Planner Job，历史扫描/子 Run 规划异步 | #614 / AC4 | not_satisfied | Planner/HTTP 已实现；待 PostgreSQL/Full-stack 证据 |
| R5 | Planner 冻结 click-time Catalog 与 admission-time Artifact cutoff，幂等/可恢复 | #614 / AC5 | not_satisfied | admission boundary 集成已建立；0066 状态实现待验证 |
| R6 | Replay 后台事务有锁竞争让路和批次墙钟反馈，不靠放大 Lease | #614 / AC6 | not_satisfied | tier batch + 3s lock_timeout 已实现；待测试/CI |
| R7 | 非取消 LeaseLost 安全放弃旧执行，不杀 Worker；Fencing 保持 | #614 / AC7 | not_satisfied | Worker 改动已实现；待真实 stale/active Lease 回归 |
| R8 | Replay 分片/取消/接管/撤回/账本/checkpoint 现有语义保持 | #614 / AC8 | not_satisfied | 相关完整 PostgreSQL/Worker 回归待 CI |
| R9 | 前端、PostgreSQL、Job、Contract、Full-stack、静态、Docs、Review、CI 完整验证 | #614 / AC9 | not_satisfied | 待完成 |
| R10 | Merge 后 main-fresh、原生 Change Archive、Closure Audit、Issue close | #614 / AC10 | not_satisfied | post-merge 门禁，当前未到达 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Brand/Vehicle Contract + Repository + Service | 原子 aliases、最弱充分 Brand 锁、create/update timing | 消除在线写竞争与请求放大 | R1—R3 / E1—E3 |
| Canonical Replay HTTP/Repository/Planner/Worker | 快速受理、冻结边界、Planner 状态、短批事务 | 切断同步历史扫描和后台长事务 | R4—R8 / E4—E5 |
| Job Worker | 真实 stale Lease 安全放弃，有效 Lease 异常继续暴露 | 避免进程重启风暴且不吞内部 Bug | R7 / E1 |
| Migration 0066 + runtime query | 持久 Planner 生命周期并展示 | 可恢复、可观察 | R5 / E4 |
| Frontend Admin + Runtime | 局部更新、后台规划提示/阶段 | 用户等待链闭环 | R3—R5 |
| Tests / generated contracts / targeted docs | 回归与事实同步 | 交付证据 | R9 |

执行过程中保持最小闭环：

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据
- [ ] 完成最小实现，不静默扩大范围
- [ ] 同步受影响的长期文档
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Contract normalize、batch tier、LeaseLost Worker、前端局部更新 |
| 接口 / 契约 | required | Pydantic→OpenAPI→Orval additive compatibility |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL KEY SHARE/NO KEY UPDATE、Brand 原子 Alias、Planner 状态/selection/Fence、Migration |
| 用户 / 工作流验收 | required | 管理员保存、Replay all 受理→规划→运行中心状态与失败闭环 |
| 跨组件关键路径 | required | API→Job→Planner→Replay Run→Content/Evidence/ledger/checkpoint/reversal |
| 外部依赖 / 供应方探测 | not_applicable | 本任务不改变 TikHub/LLM 协议且无需远端 Provider 才能证明根因 |
| 构建 / 打包 / 运行 | required | Ruff、Mypy、Alembic check、frontend lint/build、正式 Worker Registry |
| 文档 / 治理 / 其他 | required | targeted 文档、Change Completion、Deep Review、PR/main CI、Archive/Closure |

## 验证计划

- 目标测试：BrandUpdate Contract、真实 PostgreSQL 行锁、车型 create/update timing、Replay Planner boundary/state、LeaseLost。
- 相关回归：Canonical Replay/撤回/Fencing/分片、管理员 API、运行中心、前端管理员配置。
- 静态检查或构建：Ruff、Mypy、Contract generate/check、Orval diff、frontend lint/build。
- 专项真实边界：PostgreSQL 18 Migration/Integration、Real Full-stack Golden Path。
- 就绪检查：项目正式 python scripts/quality/check_change_completion.py --root . --require-active-ready 与 PR required CI。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 锁降级或异步规划可能造成并发不变量/selection 漂移 | PostgreSQL 并发、accepted_before、Fencing 和撤回回归阻断交付 |
| 兼容性 | public Contract additive；内部同步 enqueue_all 保留 | 旧 Alias API、既有内部调用与运行语义继续可用 |
| 数据 / Migration | 新增 0066，旧父请求回填 accepted_before=created_at、planning_status=planned | 不改写 Content/Evidence/历史贡献；未完成 Planner 时禁止 downgrade |
| 部署 / 运行 | 未来部署必须先 0066，再启动同版本 API/Worker | 本任务不执行生产 Migration/Deploy |
| 回滚 / 恢复 | 回滚应用前先让新版 Planner/子 Job 结清或取消；保留 additive Schema | 不在活跃 Planner 期间 downgrade，不手工改业务数据 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 同步 Replay admission/Planner/运行状态、管理员保存与 PostgreSQL 性能排障边界。
- **依赖 / Runtime**：不新增、不删除、不升级依赖或 Runtime。
- **配置 / Secret**：不新增必填配置或 Secret；Replay lock timeout 为内部固定安全边界，不成为用户配置。
- **部署 / Release**：代码引入 Migration 0066；未来 Release 必须按现有 Migration 门禁升级，本任务不执行 Release、生产 Migration 或 Deploy。
- **兼容 / 消费方通知**：BrandUpdate aliases 与 Replay planning_status 均为 additive；生成 OpenAPI/Client 已同步。

# 完成审计

- [ ] upstream_re_read：Ready 前重新读取 #614、当前 main/PR head 与受影响正式文档。
- [ ] change_coverage：Ready 前逐项核对 R1—R10，不能用 Change 自身替代上游 AC。
- [ ] reverse_audit：Ready 前执行后端→前端、前端→后端、请求→Planner→Run→结果/取消/撤回的反向审计。
- [ ] unresolved_cleared：Ready 前所有 not_satisfied 清零，post-merge R10 保持正式交付门禁而非提前声称完成。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | base main + 用户日志 | 日志时间线与当前调用链审计 | 已定位后台锁竞争、品牌请求放大、Replay HTTP 同步规划 | Red/根因边界 |
| V2 | PR 分支中间 revision | Contract 正式生成链 | OpenAPI 与 Orval 已同步 Brand aliases / planning_status | 生成链已接线；不替代最终 CI |
| V3 | PR 早期 CI | Requirement gate | 发现 Change 结构不满足最新机器 Contract | 已据 canonical template 重写；最终 CI 待执行 |

## 未验证内容与剩余风险

- 0066 Migration、完整 PostgreSQL/Full-stack、最终 static/build 尚未在包含本轮最终实现的 revision 上通过。
- 用户生产服务器未部署本分支，不能宣称生产 p95 已达到目标；发布后仍需独立运行验收。
- Release、生产 Migration、Deploy 和生产数据操作不在本次授权范围。

## 交付状态

- 提交：实现仍在进行。
- 拉取请求：#615，逻辑未就绪。
- CI：早期治理失败已定位；最终 current-head CI 未完成。
- 合并：未执行。
- Change 归档：未执行，必须由 merge 后原生 automation 完成。
- 发布 / 部署：不适用；用户未授权 Release/Deploy/生产 Migration。

## 备注

当前工作继续以 #614 AC1—AC10 为唯一上游验收来源；旧 #581/#583/#585/#593/#603 只作为历史性能与架构证据。
