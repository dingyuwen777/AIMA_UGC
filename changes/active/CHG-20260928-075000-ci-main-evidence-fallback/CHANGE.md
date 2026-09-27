---
schema: coding-change/v1
id: CHG-20260928-075000-ci-main-evidence-fallback
title: 修复main证据复用控制面兼容与故障回退
level: L2
status: ready_for_review
owner: dingyuwen777
branch: fix/636-main-evidence-fallback
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - github-actions
affected_paths:
  - scripts/quality/resolve_main_evidence.py
  - .github/workflows/ci.yml
  - .github/workflows/runtime.yml
  - .github/workflows/tooling.yml
  - tests/unit/test_ci_main_evidence_reuse.py
  - tests/unit/test_ci_workflow_structure.py
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：PR #637 合并后，main 的 Evidence Reuse 控制面由 Runner 系统 Python 在 setup-python 之前执行；resolver 使用了 Python 3.14 可接受但系统 Python 不接受的语法，导致 CI/Runtime/Tooling 在复用判断前直接失败。
- **拟议修改**：恢复 Python 3.12+ 兼容语法，并在三个 workflow 的 resolver 调用外增加 fail-closed shell fallback；resolver 自身启动/执行失败时写入 reusable=false，继续真实验证。
- **预期结果**：main 同 tree + 来源 check 绿色时正常复用；resolver 自身任何异常也只失去优化收益，不会失去 CI/Runtime/Tooling 正确性。

# 背景、现状与问题

## 背景

Issue #636 / AC1 与 AC7 要求 main 的复用机制必须 fail closed，并用 merge 后真实 Actions 证明。PR #637 的产品 Evidence 全绿并已合并，但 post-merge 首次运行暴露控制面解释器兼容缺陷，因此 Issue 已重新打开。

## 当前现状

- merge commit `883a580bed0ceacf1ee4b1dc0c06b3545586b513` 与 PR HEAD tree 完全一致。
- main 的 CI、Runtime、Tooling 都在 `setup-python` 之前用 Runner 系统 `python3` 调用 `resolve_main_evidence.py`。
- 真实日志显示 line 215 的 `except HTTPError, URLError, ...:` 触发 `SyntaxError: multiple exception types must be parenthesized`。
- PR full CI 使用 Python 3.14，因此没有暴露“bootstrap/system Python”这一独立运行边界。

## 问题、根因或约束

根因有两层：
1. resolver 源码没有保持其真实 bootstrap Runtime 的 Python 语法兼容性；
2. workflow 只让 resolver 内部 API 异常 fail closed，却没有为“resolver 进程自身无法启动/意外退出”提供外层 fail-closed fallback。

只改括号能止血，但不能覆盖第二条复发路径。

## 不修改的后果

main push 会继续在复用控制面直接失败，无法获得 CI Gate / Compose main-fresh Evidence，并且 Tooling 退化路径由 needs/always 偶然触发而不是设计保证。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | main resolver 在 Runner 系统 Python 解析阶段失败 | Runtime run 36359828200、CI run 36359828353、Tooling run 36359828197 logs | 必须验证 pre-setup/system Python 兼容 |
| E2 | 失败文本为多异常 except 缺少括号 | GitHub Actions job logs | 直接语法修复明确 |
| E3 | merge tree 与 PR tree 相同 | GitHub commit API | Evidence reuse 前提本身成立，失败在控制面 |
| E4 | 当前 resolver 内部已经把 HTTP/API 异常转换为 reusable=false | `scripts/quality/resolve_main_evidence.py` | 保留内部 fail-closed，并补进程级 fallback |
| E5 | Runtime resolver step 失败后后续验证全部 skipped | main Runtime job steps | 外层 fallback 是永久解决必要条件 |

## 推断与待确认

无。下一步均可由仓库代码和 Actions 实际运行确认。

# 目标、成功标准与非目标

## 目标

