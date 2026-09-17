---
schema: coding-change/v1
id: CHG-20260918-070619-governance-canonical-source
title: AIMA 消费 Agent_Skills 单一治理资产 canonical source
level: L3
status: proposed
owner: dingyuwen777
branch: refactor/governance-canonical-source
created: 2026-09-18T07:06:19+08:00
updated: 2026-09-18T07:06:19+08:00
completion_gate: required
depends_on: []
affected_areas: [governance, ci, agent-skills-projection]
affected_paths: [.github/ISSUE_TEMPLATE, .agents/skills/coding/assets, .agents/skills/coding/scripts/governance_contract.py, scripts/quality, tests/unit]
contracts: [governance-assets, requirement-source, coding-change]
data_changes: none
---

# 变更摘要

- **要解决的问题**：AIMA 仍复制通用 Issue/Change machine Contract，形成第二维护源。
- **拟议修改**：把通用模板/Profile/validator 收敛为 Agent_Skills installed canonical projection；AIMA 只保留 Carrier、GitHub API、CI adapter。
- **预期结果**：以后通用治理规则只改 Agent_Skills；AIMA 的 generated projection 与薄 adapter 由机器校验，不再重复维护。

# 背景、现状与问题

## 背景

用户要求 Change 模板和 Issue 模板源头只在 Agent_Skills 维护一份，并明确本次按首次安装处理、不承担旧版本升级兼容。

## 当前现状

AIMA 根 Issue Forms 与 `scripts/quality/governance_asset_contract.py`、`check_agent_governance.py` 仍复制通用字段/Profile/正则；AIMA top-level `changes/`、GitHub API loader、CI workflow 属于项目自有事实。

## 问题、根因或约束

Source Mode 解决规则从哪里读取，但若目标项目仍复制通用 validator/Profile，后续修改仍要跨仓库同步。根因是项目 adapter 过厚。

## 不修改的后果

Agent_Skills canonical 变化后 AIMA 可能继续接受旧格式或拒绝新格式，GPT/Codex/其他 Agent 仍可能得到宿主相关差异。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Agent_Skills 已完成 #256/#257，Issue Forms/Change Template/validator 只有 canonical Owner | Agent_Skills merge cde15e80c081844e74e992ac126707cf36fc4c6c | AIMA 应消费而非复制 |
| E2 | AIMA 使用 top-level `changes/` Carrier | AIMA AGENTS.md / CI | Carrier 必须继续项目自有 |
| E3 | AIMA 当前项目脚本仍复制 Issue Profile/通用正则 | scripts/quality 当前 main | 需要薄 adapter |
| E4 | 用户明确排除 upgrade/backcompat | 本轮用户决定 / #531 | 不实现迁移分支 |

## 推断与待确认

无。

# 目标、成功标准与非目标

## 目标

AIMA 的通用治理资产全部来自 Agent_Skills canonical projection，项目只拥有 Carrier/CI/API adapter。

## 成功标准

- [ ] 根 Issue Forms 与 installed canonical assets 原字节一致。
- [ ] AIMA 项目 adapter 不再定义通用 Change/Issue/AC/Profile 规则。
- [ ] top-level Change Carrier、CI 与 live GitHub Issue 读取继续正常工作。
- [ ] project governance CI 能稳定拒绝 projection drift。

## 范围

- installed canonical governance projection；
- 根 Issue Forms；
- scripts/quality 治理 adapter；
- 对应 unit/CI 回归。

## 非目标

- 不修改历史 Issue/Archive；
- 不改变业务 Product/API/Schema/Data；
- 不做 Agent_Skills upgrade migration；
- 不 Release/Deploy。

## 必须保持不变

- AIMA top-level `changes/` Carrier；
- Requirement Source live GitHub Issue 校验；
- repository-native Change Archive；
- 现有产品/数据库/前端/部署行为。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Agent_Skills owns generic; AIMA owns adapter/carrier | E1-E3 | 删除重复 Owner |
| 接口与契约 | 治理 machine Contract 由 installed canonical validator 提供 | #531 | 项目脚本仅转发 |
| 数据与迁移 | 不适用 | 无业务数据变化 | 无 Migration |
| 错误与失败语义 | projection/validator 缺失或漂移 fail closed | #531 / Agent_Skills canonical | CI 阻塞 |
| 兼容性 | 仅当前 canonical 首次安装结果 | E4 | 不做旧版兼容 |
| 部署与回滚 | revert PR | 仅仓库治理文件 | 无生产部署 |

# 修改方案与决策依据

## 最小充分方案

1. 把 Agent_Skills main 的 canonical Change Template、Issue Forms、governance validator 投影到 AIMA installed `.agents`。
2. 根 `.github/ISSUE_TEMPLATE` 写成 canonical Issue Forms 的原字节 projection。
3. 把 `governance_asset_contract.py` 改为 installed canonical validator 的薄 adapter，只保留 AIMA Carrier 包装。
4. 把 `check_agent_governance.py` 中通用 Profile/字段检查替换为 projection parity + AIMA 项目接线检查。
5. 调整 unit tests，证明 delegation/drift/live gate，并保持项目 CI/Archive 不变。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1/E3 | 只有删除项目重复语义才能真正单一维护 |
| D2 | E2 | Carrier 是项目事实，不能移入通用 Skill |
| D3 | E4 | 不为未要求的历史版本增加复杂度 |

