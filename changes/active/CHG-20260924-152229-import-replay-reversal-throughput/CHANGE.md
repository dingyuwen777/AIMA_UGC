---
schema: coding-change/v1
id: CHG-20260924-152229-import-replay-reversal-throughput
title: 历史数据导入、重筛与精确撤回后端吞吐修复
level: L3
status: in_progress
owner: yuwen.ding
branch: perf/593-import-replay-reversal-throughput
created: 2026-09-24T15:22:29+08:00
updated: 2026-09-24T17:14:11+08:00
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - vehicles
  - storage
  - jobs
affected_paths:
  - backend/src/aima_ugc/
  - tests/
  - scripts/performance/
  - docs/appendix/
  - docs/02_环境运行与部署.md
  - docs/operations/
contracts:
  - canonical-content.v1
  - ingestion.canonical-replay.v1
  - ingestion.canonical-replay-reversal.v1
data_changes:
  - canonical_replay_content_changes 精确撤回账本
  - contents 与 Brand/Vehicle Evidence
---

# 背景、目标和边界

2026-09-24 真实演示中，本地和服务器历史文件的全量预检/转换各约 41–50 秒；100 Artifact 重筛发生 `ON CONFLICT DO UPDATE` 同批重复命中并持续重试；“取消并撤回”单 Job 耗时 99.752 秒。历史微基准改善不能证明这三个过程已经流畅。

目标是在相同输入、相同数据库语义下系统性降低预检、导入、重筛和撤回端到端耗时，修复确定性失败，并保留安全边界。范围限后端、测试、基准与技术文档；不改 UI 或等待体验，不访问付费 Provider、生产库或正式历史迁移。

# 硬约束与方案

保持 Source Artifact 不可变、首笔业务写入前全量预检、Canonical Contract、过滤与 Historical Fill-Only、Content Owner、逐行账本、Fencing、检查点、取消、精确撤回以及后续事实保护。优先基于真实文件和隔离 PostgreSQL 的分段 Profile，按热点在现有 Owner 内合批或减少重复解析；性能改动必须通过结果对账，不以关闭校验或单纯放大并发取代根因修复。

备选方案：①仅加 Worker 并发，可能放大数据库锁争用且不能解决确定性失败；②先消除重复计算和逐行 SQL 往返，再按测量决定并发，当前采用；③另建 ETL/写库链，破坏 Owner 与追溯边界，拒绝。

# Requirement Traceability

| ID | 要求 | Source | 状态 | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地手工与服务器历史文件预检、转换和入库显著提速且结果对账一致 | #593；user:20260924-导入性能 | satisfied | 原日志两份 110,571 行 Snapshot 合计 82.883 秒、Chunk 完成总计 69.044 秒；本轮同文件顺序服务器入口预检 17.068+12.820 秒、入库 31.895+29.883 秒，整体约 151.9→91.7 秒；0831.xlsx 本机上传 API 完整入口上传/冻结 0.132 秒、预检 18.200 秒、入库 28.673 秒；两份 XLSX 每字段与旧 Reader 全量一致，行账本与统计对账；纯入库阶段提升较小，主要收益在预检 |
| R2 | 历史重筛显著提速，多别名同车型批量 Evidence 不再永久重试 | #593；user:20260924-重筛性能 | satisfied | 多别名去重单元+真实 PostgreSQL 回归；确定性 SQL 错误终态分类；5,000 行混合 Replay 17.198 秒，Job 全成功且贡献账本 5,000 行对账；原日志相同类型 100 Artifact 因同键冲突重复 9 次，修后不重复 |
| R3 | “取消并撤回”显著提速，撤回精确性、恢复与后续事实保护不变 | #593；user:20260924-撤回性能 | satisfied | 原日志 5,203 Content 99.752 秒；隔离库 5,000 行（4,100 既有 Evidence、900 新建）26.029 秒；5,000 行纯 Evidence 8.208 秒；101 行精确恢复与 SQL 数上界集成测试；完整 Replay 集成集覆盖接管、幂等和恢复 |
| R4 | 仅改后端，不改 UI/等待过程，不改正式业务语义与生产数据 | user:20260924-范围；AGENTS.md；docs/blueprint/07_技术决策与实施门禁.md | satisfied | 当前 diff 仅后端、配置、测试、基准和技术文档；公共 Contract、Schema、依赖未改；实验只写 aima_ugc_task593_* 隔离库，用户 aima_ugc 只读 |
| R5 | 当前 PR 的测试、文档、Review、CI 与完成审计闭环 | AGENTS.md；#593 | not_satisfied | 待当前 HEAD 证据 |
| R6 | 其他数据导入的取消及撤销同样检查并提速 | user:20260924-其他导入撤销 | satisfied | Campaign 取消并发集成回归；正式容量脚本 1,000 条普通导入撤销 8.797→1.669 秒、SQL 7038→52；同输入 0901.xlsx 撤销 5,530 条从 14.879 秒降到 7.161 秒，预览最终 0.194 秒；其余 Delta 保留精确回退路径 |
| R7 | 同一 Campaign 的多文件与多 Worker 不得以死锁或重复数据换吞吐 | #593；user:20260924-全流程；本轮两 Worker 真实文件故障 | satisfied | 两份 110,571 行真实文件双 Worker 曾在 `schedule_import_jobs()` 触发 PostgreSQL deadlock；改为共享取消门后先锁 Campaign、再锁 Chunk/Content，新增双 Worker 集成回归；相同两文件再次运行成功、110,571 行/56 Chunk 全量对账，预检 33.838 秒、入库 61.233 秒；同 Campaign 并发无稳定吞吐收益，不作为本次提速建议 |

