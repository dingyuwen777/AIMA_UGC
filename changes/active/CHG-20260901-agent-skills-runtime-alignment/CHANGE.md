---
schema: coding-change/v1
id: CHG-20260901-agent-skills-runtime-alignment
title: 对齐 AIMA_UGC Source Mode 治理与 Runtime 安装资产
level: L3
status: ready_for_review
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

按当前 `dingyuwen777/Agent_Skills` canonical Source Mode 规则重新收敛 AIMA_UGC 的项目治理边界：GPT 网页端的通用治理语义只来自当前 Agent_Skills canonical Source，AIMA 自己的规则、Contract、Schema/Migration、CI、代码、测试、文档和正式设计继续作为项目事实；AIMA 中旧版本 Agent_Skills 的 managed block、Runtime/Project Payload/Skill Projection 与 legacy install-state 只作为安装/ownership/version-drift 事实，不能覆盖当前 Source Mode 通用治理规则。

同时通过正式 Agent_Skills v3.1.1 Windows Runtime installer 把当前仓库的 legacy v3.0.0 安装状态升级到当前已发布的项目侧 managed block / Project Payload 形态；不手工编辑 installer-owned managed block，不以治理校准替代正式 Runtime upgrade。

# 成功标准

- [x] AIMA marker 外项目自有 `AGENTS.md` 规则与真实仓库事实继续生效，Source Mode 不因忽略旧安装副本而忽略项目规则。
- [x] AIMA 根 managed block 通过正式 v3.1.1 Runtime upgrade 更新为项目侧薄契约，不再出现 `Runtime Mode`、`研发治理 MCP`、内部规则标识、路由映射、加载明细等旧实现描述。
- [x] 合法 `agent-skills-install/v3` 作为一次迁移输入；正式升级成功后旧 `.agents/agent-skills-install.json` 从仓库消失，不手工伪造 sidecarless 状态。
- [x] `.agents/runtime/` 按当前 Agent_Skills 正式边界成为本地运行资产并进入 `.gitignore`；仓库不再跟踪旧 Windows Runtime binary。
- [x] 当前正式 Skill Core/Entry/Router/运行资产由 v3.1.1 installer 按 previous ownership 更新；项目自有 marker 外 AGENTS、其他项目文件和非受管内容保持。
- [x] AIMA marker 外 Overlay 与 `docs/AGENTS.md` 不再把目标项目本地旧 Agent_Skills Runtime/Skill Core 作为通用治理规则入口；项目规范只描述 AIMA 自己的长期规则、事实和真实机器门禁。
- [x] `check_agent_governance.py` 持续阻止根 managed block/项目 Overlay/文档规则重新生长 Runtime/Source/MCP/内部路由加载实现说明，同时保留 AIMA 实际 `ready_check.py` CI 接线。
- [x] 不修改业务代码、公共 Contract、Schema/Migration、依赖、Provider、Figma 或产品行为。
- [x] 目标回归先在当前 v3.0.0 状态产生有效 Red；v3.1.1 正式升级和 Overlay 校准后 Green；AIMA 适用永久 PR CI 全绿。
- [ ] PR 合并后 `main` fresh CI 绿色，随后 Change 独立归档并再次验证最终 `main`。

# 范围

- 以当前 Agent_Skills canonical main 的 Source Mode 防误用规则作为本任务通用治理来源。
- 读取 AIMA 当前项目规则和真实工程事实；旧安装 Agent_Skills 仅作为安装/ownership/drift 事实。
- 用官方 Agent_Skills v3.1.1 Windows Release binary 执行 legacy v3 → sidecarless 正式项目升级。
- 定向清理根 `AGENTS.md` marker 外 Overlay 与 `docs/AGENTS.md` 中对本地通用治理实现/旧 Skill Core 的说明。
- 强化 AIMA 自有 governance checker 与回归测试。
- 按项目实际 CI scope 完成验证、Review、PR/main fresh CI 与归档。

# 非目标

- 不修改 Agent_Skills canonical 仓库；该防误用规则已由独立 PR #128 / #129 完成并归档。
- 不手工编辑 `agent-skills:managed` block 或 `.agents/skills` installer-owned 文件来模拟升级结果。
- 不升级到未正式发布的 Agent_Skills main binary；Runtime 安装只使用当前已发布且已验证的 v3.1.1 Windows Release。
- 不改变 Runtime evaluator、MCP Tool Contract、Bundle、Project Payload schema 或 Runtime disclosure 强度。
- 不修改 AIMA 业务 API、Pydantic Contract、OpenAPI、Schema、Migration、数据库数据、Provider、AI Prompt、前端业务、Figma 或部署拓扑。
- 不启用 Branch Protection/Ruleset；平台保护继续作为独立治理议题。

# 必须保持不变

