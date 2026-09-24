---
schema: coding-change/v1
id: CHG-20260924-001142-import-pipeline-throughput
title: 数据导入与 Canonical 重筛全链路性能改造
level: L3
status: done
owner: yuwen.ding
branch: perf/import-pipeline-throughput
created: 2026-09-24T00:11:42+08:00
updated: 2026-09-24
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - content
  - vehicles
  - artifacts
  - jobs
  - persistence
  - frontend
  - logging
  - performance
affected_paths:
  - backend/src/aima_ugc/bootstrap/import_worker.py
  - backend/src/aima_ugc/bootstrap/manual_ingestion.py
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - backend/src/aima_ugc/platform/storage/canonical.py
  - backend/src/aima_ugc/modules/vehicles/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - frontend/src/features/import-batches/
  - tests/
  - scripts/performance/
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/operations/02_4000万历史迁移与Analysis Run运行手册.md
contracts:
  - canonical-content.v1
  - ingestion.import-excel.v2
  - ingestion.historical-import-chunk.v2
  - ingestion.canonical-replay.v1
data_changes: []
---

# 变更摘要

以同一套 Canonical、Brand/Vehicle 与 Content Owner 语义为边界，系统性优化本地 Excel、统一历史数据导入和全历史 Canonical 重筛三条链路。核心工作是消除重复文件扫描与整文件明文副本，把逐行数据库状态机收敛为 Owner 内的集合写入，预编译并复用冻结车型目录，降低 Campaign 进度聚合放大，并建立有硬磁盘预算的统一容量基准和服务器阶段日志。只有三条链路都取得可重复、可量化的吞吐与资源改善，且结果/取消/恢复/撤回等价，才允许合并。

# 背景、现状与问题

服务器运行当前主分支时，25,819 个 Canonical 文件被拆成 259 个 Replay 子任务；一个子任务曾在约 22 分钟只读取 17,017 行，后续约 28,151 行中匹配 6,188、新入库 5,379、已有收敛 809。同期 PostgreSQL 约 185% CPU，Worker 约 5.9% CPU，说明数据库往返、WAL/块 I/O 与多次 Artifact 扫描比纯 Python 计算更接近主瓶颈。

上一项 Change 已把 Replay 的“安全全新内容”路径从约 18,069 条 SQL/1000 行降到 72 条，并取得约 4.31 倍提升；但它不覆盖本地 Excel 逐行统一入库、统一历史 `standard_observation`、已有内容 Replay 收敛、Brand/Vehicle 按行解析、源文件重复哈希、多个明文 JSONL 中间文件，以及历史分块反复聚合 Campaign 状态。用户本机 E 盘剩余空间很小，也要求验证过程对临时数据实行硬上限并自动清理。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 决策作用 |
| --- | --- | --- | --- |
| E1 | 本地 Excel Import 当前产生 Mapper、Canonical 物化、Filter、Dedup 等多个整文件明文 JSONL，并在最终阶段逐行调用统一 Content 入库 | `import_worker.py`、`manual_ingestion.py` | 流式化和集合写入必须一起处理，否则只移动瓶颈 |
| E2 | Canonical Reader 的完整读取会复制/哈希并解析；Replay 预检与执行、部分 Import 物化会重复 Store I/O | `platform/storage/canonical.py`、Replay/Import Worker | 需要保留先预检后写入，但复用同次验证产生的有界输入，不能删除安全边界 |
| E3 | 历史 Snapshot 对 server_path 源执行存储前后元数据检查、Artifact store、额外 SHA-256，再从 Artifact 复制解析并按块写 Canonical | `historical_import_worker.py` | 应减少重复源读取并将完整性证据在正式 Owner 中复用 |
| E4 | 历史 fill-only 已有批量 Repository，但标准策略和 Brand/Vehicle Evidence 存在逐行路径 | `historical_content.py`、`historical_import_worker.py` | 需要在正式 Owner 内补齐集合路径，不能让 Worker 直写表 |
| E5 | 每个历史 Chunk 完成会重新查询 ledger/source/campaign 聚合状态 | `historical_import.py` | 大量 Chunk 会形成累计扫描放大，应使用增量或有界聚合 |
| E6 | BrandVehicleResolver 当前每行解析会重建别名映射并执行子串扫描 | `brand_vehicle.py` | 冻结 Snapshot 应在批次级预编译并复用 |
| E7 | 前端本地多文件上传按文件串行 await | `frontend/src/features/import-batches/store.ts` | 可使用小规模有界并发缩短上传墙钟，但必须保留错误收敛和服务端限制 |

