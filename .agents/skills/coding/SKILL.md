---
name: coding
description: 面向不同项目形态、研发阶段和编程语言的可靠软件研发工作流。先恢复仓库当前事实，再按项目形态、研发阶段/任务类型、编程语言/工具链和风险等级 L1-L3 组合路由；依据真实 Contract、Schema、数据、模块边界和项目规则执行需求设计、功能开发、Bug 修复、重构、Review、CI、Git 与交付验证。保留可失效项目导航、Git 可见 Change、Requirement Traceability、Completion Audit、Red-Green-Refactor、根因调试、分层验证、多人协作和新鲜证据门禁。Use for repository onboarding, planning, implementation, debugging, refactoring, review, verified delivery, release work, and parallel human or agent coding across languages and project types.
---

# Coding

把自然语言研发请求转化为一个可追溯、可验证的交付闭环：

```text
恢复当前仓库事实
→ 四维任务路由
→ 明确需求与风险
→ 选择最少但充分的流程和证据
→ 最小兼容实现
→ 新鲜验证
→ Completion Audit / Review
→ 只交付证据真正支持的结论
```

本 Skill 不是 Python、Web、Backend 或 PostgreSQL 专用流程。它的固定部分是“怎样可靠研发”；具体语言、框架、数据库、目录、包管理器、CI 和部署方式必须来自当前项目事实。

详细规则分布在 `references/`。**当本文件的触发条件命中时，对应 reference 是本 Skill 的规范组成部分，必须在执行相关动作前读取；不能只读主文件后凭印象补流程。**

`references/` 当前使用 `01_`、`02_`……两位数字前缀表达研发流程阅读顺序，便于人类从目录直接理解上下游关系。**编号只是导航，不是固定文档数量、固定文件名或固定编号上限**；未来 reference 增删时按真实依赖关系调整。每个任务仍只读取命中的最少充分规则，不要求机械通读全部编号文件。

**内容守恒优先于篇幅精简。** 对本 Skill、reference、模板或项目 Overlay 做重组、通用化、拆分、合并、改名或“精简”时，只允许改变组织方式，不允许降低规则语义、触发条件、例外、失败处理、验证责任、安全边界或兼容要求。不能把多条带条件、例外或失败处理的可执行规则压成一句抽象原则；只有逐项证明完全等价时才允许消除重复。无法证明完全等价时，保留原细节，并按 [12_规则保留映射.md](references/12_规则保留映射.md) 记录旧规则到新规范位置的可追溯关系。

## 0. 强制执行模型：先路由，再工作

每个独立任务在制定实现计划前先按 [02_跨项目研发任务路由.md](references/02_跨项目研发任务路由.md) 建立四维路由：

```text
项目形态
× 研发阶段 / 任务类型
× 编程语言 / 工具链
× 风险等级 L1 / L2 / L3
→ 本次必须读取的 references
→ 本次 Validation Matrix
→ 本次 Change / Review / Git 门禁
```

至少回答：

