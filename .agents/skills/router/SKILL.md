---
name: router
description: Agent_Skills 的唯一跨 Skill 控制面。每个使用 Agent_Skills 的任务都必须先进入本 Skill，再按当前项目事实选择专业 Skill 与必需 References；只负责路由、上下文和 Handoff，不制定项目执行计划或执行专业工作。Use before every other Agent_Skills skill for all tasks, in both Source Mode and Runtime Mode.
---

<!-- agent-routing:v1
{"协议":"Agent Skills Skill路由/v1","Skill":"router","触发":{"包含":{"维度":"风险","取值":["L1","L2","L3"]}}}
-->

# Agent Skills Router

本 Skill 是 Agent_Skills **唯一的跨 Skill Catalog / Router 事实源**。它负责回答：当前任务应先恢复哪些项目事实、进入哪些正式 Skill、何时加载哪些 完整约束，以及加载失败时必须怎样停止或降级。

它不是第二套 Coding / Review / Docs / Figma 专业规则，也不是目标项目的技术栈说明。各 Skill 的详细规则仍由自己的 `SKILL.md + 当前场景所需完整约束` 承担；目标项目自己的规则和真实文件负责说明“这个项目具体是什么”。Router 的普通 metadata trigger 只满足统一路由清单格式；Source Mode 由 `ENTRY.md` 无条件进入本 Skill，Runtime evaluator 也把正式 `router` 视为保留控制面，不依赖该普通 trigger 才命中。

## Anti-Agent Boundary

Router 只输出当前任务的 Skill 选择、必需 当前场景所需完整约束、最低风险、Handoff 目标和失败边界。它不生成项目级执行计划，不创建子 Agent，不拆分或调度开发任务，不调用项目实现工具，不修改代码/设计/文档，不运行测试、Git、CI、发布或部署，也不接管专业 Skill 的工作流。

进入专业 Skill 后，由该 Skill 在用户授权和项目规则内决定自己的调查、计划、实现与验证；Router 不持续充当上位执行者。需要组合多个专业 Skill 时，Router 只声明并集、顺序与交接条件，不替它们执行。

## 1. 先建立目标项目事实

无论通过 ChatGPT 网页端直接读取 Agent_Skills 源仓库，还是通过 Release Runtime 在目标项目中使用本 Router，都必须先读取当前目标项目及上级适用的 `AGENTS.md`、`CONTRIBUTING` 或同等项目规则，再按任务需要读取真实代码、Manifest/lock、Contract、Schema/Migration、配置、测试、CI、正式文档和当前设计事实。

项目自己的事实优先于 Agent_Skills 中的通用示例。Agent_Skills 规定“怎样可靠工作”，不能反向发明“这个项目是什么”。

以下事实必须来自目标项目当前真实内容或用户/Owner 已确认决定：

- 语言、Runtime、编译器、包管理器、Manifest、锁文件和构建/测试工具；
- Web/Backend/Frontend/Mobile/Desktop/CLI/Library/Data/Embedded/IaC 等实际项目形态；
- 框架、数据库、缓存、消息系统、外部 Provider 与部署平台；
- 模块职责、目录 Owner、公共 API/ABI/CLI、Contract、Schema、Migration 和数据语义；
- 正式需求、Roadmap、ADR/RFC/Spec/OpenSpec/Change、CI Job、发布和回滚流程；
- Figma/设计系统中的项目品牌、页面尺寸、Token、组件名、业务字段、Prototype、动态数据和用户流程。

看到 `package.json`、`pyproject.toml`、`Cargo.toml`、`go.mod`、`pom.xml` 等文件，只能证明对应事实入口存在，**不能单凭文件名推出 React、FastAPI、PostgreSQL** 或其他具体技术路线。Greenfield / Prototype 没有稳定工程事实时，先以用户已确认目标、硬约束和预期运行环境作为上游事实，再建立最小工程基线。

## 2. 正式 Skill Catalog 与动态发现

正式 Skill 集合始终从：

```text
.agents/skills/*/SKILL.md
```

动态发现。当前仓库实际存在：

