---
schema: rvc-change/v1
id: CHG-20260824-deepseek-current-pricing-rollback
title: 回滚分时价格并恢复全天价（错误中间状态，已纠正）
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

> **本 Change 记录一个已被后续纠正的中间状态，不代表当前系统事实。**
>
> PR #214 曾基于搜索结果摘要，把 `deepseek-v4-pro` 从分时价格回滚为 `0.025 / 3 / 6` CNY/百万 tokens 全天价，并删除 weekday 调度。该 PR 于 `2026-08-24` 合并为 `5d5ea112bcdaab24b29db1402151ddf24d8d755f`。
>
> 随后在归档前直接打开 DeepSeek 官方价格页面正文复核，页面明确展示 V4-Pro 工作日分时价格。归档 PR #215 因此被关闭且未合并；PR #216 恢复分时实现并于 `c7d69a50d18acaaebd2f93a6499945e1485b1219` 合入 main。当前事实以 `pricing.toml` 与 `CHG-20260824-deepseek-final-official-pricing` 为准。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 联网查询 DeepSeek 最新官方价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | satisfied | 本 Change 当时完成了代码与测试，但其采用的搜索摘要后来被直接官方页面正文否定；后续 PR #216 已纠正机器事实。 |
| R2 | 不保留未经官方正文支持的价格事实 | AGENTS.md | satisfied | 归档前重新核验官方页面，发现冲突后关闭 #215，并由 #216 恢复分时价格。 |
| R3 | 保留 effective_date 时点约束 | backend/src/aima_ugc/adapters/llm/README.md | satisfied | 该能力在 #214 和后续 #216 中均保留。 |
| R4 | 错误中间状态必须可审计但不能作为当前设计依据 | AGENTS.md | satisfied | 本文件以历史记录形式保存，顶部明确标注已被纠正；当前机器事实不引用本记录作为价格来源。 |

# 历史实现与验证

- Implementation PR #214：正常通过当时 6/6 永久门禁并合入 main；这只能证明实现符合当时 Change 定义，不能证明搜索摘要本身正确。
- #214 merge commit：`5d5ea112bcdaab24b29db1402151ddf24d8d755f`。
- Archive PR #215：closed / unmerged。
- Corrective PR #216：Final Ready 6/6 永久 workflow success，并恢复官方页面正文对应的分时价格。

# Completion Audit

- [x] upstream_re_read：归档前重新读取 current main 和 DeepSeek 官方价格页面正文，发现搜索摘要与正文冲突。
- [x] change_coverage：#214 实现、测试、合并、#215 关闭和 #216 纠正均有 Git 证据。
- [x] reverse_audit：确认 #214 删除的 weekday/分时能力已由 #216 完整恢复，`effective_date` 未丢失。
- [x] unresolved_cleared：该中间状态已不在 active；当前 main 已由 #216 恢复最终官方正文价格。

# 当前状态

当前 `main` 不使用本 Change 的全天价。当前价格见：

```text
backend/src/aima_ugc/adapters/llm/pricing.toml
```

当前正式行为是北京时间工作日分时价格，并保留 `effective_date = 2026-08-24`。

# Git / 交付

- Historical implementation PR: #214，merge `5d5ea112bcdaab24b29db1402151ddf24d8d755f`。
- Historical archive PR: #215，closed / unmerged。
- Superseding implementation PR: #216，merge `c7d69a50d18acaaebd2f93a6499945e1485b1219`。
- 本记录仅用于审计，不是当前价格事实源。
