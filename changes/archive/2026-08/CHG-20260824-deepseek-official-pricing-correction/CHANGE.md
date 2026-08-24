---
schema: rvc-change/v1
id: CHG-20260824-deepseek-official-pricing-correction
title: 修正 DeepSeek V4-Pro 官方分时价格
level: L2
status: done
owner: aima
branch: archive/deepseek-official-pricing-correction
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

纠正 AIMA `deepseek-v4-pro` 价格事实，使价格目录、选价实现和测试与 DeepSeek 官方当前“空闲/高峰 + 工作日”计费规则一致，同时保留 `effective_date` 时点约束。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 联网查询 DeepSeek 官方最新价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | satisfied | 2026-08-24 重新核验官方价格页；分时单价与工作日窗口已同步到机器配置、实现、测试和 README。 |
| R2 | deepseek-v4-pro 使用官方当前空闲/高峰单价 | user:2026-08-24-latest-deepseek-pricing | satisfied | `pricing.toml` 配置 off_peak `0.15/4.5/13.5` 与 peak `0.30/9.0/27.0` CNY/百万 tokens，时区 `Asia/Shanghai`。 |
| R3 | 高峰价仅适用于北京时间周一至周五 09:00-12:00、14:00-18:00 | user:2026-08-24-latest-deepseek-pricing | satisfied | price period 新增可选 `weekdays`；DeepSeek peak 使用 `mon..fri`，Unit 验证工作日 peak/off-peak 与周末 off-peak。 |
| R4 | 保留 effective_date，不能把未来目录价格套到更早请求 | backend/src/aima_ugc/adapters/llm/README.md | satisfied | `price_for(..., at=...)` 的 effective_date 约束保留并通过相关回归测试。 |

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
- [x] Implementation PR 已通过永久 CI 并正常合并到 main。

# 实现边界

- `weekdays` 只作为内部 TOML 价格目录字段，不改 HTTP/Pydantic/数据库 Contract。
- `weekdays` 未配置表示周一至周日都适用；配置时使用 `mon/tue/wed/thu/fri/sat/sun`，非法值与重复值 fail-fast。
- weekday 按 price schedule 的 IANA timezone 转换后的本地日历日判断；重叠检查按 weekday + 本地时间段执行。
- 不修改 DeepSeek endpoint、模型 ID、请求体、usage 字段、Prompt、重试策略或数据库；不新增依赖。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | Red CI `32742941803` / job `97481491532`：3 条官方价格测试失败、其余 621 Unit 通过；Focused Green `32743351928`；Complete Pricing Green `32743731463`；最终 CI `32743995899` 成功。 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract。 |
| PostgreSQL Integration | not_applicable | 无数据库变化；最终 CI PostgreSQL Integration 作为仓库级回归成功。 |
| Browser Mock / Full-stack | not_applicable | 无 UI/业务接线变化；最终 Full-stack Acceptance `32743995826` 成功。 |
| Real Provider Probe | not_applicable | 价格事实直接核验官方文档，不需要产生付费 LLM 请求；本次不改 Provider HTTP 协议。 |

# TDD Evidence

- Red：CI run `32742941803`，新增三条官方价格用例全部失败，结果 `3 failed, 621 passed`；失败均为错误 `Decimal('0.025')` 与官方 off-peak/peak 期望不一致。
- Green 1：run `32743351928`，新增 weekday 价格调度和 DeepSeek TOML 后，工作日 08:00/09:00 与周末 09:00 三条目标用例、Ruff、mypy 全部通过。
- Green 2 / Refactor：run `32743731463`，同步全部 DeepSeek 正式成本断言与 README，Pricing/Adapter/Audit/effective-date 套件、Ruff、mypy 全绿。

# Completion Audit

- [x] upstream_re_read：重新读取当前 main `AGENTS.md`、RVC 规则、LLM Pricing 实现/TOML/README/测试，并重新核验 DeepSeek 官方当前价格页。
- [x] change_coverage：官方三组单价、北京时间、工作日两个高峰窗口、周末 off-peak、effective_date 均映射到机器配置/实现/测试。
- [x] reverse_audit：配置→parser→local timezone/weekday→price selection→Adapter/audit cost 两条消费者链均复核；未配置 weekdays 的既有 synthetic period 继续每天适用。
- [x] unresolved_cleared：R1—R4 均 satisfied；临时 workflow 已删除，最终永久门禁与实现合并完成。

# Review

## Correctness / Scope

- 修复价格机器事实和其必要的 weekday 选价能力，不改 LLM 请求业务语义。
- 默认 `off_peak` 为 fallback，工作日 peak 显式优先；周末同一时钟时间回落 default。
- 旧错误全天 `0.025/3/6` 不再作为 DeepSeek 正式价格事实；synthetic parser 测试不冒用 DeepSeek 官方身份。

## Reliability / Compatibility

- `weekdays` 为可选字段，未配置时行为与既有 time_ranges 保持一致。
- existing effective_date、Decimal 成本、审计快照、Provider usage 和 error 语义保持不变。
- 无 Schema/Migration、公共 Contract、依赖或部署顺序变化；整体 revert Implementation PR 即可回滚。

# 最终验证与交付

- Implementation branch：`fix/deepseek-official-pricing-correction`
- Implementation PR：#212
- Final Ready HEAD：`26ce5209350ee514e48553f15964165ae2fe3d63`
- Final main base：`d6828e22bf408bfd2c05228f4614dd74991b5ff7`，合并前 `behind_by=0`
- Final permanent workflows 6/6 success：CI `32743995899`、Full-stack Acceptance `32743995826`、Local Dev Bootstrap `32743995820`、Windows Docker Desktop Compose Compatibility `32743995802`、Internal V1-A Deployable Stack `32743995792`、Change Completion Gate `32743995793`
- Implementation merge commit：`8deae122b94d613868cd8000512f96ed43917691`
- 未执行生产部署。
- Archive branch：`archive/deepseek-official-pricing-correction`
- 本文件通过独立归档 PR 从 `changes/active/` 移入 `changes/archive/2026-08/`；归档门禁通过后正常合并。
