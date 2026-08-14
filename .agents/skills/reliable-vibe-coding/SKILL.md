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

## 按需读取资源

- 首次进入仓库、缓存缺失或缓存可能过期时，读取 [project-discovery.md](references/project-discovery.md)。
- 任务分类为 L2/L3、需要需求追踪或已有 Active Change 时，读取 [change-management.md](references/change-management.md)。
- 开发功能、修 Bug、重构或调查失败时，读取 [development-workflows.md](references/development-workflows.md)。
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

### 6. 固化任务契约

在编码前明确：目标、可观察成功标准、范围、非目标、必须保持不变、影响区域、验证方式和 Git 授权。

- L1：可以在工作说明中简要维护。
- L2/L3：创建或认领一个 Active Change。优先运行：

```text
python <skill>/scripts/rvc.py new-change --root <repo> \
  --id CHG-YYYYMMDD-short-name --title <title> --owner <owner> \
  --branch <branch> --level L2 --area <area> --path <path>
```

脚本不可用时，从 [CHANGE.template.md](assets/CHANGE.template.md) 复制一份并填写；不得留下占位内容。

仅询问真正影响接口、数据、兼容性或验收结果的最上游问题，一次一个。能从仓库确认的事实不要反问。

### 7. 制定可验证计划

把任务拆成小而完整的检查点。每一步写清：修改范围、预期行为、依赖和验证命令。只并行执行互不依赖且不修改相同文件、接口或共享状态的步骤。

在实现前确定：

- 复用的现有实现和模式；
- 预计修改文件；
- 需要保持兼容的接口、配置和数据；
- 最小失败测试或测试例外；
- 目标测试、相关测试、静态检查、构建和必要运行验证；
- 哪些能力具有独立验证价值，以及它们的生产入口、测试入口、Fixture/Fake/隔离依赖、运行方式和成功判据。

先按 [development-workflows.md](references/development-workflows.md) 从目标和硬约束推导候选方案，再选择当前证据下最简单、可逆且可验证的充分方案。存在适用的仓库边界或数据交换约束时，按 [repository-constraints.md](references/repository-constraints.md) 把生产者、消费者、Owner、兼容和验证映射进计划。

### 8. 按任务类型实施

- 新功能、缺陷修复、重构和行为变化：执行 Red → Green → Refactor，并实际观察正确原因的失败和通过。
- Bug、构建失败、性能问题或异常行为：先稳定复现和确认根因，再建立回归测试并做单一修复。
- 独立可验证能力：优先提供不依赖完整系统启动的最小验证入口，使用真实生产入口与可控边界；测试粒度由行为边界、风险、依赖和失败模式决定，而不是目录或文件数量。
- 文档、纯配置、生成文件或无法自动测试的环境：说明 TDD 例外，采用解析、内容检查、构建或人工运行等替代验证。
- 多 Agent 实施：仅派发独立工作，给最少充分上下文；主 Agent 复核差异和验证证据。
- 跨边界实现：只在仓库已有相应边界时严格遵守；不得让前后端、生产者/消费者或数据读写方各自猜测共享语义，也不得为不适用的项目强加分层。

详细流程遵循 [development-workflows.md](references/development-workflows.md)，并始终采用满足需求的最少代码。

### 9. 同步当前事实

代码变更后语义检查 README、API/Contract、Schema、Migration、架构、配置示例和运维说明是否受影响。

- 正式文档描述系统现在是什么，不写变更流水账。
- Change 记录为什么改变、当时的约束和验证证据。
- 行为不变且文档不受影响时，记录判断依据，不制造无关文档修改。

### 10. 两阶段复核和新鲜验证

先逐项检查需求符合性，再检查正确性、边界、错误处理、安全、兼容性、可维护性和无关改动。严重或重要问题未解决前不要继续交付。

每个完成结论都执行：

```text
确定证明命令
→ 实际运行完整命令
→ 读取完整输出、退出码和失败数
→ 对照成功标准和 diff
→ 只陈述证据支持的状态
```

遵循 [verification-review.md](references/verification-review.md)。子 Agent 报告、历史日志、局部测试和“代码看起来正确”都不能替代本轮复核。

### 11. 关闭或保留 Change

- 尚未合并或发布：通常标记 `ready_for_review`，保留在 `changes/active/`。
- 已经完成全部成功标准、验证和文档同步，并且集成状态已确认：标记 `done`，再移动到 `changes/archive/YYYY-MM/`。
- 需求在完成前变化：更新同一个 Change 的当前确认内容。
- 已归档需求后来再次变化：创建新的 Change，不改写历史。

归档不是成功证据，不能先归档再补验证。

## 交付报告

最终报告至少包含：

1. 变更摘要与逐文件目的；
2. 成功标准完成状态；
3. 文档同步及依据；
4. 本轮实际执行的命令、退出码和结果；
5. 未验证内容、阻塞和剩余风险；
6. 兼容性、依赖、Migration、部署和回滚影响；
7. Git 分支、提交、PR、合并和清理的实际状态。

不要只回复“已完成”“已修复”或“测试通过”。

## 能力边界

- 项目缓存是可失效导航，不是向量数据库、长期记忆或需求事实副本。
- Change 文件是 Git 协作协议，不是原子锁、租约、看板、通知或在线状态服务。
- 看不到未提交、未推送、未同步、无权限访问或另一客户端私有的状态。
- 不能强制其他人或 Agent 遵守 Owner、分支或影响范围。
- 宿主不支持持久文件、脚本或 Git 时，只能执行其实际支持的流程，并明确降级。