- AIMA 当前模块化单体、Python/PostgreSQL/Vue 技术基线、模块 Owner、Contract、Schema/Migration、8 种生产 Worker Job、测试/CI、部署与 Roadmap 事实不因本次治理发生语义变化。
- 项目自有 marker 外 `AGENTS.md` 是 AIMA 长期规则资产；installer upgrade 只能替换 managed marker 内文本及其明确 ownership 范围。
- `ready_check.py` 继续是 AIMA Change Completion Gate 的机器入口；它作为项目真实 CI 接线可以被调用，但其内容不成为 Source Mode canonical 通用治理规则来源。
- Runtime Mode 的完整路由、required Context exact-text、披露、完整性和 fail-closed 语义继续由正式 Agent_Skills Runtime Release 提供。

# 关键决策

1. **只手改 AIMA managed block**：可以快速删掉旧文本，但破坏 installer ownership、升级/回滚和 previous ownership 证明；拒绝。
2. **网页 Source Mode 继续遵守 AIMA v3.0.0 managed block 的通用治理细则**：会让旧安装版本反向覆盖当前 canonical；拒绝。
3. **只做 Source Mode Overlay 校准，不升级 Runtime**：网页端可以正确工作，但团队 Runtime 使用者仍看到/执行旧 v3.0.0 项目入口；不完整，拒绝。
4. **Source Mode 使用当前 canonical；AIMA 项目事实继续读取；正式 v3.1.1 installer 负责旧安装资产迁移；Overlay 只维护 AIMA 自身规则**：Ownership 清晰且不降低执行效果；采用。
5. **为了不暴露治理实现继续删减 Runtime 内部规则**：可能降低治理效果；拒绝。本任务只收敛目标项目可见安装面和规则来源。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 用当前 Agent_Skills canonical 最新约束治理 AIMA，不让旧安装副本覆盖 Source Mode | user:current-request | satisfied | Agent_Skills PR #128/#129 已合并归档，final main `e5a147f08fb4d501e1e28a71c35bf7a100bc7057`；当前 canonical 根入口明确把目标项目 managed/Runtime/Project Payload/legacy install-state 视为非 canonical 安装资产 |
| R2 | AIMA 自己的项目规则和真实仓库事实仍必须读取、遵守 | user:current-request | satisfied | 当前根 `AGENTS.md` managed 薄契约与 marker 外 Overlay 均保留“项目事实优先”；`docs/AGENTS.md` 继续以 AIMA Blueprint/Roadmap/代码/Contract/Schema/Migration/测试/CI 为事实源 |
| R3 | 旧 managed/runtime 安装资产只作安装/ownership/drift 事实，项目 Overlay/文档不把本地安装副本当通用规则入口 | user:current-request | satisfied | `AGENTS.md` marker 外治理实现术语已清理；`docs/AGENTS.md` 不再指向 `.agents/skills/coding/`；GOV009/GOV010/GOV011 与治理单测持续防回归 |
| R4 | 旧显式 Runtime 内部描述通过正式安装升级收敛，不手改 managed block | user:current-request | satisfied | official v3.1.1 Windows installer 临时升级 Run `33468370246` success；legacy manifest / tracked Runtime binary 删除，installer-owned managed/Skill Projection 按 previous ownership 更新 |
| R5 | 优先保证 Agent_Skills 使用效果，不能为隐藏信息削弱 Runtime 治理语义 | user:current-request | satisfied | 使用正式 v3.1.1 Runtime 资产而非删减 Runtime 规则；L3 Review #5074019724 为 NO_FINDINGS_WITHIN_SCOPE；PR final-head CI/Runtime/Full-stack/Tooling 全绿 |
| R6 | 两个仓库都完成更新合并，并以各自主分支 fresh CI 与 Change 归档收口 | user:current-request | explicitly_deferred | Agent_Skills 已完成合并、main fresh Skill Tests #791 与归档；AIMA PR #277 已达到可合并门禁，AIMA merge/main fresh CI/独立归档必须在 PR 合并后执行，当前 Change 保持 active 直至这些证据产生 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | AIMA governance checker 与单元回归；Red 阶段 700 个 Unit 中恰好新增 3 项按旧 v3.0.0 状态失败，升级后 targeted 10 项与最终 Unit 全绿 |
| 接口 / 契约 | not_applicable | 不修改 AIMA 产品 Contract；Agent_Skills Runtime public contract 不变 |
| 集成 / 持久化 / 运行依赖 | required | Windows v3.1.1 formal installer Run `33468370246`；final-head PostgreSQL Integration 全层成功 |
| 用户 / 工作流验收 | required | Source Mode 项目规则来源边界、managed 薄契约、项目 Overlay/docs 入口与永久 governance checker |
| 跨组件关键路径 | not_applicable | 不改变 AIMA 产品调用链；Full-stack Acceptance 仍成功 |
| 外部依赖 / 供应方探测 | required | official v3.1.1 Windows ZIP SHA256 校验后安装；不调用业务 Provider |
| 构建 / 打包 / 运行 | required | v3.1.1 status/self-test/install + AIMA final-head CI/Runtime/Full-stack/Tooling |
| 文档 / 治理 / 其他 | required | root/docs AGENTS、governance checker、Ready Gate、L3 Review、PR/main fresh CI 与归档 |

# 完成审计

