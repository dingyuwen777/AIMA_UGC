---
name: router
description: Agent_Skills 的唯一跨 Skill 控制面。每个使用 Agent_Skills 的任务都必须先进入本 Skill，再按当前项目事实选择专业 Skill 与必需 References；只负责路由、上下文和 Handoff，不制定项目执行计划或执行专业工作。Use before every other Agent_Skills skill for all tasks, in both Source Mode and Runtime Mode.
---

<!-- agent-routing:v1
{"协议":"Agent Skills Skill路由/v1","Skill":"router","触发":{"包含":{"维度":"风险","取值":["L1","L2","L3"]}}}
-->

# Agent Skills Router

本 Skill 是 Agent_Skills **唯一的跨 Skill Catalog / Router 事实源**。它负责恢复任务事实、选择正式 Skill、加载 required 当前场景所需完整约束 和定义 Handoff；专业方法留在各 Skill，项目自己的规则与真实文件负责说明项目事实。

## Anti-Agent Boundary

Router 只输出 Skill 选择、必需 当前场景所需完整约束、最低风险、Handoff 和失败边界；不生成项目级执行计划，不创建子 Agent，不拆分或调度开发任务，不接管专业 Skill，也不执行代码/设计/文档/测试/Git/CI/发布/部署。组合多个 Skill 时只声明并集、顺序与交接条件。

## 1. 先建立目标项目事实

先读取目标项目当前目录及上级适用的 `AGENTS.md`、`CONTRIBUTING` 或同等规则，再按任务需要读取真实代码、Manifest/lock、Contract、Schema/Migration、配置、测试、CI、正式文档和设计事实。

项目自己的事实优先于通用示例。语言、Runtime、框架、数据库、模块 Owner、API/ABI/CLI、Schema、Migration、Provider、部署、设计 Token/组件/业务字段等都必须来自当前事实或 Owner 决定；**不能单凭文件名推出 React、FastAPI、PostgreSQL**。Greenfield 则以已确认目标、硬约束和运行环境建立最小基线。

## 2. 正式 Skill Catalog 与动态发现

正式 Skill 始终从：

```text
.agents/skills/*/SKILL.md
```

动态发现。当前仓库存在：

| Skill | 当前职责 | 正式入口 |
| --- | --- | --- |
| `router` | 无条件入口、动态 Catalog、跨 Skill 选择与 Handoff | [`.agents/skills/router/SKILL.md`](SKILL.md) |
| `coding` | 通用研发、调试、验证治理、Change、Git/CI 与交付 | [`.agents/skills/coding/SKILL.md`](../coding/SKILL.md) |
| `testing` | 测试策略、黑盒/User Journey、探索式、Integration/Workflow/Regression | [`.agents/skills/testing/SKILL.md`](../testing/SKILL.md) |
| `review` | 独立 Review、Findings、测试充分性/Evidence 与 re-review | [`.agents/skills/review/SKILL.md`](../review/SKILL.md) |
| `docs` | 技术文档事实同步、审查、编写与更新 | [`.agents/skills/docs/SKILL.md`](../docs/SKILL.md) |
| `figma` | Figma 事实、Canvas/Prototype、设计系统与 Ready | [`.agents/skills/figma/SKILL.md`](../figma/SKILL.md) |

这些名称**不是分发白名单**；Runtime、Project Payload、manifest、测试和 Release 必须继续动态发现。Review 只审测试充分性/Evidence，测试工程方法由 Testing 负责。

## 3. 每个研发任务的固定入口

1. 恢复当前目标项目最少充分事实；
2. 按项目形态、阶段、工具链、L1/L2/L3、意图、治理、能力和授权选择一个或多个 Skill；
3. 实现/调试/TDD/CI/Git/Release 进入 Coding；测试策略、功能/黑盒/User Journey、探索式、系统性 Regression 或独立验证进入 Testing；Review 发现 Test Gap 时叠加 Testing；`能力=测试` 或项目形态本身不触发 Testing；
4. 命中 完整约束 时必须在执行前取得其完整正式原文；
5. 不机械读取全部 Skills/当前场景所需完整约束，也不从历史聊天猜当前实现。

## 4. 双模式同源路由与 完整约束 加载

Source Mode 与 Runtime Mode 使用同一 canonical `SKILL.md + 当前场景所需完整约束`、中文路由 metadata、内部约束身份、依赖和风险下限，只改变 Context 取得通路。

### 4.1 路由不是单选分类

稳定维度为：

```text
执行模式 / 项目形态 / 阶段 / 风险 / 工具链
范围 / 意图 / 治理 / 能力 / 授权
```

多个事实取 Skill/完整约束 **并集**并展开依赖闭包；未知项保守处理。`授权` 只是已确认事实，不能自行授予权限。

### 4.2 Source Mode：直接读取 canonical 原文

```text
任务事实
→ canonical metadata 匹配/并集/依赖/风险
→ 命中 Skill Core 与 required 当前场景所需完整约束
→ 读取当前完整原文
```

