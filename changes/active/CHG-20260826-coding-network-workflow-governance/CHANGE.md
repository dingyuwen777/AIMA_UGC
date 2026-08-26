---
schema: rvc-change/v1
id: CHG-20260826-coding-network-workflow-governance
title: Coding 网络源选择与 Workflow 证据守恒治理
level: L2
status: ready_for_review
owner: dingyuwen777
branch: feature/coding-network-workflow-governance
created: 2026-08-26
updated: 2026-08-26
completion_gate: required
depends_on: []
affected_areas:
  - agent-governance
  - developer-tooling
affected_paths:
  - .agents/skills/coding/SKILL.md
  - .agents/skills/coding/README.md
  - .agents/skills/coding/references/03_编程语言与工具链适配规则.md
  - .agents/skills/coding/references/07_通用验证与证据策略.md
  - .agents/skills/coding/references/08_分层测试与验收策略.md
  - .agents/skills/coding/references/12_规则保留映射.md
  - .agents/skills/coding/tests/test_network_and_workflow_governance.py
contracts: []
data_changes: false
---

# 目标

把两条通用研发治理要求固化进 Coding Skill：

1. 涉及 Runtime/依赖安装、启动或初始化脚本、容器/镜像构建、CI bootstrap、部署环境准备等网络下载时，根据真实执行环境选择下载源；中国大陆网络优先联网核验当前稳定可信的国内镜像，但不机械影响海外/GitHub Hosted 环境，也不改变软件身份、锁定版本和完整性边界。
2. 新增/修改永久 CI/Workflow，或发现现有 Workflow 明显重复、无关触发、成本过高时，先建立测试目的和证据责任映射，再在证据守恒前提下通过触发范围、fast path、缓存/复用、分层和 Golden Path 收敛降低成本；禁止为了更快删除独立验证能力或用较弱测试冒充较强证据。

# 成功标准

- [x] `SKILL.md` 有两条可直接触发的硬规则，并明确展开细节所在 reference。
- [x] `03_编程语言与工具链适配规则.md` 完整说明网络位置判断、实时联网核验、国内候选源、供应链身份/锁/hash/digest、可覆盖/fallback、安全更新与失效镜像处理。
- [x] `07_通用验证与证据策略.md` 定义 Workflow Responsibility Audit、Evidence Preservation Mapping、允许的降本手段与不得降低的证据等级。
- [x] `08_分层测试与验收策略.md` 把 Web/API/PostgreSQL/Full-stack/Provider 的 CI 成本控制落实到现有分层职责，不重复穷举同一状态空间。
- [x] `12_规则保留映射.md` 固化两条新规则的 canonical 位置，防止未来“精简”丢失触发条件、例外和验证责任。
- [x] `coding/README.md` 补充人类可读使用说明，但不形成第二套正式规则。
- [x] 回归测试先在旧规则上失败，再在实现后通过，并证明 Review/Docs 路由等既有 Coding 内容未被破坏。
- [x] 本 Change 不修改 AIMA 当前 `.github/workflows/*.yml`；Workflow 实际重构留给独立任务。
- [ ] `ready_for_review` 最终 HEAD 的 Ready Check、PR CI/Runtime/Full-stack/Change Gate 全部取得新鲜成功证据后再合并；此项属于 Ready 状态提交后的机器交付门禁。

# 范围

- Coding 主 Skill 的条件式硬规则。
- 工具链/网络源选择 reference。
- 通用验证和 Web 分层测试 reference 中的 Workflow 治理规则。
- 规则保留映射和 Coding README。
- 针对新规则的回归测试。
- Change、Review、Docs Impact、PR/CI 和正常合并/归档闭环。

# 非目标

- 不重构或删除 AIMA 当前任何 GitHub Actions Workflow。
- 不改变 AIMA 当前 Dockerfile/Compose/Release 的既有国内/海外源策略。
- 不固定一个永久有效的国内镜像地址列表，也不把阿里云、清华、中科大、网易或其他镜像写成永远可用。
- 不引入新的镜像代理服务、依赖、CI 平台或测试框架。

# 必须保持不变

- Coding 既有四维路由、L1-L3、Change、Requirement Traceability、Completion Audit、TDD/根因调试、Validation Matrix、Review/Docs 路由、Git/安全/中文注释/北京时间/日志规则完整保留。
- 测试层的证明边界不因 Workflow 优化而降低：Mock 不能冒充真实依赖，Unit 不能冒充 Integration，单层绿色不能替代 Golden Path/外部 Probe 等独立风险证据。
- 仓库和项目自身的锁文件、软件版本、官方 canonical image identity、checksum/hash/digest、签名/校验机制不因下载加速而改变。
- 上位项目规则和现有 Source/Registry policy 优先；普通任务不得静默升级依赖或切换技术栈。

# 关键决策

