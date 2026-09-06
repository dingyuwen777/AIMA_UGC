---
name: coding
description: 面向不同项目形态、研发阶段和编程语言的可靠软件研发工作流。由 Router 选中后，先恢复仓库当前事实，再按项目形态、研发阶段/任务类型、编程语言/工具链和风险等级 L1-L3 细化研发流程；依据真实 Contract、Schema、数据、模块边界和项目规则执行需求设计、功能开发、Bug 修复、重构、Review、CI、Git 与交付验证。保留可失效项目导航、Git 可见 Change、Requirement Traceability、Completion Audit、Red-Green-Refactor、根因调试、分层验证、多人协作和新鲜证据门禁。Use after Router selection for development.
---

<!-- agent-routing:v1
{"协议":"Agent Skills Skill路由/v1","Skill":"coding","触发":{"任一":[{"包含":{"维度":"执行模式","取值":["Git","发布","运维"]}},{"全部":[{"包含":{"维度":"执行模式","取值":["实现","诊断"]}},{"包含":{"维度":"意图","取值":["测试策略","功能测试","黑盒测试","用户场景验收","探索式测试","回归测试","独立验证"]}}]},{"全部":[{"任一":[{"包含":{"维度":"执行模式","取值":["只读分析","诊断","方案","实现","验证"]}},{"包含":{"维度":"阶段","取值":["仓库初始化","事实恢复","需求设计","功能开发","缺陷修复","重构","性能优化","故障处置","交付"]}}]},{"非":{"包含":{"维度":"意图","取值":["测试策略","功能测试","黑盒测试","用户场景验收","探索式测试","回归测试","测试充分性验证","独立验证","Figma review-only","Figma review-and-fix","Figma baseline-ready","文档审查","文档编写","文档更新","文档同步"]}}}]},{"包含":{"维度":"意图","取值":["代码分析","技术方案","代码实现","代码审查","Review-only","Review-and-test","Review-and-fix","独立复核","设计转代码","Git 交付","依赖升级","Runtime 升级","Skill Mutation"]}},{"包含":{"维度":"项目形态","取值":["Greenfield","CLI","前端Web","后端服务","全栈应用","移动应用","桌面应用"]}},{"包含":{"维度":"风险","取值":["L1","L2","L3"]}},{"包含":{"维度":"授权","取值":["允许只读","允许修改项目","允许测试","允许 Git","允许发布"]}}]}}
-->

## 用户可见表达边界

用户关于目标项目的正常事实、解释、建议、风险、验证、状态和交付照常回答；描述 Agent 自身的进度、分工或执行过程时，对用户只描述项目实际动作、风险、证据和交付状态。不得把内部能力名称或标签转写成用户可见任务分工，也不得播报内部发现、选择、加载、路由、交接或约束取得过程。限制只针对内部身份转写，不限制正常工程解释；内部能力身份继续用于路由、约束加载和专业执行，不得为了用户可见隐藏而删除内部执行上下文。


# Coding

把自然语言研发请求转化为一个可追溯、可验证的交付闭环：

```text
恢复当前仓库事实 / Greenfield 约束
→ 四维任务路由
→ 明确需求与风险
→ 选择最少但充分的流程和证据
→ 最小兼容实现
→ 新鲜验证
→ 按实际门禁进入 Completion Audit / 独立 Review
→ 只交付证据真正支持的结论
```

这里的核心不是让每次开发都走同样长的流水线，而是让**风险强度**与**流程重量**解耦：L1/L2/L3 决定需要控制和证明什么；Change、Docs、独立 Review、Completion Gate、Git/PR/Release 等能力只在当前事实真正需要时加载。能力存在不等于每个任务都要使用，发现新的风险、交接或交付事实后再单调升级。

### 简单代码 Fast Path

如果用户只是要求一段**一次性简单代码 / snippet / scratch code / 小脚本示例**，并且当前已确认：

- 不对目标仓库做持久修改；
- 不改变 public API/ABI/CLI、Schema、数据格式、权限、安全、依赖、构建、部署或发布边界；
- 不对真实生产系统、外部 Provider、数据库、文件或其他资源执行有持久副作用的操作；
- 没有正式 Docs、Review、PR、Release 或可审计交付要求；

则不为了形式启动完整仓库治理。最小路径是：

```text
确认最少上下文与输入/输出
→ 直接实现最小代码
→ 使用最便宜且能直接证明目标的解析 / 编译 / 运行 / targeted test
→ 如实报告验证证据和限制
```

这类任务不为形式创建 Change、扫描仓库文档、进入独立 Review 或启动 Git 流程。**Fast Path 不是降风险漏洞**：一旦发现需要持久改仓库，先退出 Scratch Fast Path 并按当前项目事实重新判断 L1/L2/L3；如果仍是行为不变机械修改或边界明确、影响隔离的极小修复，则进入 当前场景所需完整约束 的 `Repository L1 Fast Path`，不因“持久修改仓库”本身预付完整 Feature/Bug/Docs/Review 流程。只有发现公共/数据/安全/依赖/运行时边界、真实外部副作用或正式交付要求时，才按对应事实单调升级。