# Validation Matrix

| 验证层 | 是否要求 | 范围 / 计划证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Canonical 转换、别名去重、撤回规则与错误分类的失败和回归测试 |
| 接口 / 契约 | required | Canonical/Job/API 字段与错误、生成契约保持兼容 |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL 下的导入、重筛、撤回、账本、Fencing/重试 |
| 用户 / 工作流验收 | required | 后端 API → Worker → 结果/撤回的可观察状态与对账 |
| 跨组件关键路径 | required | 真实文件 → Artifact → Job → Content → 撤回的代表路径 |
| 外部依赖探测 | not_applicable | 不改变 TikHub 或付费模型边界，本轮输入均为本地文件 |
| 构建 / 打包 / 运行 | required | 当前 Python 环境、正式 Worker 装配和包检查 |
| 文档 / 治理 / 其他 | required | 技术文档、Change Ready、架构/Owner/Secret 和 CI |

# 实施与验收步骤

1. 使用两份真实 XLSX 和隔离库建立阶段 Profile，记录输入、命中率、结果计数与基线；日志不输出正文或 Secret。
2. 先写重筛同车型多别名与永久错误的失败回归，再修生产路径；验证无重试且结果一致。
3. 对预检、转换、入库已证实的热点逐项实验，采用真正降低端到端耗时且不损坏数据语义的实现；做相同输入 A/B。
4. 测量重筛和普通导入撤回每批数据库阶段，在现有 Owner 内减少无谓往返；验证取消/重试/接管、贡献恢复和后续写保护，记录 A/B。
5. 对同 Campaign 两文件双 Worker 做隔离库实验；遇到真实父行锁死锁后统一加锁顺序并复测，不以增加 Worker 数量代替吞吐证据。
6. 同步当前技术文档，重新读取上游要求，做完成审计、两阶段 Review、项目检查与当前 PR CI。

# 兼容、数据、部署与回滚

默认保持 HTTP/Job/Canonical 格式、Schema、依赖与业务语义不变；若 Profile 证明必须改其中之一，先更新本 Change 和正式决策并补迁移方案。生产部署、Migration 和历史正式数据操作不在本次授权。代码回滚使用旧 Worker/应用，保留已经提交的业务和撤回账本；本轮实验只写隔离数据库。

# Completion Audit

- [x] upstream_re_read：2026-09-24 重新读取用户全部补充范围、#593、根 AGENTS 和 Blueprint 07；完成定义包含本机/服务器入口、预检/入库、重筛、两类撤回及取消/多 Worker。
- [x] change_coverage：逐项核对 R1–R7 与真实日志慢段；两份真实 XLSX 的旧 Reader 值、Campaign 总行数与各分类计数逐项一致；实测预检、入库、撤回和双 Worker。
- [x] reverse_audit：由本机上传/服务器目录、Source/Canonical Artifact、Campaign/Chunk/Job、Content/Evidence/来源账本及撤回结果反查消费与恢复；共享字符串、损坏坐标、已复用 Artifact、Job 重试、手工锁和后续事实均有对应测试或全量实验。
- [ ] unresolved_cleared：清零 not_satisfied，或以正式依据记录延期/不适用；证据覆盖当前 HEAD。

# 当前证据边界与剩余风险

- 真实 A/B 只在本机 PostgreSQL 18 隔离库和用户提供的两份文件上成立；没有生产服务器资源、I/O、并发和部署后测量。原两文件纯 Chunk 入库约 69.044 秒，本轮约 61.778 秒；这段改善小于预检收益，Content Owner 写入仍是主要耗时。
- 同 Campaign 两 Worker 在本机既造成一次真实父行锁死锁，修复后 110,571 行完整成功但总耗时没有稳定优于单 Worker；不能以增加 Worker 数量承诺加速。已将父行锁移到 Item/Content 之前，并把临时数据库 OperationalError 分类为 Job retry。
- 普通 Campaign 撤销仍在现有 HTTP 请求里同步完成：5,530 条真实内容 7.161 秒，受影响量更大时可能继续增长；变为异步 Job 需要公共 Contract 与页面消费方式的独立决定，本轮未擅自改变。
- Windows 全量 unit/contract/API 中 3 个既有 POSIX 权限测试因缺 `os.geteuid`/`os.chown` 无法本机通过；其他 1,440 个通过，Linux CI 尚待当前 PR revision 验证。

# 交付状态

Issue #593；分支 `perf/593-import-replay-reversal-throughput`。早期 PR、验证、Review 与 CI 状态将在实施过程中更新；未获合并授权，本 Change 在实现 PR 中保持 Active。
