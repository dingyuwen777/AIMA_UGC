---
name: coding
description: 面向不同项目形态、研发阶段和编程语言的可靠软件研发工作流。由 Router 选中后，先恢复仓库当前事实，再按项目形态、研发阶段/任务类型、编程语言/工具链和风险等级 L1-L3 细化研发流程；依据真实 Contract、Schema、数据、模块边界和项目规则执行需求设计、功能开发、Bug 修复、重构、Review、CI、Git 与交付验证。保留可失效项目导航、Git 可见 Change、Requirement Traceability、Completion Audit、Red-Green-Refactor、根因调试、分层验证、多人协作和新鲜证据门禁。Use for repository onboarding, greenfield bootstrap, planning, implementation, debugging, refactoring, review, verified delivery, release work, and parallel human or agent coding across languages and project types after Router selection.
---

<!-- agent-routing:v1
{
  "协议": "Agent Skills Skill路由/v1",
  "Skill": "coding",
  "触发": {"任一": [{"包含": {"维度": "执行模式", "取值": ["只读分析", "诊断", "方案", "实现", "审查", "验证", "Git", "发布", "运维"]}}, {"包含": {"维度": "项目形态", "取值": ["Greenfield", "CLI", "前端Web", "后端服务", "全栈应用", "移动应用", "桌面应用"]}}, {"包含": {"维度": "风险", "取值": ["L1", "L2", "L3"]}}, {"包含": {"维度": "授权", "取值": ["允许只读", "允许修改项目", "允许测试", "允许 Git", "允许发布"]}}]}
}
-->

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

**内容守恒优先于篇幅精简。** 对本 Skill、完整约束、模板或项目 Overlay 做重组、通用化、拆分、合并、改名或“精简”时，只允许改变组织方式，不允许降低规则语义、触发条件、例外、失败处理、验证责任、安全边界或兼容要求。不能把多条带条件、例外或失败处理的可执行规则压成一句抽象原则；只有逐项证明完全等价时才允许消除重复。无法证明完全等价时，保留原细节。规则重组必须用回归测试、旧入口反向检查和人工语义对照证明高价值规则仍可达，不再依赖独立的规则映射文档。

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

至少回答：

```text
执行模式是什么？
项目实际是什么形态？
现在处于什么研发阶段？是否是尚未建立完整工程事实的 Greenfield / Prototype？
使用什么真实语言、Runtime、Manifest、锁文件、构建与测试工具；尚未建立时哪些选择已经确认？
任务风险是 L1、L2 还是 L3？
会影响哪些模块、接口、数据、配置、用户行为、运行时或外部依赖？
哪些验证维度 required，哪些有事实依据地 not_applicable？
用户授权了哪些 Git / PR / Release 动作？
```