本 Skill 不是 Python、Web、Backend 或 PostgreSQL 专用流程。它的固定部分是“怎样可靠研发”；具体语言、框架、数据库、目录、包管理器、CI 和部署方式必须来自当前项目事实或 Greenfield 阶段经确认的新建工程决策。

详细规则分布在 `当前场景所需完整约束/`。**当本文件的触发条件命中时，对应 完整约束 是本 Skill 的规范组成部分，必须在执行相关动作前读取；不能只读主文件后凭印象补流程。**

**内容守恒优先于篇幅精简。** 规则重组只能改变组织方式，不能降低触发、例外、失败处理、验证责任、安全或兼容要求；只有逐项证明完全等价时才消除重复，无法证明时保留原细节并用回归与人工语义对照验证可达性。

## 0. 强制执行模型：先路由，再工作

每个独立任务在制定实现计划前先按 当前场景所需完整约束 建立四维路由：

```text
项目形态
× 研发阶段 / 任务类型
× 编程语言 / 工具链
× 风险等级 L1 / L2 / L3
→ 本次必须读取的 当前场景所需完整约束
→ 本次 Validation Matrix
→ 本次 Change / Review / Git 门禁
```

至少内部核验执行模式、项目形态/阶段、真实工具链版本与入口、L1-L3 风险、影响边界、required/not_applicable 验证维度。**用户授权了哪些 Git / PR / Release 动作？** 能从请求、仓库、锁文件、代码、CI、工具和正式事实源取得的答案必须自行恢复；只有命中**提请用户 / Owner 决策**时才提问，且已固化决定**不重复确认**。

不要先根据文件扩展名、经验或“最佳实践”假设技术栈。例如：

```text
package.json ≠ npm ≠ React ≠ Browser test
pyproject.toml ≠ uv ≠ FastAPI ≠ PostgreSQL
Cargo.toml ≠ Web Service
CMakeLists.txt ≠ Linux-only
```

继续读取项目规则、锁文件、版本文件、workspace、CI、真实代码和调用链后再判断。Greenfield 没有这些事实时，不把 Skill 示例反向当成默认技术选型；先按目标、硬约束和用户已确认决定建立最小工程基线。

## 1. 先遵守这些不变量

这些规则跨项目、跨语言、跨研发阶段成立。

