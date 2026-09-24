---
schema: coding-change/v1
id: CHG-20260925-001813-collection-runtime-revocation
title: 修复撤销后采集运行故障并按资源提升历史数据吞吐
level: L3
status: ready_for_review
owner: yuwen.ding
branch: fix/601-collection-runtime-revocation
created: 2026-09-25T00:18:13+08:00
updated: 2026-09-25
completion_gate: required
depends_on: []
affected_areas:
  - collection
  - ingestion
  - frontend
  - platform
  - deployment
affected_paths:
  - backend/src/aima_ugc/adapters/persistence/postgres/jobs.py
  - backend/src/aima_ugc/bootstrap/runtime.py
  - backend/src/aima_ugc/entrypoints/worker_main.py
  - backend/src/aima_ugc/platform/capacity.py
  - backend/src/aima_ugc/platform/config/settings.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_runtime_queries.py
  - backend/src/aima_ugc/adapters/persistence/postgres/canonical_replay.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_reversal_worker.py
  - backend/src/aima_ugc/bootstrap/historical_import_http.py
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - backend/src/aima_ugc/modules/ingestion/README.md
  - docs/02_环境运行与部署.md
  - docs/appendix/08_数据入口与统一入库实现.md
  - frontend/src/features/import-batches/format.ts
  - frontend/tests/collection-runtime.spec.ts
  - scripts/deploy/start_compose.py
  - tests/unit/jobs/test_worker_entrypoint.py
  - tests/unit/jobs/test_historical_terminal_capacity.py
  - tests/unit/platform/test_capacity.py
  - tests/unit/platform/test_settings.py
  - tests/unit/test_compose_auto_scripts.py
  - tests/integration/collection/test_stage8e_collection_http_runtime.py
  - tests/integration/database/test_canonical_replay_repository.py
  - tests/integration/ingestion/test_stage12_historical_campaign_worker.py
  - tests/integration/ingestion/test_canonical_replay_worker.py
  - tests/integration/jobs/test_job_runtime.py
contracts: []
data_changes: []
---

# 变更摘要

本机 Docker 中撤销 Data Import Campaign 后，采集运行列表因未知公共状态返回 409；随后独立发起的全量重筛仍纳入该已撤销来源，产生失败子任务。修复读取投影与来源选择，并让已排队的重筛跳过后来撤销的来源。同一组六个 XLSX 的隔离 Docker 对照还确认 API 容器的较小 CPU 配额误降新 Campaign Chunk 与 Job 窗口；改由 Worker 有效预算决定窗口，Worker 容器在既有总配额内按队列动态增减进程。保留公共状态枚举、Schema、撤销账本和入库 Owner。

# 背景、现状与根因

- 用户执行本地手工导入、服务器路径导入、历史重筛、撤销导入后，采集运行中心显示加载失败。实际列表 API 为 409，概览 API 为 200。
- `historical_import_campaigns.status` 进入 `revoking` / `revoked`；列表 SQL 原样透传状态，而公共 `CollectionRuntimeStatus` 只接受 `queued/running/partial_success/succeeded/failed/cancelled`。其中一条撤销记录导致整个分页结果验证失败。
- 00:05 的 `canonical_replay_all_created` 审计事件与 23:54 的 `data_import_campaign_revocation_requested` 是两个请求；撤销代码不会创建重筛。现场后发起的全量重筛仍选择已撤销 Campaign 的 Chunk。4 个子任务中 1 个成功、3 个失败，失败子任务曾完成预检，至少一个在失败前已提交部分行。
- 原因是全量枚举和显式来源分类只校验 linked Canonical、Chunk 与 Job，未校验所属 Campaign 撤销状态；Worker 需要在冻结后继续处理其他有效来源，并在每批事务中防止撤销与重筛写入竞态。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 对方案的作用 |
| --- | --- | --- | --- |
| E1 | 本地列表 API 409、概览 200；撤销 Campaign 状态为 `revoked` | 本机 Compose API 与 PostgreSQL 只读检查、`collection_runtime_queries.py` | 公共投影必须归一化状态，同时保留真实阶段 |
| E2 | 撤销与后续全量重筛分别由独立审计请求创建 | 本机 `audit_events` 只读查询、撤销与重筛 HTTP Service | 撤销不自动触发重筛 |
| E3 | 后续全量重筛 1 个子任务成功、3 个失败，失败来源关联已撤销 Campaign | 本机 `canonical_replay_runs`、`jobs`、Artifact 关系只读查询 | 全量枚举须排除撤销来源，已冻结输入须复核 |
| E4 | 当前重筛批次写入与 checkpoint 同事务，并具备请求级贡献撤回 | `canonical_replay_worker.py`、`canonical_replay.py`、模块 README | 跳过来源应推进 checkpoint，既有写入仍由请求级撤回处理 |
| E5 | `start_compose.py` 根据 Docker Engine 资源生成限制；原代码固定一个 Worker 进程且由 API 较小配额冻结 Chunk/Job 窗口 | 启动脚本、容量代码、旧运行日志与隔离 Docker A/B | 将 API 判断与 Worker 预算对齐，进程在容器总额度内动态伸缩 |

