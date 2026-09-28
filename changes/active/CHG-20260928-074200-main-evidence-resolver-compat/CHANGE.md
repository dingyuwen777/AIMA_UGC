---
schema: coding-change/v1
id: CHG-20260928-074200-main-evidence-resolver-compat
title: 修复主分支Evidence Resolver兼容与失败降级
level: L2
status: proposed
owner: dingyuwen777
branch: fix/636-main-evidence-resolver-compat
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on:
  - CHG-20260928-001000-ci-evidence-optimization
affected_areas:
  - ci
  - testing
  - github-actions
affected_paths:
  - scripts/quality/resolve_main_evidence.py
  - .github/workflows/ci.yml
  - .github/workflows/runtime.yml
  - .github/workflows/tooling.yml
  - tests/unit/test_ci_main_evidence_reuse.py
  - tests/unit/test_ci_workflow_structure.py
  - docs/04_测试与调试说明.md
contracts: []
data_changes: []
---

# 变更摘要

- 要解决的问题：PR #637 合并后，main 的 CI / Runtime / Tooling 在 Evidence Resolver 启动阶段因系统 Python 不接受无括号多异常语法而直接失败，未进入设计好的 fail-closed 回退。
- 拟议修改：恢复 bootstrap Python 兼容语法；在三个 workflow 中把 Resolver 进程自身失败降级为 reusable=false，继续原 changed-scope / Runtime / Tooling 真实验证；增加 system-python compile 门禁与结构回归。
- 预期结果：main 同 tree 时正常复用；Resolver 查询、执行或兼容性异常时只关闭复用，不把优化控制面本身变成阻断 main 的单点故障。

# 背景、现状与问题

## 背景

Issue #636 / AC7 要求 merge 后 main 的实际 Evidence Reuse 行为成立。PR #637 的最终 HEAD 绿色后合并，merge tree 与 PR tree 完全一致，但首次 main 运行暴露 Resolver bootstrap 兼容缺陷。

## 当前现状

- merge commit 883a580bed0ceacf1ee4b1dc0c06b3545586b513 与 PR HEAD 997a46cb28b92da16f9d7cf276297efe67a1a5a6 的 tree SHA 均为 4e86130bf6a3bb8a5df2b049c17c2d3a8ffb6e1f。
- resolve_main_evidence.py 使用无括号多异常 except。PR Core 使用 Python 3.14.7；main Resolver 在 actions/setup-python 之前用 Runner 系统 python3 执行并 SyntaxError。
- CI / Runtime / Tooling Resolver step 当前直接 set -e 执行脚本；脚本若在启动/解析阶段失败，workflow 自身失败。

## 问题、根因或约束

根因有两层：控制面脚本使用了比 bootstrap Runtime 更新的语法；workflow 只覆盖“脚本成功返回 reusable=false”，没有覆盖“脚本自身无法执行”的更上游失败模式。永久修复必须同时切断两条复发路径。

## 不修改的后果

main 会持续在 Resolver step 失败；CI Gate / Compose Golden Path 无法取得 post-merge 绿色 Evidence，Issue #636 / AC7 无法闭合。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 | 支撑决策 |
| --- | --- | --- | --- |
| E1 | merge tree 与 PR tree 相同 | GitHub Commit API | Evidence Reuse 前提成立 |
| E2 | main CI、Runtime、Tooling Resolver 均在同一语法行失败 | GitHub Actions job logs | 共同根因是 bootstrap 语法兼容 |
| E3 | PR Core 使用 Python 3.14.7，而 Resolver 在 setup-python 前用系统 python3 | workflow + logs | 必须显式验证 bootstrap Python |
| E4 | Resolver 进程失败会被 set -e 直接终止 Job | 三个 workflow | fail-closed 必须覆盖进程级失败 |
| E5 | Issue #636 已重新打开且 AC7 未完成 | Issue #636 | 本 Change 属于原 Requirement 的 post-merge closure |

## 推断与待确认

无。

# 目标、成功标准与非目标

## 目标

恢复 Evidence Reuse 控制面的可执行性和真正 fail-closed 语义，并完成 Issue #636 / AC7 的 main 实跑闭环。

## 成功标准

- [ ] Resolver 使用 Runner bootstrap Python 可解析的语法。
- [ ] CI / Runtime / Tooling 的 Resolver 进程非零退出时写 reusable=false 并继续真实验证。
- [ ] PR 阶段显式执行 bootstrap python3 -m py_compile。
- [ ] Resolver 单元回归与 workflow structure 回归覆盖兼容/降级机制。
- [ ] 修复 PR 当前 HEAD required CI 绿色且独立 Review 无 blocking finding。
- [ ] 合并后 main 实际 Evidence Reuse 成功，不再重复昂贵层。
- [ ] 新 Change 归档，Issue #636 / AC7 完成并关闭。

## 范围

仅修 Evidence Resolver、其 workflow 调用、防回归测试和直接测试说明。

## 非目标

- 不改变 PostgreSQL / Full-stack impact mapping。
- 不改变业务代码、Contract、Schema/Migration、依赖或生产部署。
- 不取消任何独立 Evidence Owner。

## 必须保持不变

