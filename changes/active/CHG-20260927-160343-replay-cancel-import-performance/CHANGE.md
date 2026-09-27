---
schema: coding-change/v1
id: CHG-20260927-160343-replay-cancel-import-performance
title: 历史重筛、取消撤回与数据导入性能修复
level: L3
status: in_progress
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

Issue #630 统一处理三个生产问题：全历史重筛约每分钟处理一万原始行；“取消并撤回”确认后按钮短暂置灰又恢复，未稳定进入撤回完成态；数据导入在重筛并发时明显变慢。验收还覆盖两种等价业务顺序：先录入品牌/车型再导入，或先导入再补目录并重筛。两条路径的最终业务事实必须一致；每一遍实际处理的吞吐不得因目录创建顺序或目录规模发生数量级下降。后者客观多执行一次初始过滤、一次 Replay 和可撤回账本写入，因此比较逐遍吞吐和额外工作，不伪造相同总墙钟。

# 目标与成功标准

- 服务器应用日志能以 HTTP request ID、Replay 父请求 ID 和 Job ID 追踪取消请求的接收、数据库阶段、事务提交、协调取消和撤回终态；失败记录安全的阶段与错误分类，不记录正文、Raw 或凭据。
- 修复取消请求未稳定持久化或前端刷新后恢复为可再次取消的真实原因；重复操作保持幂等。
- 分离测量 Replay 扫描、匹配、Content 写入、Evidence 写入、投影刷新、等待锁与事务提交，取得同机 PostgreSQL 的隔离及 mixed-load 证据。
- 修复已证实的 Replay 与数据导入瓶颈；历史目录与本地电脑的统一 Data Import 使用同一写入链路和相同批量时，吞吐应处于可解释的同一量级。
- 覆盖导入、Replay、取消协调和撤回的串行与并行组合；并行时前台导入和取消不得被已运行的后台 Replay 长事务长期占用数据库或全部 Worker。
- 在 16 核、64 GB 服务器容量边界下验证 Worker 数、批量和并行窗口由有效 CPU、内存及实测吞吐自适应；不得把当前开发机的固定参数写死到生产。
- 所有相关数据处理操作都可在同一全局预算内增长；隔离吞吐必须比修复前提高、同类完整输入的处理时间必须缩短，同时为 API、查询、取消协调和多用户访问保留容量。
- 若剩余瓶颈属于机器资源饱和，提供 CPU、I/O、锁等待或数据库吞吐证据及投入产出边界。
- 保持公共 HTTP、数据库 Schema、贡献账本、Fencing、Checkpoint、精确撤回和其他数据链路的业务语义。
- 先建目录后导入与先导入后建目录并 Replay 必须得到相同 Content、Evidence 和来源贡献；目录已有数千别名时两条路径的单遍吞吐仍处于可解释的同一量级。

非目标：升级依赖、取消全局资源预算、让单个任务独占机器、绕过统一 Job Runtime、部署或修改生产数据。

# 已确认事实、推断与未知项

## 已确认事实

