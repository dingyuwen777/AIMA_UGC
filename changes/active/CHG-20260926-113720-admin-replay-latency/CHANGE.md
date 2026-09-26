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
  - backend/src/aima_ugc/contracts/brand_vehicle.py
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/bootstrap/brand_vehicle_http.py
  - backend/src/aima_ugc/bootstrap/administration_http.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_http.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - backend/src/aima_ugc/bootstrap/worker.py
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py
  - backend/src/aima_ugc/adapters/persistence/postgres/canonical_replay.py
  - backend/src/aima_ugc/platform/jobs/worker.py
  - frontend/src/features/admin-configuration/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - tests/
  - docs/
contracts:
  - BrandUpdateRequest
  - CanonicalReplayAllCreatedResponse
  - ingestion.canonical-replay-plan.v1
data_changes: []
---

# 变更摘要

基于 Issue #614 与用户提供的 API/Worker 日志，修复后台 Canonical Replay 与在线品牌车型管理写之间的数据库竞争，收敛品牌保存的多请求/全目录刷新，并把全历史 Replay 的历史扫描与子 Run 规划从 HTTP 请求移入正式 Durable Job。保持现有 Job Runtime、Fencing、取消、精确撤回和 Brand/Vehicle 数据不变量。

# 背景、现状与问题

现场日志显示车型新增/编辑可等待 18—126 秒，并与旧运行版本 Canonical Replay 的 LeaseLost/事务回滚时刻高度重合。当前 main 已有 Replay 分片和资源反馈，但 active Brand 校验仍使用 FOR UPDATE；品牌编辑仍拆成基础字段与多个 Alias API，并在完成后重读全部品牌/车型；全历史 Replay admission 仍同步枚举全部 Artifact 并创建全部子 Run。

# 目标、成功标准与非目标

- 目标：切断后台 Replay 对在线 Brand/Vehicle 管理写的非必要锁阻塞；品牌一次保存成为单业务事务；Replay all admission 快速返回并由 Planner Job 完成历史规划；LeaseLost 不再导致 Worker 进程级崩溃。
- 成功标准：Issue #614 AC1—AC10 全部有直接代码/测试/CI 证据，且用户可见保存/提交链不再包含已确认的同步放大机制。
- 非目标：不改变 Canonical Content/Evidence 业务语义，不新建第二套队列，不升级依赖，不执行 Release/Deploy/生产 Migration/生产数据操作。

# 约束与意图决策

- Brand 校验锁只允许降到仍能阻止品牌停用/删除与 active Vehicle 创建竞态的最弱充分锁；不能为了性能移除并发不变量。
- Replay all 的品牌车型目录必须在用户点击受理时冻结；历史 Artifact 选择使用受理时间边界，Planner 后续只消费该冻结范围。
- Planner、Replay、Reversal 继续使用同一 PostgreSQL Durable Job Runtime。
- Generated OpenAPI/Orval 只能来自仓库正式生成链；本任务不手工维护第二套 Contract。
- 后台事务竞争优先让路和缩短事务，不以扩大 Lease/timeout 掩盖根因。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Replay/FK 并发时车型保存不被 Brand 校验强锁长期阻塞，停用/删除互斥仍成立 | #614 AC1 | not_satisfied | Red PostgreSQL 并发测试已建立 |
| R2 | 新增/编辑车型均有安全阶段耗时 | #614 AC2 | not_satisfied | 待实现 |
| R3 | Brand 基础字段+aliases 原子更新，前端局部更新且不全目录刷新 | #614 AC3 | not_satisfied | Red Contract 测试已建立 |
| R4 | Replay all HTTP 只创建父请求+Planner Job，历史扫描/子 Run 规划异步 | #614 AC4 | not_satisfied | Red Contract 测试已建立 |
| R5 | Planner 冻结 click-time Catalog 与 admission-time Artifact cutoff，幂等/可恢复 | #614 AC5 | not_satisfied | 待实现 PostgreSQL/Job 回归 |
| R6 | Replay 后台事务有锁竞争让路和批次墙钟反馈，不靠放大 Lease | #614 AC6 | not_satisfied | 待实现 |
| R7 | 非取消 LeaseLost 安全放弃旧执行，不杀 Worker；Fencing 保持 | #614 AC7 | not_satisfied | 待实现 |
| R8 | Replay 分片/取消/接管/撤回/账本/checkpoint 现有语义保持 | #614 AC8 | not_satisfied | 待相关回归 |
| R9 | 前端、PostgreSQL、Job、Contract、Full-stack、静态、Docs、Review、CI 完整验证 | #614 AC9 | not_satisfied | 待验证 |
| R10 | Merge 后 main-fresh、原生 Change Archive、Closure Audit、Issue close | #614 AC10 | not_satisfied | 交付后置门禁 |

# 实施计划

1. PostgreSQL 锁：用 FOR NO KEY UPDATE 替代 active Brand 校验的过强 FOR UPDATE，并补 KEY SHARE 兼容与停用竞态测试。
2. 管理写：BrandUpdateRequest 增加可选 aliases；Repository 一次目录版本内同步 Alias；前端使用返回 BrandResponse 做局部 upsert；车型 create/update 统一阶段计时。
3. Replay admission：新增 canonical-replay-plan Job，HTTP 受理时冻结 Catalog Snapshot 与 Artifact cutoff，只写父事实+Planner Job；Planner 后台枚举、摘要、拆 Run/Job。
4. Replay/Job 可靠性：后台批事务设置有界 lock_timeout 并按实际事务耗时降档；非取消 LeaseLost 记录并安全结束当前 run_once，不使进程退出。
5. 生成 Contract、targeted Docs、Completion Audit、Deep Review、PR CI、guarded merge、main-fresh 与原生归档/Closure。

# Validation Matrix

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 行为 / Unit | required | Contract normalize、批次反馈、LeaseLost Worker、前端局部更新 |
| Contract | required | Pydantic→OpenAPI→Orval additive compatibility |
| PostgreSQL Integration | required | KEY SHARE/NO KEY UPDATE、Brand 原子 Alias、Planner selection/幂等、Replay Fence |
| Workflow / Full-stack | required | 管理员保存、Replay all admission→Planner→运行状态 |
| External Provider | not_applicable | 不改变 TikHub/LLM |
| Build / Runtime | required | Ruff、Mypy、Alembic、frontend lint/build、Worker Registry |
| Docs / Governance | required | targeted 技术文档、Completion、Review、PR/main CI、Archive/Closure |

# 风险、兼容、迁移与回滚

- Contract 仅 additive；旧 Brand Alias API 保留。
- 优先不新增 Schema：父 Replay Request 现有 created_at 作为 Artifact cutoff，Job payload 持久冻结 Catalog Snapshot；若真实实现证明现有 Schema 无法安全承载再进入 Re-plan。
- 锁降级通过真实 PostgreSQL 并发反例证明，不以静态 SQL 字符串替代。
- 回滚为正常应用版本回退；不删除业务数据，不执行生产 downgrade。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 当前证据

Red 已建立：BrandUpdateRequest 尚无 aliases；CanonicalReplayAllCreatedResponse 尚无 planning_status；active Brand guard 在 KEY SHARE 下当前使用 FOR UPDATE，预期被 PostgreSQL lock_timeout 证伪。实现、Green、Review、CI 和交付尚未完成。
