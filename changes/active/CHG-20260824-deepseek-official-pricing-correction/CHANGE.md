---
schema: rvc-change/v1
id: CHG-20260824-deepseek-official-pricing-correction
title: 修正 DeepSeek V4-Pro 官方分时价格
level: L2
status: ready_for_review
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
| R1 | 联网查询 DeepSeek 官方最新价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | satisfied | 2026-08-24 重新核验官方 `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/`；当前分时单价与工作日窗口已同步到机器配置、实现、测试和 README。 |
| R2 | deepseek-v4-pro 使用官方当前空闲/高峰单价 | user:2026-08-24-latest-deepseek-pricing | satisfied | `pricing.toml` 已配置 off_peak `0.15/4.5/13.5` 与 peak `0.30/9.0/27.0` CNY/百万 tokens，`Asia/Shanghai`。 |
| R3 | 高峰价仅适用于北京时间周一至周五 09:00-12:00、14:00-18:00 | user:2026-08-24-latest-deepseek-pricing | satisfied | price period 新增可选 `weekdays`；DeepSeek peak 使用 `mon..fri`，Unit 验证工作日 peak/off-peak 与周末 off-peak。 |
| R4 | 保留 effective_date，不能把未来目录价格套到更早请求 | backend/src/aima_ugc/adapters/llm/README.md | satisfied | `price_for(..., at=...)` 的 effective_date 约束保留，既有 effective-date Unit 纳入完整价格回归。 |

# 官方事实（2026-08-24 核验）

DeepSeek 官方当前对 `deepseek-v4-pro`：

- 输入缓存命中：空闲 `0.15`、高峰 `0.30` CNY / 百万 tokens；
- 输入缓存未命中：空闲 `4.5`、高峰 `9.0` CNY / 百万 tokens；
- 输出：空闲 `13.5`、高峰 `27.0` CNY / 百万 tokens；
- 高峰时段：北京时间周一至周五 `09:00-12:00`、`14:00-18:00`，其余为空闲时段。

# 成功标准

- [x] `pricing.toml` 使用 `Asia/Shanghai`，默认空闲价与工作日高峰价均与官方一致。
- [x] price period 支持可选 weekday 条件；不配置 weekday 的现有 period 继续每天适用。
- [x] 工作日 09:00 北京时间命中 peak，工作日 08:00 命中 off-peak；周末 09:00 仍命中 off-peak。
- [x] DeepSeek 正式 Unit/Audit/Retry 成本测试全部改为当前官方价格。
- [x] `effective_date = 2026-08-24` 继续阻止更早请求使用这份 AIMA 价格快照。
- [x] 目标测试、Ruff、mypy 已通过；最终合并仍以当前永久 CI 为门禁。

# 实现边界

- `weekdays` 只作为内部 TOML 价格目录字段，不改 HTTP/Pydantic/数据库 Contract。
- `weekdays` 未配置表示周一至周日都适用；配置时使用 `mon/tue/wed/thu/fri/sat/sun`，非法值与重复值 fail-fast。
- weekday 按 price schedule 的 IANA timezone 转换后的本地日历日判断；重叠检查按 weekday + 本地时间段执行。
- 不修改 DeepSeek endpoint、模型 ID、请求体、usage 字段、Prompt、重试策略或数据库。
- 不新增依赖。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | Red CI `32742941803` / Repository Quality `97481491532`：3 条官方价格测试失败、其余 621 Unit 通过；Focused Green `32743351928` 验证官方 weekday 调度；Complete Pricing Green `32743731463` 验证 pricing/effective-date/Adapter/request-audit、Ruff、mypy 全部成功。 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract。 |
| PostgreSQL Integration | not_applicable | 无数据库变化；最终仓库 CI 仍作为回归。 |
| Browser Mock / Full-stack | not_applicable | 无 UI/业务接线变化；永久 Full-stack 仍作为仓库级回归。 |
| Real Provider Probe | not_applicable | 价格事实直接核验官方文档，不需要产生付费 LLM 请求；本次不改 Provider HTTP 协议。 |

# TDD Evidence

- Red：CI run `32742941803`，新增三条官方价格用例全部失败，精确结果 `3 failed, 621 passed`；失败均为当前错误 `Decimal('0.025')` 与官方 off-peak/peak 期望不一致。
- Green 1：run `32743351928`，新增 weekday 价格调度、DeepSeek TOML 后，工作日 08:00/09:00 与周末 09:00 三条目标用例、Ruff、mypy 全部通过。
- Green 2 / Refactor：run `32743731463`，同步全部 DeepSeek 正式成本断言与 README；分时测试中的 synthetic 场景继续使用 `llm.example`，完整相关 Pricing/Adapter/Audit/effective-date 套件、Ruff、mypy 全绿。

# Completion Audit

- [x] upstream_re_read：重新读取当前 main `AGENTS.md`、RVC Skill/change/development 规则、LLM Pricing 实现/TOML/README/测试，并重新核验 DeepSeek 官方当前价格页。
- [x] change_coverage：官方三组单价、北京时间、工作日两个高峰窗口、周末 off-peak、effective_date 均映射到机器配置/实现/测试。
- [x] reverse_audit：配置→parser→local timezone/weekday→price selection→Adapter/audit cost 两条消费者链均复核；未配置 weekdays 的既有 synthetic period 继续每天适用。
- [x] unresolved_cleared：R1—R4 均 satisfied；临时实施/测试 workflow 均已删除，无未解释延期或未满足项。

# Review

## Correctness / Scope

- 修复的是价格机器事实和其必要的 weekday 选价能力；不改 LLM 请求业务语义。
- 默认 `off_peak` 作为无 `time_ranges` 的 fallback，工作日 peak 显式优先；周末同一时钟时间正确回落 default。
- 旧错误全天 `0.025/3/6` 不再作为 DeepSeek 正式价格事实；synthetic parser 兼容测试不冒用 DeepSeek 官方身份。

## Reliability / Compatibility

- `weekdays` 是可选字段，未配置时行为与既有 time_ranges 完全一致。
- existing effective_date、Decimal 成本、审计快照、Provider usage 和 error 语义保持不变。
- 无 Schema/Migration、公共 Contract、依赖或部署顺序变化；整体 revert 即可回滚。

# 交付

- 分支：`fix/deepseek-official-pricing-correction`
- PR：#212（Draft，最终永久 CI 全绿后转 Ready 并按用户授权合并 main）
- 未执行生产部署。
