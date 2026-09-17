---
schema: coding-change/v1
id: CHG-20260917-145702-governance-asset-machine-contract
title: 接入统一治理资产机器 Contract
level: L3
status: in_progress
owner: dingyuwen777
branch: tech/governance-asset-machine-contract
created: 2026-09-17T14:57:02+08:00
updated: 2026-09-17T14:57:02+08:00
completion_gate: required
depends_on: []
affected_areas: [project-governance, requirement-source, change-gate, ci]
affected_paths: [scripts/quality, tests/unit, .github/ISSUE_TEMPLATE, docs/blueprint]
contracts: [coding-change/v1, github-requirement-source]
data_changes: []
---

# 变更摘要

- **要解决的问题**：AIMA 当前 Issue/Change CI 门禁只覆盖部分机器结构，不足以保证不同编程 Agent 通过本地 Git 或 GitHub/API 写入时产生同一治理语义。
- **拟议修改**：让项目 Requirement Source gate 校验真实 live Issue Profile，让 changed/new Change 校验当前秒级 ID 与当前模板 Profile，并保持历史 archive 不变。
- **预期结果**：任何宿主只要进入 AIMA PR/merge 链，都必须经过同一项目机器 Contract；AIMA 只保留项目 Profile/Carrier/CI 接线，通用语义继续由 Agent_Skills canonical 拥有。

# 背景、现状与问题

## 背景

Requirement Source 为 AIMA Issue #528，并关联 Agent_Skills #252。用户要求 GPT 网页端、Codex 和其他编程 Agent 按同一个机器 Contract 生产和验收治理资产。

## 当前现状

- AIMA 已有三类 Issue Form、顶层 `changes/` carrier、Requirement-Source gate、Change Completion Gate。
- `check_pr_requirement_source.py` 当前主要确认 Issue 是否存在/可访问，不校验 live Issue 是否符合当前 Profile。
- `check_change_completion.py` 负责 AIMA carrier/legacy policy，并复用 installed Ready validator；历史 date-only Change 可合法存在。
- 项目规则禁止普通业务开发手工修改受管 `.agents` 安装资产。

## 问题、根因或约束

AIMA 项目 Profile 与 machine gate 尚未闭环：Form UI 正确不等于 API 创建的 Issue 正确，历史兼容 regex 正确不等于新的 date-only Change 也应被接受。项目需要把“当前 Profile/新建 identity”机械化，但不能复制 Agent_Skills 的整套自然语言规则。

## 不修改的后果

不同 Agent 仍可能绕过 UI/generator，创建结构或 ID 不一致的治理资产，而 PR/CI 无法稳定阻止，导致需求追溯和 Change 施工契约质量依赖宿主/模型行为。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | AIMA Issue Form 已定义三类项目 Profile | `.github/ISSUE_TEMPLATE/*.yml` | live Issue validator 应以项目 Profile 为实例化事实 |
| E2 | PR Requirement Source gate 当前只验证来源存在/可访问 | `scripts/quality/check_pr_requirement_source.py` | 需要补 live instance validation |
| E3 | Change gate 已拥有 carrier 与历史兼容政策 | `scripts/quality/check_change_completion.py` | 新建规则应在 changed/new path 上增强，不改历史 |
| E4 | managed `.agents` 资产不能由普通项目开发手改 | `AGENTS.md` | AIMA 只能做 adapter/profile/CI 接线 |
| E5 | Agent_Skills #252 正在建立 canonical machine Contract | `dingyuwen777/Agent_Skills#252` | 项目不应复制第二套通用 prose |
| E6 | 用户明确不修改历史 Change/Issue | 本轮用户 Requirement | 历史 archive/closed Issue 保持原样 |

## 推断与待确认

无阻塞待确认项；Agent_Skills canonical 若需要正式安装升级到 AIMA managed projection，必须作为独立正式升级流程处理，本任务不手改受管资产。

# 目标、成功标准与非目标

## 目标

让 AIMA 对当前 PR 使用的 Requirement Source 和新建/changed Coding Change 进行真实机器 Profile 校验，使所有编程 Agent 在项目交付边界获得同一结果。

## 成功标准

- [ ] #528 AC1–AC7 全部有直接 Evidence。
- [ ] API 创建但缺项目 Profile 的 live Issue 会被 Requirement Source gate 拒绝。
- [ ] 新 date-only Coding Change 会被 changed/new gate 拒绝，历史 archive date-only 保持合法。
- [ ] 项目 Profile/CI 与 Agent_Skills canonical responsibility 不形成第二套通用事实源。