1. **上位规则优先。** 先遵守系统、开发者、用户以及目标目录中适用的 `AGENTS.md`、`CONTRIBUTING` 或同等仓库规则。本 Skill 不能降低更高优先级约束；项目本地规则是通用 Skill 的 Overlay。
2. **仓库事实优先。** 把当前仓库文件、运行结果和用户明确确认视为事实。缓存只作导航，不作事实副本；明确区分已确认事实、推断、建议和暂时无法验证，不默认用户或 Agent 判断正确。
3. **权限边界明确。** 只在任务授权范围内写文件或执行外部动作。只读分析、Review、审计或答疑不自动授权创建缓存、Change、分支、提交、PR、合并、部署或生产操作。
4. **保护用户工作。** 保留用户未提交修改。禁止覆盖式检出、强制推送、破坏性清理、未授权历史重写以及把无关用户改动混入本任务。
5. **不静默扩大变化。** 不擅自升级依赖/Runtime、切换包管理器或框架、改公共接口/ABI/格式、改变数据语义、扩大范围或进行无关重构。
6. **完成结论必须有本轮新鲜证据。** 新鲜性按 Router 的 Fresh Evidence Contract 核验；没有可追溯、仍覆盖当前结论的实际执行证据，不得宣称完成、修复、通过、可合并、可发布或可部署。
7. **从目标和根因推导机制。** 从可观察目标、硬约束、当前事实和根因选择最小充分方案；“最佳实践”只是候选证据，不能覆盖仓库事实或成为引入复杂度的理由。
8. **不发明项目制度。** 只执行仓库真实存在或本次需求明确建立的边界、Contract、Schema、Owner、Migration、测试和发布机制；经有界调查未发现时标记不适用并跳过，不为了填模板补造架构。Coding 自带 Change 只是在项目没有可复用治理载体时的 fallback，不能静默与 OpenSpec、RFC、ADR、Issue 或其他既有正式治理体系平行造一套制度。
9. **独立能力建立独立验证闭环。** 对具有明确输入输出、独立业务价值、独立失败边界，或无需启动完整系统即可验证的能力，优先复用生产入口建立最小验证闭环，使用与风险匹配的自动化测试、Fixture/Fake/隔离依赖、明确运行方式和成功判据。不要机械要求“一模块一个测试文件”或“一功能一个测试文档”。
10. **L2/L3 必须向上追溯，但不等于都要持久 Change。** 所有 L2/L3 都必须能从用户已确认决定、当前 Requirement Source 或正式项目事实说明目标和验收来源。普通轻量 L2 使用最小充分任务契约并在强完成结论前重新核对当前要求；只有持久 gated L2、L3 或项目明确要求 Completion Gate 的单元才需要完整 Requirement Traceability、持久施工契约与 Completion Audit。CI 全绿不能替代需求完整性核对，也不能依赖用户事后发现漏项。
11. **验证按风险而不是固定技术栈分层。** L2/L3 按 当前场景所需完整约束 建立 Validation Matrix；低影响修改 targeted-first，真实专项边界再叠加 当前场景所需完整约束。任何层都不能声称证明自己没有实际运行的下游边界。
12. **中文注释与函数级说明是通用规则。** 代码注释统一使用中文；专有名词、标识符、协议、库、标准名以及必须保持原样的外部文本可以保留原语言。新增或修改的 public/exported 函数必须有与复杂度匹配的函数级中文注释或文档注释；**内部/private/helper 函数也必须写函数级中文注释或文档注释**，不能因为不是 public 就省略。简单函数的说明可以非常简短，但不能用“自解释”作为完全不写函数级说明的理由。复杂规则、关键不变量、状态转换、算法取舍、兼容原因和重要副作用还要重点解释 `why / invariant / risk / compatibility`，不要逐行翻译语法。
13. **重要功能可观测性需要匹配现有体系。** 如果仓库已有日志/事件基础设施，且功能涉及关键生命周期、异步任务、外部 I/O、重试/部分失败、状态转换或后期排障价值，应补最小充分结构化观测。复用现有 logger/event/脱敏/关联 ID；禁止打印 Secret/Token/密码/敏感 Raw/PII，禁止 INFO 高频刷屏，日志也不能替代数据库/文件中的正式业务事实或 Health/Audit 机制。
14. **Git 提交信息统一中文。** 所有 Git 提交信息使用中文，包括普通提交、修复提交和合并提交的说明文本；命令、路径、标识符、版本号等必要技术内容可以保留原文。项目可以进一步规定提交格式或前缀，但不能把提交信息语言改为非中文。
15. **所有时间相关默认采用北京时间。** Coding Skill、Agent 以及由其新增或默认解释的时间戳、日期、日志、缓存、Change 元数据、报告时间、脚本默认时间和用户可见时间统一使用北京时间 `Asia/Shanghai`（UTC+8），不得依赖宿主本地时区。外部协议、原始数据或既有机器 Contract 明确规定其他时区时保留原始事实语义，但在 Agent 输出、人类可读日志和展示边界明确转换为北京时间，不得把 UTC 值直接当作北京时间。
16. **日志前缀统一且可定位。** 除非更高优先级的外部日志 wire-format Contract 强制其他序列化形式，所有人类可读日志记录统一使用 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message`；时间必须是北京时间，毫秒固定三位，`source.ext` 与 `L<line>` 来自真实调用点，`LEVEL` 使用大写。结构化日志若因平台 Contract 必须采用 JSON 等形式，仍必须提供等价的北京时间、source、line、level 字段。
17. **系统级分析先于局部实现，但不扩大修改范围。** 恢复任务相关能力边界后再决定局部修复、复用或抽象；相邻技术债不自动入 Scope。详见 当前场景所需完整约束。
18. **受影响代码域必须整洁收口，但只清本次直接责任。** 清理本次直接新增、修改或因此失效的实现；旧技术债默认只记录 Finding。详见 当前场景所需完整约束。
19. **Skill Mutation 先做 Mutation 目标解析。** 只改 canonical Owner；本地安装副本不得成为替代 Skill；Audit/Proposal 与 Apply 分开；局部 blocker 只阻塞依赖动作，required canonical Source/门禁不可得时按依赖边界**失败关闭**。详见 当前场景所需完整约束。

### 1.1 自主执行、澄清和阻塞边界

**事实恢复 / 核验默认由 Agent 自行完成**；只有有界调查后仍无法确定且答案会实质改变业务/public Contract/数据/安全/不可逆动作/重大技术路线时，才**提请用户 / Owner 决策**；已固化决定**不重复确认**。除非条款明确要求审批，否则“确认/明确/确定/恢复/核对”均表示自行核验。

**阻塞按依赖边界传播**：只停止依赖 blocker 的动作和完成声明；其他已授权工作继续。最终 `complete / mergeable / releasable / deployable` 仍必须满足各自全部 required gate。

## 2. 四维任务路由

### 2.1 项目形态

从真实仓库选择实际存在且与任务有关的形态，例如 Library/SDK、CLI、Service/API、Frontend/Web、Full-stack、Mobile/Desktop、Data/ETL/ML、Embedded、Infra/IaC、Monorepo/Polyglot 或 Documentation/Configuration/Migration-only。具体边界见 当前场景所需完整约束。

### 2.2 研发阶段 / 任务类型

支持 **Greenfield / Repository Bootstrap / Prototype / Feasibility**、**Repository Onboarding / Fact Recovery**、Requirement/Design、Feature、Bug/Incident、Refactor/Performance、Code Review、PR/Release/Delivery、Dependency/Runtime Migration 与 Security/Permission。Greenfield 先核验目标、非目标、硬约束、运行环境和已决定边界，再建立最小可验证工程基线；Prototype 的临时性不能放宽安全/数据边界。

### 2.3 编程语言 / 工具链

读取 当前场景所需完整约束，从真实版本、Manifest/workspace、lock/dependency policy、build/test/lint、package/runtime、CI/release 恢复事实。Profile 只导航，不授权升级或更换工具链。

### 2.4 风险等级

使用最低但充分等级；发现隐藏复杂度时升级，不静默降级：L1 是行为不变机械修改或隔离小修复；L2 是行为变化、重要 Bug、多文件/多人或需要追踪的工作；L3 是 public API/ABI、Schema/Migration、跨模块 Contract、架构、安全、部署恢复、重大依赖或破坏性兼容变化。行数少不等于 L1。

## 3. 按触发条件读取资源

不要把所有 完整约束 一次性全读，也不能在命中触发条件时跳过对应 完整约束。

| 触发条件 | 必须读取 |
| --- | --- |
| 首次进入仓库、Greenfield 工程基线尚未建立、缓存缺失或可能过期 | 当前场景所需完整约束 |
| 需要识别项目形态、研发阶段或组合流程 | 当前场景所需完整约束 |
| 需要确认语言、Runtime、Manifest、锁文件、构建或包管理；新增/修改网络下载源、镜像或依赖安装链 | 当前场景所需完整约束 |
| Repository L1 持久实现、已确认根因的隔离小修复或 L1 targeted validation | 当前场景所需完整约束 |
| L3、已有 Active Change、明确要求变更记录/完成门禁或其他已确认持久施工契约 | 当前场景所需完整约束 |
| 新/当前 Change 使用 Completion Gate、正式仓库初始化、L3 或交付单元 | 当前场景所需完整约束 |
| L2/L3 的 Requirement/Feature/Bug/Refactor，或任意系统性诊断、Incident、Performance | 当前场景所需完整约束 |
| Frontend / Web UI / Design-to-Code / Figma-to-code / 设计稿转代码；新增页面、跨页面 UI 或需要选择前端技术方案 | 当前场景所需完整约束 |
| L2/L3 需要规划或审计 Validation Matrix；新增/修改永久 CI/Workflow 或测试/发布门禁 | 当前场景所需完整约束；L1 targeted validation 由 当前场景所需完整约束 负责 |
| Web/API/PostgreSQL/Provider 等专项边界真实存在 | 当前场景所需完整约束 |
| 跨模块、跨消费者、Contract/Schema/Migration/Owner/数据边界 | 当前场景所需完整约束 |
| 多人、多 Agent、多个分支或 Active Change 并行 | 当前场景所需完整约束 |
| 显式 Review/Audit、持久 Change/PR Ready、Git/Release 交付或项目明确要求独立复核 | 当前场景所需完整约束 |
| 首次安装/升级 Agent_Skills、创建/补充目标项目 AGENTS、首次 Project Governance Bootstrap、治理事实漂移校准或修复 managed block | 当前场景所需完整约束 |
| Runtime Bundle/Routing Manifest/Task Route/MCP/Project Payload/安装升级或 Release identity | 当前场景所需完整约束 |
| Git/PR/Release/Delivery、依赖变化、安全边界、最终交付报告或宿主能力降级 | 当前场景所需完整约束 |
| Skill/完整约束/模板/项目 Overlay 的精简、重组、拆分、合并、改名、迁移或通用化 | 当前场景所需完整约束 |

不要要求用户重复提供能够从仓库、缓存或工具确认的信息。只读取当前任务真正需要的事实和 完整约束，不用“全仓全部读一遍”替代理解调用链。

## 4. 统一工作流

### 4.1 建立权限和宿主能力边界

先判断请求属于：

```text
只读分析 / 诊断 / 方案 / 实现 / Review / Git / Release / 运维
```

核验当前宿主是否具有：持久文件系统、终端、目标语言工具链、Git、测试环境、数据库/容器/device、CI、外部服务和多 Agent 能力。

- 没有持久文件系统：可以恢复项目事实，但不能承诺跨会话缓存或 Git 协作记录；
- 脚本/测试或 Git 首选路径失败：先按 当前场景所需完整约束 发现并核验等价能力；必要执行路径确实不可用时再按人工流程继续，明确未验证项，不伪造结果；
- 用户未授权写项目：只在会话内建立临时导航，不创建项目文件/Change/分支；
- 外部系统/生产环境没有授权：只读调查或使用已批准 sandbox/fake，不执行真实写入。

### 4.2 定位仓库并先读规则

定位真实仓库根目录。先读取从 root 到目标路径适用的 `AGENTS.md`、项目说明和规则，再做其他项目判断。

实现/Git 任务还要检查当前 branch/worktree/HEAD、未提交或未跟踪修改以及 nested repo/worktree/submodule；不是 Git repo 就记录事实。绝不覆盖、回滚、格式化或混入无关用户修改。

Greenfield 也先核验仓库根、Git 状态、运行/交付环境和已确认约束。目标项目**首次接入** Agent_Skills、治理状态待校准或长期**治理事实**疑似漂移时，按 当前场景所需完整约束 在**任何实质性生产代码修改之前**完成 `Project Governance Bootstrap`；写授权下校准 Overlay 并重读最终 `AGENTS.md` 后**继续原始研发任务**，只读授权下只做会话内调查并**继续原始只读任务**。普通后续任务没有长期治理变化时不重复全量校准。

### 4.3 恢复项目和工具链事实

按 当前场景所需完整约束 与 当前场景所需完整约束 确认任务相关的 README/Requirements/Architecture、入口目录、Manifest/Runtime/lock、Build/Test/CI、Config、Contract/Schema/Migration、调用链/数据流、错误处理、生成物、模块 Owner/public boundary 和相关历史变更。只读取任务相关内容。

Greenfield 中尚不存在的条目不是失败；区分本次必须建立、可延期和不适用。所有由 Agent 新建、填充或默认解释的时间字段按 `Asia/Shanghai` 处理；外部 UTC/其他时区先保留原始事实，再按需要转换展示。

### 4.4 复用或建立可失效项目导航

项目缓存路径固定为：

```text
.agents/project-context.json
```

它是**本地可失效导航缓存，不提交 Git**。目标仓库安装/使用 Coding 时应将它加入本地或仓库 `.gitignore`；若项目规则禁止修改，至少保证本次不提交。缓存不能替代团队共享需求、架构或 Contract。

对已授权写入的实现任务，在独立任务/会话首次规划前运行；分支同步、rebase、历史改写或事实源变化后重新运行。终端、Python 和写权限可用时：

```text
python <skill>/scripts/coding.py discover --root <repo>
```

`cache_hit` 只说明候选事实源无可见失效信号，不代替真实需求、实现、调用链或 `git diff`；脚本失败保留原错误并按 当前场景所需完整约束 人工继续。缓存只保存导航信息，`generated_at` 使用带 `+08:00` 的北京时间。

### 4.5 检查 Active Change 和并行冲突

先发现项目已有正式变更治理：OpenSpec、RFC/ADR、Issue/PR 约定、项目 `changes/` 等都可能是 Overlay。**不要为了使用 Coding 而静默创建平行 Change 系统。** Coding 自带工具只管理 `coding-change/v1`；没有可复用治理时默认 carrier 为 `.agents/changes/active/` 与 `.agents/changes/archive/YYYY-MM/`，已有兼容顶层 carrier 则沿用。

终端可用时：

```text
python <skill>/scripts/coding.py status --root <repo> --json
```

只比较真实存在或 Change 明确建立的 affected paths/modules、public Contract/API/ABI/format、data/schema/Migration、config/runtime、shared generated files/tests/fixtures 和 dependencies/build/release resources。发现交集才决定排序、拆分或共同 Owner；没有交集不制造冲突。多人/多 Agent 细节遵循 当前场景所需完整约束。

### 4.6 分类 L1/L2/L3 并固化任务契约

编码前建立最小任务契约：当前事实、目标 / 非目标、可观察成功标准、不变项、受影响能力 / Owner、最小方案、直接 Evidence 和真实未知项。输入输出、复用点、预计文件、公共接口、数据 / Schema / Migration、依赖、文档、部署 / 回滚与 Git 授权只在本次触及对应边界时展开；不适用项不逐项提问。详细字段按 当前场景所需完整约束，项目 Overlay 的额外要求仍保留。

L1 可在工作说明内维护。L2 必须有**最小充分任务契约**，但可由本轮用户要求、PR body、Issue/工单、Spec/OpenSpec/RFC 或项目既有载体承载；只有跨 Owner/PR/会话、复杂依赖/阶段、正式审计、项目规则或 Completion Gate 等**持久治理价值**出现时才升级为独立持久施工契约。L3 必须有稳定持久契约并补方案比较、公共兼容、Migration/部署/回滚和安全/运维风险。项目 Overlay 可以更严格。

需要持久施工契约时优先复用项目已有治理；它不能承载 required Requirement Traceability、Validation Matrix、Completion Audit 等语义时，不静默降级，按项目规则补最小承载或**提请用户 / Owner 决策**。只有项目没有可复用机制时才用 Coding `coding-change/v1`：

```text
python <skill>/scripts/coding.py new-change --root <repo> \
  --slug short-name --title <title> --owner <owner> \
  --branch <branch> --level L2 --area <area> --path <path>