1. 主 `SKILL.md` 只保留两条硬触发器和 reference 路由，避免继续膨胀；详细执行规则分别归入 `03`、`07`、`08`。
2. “国内源”是环境感知策略：只有目标执行环境处于中国大陆网络或任务明确要求中国大陆可用性时才优先国内源；海外/GitHub Hosted 等环境不机械切换。
3. 国内镜像必须在执行相关改动时联网核验当前官方帮助/状态/同步信息；阿里云、清华 TUNA、中科大 USTC、npmmirror 等只作为候选例子，不是永久白名单。
4. 镜像/代理原则上只改变传输路径，不改 canonical 软件/镜像身份；包管理器会把 index 写入 lock 时，必须避免静默产生无关 lock 漂移。
5. Workflow 精简先做证据责任审计，再做结构调整；删除/合并前必须能给出“原证明责任 → 新位置”的 Evidence Preservation Mapping。
6. 本 Change 只修改 Skill，不把 AIMA 当前 Workflow 优化混入同一个 Change。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 涉及启动脚本、依赖/Runtime 安装、镜像构建等网络下载时，在中国大陆环境联网查询当前稳定国内源并合理替换 | user:current-request | satisfied | `SKILL.md` §11 + `03_编程语言与工具链适配规则.md`“网络下载源与镜像选择”；Green HEAD `03e92d50757bf75e67dc741181deb5cffb81c010` |
| R2 | 国内源选择不能静态绑定历史地址，应考虑执行环境、当前可用性、供应链身份和完整性 | user:current-request | satisfied | `03` 明确目标环境、官方帮助/同步状态、候选非永久白名单、canonical/lock/checksum/hash/digest/signature/security/fallback；2026-08-26 当前镜像站事实调查支持实时核验必要性 |
| R3 | Coding 应评估永久 Workflow 是否过重、重复或无关触发，并在不丢测试目的的前提下精简 | user:current-request | satisfied | `SKILL.md` §11 + `07_通用验证与证据策略.md` Workflow Responsibility Audit；明确触发条件和 path/event/changed-scope/fast path/cache/artifact/阶段分责等降本手段 |
| R4 | Workflow 精简不得过分总结或降低原测试证明范围，必须保持证据责任可追溯 | user:current-request | satisfied | `07` Evidence Preservation Mapping + `08` 五层专项证明边界 + `12` 规则保留映射；较弱证据不得冒充较强证据 |
| R5 | 主 Skill 保留硬触发器，详细规则按既有职责放 `03`、`07`、`08`，避免主文件过度膨胀 | user:approved-plan | satisfied | PR #243 的 `SKILL.md` patch 仅末尾新增 §11；详细网络/Workflow/Web 专项规则分别位于 03/07/08 |
| R6 | 更新规则保留映射和使用说明，防止后续精简再次丢失 | user:approved-plan | satisfied | `12_规则保留映射.md` §13 + `coding/README.md` §11；README 明确只做使用说明，正式规则仍由 Skill/reference 承载 |
| R7 | 本次只改 Skill，不顺手重构 AIMA Workflow，并通过正常 PR/CI 路径交付 | user:current-request | satisfied | PR #243 当前 changed files 仅 Change、Coding Skill/README/references/test；无 `.github/workflows/*.yml`；Draft PR 已建立，最终合并仍受 Ready/CI 门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 新回归先在 Red HEAD `37e0a92e8e90eb25ff38d57f492cc5dbbe091838` 的 Change Gate 中按预期失败；Green HEAD `03e92d50757bf75e67dc741181deb5cffb81c010` 的 `Run Coding completion-gate tests` 成功，36 个 Coding 规则测试全通过 |
| 接口 / Contract | not_applicable | 不修改产品 public API/ABI/Schema/格式；Skill 文本规则由治理测试覆盖 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改产品运行时、数据库或依赖集成 |
| 用户 / Workflow Acceptance | not_applicable | 不改变产品用户工作流；人类 Skill 使用说明已完成 Docs targeted review |
| 跨组件 Golden Path | not_applicable | 不改变产品跨组件接线；现有 Full-stack 仍由仓库永久门禁独立运行 |
| External Dependency / Provider Probe | required | 2026-08-26 当前一手镜像站资料确认清华 TUNA、阿里云、USTC PyPI 等当前服务状态；USTC Docker Hub 帮助明确镜像缓存已关闭，证明静态历史镜像清单不可作为永久事实；无付费/写入操作 |
| Build / Package / Runtime | not_applicable | 不修改实际构建、镜像或 Runtime 行为 |
| Docs / Governance / Other | required | PR patch 内容守恒复核；Docs targeted review 无阻塞；Review Skill 独立审查无阻塞；Green HEAD Runtime/Full-stack/CI success，Change Gate 规则测试 success 且仅因 Change 尚未 Ready 失败 |

# Completion Audit