让 Evidence Reuse 成为“可失败的优化层”：成功时节省重复 CI；自身失败时自动回退真实验证，不得成为新的 main 单点故障。

## 成功标准

- [ ] resolver 可由 Python 3.12 语法规则解析，并继续兼容仓库 Python 3.14。
- [ ] CI / Runtime / Tooling 的 resolver 进程非零退出时写 `reusable=false` 并继续原真实验证路径。
- [ ] PR 当前 HEAD 的 targeted regression、required CI 和 Runtime 绿色。
- [ ] 合并后 main 实际 Evidence Reuse 成功；PostgreSQL / Real Full-stack / Runtime / Linux+Windows Tooling 不重复执行昂贵层。
- [ ] Issue #636 / AC7 完成，新的 Change 自动归档。

## 范围

- resolver 语法兼容；
- resolver workflow 调用的 process-level fail-closed wrapper；
- 对应自动回归。

## 非目标

- 不修改 PostgreSQL target/suite mapping；
- 不修改 Full-stack Journey mapping；
- 不改变 Ruleset、依赖、Schema、业务代码或生产部署。

## 必须保持不变

- `CI Gate` / `Compose Golden Path` check identity；
- main reuse 仍要求唯一 merged PR + tree equality + source check success；
- 无法安全复用时必须运行真实 changed-scope / Runtime / Tooling。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围 | 只修 bootstrap control plane | E1–E5 | 不回滚已验证的 impact mapping |
| 接口与契约 | 产品 Contract 不适用 | 无业务接口变化 | 仅内部 GITHUB_OUTPUT |
| 数据与迁移 | 不适用 | 无数据变化 | 无 Migration |
| 失败语义 | resolver 非零 = reusable=false + reason=resolver_process_failed | E5 / #636 AC1 | 优化层自身失败不阻塞真实 Evidence |
| 兼容性 | system Python 3.12 grammar + project Python 3.14 | E1、E2 | 覆盖 pre-setup 与项目 Runtime |
| 回滚 | 回滚本修复会重新暴露 main failure | main 实证 | 不涉及数据恢复 |

# 修改方案与决策依据

## 最小充分方案

1. Red：新增 Python 3.12 grammar parse 回归和 workflow process-fallback 结构回归。
2. Green：多异常 except 恢复括号语法；CI/Runtime/Tooling resolver 调用使用 shell `if ! python3 ...`，失败时写固定 false/reason outputs。
3. 验证 PR current-head；独立 Review 只复核本修复 diff 和原 AC1/AC7。
4. merge 后读取 main 实际 jobs，确认 reuse success 和昂贵层 skipped，再完成 Issue/Archive。

## 证据到决策

| 决策 | 依据证据 | 为什么采用 |
| --- | --- | --- |
| D1 Python 3.12 grammar regression | E1、E2 | 直接覆盖真实 bootstrap interpreter 边界 |
| D2 workflow process fallback | E4、E5 | 防止未来 syntax/import/runtime defect 再把优化层变成单点故障 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Evidence Reuse 任何不可确认/失败情况都回退真实验证 | #636 / AC1 | satisfied | resolver 已恢复 Python 3.12 grammar；CI/Runtime/Tooling 四个调用均以 shell `if ! python3 ...` 捕获进程失败并写 `reusable=false` / `reason=resolver_process_failed`。 |
| R2 | merge 后 main 行为真实完成并收尾 | #636 / AC7 | explicitly_deferred | 该要求只能在修复 PR 合并后读取 main Actions / Archive 才能证明；PR Ready 阶段不能伪造 post-merge Evidence。 |

# 计划改动

| 文件 / 资产 | 计划修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| resolver | Python 3.12+ 兼容 except | 修复真实解析失败 | R1 |
| CI/Runtime/Tooling workflows | resolver process fallback | 切断控制面单点故障 | R1 |
| CI unit/structure tests | grammar + workflow fallback regressions | 防复发 | R1 |
| Change | fresh Evidence 与收尾 | 可追溯交付 | R2 |