<!-- governance:required-for=L3 -->
## 备选方案与取舍

- 继续在 AIMA 复制同内容 validator/Profile：维护简单但仍双维护，不采用。
- CI 在线读取 Agent_Skills：引入网络和跨仓库可用性依赖，不采用。
- 使用 installed canonical projection + thin adapter：离线、可验证、职责清晰，采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 根 Issue Forms 是 canonical projection | #531 / AC1 | not_satisfied | 待实现 |
| R2 | 项目治理 Contract 变薄并委托 canonical validator | #531 / AC2 | not_satisfied | 待实现 |
| R3 | live Requirement Source/Change machine validation 继续委托统一 Contract | #531 / AC3 | not_satisfied | 待实现 |
| R4 | project governance 不再维护通用 Profile | #531 / AC4 | not_satisfied | 待实现 |
| R5 | top-level Carrier/Archive 不变 | #531 / AC5 | not_satisfied | 待验证 |
| R6 | 永久正反例、无网络/升级迁移 | #531 / AC6 | not_satisfied | 待实现/验证 |
| R7 | final-head CI/Review/merge | #531 / AC7 | not_satisfied | 交付阶段 |
| R8 | main-fresh/archive/Closure | #531 / AC8 | not_satisfied | merge 后 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| .agents/skills/coding/assets + scripts/governance_contract.py | 投影 Agent_Skills canonical | installed single source | R1-R3 |
| .github/ISSUE_TEMPLATE | 原字节投影 | GitHub UI 需要物理文件 | R1 |
| scripts/quality/governance_asset_contract.py | 薄 adapter | 删除通用规则复制 | R2/R3 |
| scripts/quality/check_agent_governance.py | project wiring + parity | 删除 Profile 清单 | R4/R5 |
| tests/unit | delegation/drift regression | 永久证据 | R1-R6 |

- [x] 调查当前实现和事实源；新建项目则确认现有资料、目标和硬约束
- [x] 建立与风险相称的任务路由和验证矩阵
- [ ] 行为变化建立失败证据或说明测试例外
- [ ] 完成最小实现，不静默扩大范围
- [ ] 同步受影响的长期文档或明确不适用依据
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | adapter delegation、projection drift、project governance |
| 接口 / 契约 | required | live Issue/Change machine Contract |
| 集成 / 持久化 / 运行依赖 | not_applicable | 无业务 DB/运行依赖变化 |
| 用户 / 工作流验收 | not_applicable | 无产品 UI/业务工作流变化 |
| 跨组件关键路径 | required | PR gate → canonical adapter → live Requirement/Change |
| 外部依赖 / 供应方探测 | not_applicable | GitHub CI 的 existing loader 有既有覆盖，不新增外部 Provider |
| 构建 / 打包 / 运行 | not_applicable | 不改变 AIMA 产品 build/runtime |
| 文档 / 治理 / 其他 | required | projection parity、Carrier、CI/Archive |

## 验证计划

- 目标测试：governance adapter / project governance / requirement source unit tests。
- 相关回归：AIMA repository quality 与 changed-scope CI。
- 静态检查或构建：Ruff/mypy（由 CI selector 决定）。
- 专项真实边界：PR live Requirement Source + Change Ready。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | adapter 仍复制规则或 projection 漂移 | source scan + parity tests |
| 兼容性 | 当前 canonical only | 用户明确排除旧版升级兼容 |
| 数据 / Migration | 不适用 | 无 Schema/Data |
| 部署 / 运行 | 不适用 | 无产品 Runtime/Deploy |
| 回滚 / 恢复 | revert PR | 无不可逆数据副作用 |

# 文档、依赖、部署与发布影响

- **长期文档**：AGENTS 已明确安装资产非项目事实源；预计无需新增项目产品文档，若实现发现导航需同步再补。
- **依赖 / Runtime**：不升级项目运行依赖；只更新治理 projection。
- **配置 / Secret**：不适用，无新配置/Secret。
- **部署 / Release**：不适用，用户未要求且无产品运行变化。
- **兼容 / 消费方通知**：治理 adapter 行为由 CI/Agent 消费，不改变业务调用方。

# 完成审计

- [ ] upstream_re_read：完成前重新读取 #531 与当前 canonical Rules。
- [ ] change_coverage：确认覆盖 AC1-AC8。
- [ ] reverse_audit：确认 generic→projection→project adapter→CI/Archive 无第二 Owner。
- [ ] unresolved_cleared：Ready 前清零 not_satisfied；AC7/AC8 按交付 lifecycle 处理。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 待实现 | targeted tests / CI | 待执行 | 待补 |

## 未验证内容与剩余风险

- 实现、final-head CI/Review、main-fresh/archive/Closure 待后续阶段取得。

## 交付状态

- 提交：首个 Change commit 待创建
- 拉取请求：待创建
- CI：待执行
- 合并：待执行
- Change 归档：待 merge 后 repository-native Archivist
- 发布 / 部署：不适用；本任务仅治理代码与生成投影。

## 备注

由于当前宿主容器 DNS 无法访问 GitHub，不能使用普通本地 git push；为遵守“不先创建远程空分支”，首个远程 ref 将直接指向包含本 Change 的首提交。
