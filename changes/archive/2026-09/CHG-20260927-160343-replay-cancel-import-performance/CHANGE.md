---
schema: coding-change/v1
id: CHG-20260927-160343-replay-cancel-import-performance
title: 历史重筛、取消撤回与数据导入性能修复
level: L3
status: done
owner: codex
branch: fix/630-replay-import-performance
created: 2026-09-27
updated: 2026-09-27
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - backend-api
  - ingestion
  - jobs
  - database
  - performance
affected_paths:
  - frontend/src/features/import-batches/
  - frontend/tests/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/modules/ingestion/
  - tests/
  - scripts/performance/
  - docs/appendix/08_数据入口与统一入库实现.md
contracts:
  - HTTP 字段形状与持久 Job Payload 保持兼容；Replay batch_size 从硬上限明确为自适应起始提示
data_changes:
  - 无 Schema 或生产数据迁移
---

# 变更摘要

Issue #630 统一处理三个相互影响的生产问题：全历史重筛约每分钟处理一万原始行；“取消并撤回”确认后按钮短暂置灰又恢复，任务未稳定进入撤回完成态；数据导入在重筛并发时明显变慢。实现从共同的 Resolver、Content/Evidence 批量写入、持久 Job、数据库事务和资源竞争边界修复，而不是继续为三个症状分别叠加补丁。

# 背景、现状与问题

用户需要本地上传、服务器历史目录、Replay、运行中取消与精确撤回在任意串行或并行顺序下都保持正确和高吞吐。品牌车型也可能先于数据创建，或在数据已保存 Canonical 后创建并触发 Replay；两种顺序必须得到相同业务事实，不能因目录规模或顺序形成快慢两套实现。

生产日志显示 2,000 行导入批次需要约 69–94 秒，Evidence 阶段约 57–64 秒；全历史 Replay 约每分钟一万原始行。取消请求曾因网关超时返回 504，父请求后来进入 cancelling/reverting，但新复现中前端按钮会恢复，说明“请求是否持久受理、当前真实状态、是否停止继续入库、是否完成撤回”没有形成稳定的端到端事实。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 决策作用 |
| --- | --- | --- | --- |
| E1 | 修复前本地同库 10,100 行 / 2,100 个目录别名 Replay 为 96.983 秒、104.72 行/秒，其中 Resolver 66.559 秒 | 同机 PostgreSQL 基准报告 | Resolver 逐行遍历全部别名是第一主因 |
| E2 | Job Payload JSON 恢复后目录对象身份改变，旧 Resolver 会重复编译索引 | `modules/vehicles/brand_vehicle.py` 调用链与计数回归 | 缓存必须使用稳定目录身份 |
| E3 | 原 Replay 不跨 Canonical Artifact 聚合；跨 Artifact 后 SQL 6,575→4,249、账本 INSERT 101→20 | 同结构 10,100 行基准 | 小文件事务放大是第二主因 |
| E4 | 父 Replay 事务可持有父行锁超过代理超时；取消 HTTP 同步等待该锁 | PostgreSQL 并发复现和用户 504 | 取消意图必须先独立持久受理 |
| E5 | 旧前端在 5xx 后刷新，并可用旧 `active` 覆盖乐观状态 | 前端 Store 实现与回归 | POST 响应和后续生命周期必须单调 |
| E6 | 服务端目录与本地上传最终进入同一 Data Import Campaign/Chunk/Content Owner | 当前 API、Job 与 Repository 调用链 | 两入口不能维护不同批量或写入实现 |
| E7 | 完成批量与自适应修复后，隔离 Replay 端到端 17.556 秒、590.89 行/秒 | 同机 PostgreSQL 最终基准 | 相对修复前吞吐提高 5.64 倍 |
| E8 | 同一 10,000 行统一导入：服务端目录 715.30 行/秒，本地上传 720.25 行/秒 | 同机 A/B 基准 | 两入口差异约 0.7%，链路等价 |
| E9 | 1,000 / 2,000 / 4,000 行 Chunk 分别为 373.25 / 393.04 / 412.66 行/秒；4,000 行事务约 8.1 秒 | 当前代码单 Worker 档位实验 | 4,000 作为事务护栏，更多资源优先扩 Job 并发 |
| E10 | Replay×Import×Reversal 混合负载中，2,000 行导入 Chunk 约 2.3–3.3 秒；运行中取消在 2 秒内受理并最终 `reverted` | 混合负载与真实 Worker 集成 | 新资源边界没有复现旧版 69–94 秒，取消与撤回闭环 |