```

脚本不可用时从 [CHANGE.template.md](assets/CHANGE.template.md) 创建到当前 carrier；进入 Ready 前不能保留占位。新模板默认 `completion_gate: required`，当前 Change 不能引用自身作为 Requirement Source。状态只允许 `satisfied / explicitly_deferred / not_applicable / not_satisfied`。

### 4.7 处理真正需要用户/Owner决策的事项

只有有界调查后仍无法确认、且会实质改变业务语义/验收、public API/ABI/CLI/格式/Contract、Schema/Migration/数据、权限/隐私/安全、外部 Provider 费用、SLO/RPO/RTO、破坏性兼容、不可逆操作或重大技术路线时才**提请用户 / Owner 决策**。给推荐、依据、必要备选与影响；有依赖的决策优先解决最上游问题，彼此独立且都必须在实施前决定的重大事项一次形成有界 Decision Package，不人为拆成多轮。已固化决定**不重复确认**；普通可逆细节和可核验事实不形成审批点；确认的决定同步正式事实源及适用 Change。

### 4.8 制定可验证计划

每一步写清修改范围、可观察结果、依赖和实际验证方式；实现前确定复用点、函数级中文注释、必要可观测性、最小失败测试/TDD 例外、独立风险验证层和可真正并行的步骤。只并行互不依赖且不修改同一文件、接口、Schema、锁文件或共享状态的任务。

### 4.9 先建立 Validation Matrix

L2/L3 使用 当前场景所需完整约束 的通用维度：行为/Unit/Component、接口/Contract、集成/Persistence/Runtime Dependency、用户/Workflow Acceptance、跨组件 Golden Path、外部依赖 Probe、Build/Package/Runtime、Docs/Governance/Other。每层只写 `required` 或 `not_applicable`。

Web/API/PostgreSQL/Provider 等边界真实存在时再读 当前场景所需完整约束，映射 Browser Mock、Backend/API/PostgreSQL Integration、Contract/Generated Client、Real Full-stack Golden Path、Real Provider Probe。L1 不为形式建完整 Matrix，按 当前场景所需完整约束 选择最便宜且直接的证据；若必须更强层才能证明目标，重新评估风险。

### 4.10 按研发阶段实施

#### Repository L1 Fast Path

满足隔离 L1 前提时读取 当前场景所需完整约束，按“最少相关事实 → 最小修改/回归 → targeted validation → Docs Impact → 按真实 Review/Git 门禁结束或升级”。根因已确认的 L1 Bug 保留回归证据；根因未知或出现公共/数据/安全/依赖/运行时边界时退出轻量路径。

#### L2/L3 Feature / 行为变化 / Bug / Refactor

读取 当前场景所需完整约束。下面默认 Red 流程适用于新增可观察行为和 Bug 修复；行为不变的重构、低影响可逆且行为 / Contract 不变的澄清或复述，先复用已有直接回归和检查，证据充分时不新增永久测试。只有真实新增行为、不变量或具体回归缺口未获保护时才补最小测试。

```text
Red
→ Verify Red：实际确认因正确目标行为失败
→ Green：最少代码通过
→ Verify Green：目标测试 + 相关测试
→ Refactor：只在行为绿色后整理
→ Verify Again
```

Bug 修复必须有回归证据。测试验证真实行为，不只验证 Mock 被调用或实现细节。

#### 文档 / 纯配置 / 生成物 / 无合理自动 Red 的操作

允许 TDD 例外，但必须明确原因和替代验证，例如 parser/schema、link/完整约束、generated diff、build、dry-run/plan、package/open、实际运行或 repository consistency；不要伪造形式化 Red。

#### 需要诊断的失败 / Bug / 性能 / 异常

根因未知、Incident、性能或复杂异常先按 当前场景所需完整约束 与命中专项执行完整错误/调用栈、稳定复现、近期变化、数据流/组件边界、正常参照、可证伪假设、单变量实验、失败回归和单一修复。**连续三次修复假设失败**时停止继续提交同类补丁并回到事实恢复/根因诊断；只要还能取得必要 Evidence 就继续，只有下一步必要 Evidence 无法取得且无其他合法路径时才报告对应 blocked。

#### 最小、精准、兼容

只写当前需求最少代码；标准库和现有依赖优先；不增加未要求功能、CLI、配置、兼容层、抽象或未来占位；不顺手重构/改名/格式化无关文件；每处 diff 可追溯到需求或验证；删除只因本次修改而失效内容；默认保持 public API/ABI/import/CLI/config/default/env/data/file/persistence/startup/error compatibility。Breaking change 先设计版本、Migration、兼容期、部署、回滚和验证。

#### 独立调试和 Probe

调试、测试、示例和 Probe 优先调用生产实现，不复制第二套生产规则。真实付费 API、外部 Provider、真机、cloud sandbox 默认受控：明确请求/费用/数据范围，不打印 Secret，不默认写生产系统，不偷塞普通 CI。

#### 注释与可观测性

代码注释统一中文；新增或修改的 public/exported 与内部/private/helper 函数都必须有函数级中文注释或文档注释。复杂逻辑重点解释 `why / invariant / risk / compatibility`。已有 logger/event 体系且观测点有独立排障价值时覆盖低频关键生命周期、external I/O、retry/partial failure/terminal state；Secret/敏感 Raw/PII 不记录。人类可读日志统一采用 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message` 和北京时间，除非上位 wire-format Contract 强制其他格式。

