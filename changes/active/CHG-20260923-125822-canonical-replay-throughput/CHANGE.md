---
schema: coding-change/v1
id: CHG-20260923-125822-canonical-replay-throughput
title: 全历史 Canonical 重筛吞吐优化
level: L3
status: ready_for_review
owner: yuwen.ding
branch: perf/canonical-replay-throughput
created: 2026-09-23T12:58:22+08:00
updated: 2026-09-23T15:37:00+08:00
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - storage
  - jobs
  - logging
affected_paths:
  - backend/src/aima_ugc/
  - migrations/versions/
  - tests/
  - docs/
  - scripts/performance/
contracts:
  - canonical-content.v1
  - ingestion.canonical-replay.v1
data_changes:
  - canonical_replay_validation_proofs 可再生验证证明
  - canonical_replay_runs 检查点
  - contents 与 canonical_replay_content_changes 业务和撤回事实
---

# 变更摘要

通过可失效的 Canonical 预检证明、Replay/Content Owner SQL 合批与多 Worker 独立日志提高多行文件的重筛吞吐；保持首笔业务写入前全输入验证、检查点、取消与精确撤回。隔离基准中的来源时间戳失败已复现并修复；稀疏文件的冷启动性能未证明显著改善，生产效果仍须按真实分布测量。

# 背景、现状与问题

全历史重筛需在不削弱预检、Content Owner、检查点、取消和精确撤回语义的前提下提高总吞吐。当前每文件重复完整解析，每条命中行又产生多次数据库往返；多 Worker 虽可领不同子任务，却共享数据库和同名日志文件。本 Change 记录预检、数据库、并发与基准的完整施工边界；不执行生产迁移或全量重筛。用户随后同意“没问题的话合并主分支”，因此仅在完成审计、Review 与 CI 后才可合并。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 决策作用 |
| --- | --- | --- | --- |
| E1 | 每 Run 最多 100 个文件，首笔写库前完整预检 | `backend/src/aima_ugc/bootstrap/canonical_replay_worker.py` | 保持坏文件零业务写入 |
| E2 | Reader 每次打开复制并校验摘要，随后解析两遍 | `backend/src/aima_ugc/platform/storage/canonical.py` | 消除重复工作，不能只信元数据 |
| E3 | 1,000 行只是一笔事务／检查点，匹配内容逐条声明身份并写入 | `backend/src/aima_ugc/bootstrap/canonical_replay_worker.py` | 优化 SQL 往返但不绕过 Owner |
| E4 | Replay 的贡献账本与 Source/Evidence 在业务事务内产生 | `backend/src/aima_ugc/bootstrap/canonical_replay_worker.py` | 批量路径必须保留精确撤回 |
| E5 | 多 Worker 共用 `worker.log` 且按进程轮转 | `backend/src/aima_ugc/platform/logging/setup.py`、`compose.yaml` | 扩容前隔离文件名 |

待确认：目标服务器真实总行数、文件大小、命中率、数据库资源和实际瓶颈。没有服务器测量不能宣称固定加速倍数；本任务先建立可重复本地/隔离环境基准。

# 目标、成功标准与非目标

- 预检在每个子任务首笔业务写入前检查全部输入，有损坏文件时保持该子任务零业务写入。
- 通过持久、可失效的验证证明减少重复解析；历史文件没有有效证明时仍须完整验证。
- 沿现有 Owner 批量化匹配行处理，保持 Current、Version、Metric、来源、Evidence、检查点和撤回结果。
- 支持可控多 Worker 并发与安全日志轮转，以阶段与数据库指标决定容量。
- 不改变 HTTP、Canonical 文件格式、品牌车型编辑触发条件；不部署、不运行生产 Migration。是否合并由本轮新鲜证据门禁决定。

# 约束与意图决策

继续保持每个子 Run 首笔业务写入前的全输入预检、Content Owner 唯一写入、Fencing、检查点、取消和精确撤回。新增证明只可在压缩字节、验证版本和当前来源关系均复核后复用；数据库元数据中的 SHA 值本身不构成证明。生产 Migration、部署与真实全量数据运行不在授权范围；用户补充授权只允许全部门禁完成后合并主分支。

