---
schema: coding-change/v1
id: CHG-20260901-agent-skills-runtime-alignment
title: 对齐 AIMA_UGC Source Mode 治理与 Runtime 安装资产
level: L3
status: done
owner: dingyuwen777
branch: chore/agent-skills-runtime-alignment
created: 2026-09-01
updated: 2026-09-01
completion_gate: required
depends_on: []
affected_areas:
  - project-governance
  - agent-skills-runtime
  - docs
  - ci
  - tests
affected_paths:
  - .agents/agent-skills-install.json
  - .agents/runtime/agent-skills-mcp.exe
  - .agents/skills/ENTRY.md
  - .agents/skills/coding/SKILL.md
  - .agents/skills/coding/agents/openai.yaml
  - .agents/skills/coding/assets/AGENTS.managed.md
  - .agents/skills/coding/assets/AGENTS.template.md
  - .agents/skills/coding/scripts/coding.py
  - .agents/skills/docs/SKILL.md
  - .agents/skills/router/SKILL.md
  - .gitignore
  - AGENTS.md
  - docs/AGENTS.md
  - scripts/quality/check_agent_governance.py
  - tests/unit/test_agent_governance.py
  - changes/active/CHG-20260901-agent-skills-runtime-alignment/CHANGE.md
contracts: []
data_changes: []
---

# 目标

按当前 `dingyuwen777/Agent_Skills` canonical Source Mode 规则收敛 AIMA_UGC 的项目治理边界：GPT 网页端的通用治理语义只来自当前 Agent_Skills canonical Source；AIMA 自己的规则、Contract、Schema/Migration、CI、代码、测试、文档和正式设计继续作为项目事实；目标项目中旧版本 Agent_Skills managed block、Runtime/Project Payload/Skill Projection 与 legacy install-state 只作为安装、ownership 和 version-drift 事实，不能覆盖当前 Source Mode 通用治理规则。

同时通过正式 Agent_Skills v3.1.1 Windows Runtime installer 将 AIMA 的 legacy v3.0.0 安装状态迁移到当前正式项目侧安装形态；不手工编辑 installer-owned managed block，不以项目治理校准替代 Runtime upgrade。

# 成功标准

- [x] AIMA marker 外项目自有 `AGENTS.md` 规则与真实仓库事实继续生效，Source Mode 不因忽略旧安装副本而忽略项目规则。
- [x] AIMA 根 managed block 通过正式 v3.1.1 Runtime upgrade 更新为项目侧薄契约，不再出现旧 `Runtime Mode`、`研发治理 MCP`、内部规则标识、路由映射、加载明细等实现描述。
- [x] 合法 `agent-skills-install/v3` 仅作为一次 previous-ownership 迁移输入；正式升级后旧 `.agents/agent-skills-install.json` 从仓库消失。
- [x] `.agents/runtime/` 成为本地运行资产并进入 `.gitignore`；仓库不再跟踪旧 Windows Runtime binary。
- [x] 正式 Skill Core/Entry/Router/Project Projection 由 v3.1.1 installer 按 previous ownership 更新；项目自有 marker 外 AGENTS 与非受管内容保持。
- [x] AIMA marker 外 Overlay 与 `docs/AGENTS.md` 不再把目标项目本地旧 Agent_Skills Runtime/Skill Core 作为通用治理规则入口。
- [x] `check_agent_governance.py` 持续阻止根 managed block、项目 Overlay、文档规则重新生长 Runtime/Source/MCP/内部路由加载说明，同时保留 AIMA 实际 `ready_check.py` CI 接线。
- [x] 不修改业务代码、公共 Contract、Schema/Migration、依赖、Provider、Figma 或产品行为。
- [x] Red → v3.1.1 正式升级 → Overlay 校准 → Green → L3 Review → PR fresh CI 全部完成。
- [x] PR #277 已合并，`main@045bc3cb0e13d9dbf9d15e4419837944c6f5b3ab` 的 5 个 fresh push Workflow 全绿；本记录已进入独立 archive carrier，归档 PR 自身仍须 fresh CI + guarded merge 后才宣告整个任务结束。

