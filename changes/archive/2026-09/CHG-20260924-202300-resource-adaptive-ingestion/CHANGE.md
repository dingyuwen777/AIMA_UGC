---
schema: coding-change/v1
id: CHG-20260924-202300-resource-adaptive-ingestion
title: 导入、重筛与撤回的资源感知运行调节
level: L3
status: done
owner: yuwen.ding
branch: fix/598-code-owned-runtime-sizing
created: 2026-09-24T20:23:00+08:00
updated: 2026-09-24
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - analysis
  - jobs
  - deployment
  - frontend
affected_paths:
  - backend/src/aima_ugc/
  - scripts/deploy/
  - compose.yaml
  - frontend/src/features/import-batches/
  - migrations/versions/
  - tests/
  - docs/
contracts:
  - historical-import-profile.v1
  - data-import-profile.v2
  - DataImportRevocationResponse
data_changes:
  - historical_import_revocation_requests
  - ix_content_source_contributions_attempt_content
---

# 变更摘要

使不同宿主机上的 Compose 部署和后端运行读取有效资源与阶段反馈，在有界范围内选择参数；不要求逐机维护五项性能 env。普通导入撤销改为持久分批 Job，响应和页面显式区分受理与完成。保持已冻结 Chunk、逐行账本、重试及撤销语义。

# 背景、现状与问题

Issue #598 和本轮用户决定要求从入口、预检、入库、重筛到撤销全链路调节。现有五项值在 Settings、env 模板和 Compose 中存在不一致：代码 Chunk 默认 2000，Compose 回退 1000，本机 env.local 为 1000。现有 Compose 一个串行 Worker；Job in-flight 窗口只限制队列积压，不等于物理并发。Analysis 的 LLM 并发由冻结 Provider Snapshot 控制。扫描文件数和目录深度是安全边界，不应随硬件放宽。

# 事实与证据

已确认事实来自 Issue #598、本轮合成基准、当前 Settings/Compose、隔离 PostgreSQL 与真实 Full-stack 检查；高配生产服务器的实际吞吐和资源干扰仍待现场验证。

2026-09-24 的隔离 PostgreSQL 合成数据试验：12,000 行、单 Worker，同口径 Chunk 1000/2000/4000/8000 的预检+导入分别为 25.00/22.05/22.33/41.58 秒，进程峰值内存为 162/181/220/298 MiB；因此生产初始 Chunk 不提高到 4000/8000。普通导入撤销同步基线 8.359 秒；分批 Job 以 500/1000/2000/4000 为候选的请求+后台完成实测约 9.14/9.14/8.92/9.02 秒，其中请求约 0.25 秒。逐级探测策略约 9.16 秒，自动拒绝本机无收益的 1000 档；最新等差版 12,000 行的预检、导入、撤销请求与后台完成分别为 1.62/20.89/0.26/9.10 秒。另用 1,200 条含证据变化的重筛撤回数据对照固定 100/500 条批量：完成耗时 1.52/1.31 秒、SQL 220/67 次，500 条最慢单批约 0.54 秒；因此两种撤销统一从 500 条起步、每次加 500 条。异步重试与批次提交增加少量总耗时，不能把请求响应变快表述成后台吞吐提升。报告在本机 `.runtime/dev/bench-598-*/capacity_report.json`，不提交含运行 ID 的报告；高配服务器仍需独立实测。

额外核对撤销账本的读取计划发现：旧查询在 12,000 条、单批 500 Content 时会把剩余完整 JSON Delta 排序，首批约 20 MiB 落盘；先限量选择 Content UUID 再读取完整 Delta 后，同一隔离库首批 EXPLAIN ANALYZE 从约 23.5 ms 降到 8.0 ms，中途从约 11.8 ms 降到 5.9 ms。重复完整读取全部 12,000 条账本为旧路径 0.76–0.83 秒、新路径约 0.69 秒；断点和同一 Content 多 Delta 的完整性由集成测试覆盖。另一轮全流程复测受本机负载波动影响，未证实撤销总耗时提升，不将查询局部收益外推为整体吞吐或千万级最优性能。

