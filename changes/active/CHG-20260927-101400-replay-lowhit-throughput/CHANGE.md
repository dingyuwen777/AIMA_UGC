---
schema: coding-change/v1
id: CHG-20260927-101400-replay-lowhit-throughput
title: 历史重筛低命中且新记录较多时的吞吐回归
level: L3
status: active
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
affected_paths:
  - backend/src/aima_ugc/bootstrap/canonical_replay_worker.py
  - backend/src/aima_ugc/platform/capacity.py
  - tests/
  - docs/appendix/08_数据入口与统一入库实现.md
contracts: []
data_changes: []
---

# 变更摘要

Issue #624 的合并后复测。用户提供的运行截图显示重筛在约 10 小时后仍为 35%，命中 1,676,245 / 读取 7,537,544（22.2%），已新增 912,024、处理已有 740,578。截图任务创建于本轮代码合并前，当前部署 revision 尚未核实，不能据此声称新代码的线上性能。用户要求确定性证据、系统排查并继续优化。

# 背景、现状与问题

在隔离 PostgreSQL 18.4、同一夹具、同机交替运行的 20,000 raw / 22.2% matched / 44.1% Existing 样本中，合并前 main `8778f8e7` 的 Replay 三次为 11.646 / 11.720 / 11.736 秒，当前 main `0bec01bb` 为 13.102 / 11.814 / 12.224 秒；SQL 语句数分别为 1,032 与 1,259。新代码在该输入形态下未证明提速，并有 227 条额外 SQL。报告在本轮临时目录，交付前将摘要落入本 Change；该样本不等于生产环境。

当前可疑机制是 matched-aware 扫描的初始事务目标为 125 matched rows，22% 命中时将约 560 raw rows 提交一次，而旧版约 1,000 raw rows 一次。当前样本的 seen/contribution ledger 插入次数从 18 增至 33，说明事务碎片化；仍需阶段耗时与受控实验确认因果，再选择修复。线上约 10 小时的主因尚不能由该小样本推定，等待当前部署 revision 与新鲜 Worker/数据库指标。

# 目标、成功标准与非目标

- 以可重复同机 A/B 实验确认并修复 20%–30% 命中、New/Existing 混合输入下的事务碎片化与吞吐回归。
- 保持 Replay 数据正确性、Fencing/checkpoint/取消/接管/撤回、3 秒事务 ceiling、资源压力降档、非 Replay Worker reserve 与 Host/Compose 资源预算。
- 同时覆盖 5%/25%/80% 命中和 Existing/New 组合，不以单一样本提速掩盖另一场景退化。
- 当前部署 revision 与运行日志未取得前，不宣称线上 10 小时任务的根因或优化效果。

非目标：提高全局 CPU/内存配额，删除低命中 shard gate，改变公共 Contract/Schema/Migration，生产部署或生产数据操作。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 系统排查并给出可重复性能证据，不把截图当作新代码效果 | 本轮用户请求 | not_satisfied | 等待阶段指标、复测和部署 revision |
| R2 | 修复代表性低命中 New/Existing 混合场景的已测吞吐回归 | 本轮用户请求；Issue #624 目标状态 | not_satisfied | 三轮 A/B 已暴露回归，待因果实验与修复 |
| R3 | 其他输入形态、资源安全、正常数据链路与正确性不退化 | Issue #624 AC1–AC9；项目 AGENTS.md | not_satisfied | 待分层验证与 mixed load |
| R4 | current-head CI、Review、main-fresh、Change Archive、Issue Closure | Issue #624 AC9–AC10；项目 AGENTS.md | not_satisfied | 待交付 |

# 实施计划

1. 对比旧版与当前版的匹配目标、扫描窗口、事务次数及阶段墙钟；受控改变单一参数验证因果。
2. 只在 Replay 局部调整必要的 batch 决策，保持资源降档和事务 ceiling；先写能暴露回归的测试，再实现。
3. 重跑同机隔离 PostgreSQL A/B、不同命中/New 比例、mixed-load 和 Replay 功能回归。
4. 同步目标文档、Completion Audit、两阶段 Review、CI 与交付。

# 验证矩阵

| 维度 | 状态 | 计划 |
| --- | --- | --- |
| 单元 / 控制器 | required | 低命中初始档位、升降档、资源压力、单事务上限 |
| PostgreSQL 集成 | required | Replay 结果、checkpoint、撤回及 SQL/事务计数 |
| 性能 / 混合负载 | required | 交替重复 A/B；5%/25%/80%，New/Existing 与正常 Import |
| 静态 / 文档 | required | Ruff、mypy、Change 检查、目标排障文档 |
| 生产实测 | explicitly_deferred | 用户提供当前部署 revision 与新鲜日志后再做同负载诊断 |

# Completion Audit

- [ ] upstream_re_read：重新读取用户请求、Issue #624 与当前实现。
- [ ] traceability_checked：核对上游要求、Change、实现/测试/文档。
- [ ] reverse_audit：复核 Replay 优化对 Worker、其他 Job、撤回链路的影响。
- [ ] validation_checked：逐项检查验证矩阵和证据新鲜度。
- [ ] review_checked：完成独立需求与代码审查。