# 范围

- 以 Agent_Skills canonical main 的 Source Mode 防误用规则作为本任务通用治理来源。
- 读取 AIMA 当前项目规则和真实工程事实；旧安装 Agent_Skills 只作为安装/ownership/drift 事实。
- 用官方 Agent_Skills v3.1.1 Windows Release binary 执行 legacy v3 正式项目升级。
- 定向清理根 `AGENTS.md` marker 外 Overlay 与 `docs/AGENTS.md` 中对本地通用治理实现/旧 Skill Core 的说明。
- 强化 AIMA 自有 governance checker 与回归测试。
- 按项目永久 CI 完成验证、Review、PR/main fresh CI 与 Change 归档。

# 非目标

- 不在本 Change 内再次修改 Agent_Skills canonical；Source Mode 防误用规则已由 Agent_Skills PR #128 / archive PR #129 完成并归档。
- 不手工编辑 `agent-skills:managed` block 或 `.agents/skills` installer-owned 文件模拟升级。
- 不升级到未正式发布的 Agent_Skills main binary；Runtime 安装使用正式 v3.1.1 Release。
- 不改变 Runtime evaluator、MCP Tool Contract、Bundle、Project Payload schema 或 Runtime disclosure 强度。
- 不修改 AIMA 业务 API、Pydantic Contract、OpenAPI、Schema、Migration、数据库数据、Provider、AI Prompt、前端业务、Figma 或部署拓扑。
- 不启用 Branch Protection/Ruleset。

# 必须保持不变

- AIMA 当前模块化单体、Python/PostgreSQL/Vue 技术基线、模块 Owner、Contract、Schema/Migration、8 种生产 Worker Job、测试/CI、部署与 Roadmap 事实不因本次治理发生语义变化。
- 项目自有 marker 外 `AGENTS.md` 是 AIMA 长期规则资产；installer upgrade 只替换 managed marker 内文本及其明确 ownership 范围。
- `ready_check.py` 继续是 AIMA Change Completion Gate 的机器入口；它是项目真实 CI 接线，不是 Source Mode canonical 通用治理规则来源。
- Runtime Mode 的完整路由、required Context exact-text、披露、完整性和 fail-closed 语义继续由正式 Agent_Skills Runtime Release 提供。

# 关键决策