### 4.11 跨模块、Contract、Schema 与数据边界

任务跨模块/消费者、接口/事件/数据或仓库已有明确 Owner/Contract/Schema/Migration 时读取 当前场景所需完整约束，沿真实生产者/消费者、public Contract、数据/写 Owner、Migration/兼容、契约/集成测试、生成物和部署/回滚检查。未发现时不为“分层”发明第二套 Interface/Client/Schema/数据源。

### 4.12 同步当前事实和文档

代码变化后检查 README/Architecture/ADR/Spec、API/Contract/Schema/Migration、generated artifact、config/env、build/startup/deploy、模块责任/调用链、logging/security/operations、调试/测试说明、用户行为和项目实际维护的 roadmap/release state。文档与实现冲突时先依据已确认决定、项目规则和机器事实判断 Owner；实现偏离则修实现，已批准方案改变系统事实则同步文档/Contract/Schema，证据不足则继续调查或提请用户 / Owner 决策。

正式文档描述系统现在是什么，不写无意义变更流水账；未实现功能不写成已支持。项目本地文档编号/命名/历史规则优先。文档与代码/Contract 尚未同步时不得标记 Ready、完成、可合并或可发布。

#### Docs Skill 按需协作（仓库存在时）

如果 Router 已命中 [`.agents/skills/docs/SKILL.md`](../docs/SKILL.md)，或 Coding 确认产生文档影响，先给出 Docs Impact：`not_applicable` 要有具体依据；有影响或任务本身是技术文档审查/编写时读取 Docs，由它选择 `targeted`（默认）或 `full`。Docs 返回 `code_issue_detected` 时回 Coding 修实现并取得新鲜验证，再做 targeted re-review。Docs 尚未闭环前不得标记 Ready/完成/可合并/可发布；仓库没有 Docs Skill 时仍执行本节文档影响判断。

