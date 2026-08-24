---
schema: rvc-change/v1
id: CHG-20260824-deepseek-official-pricing-correction
title: 修正 DeepSeek V4-Pro 官方分时价格（历史实现，已回滚）
level: L2
status: done
owner: aima
branch: archive/deepseek-pricing-final-correction
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - llm
  - pricing
  - testing
affected_paths:
  - backend/src/aima_ugc/adapters/llm/pricing.py
  - backend/src/aima_ugc/adapters/llm/pricing.toml
  - backend/src/aima_ugc/adapters/llm/README.md
  - tests/unit/analysis/test_deepseek_official_pricing.py
  - tests/unit/analysis/test_llm_pricing.py
  - tests/unit/analysis/test_llm_request_audit.py
  - tests/unit/analysis/test_openai_compatible_llm.py
contracts: []
data_changes: []
---

# 历史纠错说明

> **本 Change 只保存历史过程，不代表当前系统事实。**
>
> PR #212 曾基于一次错误的外部价格事实解读，把 `deepseek-v4-pro` 改成工作日分时价格并新增 weekday 调度；该 PR 已于 `2026-08-24` 合并为 `8deae122b94d613868cd8000512f96ed43917691`。在独立归档前再次直接核验 DeepSeek 官方当前价格页后，确认当前正式价格实际为缓存命中 `0.025`、缓存未命中 `3`、输出 `6` CNY/百万 tokens，官方当前页未列分时价格。
>
> 因此归档 PR #213 被关闭且未合并；后续 `CHG-20260824-deepseek-current-pricing-rollback` / PR #214 已完整回滚本 Change 的价格、weekday 实现与测试，并于 merge commit `5d5ea112bcdaab24b29db1402151ddf24d8d755f` 恢复当前正确机器事实。

# 原目标

当时的目标是把 AIMA `deepseek-v4-pro` 价格目录切换为被误读为官方当前规则的“空闲/高峰 + 工作日”计费，同时保留 `effective_date`。该目标已经被后续官方事实核验否定并整体回滚。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 联网查询 DeepSeek 官方最新价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | satisfied | 本 Change 当时完成了实现与测试，但依赖的外部事实解读后来被官方当前页面复核推翻；当前事实以 PR #214 与纠错 Change 为准。 |
| R2 | 将当时解读的 off-peak / peak 单价写入机器配置 | user:2026-08-24-latest-deepseek-pricing | satisfied | PR #212 曾实际实现并通过 CI；后由 PR #214 完整回滚，不再属于当前系统。 |
| R3 | 为当时解读的工作日高峰增加 weekday 调度 | user:2026-08-24-latest-deepseek-pricing | satisfied | PR #212 曾实现 weekday parser/schedule/overlap；PR #214 已删除该新增能力。 |
| R4 | 保留 effective_date | backend/src/aima_ugc/adapters/llm/README.md | satisfied | `effective_date` 来自 PR #210，PR #214 回滚分时实现时仍保留该正确能力。 |

# 历史实现与验证

- Red CI `32742941803`：当时新增的 3 条分时用例失败，结果 `3 failed, 621 passed`。
- Focused Green `32743351928`：weekday 调度目标用例、Ruff、mypy 通过。
- Complete Pricing Green `32743731463`：Pricing/Adapter/Audit/effective-date 相关套件通过。
- Final Ready HEAD `26ce5209350ee514e48553f15964165ae2fe3d63` 的 6 个永久 workflow 当时全部成功。
- Implementation PR #212 merge commit：`8deae122b94d613868cd8000512f96ed43917691`。
- 上述验证只证明“实现符合当时 Change 定义”，**不证明其依赖的外部价格事实正确**；这一缺口正是后续归档前复核发现并由 PR #214 纠正的原因。

# Completion Audit

- [x] upstream_re_read：原 Change Ready 前执行过仓库与外部事实复核，但外部事实解读后来被证明错误；归档时再次读取当前官方页面并记录纠错链。
- [x] change_coverage：历史实现、测试、PR #212 合并以及后续回滚关系均有 Git 证据。
- [x] reverse_audit：归档时确认本 Change 的 `weekdays`、分时 TOML 和专项测试已全部从当前 main 移除；`effective_date` 正确能力保留。
- [x] unresolved_cleared：本 Change 不再是 Active 当前事实；PR #213 closed/unmerged；PR #214 已通过 6/6 永久门禁并完成回滚。

# 当前状态

当前 `main` 不使用本文分时价格。当前正式机器事实见：

```text
backend/src/aima_ugc/adapters/llm/pricing.toml
```

当前值为：

```text
input_cache_hit_per_million_tokens = 0.025
input_cache_miss_per_million_tokens = 3
output_per_million_tokens = 6
```

并保留 `effective_date = 2026-08-24` 的运行时约束。

# Git / 交付

- Historical implementation PR: #212，merged as `8deae122b94d613868cd8000512f96ed43917691`。
- Historical archive PR: #213，closed / unmerged。
- Corrective PR: #214，merged as `5d5ea112bcdaab24b29db1402151ddf24d8d755f`。
- Superseding Change: `CHG-20260824-deepseek-current-pricing-rollback`。
- 本记录仅用于保留错误实施及纠正过程的可审计历史，不是当前设计依据。