不要先根据文件扩展名、个人经验或“常见最佳实践”假设技术栈。例如：

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
6. **完成结论必须有本轮新鲜证据。** 没有实际执行的完整验证证据，不得宣称完成、修复、通过、可合并、可发布或可部署。
7. **从目标和根因推导机制。** 从可观察目标、硬约束、当前事实和根因选择最小充分方案；“最佳实践”只是候选证据，不能覆盖仓库事实或成为引入复杂度的理由。
8. **不发明项目制度。** 只执行仓库真实存在或本次需求明确建立的边界、Contract、Schema、Owner、Migration、测试和发布机制；经有界调查未发现时标记不适用并跳过，不为了填模板补造架构。Coding 自带 Change 只是在项目没有可复用治理载体时的 fallback，不能静默与 OpenSpec、RFC、ADR、Issue 或其他既有正式治理体系平行造一套制度。
9. **独立能力建立独立验证闭环。** 对具有明确输入输出、独立业务价值、独立失败边界，或无需启动完整系统即可验证的能力，优先复用生产入口建立最小验证闭环，使用与风险匹配的自动化测试、Fixture/Fake/隔离依赖、明确运行方式和成功判据。不要机械要求“一模块一个测试文件”或“一功能一个测试文档”。
10. **L2/L3 必须向上追溯，但不等于都要持久 Change。** 所有 L2/L3 都必须能从用户已确认决定、当前 Requirement Source 或正式项目事实说明目标和验收来源。普通轻量 L2 使用最小充分任务契约并在强完成结论前重新核对当前要求；只有持久 gated L2、L3 或项目明确要求 Completion Gate 的单元才需要完整 Requirement Traceability、持久施工契约与 Completion Audit。CI 全绿不能替代需求完整性核对，也不能依赖用户事后发现漏项。
11. **验证按风险而不是固定技术栈分层。** L2/L3 先按 当前场景所需完整约束 建立技术栈无关 Validation Matrix。任何层都不能声称证明自己没有实际运行的下游边界。若项目真实存在 Web/API/PostgreSQL/外部 Provider，再叠加 当前场景所需完整约束 的 Browser Mock、Backend/API/PostgreSQL Integration、Contract、Real Full-stack、Real Provider Probe 专项规则；这些细节保留但不强加给 CLI、Library、Mobile、Embedded、IaC 等项目。
12. **中文注释与函数级说明是通用规则。** 代码注释统一使用中文；专有名词、标识符、协议、库、标准名以及必须保持原样的外部文本可以保留原语言。新增或修改的 public/exported 函数必须有与复杂度匹配的函数级中文注释或文档注释；**内部/private/helper 函数也必须写函数级中文注释或文档注释**，不能因为不是 public 就省略。简单函数的说明可以非常简短，但不能用“自解释”作为完全不写函数级说明的理由。复杂规则、关键不变量、状态转换、算法取舍、兼容原因和重要副作用还要重点解释 `why / invariant / risk / compatibility`，不要逐行翻译语法。
13. **重要功能可观测性需要匹配现有体系。** 如果仓库已有日志/事件基础设施，且功能涉及关键生命周期、异步任务、外部 I/O、重试/部分失败、状态转换或后期排障价值，应补最小充分结构化观测。复用现有 logger/event/脱敏/关联 ID；禁止打印 Secret/Token/密码/敏感 Raw/PII，禁止 INFO 高频刷屏，日志也不能替代数据库/文件中的正式业务事实或 Health/Audit 机制。
14. **Git 提交信息统一中文。** 所有 Git 提交信息使用中文，包括普通提交、修复提交和合并提交的说明文本；命令、路径、标识符、版本号等必要技术内容可以保留原文。项目可以进一步规定提交格式或前缀，但不能把提交信息语言改为非中文。
15. **所有时间相关默认采用北京时间。** Coding Skill、Agent 以及由其新增或默认解释的时间戳、日期、日志、缓存、Change 元数据、报告时间、脚本默认时间和用户可见时间统一使用北京时间 `Asia/Shanghai`（UTC+8），不得依赖宿主本地时区。外部协议、原始数据或既有机器 Contract 明确规定其他时区时保留原始事实语义，但在 Agent 输出、人类可读日志和展示边界明确转换为北京时间，不得把 UTC 值直接当作北京时间。
16. **日志前缀统一且可定位。** 除非更高优先级的外部日志 wire-format Contract 强制其他序列化形式，所有人类可读日志记录统一使用 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message`；时间必须是北京时间，毫秒固定三位，`source.ext` 与 `L<line>` 来自真实调用点，`LEVEL` 使用大写。结构化日志若因平台 Contract 必须采用 JSON 等形式，仍必须提供等价的北京时间、source、line、level 字段。
17. **系统级分析先于局部实现。** 先恢复任务相关能力边界，再决定局部修复、复用、公共抽象或能力归一；系统级不等于全仓扫描。详见 当前场景所需完整约束。
18. **受影响代码域必须整洁收口。** 清理本次受影响域内确认失效、重复或无用实现，同时保护兼容、隐式引用和用户工作，禁止扩大无关重构。详见 当前场景所需完整约束。
19. **Skill Mutation 先做 Mutation 目标解析。** 只改 canonical Owner；本地安装副本不得成为替代 Skill。无法读取或交付时失败关闭。详见 当前场景所需完整约束。

## 2. 四维任务路由

### 2.1 项目形态

从真实仓库选择一个或多个：

- Library / SDK；
- CLI / Developer Tool；
- Service / Backend / API；
- Frontend / Web UI；
- Full-stack Application；
- Mobile / Desktop；
- Data / Batch / ETL / ML；
- Embedded / Systems；
- Infra / IaC / Build / Release Tooling；
- Monorepo / Polyglot；
- Documentation / Configuration / Migration-only 当前任务。

具体识别和验证边界见 当前场景所需完整约束。

### 2.2 研发阶段 / 任务类型

先确定主阶段：

- Greenfield / Repository Bootstrap / Prototype / Feasibility；
- Repository Onboarding / Fact Recovery；
- Requirement / Design / Technical Decision；
- Feature / Behavior Implementation；
- Bug / Failure / Incident Diagnosis；
- Refactor / Performance / Maintainability；
- Code Review / Audit；
- Integration / PR / Release / Delivery；
- Maintenance / Dependency / Runtime Migration；
- Security / Permission / Irreversible Data Operation。

Greenfield 表示工程事实尚未建立或只建立了一部分。此时先确认用户目标、非目标、硬约束、交付/运行环境和已经决定的技术边界，再比较必要方案并建立最小可验证工程基线；不能因为“当前没有锁文件/测试/CI”就把 Skill 示例当默认方案。Prototype / Spike 可以允许明确的临时性实现，但必须写清哪些能力不是生产承诺、哪些安全/数据边界不能放宽、怎样验证可行性以及怎样决定丢弃或生产化。

同一任务可以跨相邻阶段，但不能为了赶进度跳过上游门禁。

### 2.3 编程语言 / 工具链

读取 当前场景所需完整约束。它覆盖 Python、JavaScript / TypeScript、Go、Rust、Java / Kotlin、.NET、C / C++、Swift、Dart / Flutter、PHP、Ruby、Elixir、Monorepo、Container / IaC，并提供未列语言的统一发现算法。

任何 profile 都只负责导航：

```text
版本事实
→ Manifest / Workspace
→ 锁文件 / Dependency policy
→ Build / Test / Lint / Format / Static analysis
→ Package / Artifact / Runtime
→ CI / Release
```

不得因为 profile 提供示例命令就跳过仓库实际命令调查，也不得擅自升级或更换工具链。

### 2.4 风险等级

使用最低但充分的等级；发现隐藏复杂度时升级，不静默降级。

| 等级 | 适用范围 | Change 记录 | 设计门禁 |
| --- | --- | --- | --- |
| L1 | 行为不变机械修改，或边界明确、影响隔离的极小修复 | 不创建 | 简短计划后执行，仍需验证 |
| L2 | 新功能、行为变化、重要 Bug、多文件修改、多人并行或需要追踪的工作 | 最小充分任务契约；出现持久治理价值时升级为持久施工契约 | 明确目标、成功标准、范围、非目标、不变项、验证 |
| L3 | public API/ABI、Schema/Migration、跨模块 Contract、架构、认证授权、安全、部署恢复、重大依赖或破坏性兼容变化 | 持久施工契约 | 比较 2–3 个真实方案，关键上游决策确认后实现 |

行数少不等于 L1。公共配置字段、CLI flag、序列化格式、数据库列、权限语义、不可逆数据操作都可能是 L2/L3。

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

确认当前宿主是否具有：持久文件系统、终端、目标语言工具链、Git、测试环境、数据库/容器/device、CI、外部服务和多 Agent 能力。

- 没有持久文件系统：可以恢复项目事实，但不能承诺跨会话缓存或 Git 协作记录；
- 不能执行脚本/测试：按人工流程继续，明确未验证项，不伪造脚本结果；
- 用户未授权写项目：只在会话内建立临时导航，不创建项目文件/Change/分支；
- 外部系统/生产环境没有授权：只读调查或使用已批准 sandbox/fake，不执行真实写入。

### 4.2 定位仓库并先读规则

定位真实仓库根目录。先读取从 root 到目标路径适用的 `AGENTS.md`、项目说明和规则，再做其他项目判断。

实现/Git 任务还要检查：

- 当前 branch；
- worktree；
- 未提交/未跟踪修改；
- 当前 HEAD；
- 是否存在 nested repo/worktree/submodule；
- 如果不是 Git repo，明确记录事实。

绝不覆盖、回滚、格式化或混入无关用户修改。

Greenfield 仓库即使暂时为空，也先确认仓库根、当前 Git 状态、目标运行/交付环境和用户已确认约束；没有既有代码时不伪造“当前架构”，而是把尚待建立的工程事实标成待决策或待实现。目标项目**首次接入** Agent_Skills、治理状态待校准或长期**治理事实**疑似漂移时，按 当前场景所需完整约束 在**任何实质性生产代码修改之前**完成 `Project Governance Bootstrap`：写授权下校准项目 Overlay、重读最终 `AGENTS.md` 后**继续原始研发任务**；只有只读授权时在会话内完成最少充分调查、不写项目规则并**继续原始只读任务**。普通后续任务没有长期治理变化时不重复全量校准。

### 4.3 恢复项目和工具链事实

按 当前场景所需完整约束 与 当前场景所需完整约束 确认任务相关的：

```text
README / Requirements / Architecture
入口与目录
Manifest / Runtime version / Lock
Build / Test / CI
Config
Contract / Schema / Migration
调用链 / 数据流
错误处理
生成物
模块 Owner / public boundary
相关历史变更
```

只读取任务相关内容。能从仓库、测试、CI、锁文件或工具确认的事实先自行检查。

如果是 Greenfield，上述条目中尚不存在的内容不是失败；先区分“本次必须决定/建立”“可以延期”“当前不适用”，关键路线存在实质取舍时按 L3 设计门禁确认后再建立。不要为了让发现清单看起来完整而生成无价值的框架、目录、接口或 CI。

所有由 Agent 在本任务中新建、填充或默认解释的时间字段都按 `Asia/Shanghai` 处理；如果读取到外部来源或既有 Contract 的 UTC/其他时区值，先保留原始事实，再在需要展示、记录人类日志或形成 Agent 输出时明确转换为北京时间。

### 4.4 复用或建立可失效项目导航

项目缓存路径固定为：

```text
.agents/project-context.json
```

它是**本地可失效导航缓存，不提交 Git**。目标仓库安装/使用 Coding 时应将它加入本地或仓库 `.gitignore`；如果项目规则禁止修改 `.gitignore`，至少保证本次不把该文件加入提交。缓存不能作为团队共享需求、架构或 Contract 的替代品。

对已授权写入的实现任务，在每个独立任务或新工作会话首次规划前运行；同一任务内发生同步、切换分支、rebase、历史改写或候选事实源变化后重新运行。终端、Python 和项目写权限均可用时：

```text
python <skill>/scripts/coding.py discover --root <repo>
```

- `cache_hit`：候选事实源未出现可见失效信号；复用导航，但仍读取本次真实需求、实现、调用链和相关测试；
- `created` / `refreshed`：检查索引发现的规则、需求、架构、Contract、Migration、配置、依赖和测试入口；
- 脚本失败：保留原错误，按 `当前场景所需完整约束` 人工流程继续，不声称缓存有效。

索引只保存路径、分类、轻量指纹和可直接提取的脚本名，不复制需求正文。`cache_hit` 不代表普通源码没有变化，也不能代替 `git diff`、真实文件或调用链调查。缓存 `generated_at` 必须使用带 `+08:00` 偏移的北京时间；旧缓存路径不读取、不迁移，直接由下一次 discover 在 `.agents/project-context.json` 重建。

如果目标语言/工具链不在脚本当前识别范围，缓存只是降级，不得阻止人工事实发现。

### 4.5 检查 Active Change 和并行冲突

先发现目标项目是否已有正式变更治理：OpenSpec、RFC/ADR、Issue/PR 约定、项目自己的 `changes/` 或其他机制都可能是项目 Overlay。**不要为了使用 Coding 而静默创建与既有治理体系平行的 Change 系统。**

Coding 自带工具只管理 `coding-change/v1`。当项目已经存在可兼容的 Coding Change carrier 时沿用；否则默认 carrier 是：

```text
.agents/changes/
├── active/
└── archive/YYYY-MM/
```

如果仓库已经正式使用顶层 `changes/active` / `changes/archive` 承载同一类 Coding Change，工具可以沿用该现有 carrier，避免搬迁。若检测到 OpenSpec 等不同治理体系且尚未明确如何承载 Coding 的 Requirement Traceability / Validation Matrix / Completion Audit，`new-change` 不应静默新建平行目录；先按项目规则确定承载方式。

设计/编码前读取当前 carrier 中的 Active Change。终端可用时：

```text
python <skill>/scripts/coding.py status --root <repo> --json
```

只比较真实存在或 Change 明确建立的：

- affected paths/modules；
- public Contract/API/ABI/format；
- data/schema/Migration；
- config/runtime；
- shared generated files；
- shared tests/fixtures；
- dependencies/build/release resources。

发现交集时指出具体冲突并决定排序、拆分或共同 Owner；没有交集时不因为“都改后端/都改前端”制造冲突。Change 是 Git 协作协议，不是锁，也看不到未推送/私有客户端状态。多人/多 Agent 细节遵循 当前场景所需完整约束。

### 4.6 分类 L1/L2/L3 并固化任务契约

编码前明确：

```text
背景与当前事实
目标
可观察成功标准
范围
非目标
必须保持不变
输入 / 输出
影响边界
复用点
预计文件
兼容性
数据 / Migration
依赖
验证
文档
部署 / 回滚（适用时）
Git 授权
```

L1 可以在工作说明内维护。

L2 必须有**最小充分任务契约**，但不等于必须新建持久文件。它可以由本轮已确认用户要求、PR body、Issue/工单、Spec/OpenSpec/RFC、项目已有 Change/Proposal 或其他可供执行和审查的正式事实承载，只要目标、成功标准、范围/非目标、不变项、风险和验证入口足够清楚。只有跨 Owner、跨 PR、跨会话长期开发、复杂依赖/阶段、正式审计、项目规则明确要求变更记录，或本任务确实需要 Completion Gate 等**持久治理价值**出现时，才升级为独立持久施工契约。

L3 必须有稳定的持久施工契约，并补充方案比较、公共兼容、Migration/部署/回滚以及安全/运维风险。

目标项目 Overlay 可以更严格。例如项目规则明确要求所有 L2 都使用正式 Change 时，该项目继续执行更严格门禁；通用 Coding 的轻量默认不能覆盖项目自己的治理要求。

当确实需要持久施工契约时，优先复用项目已有正式变更治理，只要它能够承载当前任务实际 required 的 Requirement Traceability、Validation Matrix、Completion Audit、验证和交付状态。项目已有机制不能承载这些 required 语义时，不静默降低门禁，应按项目规则补充最小承载或提请上游决定。

只有任务需要持久施工契约、项目又没有可复用治理机制时，才使用 Coding 自带 `coding-change/v1`：

```text
python <skill>/scripts/coding.py new-change --root <repo> \
  --slug short-name --title <title> --owner <owner> \
  --branch <branch> --level L2 --area <area> --path <path>