仍待本 Change 用专用 PostgreSQL 和统一容量 Harness 确认：三条链路各阶段墙钟、SQL 分布、临时空间峰值、混合数据比例下的实际提升，以及并发度对锁/WAL 的影响。服务器硬件与生产数据分布不能从本机结果推算，因此必须新增可直接回传的阶段日志。

# 目标、成功标准与非目标

- 本地 Excel `standard_observation` 代表性全新内容 p50 吞吐至少达到当前 main 的 3 倍；若已由 XLSX/硬件带宽主导，则 SQL 数与临时磁盘峰值均至少降低 70%，且提供阶段证据。
- 统一历史 `standard_observation` 全新内容至少 3 倍，`historical_fill_only` 新旧混合至少 2 倍；每千行 SQL 至少降低 70%。
- Replay 已有内容混合收敛至少 2 倍、每千行 SQL 至少降低 70%；现有全新快路径不得回退超过 10%。
- 三条链路临时磁盘峰值相对 main 至少降低 50%；基准默认临时预算不超过 512 MiB，低空间时在写入前拒绝并在异常后清理。
- 结果对账覆盖 Content/Version/Metric、来源账本、Evidence、计数、Job 终态、取消/重试/lease 接管和 Replay 撤回。
- 不删除持久 Raw/Input/Canonical 证据，不跳过首次业务写前的完整预检，不降低 PostgreSQL durability，不引入新基础设施或升级依赖，不执行部署/生产操作。

# 约束与意图决策

本任务是单一 L3 全局工作单元，因为三条链路共享 Canonical Reader/Writer、Brand/Vehicle Snapshot、Content Owner、Job Runtime 和 Artifact 生命周期；拆成独立并行 Change 会同时修改相同 Owner 和基准，容易制造语义漂移。本轮采用分阶段纵向切片，但保持一个 Issue、分支、Change 与 PR。

Artifact 持久证据和首次写入前的完整预检是硬边界。优化可减少同一次验证后的重复复制/解析，可使用有界 spool 或验证证明，但不能边读边产生不可回滚的业务可见写入。Content、Evidence、Artifact、Campaign 和 Job 表仍由现有 Owner 写入；性能优化不能在 Worker 中形成第二套 SQL 业务规则。

用户授权本任务在范围内生成有界临时数据、提交、PR 和完成门禁后的 main 合并；没有授权 Release、Deploy、生产 Migration 或生产数据变更。服务器验证以新增日志和运行手册由用户执行，回传证据后再继续调优；本地不可验证项必须如实标记。

# 修改方案与决策依据

采用“共享流式批次 + Owner 集合写入 + 增量状态 + 可观测基准”的组合方案：

1. 先建立三链路统一容量 Harness，记录 main 的阶段、SQL 与临时磁盘基线，并以专用数据库、空目录、磁盘预算和 finally 清理保证安全。
2. 为 Canonical 验证增加一次读取可复用的有界 spool/证明能力，Import/Replay 在保持全量预检前置的前提下，不再无条件复制、解压、解析同一 Artifact 多次。
3. 把 mapping→filter→dedup→ingest 改为有界流式批次；需要全局去重的身份只保留有界索引，不生成多个整文件副本。持久 Canonical 继续由 ArtifactService 管理。
4. 扩展现有 Content/Evidence Owner 的集合能力，按全新/已有/冲突分区；数据库唯一约束决定竞争结果，真正冲突才回退逐行正式路径。
5. Brand/Vehicle 冻结快照在任务/批次级编译一次；历史分块完成用增量计数或只在必要终态执行全量复核。
6. 前端本地上传采用配置固定的小规模并发；后端仍独立校验每个文件，任一失败保留 Campaign 事实并停止 finalize。
7. 各阶段结束记录一条 DEBUG 结构化事件，终态记录低频 INFO 摘要；服务器可用稳定 event 与 ID 定位读取、转换、筛选、数据库、Evidence 或状态聚合瓶颈。