## 范围

- `scripts/quality/check_pr_requirement_source.py`、`check_change_completion.py` 及相关 tests。
- 三类 Issue Form / project governance checker：只在 machine Profile 对齐需要时修改。
- 直接受影响的项目开发/治理文档和 CI 接线。

## 非目标

- 不修改任何历史 Change/Issue。
- 不修改 AIMA 业务 API、Schema/Migration、前端业务、Provider、部署或依赖。
- 不手改 `.agents` managed assets。
- 不发布 Agent_Skills Release。

## 必须保持不变

- 历史 archive 是不可变事实，旧 ID/旧正文不迁移。
- AIMA 顶层 `changes/` carrier 与 repository-native Change Archive 生命周期不变。
- Issue 可拥有项目额外字段；machine validator 不比较 prose 字面。
- required CI/Branch Protection/Closure Audit 不被绕过。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | AIMA 只拥有项目 Profile/Carrier/CI adapter | E4/E5 | 不复制通用 canonical prose |
| 接口与契约 | Requirement Source live Issue + new/changed Change 成为 machine gate 输入 | E1-E3 | checker/tests 需同步 |
| 数据与迁移 | 不适用：无业务数据/Schema 变化 | E6 | 无 migration |
| 错误与失败语义 | 不合规当前实例 fail closed；历史 archive 不受新 gate 回溯影响 | E3/E6 | changed/new 与 historical 分流 |
| 兼容性 | AIMA 项目 Profile 可增加字段但不能低于 canonical minimum | E1/E5 | Form/checker/tests 同步 |
| 部署与回滚 | 无生产部署；revert PR 回滚 | E6 | 无数据恢复 |

# 修改方案与决策依据

## 最小充分方案

1. 从 AIMA Issue Form 的稳定 machine field/profile 恢复 live Issue 校验规则，校验 title prefix、必需语义 headings、连续唯一 AC task list，允许额外章节。
2. 在 `check_pr_requirement_source.py` 对真实 Issue loader 返回对象执行 Profile 校验；仓库文件 Requirement Source 继续使用原路径校验。
3. 在 Change gate 只对本 PR 新增/current Change 强制秒级 ID，并从受管当前 `CHANGE.template.md` 提取顶层 Profile headings，避免项目复制通用模板正文；历史 archive 保持原兼容。
4. 加强 project governance/tests，锁定 Form/Profile/checker 之间的一致性。
5. 通过 current-head CI、Review、guarded merge、main fresh、repository-native archive 与 Closure Audit。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1/E2 | 真实 Requirement Source 必须验证实例，不能只验证 Form 文件或 Issue 存在 |
| D2 | E3/E6 | 历史兼容与新建限制必须按 Git diff/new path 分离，不能回写历史 |
| D3 | E4/E5 | 项目可读取受管 machine projection 服务 CI，但不把其正文当 AIMA 项目事实或手改 canonical |
| D4 | E1/E5 | 项目 Profile 可比 canonical 更强，但不应维护第二套通用自然语言规则 |

## 备选方案与取舍