```

脚本不可用时，从 [CHANGE.template.md](assets/CHANGE.template.md) 创建到当前 Coding Change carrier；进入 Ready 前不能保留占位内容。Coding 新建 Change 的 `created` / `updated` 日期以北京时间当天为准。

当前 Coding Change schema **只支持 `coding-change/v1`，不读取、不迁移、不兼容旧 schema**。如果目标项目里存在旧格式记录，先按该项目自己的历史/迁移策略处理，不让通用 Skill 静默猜兼容语义。

新模板默认：

```text
completion_gate: required
```

对这种持久 gated Change，编码前必须从本轮用户明确决定、正式 Requirement/Roadmap/Spec/Stage/ADR 和适用项目规则中独立建立 Requirement Traceability。状态只允许：

```text
satisfied
explicitly_deferred
not_applicable
not_satisfied
```

当前 Change 不能引用自身作为 Requirement Source，也不能把自己的成功标准冒充上游需求全集。

### 4.7 处理真正需要用户/Owner 决策的事项

只有仓库和正式资料无法确认、且会实质改变以下内容时才提请决策：

- 业务语义和用户验收；
- public API/ABI/CLI/文件格式/Contract；
- Schema/Migration/数据保留删除；
- 权限/认证/隐私/安全；
- 外部 Provider operation/费用；
- 调度/SLO/RPO/RTO；
- 破坏性兼容；
- 不可逆操作；
- 重大技术路线。

顺序：

```text
先查仓库事实和必要一手资料
→ 给明确推荐
→ 有实质取舍时列 2–3 个真实方案和影响
→ 只问最上游的一个问题
→ 用户/业务 Owner 决策
→ 同步正式事实源和 Change
```

已经固化的决定不重复问；新需求与已批准决定冲突时才重新提请。

### 4.8 制定可验证计划

每一步必须小而完整：

```text
[步骤]
→ 修改范围：[文件 / 模块]
→ 预期结果：[可观察行为 / Contract]
→ 依赖：[前置事实或步骤]
→ 验证方式：[实际命令 / 检查]
```

实现前确定：

- 要复用的现有实现/模式；
- 新增或修改的 public/exported 与内部/private/helper 函数应提供什么函数级中文注释或文档注释，以及哪些复杂规则还需要额外定点说明；
- 已有日志体系中哪些生命周期、外部 I/O、重试/部分失败/状态转换需要观测；所有新增人类可读日志如何满足 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message` 与北京时间要求；
- 最小失败测试或明确 TDD 例外；
- 行为、接口、集成、用户工作流、跨组件、外部依赖、Build/Package/Runtime、Docs/Governance 哪些有独立风险；
- 目标测试、相关测试、静态检查、构建、运行和发布验证；
- 哪些步骤可以真正并行。