- [x] upstream_re_read：已重新读取当前用户双仓库要求、Agent_Skills `main` canonical Source Mode 入口、AIMA 当前分支 `AGENTS.md`、Ready Check、真实 diff 和 final-head CI。
- [x] change_coverage：从上游要求独立确认本 Change 覆盖正式 Runtime upgrade、项目 Overlay/docs 规则来源、治理 checker/测试和 AIMA 交付；业务 Contract/Schema/Provider 等明确保持非目标。
- [x] reverse_audit：已确认 marker 外 Overlay 与 `docs/AGENTS.md` 不再把旧安装副本当通用治理规则；正式 managed block 仍保留项目事实优先和失败关闭等高层约束；Runtime 规则强度未被为隐藏信息而删减。
- [x] unresolved_cleared：R1–R5 已有新鲜证据；R6 明确只延后到 merge 后的主分支 fresh CI/归档阶段，不是省略或降低交付责任，Change 在完成前不会归档。

# 任务

- [x] 重新绑定 Agent_Skills canonical 与 AIMA main
- [x] 识别 AIMA v3.0.0 legacy install-state、旧 managed block 和 tracked Runtime binary
- [x] 建立 AIMA Red 治理回归并确认失败
- [x] 使用官方 v3.1.1 Windows Runtime 正式升级 legacy v3 安装
- [x] 校准 marker 外项目 Overlay / docs AGENTS
- [x] 强化项目 governance checker
- [x] 运行 targeted + permanent PR CI
- [x] L3 Deep Review / Completion Audit
- [ ] PR 合并、main fresh CI、Change 归档

# 验证

## Red / Upgrade / Green

- Red：旧 v3.0.0 状态下，700 个 Unit 中只有新增的 3 个治理回归按预期失败，证明 managed 内部描述、本地 Skill Core 导航和 legacy Runtime/install-state 是真实缺口；其余 699 个 Unit 通过。
- Formal upgrade：official Agent_Skills v3.1.1 Windows installer Run `33468370246` success；Release ZIP 先执行官方 SHA256 校验，再执行 `status/self-test/install --target . --json`；managed block 外项目文本在 installer 阶段保持，legacy manifest 删除，Runtime binary 停止 Git 跟踪。
- Overlay calibration：Run `33470482184` success；只定向修改 marker 外 AIMA 项目文本，`check_agent_governance.py` 与 targeted 10 项治理测试均成功；一次性 Workflow/patch script 已从最终分支清理。

## final-head permanent PR evidence

Reviewed implementation head：`d45651b427a4efa907494527b355b54ed7c617dd`。

- CI #3531：Run `33471002178` — success；包含 Python static/type、Unit/Contract/API、Architecture/Ownership、Secret/docs/docs-facts/governance、Wheel、Frontend lint/type/unit/build/Browser Mock Acceptance。
- PostgreSQL Integration：属于上述 CI run 的永久集成层，Migration、Platform、Database、Job、Collection、Content、Ingestion 全部 success。
- Change Completion Gate #1377：Run `33471002166` — success。
- Runtime Acceptance #652：Run `33471002214` — success。
- Full-stack Acceptance #590：Run `33471002169` — success。
- Developer Tooling Compatibility #223：Run `33471002176` — success。
- L3 Deep Review：Review `5074019724`，结论 `NO_FINDINGS_WITHIN_SCOPE`；`main...head` 当时 `behind_by=0`，无未解决 review thread。

Change-only Ready 元数据更新后必须重新取得该新 HEAD 的 fresh permanent CI；旧 `d45651b4…` 证据只作为 Ready 前实现证据，不冒充最终合并证据。

# 文档影响

- 根 `AGENTS.md` 与 `docs/AGENTS.md` 已完成治理语义定向校准；业务 Blueprint/Roadmap/Appendix 未制造无关差异。
- AIMA 项目文档只描述 AIMA 自身架构、Contract、Schema、测试、CI、部署、事实与导航，不复制外部通用治理实现。

# 证据守恒

- v3.0.0 legacy install-state 只作为 installer previous-ownership 迁移输入，没有被手工删除后伪装成新状态。
- 正式 v3.1.1 installer 承担 `.agents/skills/**`、managed block 和 Runtime ownership 迁移；项目治理校准只修改 marker 外 AIMA 文本。
- AIMA 的 `ready_check.py`、永久 CI、项目 docs/facts/governance 门禁仍由 AIMA 自己持有；没有把 Agent_Skills canonical 自测重新复制进业务仓库。
- 减少目标项目可见的内部治理实现描述，没有删除 Runtime 中真正负责路由、required Context、完整性、披露与 fail-closed 的规则。

# 交付

- Agent_Skills canonical 防误用规则：PR #128 / archive PR #129 已完成；final main `e5a147f08fb4d501e1e28a71c35bf7a100bc7057`；归档后 Skill Tests #791 success。
- AIMA_UGC：PR #277，当前进入 `ready_for_review`；待 Change-only final-head fresh CI 后执行 guarded merge、main fresh CI 与独立 Change 归档。