| Skill | 当前职责 | 正式入口 |
| --- | --- | --- |
| `router` | 无条件入口、动态 Catalog、跨 Skill 选择、上下文装配与 Handoff | [`.agents/skills/router/SKILL.md`](SKILL.md) |
| `coding` | 通用研发、调试、验证、Change、Git/CI 与交付 | [`.agents/skills/coding/SKILL.md`](../coding/SKILL.md) |
| `review` | 独立 Review、Findings、测试充分性与 re-review | [`.agents/skills/review/SKILL.md`](../review/SKILL.md) |
| `docs` | 技术文档事实同步、审查、编写与更新 | [`.agents/skills/docs/SKILL.md`](../docs/SKILL.md) |
| `figma` | Figma 设计事实、Canvas/Prototype、设计系统、Ready 与 Design-to-Code 交接 | [`.agents/skills/figma/SKILL.md`](../figma/SKILL.md) |

这些名称只是当前 Catalog，**不是分发白名单**。新增合法 `.agents/skills/<name>/SKILL.md` 后，Runtime、Project Payload、manifest、测试和 Release 仍应依赖动态发现，而不是要求在 Bootstrap 里同步另一份固定名单。

Review、Docs、Figma 不复制第二套 Coding 研发规则；Coding 也不复制第二套 Figma/Docs/Review 专业细则。

## 3. 每个研发任务的固定入口

处理代码分析、方案设计、功能开发、Bug 修复、重构、测试、Review、文档、Figma、Git、CI、PR、Release 或交付任务时：

1. 先按第 1 节恢复当前目标项目事实，只读取与当前任务直接相关的最少充分内容；
2. 由本 Router 根据项目形态、研发阶段/任务类型、实际语言/工具链、L1/L2/L3 风险、意图、能力、治理和授权事实，选择一个或多个专业 Skill；
3. 代码分析、方案、实现、调试、测试、CI、Git、Release 或交付命中 [`.agents/skills/coding/SKILL.md`](../coding/SKILL.md)；纯文档、纯设计或独立审查只按真实需要叠加 Coding，不把它当作所有任务的上位入口；
4. 任一专业 Skill 要求读取某个 `当前场景所需完整约束/` 文件时，必须在执行对应动作前取得该 完整约束 的完整正式原文，不能只读 Skill 主文件后凭印象补流程；
5. 只有任务命中的专业 Skill 才进入对应主文件，不机械读取全部 Skills 或全部 当前场景所需完整约束；
6. 能由当前目标项目仓库确认的事实先自行检查，不从历史聊天、旧缓存或 Skill 示例猜当前实现。

Router 只决定“该读什么、按什么顺序交接”；专业 Skill 决定“在自己的职责内怎样工作”。

## 4. 双模式同源路由与 完整约束 加载

Source Mode 与 Runtime Mode 共享同一套 canonical `SKILL.md + 当前场景所需完整约束`、嵌入式中文路由元数据、显式 内部约束身份、依赖、风险下限和版本身份。两种模式只改变 required Context 的取得通路，不改变规则语义。

### 4.1 路由不是单选分类

先把当前已确认任务事实按稳定维度组合：

```text
执行模式 / 项目形态 / 阶段 / 风险 / 工具链
范围 / 意图 / 治理 / 能力 / 授权
```

多个事实同时命中时取 Skill/完整约束 **并集**，再展开依赖闭包并应用最高风险下限；不能挑一个“主类型”丢掉其他 required Context。事实仍未知时必须明确列入未知项并保守扩大，不能在信息不足时选择狭窄路线。

`授权` 只记录宿主/用户当前明确给出的边界，不能因为路由中出现“允许 Git/发布”就自行获得真实权限。

### 4.2 Source Mode：直接读取 canonical 原文

当 Agent 能访问 Agent_Skills 源仓库时：

```text
任务事实
→ 当前 canonical metadata 的同一匹配/并集/依赖/风险语义
→ 命中 Skill Core 与 required 当前场景所需完整约束
→ 直接读取源仓库中每个 required 完整约束 的当前完整原文
```

不得使用历史聊天、摘要、旧缓存或目标项目中的安装副本替代当前 canonical 文件。Source Mode 不启动用户电脑上的本地 Runtime，也不调用 Runtime MCP。