只并行互不依赖、且不修改相同文件、接口、Schema、锁文件或共享状态的任务。

### 4.9 先建立 Validation Matrix

L2/L3 使用 当前场景所需完整约束 的通用维度：

```text
行为 / Unit / Component
接口 / Contract
集成 / Persistence / Runtime Dependency
用户 / Workflow Acceptance
跨组件 Golden Path
外部依赖 Probe
Build / Package / Runtime
Docs / Governance / Other
```

每层只写 `required` 或 `not_applicable`。

如果实际项目是 Web/API/PostgreSQL/Provider，再读取 当前场景所需完整约束，把通用维度映射为其完整专项层：

```text
Browser Mock Acceptance
Backend / API / PostgreSQL Integration
Contract / Generated Client
Real Full-stack Golden Path
Real Provider Probe
```

保留原专项职责：Browser Mock 广覆盖用户状态，Backend/DB 证明服务器与持久化，Contract 防机器接口漂移，Full-stack 用少量 Golden Path 证明真实接线，Provider Probe 仅必要时有界执行。CLI、Library、Mobile、Embedded、IaC 没有这些边界时不制造它们。

L1 targeted validation 不为形式建立完整 Matrix；确认满足 Repository L1 前提时按 当前场景所需完整约束 选择 parse/compile/typecheck/targeted test/regression/direct invocation 等最便宜且直接的证据。若只有 Contract、真实 persistence/runtime、跨组件或 package/release 等更强层才能证明目标，重新评估风险并退出轻量路径。