## 运行数据及结论边界

隔离 Compose 使用与用户本轮相同的 3 个手工 XLSX（170,310 行）和 3 个服务器 XLSX（168,792 行），每轮独立空 PostgreSQL 18.4、相同 Brand 规则与 Docker Engine（12 CPU / 15,822 MiB），不触碰用户原有 Compose。手工上传、预检、导入、初次全量重筛、普通导入撤销、撤销后全量重筛均由公开 HTTP 完成；Scheduler 关闭，Provider 禁用。所有导入行均被当前选择的无匹配 Brand 过滤，因此导入列测的是过滤路径；初次重筛随后对同一 Canonical 全量扫描并实写 35,288 行，补足写库路径。计时是单次墙钟，受主机其他负载影响，不是 p95 或跨服务器保证。

| 同文件实验 | 手工导入预检 / 入库 / 全程 | 服务器导入预检 / 入库 / 全程 | 初次全量重筛 | 普通导入撤销 | 撤销后重筛 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 原容量判断：1000 行、单 Worker | 31.8 / 24.6 / 57.2 秒 | 32.8 / 24.7 / 57.5 秒 | 170.5 秒 | 19.6 秒 | 67.7 秒 |
| 2000 行、单 Worker | 27.7 / 20.6 / 49.2 秒 | 29.8 / 20.6 / 50.4 秒 | 161.4 秒 | 22.7 秒 | 62.5 秒 |
| 2000 行、双 Worker、相同总额度 | 19.5 / 15.4 / 35.7 秒 | 21.6 / 15.4 / 37.0 秒 | 118.7 秒 | 19.8 秒 | 63.5 秒 |
| 最终验证镜像：API 读 Worker 预算、容器内动态进程 | 20.5 / 16.5 / 37.9 秒 | 22.6 / 16.6 / 39.1 秒 | 134.8 秒 | 22.8 秒 | 67.7 秒 |

最终验证镜像相对原容量判断，手工全程约缩短 33.8%、服务器全程约缩短 32.0%、初次重筛约缩短 20.9%；撤销无可证实的提速，撤销后重筛仍有波动。上述四种配置与最终验证镜像的初次重筛均扫描 339,102 行、入库 35,288 行。最终普通撤销后采集运行列表 HTTP 200，后续重筛只选择仍有效的 168,792 行来源并成功；本机旧故障 409 与无效来源失败路径已被切断。

请求级重筛撤回 A/B 使用独立空库中的同六个文件和相同操作顺序：先撤销手工导入，再由另一轮重筛接管 16,999 条内容，最后撤回初次重筛。逐条结清账本的基线为 122.7 秒；按批结清已接管内容后为 105.3 秒，约缩短 14.2%。两轮均撤回 35,288 条，隐藏 18,289 条、保留/跳过 16,999 条，采集运行列表返回 200。两轮均为 71 批 500 条；一次运行中资源采样 Worker 225 MiB / 3.09 GiB、PostgreSQL 569 MiB / 4.33 GiB，非峰值。剩余时间主要花在 18,289 条需要精确逆向的 Content Delta 上。