## 备选方案与取舍

不采用“只增加 Worker”的方案，因为它会在当前 PostgreSQL/I/O 已饱和时放大竞争；不采用绕过 Owner 的 staging/COPY 全量 SQL 重写，因为会复制复杂业务状态机；不采用删除预检、关闭 fsync/synchronous_commit 或减少证据保留换性能。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 建立一个全局任务覆盖三条数据链路并最终合并 main | external:https://github.com/dingyuwen777/AIMA_UGC/issues/587#AC8 | explicitly_deferred | 同一 Issue、分支、Change 与 PR 已覆盖三链路；guarded merge、main-fresh、自动 Archive 与 Closure 必须在当前 HEAD 的 required CI 成功后按顺序完成，不能在 Change Ready 前伪造为已发生 |
| R2 | 本地 Excel 代表性场景取得 3 倍或等价资源门槛，结果一致 | external:https://github.com/dingyuwen777/AIMA_UGC/issues/587#AC2 | satisfied | 1000 行三轮 p50：main 24.095 秒、候选 5.401 秒，4.461 倍；SQL/千行 16073→85（-99.47%），监测临时峰值 6,671,564→1,742,801 字节（-73.88%）；PostgreSQL 集成与结果计数通过 |
| R3 | 统一历史标准导入 3 倍、fill-only 混合 2 倍且 SQL 降低 70% | external:https://github.com/dingyuwen777/AIMA_UGC/issues/587#AC3 | satisfied | standard p50 41.31→173.87 行/秒（4.209 倍），SQL 16069→81；fill-only 54.38→188.54 行/秒（3.467 倍），SQL 12081→96；新旧/非空保留/账本/Evidence 集成覆盖通过 |
| R4 | Replay 已有内容 2 倍、SQL 降低 70%，全新快路径无明显回退 | external:https://github.com/dingyuwen777/AIMA_UGC/issues/587#AC4 | satisfied | 混合场景 p50 11.010→5.399 秒（2.039 倍），SQL 4860→82（-98.31%）；全新场景 5.985→5.490 秒，反而快 8.27%，SQL 保持 72 |
| R5 | 三链路临时磁盘峰值降低 50%，本机临时预算不超过 512 MiB | external:https://github.com/dingyuwen777/AIMA_UGC/issues/587#AC5 | satisfied | Excel 可比临时峰值下降 73.88%；历史与 Replay 的 PostgreSQL `temp_bytes` 在 main/候选均为 0，比例数学上不适用且候选无 spill 回退；三脚本均强制默认 512 MiB 预算、最低剩余空间检查和失败清理，测试验证仅删除脚本自有输出、不误删成功报告 |
| R6 | 业务结果、预检、Job、取消/恢复、fill-only、Replay 撤回等价 | external:https://github.com/dingyuwen777/AIMA_UGC/issues/587#AC6 | satisfied | 相关 Content/Ingestion/Vehicles PostgreSQL 集成 132 通过；取消/lease/撤回 8 通过；本地导入最终集成 8 通过；新增已有内容 101 行集合更新回归验证 Version/来源账本并限制 SQL；Replay selected scope 修复并验证不会误停用范围外 Evidence |
| R7 | 提供低噪声脱敏阶段日志和可复制的服务器排障命令 | external:https://github.com/dingyuwen777/AIMA_UGC/issues/587#AC7 | satisfied | 新增 Excel、历史 discovery/snapshot/chunk、Replay preflight/ingestion/batch 稳定事件；日志只含关联 ID、计数、字节、耗时/吞吐和临时峰值；Operations 02 已提供按 job/run/event 过滤及 PostgreSQL 活动/等待/WAL 查询命令 |
| R8 | 完成 Unit/Contract/PostgreSQL/Frontend/容量/文档/Review/CI 证据 | external:https://github.com/dingyuwen777/AIMA_UGC/issues/587#AC8 | explicitly_deferred | 本地分层验证、三轮容量证据、文档检查与两阶段自审已完成；仅 PR 当前 HEAD required CI、合并后 main-fresh、Archive governance 与 Closure Audit 按交付顺序延后到 Ready 后执行 |