### 4.3 Runtime Mode：Task Route → required Context

Runtime 安装到目标项目后，Project Payload 只包含薄 `ENTRY.md`、本 Router Skill、其他 Skill Core 和运行资产，**不包含 `当前场景所需完整约束/` 或 Stub**。因此不得尝试打开本地同名 完整约束。

宿主模型应按顺序调用：

```text
agent_skills_route_contract
→ agent_skills_start_task
→ 根据目标项目当前事实构造中文 Task Route
→ agent_skills_submit_route
→ agent_skills_load_required_context(路由令牌)
→ 使用返回的完整原文
→ 事实变化时追加 submit_route 并加载新增 Context
→ agent_skills_checkpoint
```

Task Route 是 Agent/Runtime 内部协议，不是用户日常配置；用户继续用自然语言描述任务。公共 route contract 只给出当前中文维度/取值与公开 Skill，不会枚举私有 完整约束 mapping。

同一 task 的 route 只能单调扩展；只有显式 `start_task` 新任务才能清空。`load_required_context` 默认只返回尚未加载的新 required Context，不能请求任意 ID。`checkpoint` 只汇总 Runtime 内部缺失数量，不能冒充 Requirement Traceability、Completion Audit、Review、Docs、测试或 CI。

每个返回 Context 的 `SHA256`、字节数和完整原文都必须通过当前 Bundle 完整性校验；失败时不得使用摘要、缓存或其他路径内容代替。

### 4.4 版本、失败与停止

同一次任务使用的 Router、Skill Core、Runtime、Bundle、routing identity 和 Project Payload 必须来自同一 Release。协议/digest 不一致、路由词汇非法、令牌失效、required Context 无法取得或完整性失败时，明确报告并停止依赖相应规则的动作；不得降级成旧记忆或自写摘要。

## 5. 低歧义组合示例

下表只演示怎样组合事实和进入 Owner，不替代各 Skill 的正式规则，也不是固定 完整约束 白名单。Source Mode 必须读取表中 Owner 当前命中的 canonical 原文；Runtime Mode 先通过公共 route contract 取得当前合法词汇，再提交所列信号。实际发现更多事实时，两种模式都按并集追加 required Context。

