---
schema: coding-change/v1
id: CHG-20260927-101400-replay-lowhit-throughput
title: 历史重筛入库与取消撤回性能及状态反馈
level: L3
status: done
owner: codex
branch: perf/624-replay-lowhit-throughput
created: 2026-09-27
updated: 2026-09-27
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - jobs
  - database
  - frontend
affected_paths:
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_reversal_worker.py
  - backend/src/aima_ugc/adapters/persistence/postgres/canonical_replay.py
  - backend/src/aima_ugc/bootstrap/canonical_replay_cancellation_worker.py
  - backend/src/aima_ugc/platform/jobs/registry.py
  - backend/src/aima_ugc/platform/jobs/worker.py
  - backend/src/aima_ugc/adapters/persistence/postgres/jobs.py
  - backend/src/aima_ugc/modules/ingestion/canonical_replay.py
  - backend/src/aima_ugc/bootstrap/worker.py
  - backend/src/aima_ugc/entrypoints/worker_main.py
  - frontend/src/features/import-batches/
  - frontend/e2e/collection-runtime.spec.ts
  - scripts/performance/benchmark_canonical_replay.py
  - tests/
  - docs/appendix/08_数据入口与统一入库实现.md
contracts:
  - ingestion.canonical-replay-cancellation.v1
data_changes: []
---

# 变更摘要

Issue #624 的合并后复测。用户明确要求同时解决：（1）历史重筛入库吞吐慢；（2）“取消并撤回”前端反馈不清楚；（3）取消请求和撤回执行耗时高。生产任务创建于 2026-09-27 00:05 北京时间，已运行约 10 小时、处理约 800 万原始行。服务器 Release manifest 对应 Git `1b25241d`、数据库为 `20260925_0065`，均早于 #625 合并及 `20260926_0067` 批量投影刷新优化；因此生产截图不是当前 main 的效果证据。不得在本任务中擅自部署或修改生产数据。

# 背景、现状与问题

完整生产日志（截至北京时间 10:21）中，44 个完成的 Replay Run 合计处理 7,334,260 raw 行；中位事务时间占 Run 墙钟 99.5%，Content 批量新建阶段累计 37.18 Worker 小时，中位占比 78.3%，Artifact 读取累计仅 0.14 Worker 小时。完成的 Run 共新建 887,576 条 Content，约 151 ms/条。实际瓶颈在数据库写事务内，而非读取 Canonical 文件。数据库约有 271 万条 Content、281 万条声音广场投影，后者死元组约 35.7 万，虽有最近 AutoVacuum，仍需限定归因；不能把所有成本都归于投影触发器。

同机隔离 PostgreSQL 18.4 的交替 A/B：对 20,000 raw、22.2% 均匀命中、命中内容中 44.1% Existing 的相同夹具，生产 Release `1b25241d` 三次 14.29 / 11.75 / 13.39 秒，当前 main `0bec01bb` 三次 10.74 / 8.63 / 8.44 秒；三组配对均更快。Release 的 Content 批量写阶段为 5.11 / 4.96 / 5.50 秒，main 为 1.99 / 1.82 / 1.66 秒。该小样本证明当前代码的方向性收益，但不能推断 270 万 Content 生产库上的绝对吞吐或提速比例。此前“命中集中在文件开头”的夹具得出相反的局部结果，说明夹具布局直接影响结论；本轮新增交错布局并保留两种场景。

当前代码在同机专用空库另做两轮初次导入/重筛新增对照：同为 20,000 raw、交错命中并实际新增 4,440 Content，初次导入 Worker 为 7.89 / 7.98 秒；重筛新增为 7.89 / 7.94 秒。初次导入和重筛阶段输入语义并不完全相同，故此处只确认当前小库的新增吞吐同量级，不外推生产大库。重筛处理 4,440 条全部 Existing 的两轮为 9.23 / 10.03 秒，包含可逆贡献与证据收敛。

撤回相同 4,440 条（2,480 New、1,960 Existing）的同机 A/B 两轮，生产 Release 为 4.77 / 5.08 秒，当前代码为 3.23 / 3.51 秒，均完成贡献账本对账，当前代码各快约三成。全部 New 的当前代码两轮撤回为 4.24 / 4.12 秒；全部 Existing 为 2.26 / 2.30 秒。撤回成本与内容类型有关，不应只用 raw 行数估算。生产任务后续的最终撤回总时长没有连续状态快照，暂不能给线上撤回吞吐结论。