- 用户复现中，二次确认后按钮会置灰，随后恢复为“取消并撤回”；这证明前端进入了异步提交状态，但不能单独证明后端是否提交。
- 本次日志窗口中，两个 2,000 行导入批次总耗时约 69–94 秒；Evidence 阶段约 57–64 秒，是已观测的主要耗时阶段。
- 同一日志窗口有五个 Replay Worker 与一个前台预留 Worker并发使用 PostgreSQL；导入能被领取，但执行吞吐可能受共享数据库写竞争影响。
- 当前前端在 5xx、非 JSON 或网络异常后刷新父状态；若父状态仍未变化，按钮会恢复可操作并提示结果未确认。
- 服务器日志确认 Worker 容器有效资源为 9.6 CPU / 12.5 GiB，进程池已扩到 6 个进程；生产慢并非只由“Worker 没扩容”解释。
- 服务器 Replay 样本把数据库目标批量从 125 降到 62，约 150–200 个原始行的批次仍需 3–10 秒；同一时段没有持续 PostgreSQL 阻塞者。
- 修复前本地同库 10,100 行 / 2,100 个目录别名的 Replay 为 96.983 秒、104.72 行/秒，其中 Resolver 66.559 秒；稳定目录身份复用编译匹配器后为 30.748 秒、334.26 行/秒，其中 Resolver 0.761 秒。
- 真正业务顺序对照中，“目标别名已存在后首次导入”处理 10,100 行为 251.37 行/秒；“首次过滤后补目标别名再 Replay 入库”为 243.15 行/秒，单遍差异约 3.3%，最终均为 10,100 条 Content。
- 原 Replay 不能跨 Canonical Artifact 聚合，小文件实际形成逐文件事务。跨 Artifact 聚合后，同一 10,100 行 / 2,100 别名场景从 243.15 提升到 377.80 行/秒，SQL 从 6,575 降到 4,249，账本 INSERT 从 101 次降到 20 次。
- 本机自适应控制器实测 500 行事务约 0.8–1.0 秒，1,000 行事务约 1.77–1.82 秒；这一轮 1,000 相对 500 的吞吐增益不足 8%，所以本机回落。该结论不作为生产固定上限：全历史 Replay 可按有效 CPU、内存和相邻档实测收益继续超过兼容提示 1,000，事务超过 3 秒或收益停止时自动回落。
- 完成跨 Artifact 聚合、批量写入和所有 Replay 路径资源增长后，同一隔离场景为 17.093 秒 Worker 墙钟、590.89 行/秒，相对修复前 96.983 秒、104.72 行/秒提高 5.64 倍；端到端从约 96.98 秒缩短到 17.56 秒。
- 同一 10,000 行、2,100 别名输入通过服务端目录与本地上传的统一 Data Import 总吞吐分别为 715.30 与 720.25 行/秒，导入阶段分别为 814.68 与 818.80 行/秒，差异约 0.7%。
- 最新 Replay×导入×撤回混合负载中，Replay 处理 10,100 行为 236.05 行/秒并累计主动让路约 10.6 秒；10,000 行导入在 Replay 前/中/后分别为 553.95 / 685.54 / 748.71 行/秒，在撤回中/后分别为 660.96 / 727.51 行/秒。2,000 行 Chunk 约 2.3–3.3 秒，没有复现生产旧版的 69–94 秒。
- 运行中取消的真实 PostgreSQL 集成验证中，HTTP 在 2 秒内持久受理，Replay 停止继续入库，协调 Job 随后创建撤回 Job并达到 `reverted`，贡献账本全部结清且没有活动来源残留；数据库受理提交耗时 18.191 毫秒。
- 当前代码的 10,000 行单 Worker 导入档位对照为：1,000 行 373.25 行/秒、2,000 行 393.04 行/秒、4,000 行 412.66 行/秒。4,000 相对 2,000 仅再提高约 5%，事务约 8.1 秒，因此单事务护栏停在 4,000，更多 CPU 通过受全局预算约束的 Job 并发使用。

## 合理推断

- 取消 HTTP 同步等待 Replay 正持有的父请求/子 Job 行锁，会让代理先返回 504；旧前端随后用旧父状态覆盖乐观状态，表现为按钮恢复，而持久协调与撤回可能稍后才开始。
- 大目录下逐行遍历全部别名并因 Pydantic JSON 恢复后对象身份变化重复编译匹配状态，是 Replay 和导入共同的主 CPU 放大器；单纯增加 Worker 会复制低效工作并加剧数据库竞争。
- Evidence、before/after 快照、贡献账本和投影逐行往返，以及小 Artifact 各自提交事务，是第二类写放大；必须批量化并保留真实 DML RETURNING、Fencing 和精确撤回语义。

## 暂时无法验证

- 当前服务器尚未部署本分支，因此生产大库上的新阶段耗时、WAL、I/O、CPU 和最终吞吐只能在合并后的 Release 部署后复测。
- 本机容量库能证明机制和相对改进，不能把其绝对吞吐直接承诺为服务器 SLO。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 计划证据 |
| --- | --- | --- | --- | --- |
| R1 | 系统解决历史重筛吞吐慢，最差重新筛选应与初次入库有可比速度 | Issue #630 / 用户生产复现 | satisfied | 同机隔离 Replay 提高 5.64 倍；目录顺序 A/B 单遍差异 3.3%；统一导入与 Replay 均为同一数量级 |
| R2 | “取消并撤回”必须正确持久受理、显示真实状态并最终撤回 | Issue #630 / 用户生产复现 | satisfied | 父锁并发集成、重复点击幂等、前端单调状态、真实 Worker 取消到 `reverted` 对账 |
| R3 | 修复数据导入性能回退，不得以提高全局资源掩盖共享数据库争用 | Issue #630 / 用户生产复现 | satisfied | 批量 Evidence、Resolver 复用、前后台写槽；混合负载 2,000 行 Chunk 约 2.3–3.3 秒 |
| R4 | 日志足以由用户重新运行后定位，不要求浏览器 Console 或 Network | 用户明确要求 | satisfied | API 接收/数据库阶段/提交/失败、协调批次/终态、Replay/Import 阶段字段均按 request/replay/job ID 关联 |
| R5 | 保持 Contract、Schema、贡献账本、Fencing、Checkpoint 与精确撤回 | 项目 AGENTS.md | satisfied | Contract 检查；139 项数据库/Job 与 169 项 API/Ingestion 回归；无 Schema Migration |
| R6 | 完成 Review、CI、PR 与交付门禁 | 项目 AGENTS.md | not_satisfied | Completion Audit、独立 Review、current-head CI |
| R7 | 覆盖本地电脑导入、历史目录导入、Replay、取消协调、撤回的串行与并行操作矩阵，所有路径均保持可用吞吐和正确对账 | 用户补充验收 | satisfied | 服务端/本地导入 0.7% 差异；Replay×Import×Reversal mixed-load；运行中取消与终态账本对账 |
| R8 | 服务器按 16 核 / 64 GB 资源边界自适应利用机器性能，不按开发机写死并发和批量 | 用户补充验收 | satisfied | 资源模拟选择 8 Worker、2 前台保留、4,000 行护栏；批量继续由实测吞吐升降档 |
| R9 | 先建品牌车型再导入与先导入再建目录并重筛，最终结果一致，且目录创建顺序不能使单遍处理变慢 | 用户补充验收 | satisfied | 10,100 行 / 2,100 别名 A/B 最终均 10,100 条 Content，逐遍吞吐差异 3.3% |
| R10 | 所有相关数据处理都能随机器资源增长；修复后隔离吞吐提高、处理时间缩短，同时保留多用户 API 稳定性 | 用户补充验收 | satisfied | Replay 5.64 倍；1k/2k/4k 导入档位；全局 Worker、前台保留、后台写槽测试与混合负载 |