- 仅修改 AIMA `AGENTS.md`/Prompt：无法机械阻止 API 写入，不采用。
- 复制 Agent_Skills validator 全文到 AIMA：会形成双事实源，不采用。
- 批量修历史 Issue/Change 以“统一”：违反用户范围且会改写历史，不采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | PR Requirement Source 必须验证真实 live Issue Profile | #528 / AC1 | not_satisfied | 待实现 |
| R2 | 三类 Issue machine Profile 校验稳定语义并允许扩展 | #528 / AC2 | not_satisfied | 待实现 |
| R3 | 新 Coding Change 强制秒级 ID/current Profile | #528 / AC3 | not_satisfied | 待实现 |
| R4 | 历史 archive date-only 保持兼容且不改写 | #528 / AC4 | not_satisfied | 待实现 |
| R5 | AIMA 只维护 adapter/profile/CI，不复制 canonical prose | #528 / AC5 | not_satisfied | 待实现 |
| R6 | governance tests/checkers/current-head required CI 通过 | #528 / AC6 | not_satisfied | 待实现 |
| R7 | merge 后 main fresh、Change Archive、Closure Audit 完成 | #528 / AC7 | not_satisfied | 待实现 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `scripts/quality/check_pr_requirement_source.py` | live Issue Profile validation | Requirement Source 实例一致 | R1/R2 |
| `scripts/quality/check_change_completion.py` | new ID/profile gate | 新建 Change 一致、历史兼容 | R3/R4 |
| `scripts/quality/check_agent_governance.py` / Issue Forms | 对齐 machine Profile | 防 Profile 漂移 | R2/R5 |
| `tests/unit/test_*governance*.py` | 正反例与历史兼容回归 | 防宿主/未来漂移 | R1-R6 |
| `docs/blueprint/06_开发约束与分阶段实施.md` | 必要时说明 machine contract project wiring | 长期项目事实一致 | R5 |

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [ ] 行为变化建立失败证据或说明测试例外
- [ ] 完成最小实现，不静默扩大范围
- [ ] 同步受影响的长期文档或明确不适用依据
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Requirement Source / Change gate 正反例 |
| 接口 / 契约 | required | AIMA Profile 与 Agent_Skills canonical minimum/managed machine projection 接线 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 无 DB/业务 runtime 变化 |
| 用户 / 工作流验收 | required | GitHub Issue API event / PR checker 工作流模拟 |
| 跨组件关键路径 | required | Issue/Change → project checker → CI gate |
| 外部依赖 / 供应方探测 | not_applicable | 不调用 Provider/生产外部服务 |
| 构建 / 打包 / 运行 | not_applicable | 无产品 build/runtime 变化；CI 自身按 changed scope 运行治理证据 |
| 文档 / 治理 / 其他 | required | Form/Profile/governance docs/CI/Change lifecycle |

## 验证计划

- 目标测试：`test_pr_requirement_source.py`、`test_change_completion.py`、`test_issue_acceptance_profile.py`、`test_agent_governance.py`。
- 相关回归：项目 governance checker 与 CI workflow current-head。
- 静态检查或构建：Ruff/仓库 project-quality profile 由 CI classifier 决定。
- 专项真实边界：GitHub live Issue/PR source readback 与项目 required CI。
- 就绪检查：`scripts/quality/check_change_completion.py --root .` 的 PR/main 现有入口。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | validator 误挡合法 Issue 或误伤历史 Change | 仅稳定 machine semantics；new/changed scope；历史兼容回归 |
| 兼容性 | 新实例收紧、历史保持 | #528/E3/E6 |
| 数据 / Migration | 不适用 | 无 Schema/数据变化 |
| 部署 / 运行 | 不适用 | 只改治理脚本/Profile/CI |
| 回滚 / 恢复 | revert 本 PR | 无数据恢复 |

# 文档、依赖、部署与发布影响

- **长期文档**：如 machine Contract 改变项目开发闭环，则同步 Blueprint 06；不复制 Agent_Skills Reference 正文。
- **依赖 / Runtime**：不新增/升级依赖，不手改 Runtime/managed assets。
- **配置 / Secret**：不适用。
- **部署 / Release**：不适用，无生产 Release/Deploy。
- **兼容 / 消费方通知**：所有 AIMA 编程 Agent/PR 成为直接消费者；历史资产不迁移。

# 完成审计

- [ ] upstream_re_read：Ready 前重新读取 #528、Agent_Skills #252、AIMA AGENTS/Blueprint 与实际实现。
- [ ] change_coverage：逐项核对 AC1–AC7，没有把当前 Change 当需求全集。
- [ ] reverse_audit：反查 Issue Form→live validator→PR gate 与 Change template→new gate→archive compatibility。
- [ ] unresolved_cleared：Ready 前清零 not_satisfied，延期/N/A 有正式依据。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | AIMA baseline `7f1ca524` | AGENTS/Blueprint/Issue Form/checker/CI readback | 已完成 | 确认项目现状与边界 |
| V2 | Agent_Skills main `ab78777a` | canonical Reference/tooling readback | 已完成 | 确认通用 machine contract 修改目标 |

## 未验证内容与剩余风险

实现、targeted tests、Review、PR CI、merge/main fresh 与自动归档尚未执行，当前不可声明完成或可合并。

## 交付状态

- 提交：已建立首个 Change commit。
- 拉取请求：待创建早期 PR。
- CI：待 PR 触发。
- 合并：未执行。
- Change 归档：未执行。
- 发布 / 部署：不适用。

## 备注

本 Change 只拥有 AIMA_UGC 项目接线；Agent_Skills canonical 修改由 `dingyuwen777/Agent_Skills#252` 和其独立 Change/PR 承担。