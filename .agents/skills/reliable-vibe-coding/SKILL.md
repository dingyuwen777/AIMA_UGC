---
name: reliable-vibe-coding
description: 为软件仓库首次接入、持续开发和多人并行提供可靠工作流：首次运行发现需求与高价值目录，后续每个独立任务检查最新变动并复用可失效索引；依据仓库事实和已有 Contract、Schema、数据与模块边界实施最小、可验证、兼容的变更。用于功能开发、Bug 修复、重构、代码审查、交付验证，以及 Codex、Claude Code、Cursor 等 Agent Skills 兼容工具中的协作开发。Use for repository onboarding, implementation, bug fixing, refactoring, review, verified delivery, and parallel human or agent coding.
---

# Reliable Vibe Coding

把自然语言开发请求转化为基于仓库事实、最小实现、真实测试和新鲜证据的交付闭环。使用一个可失效的项目导航索引减少重复发现，使用 Git 可见的单文件 Change 协议追踪重要变更和并行冲突。

## 先遵守这些不变量

1. 先遵守系统、开发者、用户以及目标目录中适用的 `AGENTS.md` 或同等仓库规则。本 Skill 不能降低更高优先级约束。
2. 把仓库当前文件、运行结果和用户确认视为事实。把缓存当导航，不当事实副本；明确区分事实、推断、建议和暂时无法验证，不默认用户或 Agent 的判断正确。
3. 只在任务授权范围内写文件或执行外部动作。只读分析、Review 或答疑不自动授权创建缓存、Change、分支、提交、PR 或部署。
4. 保留用户未提交修改。禁止覆盖式检出、强制推送、破坏性清理和未授权历史重写。
5. 不擅自升级依赖、改公共接口、改变数据语义、扩大范围或进行无关重构。
6. 没有本轮实际执行的完整验证证据，不得宣称完成、修复、通过或可发布。
7. 从可观察目标、硬约束和根因出发选择最小充分机制；只把“最佳实践”当候选证据，不用它覆盖仓库事实或引入无依据复杂度。
8. 只执行仓库中真实存在或本次需求明确建立的边界、Contract、Schema、Owner、Migration 和测试机制；经有界检查未发现时标记不适用并跳过，不补造制度。
9. 对具有明确输入输出、独立业务价值、独立失败边界，或无需启动完整系统即可验证的能力，优先建立独立验证闭环；测试、调试、Probe 和示例入口复用生产实现，并提供与风险匹配的自动化测试、必要的 Fixture/Fake/隔离依赖、明确运行入口和可理解的验证说明。不要机械要求“一模块一个测试文件”或“一功能一个测试文档”。
10. 对 L2/L3 正式 Change，尤其是 Stage / 子 Stage / Roadmap 单元，当前 Change 不是自身需求全集。必须从用户已确认决定和上游正式事实源建立 Requirement Traceability；进入 `ready_for_review` 前重新读取上游完成定义并执行 Completion Audit。CI 全绿不能替代需求完整性审计，也不能依赖用户后续发现漏项。
11. 对存在用户界面、跨前后端、数据库、异步任务或外部 Provider 的 L2/L3 工作，按 [testing-strategy.md](references/testing-strategy.md) 建立 Validation Matrix。Browser Mock 用于广覆盖用户可见状态，Backend/DB Integration 验证服务器规则，Contract 保证机器接口一致，Real Full-stack 只用少量关键 Golden Path 证明真实接线，Real Provider Probe 仅在必要时有界执行；任一层都不能声称证明自己没有实际运行的下游边界。
12. 代码注释不只面向 public/exported 接口。对内部/private/helper 函数，只要包含非显然业务规则、关键不变量、状态转换、算法取舍、兼容原因或重要副作用边界，也应提供简短 docstring 或定点注释，优先解释“为什么/约束是什么”，而不是逐行复述代码；简单自解释 helper 不机械补注释。
13. 实现重要功能时，如果仓库已经有日志/事件基础设施，并且该功能涉及关键生命周期、异步任务、外部 I/O、重试/部分失败、状态转换或后期排障价值，应主动设计并补最小充分的结构化日志。复用现有 logger/event/脱敏机制，使用稳定事件名、正确级别和已有 request/job/run/batch 等关联 ID；禁止打印 Secret/Token/密码/敏感 Raw/PII，禁止 INFO 级逐条高频刷屏，也不能用日志替代数据库业务事实或 Health。