# 实施计划

1. 为取消路径增加低频阶段日志：HTTP 到达、管理员校验后受理、父状态/锁阶段、取消协调 Job 入队、事务提交、返回，以及协调 Worker 的批次/锁忙/完成/失败。
2. 用并发 PostgreSQL 测试复现按钮恢复所对应的服务端失败边界；若取消仍能被 Replay 父行或 Job 行阻塞，缩短 HTTP 事务并修复锁顺序/状态收敛。
3. 把 Replay 与 Historical Import 的高耗时阶段细分为可比较、低频的聚合日志；避免每批刷 INFO。
4. 在本地 PostgreSQL 分别运行 Replay、初次导入、已有内容导入、Evidence 写入和 mixed-load；先用 2,000 行定位，再用更大批量验证扩展性。
5. 执行操作矩阵：两类统一导入串行/并行、导入与 Replay 并行、取消与运行中提交并行、撤回与导入并行；比较吞吐、锁等待、取消生效延迟和最终数据对账。
6. 用 16 核 / 64 GB 资源快照验证 Worker、批量和并行窗口选择仍由资源与实测吞吐决定，并验证前台进程保留与后台写槽收缩。
7. 回归取消、撤回、入库正确性、性能、静态检查和构建；同步长期排障文档并完成独立 Review、CI、PR 合并及 main-fresh 检查。

# 验证矩阵

| 维度 | 状态 | 验证 |
| --- | --- | --- |
| 前端状态 | required | 确认提交、请求异常、刷新旧/新父状态、重复点击 |
| API / 日志 | required | 接收、提交、冲突/异常和 request/replay ID 关联 |
| PostgreSQL 并发 | required | 父行/Job 行锁、幂等受理、取消协调、自动撤回 |
| Replay 正确性/性能 | required | New/Existing/低命中；隔离和 mixed-load 阶段吞吐 |
| Historical Import | required | Evidence 阶段、初次导入、重筛前/并行/后对照 |
| Local Data Import | required | 与历史目录相同输入、策略和批量的单独/并行对照 |
| 并行操作矩阵 | required | Import×Replay、Cancel×Replay、Reversal×Import、双 Import；吞吐、延迟、锁等待和对账 |
| 16 核 / 64 GB 自适应 | required | 资源快照单测、并发/批量选择与实际吞吐反馈 |
| 静态/生成/构建 | required | Ruff、mypy、前端 lint/typecheck/build、Contract check |
| 目录顺序 A/B | required | 先建目标目录后首次导入；先过滤后建目标目录并 Replay；结果与单遍吞吐 |
| 生产实测 | limited | 用户部署后重跑；本任务不擅自部署或写生产数据 |

# 风险、兼容与回滚

- 日志必须低频且只记录 ID、状态、数量、阶段、耗时和安全错误类；禁止正文、Raw、Token、Cookie 或 Secret。
- 若修改内部批处理或锁边界，必须通过真实 PostgreSQL 的账本、幂等、Fencing 与撤回回归。
- 公共 HTTP 与数据库 Schema 默认不变；发现必须变更时先更新本 Change 与对应 Contract/Migration 决策。
- 应用代码可按既有 Release 回滚；若存在新状态或新 Job 类型，必须先证明旧 Worker 可识别，否则以前滚修复为主。

# 完成审计

- [ ] upstream_re_read：重新读取 Issue #630、用户日志与最终代码。
- [ ] change_coverage：R1–R10 均达到 satisfied 或有正式延期依据。
- [ ] reverse_audit：前端动作到 API、API 到父状态/协调 Job、Worker 到撤回终态；Replay 到 Import 共享数据库影响。
- [ ] unresolved_cleared：没有用日志、机器性能或局部优化冒充根因闭环。
