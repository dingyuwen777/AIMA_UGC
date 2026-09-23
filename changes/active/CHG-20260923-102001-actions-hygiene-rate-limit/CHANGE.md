---
schema: coding-change/v1
id: CHG-20260923-102001-actions-hygiene-rate-limit
title: Actions Hygiene 403 Rate Limit 临时错误识别
level: L3
status: ready_for_review
owner: dingyuwen777
branch: fix/actions-hygiene-rate-limit
created: 2026-09-23
updated: 2026-09-23
completion_gate: required
depends_on:
  - CHG-20260923-091500-actions-hygiene-scale
affected_areas:
  - ci
  - github-actions
  - maintenance
affected_paths:
  - scripts/quality/actions_hygiene.py
  - tests/unit/test_actions_hygiene.py
contracts:
  - GitHub Actions Hygiene transient error semantics
data_changes: []
---

# 变更摘要

- **要解决的问题**：v2 main-fresh #5534 已快速进入 Hygiene，但 GitHub 安装级 API quota 耗尽时返回 HTTP 403 + API rate limit exceeded for installation；当前脚本误判为硬失败。
- **拟议修改**：仅把具有明确 rate-limit body/header 证据的 403 识别为 transient/exit 75；普通 403 permission 继续硬失败。
- **预期结果**：限流按 maintenance best-effort warning 重试，权限/不变量缺陷仍阻塞。

# 背景、现状与问题

## 背景

Requirement Source：Issue #575。#576 建立长期 Hygiene；#578 将全仓 36k runs 扫描优化为 workflow-ID 定向扫描。#578 main-fresh CI #5534 的 Core/CI Gate Green，Actions Hygiene 在第一条 repository workflows API 请求即收到安装级 rate-limit 403。

## 当前现状

- v2 已合并 main，Change 已 archive=done。
- Runtime Acceptance #2540 Green。
- CI #5534 仅 Actions Hygiene failure。
- 当前 transient 状态未覆盖 GitHub 403 rate-limit。

## 问题、根因或约束

必须修正 rate-limit 分类，但不能把所有 403 都降级，否则 actions:write 权限问题会被隐藏。

## 不修改的后果

GitHub 安装级 quota 暂时耗尽时，产品/治理 CI 会被 maintenance 限流误伤。

# 事实与证据

| 证据 | 事实 | 来源 | 决策 |
| --- | --- | --- | --- |
| E1 | HTTP 403 body 明确 API rate limit exceeded for installation | #5534 job 107017327794 | 该 403 应 transient |
| E2 | Actions: write 权限实际存在 | #5534 job header | 此次不是权限缺失 |
| E3 | 普通 403 仍可能是权限错误 | GitHub REST 语义 | 不能宽泛吞掉所有 403 |

# 目标、成功标准与非目标

## 目标

让明确的 GitHub rate-limit 403 按 transient 处理，同时保留普通 403 fail closed。

## 成功标准

- [ ] 明确 rate-limit 403 → exit 75。
- [ ] X-RateLimit-Remaining=0 / Retry-After 等明确 header 信号也可判 transient。
- [ ] 普通 403 permission denied → exit 1。
- [ ] 429/5xx/network/404 retired 语义不回归。
- [ ] current-head CI（Ready gate 执行）/Review/merge/main-fresh/archive/#575 closure 完整闭环。

## 范围

只修改 Actions Hygiene HTTP 错误分类和测试。

## 非目标

- 不改 v2 定向扫描算法。
- 不改 CI Job 权限/trigger。
- 不新增 Workflow/Secret/依赖。

## 必须保持不变

current path、first-parent history、active skip、completed-only、per-ID readback、6 个正式 Workflow。

# 约束与意图决策

| 维度 | 决定 | 依据 |
| --- | --- | --- |
| 403 transient | 必须有 rate-limit 明确信号 | E1/E3 |
| 普通 403 | hard fail | E3 |
| wrapper | 不改，继续 exit75→warning | 既有 Contract |
| 404 retired | 不变 | v2 Contract |

# 修改方案与决策依据

## 最小充分方案

1. 新增 transient HTTP 判定 helper。
2. 429/5xx 保持 transient。
3. 403 仅在 body/header 明确 rate-limit 时 transient。
4. 单测覆盖 rate-limit 403、permission 403、429/5xx、CLI 75/1。
5. main-fresh 验证该限流场景不会再使 Hygiene 变红；若 quota 已恢复，则至少验证正常 clean-baseline JSON。

## 证据到决策

| 决策 | 依据 | 原因 |
| --- | --- | --- |
| body+header 判定 | E1/E3 | 精确覆盖限流且不吞权限错误 |
| 不改 wrapper | 现有 exit75 Contract | 降低改动面 |
| 两仓库同步 | 用户原始目标 | 避免实现漂移 |

<!-- governance:required-for=L3 -->
## 备选方案与取舍

- 所有 403 transient：过宽，拒绝。
- 所有 403 hard：真实证据否定。
- 仅 body：可用，但 body+header 更稳健。
- body+header：采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 明确 rate-limit 403 transient | #575 / AC6 | satisfied | body/header 明确信号判定与回归资产已落库 |
| R2 | 普通 permission 403 保持 hard fail | #575 / AC4 | satisfied | 普通 403 不命中 rate-limit 证据时继续 RuntimeError；负向回归已覆盖 |
| R3 | 既有 429/5xx/network/404 retired 语义不回归 | #575 / AC4 | satisfied | 429/503 回归已覆盖，404 retired 与 v2 定向算法未修改 |
| R4 | main-fresh 与 Issue closure 完整闭环 | #575 / AC8 | not_applicable | pre-merge Change 不自证未来 CI/merge/main-fresh/archive/closure；由 downstream gate 持有 |

# 计划改动

| 文件 | 修改 |
| --- | --- |
| scripts/quality/actions_hygiene.py | 精确 rate-limit 403 分类 |
| tests/unit/test_actions_hygiene.py | HTTP 分类回归 |

- [x] 调查真实 main-fresh 失败
- [x] 收敛最小方案
- [x] 完成实现
- [ ] current-head CI
- [ ] merge/main-fresh/closure

# 验证矩阵

| 层级 | 要求 |
| --- | --- |
| unit | rate-limit 403 / permission 403 / 429 / 5xx |
| repository_quality | required |
| Runtime Acceptance | 现有 trigger 决定 |
| main-fresh | Actions Hygiene success 或明确 rate-limit warning success |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 |
| --- | --- |
| 主要风险 | 过宽吞掉权限错误；用窄 rate-limit 证据规避 |
| 兼容性 | 只修临时错误分类 |
| Migration | 不适用 |
| 回滚 | 可 revert |

# 文档、依赖、部署与发布影响

无依赖、Secret、部署、Release 或长期文档结构变化。

# 完成审计

- [x] upstream_re_read：已重读 #575、#5534 真实限流日志与 current main
- [x] change_coverage：AC6 相关错误分类与不回归已覆盖；最终 AC8 downstream
- [x] reverse_audit：HTTP 403 → rate-limit 证据 → transient 75 → CI warning；普通 403 保持 hard fail
- [x] unresolved_cleared：实现侧 blocker 清零；CI/Review/post-merge 由 delivery gate 持有

# 完成证据与状态

## 新鲜证据

- V1：#5534 Actions Hygiene job 107017327794：Actions:write 已授予，但 GET /actions/workflows 返回 HTTP 403 API rate limit exceeded for installation。

## 未验证内容与剩余风险

待 current-head CI 与 main-fresh。

## 交付状态

- PR：待创建
- CI：待 Ready PR current-head
- merge/archive/#575 closure：未执行