1. 只手改 AIMA managed block：破坏 installer ownership、升级/回滚与 previous ownership 证明；拒绝。
2. Source Mode 继续使用 AIMA v3.0.0 managed/runtime 作为通用治理规则：旧安装会覆盖当前 canonical；拒绝。
3. 只校准 Source Mode Overlay、不升级 Runtime：网页端正确但团队 Runtime 使用者仍留在旧 v3.0.0 项目入口；不完整，拒绝。
4. Source Mode 使用当前 canonical；AIMA 项目事实继续读取；正式 v3.1.1 installer 负责旧安装资产迁移；Overlay 只维护 AIMA 自身规则：采用。
5. 为隐藏信息继续删减 Runtime 内部规则：可能降低使用效果；拒绝。本 Change 只收敛目标项目可见安装面和规则来源。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 用当前 Agent_Skills canonical 最新约束治理 AIMA，不让旧安装副本覆盖 Source Mode | user:current-request | satisfied | Agent_Skills PR #128/#129 已合并归档；final main `e5a147f08fb4d501e1e28a71c35bf7a100bc7057`；canonical 根入口明确把目标项目 managed/Runtime/Project Payload/legacy install-state 视为非 canonical 安装资产 |
| R2 | AIMA 自己的项目规则和真实仓库事实仍必须读取、遵守 | user:current-request | satisfied | 根 `AGENTS.md` managed 薄契约与 marker 外 Overlay 均保留项目事实优先；`docs/AGENTS.md` 继续以 AIMA Blueprint/Roadmap/代码/Contract/Schema/Migration/测试/CI 为事实源 |
| R3 | 旧 managed/runtime 安装资产只作安装/ownership/drift 事实，项目 Overlay/文档不把本地安装副本当通用规则入口 | user:current-request | satisfied | `AGENTS.md` marker 外治理实现术语已清理；`docs/AGENTS.md` 不再指向 `.agents/skills/coding/`；GOV009/GOV010/GOV011 与治理单测持续防回归 |
| R4 | 旧显式 Runtime 内部描述通过正式安装升级收敛，不手改 managed block | user:current-request | satisfied | official v3.1.1 Windows installer Run `33468370246` success；legacy manifest / tracked Runtime binary 删除，installer-owned managed/Skill Projection 按 previous ownership 更新 |
| R5 | 优先保证 Agent_Skills 使用效果，不能为隐藏信息削弱 Runtime 治理语义 | user:current-request | satisfied | 使用正式 v3.1.1 Runtime 资产而非删减 Runtime 规则；Review `5074019724` / `5074148131` 均 NO_FINDINGS_WITHIN_SCOPE；PR final-head 和 main fresh Runtime/CI/Full-stack/Tooling 全绿 |
| R6 | 两个仓库都完成更新合并，并以各自主分支 fresh CI 与 Change 归档收口 | user:current-request | satisfied | Agent_Skills 已完成 feature/archive merge、归档后 Skill Tests #791；AIMA PR #277 merge commit `045bc3cb0e13d9dbf9d15e4419837944c6f5b3ab`，main fresh CI `33471867983`、Completion `33471867916`、Runtime `33471867915`、Full-stack `33471867900`、Tooling `33471867828` 全部 success；当前记录已移动到独立 archive carrier，归档 PR 自身仍按正常 fresh CI/guarded merge 验证 |

# 验证矩阵

| 验证层 | 是否要求 | 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Red 阶段 700 个 Unit 中只有新增 3 项按旧 v3.0.0 状态失败；升级后 targeted 10 项与最终 Unit 全绿 |
| 接口 / 契约 | not_applicable | 不修改 AIMA 产品 Contract；Agent_Skills Runtime public contract 不变 |
| 集成 / 持久化 / 运行依赖 | required | Windows v3.1.1 formal installer `33468370246`；PR/main PostgreSQL Integration 全层成功 |
| 用户 / 工作流验收 | required | Source Mode 规则来源边界、managed 薄契约、项目 Overlay/docs 入口、永久 governance checker |
| 跨组件关键路径 | not_applicable | 不改变 AIMA 产品调用链；Full-stack PR/main 均成功 |
| 外部依赖 / 供应方探测 | required | official v3.1.1 Windows ZIP SHA256 校验后安装；不调用业务 Provider |
| 构建 / 打包 / 运行 | required | v3.1.1 status/self-test/install + AIMA PR/main CI/Runtime/Full-stack/Tooling |
| 文档 / 治理 | required | root/docs AGENTS、governance checker、Ready Gate、两阶段 L3 Review、PR/main fresh CI、独立归档 |

# 完成审计

- [x] upstream_re_read：重新读取用户双仓库要求、Agent_Skills current canonical Source Mode 入口、AIMA `AGENTS.md`、Ready Check、真实 diff 与 final-head/main CI。
- [x] change_coverage：覆盖正式 Runtime upgrade、项目 Overlay/docs 规则来源、governance checker/测试和双仓库交付；业务 Contract/Schema/Provider 等明确非目标。
- [x] reverse_audit：marker 外 Overlay 与 `docs/AGENTS.md` 不再把旧安装副本当通用治理规则；managed block 仍保留项目事实优先与失败关闭等高层约束；Runtime 规则强度未为隐藏信息而删减。
- [x] unresolved_cleared：R1–R6 均已有真实证据；归档 carrier 只等待其自身 fresh CI + guarded merge，不再存在产品/治理实现未决项。

# 任务

