---
schema: rvc-change/v1
id: CHG-20260824-deepseek-final-official-pricing
title: 以 DeepSeek 官方页面正文恢复 V4-Pro 分时价格
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

# 目标

以 2026-08-24 直接打开的 DeepSeek 官方“模型 & 价格”页面正文为最终外部事实源，恢复 `deepseek-v4-pro` 北京时间工作日分时价格，并纠正此前基于搜索摘要做出的全天价回滚；同时保留 `effective_date` 时点保护。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 联网查询 DeepSeek 最新官方价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | satisfied | 直接打开官方 `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/` 页面正文，V4-Pro 空闲/高峰价格明确为 0.15/0.30、4.5/9.0、13.5/27.0 CNY/百万 tokens；`pricing.toml`、README、测试已同步。 |
| R2 | 高峰时段仅北京时间周一至周五 09:00-12:00、14:00-18:00 | user:2026-08-24-latest-deepseek-pricing | satisfied | 官方页面正文脚注明确该规则；`pricing.py` 支持可选 weekday schedule，DeepSeek peak 使用 `mon..fri` 和两个官方时间窗口。 |
| R3 | 保留 effective_date 时点约束 | backend/src/aima_ugc/adapters/llm/README.md | satisfied | PR #210 的 `price_for(..., at=...)` effective_date 保护保留；最终 CI 完整通过。 |
| R4 | 外部事实冲突时以直接官方页面正文为最终依据 | AGENTS.md | satisfied | PR #215 在归档前因再次直接核验官方页面而关闭未合并；PR #216 以官方页面正文为最终事实恢复分时实现。 |

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
- [x] 中间的全天价回滚已被完整纠正，不留下半套实现。
- [x] Implementation PR #216 已通过当前永久门禁并正常合并 `main`。

# 实现策略

采用精确恢复：以 PR #212 已通过完整 CI 的分时实现树为代码/测试/README 基线，在 current main 上重新建立正常提交，不重写历史。该实现包括：

- `pricing.toml` 的 `Asia/Shanghai` off_peak / peak；
- peak 的 `weekdays = mon..fri` 与 `09:00-12:00`、`14:00-18:00`；
- 内部可选 weekday period 解析、选择和重叠校验；
- PR #210 已有的 `effective_date` 运行约束。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | Final Ready CI `32748252045`：Unit/Contract/API、Ruff、mypy、Architecture/Owner、Secret/docs、Wheel 全部成功；分时价格、weekday、成本审计、retry cost、effective_date 均由正式测试覆盖。 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract；CI 的 OpenAPI/Orval drift 与兼容检查通过。 |
| PostgreSQL Integration | not_applicable | 无数据库变化；Final Ready CI PostgreSQL Integration 全部成功。 |
| Browser Mock / Full-stack | not_applicable | 无 UI 变化；CI Browser Mock 成功，Full-stack Acceptance `32748252047` 成功。 |
| Real Provider Probe | not_applicable | 价格事实由 DeepSeek 官方页面正文直接核验，无需产生付费请求。 |
| Runtime / Deployment Regression | required | Local Dev `32748252050`、Windows Compose `32748252077`、Internal V1-A `32748252088` 均成功。 |

# Completion Audit

- [x] upstream_re_read：Ready 前、Implementation merge 前和归档前均重新读取 current main `AGENTS.md`、Change 管理规则、LLM Pricing 实现/TOML/README/测试，并直接打开 DeepSeek 官方价格页面正文核验。
- [x] change_coverage：用户要求“联网查最新价格、修复代码和测试、合并 main”覆盖到官方正文事实、价格配置、weekday 选价、成本测试、CI 与 Git 交付。
- [x] reverse_audit：官方价格→TOML→本地时区/weekday 选择→Adapter→request audit/recalculation 两条消费者链均复核；`effective_date` 正确能力保留。
- [x] unresolved_cleared：R1—R4 全部 satisfied；Final Ready 6/6 永久 workflow 全绿；无未解释延期或未满足项。

# Review

## Correctness / Scope

- 最终外部事实使用 DeepSeek 官方页面正文，不使用搜索摘要覆盖正文。
- 恢复的是已通过完整 CI 的分时实现，不修改 DeepSeek endpoint、模型 ID、Prompt、usage、重试、数据库、公共 Contract 或依赖。
- 当前 `pricing.toml` 是本 Change 的机器事实；本归档仅保存决策与验证历史。

## Reliability / Compatibility

- `weekdays` 为可选内部 TOML 字段，未配置时既有 `price_periods` 行为不变。
- PR #210 的 `effective_date` 保护继续有效。
- 无 Migration 或部署顺序变化。

# Git / 交付

- Implementation branch: `fix/deepseek-official-direct-pricing`
- Implementation PR: #216
- Final Ready HEAD: `f158ea7030c5ed1b12a7557bc56792e7a7dea3e2`
- Final Ready workflows: CI `32748252045`、Full-stack `32748252047`、Local Dev `32748252050`、Windows Compose `32748252077`、Internal V1-A `32748252088`、Change Gate `32748252100`，6/6 success。
- Implementation merge commit: `c7d69a50d18acaaebd2f93a6499945e1485b1219`
- 中间归档 PR #215：closed / unmerged。
- 本文件通过独立归档 PR 移入 `changes/archive/2026-08/`。