### 4.13 Completion Audit、两阶段 Review 与新鲜验证

对 `completion_gate: required` 的 Coding Change 或项目等价 gated L2/L3 单元，Ready 前执行完整 Completion Audit：重新读取上游正式事实源，独立重建完成定义，比较“上游要求 → Change”和“Change → 实现/测试/文档”，执行适用反向能力审计，复核 Validation Matrix，清零 `not_satisfied`。

普通轻量 L2 不创建形式化 Audit，但强完成结论前至少重新读取当前 Requirement Source/任务事实，核对目标、范围/非目标、不变项、required 新鲜验证和未验证/延期/未知项。

使用 `coding-change/v1` 时可运行：

```text
python <skill>/scripts/ready_check.py --root <repo> --require-active-ready
```

它只验证机器可判断的结构、状态、Source、占位符和 Audit checkbox，不能替代自然语言 Requirement Review。

**只有当前实际存在显式 Review/Audit、持久 gated L2/L3 的独立审查门禁、PR/Change Ready、Git/Release 交付或项目规则明确要求独立复核时**，才按 当前场景所需完整约束 进入完整两阶段 Review：上游 Requirement Completeness → Change/Spec 符合性 → 实现/测试证据 → Code Quality/安全/兼容/可维护性/无关改动。单纯 targeted validation 不自动触发完整 Review；严重/重要问题未解决不能交付。