合理推断：大目录逐行遍历和重复编译匹配状态，是 Replay 与导入共同的 CPU 放大器；Evidence、before/after 快照、贡献账本、投影和小 Artifact 事务，是共同的数据库写放大。单纯增加 Worker 会复制低效工作并加剧共享数据库竞争，因此必须先消除放大，再在全局预算内增长。

暂时无法验证：服务器尚未部署本分支，生产大库上的新阶段耗时、WAL、I/O、CPU 与绝对吞吐需在新 Release 部署后复测。本机证据证明机制与相对改进，不承诺服务器固定 SLO。

# 目标、成功标准与非目标

- 同机相同输入下，Replay 隔离吞吐必须提高、处理时间必须缩短；最差重新筛选与初次入库保持可解释的同一数量级。
- 服务端历史目录和本地上传使用相同自适应 Chunk、Resolver、Content/Evidence 与贡献账本链路，吞吐处于同一量级。
- “取消并撤回”在父锁竞争和重复点击下仍持久受理，停止 Replay 后续入库，并精确撤回已经提交且仍由该请求独占的数据。
- 前端不再被旧轮询状态降级；请求无法确认时明确显示并允许安全重试。
- 应用日志以 HTTP request ID、Replay 父请求 ID 和 Job ID 追踪接收、数据库阶段、提交、协调取消和撤回终态。
- 所有相关数据处理可随 16 核 / 64 GB 等机器资源增长，同时为 API、查询、取消协调和多用户访问保留容量。
- 保持公共 HTTP 形状、数据库 Schema、Content Owner、贡献账本、Fencing、Checkpoint 与精确撤回语义。

非目标：升级依赖；取消全局资源预算；让单个任务独占机器；绕过统一 Job Runtime；部署或修改生产数据。

# 约束与意图决策

所有数据处理 Job 可以增长，但共享一个由容器 CPU/内存、Worker 进程池、前台保留进程和后台写槽组成的总预算。资源更强时增长的是受控 Worker、Job 窗口和经实测证明有收益的批量，不能让每个任务独立把所有旋钮拉满。API、Scheduler 与 Frontend 继续使用独立容器预算。

Replay 的持久 `batch_size` 保持公共 Contract 的 1–1,000 范围，但语义明确为起始提示；运行时根据有效资源、相邻档吞吐、3 秒事务墙钟、数据库重试和前台压力升降档。统一 Data Import 在 Campaign 创建时冻结 500/1,000/2,000/4,000 档，保持重试与接管确定性。Data Import Chunk 可被并发撤销，不能跨 Chunk 合并事务；兼容单文件和 Provider Canonical 可以跨 Artifact 聚合。

# 修改方案与决策依据

采用“先消除共同放大，再在全局预算内自适应增长”的方案：

1. 把品牌/车型别名匹配编译为 Aho-Corasick 自动机，并按目录版本、过滤范围和选定品牌复用；解析复杂度主要随正文长度增长。
2. Replay 对兼容来源跨 Artifact 累计到当前自适应目标；Content、Evidence、快照、账本和撤回保持 Owner 语义并改为有界批量。
3. 取消 HTTP 先以请求专属稳定幂等键创建协调 Job，再用 250 ms 父锁尝试投影父状态；锁忙时提交协调 Job并返回已受理状态。
4. Replay 周期探测持久取消协调 Job并同步标记当前子 Job取消；协调器停止其余子任务后创建撤回 Job。
5. 前端立即应用 POST 返回状态，并在服务端追上前阻止 `cancelling/reverting` 被旧 `active` 覆盖；5xx/非 JSON 进入“结果未确认”并安全重试。
6. Worker 进程池按资源增长并保留四分之一前台进程；Replay/撤回使用后台写槽，前台导入有压力时新后台事务收缩到一个。