真实 Excel Import 的混合负载两轮（100 raw、25 命中）在 Replay 前分别为 0.204 / 0.212 秒、Replay 并行时为 0.498 / 0.586 秒、Replay 后为 0.213 / 0.238 秒；并行时 Job 排队为 0.077 / 0.021 秒，对照约 0.007 秒。预留 Worker 保证可领取，但共享 PostgreSQL 写入使小导入执行约慢 2.4–2.8 倍。该样本只有一个 Replay Worker 与一个 Import Worker，不能证明六 Worker 生产混合负载的尾延迟；当前改动未调整 Host/Compose、正常链路预算或批量策略。

当前 main 的 matched-aware 控制器在交错样本中最终选择 125 matched rows，约 54 个批次，Release 约 22–31 批次；虽然 SQL 次数更多，main 的总时间和 Content 阶段仍更短。因此“事务碎片化导致总体回归”只在旧的聚集夹具上成立，不能作为这次生产 10 小时的根因。Release 缺少 `defer_voice_plaza_projection()`，旧迁移每次 Content/版本/贡献写语句都会同步触发投影刷新；该机制与 Content 阶段主导吻合，仍需生产新版本对照才能确认真实收益。

取消链路已由浏览器 Network 和数据库交叉验证：针对正确父请求的 POST 返回 Nginx 504 HTML；较早数据库快照父请求仍为 `active` 且没有取消审计，之后父请求于北京时间 10:40:50 进入 `reverting`，127 个子 Job 中 45 成功、82 取消，撤回 Job 已运行。这说明请求可能在网关超时后才提交，前端既不能把 504 当确定失败，也不能把尚未读到新状态当确定成功。当前服务在 HTTP 事务中先锁父行再逐个取消子 Job，存在长时间等待和与子 Job 终态回调相反的锁顺序；须用 PostgreSQL 并发测试证实并使请求短时受理。运行概览将 `reverting` 显示为泛化“运行中”，又把撤回 Job 的进度放在“总体进度”下、同时显示已结束的 Replay 子任务，造成阶段混淆。

本轮并发集成测试在另一个连接锁住子 Job 行时，旧版 API 超过一秒未提交；改为父意图及取消协调 Job 原子入队后，同一测试在一秒内通过。协调 Job 由预留 Worker 可领取，按 32 个子 Job 的短事务取消，锁忙时不阻塞预留 Worker、按统一 Job Runtime 重试；最后一个子 Job 终态仍通过现有完成屏障排队撤回。前端对 504/非结构化响应重新读取父状态；状态已变则确认受理，仍无变化则持续显示“结果暂未确认”，不伪报结果。

独立复核发现通用 Job 失败重试采用指数退避，原设 720 次重试可能使取消协调在后期长时间停滞。现仅对该 Job 设置 5 秒退避上限，通用 Job 默认退避不变；一次协调执行的数据库锁等待上限为 3 秒，Attempt 超时会显式标记失败并允许重试。单 Worker 时运行中的 Replay Run 每秒最多读取一次父取消意图，在预检和每个提交批次之间协作退出。PostgreSQL 测试分别证明封顶及默认退避、父请求重复点击幂等、单 Worker 退出。

最终代码另跑一轮 20,000 raw / 4,440 matched / 1,960 Existing 的交错样本：Replay 10.15 秒、撤回 3.67 秒；100 raw Excel Import 在 Replay 前 / 并行 / 后分别为 0.210 / 0.473 / 0.214 秒，排队分别为 0.007 / 0.067 / 0.008 秒。方向与前两轮相同；共享数据库写入下执行时间仍约增加 2.3 倍。这不支持“所有慢都是机器硬上限”，也不支持在缺少当前版本生产对照时继续盲目改变批量或全局资源预算。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 旧生产 Replay 的主要墙钟在数据库写事务内，Content 批量新建阶段主导 | 用户提供的 28 份日志，44 个完成 Run 的阶段统计 | 入库排障聚焦数据库事务，不把读取 Canonical 误判为主因 |
| E2 | 生产运行的是早于 #625 的 Release 和 Migration 0065 | 用户提供的 Release manifest 路径、服务器只读 `alembic_version` 与任务创建时间 | 旧生产截图不能证明当前 main 的吞吐 |
| E3 | 相同 20,000 raw 交错夹具三组旧/当前 A/B 均是当前代码更快 | 同机隔离 PostgreSQL 18.4 的 `benchmark_canonical_replay.py` 报告 | 当前已有有方向性的代码改进；仍不外推生产库 |
| E4 | 旧取消请求受锁可超时；浏览器 POST 504 后父请求最终进入撤回 | PostgreSQL 行锁并发红绿测试、用户 Network 截图和只读状态快照 | HTTP 只持久化意图，未知响应以父状态核对 |
| E5 | 通用 Job retry 使用指数退避 | `adapters/persistence/postgres/jobs.py::retry_transient` 与 PostgreSQL 回归 | 取消协调需要单类型 5 秒上限，其他类型保持默认 |
| E6 | 当前撤回 A/B 更快，真实 Import 在 Replay 并行时执行变慢但仍可领取 | 两轮旧/当前撤回基准与三轮 Excel mixed load | 保留资源保护并公开共享数据库争用，不盲目扩大全局预算 |