# 目标、成功标准与非目标

目标：部署时读取 Docker Engine 的有效资源；运行时根据容器配额、阶段耗时、错误和压力调整安全可变的参数；对预检、入库、重筛和撤销实施观测、正确性与回退验证。范围为后端、Compose 启停入口、普通导入撤销的 API/页面状态、Migration、测试、基准与文档。外部 Provider 调用和生产数据不在范围。页面仅修正异步状态，不扩展等待体验。

成功标准以 Issue #598 的 AC1–AC8 和下方逐条需求追溯为准：无需逐机维护五项性能 env、资源不足时保守运行或拒绝启动、已冻结账本可恢复、两种撤销本次执行中等差调节、页面显示真实状态，并用隔离数据库和正式 CI 验证。Chunk 变大或 Job 窗口升高本身不是成功标准。

# 约束与意图决策

- 不在 env 模板或 Compose 中公开这五项人工性能配置；目录扫描护栏保持代码固定、失败关闭。
- 已发布 Chunk 的行边界不在线重切；冻结的分析 Provider 并发/RPS 不因 Job 窗口调节而被绕过。
- 不用 Docker socket 挂载给业务容器；Compose 配额与 Worker 副本数由宿主机部署入口决定。运行中的调节只作用于业务可安全变更的调度和 SQL 批次。
- 硬件读取失败、反馈不足、数据库/内存压力上升时保守降档；性能结论必须同时看全流程、撤销、重试、账本与数据对账。
- 普通导入撤销和重筛撤回都从 500 条运行，每次只向上尝试 500 条；容器有效 CPU 和剩余内存决定当批可探索上限，重筛撤回因逐条账本与证据操作采用更保守的资源预算。只有相邻档位测得至少 20% 的单行耗时下降才升档。单批事务超过 3 秒、内存压力或数据库重试触发降档。普通撤销在 16 核/64 GiB 宿主经 Compose 分配后的 Worker 配额约可探索到 8000，32 核/128 GiB 约可探索到 16000，但这只是资源护栏，实际吞吐不足时不会升到这些档位；极高配机器仍受 65500 条单批安全上限约束。业务撤销事实表的不可变触发器保持原样，独立请求状态表保存 Job、断点和进度。

# 修改方案与决策依据

按启动、运行、撤销顺序实施：宿主脚本从 Docker Engine 读取资源并生成可审查的 Compose override；运行时代码读取容器配额与压力，在冻结边界外调节 Job/SQL；撤销以不可变事实、可变请求状态、持久 Job 和同事务断点处理。账本分页先选本批 Content UUID，再读取完整 Delta，避免反复排序剩余 JSON。每项决定均由上述代码边界和基准证据支持，范围与直接验证对应下方 R1–R9、计划改动和验证矩阵。

## 备选方案与取舍

