---
schema: coding-change/v1
id: CHG-20260917-145702-governance-asset-machine-contract
title: 接入统一治理资产机器 Contract
level: L3
status: ready_for_review
owner: dingyuwen777
branch: tech/governance-asset-machine-contract
created: 2026-09-17T14:57:02+08:00
updated: 2026-09-17T15:46:00+08:00
completion_gate: required
depends_on: []
affected_areas:
  - project-governance
  - requirement-source
  - change-gate
  - ci
affected_paths:
  - scripts/quality
  - tests/unit
  - .github/ISSUE_TEMPLATE
contracts:
  - coding-change/v1
  - github-requirement-source
data_changes: []
---

# 变更摘要

- **要解决的问题**：AIMA 的 Issue/Change 门禁此前不能保证网页端、Codex 或其他 Agent 通过不同写入通路时产生同一治理语义。
- **拟议修改**：live Requirement Source 按项目 Issue Form Profile 校验；本 PR 新增或修改的 Active Change 按当前秒级 ID 与受管 Change 模板 Profile 校验；历史 archive 不参与 current Profile 扫描。
- **预期结果**：宿主只影响写入方式，进入 AIMA PR/merge 链的治理资产必须满足同一机器 Contract。

# 背景、现状与问题

## 背景

Requirement Source 为 #528；跨仓 canonical 工作由 `dingyuwen777/Agent_Skills#252` 独立治理。用户明确要求 GPT 网页端、Codex 和其他编程 Agent 按同一个机器 Contract 生产和验收治理资产，同时不修改历史 Change/Issue。

## 当前现状

AIMA 已有三类 Issue Form、顶层 `changes/` carrier、Requirement-Source gate、Change Completion Gate 和 repository-native Change Archive。本次实现新增项目机器 adapter：Issue Profile 从当前 `.github/ISSUE_TEMPLATE/*.yml` 动态恢复；Change Profile 从当前受管 `CHANGE.template.md` 动态恢复。

## 问题、根因或约束

Form UI 或 generator 只能约束经过该入口的创建动作；API/Contents/Git Data 等写入可以绕过 UI。此前 PR gate 又主要确认 Issue 存在、Change Ready 只校验部分结构，因此治理结果仍依赖宿主行为。

## 不修改的后果

不同 Agent 可持续形成标题、必需语义段、Acceptance 或 Change ID/结构不一致的治理资产，并在部分情况下通过既有门禁，降低需求追溯与协作可信度。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 三类 Issue Form 是 AIMA 项目 UI/Profile 事实 | `.github/ISSUE_TEMPLATE/*.yml` | live Issue 校验从项目 Form 动态恢复 |
| E2 | PR #529 current head 的 live Requirement Source #528 已通过机器校验 | CI run `35195429492` / step `Verify PR Requirement Source` | API/网页路径已受真实 gate 约束 |
| E3 | 同一 CI 的项目治理 wiring 检查已通过 | run `35195429492` / `Verify AIMA project governance wiring` | Form/checker/CI 接线有效 |
| E4 | current head 的 Runtime Acceptance 已成功 | run `35195429256` | 未破坏当前 Runtime 接线 |
| E5 | PR gate 仅扫描 `changes/active` 的 A/M 路径，archive 不参与 | `scripts/quality/governance_asset_contract.py` + 对应回归 | 历史不迁移、不改写 |
| E6 | 本 PR 未修改业务 API、Schema/Migration、Provider、前端业务或依赖 | PR #529 changed files | 兼容/数据/部署边界不变 |

## 推断与待确认

完整 repository-quality、后端、前端、PostgreSQL 与 Real Full-stack CI 将在本 Change 进入 `ready_for_review` 后由现有 classifier 执行；这些是 merge 前 delivery evidence，不在这里伪装成已有结果。

# 目标、成功标准与非目标

## 目标

让 AIMA 的 live Requirement Source 与 Active Change 在不同宿主写入后都接受同一项目 machine Profile 验证，并保持 Agent_Skills canonical 与 AIMA Overlay 的 Ownership 分离。

## 成功标准

- [x] live GitHub Requirement Source 不再只验证“存在”，而会验证项目 Profile。
- [x] 需求/缺陷/技术变更 Profile 由当前 Issue Form 动态恢复，稳定 AC task list 由机器检查。
- [x] 本 PR 新增或修改的 Active Change 使用当前秒级 identity/模板 Profile；archive 历史不参与该扫描。
- [x] AIMA 项目层只维护 Profile/Carrier/CI adapter，不复制 Agent_Skills 完整自然语言规则。
- [ ] merge 前 required CI 取得最终 current-head 成功证据。
- [ ] merge 后 main-fresh、repository-native archive 与 Requirement Closure 完成。

## 范围