## 推断与待确认

旧 Release 缺少投影延期刷新与生产 Content 写阶段主导吻合，但不能据此断言它是线上全部耗时的唯一原因；新代码部署后大库吞吐、六 Worker mixed load 尾延迟及旧任务最终撤回总时长仍缺可比实测。本 PR 不部署，以上缺口不作为已验证收益。

# 目标、成功标准与非目标

- 把生产日志、初次入库和 Replay 阶段耗时、旧版/当前版同机对照归一到相同输入/实际写入量；只优化有可复现收益的代码瓶颈。
- 取消请求在运行 Job 行锁受阻时仍能快速、持久受理；子任务最终取消/终止后撤回自动启动，重试与重复点击幂等。
- 前端明确展示“取消中 / 撤回中 / 已撤回”和对应阶段进度；网关超时后通过真实状态确认，不误报成功或失败。
- 对撤回本身做同机基准和生产吞吐核验；若继续优化投入产出比低，以数据说明。
- 保持 Replay 数据正确性、Fencing/checkpoint/接管/精确撤回、资源压力降档、非 Replay Worker reserve 与 Host/Compose 预算。

非目标：提高全局 CPU/内存配额，删除低命中 shard gate，升级依赖或框架，生产部署或生产数据操作。

兼容与回滚：公共 HTTP/Canonical/数据库 Schema 不变；新增内部持久 Job Payload `ingestion.canonical-replay-cancellation.v1`。旧 Worker 不认识该类型，故不能在取消协调 Job 仍 queued/running、父请求仍 cancelling 时直接回滚 Worker；须让新 Worker 完成协调，确认父请求已进入撤回或撤回终态后，再按 Release 流程回滚。若协调持续失败，先保留新 Worker 并以修复版本前滚，不用生产手工 SQL 冒充正常撤回。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与 Owner | 只改 Replay/API、Job Runtime 必要的按类型重试上限和运行中心反馈 | E1、E4、E5；#624 / AC11–AC13 | 继续由 Job Owner 写 jobs，Replay Repository 写父请求，前端只读 API |
| 接口与契约 | 公共 HTTP 不变；新增版本化内部取消 Job Payload | E4；现有持久 Job Runtime | 无生成 Client 变化，旧 Worker 回滚受新 Job 类型约束 |
| 数据与迁移 | 不改 Schema、不迁移生产数据 | 当前父请求和 jobs 表已具备所需列 | 仅应用代码部署；本轮不执行部署 |
| 失败语义 | 504 属结果未知，协调失败可见且重试；锁忙短事务重试 | E4、E5 | 不伪报成功/失败，保持幂等与 Fencing |
| 资源 | 保持 Host/Compose 预算与正常 Job 配额 | E6；#624 / AC1–AC3 | 导入有 Worker 可领取，DB 争用仍需线上观测 |

# 修改方案与决策依据

取消 API 先提交父意图和唯一协调 Job，协调 Job 分批通过现有 Job Owner 通知子任务、跳过锁忙行并按 5 秒上限重试；最终屏障沿用现有撤回 Job。只有一个 Worker 时，单路 Replay 在提交边界读取父取消意图。前端以持久父状态解释 504 和阶段进度。入库路径保留 #625 已合并的投影与批次优化，本轮用同机对照判断继续改写数据库热路径的收益。

## 备选方案与取舍