| 案例 | 命中原因与叠加 | Source Mode 读取 | Runtime Mode 任务信号 |
| --- | --- | --- | --- |
| L1 机械修改 | 已确认行为、接口、数据和验收不变；只叠加事实恢复与 L1 验证，不创建 L2/L3 Change | Coding Core + canonical 任务路由规则；只读当前项目直接事实 | `执行模式=实现；风险=L1` |
| L2 Feature | 新增可观察行为；先建立最小充分任务契约和 Validation Matrix，只有出现跨 Owner/跨 PR/长期审计/项目门禁等持久治理事实时再追加 Change 与 Completion Gate | Coding Core + Feature、最小充分治理与验证 canonical 当前场景所需完整约束；命中持久治理事实时再加载 Change/完成门禁 | `执行模式=实现；阶段=功能开发；风险=L2；能力=测试`；发现真实持久治理事实后再追加对应 `治理` 信号 |
| L3 public API | 修改公共消费者 Contract；在 Feature 上叠加公共边界、兼容、独立 Review 和交付验证 | Coding Core + L3 Change、Contract、验证、完成与 Review canonical 当前场景所需完整约束 | `执行模式=方案,实现；阶段=需求设计,功能开发；风险=L3；范围=公共契约,API` |
| Schema Migration | writer/reader 与历史数据都会受影响；叠加 Schema、Migration、回滚和真实依赖验证 | Coding Core + Contract/Schema/Migration、Change、验证与完成 canonical 当前场景所需完整约束 | `执行模式=方案,实现；阶段=需求设计；风险=L3；范围=Schema,Migration` |
| Bug / Failure / Incident | 先复现并证伪根因；修复时叠加回归测试，Incident 再叠加运维/恢复边界 | Coding Core + 根因调试、风险对应 Change/验证/完成 canonical 当前场景所需完整约束 | `执行模式=诊断,实现；阶段=缺陷修复`；Incident 追加 `运维,故障处置,L3` |
| Refactor / Performance | 必须先证明行为不变或性能根因；叠加基线、目标度量和回归验证 | Coding Core + 根因/设计实施、Change 与验证 canonical 当前场景所需完整约束 | `执行模式=诊断,实现；阶段=重构` 或 `性能优化；风险=L2/L3` |
| Frontend | 真实范围包含用户界面；叠加前端状态、Contract 和用户工作流，但不因 `package.json` 推断 React/Figma | Coding Core + Frontend/Design-to-Code；真实存在 Web/API 边界时再读分层验证 canonical 当前场景所需完整约束 | `执行模式=实现；项目形态=前端Web；阶段=功能开发；范围=前端；风险=L2` |
| Figma review-only | 用户只要求设计审查且无写授权；叠加 Figma 事实审计与 Review 输出，不进入生产实现 | Coding Core + Figma Skill 及审查/Findings/layout canonical 当前场景所需完整约束；适用时进入 Review Skill | `执行模式=审查；意图=Figma review-only；能力=Figma；授权=允许只读` |
| Figma review-and-fix | 已授权修改设计；叠加 Figma 审查、修复、写后复核，完成后回 Coding | Coding Core + Figma Skill 的审查/修复/可用性 canonical 当前场景所需完整约束 | `执行模式=实现；意图=Figma review-and-fix；能力=Figma；授权=允许修改项目` |
| Figma baseline-ready | 目标是正式 Design-to-Code 基线；叠加真实系统映射、设计系统、Prototype、Ready 门禁 | Coding Core + Figma Skill 的 baseline-ready 全部命中 canonical 当前场景所需完整约束 | `执行模式=方案；意图=Figma baseline-ready；能力=Figma；风险=L2/L3` |
| Figma → Code | 既有设计又要生产实现；先完成 Figma Ready，再返回 Coding 叠加前端、测试、Review 和交付 | Coding Core + Figma baseline/Design-to-Code + Coding Frontend canonical 当前场景所需完整约束 | `执行模式=实现；项目形态=前端Web；阶段=功能开发；范围=前端；意图=设计转代码；能力=Figma,测试` |
| Docs not_applicable | 代码/行为变化经事实确认不影响任何正式文档；只记录依据，不进入 Docs | Coding 当前命中 canonical 当前场景所需完整约束；不读取 Docs Skill | 不提交 Docs 意图；保留实际实现/验证信号 |
| Docs targeted | 只有局部 README/API/配置说明受影响；叠加 Docs targeted 和事实同步 | Coding Core + Docs Skill 当前 targeted canonical 当前场景所需完整约束 | `执行模式=实现；意图=Docs targeted` |
| Docs full | 核心架构、公开 Contract 或多份正式文档变化；叠加完整事实恢复、编写、审查和回到 Coding | Coding Core + Docs Skill 全量命中 canonical 当前场景所需完整约束 | `执行模式=实现；意图=Docs full；风险=L2/L3` |
| Code Review / Audit | 用户显式审查或 Coding 要求独立 Review；叠加需求重建、Findings、测试充分性与 re-review | Coding 完成/验证 canonical 当前场景所需完整约束 + Review Skill 当前命中 canonical 当前场景所需完整约束 | `执行模式=审查；阶段=审查；意图=代码审查`，需要测试/修复时追加对应意图与授权 |
| Dependency / Runtime Upgrade | 版本、锁文件或 Runtime 变化；叠加工具链、兼容、安全、构建和回滚，不因有新版本自动升级 | Coding Core + 工具链；涉及 Agent_Skills Runtime 时再读安装/Runtime canonical 当前场景所需完整约束 | `执行模式=实现；意图=依赖升级` 或 `Runtime 升级；工具链=已确认；风险=L2/L3` |
| Git / PR / Release | 进入交付且真实授权已确认；叠加完成验证、Git/CI/Release 边界，路由标签不授予权限 | Coding Core + 完成前验证、Git/交付 canonical 当前场景所需完整约束；需要时进入 Review | `执行模式=Git,验证` 或 `发布；阶段=交付；意图=PR Ready/Git 交付/Release；能力=Git；授权=允许 Git/允许发布`，且授权值只能来自上位事实 |
| Runtime / Project Payload | 修改 Bundle、Task Route、MCP、安装或分发；叠加 L3 Contract、no-Stub、ownership、artifact 与三平台验证 | Coding Core + Bootstrap 安装 + Runtime 分发 canonical 当前场景所需完整约束 | `执行模式=实现；风险=L3；范围=Runtime,Runtime Bundle/Project Payload,MCP；意图=Runtime Bundle/Project Payload` |
| Skill Mutation | 改变 Skill/完整约束 正文、trigger、Owner 或结构；叠加内容守恒、Stable ID、Conformance 与独立 Review | 根 AGENTS + Maintenance + Router + Coding Core + Skill Mutation + 受影响 Skill canonical 原文 | `执行模式=实现；意图=Skill Mutation；治理=要求完成门禁；风险=L2/L3` |
| Greenfield | 尚无可靠 Manifest/lock/架构事实；叠加目标/硬约束确认与最小可验证工程基线，不套用示例技术栈 | Coding Core + 项目发现/Greenfield/任务路由 canonical 当前场景所需完整约束 | `执行模式=方案；项目形态=Greenfield；阶段=仓库初始化；风险=L2`，未知维度显式列入 `未知项` |
| 复杂多 Skill 叠加 | 例如 L3 Figma→Code 同时改 API、Docs、Review 并准备 PR；必须取 Coding、Figma、Docs、Review 与 Git 全部并集 | Coding Core + 四个专业 Skill 当前命中 canonical 当前场景所需完整约束 + 完成/交付 当前场景所需完整约束 | 同时提交 `实现,审查,验证,Git`、真实项目形态/范围、`L3`、`设计转代码,Docs full,Review-and-fix,Git 交付`、治理/能力/授权事实 |

