---
schema: rvc-change/v1
id: CHG-20260824-deepseek-current-pricing-rollback
title: 回滚错误分时价格并恢复 DeepSeek 当前官方价
level: L2
status: in_progress
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
| R1 | 联网查询 DeepSeek 最新官方价格并据此修复代码和测试 | user:2026-08-24-latest-deepseek-pricing | not_satisfied | 2026-08-24 最终重新核验官方 `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/`：V4-Pro 当前为缓存命中 0.025、缓存未命中 3、输出 6 CNY/百万 tokens；待恢复机器实现。 |
| R2 | 不保留与当前官方事实不一致的分时价格/weekday 逻辑 | user:2026-08-24-latest-deepseek-pricing | not_satisfied | PR #212 引入的 `weekdays` 与 off_peak/peak 当前无官方依据，必须整体撤销。 |
| R3 | 保留已验证的 effective_date 时点约束 | backend/src/aima_ugc/adapters/llm/README.md | not_satisfied | 应恢复到 PR #212 第一父 `d6828e22...` 的代码树；该树已包含 PR #210 的 effective_date 修复。 |
| R4 | 错误分时 Change 不得继续作为当前 Active 正确事实 | AGENTS.md | not_satisfied | PR #213 已关闭且未合并；纠错实现需移除错误 Active Change，后续归档记录其被回滚事实。 |

# 官方事实（最终复核）

DeepSeek 官方当前页面列出的 `deepseek-v4-pro` 人民币价格：

- 百万 tokens 输入（缓存命中）：`0.025 CNY`；
- 百万 tokens 输入（缓存未命中）：`3 CNY`；
- 百万 tokens 输出：`6 CNY`；
- 官方当前价格页未列出该模型的分时价格或工作日高峰规则。

# 成功标准

- [ ] `pricing.toml` 恢复为 `0.025 / 3 / 6` CNY/百万 tokens 的全天配置。
- [ ] 撤销 PR #212 新增的 weekday schedule/parser/overlap 逻辑，不保留无当前需求依据的复杂度。
- [ ] DeepSeek 正式 Unit/Audit/Retry 成本测试恢复当前官方全天价；删除错误分时价格专项测试。
- [ ] PR #210 的 `effective_date` 代码、Adapter cost-unavailable 行为和历史复算保护保持不变。
- [ ] 错误 `CHG-20260824-deepseek-official-pricing-correction` 不再留在 `changes/active/`。
- [ ] 当前永久 CI 全绿后按用户授权正常合并 `main`，随后独立归档本纠错 Change，并在历史记录中注明 PR #212 已被纠正。

# 实现策略

采用精确树回滚而不是手工反向编辑：以 PR #212 合并前的第一父 `d6828e22bf408bfd2c05228f4614dd74991b5ff7` 作为代码/测试/README 事实基线，再只新增本 Change。这样完整撤销 #212 的 8 个文件差异，同时保留 #210 已验证的 effective_date 修复和其归档事实。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Backend Unit | required | DeepSeek 当前官方价、精确 Decimal cost、effective_date、Adapter audit/retry cost。 |
| Contract / Generated Client | not_applicable | 不修改公共 HTTP/Pydantic/JSON Schema Contract。 |
| PostgreSQL Integration | not_applicable | 不修改数据库；永久 CI 仍运行 PostgreSQL Integration 防回归。 |
| Browser Mock / Full-stack | not_applicable | 无 UI/业务接线变化；永久 Full-stack 作为仓库级回归门禁。 |
| Real Provider Probe | not_applicable | 价格事实直接来自 DeepSeek 官方价格页，无需产生付费模型请求。 |

# TDD / Regression Evidence

- 外部事实 Red：官方当前页面与 `main 8deae122...` 的 `pricing.toml` 分时价存在直接冲突；因此当前 main 本身即为可观察失败状态。
- 回滚目标：`d6828e22...` 是 #212 第一父，也是 #210 完成并归档后的已验证树；恢复该树可同时撤销错误分时价格与无依据 weekday 逻辑。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 兼容与回滚

- 无 Schema/Migration、公共 Contract、依赖或 Provider HTTP 协议变化。
- `effective_date` 保持不变；只撤销错误价格事实和其专用调度扩展。
- 若本纠错需要回滚，可 revert 本 PR；但这会重新引入已被官方当前页面否定的分时价格，因此除非外部价格事实再次变化，不应回滚。

# 交付

- 分支：`fix/deepseek-official-current-pricing`
- 用户已授权继续修复并合并到 `main`。
- PR #213 已关闭且未合并，不再归档错误分时 Change 为最终正确状态。
