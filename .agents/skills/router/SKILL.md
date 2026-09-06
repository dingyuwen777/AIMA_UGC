---
name: router
description: Agent_Skills 的唯一跨 Skill 控制面。每个任务先进入本 Skill，再按当前项目事实选择专业 Skill 与必需 References；Router 只负责路由、上下文和 Handoff。Use before every other Agent_Skills skill in Source Mode and Runtime Mode.
---

<!-- agent-routing:v1
{"协议":"Agent Skills Skill路由/v1","Skill":"router","触发":{"包含":{"维度":"风险","取值":["L1","L2","L3"]}}}
-->

## 用户可见表达边界

用户关于目标项目的正常事实、解释、建议、风险、验证、状态和交付照常回答；描述 Agent 自身的进度、分工或执行过程时，对用户只描述项目实际动作、风险、证据和交付状态。不得把内部能力名称或标签转写成用户可见任务分工，也不得播报内部发现、选择、加载、路由、交接或约束取得过程。限制只针对内部身份转写，不限制正常工程解释；内部能力身份继续用于路由、约束加载和专业执行，不得为了用户可见隐藏而删除内部执行上下文。


# Agent Skills Router

本 Skill 是 Agent_Skills **唯一的跨 Skill Catalog / Router 事实源**。项目事实归目标项目，专业方法归各 Skill；Router **只输出** Skill、required 当前场景所需完整约束、最低风险、Handoff 和失败边界。

## Anti-Agent Boundary

Router **不生成项目级执行计划**，不创建子 Agent，**不拆分或调度开发任务**，不维护任务队列/Worker，**不接管专业 Skill**，也不执行代码/设计/文档/测试/Git/CI/发布/部署；多 Skill 只声明并集、顺序与交接。

## 1. 项目事实与确定性执行边界

先读目标项目及上级适用的 `AGENTS.md`、`CONTRIBUTING` 等规则，再按需读真实代码、Manifest/lock、Contract、Schema/Migration、配置、测试、CI、正式文档和设计事实。**项目自己的**事实优先；语言、Runtime、框架、数据库、Owner、API/ABI/CLI、Schema、Provider、部署、Design Token/业务字段不得猜，**不能单凭文件名推出 React、FastAPI、PostgreSQL**。

### 1.1 核验、决策、授权、证据与完成

- **事实恢复 / 核验**：默认由 Agent 自行查；能查出的不问。只有条款明确要求“提请用户 / Owner 决策 / 批准”且答案会实质改变业务/public Contract、Schema/数据、安全/权限、不可逆动作或重大技术路线时才问；已固化决定**不重复确认**。
- **Non-material Ambiguity Default**：未达到上述门槛时不阻塞、不提问；按“**项目既有模式 → 最小范围 → 最小副作用 → 最可逆 → 最少新机制**”自行决定，证据推翻后局部 re-plan。
- **Authorization Continuity**：已明确且未撤销的授权仅在**同目标、同范围、同副作用等级**跨 Handoff 延续，不重复确认。只读 < 测试资产写 < 生产代码写 < commit/push/PR < merge < Release < Deploy/生产变更；更高等级**不得继承升级**，必须已有对应 Requested Action + Effective Authorization。
- **Fresh Evidence Contract**：Evidence 绑定当前 **environment / Contract / Scope 与被验证的相关实现 revision**，未发生影响结论的变化即可复用；**不是由当前 Agent 启动**本身**不构成重新执行理由**。只有相关实现/Contract/输入/依赖/配置/环境/外部事实变化、现有证据不覆盖结论，或 **required gate** 明确要求 current-head/current-revision 时才重跑对应层；Change/Issue/PR 描述、Evidence 记录、排版等**不影响已验证边界的载体变化**不使开发侧 Evidence 失效。
- `完整验证证据 / 完整命令 / 完整输出` 只表示完整执行并检查**已选择的风险匹配 Evidence**，**不表示运行全仓测试、全部测试层或所有平台验证**；仍按 targeted-first 单调升级。
- **阻塞按依赖边界传播**：单一路径失败先回读结果并核验宿主等价能力，不直接判定仓库不可写；Git 细则归 Coding 交付 完整约束。仅阻塞确实缺少事实/Context/工具/环境/权限的依赖动作及声明，其他已授权工作继续；不绕过权限或质量门禁。required gate 受阻时整体才 `blocked/incomplete`。
- **Requested Outcome = Completion Scope**：**能力存在不等于继续追求更远阶段**。只读审查/测试/Mutation Audit 止于结论；提 PR→`允许开发并提交PR`（PR Ready）；合并主分支→`允许端到端交付`；审查后合并→`允许审查后交付`。先按真实命令归一化再路由，commit/push、引述或否定不升级授权；完整范围与收尾归当前场景所需完整约束。
- **Task-owned Cleanup**：Completion Scope 结束前删除本任务创建且无后续用途的临时/scratch/debug 产物；保留预存在/用户所有/仍作证据、交付物或输入的内容。未改变交付状态/运行输入时，不使既有 Green Evidence 失效。

