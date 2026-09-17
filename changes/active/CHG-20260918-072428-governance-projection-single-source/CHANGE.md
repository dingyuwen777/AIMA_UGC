---
schema: coding-change/v1
id: CHG-20260918-072428-governance-projection-single-source
title: AIMA 治理资产改为 Agent_Skills generated projection
level: L2
status: ready_for_review
owner: AIMA_UGC
branch: refactor/governance-projection-single-source
created: 2026-09-18
updated: 2026-09-18
completion_gate: required
depends_on: []
affected_areas:
  - 项目治理
  - CI
  - Requirement Source
  - Change Carrier adapter
affected_paths:
  - .agents/skills/coding
  - .github/ISSUE_TEMPLATE
  - scripts/quality
  - tests/unit
contracts:
  - Agent_Skills governance machine Contract
  - AIMA Requirement Source
  - AIMA Change Carrier
data_changes: []
---

# 变更摘要

AIMA 当前重复维护通用治理 validator 与 Issue Form Profile。本变更把 current Agent_Skills governance machine assets 作为受管 generated projection，根 Issue Forms 仅保留 projection；AIMA 自己只保留 GitHub API、顶层 `changes/` Carrier 和 CI adapter。

# 背景、现状与问题

Agent_Skills #256 / PR #257 已完成单一 canonical source：Change Template、Issue Forms、通用 machine validator 只在 Agent_Skills 维护。AIMA main 仍存在 `scripts/quality/governance_asset_contract.py`，并在 `check_agent_governance.py` 再次硬编码通用 Issue 字段/Profile，因此维护责任仍重复。

# 事实与证据

- AIMA main `scripts/quality/governance_asset_contract.py` 复制 Change ID、AC、Issue Profile、L3 标题等规则。
- AIMA main `.agents/skills/coding/` 原先没有 current canonical `governance_contract.py` 与 `assets/issue-templates/`。
- Agent_Skills PR #257 final head `f6322fa98dbf9a0b0581fece14d38ca768fb8cc5` 已通过完整 Skill/Runtime/package evidence，并 merge 为 `cde15e80c081844e74e992ac126707cf36fc4c6c`。
- Agent_Skills merge main-fresh Skill Tests run `35284850234` success，随后 Change 已 repository-native archive，Issue #256 已 completed。

# 目标、成功标准与非目标

成功标准是 AIMA 不再持有通用治理规则的第二人工 Owner：受管 canonical validator/assets 与根 Issue Form projection 保持一致；项目 gate 只实现 AIMA 的 live GitHub API、Carrier 和 CI 接线。

非目标：不改变产品/API/Schema/Data/Frontend/Provider；不改历史 Issue/Change；不实现旧 Agent_Skills 版本升级/迁移；不 Release/Deploy。

# 约束与意图决策

- canonical 语义 Owner 必须是 Agent_Skills；AIMA `.agents` 文件只作为 managed/generated projection。
- AIMA 的顶层 `changes/` 是项目 Carrier，不能改成 Agent_Skills 源仓的 `.agents/changes`。
- GitHub 根 Issue Forms 必须物理存在，因此在 AIMA 中保留原字节 generated projection，而不是远程引用。
- 本次按用户决定只处理当前版本干净首次安装结果，不增加 alias/fallback/迁移分支。

# 修改方案与决策依据

1. 投影 current Agent_Skills `governance_contract.py`、Change Template 与 Issue Form assets 到 AIMA `.agents/skills/coding/`。
2. 根 `.github/ISSUE_TEMPLATE/*.yml` 与受管 assets 原字节一致。
3. 删除 `scripts/quality/governance_asset_contract.py` 及其项目重复测试。
4. `check_pr_requirement_source.py` 只负责 AIMA live Issue 加载、仓库路径来源和 `changes/active` changed-scope 枚举；单个 Issue/Change 调 canonical validator。
5. `check_agent_governance.py` 只检查 generated projection parity、项目 CI/PR template/Carrier 接线。
6. AIMA 不复制 Agent_Skills 自身 canonical 测试；只保留“项目是否正确消费 projection”的回归。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | AIMA 使用 current canonical validator/Change Template/Issue Form assets 的 generated projection | #534 / AC1 | satisfied | implementation commit `1c78e69aaa123ba77215f9f2d475d9184d3c6b17` 已加入受管 projection |
| R2 | 根 Issue Forms 与受管 assets 原字节一致且 drift fail closed | #534 / AC2 | satisfied | implementation commit 同步四个 projection；项目 checker 新增 byte-parity gate 与 drift regression |
| R3 | 删除 AIMA 通用 governance Contract 副本 | #534 / AC3 | satisfied | `scripts/quality/governance_asset_contract.py` 与对应重复单测已从当前 PR 删除 |
| R4 | Requirement Source / Change 只由项目 adapter 接线 canonical validator | #534 / AC4 | satisfied | `check_pr_requirement_source.py` 已改为受管 canonical import + AIMA Carrier/API adapter |
| R5 | 项目治理 checker 不再维护三类通用 Profile | #534 / AC5 | satisfied | `check_agent_governance.py` 已收敛为 parity/CI/PR template 接线检查 |
| R6 | final-head CI 与独立 Review 无 blocker | #534 / AC6 | explicitly_deferred | PR 生命周期责任；必须在当前 Change 进入 Ready 后取得 exact-head required CI 与独立 Review，未取得前禁止 merge |
| R7 | guarded merge + main-fresh + Change Archive | #534 / AC7 | explicitly_deferred | post-merge 生命周期责任；仅 final-head Green/Review 后执行 guarded merge，并以实际 main-fresh 与 repository-native Archive 证据完成 |
| R8 | post-merge Closure Audit | #534 / AC8 | explicitly_deferred | post-merge 生命周期责任；Issue #534 保持 open，只有 main-fresh 与 archive 证据齐全后才回写 AC、重读并关闭 |