- [x] 重新绑定 Agent_Skills canonical 与 AIMA main
- [x] 识别 AIMA v3.0.0 legacy install-state、旧 managed block 和 tracked Runtime binary
- [x] 建立 AIMA Red 治理回归并确认失败
- [x] 使用官方 v3.1.1 Windows Runtime 正式升级 legacy v3 安装
- [x] 校准 marker 外项目 Overlay / docs AGENTS
- [x] 强化项目 governance checker
- [x] 运行 targeted + permanent PR CI
- [x] L3 Deep Review / Completion Audit
- [x] PR #277 guarded merge
- [x] main fresh CI 全绿
- [x] Change 进入独立 archive carrier

# 关键证据

## Agent_Skills canonical

- Feature PR #128 merged；archive PR #129 merged。
- Final Agent_Skills main：`e5a147f08fb4d501e1e28a71c35bf7a100bc7057`。
- Archive-main Skill Tests #791 — success。

## AIMA Red / Upgrade / Green

- Red：legacy v3.0.0 状态下，700 个 Unit 中仅新增 3 个治理回归按预期失败，其余 699 通过。
- Formal upgrade：official v3.1.1 Windows installer Run `33468370246` — success；先校验 Release ZIP SHA256，再执行 `status/self-test/install --target . --json`；legacy manifest 删除、Runtime binary 停止 Git 跟踪。
- Overlay calibration：Run `33470482184` — success；项目 governance checker 与 targeted 10 项治理测试成功；一次性施工资产在最终 PR 前删除。

## AIMA PR #277

- Implementation Review `5074019724` — NO_FINDINGS_WITHIN_SCOPE。
- Final-head Review `5074148131` — NO_FINDINGS_WITHIN_SCOPE。
- Final PR head：`cbf6be68039172cb03f8872ba765a599884728ae`。
- CI `33471492936` — success。
- Change Completion Gate `33471492904` — success。
- Runtime Acceptance `33471492941` — success。
- Full-stack Acceptance `33471492907` — success。
- Developer Tooling Compatibility `33471492930` — success。
- Guarded merge commit：`045bc3cb0e13d9dbf9d15e4419837944c6f5b3ab`。

## AIMA main fresh CI after feature merge

- CI `33471867983` — success（Repository Quality、PostgreSQL Integration、CI Gate 全绿）。
- Change Completion Gate `33471867916` — success。
- Runtime Acceptance `33471867915` — success。
- Full-stack Acceptance `33471867900` — success。
- Developer Tooling Compatibility `33471867828` — success。

# 文档与行为影响

- 根 `AGENTS.md` 与 `docs/AGENTS.md` 完成治理语义定向校准；业务 Blueprint/Roadmap/Appendix 未制造无关差异。
- AIMA 项目文档只描述 AIMA 自身架构、Contract、Schema、测试、CI、部署、事实与导航，不复制外部通用治理实现。
- 没有业务行为、公共 Contract、Schema/Migration、Provider、依赖、Figma 或部署拓扑变化。

# 证据守恒

- v3.0.0 legacy install-state 作为 installer previous-ownership 迁移输入，没有被手工删除后伪装成新状态。
- 正式 v3.1.1 installer 承担 `.agents/skills/**`、managed block 和 Runtime ownership 迁移；项目治理校准只修改 marker 外 AIMA 文本。
- AIMA `ready_check.py`、永久 CI、项目 docs/facts/governance 门禁仍由 AIMA 自己持有；没有把 Agent_Skills canonical 自测重新复制进业务仓库。
- 减少目标项目可见的内部治理实现描述，没有删除 Runtime 中真正负责路由、required Context、完整性、披露与 fail-closed 的规则。

# 归档说明

本记录在功能 PR #277 合并且 `main@045bc3cb0e13d9dbf9d15e4419837944c6f5b3ab` fresh CI 全绿后进入独立归档分支。归档 PR 必须只包含本 Change 的 active → archive 迁移与证据封存；归档 PR fresh CI、Review、guarded merge 和归档后 main fresh CI 完成后，整个双仓库任务才最终闭环。