## 按需读取资源

- 首次进入仓库、缓存缺失或缓存可能过期时，读取 [project-discovery.md](references/project-discovery.md)。
- 任务分类为 L2/L3、需要需求追踪或已有 Active Change 时，读取 [change-management.md](references/change-management.md)；新模板带 Completion Gate 时同时遵循 [completion-gate.md](references/completion-gate.md)。
- 开发功能、修 Bug、重构或调查失败时，读取 [development-workflows.md](references/development-workflows.md)。
- 任务涉及用户可见行为、前后端/数据库/异步链路、公共 Contract、Full-stack 或外部 Provider 验证时，读取 [testing-strategy.md](references/testing-strategy.md)，并把适用层写进当前 Change 的 Validation Matrix。
- 任务跨模块、跨前后端、涉及接口/事件/数据，或仓库已有明确 Owner、Contract、Schema、Migration 和契约测试时，读取 [repository-constraints.md](references/repository-constraints.md)。
- 多人、多 Agent、多个分支或多个 Active Change 并行时，读取 [collaboration.md](references/collaboration.md)。
- Review、准备交付或即将表达任何完成结论时，读取 [verification-review.md](references/verification-review.md)。

不要要求用户重复提供能够从仓库、缓存或工具确认的信息。不要读取与本次任务无关的引用文件。

## 统一工作流

### 1. 建立权限和能力边界

先判断请求属于只读分析、诊断、方案、实现、Review、发布还是 Git 操作。确认当前宿主是否具有持久文件系统、终端、Python、Git、测试环境和多 Agent 能力。

- 没有持久文件系统：可以发现项目事实，但不能承诺跨会话缓存或 Git 协作记录。
- 不能执行脚本：按引用文档进行人工发现和 Change 检查，不伪造脚本结果。
- 用户未授权写项目：只在当前会话内建立临时导航，不落盘。

### 2. 定位仓库并先读规则

定位实际仓库根目录。先读取从根到目标文件路径上适用的 `AGENTS.md`、项目说明和规则文件，再做其他项目判断。检查当前分支、工作区状态和未提交修改；如果不是 Git 仓库，明确记录这一事实。

### 3. 复用或建立项目导航

项目缓存路径固定为：

```text
.reliable-vibe-coding/project-context.json
```

对已授权写入的实现任务，在每个独立任务或新工作会话首次规划前运行；同一任务内发生同步、切换分支、rebase、历史改写或候选事实源变化后重新运行。终端、Python 和项目写权限均可用时执行：

```text
python <skill>/scripts/rvc.py discover --root <repo>
```

- 返回 `cache_hit`：本次失效检查没有发现可见的候选事实源变化；复用导航，只读取本次任务直接相关的真实文件。
- 返回 `created` 或 `refreshed`：检查索引中的规则、需求、架构、Contract、Migration、配置、依赖和测试入口。
- 脚本失败：保留错误，按 [project-discovery.md](references/project-discovery.md) 的人工流程继续，不声称缓存有效。

每次运行都检查最新可见变化，但缓存有效时不重复全量理解文档。索引只保存路径、分类、轻量指纹和可直接提取的脚本名称，不复制需求正文。即使缓存有效，也必须读取将要修改的真实需求、实现、调用链和相关测试；`cache_hit` 不代表普通源码没有变化。

### 4. 检查并行状态

如果存在 `changes/active/*/CHANGE.md`，在设计或编码前读取当前 Active Change。终端可用时运行：

```text
python <skill>/scripts/rvc.py status --root <repo> --json
```

只比较仓库实际存在或当前 Change 明确建立的影响路径、模块、Contract、数据、Migration、配置、共享测试资源和依赖关系。发现冲突时指出具体交集，并在共享语义修改前要求排序、重新划分范围或明确共同 Owner。未发现某类约束时跳过该维度；不要为填元数据而发明名称，也不要把无冲突预检描述成锁。

### 5. 分类任务复杂度

使用最低但充分的等级；发现隐藏复杂度时升级，不静默降级。

