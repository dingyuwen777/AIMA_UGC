---
schema: rvc-change/v1
id: CHG-20260824-deepseek-pricing-effective-date
title: DeepSeek 最新价格与生效日期修复
level: L2
status: in_progress
owner: aima
branch: fix/deepseek-pricing-effective-date
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
  - tests/unit/analysis/test_llm_pricing.py
  - tests/unit/analysis/test_llm_request_audit.py
  - tests/unit/analysis/test_openai_compatible_llm.py
contracts: []
data_changes: []
---

# 目标

以 DeepSeek 官方当前价格页为唯一价格事实源，保证 `deepseek-v4-pro` 计费配置、费用计算和测试一致，并修复 `effective_date` 已配置但运行时未生效的问题。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 联网查询并使用 DeepSeek 官方最新价格 | user:2026-08-24-latest-deepseek-pricing | satisfied | 官方 `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/` 当前列出 V4-Pro：缓存命中 0.025 CNY/M、缓存未命中 3 CNY/M、输出 6 CNY/M。 |
| R2 | 修复价格代码与测试，而不是只改说明 | user:2026-08-24-latest-deepseek-pricing | not_satisfied | 待完成 effective_date 运行时约束与相关测试。 |
| R3 | 不把历史请求静默按尚未生效的新价格重算 | backend/src/aima_ugc/adapters/llm/README.md | not_satisfied | README 定义 effective_date 为 AIMA 价格目录生效日，但当前 `price_for()` 未检查。 |
| R4 | 不重新引入 DeepSeek 已取消的旧分时价格 | DeepSeek official pricing | not_satisfied | 测试中仍存在以 DeepSeek 身份承载的假分时旧价格夹具，需改为通用 synthetic provider。 |

# 成功标准

- [ ] `pricing.toml` 与官方当前人民币价格一致：0.025 / 3 / 6 CNY per 1M tokens。
- [ ] `price_for()` 不允许把配置应用到 `effective_date` 之前的请求时间。
- [ ] 价格尚未生效时，真实 LLM 请求仍可执行，但费用明确记为不可计算，不因计费元数据阻断业务请求。
- [ ] 费用复算对价格生效日前的历史审计输出 unavailable，而不是套用最新价。
- [ ] DeepSeek 正式测试只出现当前官方价格；分时选价测试改用 synthetic provider/model。
- [ ] 相关 Unit、完整 CI、Full-stack/运行门禁按当前仓库规则通过。

# 实现边界

- `effective_date` 按请求 `started_at` 的 UTC 日期比较；正式 Adapter 本身使用 UTC timestamp，历史审计要求 timezone-aware timestamp。
- 价格未生效复用 `LLMPriceNotConfiguredError` 语义，表示“该 provider/model 在该时点没有可用价格”，不新增公共 Contract。
- Adapter 捕获该计费不可用状态并继续请求，`cost_unavailable_reason` 明确记录原因。
- 不修改 DeepSeek HTTP endpoint、请求参数、Prompt、模型 ID、重试策略或 Token usage 字段解析。
- 不新增依赖，不修改数据库 Schema/Migration。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | Pricing effective_date、当前官方价格精确 Decimal、Adapter pre-effective 请求、审计复算、retry cost。 |
| Contract / Generated Client | not_applicable | 不修改 HTTP/Pydantic/JSON Schema Contract。 |
| PostgreSQL Integration | not_applicable | 不修改数据库或持久化 Schema。 |
| Browser Mock / Full-stack | not_applicable | 不修改用户页面或业务 Full-stack 接线；永久仓库门禁仍需整体通过后方可合并。 |
| Real Provider Probe | not_applicable | 官方价格通过 DeepSeek 官方文档核验；本次不需要产生真实付费 LLM 请求。 |

# TDD

- [ ] Red：新增 effective_date 前查询失败测试，并验证旧实现因仍返回价格而失败。
- [ ] Green：最小修复 pricing + Adapter unavailable 处理。
- [ ] Refactor：将 DeepSeek 假分时测试改为 synthetic provider，消除旧价混淆。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 交付

用户已授权修复代码和测试。完成后需通过当前永久 CI，再正常合并到 `main`；不得绕过门禁。