```text
执行模式是什么？
项目实际是什么形态？
现在处于什么研发阶段？
使用什么真实语言、Runtime、Manifest、锁文件、构建与测试工具？
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

继续读取项目规则、锁文件、版本文件、workspace、CI、真实代码和调用链后再判断。

## 1. 先遵守这些不变量

这些规则跨项目、跨语言、跨研发阶段成立。

1. **上位规则优先。** 先遵守系统、开发者、用户以及目标目录中适用的 `AGENTS.md`、`CONTRIBUTING` 或同等仓库规则。本 Skill 不能降低更高优先级约束；项目本地规则是通用 Skill 的 Overlay。
2. **仓库事实优先。** 把当前仓库文件、运行结果和用户明确确认视为事实。缓存只作导航，不作事实副本；明确区分已确认事实、推断、建议和暂时无法验证，不默认用户或 Agent 判断正确。
3. **权限边界明确。** 只在任务授权范围内写文件或执行外部动作。只读分析、Review、审计或答疑不自动授权创建缓存、Change、分支、提交、PR、合并、部署或生产操作。
4. **保护用户工作。** 保留用户未提交修改。禁止覆盖式检出、强制推送、破坏性清理、未授权历史重写以及把无关用户改动混入本任务。
5. **不静默扩大变化。** 不擅自升级依赖/Runtime、切换包管理器或框架、改公共接口/ABI/格式、改变数据语义、扩大范围或进行无关重构。
6. **完成结论必须有本轮新鲜证据。** 没有实际执行的完整验证证据，不得宣称完成、修复、通过、可合并、可发布或可部署。
7. **从目标和根因推导机制。** 从可观察目标、硬约束、当前事实和根因选择最小充分方案；“最佳实践”只是候选证据，不能覆盖仓库事实或成为引入复杂度的理由。
8. **不发明项目制度。** 只执行仓库真实存在或本次需求明确建立的边界、Contract、Schema、Owner、Migration、测试和发布机制；经有界调查未发现时标记不适用并跳过，不为了填模板补造架构。
9. **独立能力建立独立验证闭环。** 对具有明确输入输出、独立业务价值、独立失败边界，或无需启动完整系统即可验证的能力，优先复用生产入口建立最小验证闭环，使用与风险匹配的自动化测试、Fixture/Fake/隔离依赖、明确运行方式和成功判据。不要机械要求“一模块一个测试文件”或“一功能一个测试文档”。
10. **L2/L3 必须向上追溯。** 当前 Change 不是自身需求全集。必须从用户已确认决定和上游正式事实源建立 Requirement Traceability；进入 `ready_for_review` 前重新读取上游完成定义并执行 Completion Audit。CI 全绿不能替代需求完整性审计，也不能依赖用户事后发现漏项。
11. **验证按风险而不是固定技术栈分层。** L2/L3 先按 [07_通用验证与证据策略.md](references/07_通用验证与证据策略.md) 建立技术栈无关 Validation Matrix。任何层都不能声称证明自己没有实际运行的下游边界。若项目真实存在 Web/API/PostgreSQL/外部 Provider，再叠加 [08_分层测试与验收策略.md](references/08_分层测试与验收策略.md) 的 Browser Mock、Backend/API/PostgreSQL Integration、Contract、Real Full-stack、Real Provider Probe 专项规则；这些细节保留但不强加给 CLI、Library、Mobile、Embedded、IaC 等项目。
12. **中文注释与函数级说明是通用规则。** 代码注释统一使用中文；专有名词、标识符、协议、库、标准名以及必须保持原样的外部文本可以保留原语言。新增或修改的 public/exported 函数必须有与复杂度匹配的函数级中文注释或文档注释；**内部/private/helper 函数也必须写函数级中文注释或文档注释**，不能因为不是 public 就省略。简单函数的说明可以非常简短，但不能用“自解释”作为完全不写函数级说明的理由。复杂规则、关键不变量、状态转换、算法取舍、兼容原因和重要副作用还要重点解释 `why / invariant / risk / compatibility`，不要逐行翻译语法。
13. **重要功能可观测性需要匹配现有体系。** 如果仓库已有日志/事件基础设施，且功能涉及关键生命周期、异步任务、外部 I/O、重试/部分失败、状态转换或后期排障价值，应补最小充分结构化观测。复用现有 logger/event/脱敏/关联 ID；禁止打印 Secret/Token/密码/敏感 Raw/PII，禁止 INFO 高频刷屏，日志也不能替代数据库/文件中的正式业务事实或 Health/Audit 机制。
14. **Git 提交信息统一中文。** 所有 Git 提交信息使用中文，包括普通提交、修复提交和合并提交的说明文本；命令、路径、标识符、版本号等必要技术内容可以保留原文。项目可以进一步规定提交格式或前缀，但不能把提交信息语言改为非中文。
15. **所有时间相关默认采用北京时间。** Coding Skill、Agent 以及由其新增或默认解释的时间戳、日期、日志、缓存、Change 元数据、报告时间、脚本默认时间和用户可见时间统一使用北京时间 `Asia/Shanghai`（UTC+8），不得依赖宿主本地时区。外部协议、原始数据或既有机器 Contract 明确规定其他时区时保留原始事实语义，但在 Agent 输出、人类可读日志和展示边界明确转换为北京时间，不得把 UTC 值直接当作北京时间。
16. **日志前缀统一且可定位。** 除非更高优先级的外部日志 wire-format Contract 强制其他序列化形式，所有人类可读日志记录统一使用 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message`；时间必须是北京时间，毫秒固定三位，`source.ext` 与 `L<line>` 来自真实调用点，`LEVEL` 使用大写。结构化日志若因平台 Contract 必须采用 JSON 等形式，仍必须提供等价的北京时间、source、line、level 字段。