# 计划改动

1. 基准与 Red：扩展容量脚本，固定全新/已有/混合输入、SQL 计数、阶段耗时与临时峰值；在 main 上取得小规模三轮基线，新增会因重复扫描/逐行写入而失败的回归。
2. 流式与磁盘：为 Canonical/Excel/过滤/去重建立共享迭代批次，复用预检结果，消除不必要整文件副本；实现磁盘预算和异常清理。
3. 数据库与车型：扩展 Content/Evidence 集合 Owner，预编译 Resolver，批量处理新/旧内容并保持冲突回退与事务/Fencing。
4. 历史状态：减少源重复读取和 Campaign/Batch 重复聚合；验证 standard/fill-only/local/server_path 的一致结果。
5. 上传与观测：有界并发上传；加入阶段 DEBUG 和终态 INFO，补服务器日志/PostgreSQL 排障命令。
6. 迭代基准：同机同库同数据至少三轮 p50；不达门槛则继续按阶段证据定位，不提前 Ready。
7. 文档、Completion Audit、Deep Review、PR current-head CI、guarded merge、main-fresh、自动 Change Archive 和 Issue Closure。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | 流式批次、去重、Resolver 编译、磁盘预算、阶段计时、上传并发和增量计数 |
| 接口 / Contract | required | Canonical/HTTP/Job/生成 Client 兼容；若扩展字段则生成物与兼容检查同步 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL 下新/旧/冲突/fill-only、来源账本、Evidence、事务回滚、Fencing、取消、接管、撤回和 SQL 计数 |
| 用户 / Workflow Acceptance | required | 本地上传、历史 Campaign、Replay 在运行中心的进度、失败、取消、结果与诊断信息 |
| 跨组件 Golden Path | required | API→Artifact→Job→Worker→Canonical→Content/Evidence→结果的三条代表性真实链 |
| External Dependency / Provider Probe | not_applicable | 三条链路不发送 TikHub/LLM 请求，输入使用本地有界合成文件 |
| Build / Package / Runtime | required | Python/TypeScript 静态检查、正式 Worker/Frontend 构建、Compose 配置相关检查 |
| Docs / Governance / Other | required | Appendix/Operations/必要 Blueprint、Issue/Change/PR 追溯、容量 JSON、Completion Gate、Deep Review、PR/main CI |

# 风险、兼容性、迁移与回滚

- 语义风险：集合写入可能改变冲突顺序、版本生成、fill-only 或贡献撤回。用同输入旧/新数据库快照和失败注入覆盖，无法证明的行保留正式逐行回退。
- 内存风险：去掉临时文件后可能把压力移到内存。所有流式批次与去重索引必须有明确上限；容量基准同时记录峰值，不接受无界全量列表。
- 磁盘风险：Persistent Artifact 是业务证据，不能以删除换空间；只减少临时副本，并在创建前检查空间、异常时清理任务自有目录。
- 并发风险：上传/Worker 并发可能放大锁和 WAL。默认采用小规模有界并发，并以 SQL/锁等待/阶段日志决定上限。
- 兼容/Migration：当前优先不改 Schema/Contract；若事实证明必须变更，先更新本 Change 与用户决策，再提供 Alembic 和回滚证据。
- 回滚：性能或一致性门槛失败不合并；合并后可整体 revert。既有持久 Artifact 保持可读，Replay 贡献使用正式 reversal，不使用手工 SQL。

# 文档、依赖、部署与发布影响

Docs Impact 为 full（限定在数据导入链路）：至少同步 Appendix 08、Operations 02，以及实现实际改变的 Blueprint 02/03/04/05 与 Roadmap 容量事实；不重写无关文档。预计无新依赖、无版本升级。若无 Migration/Contract 变化，明确记录 not applicable；若出现则按机器事实完整同步。合并不包含 Release/Deploy/生产 Migration，服务器需在未来正式发布后按运行手册验证。

# 完成审计