| 等级 | 适用范围 | Change 记录 | 设计门禁 |
|---|---|---|---|
| L1 | 行为不变的机械修改，或边界明确、影响隔离的极小修复 | 不创建 | 简短内部计划后执行 |
| L2 | 新功能、行为变化、重要 Bug、多文件修改、多人并行或需要追踪的工作 | 一个 `CHANGE.md` | 形成目标、成功标准、范围、非目标和不变项 |
| L3 | 公共 API、Schema、Migration、跨模块 Contract、架构、认证授权、安全、部署、重大依赖或破坏性兼容变化 | 扩展同一个 `CHANGE.md` | 比较 2–3 个方案，用户确认上游决策后实现 |

行数少不等于 L1。公共配置改名、数据库字段变化或权限语义变化至少是 L2，通常是 L3。

### 6. 固化任务契约与上游追溯

在编码前明确：目标、可观察成功标准、范围、非目标、必须保持不变、影响区域、验证方式和 Git 授权。

- L1：可以在工作说明中简要维护。
- L2/L3：创建或认领一个 Active Change。优先运行：

```text
python <skill>/scripts/rvc.py new-change --root <repo> \
  --id CHG-YYYYMMDD-short-name --title <title> --owner <owner> \
  --branch <branch> --level L2 --area <area> --path <path>
```

脚本不可用时，从 [CHANGE.template.md](assets/CHANGE.template.md) 复制一份并填写；不得留下占位内容进入 Ready。

新模板默认 `completion_gate: required`。对这种 Change，编码前先从本轮用户明确决定、正式 Roadmap/Spec/Stage 完成定义和适用规则中独立提取 Requirement Traceability。每条要求只允许 `satisfied / explicitly_deferred / not_applicable / not_satisfied`；当前 Change 不能引用自身作为 Requirement Source，也不能把自己的成功标准当作上游需求全集。

同一 Change 还要按 [testing-strategy.md](references/testing-strategy.md) 建立 Validation Matrix。每个验证层只标记 `required` 或 `not_applicable`：前者写清 Scope 并在完成前补新鲜证据，后者必须有真实依据。不要机械执行全部测试层，也不要为了少跑测试把独立风险标成不适用。

仅询问真正影响接口、数据、兼容性或验收结果的最上游问题，一次一个。能从仓库确认的事实不要反问。

### 7. 制定可验证计划

把任务拆成小而完整的检查点。每一步写清：修改范围、预期行为、依赖和验证命令。只并行执行互不依赖且不修改相同文件、接口或共享状态的步骤。

在实现前确定：

- 复用的现有实现和模式；
- 预计修改文件；
- 需要保持兼容的接口、配置和数据；
- 新增或修改的 public 与内部/private/helper 函数中，哪些非显然规则、关键约束或副作用需要 docstring/定点注释；
- 如果仓库已有日志能力，本次重要业务阶段、外部 I/O、异步状态和失败边界中哪些需要新增/调整日志，以及哪些高频细节应保持 DEBUG 或不记录；
- 最小失败测试或测试例外；
- 目标测试、相关测试、静态检查、构建和必要运行验证；
- 哪些能力具有独立验证价值，以及它们的生产入口、测试入口、Fixture/Fake/隔离依赖、运行方式和成功判据；
- Validation Matrix 中 Browser Mock、Backend/API/PostgreSQL Integration、Contract、Real Full-stack Golden Path、Real Provider Probe 和其他专项验证哪些 `required`、哪些 `not_applicable`，以及各自要证明什么。

对有用户界面的功能，Browser Mock Acceptance 通常负责最宽的用户可见状态空间；对服务器/数据库行为使用 Backend/DB Integration；公共机器接口用 Contract；Real Full-stack 只保留足够证明真实接线的关键 Golden Path；外部 Provider 当前事实只有必要时才做有界 Probe。

先按 [development-workflows.md](references/development-workflows.md) 从目标和硬约束推导候选方案，再选择当前证据下最简单、可逆且可验证的充分方案。存在适用的仓库边界或数据交换约束时，按 [repository-constraints.md](references/repository-constraints.md) 把生产者、消费者、Owner、兼容和验证映射进计划。

### 8. 按任务类型实施