规则重组时还必须遵守 [12_规则保留映射.md](references/12_规则保留映射.md)：通用化只能移动和分类规则，不能用“精简”删除仍有效内容。

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

具体识别和验证边界见 [02_跨项目研发任务路由.md](references/02_跨项目研发任务路由.md)。

### 2.2 研发阶段 / 任务类型

先确定主阶段：

- Repository Onboarding / Fact Recovery；
- Requirement / Design / Technical Decision；
- Feature / Behavior Implementation；
- Bug / Failure / Incident Diagnosis；
- Refactor / Performance / Maintainability；
- Code Review / Audit；
- Integration / PR / Release / Delivery；
- Maintenance / Dependency / Runtime Migration；
- Security / Permission / Irreversible Data Operation。

同一任务可以跨相邻阶段，但不能为了赶进度跳过上游门禁。

### 2.3 编程语言 / 工具链

读取 [03_编程语言与工具链适配规则.md](references/03_编程语言与工具链适配规则.md)。它覆盖 Python、JavaScript / TypeScript、Go、Rust、Java / Kotlin、.NET、C / C++、Swift、Dart / Flutter、PHP、Ruby、Elixir、Monorepo、Container / IaC，并提供未列语言的统一发现算法。

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
| L2 | 新功能、行为变化、重要 Bug、多文件修改、多人并行或需要追踪的工作 | 一个 `CHANGE.md` | 明确目标、成功标准、范围、非目标、不变项、验证 |
| L3 | public API/ABI、Schema/Migration、跨模块 Contract、架构、认证授权、安全、部署恢复、重大依赖或破坏性兼容变化 | 扩展同一个 `CHANGE.md` | 比较 2–3 个真实方案，关键上游决策确认后实现 |

行数少不等于 L1。公共配置字段、CLI flag、序列化格式、数据库列、权限语义、不可逆数据操作都可能是 L2/L3。

## 3. 按触发条件读取资源

不要把所有 reference 一次性全读，也不能在命中触发条件时跳过对应 reference。

| 触发条件 | 必须读取 |
| --- | --- |
| 首次进入仓库、缓存缺失或可能过期 | [01_项目发现与可失效缓存.md](references/01_项目发现与可失效缓存.md) |
| 需要识别项目形态、研发阶段或组合流程 | [02_跨项目研发任务路由.md](references/02_跨项目研发任务路由.md) |
| 需要确认语言、Runtime、Manifest、锁文件、构建或包管理 | [03_编程语言与工具链适配规则.md](references/03_编程语言与工具链适配规则.md) |
| L2/L3、需要需求追踪或已有 Active Change | [04_轻量变更管理.md](references/04_轻量变更管理.md) |
| 新/当前 Change 使用 Completion Gate | [10_完成定义追溯门禁.md](references/10_完成定义追溯门禁.md) |
| 开发 Feature、修 Bug、重构、性能或调查失败 | [05_设计实施与根因调试.md](references/05_设计实施与根因调试.md) |
| 需要规划或审计验证证据 | [07_通用验证与证据策略.md](references/07_通用验证与证据策略.md) |
| Web/API/PostgreSQL/Provider 等专项边界真实存在 | [08_分层测试与验收策略.md](references/08_分层测试与验收策略.md) |
| 跨模块、跨消费者、Contract/Schema/Migration/Owner/数据边界 | [06_仓库边界数据交换与条件式约束.md](references/06_仓库边界数据交换与条件式约束.md) |
| 多人、多 Agent、多个分支或 Active Change 并行 | [09_多人和多智能体并行协作.md](references/09_多人和多智能体并行协作.md) |
| Review、Ready、交付或准备表达完成结论 | [11_两阶段复核与完成前验证.md](references/11_两阶段复核与完成前验证.md) |
| Skill 自身规则重组/迁移/完整性审计 | [12_规则保留映射.md](references/12_规则保留映射.md) |

