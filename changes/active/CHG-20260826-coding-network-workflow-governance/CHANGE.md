---
schema: rvc-change/v1
id: CHG-20260826-coding-network-workflow-governance
title: Coding 网络源选择与 Workflow 证据守恒治理
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/coding-network-workflow-governance
created: 2026-08-26
updated: 2026-08-26
completion_gate: required
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

- [ ] `SKILL.md` 有两条可直接触发的硬规则，并明确展开细节所在 reference。
- [ ] `03_编程语言与工具链适配规则.md` 完整说明网络位置判断、实时联网核验、国内候选源、供应链身份/锁/hash/digest、可覆盖/fallback、安全更新与失效镜像处理。
- [ ] `07_通用验证与证据策略.md` 定义 Workflow Responsibility Audit、Evidence Preservation Mapping、允许的降本手段与不得降低的证据等级。
- [ ] `08_分层测试与验收策略.md` 把 Web/API/PostgreSQL/Full-stack/Provider 的 CI 成本控制落实到现有分层职责，不重复穷举同一状态空间。
- [ ] `12_规则保留映射.md` 固化两条新规则的 canonical 位置，防止未来“精简”丢失触发条件、例外和验证责任。
- [ ] `coding/README.md` 补充人类可读使用说明，但不形成第二套正式规则。
- [ ] 回归测试先在旧规则上失败，再在实现后通过，并证明 Review/Docs 路由等既有 Coding 内容未被破坏。
- [ ] 本 Change 不修改 AIMA 当前 `.github/workflows/*.yml`；Workflow 实际重构留给独立任务。
- [ ] 当前 HEAD 的适用 Coding tests、Ready Check、PR CI/Runtime/Full-stack/Change Gate 全部取得新鲜成功证据后才允许合并。

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
| R1 | 涉及启动脚本、依赖/Runtime 安装、镜像构建等网络下载时，在中国大陆环境联网查询当前稳定国内源并合理替换 | user:current-request | not_satisfied | 待实现与验证 |
| R2 | 国内源选择不能静态绑定历史地址，应考虑执行环境、当前可用性、供应链身份和完整性 | user:current-request | not_satisfied | 待实现与验证 |
| R3 | Coding 应评估永久 Workflow 是否过重、重复或无关触发，并在不丢测试目的的前提下精简 | user:current-request | not_satisfied | 待实现与验证 |
| R4 | Workflow 精简不得过分总结或降低原测试证明范围，必须保持证据责任可追溯 | user:current-request | not_satisfied | 待实现与验证 |
| R5 | 主 Skill 保留硬触发器，详细规则按既有职责放 `03`、`07`、`08`，避免主文件过度膨胀 | user:approved-plan | not_satisfied | 待实现与验证 |
| R6 | 更新规则保留映射和使用说明，防止后续精简再次丢失 | user:approved-plan | not_satisfied | 待实现与验证 |
| R7 | 本次只改 Skill，不顺手重构 AIMA Workflow；完成后正常 PR/CI 并合并 main | user:current-request | not_satisfied | 待实现、PR/CI/合并 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 新回归测试对主 Skill、03/07/08/12/README 的关键语义做可失败断言；先 Red 后 Green |
| 接口 / Contract | not_applicable | 不修改产品 public API/ABI/Schema/格式；Skill 文本规则由治理测试覆盖 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改产品运行时、数据库或依赖集成 |
| 用户 / Workflow Acceptance | not_applicable | 不改变产品用户工作流；人类 Skill 使用说明由 Docs targeted review 覆盖 |
| 跨组件 Golden Path | not_applicable | 不改变产品跨组件接线 |
| External Dependency / Provider Probe | required | 通过当前官方镜像站帮助/状态页确认“国内镜像会失效、应实时核验”的事实；不执行付费/写入外部操作 |
| Build / Package / Runtime | not_applicable | 不修改实际构建、镜像或 Runtime 行为 |
| Docs / Governance / Other | required | Coding 全套规则测试、规则保留审计、Docs targeted review、Review Skill 独立审查、Ready Check、PR/CI 门禁 |

# Completion Audit

- [ ] upstream_re_read：重新读取本轮用户批准方案、当前 AGENTS/Coding/03/07/08/12/README 和相关测试。
- [ ] change_coverage：确认两条上游要求和“只改 Skill、不改 Workflow”均进入本 Change。
- [ ] reverse_audit：从主硬触发器反向检查 03/07/08 展开规则、12 保留映射、README 和测试是否全部可达；确认没有削弱既有 Review/Docs/验证边界。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零，所有 required Validation 有新鲜证据。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立四维任务路由：Infra/Build/Release Tooling + Governance / Rule change / Markdown+Python tests / L2
- [ ] 建立失败测试并 Verify Red
- [ ] 在 `SKILL.md` 增加两条条件式硬触发器
- [ ] 完成 03 网络源规则
- [ ] 完成 07 Workflow Responsibility Audit
- [ ] 完成 08 Web 分层 CI 成本控制补充
- [ ] 更新 12 规则保留映射和 Coding README
- [ ] Verify Green + 全套 Coding tests
- [ ] Docs targeted review
- [ ] Review Skill 独立审查
- [ ] Ready Check / PR CI / 合并 / main 集成验证 / Change 归档

# 验证

## 计划

- Red/Green：`python -m unittest .agents.skills.coding.tests.test_network_and_workflow_governance`（按仓库实际可执行入口调整）
- Coding tests：运行 `.agents/skills/coding/tests/` 全套 unittest/pytest 入口
- Ready Check：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`
- PR 永久门禁：Change Completion Gate / CI / Runtime Acceptance / Full-stack Acceptance
- Docs：`docs` targeted review 本次修改的 Coding README/Skill references
- Review：读取 `.agents/skills/review/SKILL.md` 独立审查 diff 与测试充分性

## 新鲜证据

- 官方镜像事实调查：已确认 2026-08-26 前后清华 TUNA、阿里云、USTC PyPI 等镜像仍提供当前同步信息；USTC Docker Hub 帮助页明确镜像缓存已关闭，证明不能把历史国内镜像地址当永久事实。
- 代码/规则测试：待执行。

# 文档影响

Docs Impact: targeted。

- `coding/README.md` 需要同步新增使用说明。
- `.agents/README.md` 的 Skill 选择和协作模型不变，不需要修改。
- AIMA Blueprint 不承载通用 Coding Skill 的镜像候选/Workflow 审计细节，本次无 Blueprint 变更。

# 交付

- Commit：待补。
- PR：待创建。
- 发布：不适用。