## 备选方案与取舍

1. 只增加 Worker 与固定大批量：改动小，但复制逐别名扫描和逐行 SQL，会放大锁、WAL、内存和连接竞争；不采用。
2. 把所有来源固定为 2,000 或 4,000 行：实现简单，但小机器风险高，大机器又不能继续探索；不采用。
3. 取消请求继续同步等待父行锁，只提高 Nginx 超时：只能掩盖 504，不能证明意图已持久化，也会继续阻塞用户；不采用。
4. 已采用：消除共同放大，Replay 按实测逐级升降，Data Import 冻结资源档并通过 Job 并发扩展，全局保留前台容量。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 系统解决历史重筛吞吐慢，重新筛选与初次入库有可比速度 | #630 / AC3 | satisfied | Replay 104.72→590.89 行/秒、端到端约 96.98→17.56 秒；与统一导入保持同一数量级 |
| R2 | “取消并撤回”正确持久受理、显示真实状态并最终撤回 | #630 / AC2 | satisfied | 父锁并发、重复点击、前端单调状态、真实 Worker 取消到 `reverted` 对账 |
| R3 | 修复导入性能回退，并验证服务端目录与本地上传等价 | #630 / AC4 | satisfied | 两入口 715.30 / 720.25 行/秒；混合负载 2,000 行 Chunk 约 2.3–3.3 秒 |
| R4 | 仅凭服务器日志定位取消、Replay、导入与撤回阶段 | #630 / AC1 | satisfied | API 接收/数据库阶段/提交/失败、协调批次/终态、Replay/Import 阶段均关联 request/replay/job ID |
| R5 | 保持 Contract、Schema、贡献账本、Fencing、Checkpoint 与精确撤回 | #630 / AC5 | satisfied | Contract 检查；数据库/Job 139 项、API/Ingestion 169 项；无 Schema Migration |
| R6 | 建立并执行 Review、CI、PR 与合并门禁，任一门禁未绿时禁止合并 | #630 / AC5 | satisfied | 本地完成审计与 Review；PR #631 已 Ready；分支保护继续要求 current-head CI 成功后才允许合并 |
| R7 | 覆盖本地上传、服务器目录、Replay、取消与撤回的串行/并行矩阵 | #630 / AC6 | satisfied | 两类导入 A/B、Replay×Import×Reversal mixed-load、运行中取消及终态账本对账 |
| R8 | 16 核 / 64 GB 等服务器按真实资源自适应，不写死开发机参数 | #630 / AC7 | satisfied | 资源模拟选择 8 Worker、2 前台保留、4,000 行护栏；Replay 批量按吞吐反馈升降 |
| R9 | 目录先建后导入与先导入后建目录再 Replay 的最终结果和单遍吞吐等价 | #630 / AC6 | satisfied | 10,100 行 / 2,100 别名 A/B 最终均 10,100 条 Content，单遍差异约 3.3% |
| R10 | 修复后处理效率提高、时间缩短，同时保留多用户 API 稳定性 | #630 / AC7 | satisfied | Replay 5.64 倍；1k/2k/4k 档位实验；前台保留、后台写槽测试与混合负载 |

# 计划改动

1. 取消与日志：API、Repository、协调 Worker 和前端 Store 建立持久受理、幂等、关联日志和单调生命周期。
2. Resolver 与批量写：稳定目录索引、跨 Artifact Replay、批量 Evidence/快照/账本/撤回。
3. 资源调度：Worker 前台保留、后台 PostgreSQL 写槽、Replay 自适应批量和 Data Import 资源档。
4. 基准：同机隔离 Replay、服务端/本地导入、1k/2k/4k 档位、目录顺序 A/B 与 Replay×Import×Reversal 混合负载。
5. 验证与交付：Contract、静态检查、前端、PostgreSQL、Job、API/Ingestion、文档和 PR current-head CI。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Resolver 索引复用、批量控制器、Worker 前台保留、前端取消状态 |
| 接口 / 契约 | required | OpenAPI 生成同步、兼容检查、`batch_size` 提示语义 |
| 集成 / 持久化 | required | 父行/Job 锁、幂等受理、取消协调、撤回账本、工作负载写槽、Migration 不变量 |
| 用户 / 工作流 | required | 运行中取消到 `reverted`；两种导入入口；目录顺序 A/B |
| 性能 / 混合负载 | required | 修复前后 Replay、Chunk 档位、Import×Replay×Reversal 吞吐和让路时间 |
| 构建 / 运行 | required | 前端 lint/typecheck/test/build，Compose 资源选择，Worker 注册与启动 |
| 外部依赖 | not_applicable | 本次 Replay/导入基准不调用 TikHub 或付费模型 |
| 生产实测 | limited | 本任务未授权部署或写生产库；部署后按新增日志在服务器复测 |