- 新功能、缺陷修复、重构和行为变化：执行 Red → Green → Refactor，并实际观察正确原因的失败和通过。
- Bug、构建失败、性能问题或异常行为：先稳定复现和确认根因，再建立回归测试并做单一修复。
- 用户可见行为：优先用 Browser Mock Acceptance 穷举状态、错误、请求和跨页结果；它不能替代真实 Backend/DB/Worker 验证。
- 后端/数据库/异步规则：优先用真实 Service/API/PostgreSQL/Job Runtime 的 Integration 证明，不把 DOM 测试当数据库证据。
- 公共 Contract：使用仓库已有 Schema/OpenAPI/generated client/兼容检查，避免 Mock 形成第二套接口事实。
- 跨组件关键链：用少量 Real Full-stack Golden Path 证明真实组件组装后能工作；不要为了覆盖全部状态复制大量昂贵 Full-stack。
- 外部 Provider：稳定 Fixture/Fake/Mapper 测试承担普通回归；只有当前真实接口事实需要确认时才执行有界 Provider Probe。
- 独立可验证能力：优先提供不依赖完整系统启动的最小验证入口，使用真实生产入口与可控边界；测试粒度由行为边界、风险、依赖和失败模式决定，而不是目录或文件数量。
- 代码可读性：public/exported 接口与非显然内部/private/helper 逻辑都按 `development-workflows.md` 补必要 docstring/注释；注释解释意图、约束和原因，不翻译语法。
- 重要功能可观测性：仓库已有日志体系且观测点对调试/运维有价值时，按 `development-workflows.md` 增加最小充分日志；没有现有日志基础设施或没有独立排障价值时，不为满足清单新造日志框架。
- 文档、纯配置、生成文件或无法自动测试的环境：说明 TDD 例外，采用解析、内容检查、构建或人工运行等替代验证。
- 多 Agent 实施：仅派发独立工作，给最少充分上下文；主 Agent 复核差异和验证证据。
- 跨边界实现：只在仓库已有相应边界时严格遵守；不得让前后端、生产者/消费者或数据读写方各自猜测共享语义，也不得为不适用的项目强加分层。

详细测试职责遵循 [testing-strategy.md](references/testing-strategy.md)；详细开发流程遵循 [development-workflows.md](references/development-workflows.md)，并始终采用满足需求的最少代码。

### 9. 同步当前事实

代码变更后语义检查 Blueprint、README、API/Contract、Schema、Migration、架构、配置示例、测试说明和运维说明是否受影响。这是交付门禁，不是可选收尾。

- 实施过程中或验证阶段一旦发现实现方案、代码、Contract、Schema、Migration、配置、测试或实际运行行为与正式 Blueprint、README、API/接口文档不一致，不得静默以代码为准或以文档为准。先依据用户已确认决策、适用 `AGENTS.md` 和仓库当前事实确定正确事实源：实现偏离正式约束时修正实现；已确认方案改变系统事实时，在同一任务中同步更新所有受影响的正式文档。
- 正式文档描述系统现在是什么，不写变更流水账；已经失效的说明必须在同一任务中删除或改正，不为未实现功能提前写正式说明。
- Change 记录为什么改变、当时的约束和验证证据，但 `CHANGE.md` 不能代替 Blueprint、README、Contract/API 文档等正式事实源。
- 行为不变且文档确实不受影响时，记录判断依据，不制造无关文档修改。
- 文档与实现尚未同步、受影响文档尚未检查，或只能证明其中一方正确时，不得把任务标记为完成、`ready_for_review`、可合并或可发布。


#### `docs/` 技术文档文件名规范

对仓库 `docs/` 下的 Markdown 技术文档，文件名本身承担稳定的阅读与开发顺序导航，必须遵守：

- 每个 `docs/` 子目录独立编号，不使用跨目录全局连续序号；
- 除 `README.md` 外，技术文档统一使用两位数字加下划线前缀：`01_`、`02_`、`03_`……；`README.md` 永远不加编号；
- 编号按代码/功能开发先后和上游依赖关系排序：基础架构、底层能力和前置事实使用更小编号，依赖它们的后续能力使用更大编号；不要按文件创建时间、字母顺序或个人偏好随意编号；
- `docs/blueprint/` 的核心 Blueprint 固定保持当前 01—08 领域顺序，文件名使用 `01_...md` 至 `08_...md`；普通功能任务不得为了插入新主题静默重排核心 Blueprint；
- 新增技术文档时先确定其职责、所属目录和顺序，再选择编号；确需重命名/重新编号时，同一任务同步当前正式文档、README、AGENTS、代码/配置中的有效路径引用；
- `changes/archive/` 保存历史证据，不因当前文档改名批量改写；`docs/assets/` 等非 Markdown 资源不适用本规则；模块级 `README.md` 继续保持 README 命名。

