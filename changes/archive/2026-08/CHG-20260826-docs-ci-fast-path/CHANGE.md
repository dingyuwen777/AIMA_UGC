---
schema: rvc-change/v1
id: CHG-20260826-docs-ci-fast-path
title: 文档与治理变更 CI 风险分层快速路径
level: L2
status: done
owner: dingyuwen777
branch: feature/docs-ci-fast-path
created: 2026-08-26
updated: 2026-08-26
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - agent-governance
  - documentation-governance
affected_paths:
  - .github/workflows/ci.yml
  - .github/workflows/fullstack.yml
  - scripts/quality/classify_ci_scope.py
  - scripts/quality/scan_secrets.py
  - .agents/skills/coding/README.md
  - .agents/skills/coding/references/07_通用验证与证据策略.md
  - .agents/skills/coding/tests/test_docs_ci_fast_path.py
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts: []
data_changes: []
---

# 目标

让 AIMA_UGC 的永久 CI 按真实风险选择验证层，而不是纯文档或纯治理变更也机械执行完整产品 CI。

核心行为：

1. 仅修改不影响机器业务行为的说明文档时进入 `docs_only`，只运行文档、Secret 和仓库治理相关轻量验证；
2. 仅修改 `changes/**`、任意层级 `AGENTS.md`、`.agents/**` 等研发治理事实时进入 `governance_only`，仍保留文档/Secret/Change/Skill 等治理门禁，但不运行 PostgreSQL、Wheel、Frontend Browser Mock、真实 Full-stack 等产品验证；
3. 一旦存在机器行为、Prompt、Contract、Migration、依赖/lock、build/config/workflow、产品代码、混合 diff 或无法安全归类的路径，进入 `full`，保持现有完整 CI 证明责任；
4. `CI Gate` check identity 始终存在，不使用简单 `paths-ignore` 让主 CI check 消失。

# 成功标准

- [x] Coding 的现有 Workflow 硬路由继续由 `SKILL.md` §11 触发；`07_通用验证与证据策略.md` 明确 Documentation / Governance Fast Path，纯文档不得为了形式机械跑完整产品 CI。
- [x] `07_通用验证与证据策略.md` 定义保守的 docs/governance/full changed-scope 分类和退出 fast path 条件，并明确 profile 名称是项目本地映射而非通用固定 API。
- [x] `scripts/quality/classify_ci_scope.py` 用标准库实现白名单式分类；未知路径、空 diff、不可读基线和机器消费文件默认 `full`。
- [x] `.github/workflows/ci.yml` 始终产生 `CI Gate`；轻量 profile 只跑 `Docs and Governance`，full profile 保持 `Repository Quality + PostgreSQL Integration`。
- [x] `.github/workflows/fullstack.yml` 对确认无产品接线风险的 docs/governance 路径不再触发真实 Full-stack；Prompt/未知 Markdown 不在忽略范围。
- [x] 轻量 profile 运行当前 `check_docs.py` 和 `scan_secrets.py`；Secret scan 已覆盖 `.agents/**`；`governance_only` 额外运行 Coding governance regression。
- [x] Blueprint 06 把“PR 最新 HEAD CI”改为“PR 最新 HEAD 风险相关 required CI profile”，并解释 AIMA 的三种 profile、Prompt 例外和各永久 Workflow 分责。
- [x] 回归测试先在旧实现上真实失败，再在实现后通过，覆盖 docs_only/governance_only/full、Prompt `.md`、未知路径、docs 目录机器文件、点目录、CI Gate 和 Full-stack 路径边界。
- [x] 不删除或降低原产品 CI 的 Unit/Contract/API/PostgreSQL/Wheel/Frontend/Browser Mock/Full-stack 证明责任；feature PR 和 main merge commit 的真实 full profile 都证明原产品层仍执行并成功。
- [x] fast-path 合入 main 后，独立临时 PR #246 真实验证 `docs_only`：轻量 Docs/Secret 与 `CI Gate` 成功，产品重型 jobs skipped，Full-stack 未触发；PR 已关闭且未合并，验证文件没有进入 main。
- [ ] 独立归档 PR 真实验证 `governance_only`：`Docs and Governance` 与 Coding governance regression 成功，产品重型 jobs skipped，`CI Gate` 成功；取得该证据后再合并归档 PR。

# 非目标

- 不改变产品业务代码、Contract、Schema/Migration 或数据库行为。
- 不删除现有永久 Workflow。
- 不把任意 `.md` 都视为文档；Prompt、机器消费 Markdown 和未知路径默认走 full。
- 不通过改 check name、关闭门禁、`continue-on-error` 或降低断言达到“加速”。
- 不在本 Change 顺手重构 Runtime/Tooling/Release 的其他职责。