- `.github/ISSUE_TEMPLATE/01-requirement.yml`、`02-bug.yml`、`03-technical-change.yml`。
- `scripts/quality/check_pr_requirement_source.py`、`governance_asset_contract.py`、`check_agent_governance.py`。
- 对应治理单元回归与本 Change。

## 非目标

- 不修改任何历史 archived Change 或已关闭 Issue。
- 不修改业务 API、Schema/Migration、Provider、前端业务、部署、依赖版本。
- 不手改受管 `.agents` 安装资产。
- 不发布 Agent_Skills Release。

## 必须保持不变

- AIMA 顶层 `changes/` carrier 与 repository-native archive 生命周期。
- 历史 archive identity/正文。
- required CI、Branch/PR gate 与 Closure Audit。
- 项目可在 canonical minimum 上增加更强字段。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Agent_Skills 拥有通用 canonical；AIMA 拥有项目 Profile/Carrier/CI adapter | #528、Agent_Skills #252 | 不建立第二套通用 prose |
| 接口与契约 | machine gate 输入为 live Issue 与 Active Change | E1-E5 | 不改变产品 HTTP Contract |
| 数据与迁移 | 不适用 | E6 | 无 Schema/Migration/数据回填 |
| 错误与失败语义 | 不合规 current 治理资产 fail closed | E2/E5 | PR 在 Ready/merge 前被阻断 |
| 兼容性 | current 实例收紧；archive 历史保持 | 用户范围、E5 | 不进行历史迁移 |
| 部署与回滚 | 无生产部署；通过 revert PR 回滚 | E6 | 无数据恢复步骤 |

# 修改方案与决策依据

## 最小充分方案

1. Issue Profile 直接从项目 Forms 的 title prefix 与 required textarea labels 恢复；AC 使用连续唯一 task list 机器判据。
2. PR Requirement Source loader 读取真实 live Issue 后调用同一 Project Profile validator。
3. Active Change Profile 从受管 `CHANGE.template.md` 动态恢复；PR base→head 的 A/M Active Change 重新校验 current 秒级 identity、模板结构和 L3 方案取舍入口。
4. `changes/archive/**` 不进入 current Profile diff；历史不迁移。
5. 用项目治理 checker、单元回归、current-head CI、Runtime Acceptance、merge/main/archive/closure 完成交付。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1/E2 | 验证 live 实例，而不是只相信 Form/UI |
| D2 | E5 | 只对 Active A/M current 实例收紧，满足历史不可变要求 |
| D3 | E1/E3 | Profile 从项目事实恢复，避免 Python 再维护一份字段表 |
| D4 | E6 | 不扩大到产品 Runtime/API/Schema 或依赖变更 |

## 备选方案与取舍

- **只强化 Prompt/AGENTS**：不能机械阻止 API/直接文件写入，不能满足目标。
- **复制 Agent_Skills 全套 validator/prose**：会形成双事实源，后续仍会漂移。
- **批量迁移历史**：违反用户明确范围，也会改写审计事实。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | live Requirement Source 必须通过真实 Issue Profile 校验 | #528 / AC1 | satisfied | CI `35195429492` 的 `Verify PR Requirement Source` 已通过 |
| R2 | 三类 Issue 校验标题、必需语义段与稳定 AC，并允许额外字段 | #528 / AC2 | satisfied | Forms + `governance_asset_contract.py` + `test_pr_requirement_source.py` / `test_governance_asset_contract.py` |
| R3 | 本 PR 新增/修改 Active Change 强制 current 秒级 ID/Profile | #528 / AC3 | satisfied | PR gate 已实际校验本 Change；A/M gate 与正反例已实现 |
| R4 | 历史 archive 不迁移、不进入 current Profile 扫描 | #528 / AC4 | satisfied | scanner 仅限定 `changes/active`；archive exclusion regression 已加入 |
| R5 | AIMA 只维护项目 Profile/Carrier/CI adapter | #528 / AC5 | satisfied | PR changed files 无 Agent_Skills canonical Reference/managed `.agents` 修改 |
| R6 | 完整 current-head required CI | #528 / AC6 | not_applicable | 属于 `ready_for_review` 后的 PR delivery gate，由 GitHub Actions/CI Gate 持有；不作为 Change pre-Ready 自证 |
| R7 | main-fresh、archive、Closure | #528 / AC7 | not_applicable | 属于 merge 后 delivery/Requirement Closure owner；Change Ready 不能预先伪造这些事实 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Issue Forms | 与当前 machine semantics 对齐 | API/UI 同效 | R1/R2 |
| `check_pr_requirement_source.py` | live Issue + Active Change gate | 交付时不可绕过 | R1/R3 |
| `governance_asset_contract.py` | 项目 Profile adapter | 单一项目 machine adapter | R2-R5 |
| `check_agent_governance.py` | 锁定 Form/Profile 项目接线 | 防项目漂移 | R2/R5 |
| governance unit tests | 正反例、A/M 与 archive 边界 | 防未来回归 | R1-R5 |

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 建立正反例治理回归
- [x] 完成最小实现，不扩大到业务代码
- [x] 文档影响审计：现有 Blueprint 06 的“项目治理接线/通用规则不复制”原则仍成立；本 PR 的精确机器字段由脚本/Form 自身维护，不新增第二份易漂移文档
- [x] 取得 machine gate 与 Runtime Acceptance 当前证据
- [x] 完成需求追溯与 pre-Ready 反向审计

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Issue/Change validator 正反例；PR Ready 后由 CI 执行完整 targeted/unit profile |
| 接口 / 契约 | required | Form → Project Profile → PR checker；current Change template/Profile |
| 集成 / 持久化 / 运行依赖 | not_applicable | 无数据库/业务运行依赖变化 |
| 用户 / 工作流验收 | required | GitHub live Issue / PR machine gate，已在 CI `35195429492` 真实执行 |
| 跨组件关键路径 | required | Issue/Change → project checker → CI；Runtime Acceptance `35195429256` success |
| 外部依赖 / 供应方探测 | not_applicable | 无 Provider/远端业务事实需要探测 |
| 构建 / 打包 / 运行 | required | repository full CI 在 Ready 后执行；Runtime Acceptance 当前 head 已 success |
| 文档 / 治理 / 其他 | required | project governance wiring、Change Ready、PR/main/archive/Closure lifecycle |