每个完成结论先按 Router 的 Fresh Evidence Contract 核验来源、相关 revision、环境、Contract、范围与成功标准。已执行且仍有效的证据可复用，本轮核验不等于由当前 Agent 重跑。仅在证据失效、覆盖不足或 required current-head gate 要求时运行对应完整命令/检查，读取输出、退出码与失败数量；阶段切换、报告或证据载体更新本身不触发重复。无法定位底层结果的历史日志、作者/子 Agent 声明及“看起来正确”不能冒充证据；对照 Traceability、Validation Matrix 和 diff，只陈述实际支持的状态。

### 4.14 关闭或保留 Change

只有实际使用持久 Change/项目等价施工契约时才做状态和归档：未合并/发布时只有 Traceability、Validation Matrix、Completion Audit、验证和文档满足才进入 `ready_for_review`；全部成功且集成状态确认后才标记 `done` 并归档；active 需求变化先更新上游事实与 Traceability；归档后需求再变新建 Change；archive 不是成功证据。普通 L1/轻量 L2 不为关闭流程补建 Change。

## 5. 多 Agent / 多人协作

只有互不依赖且不修改同一文件、接口、Schema、锁文件或共享状态的工作才并行。派发时给最少充分上下文：目标、范围、事实源、禁止项、验收和输出格式。主 Agent 必须复核子任务实际 diff、HEAD/Change 冲突、测试是否真实运行、证据范围和无关改动；不要直接相信“子 Agent 已完成”。详细规则见 当前场景所需完整约束。

## 6. Git、依赖、安全、交付与宿主能力边界

`Git/PR/Release/Delivery`、依赖变化、安全边界、最终交付报告或宿主能力降级命中时，必须读取 当前场景所需完整约束。原主文件中 Git、依赖、安全、最终报告和能力边界的详细规则已完整迁入该 完整约束；不能因为本节变短而把它们视为可选建议。

## 7. 规则内容守恒与 Skill 维护

当任务会精简、重组、拆分、合并、改名、迁移或通用化 [`SKILL.md`](SKILL.md)、完整约束、模板或项目 Overlay 时，必须在修改之前读取 当前场景所需完整约束。内容守恒仍是硬门禁：只有逐项证明完全等价时才允许消除重复，无法证明时保留原细节。

## 8. 不可延迟 Core 核对清单

本节仅保留进入 当前场景所需完整约束 前必须直接可见的检查名；详细方法由前文和 当前场景所需完整约束 承担。

### 8.1 事实与需求

- 项目规则。
- 仓库根。
- 当前 HEAD。
- 当前 branch。
- 用户未提交修改。
- Requirement Source。
- 目标 / 非目标。
- 成功标准。
- 不变项。
- 未知项。
- 事实 / 推断。
- 不猜历史实现。
- 不猜框架。
- 不猜项目形态。
- 不猜数据库。
- Greenfield 不伪造现状。
- 缓存仅导航。
- 代码 / Contract 优先。
- 工具结果优先。
- 必要一手资料。

### 8.2 范围与风险

- affected paths。
- 模块 Owner。
- public API/ABI。
- CLI flags。
- 配置字段。
- serialization/file format。
- Schema/Migration。
- 认证授权。
- Secret/隐私。
- 依赖 / Runtime。
- Build/CI。
- deploy/release。
- 外部 Provider。
- 不可逆数据。
- 行数少不等于 L1。
- 隐藏复杂度升级。
- 不静默降级。
- 不吸收相邻技术债。
- 能力不等于触发。
- blocker 只沿依赖传播。