第三轮把本机撤回探索上限放宽到 1500 条，控制器实际多次尝试 1000 后降回 500，同样的撤回用了 120.8 秒，未带来收益。最终保留同一 500 起步和 500 步长，但要求可用 Worker 内存达到每千行约 3 GiB 才开放相邻上档：本机约 2.9 GiB 不重复低收益探测；模拟 4.8 CPU / 11 GiB 可探索至 2000，9.6 CPU / 24 GiB 可探索至 4500，是否真正升档仍由每台服务器的批次吞吐和事务时间决定。这些模拟值是资源上界，不是服务器已验证的最优批量。

最终验证镜像按该策略撤回 35,288 条用了 97.7 秒，相对旧路径约缩短 20.4%；完成日志记录 71 批、35,288 条、批次耗时合计 96,801 毫秒和最慢批 1,747 毫秒。隐藏/保留/跳过计数仍为 18,289 / 16,999 / 16,999，采集运行列表为 HTTP 200。两次优化运行的 97.7 和 105.3 秒之间存在主机波动，不能把约 20% 写成服务器保证值。

新阶段日志把手工 1000 行快照转换合计约 30.7 秒拆为 Reader/Mapper 约 16.8 秒、Chunk 发布约 13.5 秒；2000 行手工快照发布降至约 10.3 秒，Reader/Mapper 仍约 16.7 秒。文件复制、ZIP 校验合计远小于解析和发布。最终重筛 Run 的内容和证据写入约占入库阶段的主要部分，文件读取约数秒；并行两个独立 Run 缩短墙钟，但数据库事务时间仍是后续重点。最终 Worker 扩容日志记录 1→2，API 日志记录 Worker 预算 3.59 CPU / 3,164 MiB、冻结 2000 行和窗口 2；空闲缩容日志已在前一轮同代码进程池实验观察到。一次 `docker stats` 采样显示 Worker 344.7 MiB / 3.09 GiB、PostgreSQL 325.2 MiB / 4.33 GiB；采样不是峰值。

## 全链路性能评估与后续方案

| 环节 | 本轮证据与边界 | 下次可验证的优化方向 |
| --- | --- | --- |
| 本地上传 / 服务器发现 | 本轮服务器只发现 3 个文件，用约 40 毫秒；没有大型目录、网络盘或上传链路对照 | 保留目录深度/文件数安全护栏；分别记录上传收包、Artifact 写入、目录遍历与清单事务。发现慢时再优化遍历，不把安全阈值当数据库容量档位 |
| 文件快照与预检 | 新日志显示三个手工文件在 1000 行档 Reader/Mapper 约 16.8 秒、Chunk 发布约 13.5 秒；2000 行将发布降至约 10.3 秒，两个 Worker 让文件快照重叠 | 若继续提升，须对 Writer 序列化/Artifact 元数据事务做同文件 A/B；任何缓存或减少二次校验仍须保留 SHA、ZIP 资源限制与崩溃恢复证明 |
| Chunk 入库 | 2000 行档使 Job 数约减半，过滤路径 24.6→16.4 秒；本次导入 339,102 行全部过滤，不能外推大量写入 | 用全过滤、大量新建、大量已有、混合作者四种数据形态分别测 Content、Evidence、Ledger、锁与 WAL；单次历史写入当前硬限制 2000 行，扩大 Chunk 前须重构事务内分段语义并实测 |
| 全量重筛 | 同数据 170.5→134.8 秒；INFO 聚合显示每 Run 的 Content/Evidence 数据库阶段显著长于文件读取，并行两个 Run 有真实收益 | 对相同匹配率与并发数测 SQL/锁/WAL、Content/Evidence 阶段，优先优化持久 Owner 热点；不能用本轮不同数据分布的单次时间推断线性扩容 |
| 撤销 / 撤回 | 同数据普通撤销约 19.6—22.8 秒；初次重筛的 35,288 条贡献在后续重筛接管 16,999 条后撤回，旧路径用了 122.7 秒，其中已接管内容仍逐条更新账本 | 已接管内容改为单批集合 UPDATE 后两轮为 105.3 / 97.7 秒，数量一致；扩大批量的本机实测反而 120.8 秒，因此按资源和每批吞吐谨慎探测。复杂 Content Delta 的逐条路径仍是后续优化重点 |
| 调度与资源 | 启动脚本按 Docker Engine 总额限制容器，保留至少 20% CPU、25% 内存；最终 API 取得自动生成的 Worker 预算，Worker 在单容器配额内按队列动态增减进程，Job 窗口由同一预算计算而不固定为 2 | 本机确认 3.59 CPU / 3,164 MiB→上限 2；容量单测覆盖 4.8 CPU / 12 GiB→3 和 9.6 CPU / 25 GiB→6。服务器实际吞吐、宿主其他负载和上限收益仍须在部署时复测，不能宣称绝对最优 |