不要要求用户重复提供能够从仓库、缓存或工具确认的信息。只读取当前任务真正需要的事实和 reference，不用“全仓全部读一遍”替代理解调用链。

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

### 4.3 恢复项目和工具链事实

按 [01_项目发现与可失效缓存.md](references/01_项目发现与可失效缓存.md) 与 [03_编程语言与工具链适配规则.md](references/03_编程语言与工具链适配规则.md) 确认任务相关的：

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

所有由 Agent 在本任务中新建、填充或默认解释的时间字段都按 `Asia/Shanghai` 处理；如果读取到外部来源或既有 Contract 的 UTC/其他时区值，先保留原始事实，再在需要展示、记录人类日志或形成 Agent 输出时明确转换为北京时间。

### 4.4 复用或建立可失效项目导航

项目缓存路径固定为：

```text
.agents/project-context.json
```

对已授权写入的实现任务，在每个独立任务或新工作会话首次规划前运行；同一任务内发生同步、切换分支、rebase、历史改写或候选事实源变化后重新运行。终端、Python 和项目写权限均可用时：

```text
python <skill>/scripts/coding.py discover --root <repo>
```

- `cache_hit`：候选事实源未出现可见失效信号；复用导航，但仍读取本次真实需求、实现、调用链和相关测试；
- `created` / `refreshed`：检查索引发现的规则、需求、架构、Contract、Migration、配置、依赖和测试入口；
- 脚本失败：保留原错误，按 `01_项目发现与可失效缓存.md` 人工流程继续，不声称缓存有效。

索引只保存路径、分类、轻量指纹和可直接提取的脚本名，不复制需求正文。`cache_hit` 不代表普通源码没有变化，也不能代替 `git diff`、真实文件或调用链调查。缓存 `generated_at` 必须使用带 `+08:00` 偏移的北京时间；旧缓存路径不读取、不迁移，直接由下一次 discover 在 `.agents/project-context.json` 重建。

如果目标语言/工具链不在脚本当前识别范围，缓存只是降级，不得阻止人工事实发现。

### 4.5 检查 Active Change 和并行冲突

存在 `changes/active/*/CHANGE.md` 时，在设计/编码前读取当前 Active Change。终端可用时：

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

发现交集时指出具体冲突并决定排序、拆分或共同 Owner；没有交集时不因为“都改后端/都改前端”制造冲突。Change 是 Git 协作协议，不是锁，也看不到未推送/私有客户端状态。多人/多 Agent 细节遵循 [09_多人和多智能体并行协作.md](references/09_多人和多智能体并行协作.md)。

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

L2/L3 创建或认领一个 Active Change。优先：

```text
python <skill>/scripts/coding.py new-change --root <repo> \
  --id CHG-YYYYMMDD-short-name --title <title> --owner <owner> \
  --branch <branch> --level L2 --area <area> --path <path>
```

脚本不可用时，从 [CHANGE.template.md](assets/CHANGE.template.md) 创建；进入 Ready 前不能保留占位内容。Coding 新建 Change 的 `created` / `updated` 日期以北京时间当天为准。

新模板默认：

