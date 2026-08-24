---
schema: rvc-change/v1
id: CHG-20260824-deepseek-pricing-effective-date
title: DeepSeek 最新价格与生效日期修复
level: L2
status: ready_for_review
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
  - backend/src/aima_ugc/adapters/llm/openai_compatible.py
  - backend/src/aima_ugc/adapters/llm/pricing.toml
  - backend/src/aima_ugc/adapters/llm/README.md
  - tests/unit/analysis/test_llm_pricing.py
  - tests/unit/analysis/test_llm_pricing_effective_date.py
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
| R1 | 联网查询并使用 DeepSeek 官方最新价格 | user:2026-08-24-latest-deepseek-pricing | satisfied | 2026-08-24 核验官方 `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/`：V4-Pro 缓存命中 0.025 CNY/M、缓存未命中 3 CNY/M、输出 6 CNY/M；官方当前页未列分时价格。 |
| R2 | 修复价格代码与测试，而不是只改说明 | user:2026-08-24-latest-deepseek-pricing | satisfied | `pricing.py` 执行 effective_date；Adapter 非阻断处理价格未生效；新增三条时点测试并清理旧 DeepSeek 假分时夹具。 |
| R3 | 不把历史请求静默按尚未生效的新价格重算 | backend/src/aima_ugc/adapters/llm/README.md | satisfied | `price_for()` 对请求 UTC 日期早于 effective_date 抛 `LLMPriceNotConfiguredError`；复算测试验证请求进入 uncalculated。 |
| R4 | 不重新引入 DeepSeek 已取消的旧分时价格 | user:2026-08-24-latest-deepseek-pricing | satisfied | 分时选价与费用复算测试已改为 `llm.example/model-a` synthetic catalog；仓库搜索不存在 `api.deepseek.com` 与旧 0.15/4.5 分时价绑定。 |

# 成功标准

- [x] `pricing.toml` 与官方当前人民币价格一致：0.025 / 3 / 6 CNY per 1M tokens。
- [x] `price_for()` 不允许把配置应用到 `effective_date` 之前的请求时间。
- [x] 价格尚未生效时，真实 LLM 请求仍可执行，但费用明确记为不可计算，不因计费元数据阻断业务请求。
- [x] 费用复算对价格生效日前的历史审计输出 unavailable，而不是套用最新价。
- [x] DeepSeek 正式测试只使用当前官方价格；分时选价测试改用 synthetic provider/model。
- [x] 目标 Unit、Ruff、mypy 已通过；最终合并仍以本 HEAD 的永久 CI 为门禁。

# 实现边界

- `effective_date` 按请求 `started_at` 的 UTC 日期比较；正式 Adapter 本身使用 UTC timestamp，历史审计要求 timezone-aware timestamp。
- 价格未生效复用 `LLMPriceNotConfiguredError` 语义，表示“该 provider/model 在该时点没有可用价格”，不新增公共 Contract。
- Adapter 捕获该计费不可用状态并继续请求，`cost_unavailable_reason = price_not_effective_at_request_time`。
- 不修改 DeepSeek HTTP endpoint、请求参数、Prompt、模型 ID、重试策略或 Token usage 字段解析。
- 不新增依赖，不修改数据库 Schema/Migration。
- `pricing.toml` 数值在本任务开始时已与官方当前值一致；本任务只补充 effective_date 注释，没有为了制造差异改写相同数值。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | Red run `32736326648`：新 effective_date 测试 `DID NOT RAISE`，618 个既有 unit 通过；Targeted Green run `32737727425`：pricing/effective-date/Adapter/request-audit 目标套件、Ruff、mypy 全部成功。 |
| Contract / Generated Client | not_applicable | 不修改 HTTP/Pydantic/JSON Schema Contract。 |
| PostgreSQL Integration | not_applicable | 不修改数据库或持久化 Schema；永久 CI 仍运行现有 PostgreSQL Integration 防回归。 |
| Browser Mock / Full-stack | not_applicable | 不修改用户页面或业务 Full-stack 接线；永久 Full-stack/Runtime 仍作为仓库级回归门禁。 |
| Real Provider Probe | not_applicable | 价格事实通过 DeepSeek 官方文档核验；无需产生真实付费 LLM 请求，且本次不改 Provider HTTP 协议。 |

# TDD Evidence

- Red：CI run `32736326648`，`test_deepseek_current_price_is_not_available_before_effective_date` 因旧实现未抛异常而失败；结果 `1 failed, 618 passed`。
- Green 第一次实验：run `32736961514` 暴露费用 unavailable 原因仍传旧字段；LLM 请求本身已成功，证明非阻断边界正确，随后修正 `_calculate_cost()` 使用本次请求局部原因。
- Green：run `32737727425` 完整目标套件、Ruff 与 mypy 全部通过并提交生产实现。
- Refactor：DeepSeek 假分时测试改成 synthetic `llm.example/model-a`；DeepSeek 正式价格事实只保留官方当前全天价 0.025 / 3 / 6。

# Completion Audit

- [x] upstream_re_read：已重新读取当前 main `AGENTS.md`、RVC Skill/development workflow、LLM README、pricing TOML/实现/审计/Adapter 与直接相关测试，并核对 DeepSeek 官方当前价格页。
- [x] change_coverage：R1—R4 均映射到机器配置、effective_date 代码、Adapter 行为、审计复算、测试和 README，均为 satisfied。
- [x] reverse_audit：在线 Adapter 与离线 audit recalculation 两个价格消费者都经过 `price_for(..., at=...)` 时点约束；价格未生效不会阻断 LLM HTTP 请求，也不会形成伪费用。
- [x] unresolved_cleared：目标 Green 已通过；临时实施 workflow 已删除；剩余仅为最终永久 CI/Ready/merge 的外部门禁。

# Review

## Correctness / Scope

- 官方当前 CNY 单价与 `pricing.toml` 完全一致，无需修改数值。
- `effective_date` 从“仅解析/展示”变成真正运行时约束，修复历史请求套用未来价的逻辑缺陷。
- 没有修改价格公式、Provider 协议、Token usage、Prompt、模型 ID、重试或数据库。

## Reliability / Compatibility

- Legacy 未配置 effective_date 的旧价格对象仍保持可用，不破坏兼容路径。
- 带 effective_date 的价格要求调用方提供 timezone-aware `at`；正式 Adapter 和审计记录均满足。
- 价格时点不可用使用已有 `LLMPriceNotConfiguredError`，在线请求降级为 cost unavailable，离线复算记录 unavailable，不猜测价格。

# 交付

- 分支：`fix/deepseek-pricing-effective-date`
- PR：#210，当前为 Draft；最终永久 CI 全绿后再转 Ready/合并。
- 回滚：纯 Python/TOML/测试/README 变更，无数据库 Migration；整体 revert 即可。