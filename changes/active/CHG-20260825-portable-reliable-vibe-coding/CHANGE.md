---
schema: rvc-change/v1
id: CHG-20260825-portable-reliable-vibe-coding
title: Reliable Vibe Coding 跨项目跨阶段跨语言通用化重组
level: L2
status: in_progress
owner: aima
branch: refactor/reliable-vibe-coding-portable-routing
created: 2026-08-25
updated: 2026-08-25
completion_gate: required
depends_on: []
affected_areas:
  - developer-tooling
  - agent-workflow
  - testing-governance
affected_paths:
  - .agents/skills/reliable-vibe-coding/
  - tests/unit/test_reliable_vibe_coding_portability.py
contracts: []
data_changes: []
---

# 背景与当前事实

当前仓库只有一套 `.agents/skills/reliable-vibe-coding/` Skill。它已经包含项目发现、L1-L3 分级、Change 管理、Requirement Traceability、Completion Audit、Red-Green-Refactor、根因调试、分层验证、多人协作、Review、Git 和交付证据等完整机制，但主 `SKILL.md` 同时承担入口、路由、流程正文、AIMA/Web 技术形态示例和交付门禁，职责偏重。

现有 `testing-strategy.md` 中 Browser Mock、Backend/API/PostgreSQL、Real Full-stack、Real Provider Probe 等内容对 Web/API/数据库/外部 Provider 项目有直接价值，不能删除；但这些具体技术形态不应被误解为所有 CLI、Library、Mobile、Embedded、Infra 或其他语言项目都必须具备的固定架构。

本次只重组 Skill 自身，不改变 AIMA 产品 API、Schema、Migration、运行时、业务行为或现有 CI 风险层。

任务开始基线为 `main` 的 `e8f974b6679a6e2ef8382324196d70311ec12b3a`。开发过程中 `main` 又前进 3 个提交，只归档了已完成的 `CHG-20260825-ci-long-term-risk-layers`；当前分支已正常合入最新 `main` `9b6457d3549dea57f85d52bf664227b47791b9b4`，并同步把本 Change 的 R6 Source 指向归档后的真实路径。

# 目标

把 Reliable Vibe Coding 重组为一个可以复制到不同项目使用的通用研发 Skill，并让 Agent 在执行前先按四个互相独立的维度路由：

```text
项目形态
× 研发阶段 / 任务类型
× 编程语言 / 工具链
× 风险等级 L1-L3
→ 选择最少但充分的规则、验证和交付门禁
```

核心流程保持稳定；项目、阶段、语言和验证细节按真实仓库事实条件式加载。现有有价值规则和专项细节全部保留，不因“精简”而删除。

# 成功标准

- [ ] `SKILL.md` 形成清晰的强制入口与四维任务路由，明确“先识别项目事实，再选择阶段/技术栈/风险规则”，而不是默认 Web/Python/PostgreSQL。
- [ ] 新增项目/研发阶段路由参考，覆盖首次接入、需求/设计、实现、Bug/调试、重构、Review、发布/运维、维护/迁移等阶段，并明确各阶段应加载哪些现有规则。
- [ ] 新增编程语言与工具链适配参考，至少覆盖 Python、JavaScript/TypeScript、Go、Rust、Java/Kotlin、.NET、C/C++、Swift、Dart/Flutter、PHP、Ruby、Elixir，以及多语言/Monorepo、Container/IaC；不硬编码版本或擅自更换包管理器。
- [ ] 新增通用 Validation Matrix，把验证抽象为行为/接口/集成/用户流程/跨组件/外部依赖/构建运行/治理等风险维度；现有 Browser/PostgreSQL/Provider 细节保留为适用项目的专项 profile，不删除。
- [ ] `CHANGE.template.md` 不再要求所有项目机械使用 Browser/PostgreSQL/Provider 行名，同时保留对这些专项层的映射和使用条件。
- [ ] 建立“旧规则 → 新位置”完整保留映射，覆盖原 `SKILL.md` 与现有 references 的重要规则，明确哪些内容是核心、条件式专项或项目本地 override，避免重组时静默丢失。
- [ ] 保持现有 `project-discovery.md`、`development-workflows.md`、`repository-constraints.md`、`collaboration.md`、`testing-strategy.md`、`verification-review.md` 中有价值细节可达；不改名/删除已归档 CI Change 仍引用的 `testing-strategy.md`。
- [ ] 新增自动化回归测试，验证通用路由、主要语言覆盖、关键旧规则仍可达、AIMA Web/PostgreSQL 专项内容仍存在。
- [ ] 本轮新鲜目标测试、Repository Quality/CI 和 Completion Gate 证据支持交付结论。