- [x] upstream_re_read：重新读取本轮用户批准方案、当前 `AGENTS.md`、Coding 主规则、03/07/08/12、README、现有 Review/Docs 路由和相关测试；未以本 Change 自身作为需求全集。
- [x] change_coverage：两条上游要求、环境感知例外、证据守恒、不过度总结，以及“只改 Skill、不改 AIMA Workflow”均进入 R1-R7 与成功标准。
- [x] reverse_audit：从 `SKILL.md` §11 反向可达 03/07/08；12 固化 canonical 位置；README 提供使用导航；新增测试同时保护 Review/Docs/Red→Green/中文提交/北京时间/`强制其他序列化形式` 等既有高价值规则；PR patch 未发现既有正文被改写。
- [x] unresolved_cleared：R1-R7 均已满足；required Validation 已有 Green/外部当前事实/Docs/Review 证据。Ready 状态提交后的最终机器门禁作为合并前交付检查继续执行。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立四维任务路由：Infra/Build/Release Tooling + Governance / Rule change / Markdown+Python tests / L2
- [x] 建立失败测试并 Verify Red
- [x] 在 `SKILL.md` 增加两条条件式硬触发器
- [x] 完成 03 网络源规则
- [x] 完成 07 Workflow Responsibility Audit
- [x] 完成 08 Web 分层 CI 成本控制补充
- [x] 更新 12 规则保留映射和 Coding README
- [x] Verify Green + 全套 Coding tests
- [x] Docs targeted review
- [x] Review Skill 独立审查
- [ ] Ready Check / 最终 PR CI / 合并 / main 集成验证 / Change 归档

# 验证

## Red → Green

- Red HEAD `37e0a92e8e90eb25ff38d57f492cc5dbbe091838`：Change Completion Gate 执行 36 个 Coding 规则测试，新加的网络源/Workflow 五组断言因旧规则缺失而失败；既有 Review/Docs/TDD/时间/日志保护测试通过，确认失败原因正确。
- Green HEAD `03e92d50757bf75e67dc741181deb5cffb81c010`：Change Completion Gate 的 `Run Coding completion-gate tests` 成功；该 run 总体 failure 只因 Change 当时仍为 `in_progress`，不是规则测试失败。

## Green HEAD 永久门禁

- Runtime Acceptance `32914883786`：success。
- Full-stack Acceptance `32914883614`：success。
- CI `32914883575`：success。
- Change Completion Gate `32914883589`：规则测试 success；Ready enforcement 因当时 `status: in_progress` 按预期 failure。

## Docs targeted review

范围：`SKILL.md` §11、03/07/08/12 新增章节、`coding/README.md` §11。

结论：
- Fact Correctness：规则与当前仓库 Dockerfile/Release/CI 分环境事实以及当前镜像站状态一致；没有把某个国内镜像写成永久事实。
- Coverage：包含目标环境、实时核验、海外例外、供应链完整性、security/fallback、Workflow 责任/证据映射、check consumer 与验证闭环。
- First-principles / Terminology：先解释“下载链路稳定但不改供应链身份”“CI 降本但不降证据”，再引入术语；README 对 Workflow Responsibility Audit / 证据守恒有白话解释。
- Source-of-truth Safety：具体长期规则只在 Skill/reference；README 只做导航；镜像地址不作为固定事实复制到 Skill。
- Usability：开发者能从硬触发器定位到 03/07/08，并知道什么时候不应触发。
- `code_issue_detected`：无。

## Review Skill 独立审查

Review Target：PR #243，base `ec232dfa678ffb7afccd65ce157cd7cce41c8639`，head `03e92d50757bf75e67dc741181deb5cffb81c010`；模式 `review-only`。

结论：
- Requirement A1：R1-R7 覆盖用户批准的环境感知国内源、Workflow 证据守恒、不过度总结和“本次不改实际 Workflow”。
- Requirement A2：主 Skill 仅追加硬触发器；03/07/08/12/README 与测试形成可达闭环；PR changed files 无 `.github/workflows/*.yml`。
- 测试充分性：Red/Green 规则测试直接覆盖新语义并保护既有高价值字符串；外部当前性由一手镜像站资料补足；产品集成层本次不属于独立风险，但仓库永久 Runtime/Full-stack/CI 仍成功。
- Findings：无阻塞 Finding；未发现较弱证据替代、规则删除、Workflow 越界修改或第二套事实。

# 文档影响

Docs Impact: targeted。

- `coding/README.md` 已同步新增使用说明。
- `.agents/README.md` 的 Skill 选择和协作模型不变，不需要修改。
- AIMA Blueprint 不承载通用 Coding Skill 的镜像候选/Workflow 审计细节，本次无 Blueprint 变更。

# 交付

- Branch：`feature/coding-network-workflow-governance`。
- PR：#243 `增强 Coding 网络源与 Workflow 治理`，当前仍为 Draft；待 Ready 状态提交的最终机器门禁通过后转 Ready 并合并。
- Product Contract / Schema / Migration / data：无变化。
- AIMA `.github/workflows/*.yml`：无变化。
- Release：不适用；用户要求的 main 合并属于本 Change 的正常 Git 交付步骤，完成后再做 main 集成验证与独立 Change 归档。