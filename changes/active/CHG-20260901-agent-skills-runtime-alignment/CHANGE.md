---
schema: coding-change/v1
id: CHG-20260901-agent-skills-runtime-alignment
title: 对齐 AIMA_UGC Source Mode 治理与 Runtime 安装资产
level: L3
status: in_progress
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
  - AGENTS.md
  - docs/AGENTS.md
  - .agents/agent-skills-install.json
  - .agents/runtime/
  - .agents/skills/**
  - .codex/config.toml
  - .cursor/mcp.json
  - .mcp.json
  - CLAUDE.md
  - .gitignore
  - scripts/quality/check_agent_governance.py
  - tests/unit/test_agent_governance.py
contracts: []
data_changes: []
---

# 目标

按当前 `dingyuwen777/Agent_Skills` canonical Source Mode 规则重新收敛 AIMA_UGC 的项目治理边界：GPT 网页端的通用治理语义只来自当前 Agent_Skills canonical Source，AIMA 自己的规则、Contract、Schema/Migration、CI、代码、测试、文档和正式设计继续作为项目事实；AIMA 中旧版本 Agent_Skills 的 managed block、Runtime/Project Payload/Skill Projection 与 legacy install-state 只作为安装/ownership/version-drift 事实，不能覆盖当前 Source Mode 通用治理规则。

同时通过正式 Agent_Skills v3.1.1 Windows Runtime installer 把当前仓库的 legacy v3.0.0 安装状态升级到当前已发布的项目侧 managed block / Project Payload 形态；不手工编辑 installer-owned managed block，不以治理校准替代正式 Runtime upgrade。

# 成功标准

- [ ] AIMA marker 外项目自有 `AGENTS.md` 规则与真实仓库事实继续生效，Source Mode 不因忽略旧安装副本而忽略项目规则。
- [ ] AIMA 根 managed block 通过正式 v3.1.1 Runtime upgrade 更新为项目侧薄契约，不再出现 `Runtime Mode`、`研发治理 MCP`、内部规则标识、路由映射、加载明细等旧实现描述。
- [ ] 合法 `agent-skills-install/v3` 作为一次迁移输入；正式升级成功后旧 `.agents/agent-skills-install.json` 从仓库消失，不手工伪造 sidecarless 状态。
- [ ] `.agents/runtime/` 按当前 Agent_Skills 正式边界成为本地运行资产并进入 `.gitignore`；仓库不再跟踪旧 Windows Runtime binary。
- [ ] 当前正式 Skill Core/Entry/Router/运行资产由 v3.1.1 installer 按 previous ownership 更新；项目自有 marker 外 AGENTS、其他项目文件和非受管内容保持。
- [ ] AIMA marker 外 Overlay 与 `docs/AGENTS.md` 不再把目标项目本地旧 Agent_Skills Runtime/Skill Core 作为通用治理规则入口；项目规范只描述 AIMA 自己的长期规则、事实和真实机器门禁。
- [ ] `check_agent_governance.py` 持续阻止根 managed block/项目 Overlay/文档规则重新生长 Runtime/Source/MCP/内部路由加载实现说明，同时保留 AIMA 实际 `ready_check.py` CI 接线。
- [ ] 不修改业务代码、公共 Contract、Schema/Migration、依赖、Provider、Figma 或产品行为。
- [ ] 目标回归先在当前 v3.0.0 状态产生有效 Red；v3.1.1 正式升级和 Overlay 校准后 Green；AIMA 适用永久 CI 全绿。
- [ ] L3 Deep Review 无未解决 BLOCKER/HIGH/MEDIUM Finding；PR final-head fresh CI、合并后 main fresh CI 绿色，随后 Change 独立归档。

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
| R1 | 用当前 Agent_Skills canonical 最新约束治理 AIMA，不让旧安装副本覆盖 Source Mode | user:current-request | not_satisfied | 待正式治理与回归 |
| R2 | AIMA 自己的项目规则和真实仓库事实仍必须读取、遵守 | user:current-request | not_satisfied | 待 Overlay/测试复核 |
| R3 | 旧 managed/runtime 安装资产只作安装/ownership/drift 事实 | user:current-request | not_satisfied | 待项目门禁与正式升级 |
| R4 | 旧显式 Runtime 内部描述通过正式安装升级收敛，不手改 managed block | user:current-request | not_satisfied | 待 v3.1.1 installer 实证 |
| R5 | 优先保证 Agent_Skills 使用效果，不能为隐藏信息削弱 Runtime 治理语义 | user:current-request | not_satisfied | 待升级 self-test/项目 CI 与 Review |
| R6 | 两个仓库都完成更新合并；Agent_Skills 已先完成，本 Change 完成 AIMA 侧合并与归档 | user:current-request | not_satisfied | Agent_Skills main 已完成；AIMA 待交付 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | AIMA governance checker 与单元回归 |
| 接口 / 契约 | not_applicable | 不修改 AIMA 产品 Contract；Agent_Skills Runtime public contract 不变 |
| 集成 / 持久化 / 运行依赖 | required | Windows v3.1.1 formal installer：legacy v3 migration、managed block、Project Payload、host config、sidecar removal |
| 用户 / 工作流验收 | required | Source Mode 项目规则来源边界 + Runtime install result 的项目入口验收 |
| 跨组件关键路径 | not_applicable | 不改变 AIMA 产品调用链 |
| 外部依赖 / 供应方探测 | required | GitHub Release asset 下载 + SHA256 校验；不调用业务 Provider |
| 构建 / 打包 / 运行 | required | v3.1.1 Windows binary status/self-test/install，AIMA Runtime/CI 相关 permanent checks |
| 文档 / 治理 / 其他 | required | root/docs AGENTS、governance checker、Change/Review/CI |

# 完成审计

- [ ] upstream_re_read：重新读取当前用户要求、Agent_Skills 最新 canonical Source、AIMA 项目规则和真实安装/CI 事实。
- [ ] change_coverage：从上游独立确认本 Change 覆盖 Source Mode、正式 Runtime upgrade、项目 Overlay、门禁和交付。
- [ ] reverse_audit：确认 AIMA 没有继续把旧安装副本当通用治理规则，同时真实项目门禁/规则未被误删。
- [ ] unresolved_cleared：R1–R6 全部 satisfied 或有正式 defer/not-applicable 依据。

# 任务

- [x] 重新绑定 Agent_Skills canonical 与 AIMA main
- [x] 识别 AIMA v3.0.0 legacy install-state、旧 managed block 和 tracked Runtime binary
- [ ] 建立 AIMA Red 治理回归并确认失败
- [ ] 使用官方 v3.1.1 Windows Runtime 正式升级 legacy v3 安装
- [ ] 校准 marker 外项目 Overlay / docs AGENTS
- [ ] 强化项目 governance checker
- [ ] 运行 targeted + permanent CI
- [ ] L3 Deep Review / Completion Audit
- [ ] PR 合并、main fresh CI、Change 归档

# 验证

## 计划

- Red：当前仓库 `AGENTS.md` managed block 仍含 Runtime/MCP/内部披露词汇，`docs/AGENTS.md` 仍把本地 Coding Skill 当通用治理入口。
- Upgrade：固定 official v3.1.1 Windows ZIP SHA256 后执行 `status/self-test/install --target . --json`。
- Targeted：`tests/unit/test_agent_governance.py`、`scripts/quality/check_agent_governance.py`、docs/facts 检查、`git diff --check`。
- Permanent：AIMA PR 实际触发的 CI / Change Completion Gate / Runtime / Full-stack 等 Workflow 以 scope classifier 为准；不人为跳过 required 层。

## 新鲜证据

- 尚未执行 AIMA Red。

# 文档影响

- 根 `AGENTS.md` 与 `docs/AGENTS.md` 会做治理语义定向校准；业务 Blueprint/Roadmap/Appendix 不因本任务制造无关差异。

# 交付

- Agent_Skills canonical 防误用规则：已完成 PR #128、归档 PR #129、final main `e5a147f08fb4d501e1e28a71c35bf7a100bc7057`，Skill Tests #791 success。
- AIMA_UGC：当前分支 `chore/agent-skills-runtime-alignment`，进行中。