## 2. 正式 Skill Catalog

正式 Skill 从 `.agents/skills/*/SKILL.md` 动态发现；下表只作导航，**不是分发白名单**。

| Skill | 职责 | 入口 |
| --- | --- | --- |
| `router` | 路由 | [`.agents/skills/router/SKILL.md`](SKILL.md) |
| `coding` | 研发/Git | [`.agents/skills/coding/SKILL.md`](../coding/SKILL.md) |
| `testing` | 测试 | [`.agents/skills/testing/SKILL.md`](../testing/SKILL.md) |
| `review` | 审查 | [`.agents/skills/review/SKILL.md`](../review/SKILL.md) |
| `docs` | 文档 | [`.agents/skills/docs/SKILL.md`](../docs/SKILL.md) |
| `figma` | 设计 | [`.agents/skills/figma/SKILL.md`](../figma/SKILL.md) |

Runtime/Project Payload/manifest/测试/Release 也动态发现；Review 判充分性，测试方法归 Testing。

## 3. Owner-gated 固定入口

1. 恢复最少充分事实；
2. 按任务对象/专业意图选 Owner；其余维度只细化已命中 Owner；
3. 实现/调试/TDD/CI/Git/Release → Coding；测试策略/功能/黑盒/Journey/探索式/Regression/独立验证 → Testing；源码/PR/diff 审查 → Coding + Review；Figma → Figma；技术文档 → Docs。共享 `审查/验证`、`能力=测试/Figma/Git` 不制造无关 Owner；
4. 仅在已命中 Owner 内匹配 完整约束；显式 dependency 可跨 Skill；
5. 命中 完整约束 必须在执行前取得**完整原文**；
6. 不机械读全部 Skills/当前场景所需完整约束。

## 4. 双模式同源路由

Source/Runtime 使用同一 canonical metadata、内部约束身份、依赖和风险下限，只改变 Context 取得通路。

Owner 选择时 `项目形态 / 风险 / 工具链 / 范围 / 治理 / 授权` 是 refinement，不独立制造 Owner。固定点：

```text
任务事实
→ Skill Core Owner 投影取并集
→ Owner 内 完整约束 匹配
→ dependency closure
→ 风险/Owner 扩展后重复至稳定
```

未知项只扩大相关候选，不导出全库；授权只是事实，不授予权限。

### 4.1 Source Mode

```text
任务事实 → canonical Owner → required 当前场景所需完整约束 → 读取当前完整原文
```

不得用历史聊天/摘要/旧缓存替代 canonical Source；**目标项目中的安装副本**（含 managed block）**不作为当前通用治理语义来源**，项目自有规则仍读取。Source Mode 不调用本地 Runtime MCP。

### 4.2 Runtime Mode

```text
agent_skills_route_contract
→ agent_skills_start_task
→ agent_skills_submit_route
→ agent_skills_load_required_context(路由令牌)
→ 事实变化时追加 submit/load
→ agent_skills_checkpoint
```

Runtime evaluator 执行同一 fixed-point；`load_required_context` 只返回 required Context；`checkpoint` 不冒充 Traceability/Completion/Review/Docs/测试/CI。每个 Context 校验 **SHA256**、字节数和完整原文。

Router/Core/Runtime/Bundle/routing identity/Project Payload 必须同源同版本；协议/digest/路由/完整性失败时不得用旧记忆冒充，按第 1.1 节传播 blocker。

## 5. 低歧义组合示例