### 4.10 按研发阶段实施

#### Repository L1 Fast Path

如果当前事实已经证明是行为不变机械修改，或根因已确认、边界明确且影响隔离的极小修复，并且不触及 public/数据/安全/依赖/运行时/CI/部署/交付等升级边界，则读取 当前场景所需完整约束，按：

```text
最少相关事实
→ 最小修改 / 最小回归
→ targeted validation
→ Docs Impact
→ 按真实 Review / Git 门禁结束或升级
```

已确认根因的 L1 Bug 必须保留回归证据，但不因为 `阶段=缺陷修复` 本身进入完整系统性诊断。调查中发现根因未知、公共边界或其他更强风险后，立即退出本路径并重新路由。

#### L2/L3 Feature / 行为变化 / Bug / Refactor

读取 当前场景所需完整约束，默认：

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

允许 TDD 例外，但必须明确原因和替代验证，例如：

- parser/schema；
- link/完整约束；
- generated diff；
- build；
- dry-run/plan；
- package/open；
- 实际运行；
- repository consistency。

不要伪造一个形式化 Red。

#### 需要诊断的失败 / Bug / 性能 / 异常

根因未知、需要提出和证伪假设、Incident、性能或复杂异常先读取 当前场景所需完整约束 并执行根因调查，不猜测式修补：