本轮已在本地 Docker 独立空库完成四种配置的同文件对照。服务器尚未实际部署或运行：上线前须用相同方法分别记录预检、总墙钟、实际新增/更新/过滤行数、批次 p50/p95、Worker/数据库峰值内存、CPU、WAL、锁等待与宿主余量。更高配置服务器重新探索，不继承本机“最优”数值；动态上限只保证按有效资源计算并可由队列驱动，不保证线性提速。

# 目标、范围和不变项

- 采集运行中心在撤销中、撤销后正常分页、搜索、按状态筛选；阶段标签准确，已撤销来源不能错误补采。
- 全量重筛创建时排除撤销来源；已排队后撤销的来源在预检/处理时跳过并推进检查点，其他有效来源继续；每个入库批次与 Campaign 状态转换串行化。
- 保持公共 API 状态枚举、数据库 Schema、Job 类型与 Payload、导入/撤销业务写入语义、可逆贡献账本、用户 env 和依赖不变。启动脚本可生成内部 Compose Worker 预算，不修改用户 env。
- 不自动对用户本机现存失败重筛请求执行数据撤回；该请求已部分提交数据，已有请求级撤回入口可按账本处理。

# 修改方案

1. 统一运行列表将 `revoking` 映射为 `running`、`revoked` 映射为 `cancelled`，保留原始阶段供页面展示；同步状态统计与前端标签。
2. 全量重筛枚举过滤撤销中和已撤销的 Campaign；显式指定这类 Chunk 在创建时失败关闭。区分“合法来源后来撤销”与其他无效输入异常。
3. Worker 预检和逐件处理时跳过后来撤销的 Chunk，使用现有 Fenced checkpoint 推进；同一 Chunk 的批次事务在既有查询中共享锁 Campaign 行，撤销状态切换后拒绝继续写入；其他输入错误保持失败关闭。完成日志输出跳过件数，永久输入错误输出安全的阶段与异常类别。
4. 依据 Docker Engine 预算自动分配容器资源；API 使用生成的 Worker 预算冻结 Chunk / 投放窗口，Worker 在单容器总配额内按队列和有效资源增减进程，空闲或内存压力只结束没有在途 Job 的进程。Job 窗口由 Worker 可承受的进程数计算，不保留固定 2 的生产上限。
5. 将重筛撤回中已由后续写入接管的内容按批结清账本，保持逐内容当前版本和撤回统计；复杂 Delta 仍走精确逆向路径。为快照转换与重筛入库补充低频阶段日志；用真实 PostgreSQL、同一六个 XLSX、HTTP、Worker 覆盖完整链路与撤回，和原容量判断同条件对比。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 撤销中/已撤销 Campaign 列表、筛选、阶段与补采资格正确 | #601 / AC1 | satisfied | `test_revoked_campaign_keeps_runtime_list_queryable`，前端阶段标签测试 |
| R2 | 同数据提升预检、导入、重筛吞吐且撤销/撤回保持正确 | #601 / AC2 | satisfied | 独立 Docker A/B；最终手工 37.9 秒、服务器 39.1 秒、初次重筛 134.8 秒，普通撤销 22.8 秒；请求级重筛撤回的进一步 A/B 见运行证据 |
| R3 | 量化本轮耗时、瓶颈和跨服务器资源调整范围；为下一轮细分耗时取证 | #601 / AC3 | satisfied | 本文件“运行数据及结论边界”，本机日志、容量脚本和运行配置核对；文件快照与重筛完成事件新增聚合阶段指标 |
| R4 | 全量重筛跳过撤销来源，冻结后撤销仍继续有效来源 | #601 / AC5 | satisfied | 仓储分类测试、`test_queued_all_replay_skips_later_revoked_campaign_and_keeps_other_sources`、`test_replay_skips_remaining_rows_when_campaign_revocation_starts_between_batches` |
| R5 | Worker 数量与 Historical/Analysis Job 窗口随不同服务器资源自动调整 | #601 / AC6 | satisfied | Docker Engine 12 CPU / 15,822 MiB→Worker 上限 2、Job 窗口 2；容量单测覆盖 4.8 CPU / 12 GiB→3、9.6 CPU / 25 GiB→6；失败回调测试证明旧 Campaign 初始窗口 1 在新 Worker 容量下补投至 3；进程池日志显示按队列扩容和空闲降档 |
| R6 | 重筛撤回不逐条更新已由后续来源接管的账本，并对升档做实测取舍 | #601 / AC2 | satisfied | 101 条后续普通导入接管的 PostgreSQL 集成测试，撤回期间 SQL 总数小于 100；同六文件 Docker 撤回旧路径 122.7 秒、优化运行 105.3 / 97.7 秒；放宽本机探索上限后的反例为 120.8 秒，已拒绝该档位策略 |