# 必须保持不变

- `CI Gate`、`Repository Quality`、`PostgreSQL Integration` 的 check identity 和 full profile 证明范围。
- Change Completion Gate 继续独立运行 Requirement Traceability / Coding Skill regression / Ready Check。
- Runtime Acceptance 现有 risk-detection / fast-path 机制保持。
- Full-stack 的真实 Excel Golden Path 在产品相关变更时继续运行。
- Release 当前仍以 `CI Gate`、`Compose Golden Path`、`Requirement Traceability and Completion Audit` 作为正式 main check 消费者，不因本 Change 失效。
- Docs/Coding/Review 路由、Completion Audit、中文提交、北京时间和安全边界保持。

# 关键决策

1. 不在主 `SKILL.md` 重复增加 AIMA 专属 profile 名称：现有 §11 已硬路由永久 Workflow 优化到 `07`；通用 fast-path 规则放 `07`，AIMA 具体路径事实放 Blueprint 和 Workflow，避免第二套规则。
2. Main CI 不使用顶层 `paths-ignore` 跳过自身，而是始终创建 `CI Gate`；内部 `CI Scope` 决定哪些层 required。
3. 轻量分类采用白名单：任意未知、混合、机器消费或无法读取 changed scope 时回退 `full`。
4. `git diff --no-renames --name-only -z` 用于 changed scope；rename 同时保留旧/新路径风险，不能通过移动文件伪装成 docs-only。
5. `docs/**` 只有 Markdown 和常见文档图片后缀进入 docs-only；放入 docs 目录的 JSON/YAML/脚本等未知机器文件仍 `full`。
6. 任意层级 `AGENTS.md` 和 `.agents/**` 归 `governance_only`；点目录规范化不得破坏 `.agents`。
7. 部署/Release 专题文档若被其专用 Workflow path 明确消费，仍可触发对应 targeted specialized workflow；本 Change 只消除与该 diff 无关的完整产品 CI。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 纯文档变更在不影响业务和仓库级门禁时，不跑完整产品 CI | user:current-request | satisfied | `ci.yml` 的 `CI Scope` + `docs_only`；`07` Documentation / Governance Fast Path；Blueprint 06 §19.1；真实 PR #246 |
| R2 | 只跑文档相关 CI，而不是简单跳过所有检查 | user:current-request | satisfied | PR #246 的 `Docs and Governance`、Secret/docs、`CI Gate` success；Repository Quality/PostgreSQL skipped |
| R3 | 文档 fast path 必须保守，Prompt/机器行为 Markdown 不能误判 | user:approved-plan | satisfied | classifier 白名单、未知/空/错误回退 full；Prompt 和 `docs/generated-policy.json` 回归均为 full；rename 使用 `--no-renames` |
| R4 | required check identity 不因优化消失 | user:approved-plan | satisfied | `CI Gate` 保持原名且 `if: always()`；Release required checks 已重新核对并继续消费 `CI Gate`；full/docs-only 均实际成功 |
| R5 | Skill 与 Blueprint 同步表达风险相关 CI，而非机械全量 CI | user:approved-plan | satisfied | 主 Skill 现有 §11 硬路由保留；07 新增 fast-path 细则；Coding README §11.1；Blueprint 06 固化 AIMA profile |
| R6 | 不降低原 Unit/Contract/API/PostgreSQL/Wheel/Frontend/Full-stack 证明责任 | .agents/skills/coding/references/07_通用验证与证据策略.md | satisfied | Evidence Preservation Mapping；feature/main full profile 实际运行 Repository Quality、PostgreSQL Integration、CI Gate；Full-stack/Runtime success |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | `test_docs_ci_fast_path.py` + 全套 Coding tests；Red run `32917899126` 中新增 5 组断言按预期失败，旧 36 组通过；最终 Ready HEAD Change Gate `32919528138` success |
| 接口 / Contract | not_applicable | 不改变产品 public Contract；CI profile 输出仅在当前 Workflow 内部消费 |
| 集成 / Persistence / Runtime Dependency | required | feature final full CI `32919528146` 与 main full CI `32919813749` 的 PostgreSQL Integration 均 success |
| 用户 / Workflow Acceptance | required | feature/main `full` 实际成功；post-merge PR #246 真实 `docs_only` 成功；归档 PR 负责最终 `governance_only` 真实验收 |
| 跨组件 Golden Path | required | feature Full-stack `32919528156` success；main Full-stack `32919813732` success；docs-only PR #246 未触发 Full-stack |
| External Dependency / Provider Probe | not_applicable | 不改变 Provider 或外部接口事实 |
| Build / Package / Runtime | required | feature/main full profile 的 startup smoke、Wheel、Frontend unit/build/Browser Mock success；Runtime feature/main 均 success |
| Docs / Governance / Other | required | Coding tests、Secret/docs、Change Gate success；Docs targeted review 无 code_issue_detected；Review 找到点目录规范化缺陷后已修复并 re-review；PR #246 docs-only 轻量门禁 success |

# Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| Python lint/type/unit/contract/API | CI / Repository Quality | full profile / Repository Quality | 保持 | 原命令未删除；feature/main full profile 均成功执行 |
| Secret + docs gates | CI / Repository Quality | full profile 原位置；轻量 profile / Docs and Governance | 保持 | 两类 profile 均运行同一质量脚本；Secret scan 增加 `.agents`；PR #246 实证成功 |
| Wheel + Frontend unit/build/Browser Mock | CI / Repository Quality | full profile / Repository Quality | 保持 | feature/main full profile 均成功执行 |
| PostgreSQL transaction/migration/integration | CI / PostgreSQL Integration | full profile / PostgreSQL Integration | 保持 | 仍使用 PostgreSQL 18.4；feature/main full profile 均成功 |
| CI 总门禁身份 | CI / CI Gate | CI / CI Gate | 保持 | 原 check name 不变；feature/main full 与 PR #246 docs-only 都成功 |
| Real Full-stack Golden Path | Full-stack Acceptance | 产品相关 path 保持；安全 docs/governance path 不触发 | 保持 | Golden Path Job body 未修改；feature/main success；docs-only PR 不触发 |
| Requirement/Ready/Coding regression | Change Completion Gate | Change Completion Gate | 保持 | Workflow 未修改；feature Ready HEAD 与 main merge commit success；PR #246 success |

# Red → Green

## Verify Red

Red HEAD 建立 Change + 新回归后，Change Completion Gate `32917899126` 真实执行 41 个 Coding tests：

- 新增的 5 个 fast-path 测试全部因旧实现缺少目标能力而失败；
- 原有 36 个 Coding/Docs/Review/Ready/网络源/Workflow 治理回归继续通过；
- 失败点对应 classifier、轻量 CI route、Skill reference、Full-stack scope、`.agents` Secret scan 五个本次目标。

因此 Red 原因正确，不是环境或既有回归。

## Verify Green / full profile

实现阶段曾由 full CI 准确发现 classifier Ruff formatting failure，修正后整套产品证据恢复全绿，证明新路由没有通过跳过失败达到成功。

最终 feature Ready HEAD `888aa3cdfb9302c0d8d7052432b1fbd86c3848b3`：

- Change Completion Gate `32919528138`：success；
- Runtime Acceptance `32919528158`：success；
- Full-stack Acceptance `32919528156`：success；
- CI `32919528146`：success；当前 Workflow feature diff 正确选择 `full`，`Repository Quality`、`PostgreSQL Integration`、`CI Gate` 全部 success。

Feature PR #245 已正常合并，merge commit `9435fe354e6a32320ac693e103229616224d271e`。该 main commit 再次按 `full` 验证：

- Change Completion Gate `32919813783`：success；
- Runtime Acceptance `32919813682`：success；
- Full-stack Acceptance `32919813732`：success；
- CI `32919813749`：success；`Repository Quality`、`PostgreSQL Integration`、`CI Gate` 全部 success。

## Post-merge docs_only 真实验收

为避免把 classifier 单元测试冒充 GitHub Actions 调度证据，从 `main 9435fe35...` 创建临时分支 `test/docs-ci-fast-path-probe`，仅新增 `docs/ci-fast-path-probe.md`，形成临时 PR #246。该 PR 明确不合并。

真实结果：

- CI `32920048962`：success；
  - `CI Scope`：success；
  - `Docs and Governance`：success；
  - `Secret and docs gates`：success；
  - `Coding governance regression`：skipped，符合 `docs_only`；
  - `Repository Quality`：skipped；
  - `PostgreSQL Integration`：skipped；
  - `CI Gate`：success；
- Change Completion Gate `32920048968`：success；
- Runtime Acceptance `32920048914`：success，走无 Runtime 风险 fast path；
- Full-stack Acceptance：未触发，符合 docs-only trigger policy。

PR #246 已关闭且 `merged=false`，验证文件未进入 `main`。

# Docs targeted review

范围：Coding README §11.1、reference 07 的 Documentation / Governance Fast Path、Blueprint 06 的 CI profile 说明，以及它们直接依赖的 classifier/CI/Full-stack 实现。

