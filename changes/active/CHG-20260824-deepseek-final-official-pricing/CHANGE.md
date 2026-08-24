---
schema: rvc-change/v1
id: CHG-20260824-deepseek-final-official-pricing
title: 以 DeepSeek 官方页面正文恢复 V4-Pro 分时价格
level: L2
status: ready_for_review
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
| R1 | 联网查询 DeepSeek 最新官方价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | satisfied | 直接打开官方 `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/` 页面正文，V4-Pro 空闲/高峰价格明确为 0.15/0.30、4.5/9.0、13.5/27.0 CNY/百万 tokens；`pricing.toml`、README、测试已恢复该事实。 |
| R2 | 高峰时段仅北京时间周一至周五 09:00-12:00、14:00-18:00 | user:2026-08-24-latest-deepseek-pricing | satisfied | 官方页面正文脚注明确该规则；`pricing.py` 恢复可选 weekday schedule，DeepSeek peak 使用 `mon..fri` 和两个官方时间窗口。 |
| R3 | 保留 effective_date 时点约束 | backend/src/aima_ugc/adapters/llm/README.md | satisfied | 恢复树来自 PR #212，包含 PR #210 的 `price_for(..., at=...)` effective_date 保护；当前 CI 完整通过。 |
| R4 | 不把搜索摘要覆盖官方页面正文 | AGENTS.md | satisfied | PR #215 已关闭未合并；本 Change 以直接官方页面正文作为最终外部证据，并使用 current-main 永久 CI 重新验证。 |

# 官方事实

DeepSeek 官方当前页面正文对 `deepseek-v4-pro`：

- 输入缓存命中：空闲 `0.15`、高峰 `0.30` CNY/百万 tokens；
- 输入缓存未命中：空闲 `4.5`、高峰 `9.0`；
- 输出：空闲 `13.5`、高峰 `27.0`；
- 高峰：北京时间周一至周五 `09:00-12:00`、`14:00-18:00`，其余为空闲。

# 成功标准

- [x] `pricing.toml` 使用 `Asia/Shanghai` 的 off_peak/peak 配置并与官方页面正文一致。
- [x] `pricing.py` 支持可选 weekday period，未配置 weekday 的既有 period 继续每天适用。
- [x] 工作日/周末分时测试、成本审计、retry cost、effective_date 回归全部通过。
- [x] PR #214 的全天价回滚被完整纠正，不留下半套实现。
- [x] current-main 的 CI、Full-stack、Local Dev、Windows Compose、Internal V1-A 已通过；Ready 状态由 Completion Gate 再复验后正常合并 main。

# 实现策略

采用精确恢复：以已通过完整 CI 的 PR #212 merge tree `8deae122...` 为代码/测试/README 基线，移除其旧 Active Change，新增本最终 Change；提交父节点保持当前 main，避免历史重写。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | CI `32747865482`：Unit/Contract/API、Ruff、mypy、Architecture/Owner、Secret/docs、Wheel 全部成功；分时价格、weekday、成本审计、retry cost、effective_date 均由正式测试覆盖。 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract；CI 的 OpenAPI/Orval drift 与兼容检查额外通过。 |
| PostgreSQL Integration | not_applicable | 无数据库变化；CI `32747865482` PostgreSQL Integration 全部成功。 |
| Browser Mock / Full-stack | not_applicable | 无 UI 变化；CI Browser Mock 成功，Full-stack Acceptance `32747865501` 成功。 |
| Real Provider Probe | not_applicable | 价格事实由 DeepSeek 官方页面正文直接核验，无需产生付费请求。 |
| Runtime / Deployment Regression | required | Local Dev `32747865515`、Windows Compose `32747865454`、Internal V1-A `32747865495` 均成功。 |

# Completion Audit

- [x] upstream_re_read：重新读取 current main `AGENTS.md`、Change 规则、LLM Pricing 实现/TOML/README/测试，并直接打开 DeepSeek 官方价格页面正文复核。
- [x] change_coverage：用户要求“联网查最新价格、修复代码和测试、合并 main”已覆盖官方正文事实、价格配置、weekday 选价、成本测试和 Git 交付。
- [x] reverse_audit：官方价格→TOML→本地时区/weekday 选择→Adapter→request audit/recalculation 两条消费者链均复核；`effective_date` 正确能力保留。
- [x] unresolved_cleared：R1—R4 全部 satisfied；PR #215 已关闭未合并；5 个非 Change 永久 workflow 与主 CI 均成功。

# Review

## Correctness / Scope

- 当前官方页面正文明确展示分时价格与工作日高峰脚注；页面正文优先于搜索摘要。
- 恢复使用已验证的 #212 tree，避免再次人工拼接价格实现。
- 不修改 DeepSeek endpoint、模型 ID、Prompt、usage、重试、数据库、公共 Contract 或依赖。

## Reliability / Compatibility

- `weekdays` 为可选内部 TOML 字段；未配置时既有 `price_periods` 每天适用。
- PR #210 的 `effective_date` 保护继续有效。
- 无 Migration 或部署顺序变化。

# 交付

- 分支：`fix/deepseek-official-direct-pricing`
- PR：#216（Draft；Ready Gate 通过后按用户授权正常合并）
- 代码候选 HEAD：`ce77f4895c71294680be2f0c8a5a522dd2c47d7a`
- PR #215：closed / unmerged。
- 用户已授权继续修复并合并 `main`。