```text
completion_gate: required
```

对这种 Change，编码前必须从本轮用户明确决定、正式 Requirement/Roadmap/Spec/Stage/ADR 和适用项目规则中独立建立 Requirement Traceability。状态只允许：

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

L2/L3 使用 [07_通用验证与证据策略.md](references/07_通用验证与证据策略.md) 的通用维度：

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

如果实际项目是 Web/API/PostgreSQL/Provider，再读取 [08_分层测试与验收策略.md](references/08_分层测试与验收策略.md)，把通用维度映射为其完整专项层：

```text
Browser Mock Acceptance
Backend / API / PostgreSQL Integration
Contract / Generated Client
Real Full-stack Golden Path
Real Provider Probe
```

保留原专项职责：Browser Mock 广覆盖用户状态，Backend/DB 证明服务器与持久化，Contract 防机器接口漂移，Full-stack 用少量 Golden Path 证明真实接线，Provider Probe 仅必要时有界执行。CLI、Library、Mobile、Embedded、IaC 没有这些边界时不制造它们。

### 4.10 按研发阶段实施

#### Feature / 行为变化 / Bug / Refactor

读取 [05_设计实施与根因调试.md](references/05_设计实施与根因调试.md)，默认：

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
- link/reference；
- generated diff；
- build；
- dry-run/plan；
- package/open；
- 实际运行；
- repository consistency。

不要伪造一个形式化 Red。

#### 失败 / Bug / 性能 / 异常

先根因调查，不猜测式修补：

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

连续三次修复假设失败时停止叠加补丁，重新审视架构、前提和观测手段并报告阻塞。

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

任务跨模块、跨消费者、接口/事件/数据，或仓库已有明确 Owner/Contract/Schema/Migration 时读取 [06_仓库边界数据交换与条件式约束.md](references/06_仓库边界数据交换与条件式约束.md)。

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

#### Docs Skill 按需路由（仓库存在时）

如果仓库存在 `.agents/skills/docs/SKILL.md`，本节的文档同步检查必须先给出 Docs Impact：

- 当前变化不改变人类需要理解、使用、维护、部署或排障的事实：记录 `Docs Impact: not_applicable` 和具体依据，不加载 Docs，不制造无意义文档 diff；
- 当前变化存在文档影响，或当前任务本身就是技术文档 Review / 编写 / 更新：必须读取 `.agents/skills/docs/SKILL.md`，再由 Docs 根据真实影响选择 `targeted`（默认）或 `full`；
- Coding 可以提供候选文档作为导航，但不能代替 Docs 决定真正需要读取或修改哪些文档，也不得把 Docs 的详细写作/审查规则复制或总结进 Coding；
- Docs 返回 `code_issue_detected` 时，回到 Coding 当前完整流程修复实现；修复完成并取得新鲜验证后，再执行 Docs `targeted re-review`。Docs 尚未闭环前，继续受上一条“不得标记 Ready、完成、可合并或可发布”的约束。

如果仓库没有 Docs Skill，则继续完整执行本节原有文档同步规则；不能因为缺少 Docs Skill 跳过文档影响判断或文档同步。

### 4.13 Completion Audit、两阶段 Review 与新鲜验证

对 `completion_gate: required` 的 Change，在 `ready_for_review` 前先执行：