# 交付要求

#601 / AC4 要求 Review、CI 后合并 main。这是变更 Ready 之后的交付门禁，不提前标为已完成；PR、CI、merge 和归档结果在实际发生后补证据。

# 验证矩阵

| 验证层 | 是否要求 | 实际证据 |
| --- | --- | --- |
| 公共接口和用户工作流 | required | HTTP 列表测试、撤销阶段前端标签测试 |
| PostgreSQL 与 Worker 集成 | required | 独立 PostgreSQL 18.4，106 项采集、重筛、历史导入相关测试，以及 8 项 Job Runtime 测试通过；最终镜像同六文件公开 HTTP 全链路与请求级撤回通过 |
| 静态检查 | required | Ruff check、Mypy 370 文件、架构/表 Owner/文档事实/Change Ready 检查、前端 typecheck 与 lint 通过；Ruff format 已针对变更文件执行 |
| 真正运行中的新版本 UI | required | 独立 Compose 的同源前端访问 `/api/v1/collection-runtime/runs` 在导入撤销、后续重筛与请求级撤回后均为 200；用户现有 Compose 不重建 |
| 外部 Provider | not_applicable | 本次读模型与历史文件重筛不调用付费 Provider |

# 风险、迁移、部署与回滚

- 新增 Campaign 行锁只发生在重筛处理 Data Import Chunk 时，复用原有每批来源查询；状态转换最多等待当前有界批次事务结束。没有增加导入和撤销写入查询，也没有增加外部请求。
- 本轮做了相同六个文件、相同 Docker Engine、隔离空库的多轮对照，但均为单次墙钟；导入数据全部被选择的 Brand 过滤，不能从这些数字外推大量 Content 新建、不同服务器或 p95。请求级撤回的复杂 Delta 仍逐条执行，批量优化只覆盖已被后续写入接管的安全分支。
- 没有 Schema/Migration、用户 env、Secret、依赖或公共 Contract 变动。重建 API/Worker/前端后生效；启动脚本每次重算 Compose 资源，Worker 运行中扩缩进程。回滚代码会重新暴露列表 409 和无效重筛选源，因此不应作为长期修复。
- 本机现存的第二轮全量重筛请求仍是 `active`，4 个子任务已经终态，至少两个子任务有写入；本 PR 不追溯改写该请求。用户若要撤回这轮重筛，应使用该请求现有的 `revoke` 操作，由贡献账本保护后续数据。