# 风险、兼容性、迁移与回滚

无数据库 Schema/Migration。HTTP 字段形状保持兼容；新增 Cancellation Payload 字段均可选，旧任务仍可恢复。跨 Artifact 只用于不可由 Data Import Campaign 并发撤销的兼容来源；Data Import 保持单 Chunk 事务边界。Replay 批量有 64,000 绝对安全护栏、资源上界、3 秒事务墙钟、8% 相邻档收益门槛和数据库重试降档；Data Import 当前 4,000 护栏来自同机边际收益与事务时长证据。

代码可回滚到旧 Release；无新表需要降级。回滚会恢复旧性能与取消超时行为，但不会改变已经提交的业务事实；已经开始的撤回应先由同版本 Worker 结清，不能用回滚替代数据操作。

# 文档、依赖、部署与发布影响

同步 Ingestion README、数据入口与统一入库 Appendix、OpenAPI 与生成前端 Client。无新依赖、无版本升级、无数据库部署步骤。Compose 自动资源上限提高为可重叠峰值预算：PostgreSQL/Worker 各最多 75% CPU，API 最多 25%，Worker 内部仍受进程池、前台保留和后台写槽约束。正式服务器部署与生产复测需要新的 Release 和独立部署授权。

# 完成审计

- [x] upstream_re_read：重新读取 Issue #630、用户日志、最终代码、Contract、Schema、测试、CI 与部署配置，按最终补充要求重建完成定义。
- [x] change_coverage：R1–R10 覆盖三个原始问题、两类导入、两种目录顺序、串行/并行、资源增长、处理时间缩短和多用户稳定性。
- [x] reverse_audit：从前端动作到 API 持久受理、协调 Job、Replay 停止、Reversal 账本终态；从两类导入入口到同一 Campaign/Chunk/Owner；从资源预算到 Worker 与数据库写槽反向核对。
- [x] unresolved_cleared：已用同机隔离和混合负载证明主要机制与相对改进；服务器绝对吞吐明确保留为部署后复测，不用机器性能或日志替代根因闭环。

# 完成证据与状态

当前分支 `fix/630-replay-import-performance`，Issue #630，PR #631，提交 `2b218c47` 尚未合并。Ruff、mypy 387 个源码文件、Contract 生成/兼容、文档事实/导航、架构、Table Owner 与 Secret 检查通过；数据库/Job/锁/Migration 集成 139 项，API/Ingestion 完整流程 169 项，相关单元 77 项，容量报告 2 项通过；前端 lint、TS7/Vue 类型检查、33 个文件 249 项测试和生产构建通过。完整 Python 单元在 Windows 上另有 1,319 项通过、9 项跳过；9 项失败来自未修改的文档导航 Windows 行为和直接假设 `os.geteuid/os.chown` 的 POSIX 宿主测试，Linux current-head CI 继续作为合并门禁。

同机性能：Replay 端到端约 96.98→17.56 秒、104.72→590.89 行/秒；服务端目录/本地上传 715.30/720.25 行/秒；目录顺序 A/B 单遍差异约 3.3%；混合负载没有复现旧版 69–94 秒的 2,000 行批次。PR 转 Ready 后第一次 CI 仅因本 Change 使用了非规范章节标题失败，代码 Job 尚未因此获得绿色结论；本次已按 canonical Change Contract 重组，当前提交的 CI 成功前禁止合并。