不得用历史聊天、摘要、旧缓存替代 canonical Source；**目标项目中的安装副本**（含 managed block）**不作为当前通用治理语义来源**，项目自有规则仍必须读取。Source Mode 不调用本地 Runtime MCP。

### 4.3 Runtime Mode：Task Route → required Context

Project Payload 不含 canonical `当前场景所需完整约束/` 或 Stub。宿主按顺序调用：

```text
agent_skills_route_contract
→ agent_skills_start_task
→ agent_skills_submit_route
→ agent_skills_load_required_context(路由令牌)
→ 事实变化时追加 submit_route / load
→ agent_skills_checkpoint
```

Task Route 是内部协议。`load_required_context` 只返回当前 required Context；`checkpoint` 不能冒充 Traceability、Completion、Review、Docs、测试或 CI。每个 Context 的 `SHA256`、字节数和**完整原文**必须通过当前 Bundle 校验。

### 4.4 版本、失败与停止

同一任务的 Router、Skill Core、Runtime、Bundle、routing identity 和 Project Payload 必须同源同版本。协议/digest、required Context 或完整性失败时停止，不得以旧记忆或摘要降级。

## 5. 低歧义组合示例

| 案例 | 命中原因与叠加 | Source Mode 读取 | Runtime Mode 任务信号 |
| --- | --- | --- | --- |
| L1 机械修改 | 行为/接口/数据不变 | Coding Core + L1 路由 | `执行模式=实现；风险=L1` |
| L2 Feature | 新增可观察行为；先建立最小充分任务契约，持久治理按事实升级 | Coding + 验证；独立用户场景按需 Testing | `执行模式=实现；阶段=功能开发；风险=L2`；需要时加测试意图 |
| L3 public API | 公共消费者 Contract 变化 | Coding + Contract/兼容/完成；按门禁 Review | `执行模式=方案,实现；风险=L3；范围=公共契约,API` |
| Schema Migration | writer/reader/历史数据受影响 | Coding + Schema/Migration/回滚 | `执行模式=方案,实现；风险=L3；范围=Schema,Migration` |
| Bug / Failure / Incident | 先复现根因；独立回归按需 Testing | Coding 根因；需要时 Testing Regression | `执行模式=诊断,实现；阶段=缺陷修复` |
| Refactor / Performance | 证明行为不变或性能根因 | Coding + 基线/回归 | `执行模式=诊断,实现；阶段=重构/性能优化` |
| Frontend | 前端实现归 Coding，独立 Journey 归 Testing | Coding Frontend；按需 Testing | `执行模式=实现；项目形态=前端Web；范围=前端；风险=L2` |
| Testing only | 真实测试意图直接命中 Testing | Testing 当前命中 当前场景所需完整约束 | `意图=黑盒测试/功能测试/探索式测试/独立验证；能力=测试` |
| Figma review-only | 只读设计审查 | Figma + 适用 Review | `执行模式=审查；意图=Figma review-only；能力=Figma；授权=允许只读` |
| Figma review-and-fix | 授权修改设计 | Figma；存在生产实现再 Coding | `执行模式=实现；意图=Figma review-and-fix；能力=Figma；授权=允许修改项目` |
| Figma baseline-ready | 正式设计基线 | Figma baseline-ready | `执行模式=方案；意图=Figma baseline-ready；能力=Figma；风险=L2/L3` |
| Figma → Code | Figma Ready 后实现；独立验收按需 Testing | Figma + Coding Frontend；按需 Testing/Review | `执行模式=实现；范围=前端；意图=设计转代码；能力=Figma,测试` |
| Docs not_applicable | 已证明无文档影响 | 当前专业 Skill | 不提交 Docs 意图 |
| Docs targeted | 局部正式文档受影响 | Coding + Docs targeted | `执行模式=实现；意图=Docs targeted` |
| Docs full | 架构/公开 Contract/多文档变化 | Coding + Docs full | `执行模式=实现；意图=Docs full；风险=L2/L3` |
| Code Review / Audit | Review 独立审实现和测试充分性 | Coding 研发规范 + Review；Test Gap 时 Testing | `执行模式=审查；意图=代码审查`；补测加 `Review-and-test` |
| Dependency / Runtime Upgrade | 版本/锁/Runtime 变化 | Coding 工具链；Runtime 时加安装/分发 Owner | `执行模式=实现；意图=依赖升级/Runtime 升级` |
| Git / PR / Release | 交付且真实授权已确认 | Coding 完成/Git/交付；按需 Review | `执行模式=Git,验证；阶段=交付；意图=Git 交付；能力=Git` |
| Runtime / Project Payload | Bundle/Route/MCP/安装分发 | Coding Bootstrap + Runtime 当前场景所需完整约束 | `执行模式=实现；风险=L3；范围=Runtime,MCP` |
| Skill Mutation | Skill/完整约束/trigger/Owner 变化 | 根 AGENTS + Maintenance + Coding Mutation + 受影响 Skill | `执行模式=实现；意图=Skill Mutation；治理=要求完成门禁；风险=L2/L3` |
| Greenfield | 无稳定工程事实 | Coding + 项目发现/Greenfield | `执行模式=方案；项目形态=Greenfield；阶段=仓库初始化；风险=L2` |
| 复杂多 Skill 叠加 | 同时存在多类真实事实 | 所有真实命中 Skill/当前场景所需完整约束 并集 | 提交真实 `实现/审查/验证/Git` 与范围/意图/治理/授权 |