文件名规范只负责导航和排序，不替代 Blueprint/Appendix/Guide/Roadmap 的职责划分，也不能作为修改文档技术内容的理由。

### 10. Completion Audit、两阶段复核和新鲜验证

对 `completion_gate: required` 的 Change，在进入 `ready_for_review` 前先执行 Completion Audit：

```text
重新读取上游正式事实源
→ 不看当前 Change checklist，独立重建完成定义
→ 比较“上游要求 → Change”，检查 requirement omission
→ 比较“Change → 实现/测试/文档”
→ 执行适用的反向能力审计
→ 复核 Validation Matrix 的层级选择和证据等级
→ 清零 not_satisfied
```

前后端/异步任务的反向审计通常需要检查“后端能力 → 前端入口”和“前端动作 → 后端能力”，以及状态、错误、最终结果和跨页面闭环。没有对应边界时记录不适用依据，不制造机制。

Validation Matrix 复核至少确认：用户可见行为没有只靠后端测试；后端/数据库规则没有只靠 Browser Mock；公共 Contract 有机器一致性证据；关键跨组件链需要真实接线时有足够 Golden Path；Provider Probe 只有必要时才执行并保持有界。任何 `not_applicable` 都必须有真实依据。

机器门禁：

```text
python <skill>/scripts/ready_check.py --root <repo> --require-active-ready
```

脚本只验证机器可判断的结构、状态、Source 路径、占位符和 Audit checkbox；**不能**判断业务需求是否完整，也不能自动证明 Validation Matrix 是否充分，更不能替代语义 Review。

完成 Audit 后，再按 [verification-review.md](references/verification-review.md) 先检查需求符合性，再检查正确性、边界、错误处理、安全、兼容性、可维护性和无关改动。严重或重要问题未解决前不要继续交付。

每个完成结论都执行：

```text
确定证明命令
→ 实际运行完整命令
→ 读取完整输出、退出码和失败数
→ 对照上游完成定义、成功标准、Validation Matrix 和 diff
→ 只陈述证据支持的状态
```

子 Agent 报告、历史日志、局部测试和“代码看起来正确”都不能替代本轮复核。

### 11. 关闭或保留 Change

- 尚未合并或发布：只有 Requirement Traceability、Validation Matrix、Completion Audit、验证和文档同步满足时才能标记 `ready_for_review`，继续保留在 `changes/active/`。
- 已经完成全部成功标准、验证和文档同步，并且集成状态已确认：标记 `done`，再移动到 `changes/archive/YYYY-MM/`。
- 需求在完成前变化：先回到上游事实源更新 Traceability，再更新同一个 Change 的当前确认内容和 Validation Matrix。
- 已归档需求后来再次变化：创建新的 Change，不改写历史。

归档不是成功证据，不能先归档再补验证。不得为了绕过 Ready Check 删除 `completion_gate`。

## 交付报告

最终报告至少包含：

1. 变更摘要与逐文件目的；
2. 上游 Requirement Traceability 与成功标准完成状态；
3. Validation Matrix 与各层实际证据；
4. Completion Audit / 两阶段 Review 结果；
5. 文档同步及依据；
6. 本轮实际执行的命令、退出码和结果；
7. 未验证内容、阻塞和剩余风险；
8. 兼容性、依赖、Migration、部署和回滚影响；
9. Git 分支、提交、PR、合并和清理的实际状态。

不要只回复“已完成”“已修复”或“测试通过”。

## 能力边界

- 项目缓存是可失效导航，不是向量数据库、长期记忆或需求事实副本。
- Change 文件是 Git 协作协议，不是原子锁、租约、看板、通知或在线状态服务。
- Completion Gate 是流程完整性门禁，不是自然语言需求证明器；它不能替代 Agent/Reviewer 从上游事实源做语义完整性审计。
- Validation Matrix 是风险到证据的语义映射，不是固定测试配额，也不是 `ready_check.py` 能自动证明充分性的清单。
- 看不到未提交、未推送、未同步、无权限访问或另一客户端私有的状态。
- 不能强制其他人或 Agent 遵守 Owner、分支或影响范围；仓库 CI 可阻止不满足门禁的 PR 合入。
- 宿主不支持持久文件、脚本或 Git 时，只能执行其实际支持的流程，并明确降级。