### 8.3 实现

- 复用正确实现。
- 单一事实源。
- 单一 Contract。
- 单一 Schema。
- 不为抽象而抽象。
- 不顺手升级依赖。
- 不顺手换框架。
- 不顺手换包管理器。
- 不格式化无关文件。
- 不覆盖用户修改。
- diff 可追溯。
- public/exported 中文说明。
- internal/private/helper 中文说明。
- why/invariant/risk。
- 复用日志体系。
- 不记录 Secret/PII。
- 关键副作用可观测。
- Breaking change：Migration。
- Breaking change：rollback。
- 修根因。

### 8.4 验证

- 新鲜证据。
- 复用现有测试。
- targeted-first。
- Red 因目标失败。
- Green 后回归。
- Refactor 后复验。
- Unit ≠ Contract。
- Mock ≠ persistence。
- Browser Mock ≠ Backend。
- Golden Path ≠ 全状态。
- Provider Probe ≠ 稳定回归。
- 源码测试 ≠ package。
- 只声明实跑边界。
- required：Scope。
- not_applicable：依据。
- 失败先分类。
- 测试错先证明。
- 不删测试造 Green。
- 不降断言造 Green。
- 不抬预算造 Green。
- 新风险才扩 Evidence。
- targeted-first 不替代 CI gate。

### 8.5 文档、Review 与交付

- Docs Impact。
- 文档写当前事实。
- 未实现不写已支持。
- Contract 同步消费者。
- 配置同步示例。
- Schema 同步 Migration。
- Build/启动同步运维。
- Docs 未闭环不 Ready。
- Code Review 需真实意图。
- Figma/Docs 审查不叠加 Review。
- Findings 分严重度。
- 修复后复验。
- required Review 不作者自证。
- PR Ready 重读 Requirement Source。
- Completion Gate 执行 Audit。
- CI Green ≠ 需求完整。
- Git 需授权。
- 不绕过 Branch Protection。
- merge 前核 head。
- release 核 artifact。
- main 后新鲜验证。
- 报告未验证风险。

## 10. Review Skill 集成

#### Review Skill 按实际门禁协作（仓库存在时）

如果仓库存在 [`.agents/skills/review/SKILL.md`](../review/SKILL.md)，Coding 在**真实审查条件命中时**把 Review 作为独立审查层；Review 能力完整保留，但不是所有实现任务的固定终点：

- **显式 Code Review / Audit**：Coding 先完成仓库事实恢复、四维任务路由、风险/工具链/权限确认，并读取当前任务应触发的 Coding 当前场景所需完整约束；随后必须读取 [`.agents/skills/review/SKILL.md`](../review/SKILL.md)，立即切入 Review，由 Review 负责独立需求重建、Findings 和测试充分性审查；
- **L3、持久 gated L2、PR/Change Ready、Git/Release 交付或项目规则明确要求独立 Review**：完成实现、目标验证、Docs Impact 和适用 Completion Audit 后，必须读取 Review 并执行与风险匹配的 Quick / Standard / Deep Review；作者自检不能替代真实独立审查门禁；
- **隔离 L1 与普通轻量 L2**：在 targeted validation、最小完成核对和 Docs Impact 闭环后，如无显式 Review、跨 Owner/PR 交接、项目门禁或更高风险事实，不机械加载独立 Review；
- Review 可复用 Coding 作为唯一研发规范源，但 Coding 不复制 Review 的 Findings、测试专家方法和报告细节；`review-only` 不自动获得修改授权；修生产代码后必须新鲜验证并 re-review；
- Review Skill 无法读取时，只阻塞依赖它的正式 Review/可合并/可交付结论；与 Review 无依赖的已授权工作继续；
- 仓库没有 Review Skill 而事实要求独立 Review 时，继续执行 当前场景所需完整约束；若 Review `not_applicable`，不反向制造一轮审查。

这项协作保留 Coding 原有 L1-L3、Change、TDD、Validation Matrix、Completion Audit、Docs、Git、CI 和交付能力，只把它们从固定串行流水线改成按真实触发条件组合；跨 Skill 选择和交接条件由 Router 负责。

## 11. 网络下载源与永久 Workflow 治理

涉及 Runtime/Compiler/SDK、系统包、语言依赖、bootstrap、Docker/OCI、CI bootstrap、部署/恢复等网络下载行为时，必须读取 当前场景所需完整约束 的“网络下载源与镜像选择”完整规则；该 完整约束 已保留中国大陆/海外环境判断、联网核验、供应链身份、完整性与 fallback 的全部细节。

新增或修改永久 CI/Workflow/test gate/build/package/release 流程，或明确优化其成本/时延时，必须读取 当前场景所需完整约束 的 `CI / Workflow Responsibility Audit` 完整规则。删除、合并、迁移或大幅收缩永久 Job/Step 前仍必须完成 `Evidence Preservation Mapping`，并检查 Branch Protection/Ruleset/release gate/check name 的实时消费者；不能因主文件不再复制该长段规则而降低证据责任。