## 6. Bootstrap / Runtime 专项路由

- 触发：首次安装/升级 Agent_Skills、`AGENTS.md` Bootstrap/managed block，或 Bundle/Routing/MCP/Project Payload/安装分发变化。
- 必须动作：恢复 installation/ownership/schema/宿主配置事实并读取对应完整 canonical 完整约束。
- 不适用：普通业务任务未触及这些边界。
- 交接：Bootstrap/managed block 进入 Coding 当前场景所需完整约束；Runtime/分发边界在此基础上进入 Coding 当前场景所需完整约束。
- 返回：真实 smoke 后回 Coding 验证/Review/Git。
- 失败关闭：关键事实不可验证时停止写入/交付。

当前场景所需完整约束

涉及 Runtime/Project Payload/Task Route/MCP 时还必须读取：

当前场景所需完整约束

## 7. Figma 路由

- 触发：Figma 创建、修改、审查、设计系统、Prototype、正式基线或 Design-to-Code。
- 必须动作：读取并执行 Figma Skill，输出 `READY / READY_WITH_NOTES / NOT_READY`。
- 不适用：无 Figma/design-to-code 事实。
- 交接：设计交给 [`.agents/skills/figma/SKILL.md`](../figma/SKILL.md)；生产实现再 Coding。
- 返回：Ready 后按真实需要进入 Coding/Testing/Review。
- 失败关闭：Figma/required 完整约束 不可得时不得冒充 Ready。

## 8. Testing 路由

- 触发：真实测试意图，或 Review/Coding 识别独立 Test Gap。
- 必须动作：读取 [`.agents/skills/testing/SKILL.md`](../testing/SKILL.md)。
- 不适用：隔离 L1、普通开发期最小 TDD；**不为了“走完所有 Skill”机械叠加 Testing**。
- 交接：Coding/Review 提供 Requirement、Test Target 和 Evidence Gap。
- 返回：生产缺陷 → Coding；修复后 → Testing Regression；合并判断 → Review。
- 失败关闭：Testing/目标/required Context 不可得时不得冒充测试证据。

## 9. Review 路由

- 触发：显式 Code Review/Audit、专业 Skill 请求独立 Review 或 L2/L3 门禁要求。
- 必须动作：读取 Review，独立重建上游要求，审 Findings 与测试充分性/Evidence。
- 不适用：无审查请求/门禁的纯事实恢复或隔离 L1。
- 交接：Review Target、base/head、上游事实交给 [`.agents/skills/review/SKILL.md`](../review/SKILL.md)；Test Gap → Testing。
- 返回：生产 Finding → Coding；独立 Regression → Testing；随后 re-review。
- 失败关闭：Review/目标 diff/关键事实不可得时不得声称可合并。

## 10. Docs 路由

- 触发：专业 Skill 判断有文档影响，或用户显式要求文档审查/同步/编写。
- 必须动作：读取 Docs，判断 `not_applicable / targeted / full` 后同步。
- 不适用：已证明行为/接口/配置/架构/用户操作无文档影响。
- 交接：实现事实和 Docs Impact 交给 [`.agents/skills/docs/SKILL.md`](../docs/SKILL.md)。
- 返回：完成后回原专业 Skill；发现实现缺陷则回 Coding。
- 失败关闭：Docs/实现事实不可得时不得写推测性说明。

## 11. 失败、冲突与权限边界

- 必需 Skill/Router/完整约束 **无法读取**时明确阻塞，**不得假装**已遵守；
- 冲突时遵守更高优先级和更具体规则；
- 不绕过 CI、**Branch Protection**、PR、Release、Migration 或安全门禁；
- **没有相应授权**时不获得修改、Git、发布、部署等副作用权限；
- 不用强制推送、历史重写或破坏性清理制造“干净状态”。

## 12. Router 自身的维护边界

Router 只拥有跨 Skill 的发现、入口、加载和 Handoff：Coding 的研发/TDD/验证治理归 Coding；Testing 的 Test Strategy/Black-box/User Journey/Exploratory/Integration/Regression 归 Testing；Review 的 Findings/充分性/re-review 归 Review；Docs、Figma、Runtime 细节分别归各自 Owner；Runtime 细节由 Coding 当前场景所需完整约束 + Runtime 实现承接。不能为了入口自包含把专业细则复制回 Router/ENTRY/managed block。