- 固定把 Chunk 从 2000 提到 4000/8000：本机同口径全流程并未稳定变快，8000 明显变慢，且已发布 Chunk 不能重切，因此保留经测量的 2000 初始粒度。
- 只把 Job 窗口或 Worker 副本数拉满：当前 Compose 单 Worker 串行，窗口不是物理并发，更多副本可能增加数据库争用；先按资源调背压和批量，并保留独立单/双 Worker 正确性验证。
- 撤销无限增加批量：长事务使锁、恢复与尾部延迟失控；采用 500 等差探索、资源护栏、吞吐门槛和 3 秒事务门槛。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 五项性能 env 不再逐机配置，由代码决定 | #598 / AC1 | satisfied | Settings/Compose/env 模板及配置单测；旧 env 值不覆盖代码选择 |
| R2 | 不同 Docker 配额下自动选择有意义的运行参数与反馈规则 | #598 / AC2 | satisfied | Docker Engine 资源计划、cgroup 探测、Job/SQL 调节和容量单测；未知资源保守运行 |
| R3 | 普通导入撤销和重筛撤回统一在本次运行内等差升降档 | #598 / AC6 | satisfied | 两种撤销 500 起步、+500，资源/事务护栏单测 10 个；4,000 条重筛撤回日志证实 500→1000 |
| R4 | 已发布 Chunk 的冻结、幂等和逐行账本保持稳定 | #598 / AC3 | satisfied | Campaign profile 选择/重试单测与隔离 PostgreSQL ingestion 集成 69 个通过；未在线重切 |
| R5 | 调节日志和可复现全链路基准准确区分请求与后台耗时 | #598 / AC8 | satisfied | capacity.* 日志；12,000 行导入/撤销、1,200/4,000 行重筛撤回报告及账本对账；分页读取 EXPLAIN 与完整读取微基准；高配机器未实测 |
| R6 | 普通撤销短请求、可恢复 Job 和页面状态准确；重筛撤回共享调节机制 | #598 / AC6 | satisfied | Job/断点/Contract/页面已实现，前端 228 单测与真实数据库 30 相关集成通过；真实 Full-stack run 36012858186 通过 |
| R7 | 跨平台启停只依赖外部稳定 env，资源不足拒绝启动 | #598 / AC7 | satisfied | start/stop 脚本、Windows overlay 和 Release 打包，资源计划/外部 env 单测通过 |
| R8 | Job 窗口不冒充物理 Worker/LLM 并发，保持安全扫描护栏 | #598 / AC4 | satisfied | Compose 仍为单 Worker；Analysis Provider Snapshot 不变；Discover 文件/深度限额固定且失败关闭 |
| R9 | 单/双 Worker、低资源、取消/重试、Full-stack 两 Chunk 与性能对账 | #598 / AC5 | satisfied | 隔离库 ingestion 69 个、容量/低资源单测和实测报告；真实 Full-stack run 36012858186 通过；PR 必需 CI 仍是合并门禁 |

# 计划改动

1. 记录全链路已有阶段指标与缺口，保留 2000 Chunk 基线及扫描安全护栏；用相同数据和隔离库筛选候选，不以单次小差距宣布最优。
2. 增加标准库资源探测与有界调节器；Campaign 创建冻结安全选择，运行中的可变批次与 Job 窗口按资源和反馈调整，并记录调整原因。
3. 增加宿主机 Compose 启动入口，在启动前生成可审查的资源 override，不把 Docker 控制权放入业务容器。
4. 对手工/服务器导入、重筛与撤销执行低资源、恢复、重试、取消、并发及账本对账；核对本机和 Compose 解析结果。
5. 同步文档、两阶段 Review、CI 和完成审计；通过后按仓库保护规则合并并清理本地分支。

# 验证矩阵

| 层级 | 需要 | 本轮证据 |
| --- | --- | --- |
| Unit / 静态 | required | 容量与脚本单测 33 个通过，相关回归 42 个通过；Ruff/Mypy 通过；完整后端 Unit/API 在 Windows 有 9 个既有 POSIX/路径测试不适用问题，相关新增失败已修复，Linux CI 待确认 |
| Contract / API | required | OpenAPI 生成与兼容检查通过；API 单测主体已运行，前端 generated client 与 TypeScript typecheck 通过 |
| PostgreSQL / Job | required | 专用隔离库 Migration 至 0063、Alembic check 无差异；ingestion 集成 69 个、撤销与重筛相关 30 个通过，覆盖双 Worker/取消/断点恢复；分页读取改动后普通撤销集成 4 个通过 |
| 用户 / 浏览器 | required | 前端 228 个单测、lint/typecheck 通过；独立真实 Full-stack run 36012858186 通过，PR CI 待运行 |
| 部署 / Runtime | required | 跨平台脚本单测与 Release Bundle 测试通过；实际 Docker Compose 和 Windows/Linux 机器部署等待 CI/目标服务器验证 |
| 性能 / 观测 | required | 12,000 行导入/撤销及 1,200/4,000 行重筛撤回隔离库报告；日志可见档位调整与结果，不外推高配服务器 |
| 外部 Provider | not_applicable | 不改 TikHub/LLM 调用、额度和模型快照；无需付费探测 |
| Docs / 迁移 | required | Blueprint、Appendix、Operations、环境文档及生成 Contract 已同步；docs facts 通过，Migration 升级与 Schema 对账通过 |