```text
重新读取上游正式事实源
→ 不看当前 Change checklist，独立重建完成定义
→ 比较“上游要求 → Change”，查 requirement omission
→ 比较“Change → 实现 / 测试 / 文档”
→ 执行适用的反向能力审计
→ 复核 Validation Matrix 的层级选择和证据等级
→ 清零 not_satisfied
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

机器门禁：

```text
python <skill>/scripts/ready_check.py --root <repo> --require-active-ready
```

它只验证机器能判断的结构、状态、Source 路径、占位符和 Audit checkbox，不能判断自然语言业务完整性，也不能自动证明 Validation Matrix 充分。

完成 Audit 后按 [11_两阶段复核与完成前验证.md](references/11_两阶段复核与完成前验证.md)：

```text
上游 Requirement Completeness Review
→ 当前 Change / Spec 需求符合性
→ 实现和测试证据
→ Code Quality / 安全 / 兼容 / 可维护性 / 无关改动
```

严重/重要问题未解决不能继续交付。

每个完成结论都重新执行：

```text
确定能证明结论的命令/检查
→ 实际运行完整命令
→ 读取完整输出、退出码、失败数量
→ 对照成功标准、Requirement Traceability、Validation Matrix、diff
→ 只陈述证据支持的状态
```

历史日志、子 Agent 报告、局部测试、“代码看起来正确”不能替代本轮新鲜证据。

### 4.14 关闭或保留 Change

- 尚未合并/发布：只有 Traceability、Validation Matrix、Completion Audit、验证和文档同步满足时才能 `ready_for_review`，继续留在 `changes/active/`；
- 全部成功标准、验证、文档同步完成且集成状态已确认：标记 `done` 后再移动到 `changes/archive/YYYY-MM/`；
- active 期间需求变化：先回上游事实源和 Traceability，再更新同一个 Change；
- 已归档需求后来再变：创建新 Change，不改历史；
- archive 不是成功证据，不能先归档再补验证；
- 不得删除 `completion_gate` 来绕过 Ready Check。

## 5. 多 Agent / 多人协作

只有互不依赖且不修改同一文件、接口、Schema、锁文件或共享状态的工作才并行。派发时给最少充分上下文：目标、范围、事实源、禁止项、验收和输出格式。

主 Agent 必须复核：

- 子任务实际 diff；
- 与当前 HEAD/Change 是否冲突；
- 测试命令是否真的运行；
- 证据范围是否被夸大；
- 是否混入无关改动。

不要直接相信“子 Agent 已完成”。详细规则见 [09_多人和多智能体并行协作.md](references/09_多人和多智能体并行协作.md)。

## 6. Git、依赖与安全的通用边界

### Git

- 修改前检查 branch、worktree、未提交修改；
- 不覆盖用户改动；
- 禁止 `git reset --hard`、`git clean -fd`、强制推送、未授权共享历史重写；
- 未经授权不创建分支、提交、推送、PR、合并、部署、删分支；
- CI 失败、冲突、保护规则或结果未确认时不强行推进；
- 所有 Git 提交信息使用中文；项目可以额外规定提交格式、前缀或工单号，但不能覆盖中文语言要求。

### 依赖

- 先确认语言、Runtime、包管理器、Manifest、锁文件和实际版本；
- 优先标准库和现有依赖；
- 普通功能不顺手升级；
- 新依赖说明必要性、维护、许可证、体积/构建影响和替代方案；
- Manifest 改动同步仓库正式 lock；
- 不用删除 lock、切换包管理器或解析 `latest` 掩盖问题。

### 安全

- 不硬编码、打印、提交或上传 Secret/Token/密码；
- 不关闭认证、授权、证书、输入校验或既有安全门禁制造“通过”；
- 避免不安全反序列化、任意命令/动态代码执行、字符串拼接 SQL；
- 按任务风险校验路径、文件、网络、数据库、命令、模板、归档和用户输入；
- 外部服务、生产数据、真实环境写入必须受明确权限和数据边界约束。

## 7. 交付报告

最终报告至少包含：

1. 变更摘要与逐文件/按类别目的；
2. 本次项目形态、研发阶段、语言/工具链和风险等级；
3. 上游 Requirement Traceability 与成功标准完成状态；
4. Validation Matrix：每层 Scope、实际 Evidence、`not_applicable` 依据；
5. Completion Audit / 两阶段 Review 结果；
6. Contract/API/ABI/Schema/Migration/数据变化（无则明确无）；
7. 文档同步及判断依据；
8. 本轮实际执行命令/检查、退出码、通过/失败数量；
9. 未验证内容、阻塞和剩余风险；
10. 兼容性、依赖、Migration、部署、迁移和回滚影响；
11. Git 分支、提交、PR、CI、合并和分支清理的实际状态。

不要只回复“已完成”“已修复”或“测试通过”。

## 8. 能力边界

- 项目缓存是可失效导航，不是向量数据库、长期记忆或需求事实副本；
- Change 是 Git 协作协议，不是原子锁、租约、看板、通知或在线状态服务；
- Completion Gate 是流程完整性门禁，不是自然语言需求证明器；它不能替代 Agent/Reviewer 从上游事实源做语义完整性审计；
- Validation Matrix 是风险到证据的语义映射，不是固定测试配额，也不是 `ready_check.py` 能自动证明充分性的清单；
- 语言/项目 profile 是发现和验证导航，不是授权升级技术栈或重构架构；
- 看不到未提交、未推送、未同步、无权限访问或另一客户端私有状态；
- 不能强制其他人/Agent 遵守 Owner、分支或影响范围；仓库 CI/Branch Protection 可以阻止不满足门禁的变更合入；
- 宿主不支持持久文件、目标工具链、脚本、Git、device、数据库或外部服务时，只能执行其实际支持的流程，并明确降级与未验证风险。

## 9. 规则完整性维护

后续如果要再次“精简”“拆分”“合并”本 Skill：

1. 先读取 [12_规则保留映射.md](references/12_规则保留映射.md)；
2. 检查现有 Change/CI/文档对 reference 路径的实时引用；
3. 建立会因规则丢失而失败的回归；
4. 内容守恒优先于篇幅精简；不能用一条抽象原则替代多条带条件、例外或失败处理的可执行规则；
5. 对每条被移动、合并、条件化或改名的规则记录“旧位置 → 新规范位置”，并复核触发条件、例外、失败行为、验证责任和安全/兼容边界；
6. 只有逐项证明完全等价时才允许删除重复；无法证明完全等价时，保留原细节；
7. 项目特定规则迁回项目 Overlay 前，先证明已有新的正式承载；
8. 完成后从旧入口反向检查每条高价值规则是否仍可达，并执行 portability / preservation 回归与人工内容守恒 Review。

## 10. Review Skill 集成

#### Review Skill 强制路由（仓库存在时）

如果仓库存在 `.agents/skills/review/SKILL.md`，Coding 必须把 Review 视为完成前的独立审查层，而不是可选建议：

- **显式 Code Review / Audit**：Coding 先完成仓库事实恢复、四维任务路由、风险/工具链/权限确认，并读取当前任务应触发的 Coding references；随后必须读取 `.agents/skills/review/SKILL.md`，立即切入 Review，由 Review 负责独立需求重建、Findings 和测试充分性审查；
- **任何 Coding 实现任务**：完成实现、目标验证、文档同步和进入完成前 Review 时，必须读取 `.agents/skills/review/SKILL.md` 并执行适用 Review；不能只由同一个 Coding 流程用一句“自检完成”替代独立 Review 方法；
- Review 可以复用 Coding 作为唯一研发规范源，但 Coding 不把 Review 的 Findings、测试专家方法和报告细节复制进本文件；
- Review 处于 `review-only` 时不自动获得实现修改授权；Review 发现需要修生产代码且任务已授权修复时，返回 Coding，重新按 Coding 完整流程修复并取得新鲜验证，然后再次进入 Review 做 re-review；
- Review Skill **存在但无法读取**时，必须报告阻塞，**不得宣称 Review 完成**、可合并或可交付；
- 如果仓库没有 Review Skill，则继续执行 Coding 当前 [11_两阶段复核与完成前验证.md](references/11_两阶段复核与完成前验证.md) 的既有 Review 规则，不能因为可选 Skill 缺失跳过 Review 本身。

这条路由只增加独立审查层，不改变 Coding 原有 L1-L3、Change、TDD、Validation Matrix、Completion Audit、Docs、Git、CI 或交付规则。
