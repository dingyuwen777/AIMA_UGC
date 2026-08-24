---
schema: rvc-change/v1
id: CHG-20260824-deepseek-official-pricing-correction
title: 修正 DeepSeek V4-Pro 官方分时价格（首次实现，最终由 #216 重新确认）
level: L2
status: done
owner: aima
branch: archive/deepseek-final-official-pricing
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

# 历史状态说明

本 Change 是 `deepseek-v4-pro` 工作日分时价格的首次正式实现。PR #212 于 `2026-08-24` 合入 main，随后曾被 PR #214 基于搜索摘要临时回滚；归档前再次直接打开 DeepSeek 官方价格页面正文后，确认本 Change 的分时价格与工作日高峰规则和官方正文一致。最终 PR #216 在 current main 上重新恢复并验证同一行为。

因此，本 Change 的**业务实现方向最终被确认正确**，但当前系统事实仍应读取 `pricing.toml`、当前代码和最终 Change `CHG-20260824-deepseek-final-official-pricing`，而不是依赖历史 Change。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 联网查询 DeepSeek 官方最新价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | satisfied | 直接官方页面正文最终确认 V4-Pro 空闲/高峰价格为 0.15/0.30、4.5/9.0、13.5/27.0 CNY/百万 tokens。 |
| R2 | 高峰仅北京时间工作日 09:00-12:00、14:00-18:00 | user:2026-08-24-latest-deepseek-pricing | satisfied | 首次实现增加可选 weekday schedule，最终 PR #216 使用相同机器行为并再次通过完整 CI。 |
| R3 | 保留 effective_date | backend/src/aima_ugc/adapters/llm/README.md | satisfied | PR #210 的 effective_date 保护在 #212、#214、#216 全链路均保留。 |
| R4 | 历史 Change 不代替当前机器事实 | AGENTS.md | satisfied | 当前价格事实由 main 的 `pricing.toml`/代码维护，最终 Change 记录最终核验；本文件仅保存首次实现历史。 |

# 历史实现与验证

- PR #212 Red：新增官方分时价格用例在旧全天价下失败，结果 `3 failed, 621 passed`。
- Focused Green `32743351928`：工作日 08:00 off-peak、工作日 09:00 peak、周末 09:00 off-peak、Ruff、mypy 通过。
- Complete Pricing Green `32743731463`：Pricing/Adapter/Audit/effective-date 相关套件通过。
- PR #212 Final Ready 6/6 永久 workflow 全绿，merge commit `8deae122b94d613868cd8000512f96ed43917691`。
- PR #214 曾临时回滚该实现；最终 PR #216 重新恢复同一价格/weekday 行为并在 current main 上 6/6 永久 workflow 全绿。

# Completion Audit

- [x] upstream_re_read：最终归档前重新读取 current main 和 DeepSeek 官方页面正文，确认首次分时实现与正文一致。
- [x] change_coverage：首次实现、临时回滚、最终恢复均有 PR/commit/CI 证据。
- [x] reverse_audit：最终 main 的 TOML、weekday 调度、Adapter/audit 消费链与本 Change 的核心实现方向一致；`effective_date` 仍保留。
- [x] unresolved_cleared：本 Change 不再 Active；最终行为由 #216 和最终 Change 接管。

# 当前状态

当前正式价格配置：

- off-peak：`0.15 / 4.5 / 13.5` CNY/百万 tokens；
- peak：`0.30 / 9.0 / 27.0` CNY/百万 tokens；
- peak：北京时间周一至周五 `09:00-12:00`、`14:00-18:00`；
- `effective_date = 2026-08-24`。

# Git / 交付

- First implementation PR: #212，merge `8deae122b94d613868cd8000512f96ed43917691`。
- Temporary rollback PR: #214，merge `5d5ea112bcdaab24b29db1402151ddf24d8d755f`。
- Final restoring PR: #216，merge `c7d69a50d18acaaebd2f93a6499945e1485b1219`。
- 本记录仅保存首次实现历史，最终交付以 #216 与最终 Change 为准。