# 风险、兼容性、迁移与回滚

| 项目 | 当前结论与处理 |
| --- | --- |
| 性能风险 | 本机只证明撤销请求响应与局部读取改善，后台总耗时未证实下降；高配生产需现场容量验收，日志记录档位和阶段耗时以便回退判断。 |
| 兼容性 | 已冻结 Campaign Chunk/Provider Snapshot 不重切；普通撤销 API 增加 queued/running/failed 状态并同步生成 Client 与页面，现有已撤销事实仍可读取。 |
| 数据与 Migration | 0062 增加撤销请求/断点表，0063 并发建立 Attempt-Content 索引；已有持久撤销请求后不允许直接降级 0062，需协调备份恢复。 |
| 部署与回滚 | 服务器沿用 Release 外部 env；启停脚本生成 override。回退镜像前核对 Migration 与已创建撤销请求，不能只替换代码来回退新状态机。 |

# 文档、依赖、部署与发布影响

- 长期文档：已同步环境运行、数据入口、Blueprint 与 Operations 中的资源选择、异步撤销和部署入口。
- 依赖与 Runtime：未升级 Python、PostgreSQL、前端或后端依赖；保留单 Worker 基线及现有模块化单体。
- 配置与 Secret：五项人工容量 env 从模板移除，外部长期 env 保留身份与 Secret 配置；生成的 override 不含 env 内容。
- 部署与发布：需先运行 Migration 0062/0063，再用脚本启动；正式离线 Bundle 包含脚本和 Windows overlay，仍由 Release/Runtime CI 验证。
- 消费方：普通撤销公共响应与页面状态一并变更；生成 OpenAPI/TypeScript Client 已同步。

# 完成审计

- [x] upstream_re_read：已重新读取 Issue #598 的 AC1–AC8、用户追加决定、项目 Blueprint/Operations 与实际 API/Worker/Compose 调用链。
- [x] change_coverage：AC1–AC8 已映射到实现、Contract、文档和分层测试；高配机器性能明确标为待现场验证，不宣称绝对最优。
- [x] reverse_audit：已从导入入口、Campaign/Chunk、SQL/Job、两种撤销、API/页面状态反查所有新增能力及旧路径；单/双 Worker 与取消/重试集成覆盖已运行。
- [x] unresolved_cleared：要求的实现、Contract、隔离库、真实 Full-stack 与文档证据已核对；PR 必需 CI、Release/Runtime Workflow 和最终 Review 仍为合并门禁，尚未声称可合并。高配生产服务器性能留待现场容量验收。

# 完成证据与状态

- 实现提交 `e373ead3`：容量/脚本单测、隔离 PostgreSQL 集成、前端单测、Ruff/Mypy、文档与本地 Ready Check 已通过；本轮新增的 Change 文档提交另由 canonical Change 校验验证。真实 Full-stack 两 Chunk 的独立运行是 36012858186。
- PR #599 已进入 Ready；2026-09-24 首轮必需 CI 的 Requirement Source 检查指出本 Change 缺少 canonical 标题，本次补齐后需以新提交重新验证。Runtime/Release 与最终 Review 仍待最新提交完成。
- 已知界限：另一轮全流程复测本机负载波动较大，不能据此声明普通撤销后台已提速；高配服务器和实际用户文件尚未做现场容量验收。