## 6. Bootstrap / Runtime 专项路由

- 触发：首次安装/升级 Agent_Skills、创建/补充目标项目 `AGENTS.md`、修复 managed block，或修改 Bundle、Routing、MCP、Project Payload、install manifest 与宿主 MCP 配置。
- 必须动作：先恢复当前安装/ownership/schema/宿主配置事实，再读取对应完整 canonical 完整约束；不得自由重写项目 Overlay、managed ownership 或 Runtime Contract。
- 不适用：普通业务功能、文档或设计任务没有触及这些安装/Runtime 边界时，不进入本专项路由。
- 交接：Bootstrap/managed block 进入 Coding 当前场景所需完整约束；Runtime/分发边界在此基础上进入 Coding 当前场景所需完整约束。
- 返回：完成安装/Runtime 实现与真实 smoke 后回到 Coding 的验证、Review、Git/交付流程。
- 失败关闭：schema、ownership、artifact、required Context 或宿主能力无法验证时，停止写入/交付，不猜测迁移或降级为旧 Runtime 通路。

Bootstrap/managed block 必须读取：

当前场景所需完整约束

涉及本地 MCP Runtime 构建/Release/项目安装/升级、Project Payload、Routing Manifest/Task Route、Bundle、installation manifest 或宿主 MCP 配置，还必须读取：

当前场景所需完整约束

## 7. Figma 路由

- 触发：任务涉及 Figma 创建、修改、整理、审查、设计系统、Prototype、正式设计基线验收，或按 Figma 实现/替换页面。
- 必须动作：读取并执行 Figma Skill；Figma 负责设计事实、Canvas/Prototype、设计修复和 `READY / READY_WITH_NOTES / NOT_READY`。
- 不适用：没有 Figma/design-to-code 事实的普通 Frontend、CLI、Backend 或文档任务不进入 Figma。
- 交接：Router 把设计事实、审查或修复交给 [`.agents/skills/figma/SKILL.md`](../figma/SKILL.md)；同时存在生产实现时再叠加 Coding。
- 返回：达到 `READY / READY_WITH_NOTES` 后，只有存在真实代码、测试、CI、Git 或交付工作时才进入 Coding；review-only 直接返回用户边界。
- 失败关闭：Figma Skill/required 完整约束 无法读取、工具事实不足或结果为 `NOT_READY` 时，不得把已知缺陷写入生产实现，也不得把 Figma Ready 冒充代码/PR/Release Ready。

