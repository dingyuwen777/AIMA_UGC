---
schema: rvc-change/v1
id: CHG-20260824-deepseek-final-official-pricing
title: 以 DeepSeek 官方页面正文恢复 V4-Pro 分时价格
level: L2
status: in_progress
owner: aima
branch: fix/deepseek-official-direct-pricing
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

# 目标

以 2026-08-24 直接打开的 DeepSeek 官方“模型 & 价格”页面正文为最终外部事实源，恢复 `deepseek-v4-pro` 北京时间工作日分时价格，并撤销 PR #214 基于搜索摘要做出的全天价回滚。保留 `effective_date` 时点保护。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 联网查询 DeepSeek 最新官方价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | not_satisfied | 官方页面正文已直接核验：V4-Pro 空闲/高峰价格分别为 0.15/0.30、4.5/9.0、13.5/27.0 CNY/百万 tokens；待恢复机器事实。 |
| R2 | 高峰时段仅北京时间周一至周五 09:00-12:00、14:00-18:00 | user:2026-08-24-latest-deepseek-pricing | not_satisfied | 官方页面正文脚注明确该规则；待恢复 weekday schedule。 |
| R3 | 保留 effective_date 时点约束 | backend/src/aima_ugc/adapters/llm/README.md | not_satisfied | 目标恢复树来自 PR #212，其包含 PR #210 的 effective_date 保护。 |
| R4 | 不把搜索摘要覆盖官方页面正文 | AGENTS.md | not_satisfied | PR #215 已关闭未合并；本 Change 以直接官方页面正文作为最终外部证据。 |

# 官方事实

DeepSeek 官方 `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/` 当前页面正文：

- `deepseek-v4-pro` 输入缓存命中：空闲 `0.15`、高峰 `0.30` CNY/百万 tokens；
- 输入缓存未命中：空闲 `4.5`、高峰 `9.0`；
- 输出：空闲 `13.5`、高峰 `27.0`；
- 高峰：北京时间周一至周五 `09:00-12:00`、`14:00-18:00`，其余为空闲。

# 成功标准

- [ ] `pricing.toml` 恢复 `Asia/Shanghai` 的 off_peak/peak 配置并与官方页面正文一致。
- [ ] `pricing.py` 恢复可选 weekday period 选择能力，未配置 weekday 的既有 period 继续每天适用。
- [ ] 工作日/周末分时测试、成本审计、retry cost、effective_date 回归全部通过。
- [ ] PR #214 的全天价回滚被完整纠正，不留下半套实现。
- [ ] 当前永久 CI 全绿后正常合并 main，并通过独立归档记录整个纠错链。

# 实现策略

采用精确恢复：以已通过完整 CI 的 PR #212 merge tree `8deae122...` 为代码/测试/README 基线，移除其旧 Active Change，新增本最终 Change；提交父节点保持当前 main，避免历史重写。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | 分时价格、weekday、成本审计、retry cost、effective_date、Ruff、mypy。 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract。 |
| PostgreSQL Integration | not_applicable | 无数据库变化；永久 CI 仍做回归。 |
| Browser Mock / Full-stack | not_applicable | 无 UI 变化；永久 Full-stack 作为仓库级回归。 |
| Real Provider Probe | not_applicable | 价格事实由 DeepSeek 官方页面正文直接核验，无需产生付费请求。 |
| Runtime / Deployment Regression | required | Local Dev、Windows Compose、Internal V1-A。 |

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 交付

- 分支：`fix/deepseek-official-direct-pricing`
- PR #215 已关闭且未合并。
- 用户已授权继续修复并合并 `main`。
