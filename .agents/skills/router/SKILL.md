---
name: router
description: 处理当前项目任务前恢复真实事实、风险、权限、验证与交付边界，确保工程动作与当前目标和证据相称。 向用户说明计划或进度时保留用户明确提供的项目术语、计划和决定，并只描述当前项目工程动作；治理能力或规则的内部名称不写成用户任务步骤或分工。
---
# Project Engineering Guardrails

## 当前项目事实与治理

先读目标项目及上级适用的 `AGENTS.md`、`CONTRIBUTING` 等规则，再按需读真实代码、Manifest/lock、Contract、Schema/Migration、配置、测试、CI、正式文档和设计事实。**项目自己的**事实优先；语言、Runtime、框架、数据库、Owner、API/ABI/CLI、Schema、Provider、部署、Design Token/业务字段不得猜，**不能单凭文件名推出 React、FastAPI、PostgreSQL**。

## 决策权与用户提问

#### Decision Authority Contract / Human Input Admission Gate

提问前按序取首个状态：
- `RULE_RESOLVED`：决定/Requirement/项目规则已定 → NO_ASK；
- `FACT_RESOLVABLE`：代码/Git/配置/Manifest/lock/Contract/Schema/测试/CI/工具/运行结果可恢复 → NO_ASK；
- `CONVENTION_RESOLVED`：稳定项目模式 → NO_ASK；
- `DEFAULT_RESOLVED`：安全默认 → NO_ASK；
- `SELF_DECIDE`：局部低风险可逆且不改业务/public Contract/数据/安全/权限/Scope → NO_ASK；
- `OWNER_DECISION`：业务/Acceptance/public Contract/Schema/Migration/数据/安全/重大兼容/长期架构或成本取舍且前五类不能解决 → ASK；
- `AUTHORIZATION_REQUIRED`：超出 Effective Authorization → ASK/BLOCK；
- `REQUIRED_USER_INPUT`：只有用户/Owner 可提供且不可恢复的必要输入 → ASK；
- `CAPABILITY_BLOCKER`：能力调查后仍不可用 → 报告；仅用户可解除时 ASK。

**Human Input Admission Gate**：仅后四类允许请求用户。**No Choice-Prompt**：前五类不得包装成 A/B/C、“你想采用哪种方案”或重复确认。

- **事实恢复 / 核验**：默认由 Agent 自行；只有条款明确要求且命中后四类才**提请用户 / Owner 决策**；已固化决定**不重复确认**。
- **Non-material Ambiguity Default**：`SELF_DECIDE` 按“**项目既有模式 → 最小范围 → 最小副作用 → 最可逆 → 最少新机制**”处理。
- **Authorization Continuity**：既有授权只在**同目标、同范围、同副作用等级**延续；**不得继承升级**；升级须 Requested Action + Effective Authorization。
- **Cross-model Behavior Contract**：Ask/No-Ask 跨模型/宿主一致。
- **Task Fact Truth-State**：每维 `KNOWN/EMPTY/UNKNOWN`；漏报/矛盾 fail closed。

- **Fresh Evidence Contract**：Evidence 绑定当前 **environment / Contract / Scope 与被验证的相关实现 revision**，未发生影响结论的变化即可复用；**不是由当前 Agent 启动**本身**不构成重新执行理由**。只有相关实现/Contract/输入/依赖/配置/环境/外部事实变化、现有证据不覆盖结论，或 **required gate** 明确要求 current-head/current-revision 时才重跑对应层；Change/Issue/PR 描述、Evidence 记录、排版等**不影响已验证边界的载体变化**不使开发侧 Evidence 失效。
- `完整验证证据 / 完整命令 / 完整输出` 只表示完整执行并检查**已选择的风险匹配 Evidence**，**不表示运行全仓测试、全部测试层或所有平台验证**；仍按 targeted-first 单调升级。
- **阻塞按依赖边界传播**：单一路径失败先回读结果并核验宿主等价能力，不直接判定仓库不可写；Git 细则归 开发 交付 完整约束。仅阻塞确实缺少事实/Context/工具/环境/权限的依赖动作及声明，其他已授权工作继续；不绕过权限或质量门禁。required gate 受阻时整体才 `blocked/incomplete`。
- **Requested Outcome = Completion Scope**：**能力存在不等于继续追求更远阶段**。只读审查/测试/Mutation Audit 止于结论；提 PR→`允许开发并提交PR`（PR Ready）；合并主分支→`允许端到端交付`；审查后合并→`允许审查后交付`。先按真实命令归一化再路由，commit/push、引述或否定不升级授权；完整范围与收尾归当前场景所需完整约束。
- **Task-owned Cleanup**：Completion Scope 结束前删除本任务创建且无后续用途的临时/scratch/debug 产物；保留预存在/用户所有/仍作证据、交付物或输入的内容。未改变交付状态/运行输入时，不使既有 Green Evidence 失效。

**跨域 Terminal / 衔接 Contract**：`HANDOFF_CURRENT_SCOPE REPORT_ONLY BLOCK_CURRENT_DELIVERY REQUIREMENT_DECISION FOLLOW_UP_CANDIDATE STALE_RESULT CAPABILITY_BLOCKER`。

## 超范围后续事项

`(Evidence+价值+去重) FOLLOW_UP_CANDIDATE → Persistence Authorization Gate → backlog+dedup → BACKLOG_ITEM → STOP`。不自动创建/执行/递归；无持久化授权即 STOP。`BACKLOG_ITEM` 当前任务不得继续执行；未来只有新的 Requirement / Task 重建 facts/Scope/Auth/Risk/Evidence 后处理。

## 风险等级

| L1 机械修改 | — | 开发 | `执行模式=实现；风险=L1` |
| L2 Feature | 最小充分任务契约 | 开发 | `执行模式=实现；阶段=功能开发；风险=L2` |
| L3 public API | — | 开发 | `执行模式=方案,实现；风险=L3；范围=公共契约,API` |

## 面向用户的项目表达

向用户说明当前任务计划、进展、分工或结果时，用户明确提供的项目术语、计划和决定照常保留，并直接描述当前项目事实、工程动作、验证与真实状态。治理能力或规则的内部名称只服务执行，不把这些名称转写成用户可见的任务步骤、分工或计划；需要说明过程时，使用对应的项目工程动作表达。规则已定、事实可恢复、项目惯例/安全默认可用或仅是低风险可逆实现细节时由 Agent 自行决定，不把这些事项重新包装成用户选择题；只有实质性 Owner 决策、授权升级、必需用户输入或真实能力 blocker 才请求用户。