```text
完整错误和调用栈
→ 稳定复现
→ 近期变更与环境差异
→ 数据流和组件边界
→ 仓库内正常参照与差异
→ 一个可证伪根因假设
→ 单变量最小实验
→ 失败回归用例
→ 单一修复
```

连续三次修复假设失败时停止叠加补丁，重新审视架构、前提和观测手段并报告阻塞。已确认根因且仍满足 Repository L1 的隔离小修复按上一节执行，不重复预付完整诊断上下文。

#### 最小、精准、兼容

实现始终遵守：

- 只写当前需求最少代码；
- 标准库和现有依赖优先；
- 不增加未要求功能、CLI、配置、兼容层、抽象或未来占位；
- 不顺手重构、改名、格式化无关文件；
- 每处 diff 可追溯到需求或验证；
- 删除只因本次修改而失效的内容；
- 默认保持 public API/ABI/import/CLI/config/default/env/data/file/persistence/startup/error compatibility；
- breaking change 必须先设计版本、Migration、兼容期、部署、回滚和验证。

#### 独立调试和 Probe

调试、测试、示例和 Probe 优先调用生产实现，不复制第二套生产规则。真实付费 API、外部 Provider、真机、cloud sandbox 等默认受控：明确请求/费用/数据范围，不打印 Secret，不默认写生产系统，不偷塞普通 CI。

#### 注释与可观测性

代码注释统一使用中文；专有名词、标识符、协议、库、标准名和必须保持原样的外部文本可以保留原语言。新增或修改的 public/exported 与内部/private/helper 函数都必须有函数级中文注释或文档注释；内部函数不能因为可见性低而省略。简单函数可以使用一句简短说明，复杂逻辑重点解释 `why / invariant / risk / compatibility`，不要逐行翻译语法。