- 继续在 HTTP 事务中逐个取消 127 个子 Job：行锁复现实测会超过一秒，且可能碰到反向锁顺序，故不采用。
- 提高 Worker/PostgreSQL 全局配额或扩大 Replay 固定批次：真实 Import mixed load 已显示共享 DB 争用，生产当前代码尚无大库对照，故不采用。
- 为取消引入第二套线程/队列：现有持久 Job Runtime 已提供重试、Lease、Fencing 和审计；复用现有机制更便于恢复。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 系统排查入库吞吐，给出初次入库及旧/当前代码可重复证据，只优化可证明有收益的瓶颈 | #624 / AC11 | satisfied | 生产 44 Run 日志；三组旧/当前 A/B；两轮初次入库与重筛 New/Existing 对照；最终代码复测 10.15 秒；生产新版本尚未部署，线上收益不作断言 |
| R2 | “取消并撤回”的前端状态、进度、超时反馈与数据库事实一致 | #624 / AC12 | satisfied | 前端 31 项定向测试、目标浏览器场景 1 passed、类型检查、ESLint 与构建；504 未知结果、快速失败状态确认、既有失败重试及无 Run 的正确入口 |
| R3 | 取消请求在重负载及锁等待时短时持久受理，子任务取消与撤回自动幂等收敛 | #624 / AC13 | satisfied | 旧实现锁等待红测；新实现锁冲突、幂等、协调重试、最终失败后重试、自动排队撤回、单 Worker 协作退出、5 秒退避封顶 PostgreSQL 测试；线上新版本尚待部署 |
| R4 | 撤回执行吞吐有同机证据，剩余优化按收益判断 | #624 / AC13 | satisfied | 两轮 Release/当前同机撤回 A/B、New/Existing 单独对照；最终代码撤回 3.67 秒；服务器旧版最终耗时未取得，不外推大库 |
| R5 | Host/Compose 总资源预算不变 | #624 / AC1 | satisfied | 本分支无 Host/Compose 资源分配文件 diff；Worker 现有容量测试保留，未提高全局配额 |
| R6 | 多 Worker 时为非 Replay 留领取槽，单 Worker 仍执行 Replay | #624 / AC2 | satisfied | Worker reserve 单元测试及单 Worker 父取消 PostgreSQL 回归通过；取消协调被前台预留 Worker 允许领取 |
| R7 | Collection/Import/Historical Import/Analysis/Export 原有资源和业务边界不下降 | #624 / AC3 | satisfied | 未改各链路优先级、并发/批量和公共 HTTP Contract；真实 Excel Import mixed load 在 Replay 期间仍被领取，但 DB 执行慢约 2.3 倍，风险明确记录 |
| R8 | Replay Shard 与 Import Reversal 优先级保持已验收语义 | #624 / AC4 | satisfied | 本分支未改 Replay Shard/Import Reversal 优先级，Job 注册与 reserve 回归通过 |
| R9 | 低命中 scan window、matched 事务和资源上限保持受控 | #624 / AC5 | satisfied | 5%/25%/高命中控制器及性能工具单元回归；最终交错 22.2% 命中基准记录扫描与批次 |
| R10 | Existing Evidence 和 before/after ledger 保持可逆正确性 | #624 / AC6 | satisfied | 本分支未改 Evidence 写路径；Replay/撤回 PostgreSQL 集成及最终账本对照通过 |
| R11 | 排障日志不泄露正文、Secret、敏感 Raw | #624 / AC7 | satisfied | 新日志无正文/Secret 字段；沿用既有 Job/Replay 生命周期和批次事件，代码审查未见敏感值输出 |
| R12 | 容量基准覆盖 New/Existing 与 mixed load，正常 Import 保持可领取 | #624 / AC8 | satisfied | 旧/当前交错与聚集样本、New/Existing/初次导入及真实 Excel Import 前/并行/后两轮加最终一轮；DB 争用实测已记录 |
| R13 | Review、current-head required CI | #624 / AC9 | explicitly_deferred | 项目 AGENTS.md 规定 Ready 后触发 PR CI；本地分层验证与 Review 先完成，CI 仍为合并硬门禁，归档时补填实际 run/HEAD |
| R14 | 合并后 main-fresh、Change Archive、Issue Closure 和分支清理 | #624 / AC10 | explicitly_deferred | 项目 AGENTS.md 规定 PR 合并后执行归档和 main-fresh；本项按交付顺序执行，不能在 Ready 前伪称已完成 |

# 计划改动

1. 完成初次入库与 Replay 的可比口径及撤回 A/B；结合生产表规模和状态判断当前代码已修复多少、剩余瓶颈是否值得改。
2. 在 PostgreSQL 并发测试中复现取消 HTTP 被运行 Job 行锁拖过网关 timeout；将父取消意图短事务持久化，子 Job 的协作取消由现有持久 Job Runtime 异步执行。
3. 前端区分 Replay 入库与撤回阶段，网关超时后只提示状态待确认并继续轮询；状态确认后再显示真实结果。
4. 重跑取消/撤回正确性、性能、资源保护及其他数据链路回归；同步文档、Completion Audit、Review、CI 与交付。

# 验证矩阵