| 案例 | 命中原因与叠加 | Source Mode 读取 | Runtime Mode 任务信号 |
| --- | --- | --- | --- |
| L1 机械修改 | — | Coding | `执行模式=实现；风险=L1` |
| L2 Feature | 最小充分任务契约 | Coding | `执行模式=实现；阶段=功能开发；风险=L2` |
| L3 public API | — | Coding | `执行模式=方案,实现；风险=L3；范围=公共契约,API` |
| Schema Migration | — | Coding | `执行模式=方案,实现；风险=L3；范围=Schema,Migration` |
| Bug / Failure / Incident | — | Coding | `执行模式=诊断,实现；阶段=缺陷修复` |
| Refactor / Performance | — | Coding | `执行模式=诊断,实现；阶段=重构/性能优化` |
| Frontend | — | Coding | `执行模式=实现；项目形态=前端Web；范围=前端；风险=L2` |
| Testing only | — | Testing | `意图=黑盒测试/功能测试/探索式测试/独立验证；能力=测试` |
| Figma review-only | — | Figma | `执行模式=审查；意图=Figma review-only；授权=允许只读` |
| Figma review-and-fix | — | Figma | `执行模式=实现；意图=Figma review-and-fix；授权=允许修改项目` |
| Figma baseline-ready | — | Figma | `执行模式=方案；意图=Figma baseline-ready；风险=L2/L3` |
| Figma → Code | — | Figma + Coding | `执行模式=实现；意图=设计转代码；范围=前端` |
| Docs not_applicable | — | 当前 Owner | 不提交 Docs 意图 |
| Docs targeted | — | Coding + Docs | `执行模式=实现；意图=Docs targeted` |
| Docs full | — | Coding + Docs | `执行模式=实现；意图=Docs full；风险=L2/L3` |
| 文档 Review | — | Docs | `执行模式=审查；意图=文档审查` |
| Code Review / Audit | — | Coding + Review | `执行模式=审查；意图=代码审查` |
| Dependency / Runtime Upgrade | — | Coding | `执行模式=实现；意图=依赖升级/Runtime 升级` |
| Git / PR / Release | — | Coding | `执行模式=Git,验证；阶段=交付；意图=Git 交付` |
| Runtime / Project Payload | — | Coding | `执行模式=实现；风险=L3；范围=Runtime,MCP` |
| Skill Mutation Audit / Proposal | 只读 | 根 AGENTS + Mutation | `执行模式=只读分析；意图=Skill Mutation Audit；授权=允许只读`；宽泛 `Skill Mutation` 无写入事实→Audit-compatible |
| Skill Mutation Apply | 写入 | Maintenance + Mutation | `执行模式=实现；意图=Skill Mutation Apply；治理=要求完成门禁；风险=L2/L3` |
| Greenfield | — | Coding | `执行模式=方案；项目形态=Greenfield；阶段=仓库初始化；风险=L2` |
| 复杂多 Skill 叠加 | 多 Owner | 命中并集 | 提交真实模式/范围/意图/治理/授权 |

## 6. Bootstrap / Runtime 专项路由

- 触发：安装/升级、AGENTS Bootstrap/managed block、Bundle/Routing/MCP/Project Payload/分发。
- 必须动作：恢复 installation/ownership/schema/宿主事实；读完整 canonical 完整约束。
- 不适用：普通业务。
- 交接：当前场景所需完整约束（`当前场景所需完整约束`）→ Runtime 再读 当前场景所需完整约束（`当前场景所需完整约束`）。
- 返回：smoke → Coding 验证/Review/Git。
- 失败关闭：关键事实**无法读取**/验证→阻塞依赖动作，**不得假装**完成。

## 7. Figma 路由

- 触发：Figma 创建/修改/审查/Prototype/基线/Design-to-Code。
- 必须动作：读 [`.agents/skills/figma/SKILL.md`](../figma/SKILL.md)；review-only 不要求 `READY`，baseline-ready 输出 **READY / READY_WITH_NOTES / NOT_READY**。
- 不适用：无 Figma 事实。
- 交接：设计 → Figma；生产实现 → Coding。
- 返回：Review → Findings；Ready 后按需 Coding/Testing/Review。
- 失败关闭：缺 Figma/required Context→不冒充审查/Ready；其他继续。

## 8. Testing 路由

- 触发：测试意图或独立 Test Gap。
- 必须动作：读 Testing。
- 不适用：隔离 L1/开发期最小 TDD；**不为了“走完所有 Skill”机械叠加 Testing**。
- 交接：Coding/Review → Requirement、Test Target、Gap。
- 返回：生产缺陷 → Coding；回归 → Testing；合并判断 → Review。
- 失败关闭：缺 Testing Context→不冒充测试证据；其他继续。

## 9. Review 路由

- 触发：Code Review/Audit、独立 Review 或项目门禁；Figma/Docs“审查”不自动成为 Code Review。
- 必须动作：读 [`.agents/skills/review/SKILL.md`](../review/SKILL.md)，独立重建要求并审 Findings/Evidence。
- 不适用：无源码/PR/diff Review 或独立门禁。
- 交接：Review Target/base/head/上游事实 → Review；Test Gap → Testing。
- 返回：Finding → Coding；Regression → Testing；再 re-review。
- 失败关闭：缺目标/关键事实→不宣称 Review 完成/可合并。

## 10. Docs 路由

- 触发：文档影响或显式文档任务。
- 必须动作：读 [`.agents/skills/docs/SKILL.md`](../docs/SKILL.md)，判断 not_applicable/targeted/full。
- 不适用：已证明无文档事实变化。
- 交接：实现事实/Docs Impact → Docs。
- 返回：完成回原 Skill；实现缺陷 → Coding。
- 失败关闭：缺事实→不写推测文档。

## 11. 失败、冲突与权限

- 必需 Skill/Router/完整约束 **无法读取**时只阻塞依赖动作，**不得假装**已遵守；
- 冲突遵守更高优先级/更具体规则；不绕过 CI、**Branch Protection**、PR、Release、Migration、安全门禁；
- **没有相应授权**时不获得修改、Git、发布、部署权限；不强推、重写共享历史或破坏性清理。

## 12. Router 维护边界

Router 只拥有发现、Owner-gated 加载和 Handoff；专业细节归各 Owner，不复制回 Router/ENTRY/managed block。