- 同 tree + 来源 check 绿色才允许复用。
- 无法确认 GitHub 事实时仍为 reusable=false。
- CI Gate / Compose Golden Path identity 与 main 轻量治理门禁保持。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围 | 修复控制面兼容与 fallback | E1-E5 | 不扩大到业务测试重构 |
| 接口与契约 | 产品 Contract 不变 | 无产品接口变化 | 仅内部 CI 输出 |
| 数据与迁移 | 不适用 | 无数据变化 | 无 Migration |
| 错误与失败语义 | Resolver 非零 = 不可复用，转入真实验证 | E4 | 避免控制面单点故障 |
| 兼容性 | bootstrap 脚本以 Runner system python 可执行为最低边界 | E3 | PR 增加 compile gate |
| 部署与回滚 | 普通 CI 变更，可 Git revert | 无生产数据改变 | 无 Deploy |

# 修改方案与决策依据

## 最小充分方案

1. 将多异常 except 恢复为括号 tuple。
2. 三个 Resolver workflow 调用先写临时 output；成功才转写 GITHUB_OUTPUT，失败则写 reusable=false/reason=resolver_execution_failed 并继续。
3. CI 在 setup-python 之前增加 system python3 -m py_compile，验证控制面 bootstrap 兼容。
4. 增加兼容与 workflow fallback 回归。
5. 更新测试说明，明确 GitHub facts 不可确认和 Resolver 自身执行失败都只关闭复用。
6. PR 绿色 + Review 后合并；读取 main 实际 jobs 证明 reuse；归档 Change，关闭 #636。

## 证据到决策

| 决策 | 依据证据 | 原因 |
| --- | --- | --- |
| D1 兼容括号语法 | E2、E3 | 直接切断当前 SyntaxError |
| D2 workflow process fallback | E2、E4 | 未来脚本启动失败也不会阻断真实验证 |
| D3 bootstrap compile gate | E3 | merge 前覆盖脚本实际执行 Runtime |
| D4 不改 impact mapping | E1、E5 | 当前缺陷与测试选择逻辑无关 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | merge 后 main 实际行为与设计一致 | #636 / AC7 | not_satisfied | 待修复后 main Actions |
| R2 | 无法安全复用时必须执行真实 Evidence | #636 / AC1 | not_satisfied | 待 process-failure fallback 回归与 Actions |
| R3 | CI Gate / Runtime 继续 fail closed | #636 / AC5 | not_satisfied | 待 workflow structure 与 main Evidence |

# 计划改动

| 文件 / 资产 | 计划修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| scripts/quality/resolve_main_evidence.py | 修兼容语法 | bootstrap 可执行 | R1-R3 |
| CI / Runtime / Tooling workflows | 进程失败 fallback + bootstrap compile | 控制面失败不阻断真实验证 | R1-R3 |
| CI tests | 兼容与结构回归 | 防止复发 | R1-R3 |
| docs/04_测试与调试说明.md | 同步 fail-closed 边界 | 维护者理解行为 | R2-R3 |

- [x] 调查当前实现和失败日志。
- [x] 确认根因和两条复发路径。
- [ ] 建立失败回归。
- [ ] 完成最小实现。
- [ ] 同步文档。
- [ ] 取得 PR fresh CI / Review。
- [ ] 完成 post-merge main / archive / issue closure。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Resolver 兼容与 fallback 结构 |
| 接口 / 契约 | not_applicable | 无产品 Contract 变化 |
| 集成 / 持久化 / 运行依赖 | required | main push 真实 Actions 控制面 |
| 用户 / 工作流验收 | not_applicable | 无产品 UI 变化 |
| 跨组件关键路径 | required | PR check → merge → main reuse/fallback |
| 外部依赖 / 供应方探测 | not_applicable | GitHub 由实际 Actions 证明 |
| 构建 / 打包 / 运行 | required | Runner bootstrap system Python compile |
| 文档 / 治理 / 其他 | required | Change/Issue/Review/Archive |

## 验证计划

- system python3 py_compile Resolver / classifier。
- CI resolver / workflow structure targeted tests。
- 当前 PR required Actions。
- merge 后 main CI / Runtime / Tooling jobs。
- Change Archive 与 Issue #636 状态。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | fallback 错误跳过 required 层 | fallback 只写 reusable=false，后续原路径继续 |
| 兼容性 | 提升 bootstrap Python 兼容 | 使用经典括号多异常语法 |
| 数据 / Migration | 不适用 | 无数据/Schema |
| 部署 / 运行 | 只改变 GitHub Actions | 无生产变更 |
| 回滚 / 恢复 | 普通 Git revert | 无持久副作用 |

# 文档、依赖、部署与发布影响

- 长期文档：targeted 更新测试与调试说明。
- 依赖 / Runtime：不升级依赖，不改变 Python 3.14 项目基线。
- 配置 / Secret：不新增 Secret。
- 部署 / Release：不适用。
- 兼容 / 消费方通知：CI 维护者无需新增操作。

# 完成审计

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 待填写 | bootstrap compile | 待执行 | 兼容 Runner system Python |
| V2 | 待填写 | targeted unit/structure | 待执行 | fallback 不绕过真实验证 |
| V3 | 待填写 | PR Actions | 待执行 | 当前 HEAD 可交付 |
| V4 | 待填写 | main Actions | 待执行 | post-merge reuse 成立 |

## 未验证内容与剩余风险

当前尚未完成实现和验证，不得声称 AC7 已闭合。

## 交付状态

- 分支：fix/636-main-evidence-resolver-compat
- PR：待创建
- CI：待执行
- 合并：待 current-head required CI + Review
- Change Archive：待 merge 后
- Issue #636：open，AC7 pending
- Release / Deploy：不适用