# 修改方案与决策依据

采用选项 2。后续重筛可在逐字节 SHA 和当前来源关系复核后跳过重复 Contract 解析；旧文件逐件完整验证并记录证明。命中行的 Run 身份与贡献账本可安全批量写，Content Current/Version/Metric、来源贡献和自动证据仍走原 Owner，避免复制业务规则。基准同时报告多小文件的固定开销和较大文件的逐行 SQL 开销。

## 备选方案与取舍

1. 保持当前完整预检，只优化 Reader 第二次读取和批量声明身份：迁移风险低，可立即减少解析和 SQL，但每次重筛仍重复预检，其他逐行写入仍慢。
2. 已采用：在方案 1 基础上增加与压缩字节摘要、当前 Contract/来源规则及来源关系绑定的持久证明；旧文件首次完整验证时逐件回填，之后逐字节与当前来源复核；在现有 Owner 内减少可证明冗余的逐行 SQL。新增向前 Schema，但不做盲信式历史回填。
3. 删除预检、边读边写、遇错自动撤回：首次读取成本最低，但当前撤回不是失败子任务自动回滚，坏文件会形成已可见部分写入，改变已批准安全语义，不采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 任一坏文件在子任务首笔写入前被发现，取消/重试/Fence 仍有效 | #581 / AC1 | satisfied | 后部坏文件及导入父级失效零业务写入、证明命中后篡改零写入、原有取消/接管/Fence 集成测试通过 |
| R2 | 消除无必要的重复解析，历史和新 Artifact 均有安全验证路径 | #581 / AC2 | satisfied | `CanonicalArtifactReader` 单遍专用预检；证明复用、版本失效、篡改回归通过；`20260923_0060` |
| R3 | 减少逐行数据库往返，保持内容、证据、来源、账本及撤回等价 | #581 / AC3 | satisfied | 未修改 main 与当前分支同结构 100 行样本：SQL 2749→1858、Replay 3.603→3.067 秒；摄取、内容、采集集成 262 项及撤回/账本用例通过 |
| R4 | 多 Worker 日志安全轮转，并按真实负载控制并发 | #581 / AC4 | satisfied | 正式入口进程独立 UUID 日志；301 文件本地 1/2/4 Worker 对照，运行手册限制服务器扩容条件 |
| R5 | 可重复基准和相关集成、迁移验证证明改进与兼容 | #581 / AC5 | satisfied | 全新测试库带异常定位复现：数据库开始时间晚于应用完成时间，`ProviderAttemptV1` 拒绝非计费来源；强制时钟落后回归 Red→Green，同路径 301 文件完整复测 301/301 成功。main/当前 100 行同结构基准 SQL 2749→1858；迁移回环/Schema 与相关集成通过。301 个单行文件 main 31.575 秒、当前样本 28.676/34.148 秒，不能认定冷启动稀疏文件已提速。 |

# 计划改动