仓库已有 logger/event 体系且观测点有独立排障价值时，覆盖低频关键生命周期、异步阶段、external I/O、retry/partial failure/terminal state。高频正常细节保持 DEBUG 或不记录；Secret/敏感 Raw/PII 不记录；日志不能代替正式业务事实。除更高优先级外部 wire-format Contract 强制其他格式外，人类可读日志统一采用 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message`，其中时间为 `Asia/Shanghai` 北京时间、毫秒固定三位、源文件名和真实调用行号可定位、LEVEL 大写；结构化日志必须提供等价字段。

### 4.11 跨模块、Contract、Schema 与数据边界

任务跨模块、跨消费者、接口/事件/数据，或仓库已有明确 Owner/Contract/Schema/Migration 时读取 当前场景所需完整约束。

只在仓库真实存在的边界上执行：

- 找生产者和消费者；
- 找 public Contract；
- 找数据/写 Owner；
- 找 Migration 与兼容机制；
- 找契约/集成测试；
- 评估生成物；
- 评估部署/回滚。

未发现时不为了“分层”发明 Interface/Facade/Factory/BaseRepository、第二套 Client、第二套 Schema 或平行数据源。

### 4.12 同步当前事实和文档

代码变化后语义检查：

```text
README / Architecture / Blueprint / ADR / Spec
API / Contract / Schema / Migration
generated artifact
config / env example
build / startup / deploy
module responsibility / call chain
logging / security / operations
debug / testing instructions
user-visible behavior
roadmap / release state（项目实际维护时）
```

如果文档与实现冲突：

```text
先依据用户已确认决定、项目规则、机器事实判断哪一方正确
→ 实现偏离正式约束：修实现
→ 已批准方案改变系统事实：同步正式文档/Contract/Schema
→ 证据不足：继续调查或提请上游决定
```

正式文档描述系统现在是什么，不写无意义变更流水账；Change 记录为什么变和当时证据。未实现功能不提前写成“当前已支持”。文档不受影响时记录判断依据，不制造无关差异。

项目若有文档编号、命名、历史不可改写等本地规则，严格遵守项目 Overlay；通用 Skill 不强迫所有仓库使用同一编号体系，也不预设任一项目的 Blueprint 数量、具体文件名或编号上限。

文档与代码/Contract 尚未同步时，不得标记 Ready、完成、可合并或可发布。

#### Docs Skill 按需协作（仓库存在时）

如果 Router 已命中 [`.agents/skills/docs/SKILL.md`](../docs/SKILL.md)，或 Coding 在实现过程中确认产生文档影响，本节的文档同步检查必须先给出 Docs Impact，并按 Router 的 Handoff 进入 Docs：

- 当前变化不改变人类需要理解、使用、维护、部署或排障的事实：记录 `Docs Impact: not_applicable` 和具体依据，不加载 Docs，不制造无意义文档 diff；
- 当前变化存在文档影响，或当前任务本身就是技术文档 Review / 编写 / 更新：必须读取 [`.agents/skills/docs/SKILL.md`](../docs/SKILL.md)，再由 Docs 根据真实影响选择 `targeted`（默认）或 `full`；
- Coding 可以提供候选文档作为导航，但不能代替 Docs 决定真正需要读取或修改哪些文档，也不得把 Docs 的详细写作/审查规则复制或总结进 Coding；
- Docs 返回 `code_issue_detected` 时，回到 Coding 当前完整流程修复实现；修复完成并取得新鲜验证后，再执行 Docs `targeted re-review`。Docs 尚未闭环前，继续受上一条“不得标记 Ready、完成、可合并或可发布”的约束。

如果仓库没有 Docs Skill，则继续完整执行本节原有文档同步规则；不能因为缺少 Docs Skill 跳过文档影响判断或文档同步。

### 4.13 Completion Audit、两阶段 Review 与新鲜验证

对 `completion_gate: required` 的 Coding Change，或项目既有治理中承载等价 Completion Gate 的 gated L2/L3 单元，在 `ready_for_review` / 等价 Ready 状态前执行完整 Completion Audit：

```text
重新读取上游正式事实源
→ 不看当前 Change checklist，独立重建完成定义
→ 比较“上游要求 → Change”，查 requirement omission
→ 比较“Change → 实现 / 测试 / 文档”
→ 执行适用的反向能力审计
→ 复核 Validation Matrix 的层级选择和证据等级
→ 清零 not_satisfied
```

普通轻量 L2 没有持久 gated Change 时，不创建形式化 Completion Audit；但在给出“完成 / 可交付 / 可合并”这类强结论前仍至少执行最小完成核对：

```text
重新读取当前 Requirement Source / 已确认任务事实
→ 目标、范围、非目标和验收是否仍是当前版本
→ 关键不变项是否保持
→ required 验证是否有本轮新鲜证据
→ 未验证项、延期和未知项是否如实暴露
```

反向审计不是固定“前端 ↔ 后端”；按项目形态检查真实双向能力，例如：

- public API → 实际 consumer；
- CLI command → handler/output；
- backend capability → UI/consumer entry；
- producer → event → consumer；
- schema → migration → reader/writer；
- package API → downstream example/test；
- deployment config → runtime startup/health。

没有对应边界时记录不适用依据，不制造机制。

使用 Coding 自带 `coding-change/v1` 时，机器门禁：

```text
python <skill>/scripts/ready_check.py --root <repo> --require-active-ready
```

它只验证机器能判断的结构、状态、Source 路径、占位符和 Audit checkbox，不能判断自然语言业务完整性，也不能自动证明 Validation Matrix 充分。项目使用其他正式治理载体时，使用该项目已有机器校验，并保留同等语义 Review；不要假装 Coding 的脚本懂它没有实现的外部 schema。

**只有当前实际存在显式 Review/Audit、持久 gated L2/L3 的独立审查门禁、PR/Change Ready、Git/Release 交付或项目规则明确要求独立复核时**，才按 当前场景所需完整约束 进入完整两阶段 Review：

```text
上游 Requirement Completeness Review
→ 当前 Change / Spec 需求符合性
→ 实现和测试证据
→ Code Quality / 安全 / 兼容 / 可维护性 / 无关改动
```

单纯为了获得 targeted validation 新鲜证据而执行 `验证`，不自动触发完整两阶段 Review。隔离 L1 与普通轻量 L2 在目标验证、最小完成核对和 Docs Impact 闭环后，如果没有新的审查/交付门禁，可以结束当前实现任务。

严重/重要问题未解决不能继续交付。

每个完成结论都重新执行：

```text
确定能证明结论的命令/检查
→ 实际运行完整命令
→ 读取完整输出、退出码、失败数量
→ 对照成功标准、Requirement Traceability（适用时）、Validation Matrix、diff
→ 只陈述证据支持的状态
```

历史日志、子 Agent 报告、局部测试、“代码看起来正确”不能替代本轮新鲜证据。

### 4.14 关闭或保留 Change

只有当前任务实际使用了持久 Change / 项目等价施工契约时才进入本节的状态和归档动作：

- 尚未合并/发布：只有 Traceability、Validation Matrix、Completion Audit、验证和文档同步满足时才能进入 `ready_for_review` 或项目等价 Ready 状态；
- 全部成功标准、验证、文档同步完成且集成状态已确认：标记 `done` / 项目等价完成状态后再归档；Coding 自带 carrier 归档到 `<change-root>/archive/YYYY-MM/`；
- active 期间需求变化：先回上游事实源和 Traceability，再更新同一个 Change；
- 已归档需求后来再变：创建新 Change，不改历史；
- archive 不是成功证据，不能先归档再补验证；
- 不得删除 `completion_gate`、降低项目现有 gate 或改写状态来绕过 Ready Check。

普通 L1/轻量 L2 没有持久 Change 时，不为了“关闭流程”补建再归档一份 Change。

## 5. 多 Agent / 多人协作

只有互不依赖且不修改同一文件、接口、Schema、锁文件或共享状态的工作才并行。派发时给最少充分上下文：目标、范围、事实源、禁止项、验收和输出格式。

主 Agent 必须复核：

- 子任务实际 diff；
- 与当前 HEAD/Change 是否冲突；
- 测试命令是否真的运行；
- 证据范围是否被夸大；
- 是否混入无关改动。

不要直接相信“子 Agent 已完成”。详细规则见 当前场景所需完整约束。

## 6. Git、依赖、安全、交付与宿主能力边界

只要任务涉及 Git / PR / Release / Delivery、依赖变化、安全边界、最终交付报告，或当前宿主能力不足需要降级，必须读取 当前场景所需完整约束。原主文件中 Git、依赖、安全、最终报告和能力边界的详细规则已完整迁入该 完整约束；不能因为本节变短而把它们视为可选建议。

## 7. 规则内容守恒与 Skill 维护

当任务会精简、重组、拆分、合并、改名、迁移或通用化 [`SKILL.md`](SKILL.md)、完整约束、模板或项目 Overlay 时，必须在修改之前读取 当前场景所需完整约束。内容守恒仍是硬门禁：只有逐项证明完全等价时才允许消除重复，无法证明时保留原细节。

## 10. Review Skill 集成

#### Review Skill 按实际门禁协作（仓库存在时）

如果仓库存在 [`.agents/skills/review/SKILL.md`](../review/SKILL.md)，Coding 在**真实审查条件命中时**把 Review 作为独立审查层；Review 能力完整保留，但不是所有实现任务的固定终点：

- **显式 Code Review / Audit**：Coding 先完成仓库事实恢复、四维任务路由、风险/工具链/权限确认，并读取当前任务应触发的 Coding 当前场景所需完整约束；随后必须读取 [`.agents/skills/review/SKILL.md`](../review/SKILL.md)，立即切入 Review，由 Review 负责独立需求重建、Findings 和测试充分性审查；
- **L3、持久 gated L2、PR/Change Ready、Git/Release 交付或项目规则明确要求独立 Review**：完成实现、目标验证、Docs Impact 和适用 Completion Audit 后，必须读取 [`.agents/skills/review/SKILL.md`](../review/SKILL.md) 并执行与风险匹配的 Quick / Standard / Deep Review；不能只用作者自检替代真实独立审查门禁；
- **隔离 L1 与普通轻量 L2**：在 targeted validation、最小完成核对和 Docs Impact 闭环后，如果没有显式 Review、跨 Owner/PR 交接、项目门禁或更高风险事实，不机械加载独立 Review。后续发现这些事实时再升级，不能为了省流程拒绝已经真实命中的 Review；
- Review 可以复用 Coding 作为唯一研发规范源，但 Coding 不把 Review 的 Findings、测试专家方法和报告细节复制进本文件；
- Review 处于 `review-only` 时不自动获得实现修改授权；Review 发现需要修生产代码且任务已授权修复时，返回 Coding，重新按 Coding 完整流程修复并取得新鲜验证，然后再次进入 Review 做 re-review；
- Review Skill **存在但无法读取**时，只有在当前 Review 实际 required 时才构成完成/交付阻塞；此时不得宣称 Review 完成、可合并或可交付；
- 如果仓库没有 Review Skill，而当前事实又要求独立/正式 Review，则继续执行 Coding 当前 当前场景所需完整约束 的既有 Review 规则；如果最小充分治理已证明 Review `not_applicable`，不因为缺少 Review Skill 反向制造一轮审查。

这项协作保留 Coding 原有 L1-L3、Change、TDD、Validation Matrix、Completion Audit、Docs、Git、CI 和交付能力，只把它们从固定串行流水线改成按真实触发条件组合；跨 Skill 选择和交接条件仍由 Router 负责。

## 11. 网络下载源与永久 Workflow 治理

涉及 Runtime/Compiler/SDK、系统包、语言依赖、bootstrap、Docker/OCI、CI bootstrap、部署/恢复等网络下载行为时，必须读取 当前场景所需完整约束 的“网络下载源与镜像选择”完整规则；该 完整约束 已保留中国大陆/海外环境判断、联网核验、供应链身份、完整性与 fallback 的全部细节。

新增或修改永久 CI/Workflow/test gate/build/package/release 流程，或明确优化其成本/时延时，必须读取 当前场景所需完整约束 的 `CI / Workflow Responsibility Audit` 完整规则。删除、合并、迁移或大幅收缩永久 Job/Step 前仍必须完成 `Evidence Preservation Mapping`，并检查 Branch Protection/Ruleset/release gate/check name 的实时消费者；不能因主文件不再复制该长段规则而降低证据责任。