## 验证计划

- 目标：治理单元测试、project governance checker、Requirement Source / Active Change gate。
- PR Ready 后：repository full profile（当前 changed scope 已分类为 full）。
- Runtime：Runtime Acceptance 已 success，后续 head 变化按 fresh-evidence 规则复核。
- 交付：guarded merge、main-fresh CI、repository-native Change Archive、Closure Audit。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | validator 误挡合法 current Issue/Change | Profile 从项目 Forms/template 恢复，正反例覆盖 |
| 兼容性 | 新/current 治理资产更严格；历史 archive 不变 | active-only A/M scanner |
| 数据 / Migration | 不适用 | 无 DB/Schema/data change |
| 部署 / 运行 | 不改变生产部署 | 治理脚本/Profile only |
| 回滚 / 恢复 | revert implementation PR | 无数据迁移 |

# 文档、依赖、部署与发布影响

- **长期文档**：不新增第二份 machine field 清单；现有 Blueprint 06 的项目/通用治理 Ownership 原则保持有效。
- **依赖 / Runtime**：无依赖或 Runtime 升级；未手改受管 `.agents`。
- **配置 / Secret**：不适用。
- **部署 / Release**：不执行部署/Release。
- **兼容 / 消费方通知**：对开发 Agent 的治理资产输入更严格；业务调用方无变化。

# 完成审计

- [x] upstream_re_read：已重新读取用户要求、#528、AIMA 项目规则及 Agent_Skills 当前 canonical Owner。
- [x] change_coverage：AC1–AC5 均进入实现与直接证据；AC6/AC7 明确由后续 delivery/closure owner 承担，没有伪造 pre-Ready 结果。
- [x] reverse_audit：已反查 Form → Profile → live Issue gate、template → Active A/M gate、archive exclusion、项目 CI wiring 与 Runtime 边界。
- [x] unresolved_cleared：当前 Change 施工范围无 `not_satisfied`；后续 PR/main 生命周期作为下游 gate 保持未执行状态。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | PR #529 head `413ca26b` | CI run `35195429492` / Requirement Source step | success | live #528 Project Profile 与本 Change current Profile 均被真实读取校验 |
| V2 | PR #529 head `413ca26b` | `check_agent_governance.py` | success | 项目治理 wiring 与 Forms 接线合法 |
| V3 | PR #529 head `413ca26b` | Runtime Acceptance run `35195429256` | success | 当前 Runtime Acceptance 未回归 |
| V4 | PR #529 current diff | changed-files 审计 | success | 未修改历史 archive、业务 API/Schema/Migration、依赖或受管 `.agents` |

## 未验证内容与剩余风险

完整 repository full CI 将由本次 `ready_for_review` 提交触发；未取得该 current-head 证据前不得合并。main-fresh、Change Archive、Issue Closure 只能在 merge 后取证。

## 交付状态

- 提交：实现与治理提交已在 `tech/governance-asset-machine-contract`。
- 拉取请求：#529，进入评审就绪；仍需新的 current-head required CI。
- CI：已有 machine gate/Runtime 证据；完整 full profile 待本提交触发。
- 合并：未执行。
- Change 归档：未执行，由 repository-native archivist 在 merge 后负责。
- 发布 / 部署：不适用。

## 备注

本 Change 只拥有 AIMA 项目接线；Agent_Skills canonical 修改由其独立 Issue/Change/PR 管理。