- [x] upstream_re_read：Ready 前已重新读取 #587、本轮用户决定、相关 Blueprint/Appendix/Operations、归档流程和最终代码，独立重建 AC1—AC8。
- [x] change_coverage：已逐条确认 AC、硬不变量、非目标和三链路输入/输出；性能原始样本、环境与比率固化在 `performance-results.json`。
- [x] reverse_audit：已从前端有界上传/API/Artifact/Job 正向追踪到 Canonical、Content/Version/Metric、来源账本、Evidence 与结果，并从取消/lease/重试/撤回和服务器阶段日志反向核对实际消费者。
- [x] unresolved_cleared：Requirement Traceability 已无 `not_satisfied`；仅把必须发生于 Ready 之后的 current-head CI、merge、main-fresh、Archive 与 Closure 按真实时序标为 `explicitly_deferred`。

# 完成证据与状态

候选生产代码 revision 为 `3874067c2e4fd12f55c77b8f444b4762c1c953e6`，基线 revision 为 `cdd8482dd19c511fe9905794b9ef58de12a57db5`；详细环境、三轮原始样本、p50、SQL 与临时空间证据见同目录 `performance-results.json`。

实现结果：本地 Excel 1000 行全新内容 p50 提升 4.461 倍；统一历史 standard 提升 4.209 倍，fill-only 混合提升 3.467 倍；Replay 混合提升 2.039 倍，全新快路径提升 8.27%。三条数据库写入路径的 SQL/千行分别从 16073→85、16069→81 / 12081→96、4860→82。Excel 可比临时峰值下降 73.88%；历史与 Replay 两侧 PostgreSQL 临时落盘均为 0，因此没有可计算的 50% 降幅，但候选保持零 spill，并由 512 MiB 硬预算、空闲空间保护和失败清理约束。

实现保持 Canonical/HTTP/Job Contract、Schema、Migration、依赖和部署拓扑不变。首次业务写前的完整预检、持久 Raw/Input/Canonical 证据、Content Owner、唯一约束、事务 durability、Job lease/fencing/cancel/retry/progress 和 Replay reversal 均未被关闭。前端只把多文件上传改为固定 3 路有界并发；后端仍逐文件独立校验并维护原 Campaign/Item 事实。

本轮新鲜验证：

- `ruff format --check` 与 `ruff check` 覆盖 27 个改动 Python 文件，均通过；`mypy backend/src` 366 个源文件通过。
- `tests/integration/content tests/integration/ingestion tests/integration/vehicles`：132 通过；其中取消/lease/撤回定向 8 通过，本地导入最终集成复验 8 通过。
- 容量脚本/Resolver/离线处理相关 Unit：33 通过；三个脚本成功路径小样本 smoke 均通过，失败清理、专用数据库拒绝与报告保留均有回归。
- Frontend 定向 Store：10 通过；`npm run lint`、`npm run build` 通过（Vite 220 modules）。
- 文档导航和两项文档一致性检查通过；性能 JSON 已重新解析。
- 非数据库全量测试：1430 通过、8 skipped、12 subtests 通过、4 失败。3 个失败来自 Windows 不具备 Linux `os.geteuid/os.chown`；1 个来自任务外用户 Provider 输出目录含原始 `xhsdiscover` 标识。相关产品测试、静态检查和构建均通过；未删除或改写该用户目录，也未把这些环境/任务外失败伪装为成功。

两阶段自审先按需求、Contract、Owner 与异步语义审查，再按最终 diff 和证据复核。审查发现并修复：selected Replay 曾会停用范围外 Evidence；已有 Content 仍逐行收敛；Resolver 每行做快照深比较；失败基准残留半成品且历史脚本在数据库门禁前写 fixture；Excel 临时峰值未计入压缩 Canonical 临时副本。每项均补了回归并重跑相关层。当前没有未解决的已确认生产代码 finding。

当前分支 `perf/import-pipeline-throughput`，Requirement Source 为 #587，PR 为 #588。用户工作区 `.codex/config.toml`、既有 pytest 临时目录和任务外文件不属于本 Change，未修改或提交。当前只剩 Ready 后的 PR current-head CI、guarded merge、main-fresh、自动 Change Archive 和 Issue Closure；不包含 Release、Deploy、生产 Migration 或生产数据操作。