# 范围

- 重组 `.agents/skills/reliable-vibe-coding/SKILL.md` 的入口和路由结构。
- 新增跨项目/阶段/语言/通用验证参考文件及规则保留映射。
- 必要时调整 `change-management.md`、`completion-gate.md`、`CHANGE.template.md`，使 Change/Validation Matrix 本身不绑定单一技术栈。
- 保留现有 `testing-strategy.md` 作为 Web/API/数据库/Provider 边界的高价值专项策略，并从通用验证策略明确路由到它。
- 增加仓库级 Unit 测试验证 Skill 结构和关键规则可达性。
- 扩充 `rvc.py` 对常见多语言 Manifest/Workspace 的只读发现能力，但不改变缓存/Change schema。

# 非目标

- 不修改 AIMA 产品代码、HTTP/Canonical Contract、数据库 Schema/Migration、前端功能或运行时。
- 不修改当前六层 CI Workflow 架构，不把 Skill 测试塞进新的平行 Workflow。
- 不删除现有 references 中仍有效的细节，不把十几条硬规则压缩成抽象口号。
- 不为所有语言制定一套固定测试框架、目录结构、包管理器或格式化工具。
- 不自动升级任何语言、运行时、依赖、Action、镜像或锁文件。

# 必须保持不变

- 系统/开发者/用户/仓库 `AGENTS.md` 等高优先级规则始终高于通用 Skill。
- 仓库事实、锁文件、真实命令、当前实现和本轮新鲜验证证据优先，不从聊天或缓存猜实现。
- L1/L2/L3 分级、L2/L3 Change、Requirement Traceability、Completion Audit、两阶段 Review、Red-Green-Refactor、根因调试、最小兼容实现、并行冲突检查、文档同步和 Git 安全边界不降低。
- 现有 `testing-strategy.md` 路径与 Browser Mock / Backend/API/PostgreSQL / Contract / Real Full-stack / Real Provider Probe 的详细语义保留，避免破坏仍引用该 Source 的归档 Change。
- `.reliable-vibe-coding/project-context.json` 和 `rvc.py` 当前缓存/Change 协议不做破坏性格式迁移。

# 关键决策

1. 采用“核心流程 + 条件式 profiles/路由”而不是为每种语言复制一套 Skill；避免规则漂移。
2. 现有 Web/API/PostgreSQL/Provider 测试策略保留为专项 profile；通用层只抽象风险与证据职责，不弱化原有测试边界。
3. 本次不迁移 `rvc.py` 的缓存协议；只扩展 Manifest/Workspace 发现表面，保持 `rvc-project-context/v1` 与 `rvc-change/v1` 不变。
4. 原规则只允许移动、分类或消除完全等价重复；不能因缩短主 `SKILL.md` 删除约束。新增 preservation map 作为人工/自动回归入口。
5. AIMA 自身 PostgreSQL、Blueprint 编号、中文 Git 提交等项目约束继续由 `AGENTS.md` / Blueprint 承载；通用 Skill 只定义“发现并服从项目本地 Overlay”的机制。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Skill 必须适用于不同项目、不同研发阶段、不同编程语言 | user:2026-08-25-portable-skill | not_satisfied | 四维路由、语言 profile、通用验证策略和多语言 Manifest 发现已实现；待本轮新鲜 Green/CI 证据确认 |
| R2 | 重新组织现有 Skill，使大模型能严格按流程工作 | user:2026-08-25-portable-skill | not_satisfied | 主 Skill 已把“先路由、命中 reference 必须读取、再工作”设为强制入口；待验证与 Review |
| R3 | 不丢失任何现有内容和有价值细节，不做过度总结 | user:2026-08-25-preserve-skill-details | not_satisfied | `rule-preservation-map.md` 已逐层映射原主 Skill/8 个 references；专项 `testing-strategy.md` 原路径保留；待完整差异与回归复核 |
| R4 | 不从仓库历史或聊天猜实现，按当前 AGENTS 与真实仓库事实工作 | AGENTS.md | satisfied | 任务从仓库 `AGENTS.md`、当前 Skill/references/测试恢复事实；期间 main 前进后重新比较并合入最新 `9b6457d3549dea57f85d52bf664227b47791b9b4` |
| R5 | L2 变更维护 Change、Validation Matrix、Completion Audit 和新鲜证据 | .agents/skills/reliable-vibe-coding/references/change-management.md | not_satisfied | 当前 Change 已建立并持续维护；待 Matrix/Audit/Ready/CI 最终证据 |
| R6 | 已完成 CI Change 对 `testing-strategy.md` 的 Requirement Source 不得因本次重组失效 | changes/archive/2026-08/CHG-20260825-ci-long-term-risk-layers/CHANGE.md | satisfied | `testing-strategy.md` 文件路径与专项内容保留；归档 Change R5 Source 仍可解析 |

