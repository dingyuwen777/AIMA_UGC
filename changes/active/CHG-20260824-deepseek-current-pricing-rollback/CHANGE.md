---
schema: rvc-change/v1
id: CHG-20260824-deepseek-current-pricing-rollback
title: 回滚错误分时价格并恢复 DeepSeek 当前官方价
level: L2
status: ready_for_review
owner: aima
branch: fix/deepseek-official-current-pricing
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
| R2 | 不保留与当前官方事实不一致的分时价格/weekday 逻辑 | user:2026-08-24-latest-deepseek-pricing | satisfied | 精确恢复 PR #212 第一父 `d6828e22...` 的代码树；`pricing.py` 不再包含 #212 新增 weekday schedule/parser/overlap 逻辑，错误分时专项测试已移除。 |
| R3 | 保留已验证的 effective_date 时点约束 | backend/src/aima_ugc/adapters/llm/README.md | satisfied | 恢复树来自 PR #210 完成并归档后的 `d6828e22...`；`price_for(..., at=...)`、Adapter cost-unavailable 和历史复算保护均保留，CI 621 Unit 全绿。 |
| R4 | 错误分时 Change 不得继续作为当前 Active 正确事实 | AGENTS.md | satisfied | PR #213 已关闭且未合并；本分支移除 `CHG-20260824-deepseek-official-pricing-correction` Active Change，并由当前纠错 Change 记录替代。 |

# 官方事实（最终复核）

DeepSeek 官方当前页面列出的 `deepseek-v4-pro` 人民币价格：

- 百万 tokens 输入（缓存命中）：`0.025 CNY`；
- 百万 tokens 输入（缓存未命中）：`3 CNY`；
- 百万 tokens 输出：`6 CNY`；
- 官方当前价格页未列出该模型的分时价格或工作日高峰规则。

# 成功标准

- [x] `pricing.toml` 恢复为 `0.025 / 3 / 6` CNY/百万 tokens 的全天配置。
- [x] 撤销 PR #212 新增的 weekday schedule/parser/overlap 逻辑，不保留无当前需求依据的复杂度。
- [x] DeepSeek 正式 Unit/Audit/Retry 成本测试恢复当前官方全天价；删除错误分时价格专项测试。
- [x] PR #210 的 `effective_date` 代码、Adapter cost-unavailable 行为和历史复算保护保持不变。
- [x] 错误 `CHG-20260824-deepseek-official-pricing-correction` 不再留在本分支 `changes/active/`。
- [x] 代码候选的 CI、Full-stack、Local Dev、Windows Compose、Internal V1-A 已全部通过；Ready 状态再由 Completion Gate 复验后按用户授权合并 `main`。

# 实现策略

采用精确树回滚而不是手工反向编辑：以 PR #212 合并前的第一父 `d6828e22bf408bfd2c05228f4614dd74991b5ff7` 作为代码/测试/README 事实基线，再只新增本 Change。这样完整撤销 #212 的 8 个文件差异，同时保留 #210 已验证的 effective_date 修复和其归档事实。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | CI `32745471740` / Repository Quality `97489832078`：621 Unit、75 Contract、34 API 全部通过；Ruff、mypy、Architecture/Owner、Secret/docs、Wheel 也通过。DeepSeek 当前价、精确 Decimal cost、effective_date、Adapter audit/retry cost 均由恢复后的既有正式测试覆盖。 |
| Contract / Generated Client | not_applicable | 不修改公共 HTTP/Pydantic/JSON Schema Contract；CI generated Contract/Orval drift 与兼容检查额外通过。 |
| PostgreSQL Integration | not_applicable | 不修改数据库；CI `32745471740` PostgreSQL Integration 全部成功，包含空库升级、历史 Migration、Platform/Job/Collection/Content/Ingestion。 |
| Browser Mock / Full-stack | not_applicable | 无 UI/业务接线变化；仓库级回归额外通过 39 Vitest、22 Browser Mock Playwright，Full-stack Acceptance `32745471864` 成功。 |
| Real Provider Probe | not_applicable | 价格事实直接来自 DeepSeek 官方价格页，无需产生付费模型请求；本次不修改 Provider HTTP 协议。 |
| Runtime / Deployment Regression | required | Local Dev `32745471699`、Windows Compose `32745471689`、Internal V1-A `32745471783` 均成功。 |

# TDD / Regression Evidence

- 外部事实 Red：官方当前页面与 `main 8deae122...` 的 `pricing.toml` 分时价直接冲突；当前 main 是可观察失败状态。
- 回滚目标：`d6828e22...` 是 #212 第一父，也是 #210 完成并归档后的已验证树；恢复该树同时撤销错误分时价格与无依据 weekday 逻辑。
- Green：候选 HEAD `ebbf74591b267b5b948806e4f264d8947bd244cb` 上 CI `32745471740` 成功；Repository Quality 为 621 Unit / 75 Contract / 34 API / 39 Vitest / 22 Browser Mock Playwright，全绿；Full-stack、Local Dev、Windows Compose、Internal V1-A 也成功。

# Completion Audit

- [x] upstream_re_read：重新读取当前 main `AGENTS.md`、RVC Change/Completion 规则、LLM Pricing 机器配置/实现/README/测试，并在归档前再次直接核验 DeepSeek 官方当前价格页面。
- [x] change_coverage：用户要求“联网查最新价格、修复代码和测试、合并 main”已映射到官方价格事实、TOML、pricing 实现、正式成本测试、错误 Change 清理与 Git 交付。
- [x] reverse_audit：配置→`LLMPricingCatalog.price_for()`→Adapter→request audit/recalculation 两条价格消费者链均恢复 PR #210 已验证语义；不再存在仅为错误分时事实服务的 weekday 调度。
- [x] unresolved_cleared：R1—R4 全部 satisfied；PR #213 已关闭；候选代码 5 个非 Change 永久 workflow 全绿，剩余只需 Ready 状态 Completion Gate 复验。

# Review

## Correctness / Scope

- 当前官方中文价格页明确列出 `deepseek-v4-pro` 为 `0.025 / 3 / 6 CNY / 百万 tokens`，未列当前分时价。
- 实现使用精确树恢复，避免手工反改漏掉 #212 某个 parser/test/doc 片段。
- 不修改 DeepSeek endpoint、模型 ID、请求体、Prompt、usage 字段、重试策略、数据库、公共 Contract 或依赖。

## Reliability / Compatibility

- PR #210 的 `effective_date` 保护保留：早于 2026-08-24 的请求不会套用这份 AIMA 价格目录；在线 LLM 请求仍不因 cost unavailable 被阻断。
- legacy `price_periods` 能力本身仍存在；只撤销 #212 为错误事实新增的 weekday 扩展，因此其他 synthetic 分时测试与既有能力保持兼容。
- 无 Migration/部署顺序变化；整体 revert 本纠错 PR 会重新引入已被官方当前页面否定的价格事实，不建议回滚，除非官方价格再次变化。

# 交付

- 分支：`fix/deepseek-official-current-pricing`
- PR：#214（Draft → Ready 前置完成；Completion Gate 复验后按用户授权正常合并）
- 候选 HEAD：`ebbf74591b267b5b948806e4f264d8947bd244cb`
- PR #213：closed / unmerged。
- 用户已授权继续修复并合并到 `main`。