# 文档与依赖

- 定向同步 `backend/src/aima_ugc/modules/ingestion/README.md` 与 `docs/appendix/08_数据入口与统一入库实现.md`：撤销不会自动重筛、失效来源处理与现有请求级撤回边界。
- 同步 `docs/02_环境运行与部署.md`：Windows/Linux 同一启动与停止入口、Docker Engine 预算、自动进程池及 Job 窗口；Windows Docker Desktop 虚拟机上限先于应用生效。无依赖升级。

# 完成审计

- [x] upstream_re_read：重新核对用户本轮问题和“应跳过”决定、#601 验收内容、当前 Contract/Schema、代码及本机审计事件，独立重建列表与重筛来源的完成定义。
- [x] change_coverage：R1–R6 覆盖采集运行故障、全链路性能、自动 Worker/Job 窗口、请求级撤回以及排队/运行中撤销场景；AC4 作为后续交付门禁单列。
- [x] reverse_audit：从 Campaign 撤销 HTTP/Worker 到运行列表、重筛枚举和逐批写入反向核对；前端标签消费真实阶段，公共状态仍在既有枚举内；106 项 PostgreSQL 场景覆盖关键状态交叉。
- [x] unresolved_cleared：需求追溯没有 `not_satisfied`；服务器真实吞吐最优属于未验证性能结论，没有写成已满足的加速承诺。

# 两阶段 Review

1. 需求与机制复核：逐条比对 #601 AC1—AC6、公共运行状态、Campaign/Chunk/Job 账本和用户“失效来源跳过”的决定；确认撤销不会自动重筛，已提交的旧 Replay 贡献由请求级撤回结清。检查 `revoking/revoked` 映射、来源选择、Worker 复核、Campaign 共享锁和后续所有权保护，没有发现改变公共 Contract 或 Schema 的需求。
2. 实现与证据复核：检查完整 diff、同六文件 A/B、失败/排队/处理中撤销测试、提交批次幂等及 Job Fence。架构检查发现 EntryPoint 直接 SQL 后已改为 Job Repository，并补真实 PostgreSQL 查询测试；放宽本机撤回批量的实测反例已回退为资源约束。保留两项证据边界：本轮导入是全过滤分布；服务器未实际部署，不能宣称跨服务器绝对最优或峰值资源安全已实测。

# 完成证据与交付状态

- 独立临时 PostgreSQL 18.4 容器，迁移至当前 Alembic head；测试仅操作该库，未清理或更新用户运行中的 Compose 数据。
- `pytest`：采集运行、重筛仓储/Worker、历史导入四组相关集成测试 106 passed；Job Runtime 8 passed；容量/进程池/Compose 等单测 21 passed，另有失败回调定向单测 1 passed。
- `ruff check`：修改的 Python 源码与测试全部通过；`ruff format` 已格式化对应文件，需在提交后复查。
- `mypy backend/src`：370 文件无错误。前端 Vitest 定向 9 passed，typecheck、lint 与 production build 通过。
- 项目门禁：架构、表 Owner、文档、文档事实与 Change Ready 检查通过；架构检查曾识别进程池入口直接 SQL，已把查询移至 Job Repository 并用真实 PostgreSQL 测试验证。
- 将进程池查询移入 Job Repository 后重新构建并启动最终镜像，沿保留的隔离数据再次发起历史重筛：仅扫描仍有效来源的 168,792 行，68.774 秒成功结束，采集运行列表返回 200；随后已停止该隔离 Compose 项目。
- PR：#602；CI、Review、合并与归档在后续交付步骤记录。未执行生产部署或 Migration。