- [x] 调查 main 真实失败日志。
- [x] 根因闭合到解释器兼容 + 进程级 fallback 缺口。
- [x] 建立 Red：Python 3.12 grammar 与四个 workflow process fallback 回归。
- [x] 完成最小 Green：兼容异常语法 + resolver 进程级 fail-closed wrapper。
- [ ] PR current-head CI / Review：Ready 后执行，作为 merge gate。
- [ ] merge 后 main reuse / Archive / Issue closure：仅 post-merge 可执行。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Python 3.12 grammar parse + resolver evaluation |
| 接口 / 契约 | not_applicable | 产品 Contract 不变 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 本修复不改变 PostgreSQL 行为；main post-merge只验证是否跳过重复层 |
| 用户 / 工作流验收 | not_applicable | 无产品 UI 行为 |
| 跨组件关键路径 | required | PR → merge → main resolver → reuse/fallback → Gate |
| 外部依赖 / 供应方探测 | not_applicable | GitHub 为 CI 平台，由正式 Actions 实跑证明 |
| 构建 / 打包 / 运行 | required | Runner system Python + GitHub workflow |
| 文档 / 治理 / 其他 | required | Issue/Change/Review/Archive |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理 |
| --- | --- | --- |
| 主要风险 | fallback 输出缺字段导致下游误判 | 固定 reusable/reason，未写 source 字段也不参与 false 路径 |
| 兼容性 | 向下兼容 system Python grammar | 使用传统括号 tuple except |
| 数据 / Migration | 不适用 | 无数据变化 |
| 部署 / 运行 | GitHub Actions only | 无生产部署 |
| 回滚 | 不建议，除非整体回滚 evidence reuse | 当前 main failure 已证明必要性 |

# 文档、依赖、部署与发布影响

- 长期文档：原 CI 文档语义不变，无需新增说明；“resolver 失败 fail closed”本来就是既定语义，本修复使实现符合文档。
- 依赖：不变。
- Secret：不变。
- Release/Deploy：不适用。

# 完成审计

- [x] upstream_re_read：已重读 #636 AC1/AC7、main 失败日志和当前 resolver/workflow。
- [x] change_coverage：R1 已实现；R2 有正式 post-merge 生命周期依据。
- [x] reverse_audit：resolver 内部 API fail-closed 与 workflow 进程级 fail-closed 均存在；false 路径继续原真实 CI/Runtime/Tooling。
- [x] unresolved_cleared：无 `not_satisfied`；R2 按 #636 AC7 明确为 post-merge `explicitly_deferred`。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明 |
| --- | --- | --- | --- | --- |
| V1 | 当前分支 | `test_resolver_source_is_compatible_with_runner_bootstrap_python` readback | Red/Green 资产已建立，待 PR CI 执行 | pre-setup Python 3.12 grammar compatibility |
| V2 | 当前分支 | `test_main_evidence_resolver_process_failure_falls_back_in_all_workflows` readback | 四个调用均存在 process fallback，待 PR CI 执行 | resolver process failure 不再阻塞真实验证 |
| V3 | PR #638 current HEAD | GitHub CI / Runtime / Tooling | Ready 后执行 | current-head formal evidence |
| V4 | merge 后 main | GitHub Actions | explicitly_deferred 到 #636 AC7 | actual reuse + expensive layers skipped |

## 未验证内容与剩余风险

实现已完成但 PR current-head 与 post-merge main Evidence 尚未取得；CI/Review 未绿前不得合并，main reuse 未实证前不得关闭 AC7。

## 交付状态

- 分支：`fix/636-main-evidence-fallback`
- PR：#638，Draft，关联 #636
- CI：待 Ready 后 current-head 执行
- merge：待 current-head required gates 与独立 Review
- Archive：待 merge 后 repository-native workflow
- Release/Deploy：不适用