结论：

- Fact Correctness：文档描述与 classifier、CI Gate route、Full-stack path filter、Change Gate/Runtime 分责一致；
- Coverage：说明了 why、三个 profile、Prompt/机器消费文件例外、混合/未知回退、check identity 和 specialized Workflow 边界；
- Source-of-truth Safety：通用原则在 07；AIMA 精确路径由 classifier/Workflow 作为机器事实，Blueprint 解释职责，README 只做使用导航；
- Usability：开发者能理解“纯文档为什么不用跑 DB/Browser”以及“为什么 `.md` 仍可能 full”；
- `code_issue_detected`：无。

# Review Skill 独立审查

Review Target：PR #245，base `ae3a03b76d830613ce64858976a524b717320e27`，mode `review-and-fix`。

独立重建的最高风险：

1. 机器行为文件被误判成轻量；
2. stable required check identity 消失；
3. full profile 原测试责任被删除/弱化；
4. Full-stack 对产品相关变化被错误跳过；
5. changed-scope 在 rename、点目录、未知路径上产生绕过。

Finding：

- 初版 `_normalize_path()` 使用 `lstrip("./")`，会把 `.agents/**` 的前导点剥掉，导致 governance path 错误回退 `full`。已返回 Coding 修复为只移除字面量 `./` 前缀，并补嵌套 `AGENTS.md`、`.agents/**`、docs 目录机器文件回归。

Re-review：

- classifier 现在 full 优先、未知/空/错误回退 full；
- `.agents` 点目录保持；rename 使用 `--no-renames`；
- `CI Gate` 原名和 Release consumer 均保持；
- `Repository Quality`/`PostgreSQL Integration` 原命令未删除；
- Full-stack 只增加安全 docs/governance ignore，没有 `**/*.md` 或 `prompts/**`；
- feature PR changed files 仅本 Change 预期的 CI/治理/文档/测试文件，无产品业务 diff。

无剩余阻塞 Finding。

# Completion Audit

- [x] upstream_re_read：重新读取用户批准方案、当前 `AGENTS.md`、Coding §11/07、Docs、Review、CI/Full-stack/Runtime/Change Gate、Release required check consumer、Blueprint 06 和当前 diff。
- [x] change_coverage：R1-R6 覆盖“纯文档不全跑、仍保留文档门禁、保守分类、check identity、Skill/Blueprint 同步、证据守恒”。
- [x] reverse_audit：从用户目标反查到 classifier → CI route → CI Gate → specialized workflows；从当前 diff 反查测试、文档、Release consumer 和 full product evidence，未发现要求落空。
- [x] unresolved_cleared：feature/full 与 docs-only 两类真实路由均闭环；归档 PR 仅承担 governance-only 最后一项集成验证，未通过前不合并归档。

# 任务

- [x] 恢复当前 main / AGENTS / Coding / Docs / CI / Full-stack / Blueprint 事实
- [x] 建立 L2 Change 与 Evidence Preservation Mapping
- [x] 建立 Red 回归并 Verify Red
- [x] 实现 scope classifier
- [x] 实现 CI lightweight/full profile 路由
- [x] 收敛 Full-stack docs/governance 无关触发
- [x] 更新 Coding reference/README/Blueprint；主 SKILL 已有正确硬路由，无重复修改
- [x] Verify Green + full profile
- [x] Docs targeted review + Review Skill + re-review
- [x] Ready 状态最终 HEAD 的 Change Gate / CI / Runtime / Full-stack 新鲜验证
- [x] PR #245 正常合并与 main full-profile 集成验证
- [x] 临时 PR #246 真实验证 docs_only，随后关闭不合并
- [ ] 独立归档 PR 真实验证 governance_only 并归档 Change

# 文档影响

Docs Impact: targeted。

- `coding/README.md` 已同步人类使用方式；
- reference 07 已同步通用 fast-path 规则；
- Blueprint 06 已同步 AIMA 当前 profile/Workflow 事实；
- Docs Skill 本体已能正确承担 targeted/not_applicable，不需要修改。

# 交付

- Feature branch：`feature/docs-ci-fast-path`
- Feature PR：#245 `优化纯文档与治理变更 CI 快速路径`，已合并；merge commit `9435fe354e6a32320ac693e103229616224d271e`
- Docs-only probe PR：#246，已关闭、未合并；临时验证文件未进入 main
- Product Contract / Schema / Migration / dependency / data：无变化
- 归档：本文件位于 `changes/archive/2026-08/`；归档 PR 只包含 Change rename/update，并在合并前必须以真实 Actions 证明 `governance_only`。