1. 预检与 Reader：在 `platform/storage` 与 Replay Worker 保留全文件前置校验，消除内部冗余解析；测试后部坏文件和中途取消。
2. 验证证明：新增 `20260923_0060` 与 Replay Owner 证明表；历史文件首次完整验证后逐件回填，证明命中仍校验当前字节与来源；测试版本失效、篡改、接管与部分回填。
3. 数据库：先量化逐行热点，再在现有 Owner 内批量声明身份、预取与写入；以隔离 PostgreSQL 对照旧语义和撤回结果。
4. 派生刷新：已检查当前证据写入路径；未获得足够证据证明可安全合并自动 Brand/Vehicle 刷新，保持原 Owner 同事务行为，不为减少 SQL 绕过触发器或证据规则。
5. 并发、观测与基准：隔离 Worker 文件日志，记录阶段耗时和吞吐；从 1、2、4 Worker 逐级比较总吞吐、锁、WAL、I/O 和连接占用。
6. 同步当前运行文档，执行完成审计、独立 Review、CI 和 PR Ready；仅当 R5 缺口闭合且无阻塞 Finding 时按用户最新决定合并 main。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Reader 校验、验证证明、日志命名及批次规则 |
| 接口 / 契约 | required | Canonical 文件与 Job/API 兼容、Schema/Migration 检查 |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL 的写入、账本、取消/重试/Fence/撤回和 Migration |
| 用户 / 工作流验收 | required | 手动重筛到运行结果，坏文件失败与撤回状态 |
| 跨组件关键路径 | required | API → Job → Artifact → Content → 结果的代表性路径 |
| 外部依赖 / 供应方探测 | not_applicable | Replay 不调用 TikHub 或付费模型，外部服务不是本次瓶颈事实源 |
| 构建 / 打包 / 运行 | required | Worker 启动、Compose 多副本配置与正式包检查 |
| 文档 / 治理 / 其他 | required | Operations/Appendix、Change、架构/Owner/Secret/CI 门禁 |

# 风险、兼容性、迁移与回滚

新 Schema 仅向前增加验证证明，不改历史 Migration；旧代码不依赖新表。历史 Artifact 不直接信任 SHA 元数据，需完整验证后逐件回填；失败可重试。代码回滚时保留新增证明表但旧 Worker 不读取它；不能对可能已执行重筛的数据直接删除或回滚 Schema。部署须先升级数据库，再启动新 Worker。业务写入与派生刷新仍保持原事务、Fencing 和撤回语义。本任务没有生产操作授权。

# 文档、依赖、部署与发布影响

同步数据库/Artifact Blueprint、Replay 实现说明与 4000 万历史迁移运行手册，明确证明失效、Worker 独立日志、多 Worker 容量测量和 `20260923_0060` 部署顺序。无新依赖、无公共 HTTP/Job/Canonical 格式变化；前端现有运行记录、取消和撤回入口保持原行为。生产部署与 Release 仍需独立授权及服务器容量验证。

# 完成审计

- [x] upstream_re_read：重读 #581 和相关正式文档，独立重建完成定义。
- [x] change_coverage：核对 AC1–AC5 均进入本 Change；原始时钟失败和 CI 旧日志路径也进入回归边界。
- [x] reverse_audit：从 Artifact/数据库生产者到运行中心结果及撤回反向核对，保持原 API、Job 结果和可逆账本。
- [x] unresolved_cleared：AC1–AC5 的本地可验证要求满足；服务器真实文件分布与容量未确认，按运行手册上线前测量。

# 完成证据与状态

当前分支 `perf/canonical-replay-throughput`，Issue #581，PR #582，尚未合并。隔离 PostgreSQL 到 `20260923_0060 (head)` 且 `alembic check` 无差异；独立一次性数据库完成 `0059→0060→0059→0060` 回环及 Schema 检查。单元/Contract/API 1,397 通过、8 跳过（排除三个与本任务无关的 Windows/本地原始输出失败文件）；最新摄取/内容/采集集成 262 通过；Ruff、Mypy、文档事实/导航、架构与表 Owner 检查通过。未修改 main 与当前分支的 100 行单文件本地样本：Replay 3.603→3.067 秒，SQL 2749→1858（约少 32%）；301 个单行文件 main 31.575 秒，当前分支不同运行 28.676/34.148 秒，冷启动稀疏场景没有稳定加速证据。旧失败在新隔离库精确复现为应用/数据库时钟偏差：`dispatch_started_at` 比应用生成的 `completed_at` 晚；参照同仓撤销来源逻辑将完成时间约束为至少等于已持久化的创建/开始时间，强制偏差测试先失败后通过，修复后全新 301 文件运行全部成功且账本 301 行。以上仅本机样本，不可推算服务器 25,819 件的完成时间。CI 曾因正式 Worker 改为实例日志后验收脚本仍检查 `worker.log` 而失败；已同步新文件名，等待新提交的 CI 验证。正式 Review 与 CI 未完成前禁止合并。
