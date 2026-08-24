---
schema: rvc-change/v1
id: CHG-20260824-deepseek-official-pricing-correction
title: 修正 DeepSeek V4-Pro 官方分时价格
level: L2
status: in_progress
owner: aima
branch: fix/deepseek-official-pricing-correction
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

纠正 AIMA 当前 `deepseek-v4-pro` 价格事实，使价格目录、选价实现和测试与 DeepSeek 官方当前“空闲/高峰 + 工作日”计费规则一致，同时保留上一 Change 已实现的 `effective_date` 时点约束。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 联网查询 DeepSeek 官方最新价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | not_satisfied | 官方页面已核验，待实现当前分时价格。 |
| R2 | deepseek-v4-pro 使用官方当前空闲/高峰单价 | user:2026-08-24-latest-deepseek-pricing | not_satisfied | 待将 TOML 从错误全天价改为官方分时价。 |
| R3 | 高峰价仅适用于北京时间周一至周五 09:00-12:00、14:00-18:00 | user:2026-08-24-latest-deepseek-pricing | not_satisfied | 当前 parser 只有 time_ranges，没有 weekday 条件。 |
| R4 | 保留 effective_date，不能把未来目录价格套到更早请求 | backend/src/aima_ugc/adapters/llm/README.md | satisfied | 上一修复已由 `price_for(..., at=...)` 执行 effective_date，本次不得回退。 |

# 官方事实（2026-08-24 核验）

DeepSeek 官方 `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/` 当前对 `deepseek-v4-pro`：

- 输入缓存命中：空闲 `0.15`、高峰 `0.30` CNY / 百万 tokens；
- 输入缓存未命中：空闲 `4.5`、高峰 `9.0` CNY / 百万 tokens；
- 输出：空闲 `13.5`、高峰 `27.0` CNY / 百万 tokens；
- 高峰时段：北京时间周一至周五 `09:00-12:00`、`14:00-18:00`，其余为空闲时段。

# 成功标准

- [ ] `pricing.toml` 使用 `Asia/Shanghai`，默认空闲价与工作日高峰价均与官方一致。
- [ ] price period 支持可选 weekday 条件；不配置 weekday 的现有 period 继续每天适用。
- [ ] 工作日 09:00 北京时间命中 peak，工作日 08:00 命中 off-peak；周末 09:00 仍命中 off-peak。
- [ ] DeepSeek 正式 Unit/Audit/Retry 成本测试全部改为当前官方价格。
- [ ] `effective_date = 2026-08-24` 继续阻止更早请求使用这份 AIMA 价格快照。
- [ ] 目标测试与当前永久 CI 全绿后正常合并 main。

# 实现边界

- `weekdays` 只作为内部 TOML 价格目录字段，不改 HTTP/Pydantic/数据库 Contract。
- `weekdays` 未配置表示周一至周日都适用；配置时使用 `mon/tue/wed/thu/fri/sat/sun`。
- weekday 按 price schedule 的 IANA timezone 转换后的**本地日历日**判断。
- 不修改 DeepSeek endpoint、模型 ID、请求体、usage 字段、Prompt、重试策略或数据库。
- 不新增依赖。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | 官方 off-peak/peak/weekend、边界解析、审计成本、retry cost、effective_date 回归。 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract。 |
| PostgreSQL Integration | not_applicable | 无数据库变化；最终仓库 CI 仍作为回归。 |
| Browser Mock / Full-stack | not_applicable | 无 UI/业务接线变化；永久 Full-stack 仍作为仓库级回归。 |
| Real Provider Probe | not_applicable | 价格事实直接核验官方文档，不需要产生付费 LLM 请求。 |

# TDD

- [ ] Red：新增官方分时价格测试，当前错误全天价应失败。
- [ ] Green：最小增加 weekday schedule 条件并修正 pricing TOML。
- [ ] Refactor：同步既有 DeepSeek 成本断言和 README，保持 synthetic schedule 测试独立。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 交付

用户已授权修复代码、测试并继续合并到 main。最终必须通过当前永久门禁，随后独立归档 Change。