# 计划改动

- managed projections：`.agents/skills/coding/scripts/governance_contract.py`、`assets/CHANGE.template.md`、`assets/issue-templates/*.yml`。
- GitHub projections：`.github/ISSUE_TEMPLATE/*.yml`。
- project adapters：`scripts/quality/check_pr_requirement_source.py`、`check_agent_governance.py`。
- tests：更新项目消费/漂移/Requirement Source 回归；删除项目重复 canonical contract 测试。

# 验证矩阵

| 维度 | 状态 | 证据责任 |
| --- | --- | --- |
| canonical projection parity | required | root Issue Forms 与受管 assets byte parity；drift 反例 |
| Requirement Source | required | canonical live Issue 正反例 + AIMA GitHub API adapter |
| Change Carrier | required | 顶层 `changes/active` changed-scope + canonical single Change validation |
| repository quality | required | AIMA governance targeted tests、ruff |
| product backend/frontend/db/full-stack | not_applicable | 未修改产品/runtime/Contract/Schema/Data/Frontend；CI selector 以真实 diff 决定 |
| final-head Review | required | PR exact head 独立 Review |
| post-merge | required | implementation main-fresh + repository-native Change Archive + Issue Closure Audit |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | governance projection 漂移或 Carrier 接线遗漏 | byte parity + targeted regression + PR gate |
| 兼容性 | 产品行为不变 | 仅治理/CI 文件；不改 API/Schema/Data |
| 数据 / Migration | 不适用 | 无数据库/数据格式变化 |
| 部署 / 运行 | 不适用 | 不改运行时产品部署，不执行 Release/Deploy |
| 回滚 / 恢复 | 可直接 revert implementation merge | 无数据副作用 |

# 文档、依赖、部署与发布影响

- **长期文档**：AIMA `AGENTS.md` 已明确“项目只维护治理接线、不复制外部通用治理源码回归”，无需新增第二份说明。
- **依赖 / Runtime**：不升级产品依赖；仅更新治理 generated projection。
- **配置 / Secret**：不变。
- **部署 / Release**：不适用。
- **兼容 / 消费方通知**：不适用；开发 Agent 继续通过同一项目治理入口工作。

# 完成审计

- [x] upstream_re_read：已重新读取用户决定、Issue #534、AIMA 当前 AGENTS/Blueprint 06/07 与 Agent_Skills current canonical Contract。
- [x] change_coverage：AC1-AC5 已由实现覆盖；AC6-AC8 明确委托给 final-head / merge / post-merge 生命周期并保持 explicitly_deferred，没有用本 Change 把未来证据写成已完成。
- [x] reverse_audit：已从 canonical assets → managed projection → root Forms/Requirement gate/Change Carrier/CI 反向检查消费链；产品前后端/DB 边界不适用。
- [x] unresolved_cleared：无 not_satisfied；R6-R8 只因生命周期尚未发生而 explicitly_deferred，并由 open Issue #534 继续持有最终完成状态；旧版本 upgrade/migration 由用户明确排除，Release/Deploy 不在本次范围。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Agent_Skills merge `cde15e80...` | main-fresh Skill Tests run `35284850234` | success | canonical single-source Contract 与 Runtime clean-install projection 已在 Owner 仓闭环 |
| V2 | AIMA PR #535 commit `1c78e69...` | changed-file / source audit | implementation present | AIMA 已按目标结构移除重复 Owner、接入受管 projection |

## 未验证内容与剩余风险

PR body edited 与同分支 push 曾触发 concurrency 取消，因此 final head 必须重新取得一轮完整 same-SHA required CI；metadata-only 结果不能替代该完整基线。

正式 Release/Deploy、产品功能、数据库/Provider 不在本次变更边界。final-head CI/Review 与 post-merge Evidence 由对应生命周期门禁取得；在这些证据实际 Green 前不得 merge/关闭 Issue。

## 交付状态

- 提交：Red `f102c513344a85a4e9d4d9e8c57f9ae28e2c2969`；Green `1c78e69aaa123ba77215f9f2d475d9184d3c6b17`
- 拉取请求：#535
- CI：待 current ready head required CI
- 合并：待 final-head Green + Review
- Change 归档：待 merge 后 repository-native Archivist
- 发布 / 部署：不适用，本需求明确排除

## 备注

AIMA 根 Issue Forms 物理存在仅为 GitHub UI generated projection；其语义 Owner 仍是 Agent_Skills canonical assets。

CI 并发事实：head `a0b12c657da530b013739516dae51334c0967b6f` 的 synchronize full CI run `35287879772` 在 PR metadata edited run `35287919417` 之后被 concurrency 取消；该结果不作为 Green Evidence。最终候选 head 必须重新取得完整 synchronize CI，再进入 merge。