# Validation Matrix

本 Change 仍运行在 AIMA 仓库，因此按当前仓库专项 testing profile 记录；通用 Skill 的新模板已改为技术栈无关的语义层。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本次不改变前端产品行为或用户页面 |
| Backend/API/PostgreSQL Integration | not_applicable | 本次不改变后端、数据库、Job/Worker 或持久化行为 |
| Contract / Generated Client | not_applicable | 不修改产品 Pydantic/OpenAPI/generated client Contract |
| Real Full-stack Golden Path | not_applicable | 不改变跨前后端真实产品接线；仓库 Full-stack CI 若运行只作为无回归辅助证据，不替代本任务主验证 |
| Real Provider Probe | not_applicable | 不修改 Provider endpoint、字段、分页、capability 或 pricing |
| Docs / Governance / Other | required | Skill 文档结构回归、`rvc.py` Manifest 分类、Change/template 语义、仓库 Unit 测试、Ruff/Docs/Secret/CI、Ready Check |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取用户要求、AGENTS、原/当前 Skill 与所有受影响 references/template/test，独立重建“通用化且不丢规则”的完成定义。
- [ ] change_coverage：逐条比较原规则与 preservation map/新结构，确认没有 requirement omission。
- [ ] reverse_audit：从不同项目形态、研发阶段、语言栈反向检查能否路由到正确流程；再从原有 Web/PostgreSQL/Provider 规则反向确认仍可达。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零，所有不适用项有事实依据。

# 任务

- [x] 调查当前 Skill、references、模板、脚本、测试和 AIMA 上游规则
- [x] 检查 Active Change 冲突并确定保留 `testing-strategy.md` 路径
- [x] 先建立 Skill 通用性/规则保留回归测试并取得正确失败证据：Ruff 通过后 `tests/unit` 为 628 passed / 5 个目标失败
- [x] 新增四维任务路由与编程语言/工具链 profile
- [x] 新增通用 Validation Matrix 规则
- [x] 重组主 `SKILL.md`，保持关键硬门禁在入口层可见
- [x] 调整 Change/Completion/template 的技术栈中立表达
- [x] 建立原规则完整 preservation map
- [x] 扩充 `rvc.py` 多语言 Manifest 发现并增加回归覆盖
- [ ] 运行实现后目标测试、相关测试、质量门禁和 Ready Check
- [ ] 完成 Requirement Traceability、Completion Audit 和两阶段 Review

# 验证

## 计划

- Red：`tests/unit/test_reliable_vibe_coding_portability.py` 已在实现前证明缺少四维路由、主要语言 profile、generic Validation Matrix/preservation map/template 时失败；有效 Red 为 `628 passed / 5 failed`，失败均指向本 Change 目标。
- Green：当前实现后重新运行 `tests/unit/test_reliable_vibe_coding_portability.py` 与 `tests/unit`。
- 相关测试：现有 `.agents/skills/reliable-vibe-coding/tests/`、`tests/unit`、`rvc.py` Manifest 分类回归。
- 静态/文档：Repository Quality 中 Ruff/Secret/Docs/Architecture 等受影响项；不新增平行 Workflow。
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`。
- PR：Draft PR #222；完成前取得当前候选 HEAD 的 CI / Change Completion Gate 新鲜证据。

## 新鲜证据

- Red：实现前 CI `32794478331` 中 Ruff/mypy 通过，Unit 阶段 `628 passed / 5 failed`；5 个失败均为缺少本次要求的通用路由/文件/template 行为。
- 当前 HEAD 实现后 CI 正在运行；尚未形成可用于完成声明的最终 Green/Ready 证据。

# 文档影响

- Skill 自身 references/template 属于本次主要交付物。
- AIMA 产品 Blueprint/模块 README/API 文档不受产品行为影响；AIMA 项目专属规则仍由根 `AGENTS.md` 和 Blueprint 承载，不迁入通用核心。

# 交付

- Branch：`refactor/reliable-vibe-coding-portable-routing`
- PR：#222（Draft）
- Release：不适用