## 8. Review 路由

- 触发：用户显式要求 Code Review/Audit，专业 Skill 判断需要独立 Review，或当前 L2/L3 Change/PR Ready 门禁要求 Review。
- 必须动作：读取 Review Skill，独立重建上游要求与风险，审查 Findings、测试充分性和 re-review；不得把作者清单或绿色测试当作需求全集。
- 不适用：纯事实恢复且没有审查请求/门禁，或经项目规则确认的隔离 L1 机械任务，不机械进入独立 Review。
- 交接：Router 要求发起方把当前 Review Target、base/head、授权、上游事实和新鲜验证交给 [`.agents/skills/review/SKILL.md`](../review/SKILL.md)。
- 返回：确认代码 Finding 需要修复时进入 Coding 建立失败证据并最小修复，随后返回 Review re-review；无 Finding 时返回原专业 Skill 或用户边界。
- 失败关闭：Review Skill/required 完整约束、目标 diff 或关键上游事实不可得时，不得声称已独立审查或可合并。

## 9. Docs 路由

- 触发：任一专业 Skill 判断存在文档影响，或用户显式要求技术文档审查、事实同步、编写或更新。
- 必须动作：读取 Docs Skill，先从代码/Contract/Schema/配置等当前事实判断 `not_applicable`、`targeted` 或 `full`，再同步受影响正式文档。
- 不适用：已用当前差异和文档事实证明行为、接口、配置、架构和用户操作均未受影响时，记录依据并保持 Docs `not_applicable`。
- 交接：发起方把实现事实、Docs Impact 和受影响文档域交给 [`.agents/skills/docs/SKILL.md`](../docs/SKILL.md)；默认不机械扫描全部 Markdown。
- 返回：文档同步/审查完成后回到原专业 Skill 的一致性与交付验证；若 Docs 发现代码/Contract 缺陷，再进入 Coding 修复事实后执行 targeted re-review。
- 失败关闭：Docs Skill/required 完整约束 或实现事实不可得时，不得写推测性说明、迎合 Bug 或宣称文档已同步。

## 10. 失败、冲突与权限边界

- 某个必需 Skill、Router 或 完整约束 缺失、无法读取或不可验证，或者 Runtime route/required Context 无法取得并验证完整原文时，明确报告真实阻塞，不得假装已经遵守；
- 通用 Skill 与更高优先级指令或更具体项目规则存在冲突时，遵守更高优先级和更具体规则；无法安全解析冲突时停止受影响动作并提请 Owner，而不是自行选择有利解释；
- 不绕过目标项目已有 CI、Branch Protection、PR、Release、Migration、安全或其他质量门禁；
- 没有相应授权时，不自动获得创建/切换分支、修改文件、提交、推送、创建 PR、合并、发布、部署、数据库写入或其他外部副作用权限；
- 不覆盖项目已有工作，不用 `git reset --hard`、`git clean -fd`、强制推送或历史重写制造“干净状态”。

## 11. Router 自身的维护边界

本 Skill 只拥有**跨 Skill 的发现、入口、加载和 Handoff**。以下细节必须继续留在各自 Owner：

- Coding 的 L1/L2/L3、TDD、调试、验证、Change、Git/CI/交付细节 → Coding `SKILL.md + 当前场景所需完整约束`；
- Review 的 Findings、测试审查与 re-review 方法 → Review；
- Docs 的文档事实、范围与写作/审查方法 → Docs；
- Figma 的 Canvas、Prototype、Owner、状态、Ready、失败处理与写后复核 → Figma；
- Runtime 的 Bundle/Routing/Task Route/Payload/MCP/安装/升级/回滚细节 → Coding 当前场景所需完整约束 + Runtime 实现。

不能为了让入口“自包含”再把这些专业细则复制回根 `AGENTS.md`、`AGENTS.managed.md`、`ENTRY.md` 或本 Router。