| 维度 | 状态 | 计划 |
| --- | --- | --- |
| 单元 / 控制器 | required | 低命中布局、前端状态与超时响应、取消 Job 幂等/重试 |
| PostgreSQL 集成 | required | 运行 Job 行锁并发、取消后所有子 Job 终态、撤回账本与 Fencing |
| 性能 / 混合负载 | required | 同机交替旧/当前入库和撤回 A/B；初次入库、New/Existing 与正常 Import 对照 |
| 静态 / 文档 | required | Ruff、mypy、前端类型检查、Change 检查、目标排障文档 |
| 生产实测 | limited | 已取得旧版生产日志、DB 版本/锁/状态/规模；新代码尚未部署，线上收益不得宣称已验证 |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 取消协调在锁竞争下延迟；正常 Import 在 Replay 并行时变慢 | E4、E6；锁等待最多 3 秒、按类型退避封顶 5 秒；mixed load 明示争用 |
| 兼容性 | 公共 HTTP/Schema 不变，内部持久 Job 类型新增 | Contract 生成检查通过；旧 Worker 不认识取消协调类型 |
| 数据 / Migration | 无 Schema Migration 或数据回填 | 使用现有父意图、Job 与贡献账本 |
| 部署 / 运行 | 沿既有 API/Worker/PostgreSQL 拓扑发布；本 PR 不部署 | 用户授权范围与项目 Release 门禁 |
| 回滚 / 恢复 | 不直接回滚仍有取消协调任务的 Worker；先结清或前滚修复 | 新 Job 类型回滚兼容约束；只读检查已写入长期文档 |

# 文档、依赖、部署与发布影响

- 长期文档：同步 `AGENTS.md` 的 Worker 注册导航和 `docs/appendix/08_数据入口与统一入库实现.md` 的取消、状态、回滚检查。
- 依赖 / Runtime：无新增依赖或版本升级；`uv.lock`、前端 lock 文件均不变。
- 配置 / Secret：无新增配置或 Secret，基准数据只在未跟踪本地临时目录，未提交。
- 部署 / Release：无生产 Migration；未来部署按既有 Release 流程，并在回滚前执行新 Job/父状态只读检查。本任务不部署。
- 消费方：生成 OpenAPI/Client 无变化；运行中心状态反馈属于已有响应字段的新展示。

# 完成审计

- [x] upstream_re_read：重读用户三个问题、Issue #624 的 AC1–AC13、项目 AGENTS.md 和当前 Replay/API/Job/前端代码；旧生产 Release 与当前 main 分开判断。
- [x] change_coverage：R1–R14 分别映射入库证据、前端反馈、取消与撤回、资源/其他链路、CI 与交付；本地 PostgreSQL、前端、静态、Contract 和同机基准均有实际结果；CI/合并按正式顺序仍须执行。
- [x] reverse_audit：检查前端动作到 API、父状态到取消协调 Job、子 Job 终态到撤回、单 Worker 和预留 Worker、真实 Import mixed load；没有修改 Host/Compose 与其他链路预算，DB 写竞争仍作为实测限制公开。
- [x] unresolved_cleared：独立复核发现的指数退避无上限、单 Worker 取消、取消失败重试、前端旧失败误判及新 Job 回滚限制均已修复或记录；定向回归、Ruff、mypy、前端类型/ESLint/构建、Contract 检查已通过；生产新版本吞吐须部署后核验，不作为当前 PR 已验证结论。

# 完成证据与状态

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 本分支 `6f5920c0`，本地 PostgreSQL 18.4 | Job/Replay/API 组合 pytest；取消边界和失败重试复测 | 组合 97 passed、一个断言因新增提交前检查需调整；调整后的两项取消边界及失败重试均通过 | 真实 PostgreSQL 的受理、取消、撤回屏障与恢复行为 |
| V2 | 本分支，前端本地 | Vitest 定向 31 项、目标 Playwright 场景 1 项、typecheck、ESLint、Vite build | 全部成功 | 504、阶段状态、失败重试入口、浏览器详情与前端产物 |
| V3 | 本分支，同机隔离 PostgreSQL 18.4 | 旧/当前交错 A/B、初次导入与 New/Existing、撤回 A/B、Excel mixed load | 实测数值见 E3/E6 和上文 | 性能判断与共享 DB 争用的适用范围 |
| V4 | 本分支 | Ruff check/format、mypy、Contract generate --check、Change Ready Check | 全部成功 | 静态、公共生成事实和本地就绪 |

未验证：新代码尚未在 270 万 Content 的生产库部署；无法声称线上吞吐或最终撤回速度已改善。交付状态：PR #629 Ready；current-head required CI、merge、main-fresh、机器 Change Archive 与 Issue Closure 仍按正式顺序完成；本任务不部署。
