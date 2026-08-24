---
schema: rvc-change/v1
id: CHG-20260824-deepseek-current-pricing-rollback
title: 回滚错误分时价格并恢复 DeepSeek 当前官方价
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
  - changes/active/CHG-20260824-deepseek-official-pricing-correction/CHANGE.md
contracts: []
data_changes: []
---

# 目标

在归档前重新核验 DeepSeek 官方当前“模型 & 价格”页面后，纠正 PR #212 已合入 `main` 的错误分时价格判断：恢复 `deepseek-v4-pro` 当前官方人民币全天价 `0.025 / 3 / 6` CNY/百万 tokens，撤销为该错误判断新增的 weekday/分时调度实现与相关测试，同时保留 PR #210 已正确实现的 `effective_date` 运行时约束。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 联网查询 DeepSeek 最新官方价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | satisfied | 2026-08-24 最终重新核验官方 `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/`：V4-Pro 当前为缓存命中 0.025、缓存未命中 3、输出 6 CNY/百万 tokens；`pricing.toml` 与正式 DeepSeek 测试已恢复该事实。 |
| R2 | 不保留与当前官方事实不一致的分时价格/weekday 逻辑 | user:2026-08-24-latest-deepseek-pricing | satisfied | PR #214 精确恢复 PR #212 第一父 `d6828e22...` 的代码树；`pricing.py` 不再包含 #212 新增 weekday schedule/parser/overlap 逻辑，错误分时专项测试已移除。 |
| R3 | 保留已验证的 effective_date 时点约束 | backend/src/aima_ugc/adapters/llm/README.md | satisfied | 恢复树来自 PR #210 完成并归档后的 `d6828e22...`；`price_for(..., at=...)`、Adapter cost-unavailable 和历史复算保护均保留。 |
| R4 | 错误分时 Change 不得继续作为当前 Active 正确事实 | AGENTS.md | satisfied | PR #213 已关闭且未合并；PR #214 移除错误 Active Change，本归档 PR 只保留其历史记录并明确标注已被纠正。 |

# 当前官方事实

DeepSeek 官方当前页面列出的 `deepseek-v4-pro` 人民币价格：

- 百万 tokens 输入（缓存命中）：`0.025 CNY`；
- 百万 tokens 输入（缓存未命中）：`3 CNY`；
- 百万 tokens 输出：`6 CNY`；
- 官方当前价格页未列出该模型的分时价格或工作日高峰规则。

# 成功标准

- [x] `pricing.toml` 恢复为 `0.025 / 3 / 6` CNY/百万 tokens 的全天配置。
- [x] 撤销 PR #212 新增的 weekday schedule/parser/overlap 逻辑。
- [x] DeepSeek 正式 Unit/Audit/Retry 成本测试恢复当前官方全天价；错误分时价格专项测试删除。
- [x] PR #210 的 `effective_date`、Adapter cost-unavailable 和历史复算保护保持不变。
- [x] 错误分时 Change 不再留在 `changes/active/`。
- [x] Implementation PR #214 已通过当前全部永久门禁并正常合并 `main`。

# 实现策略

采用精确树回滚：以 PR #212 合并前第一父 `d6828e22bf408bfd2c05228f4614dd74991b5ff7` 作为代码/测试/README 事实基线，再保留当前纠错 Change。这样完整撤销 #212 的价格/weekday 差异，同时保留 PR #210 已验证的 `effective_date` 修复。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | Final Ready CI `32745874148`：621 Unit、75 Contract、34 API 全部通过；Ruff、mypy、Architecture/Owner、Secret/docs、Wheel 通过。 |
| Contract / Generated Client | not_applicable | 无公共 Contract 变化；Final Ready CI 的 OpenAPI/Orval drift 与兼容检查通过。 |
| PostgreSQL Integration | not_applicable | 无数据库变化；Final Ready CI PostgreSQL Integration 全部成功。 |
| Browser Mock / Full-stack | not_applicable | 无 UI/业务接线变化；39 Vitest、22 Browser Mock Playwright 以及 Full-stack Acceptance `32745874577` 通过。 |
| Real Provider Probe | not_applicable | 价格事实直接来自 DeepSeek 官方价格页，无需产生付费模型请求。 |
| Runtime / Deployment Regression | required | Local Dev `32745874778`、Windows Compose `32745874521`、Internal V1-A `32745874371` 均成功。 |

# Completion Audit

- [x] upstream_re_read：Implementation merge 前与归档前均重新读取 `main` AGENTS、Change 管理规则、LLM Pricing 机器事实，并重新核验 DeepSeek 官方价格页面。
- [x] change_coverage：用户要求“联网查最新价格、修复代码和测试、合并 main”均映射到配置、实现、测试、错误 Change 清理与 Git 交付。
- [x] reverse_audit：配置→`LLMPricingCatalog.price_for()`→Adapter→request audit/recalculation 两条价格消费链均恢复 PR #210 已验证语义。
- [x] unresolved_cleared：R1—R4 全部 satisfied；PR #213 已关闭未合并；PR #214 Final Ready 6/6 永久 workflow 全绿。

# Review

## Correctness / Scope

- 最终官方事实以 DeepSeek 当前价格页为准，正式配置是全天 `0.025 / 3 / 6`。
- PR #214 使用精确树恢复，避免手工反改漏掉 #212 的 parser/test/doc 片段。
- 不修改 DeepSeek endpoint、模型 ID、请求体、Prompt、usage 字段、重试策略、数据库、公共 Contract 或依赖。

## Reliability / Compatibility

- PR #210 的 `effective_date` 保护保留：早于 `2026-08-24` 的请求不会套用这份 AIMA 价格目录；在线 LLM 请求仍不因 cost unavailable 被阻断。
- legacy `price_periods` 能力仍存在；只撤销 #212 新增的 weekday 扩展。
- 无 Migration 或部署顺序变化。

# Git / 交付

- Implementation branch: `fix/deepseek-official-current-pricing`
- Implementation PR: #214
- Final Ready HEAD: `b50d2836b7c41dd46eb958eb90dec0b7bdbd193d`
- Final Ready workflows: CI `32745874148`、Full-stack `32745874577`、Local Dev `32745874778`、Windows Compose `32745874521`、Internal V1-A `32745874371`、Change Gate `32745874615`，6/6 success。
- Implementation merge commit: `5d5ea112bcdaab24b29db1402151ddf24d8d755f`
- PR #213: closed / unmerged。
- 本文件通过独立归档 PR 移入 `changes/archive/2026-08/`。
