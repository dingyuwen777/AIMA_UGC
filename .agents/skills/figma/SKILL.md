---
name: figma
description: 面向任意项目的 Figma 产品原型、设计系统、页面可用性和 Design-to-Code 正式开发基线的事实驱动审查、修复与实施交接工作流。支持从“全面检查这个 Figma”“检查并修复”“按这个 Figma 替换现有页面”等自然语言自动路由到 review-only、review-and-fix、baseline-ready 或 baseline-ready → 开发 handoff。先识别项目形态和目标用户，再按实际边界读取需求、设计系统、代码、Contract/API/SDK/数据源/运行状态等事实；审查页面尺寸、布局、间距、Canvas 组织、图片与标注、公共组件与可复用业务逻辑、Prototype、状态覆盖、动态数据来源、用户习惯和实现可行性。禁止把 Figma 示例当生产事实、把截图当结构证据、机械暴露内部实现、复制可复用业务规则，或由设计稿创造系统不存在的能力。Use for Figma prototype review, design audit, design-system review, layout/usability QA, prototype QA, canvas readability, annotation hygiene, real-system capability alignment, Design-to-Code readiness, and handing a READY design to the target project's 开发 workflow for implementation across web, mobile, desktop, dashboards, admin tools, static sites, and other UI projects. 向用户说明计划或进度时保留用户明确提供的项目术语、计划和决定，并只描述当前项目工程动作；治理能力或规则的内部名称不写成用户任务步骤或分工。
---



# Figma

这个 规则 不是“看起来好不好看”的主观点评器。

它要判断：

```text
这个页面适合目标用户吗？
页面尺寸、布局、间距、图片和标注是否合理？
整个 Canvas 的画板、Section、Annotation、状态稿和历史稿是否清晰可读？
用户能否按自然顺序完成任务？
设计中的字段、按钮、状态和选项是否有真实系统能力支持？
动态数据来自哪里，是否明确标注？
公共视觉组件是否真正复用？
可复用业务逻辑是否有唯一 Owner？
现有 Design System / Page Template / Feature/Page Owner 是否保持唯一 Owner，Formal Screen/State 的公共稳定语义是否消费它们、单页特例是否留在 Page-private？
Prototype Interaction Completeness / 无代码验收是否通过：所有视觉上可操作且 enabled 的控件有有效 Reaction，关键流程无需前端代码即可走通？
实现方能否无歧义地把设计接到当前项目？
```

`能力=Figma` 只表示宿主具备 Figma 能力，**不能单独触发本 规则**；必须存在真实 Figma 专业意图。通用 `执行模式=审查` 也不能把 Figma 设计审查机械叠加成 Code Review。

核心流程按模式收敛：

```text
识别项目形态和目标用户
→ 明确 Review Target 与授权模式
→ 恢复当前需求 / 设计 / 系统事实
→ 审查页面尺寸、布局与真实使用习惯
→ 审查视觉层级、图片、标注、表格、表单
→ 审查 Canvas / Section / Annotation 的组织与间距
→ 审查公共组件 / Page Template / Feature/Page Owner 和业务逻辑复用
→ 审查系统能力、动态数据和状态来源
→ 审查 Prototype Variable / Reaction / Flow / Interaction Completeness
→ Figma 写操作后执行 Canvas-level Review
→ Fresh Screenshot / Machine Audit（模式要求时）
→ Design Context / 实现视角复核（适用时）
→ Findings
→ review-and-fix 时修最小 Owner
→ re-review
→ 只有 baseline-ready 才输出 READY / READY_WITH_NOTES / NOT_READY
```

详细方法位于 `当前场景所需完整约束/`。命中对应场景时必须读取相关 完整约束；不能只读本文件后凭经验完成审查。

Owner 层级、Prototype 交互完整性与 READY 判定分别由 当前场景所需完整约束、04、05 唯一维护。

---

# 1. 通用适用性

本 规则 不绑定某个项目、某个页面或某一种技术栈。

适用于：

```text
Web 应用
移动端 App
桌面端 App
内部管理系统
数据看板
内容/媒体产品
交易/电商产品
表单/工作流系统
营销/品牌站
静态站
设计系统 / 组件库
Design-only 原型
```

开始前先读取 当前场景所需完整约束，只加载当前项目真实存在的边界。

硬规则：

```text
规则 提到了 API
≠ 每个项目都必须有 API

规则 提到了 Route
≠ Mobile/Desktop 必须套 Web Route

规则 提到了数据库
≠ 客户端应直接访问数据库
```

---

# 2. 上位规则与宿主工具

## 2.1 有仓库时

顺序：

```text
适用 AGENTS / CONTRIBUTING / 项目规则
→ 同仓 开发 规则（存在时）
→ 产品 / 设计 / 前端 / 平台 Guide
→ 当前任务直接相关的 Spec / Contract / Code / Test
→ 本 规则
```

本 规则 不复制研发、Git、CI、文档或代码 Review 规则。

发现生产实现问题：

```text
code_issue_detected
→ 返回项目 开发 工作流
→ 实现修复并验证
→ Figma targeted re-review
```

需要同步长期文档时，路由到项目现有 Docs 工作流。

## 2.2 宿主 Figma 工具优先

本 规则 定义审查方法，不替代当前宿主的 Figma MCP、插件、写入 API、权限和前置技能。

```text
先遵守宿主工具规则
→ 再按本 规则 决定读什么、查什么、怎样判定 Ready
```

如果环境只有读权限，`review-and-fix` 的**写动作**必须明确阻塞，不能假装已经改过设计；但只要读取能力可用，仍应完成不依赖写权限的 review-only 审查、Findings 和证据边界，不把写权限缺口扩大成整个调查停止。

详见 当前场景所需完整约束。

---

# 3. 三种工作模式

## `review-only`

在没有更具体的正式开发基线验收意图时，用于普通设计审查；无论是否存在对应代码仓库，**普通“全面检查 / 审查 / 找问题”默认 `review-only`**。有仓库时照样读取必要实现/Contract/状态事实来判断设计是否合理，但不因为“仓库存在”自动升级成正式基线验收。

允许读取 Figma、仓库/需求事实、截图、Metadata、Prototype、Design Context，并输出 Findings。

不自动获得：

- 修改 Figma；
- 修改代码；
- 修改文档；
- commit / PR / merge / release 权限。

“只检查、不修改”首先是写权限限制；如果用户另外明确要求“是否可交付开发 / 正式基线 / READY / 对照代码全面验收”等 baseline-ready 目标，仍执行只读的正式基线验收。

## `review-and-fix`

仅在明确授权修改 Figma 时使用。

只要本轮涉及页面、Canvas、Frame、Section、Annotation 或状态稿的视觉修改，修改前必须读取 当前场景所需完整约束，并在每轮 Figma 写操作后执行其中的 Canvas-level Review。

任何 Figma 写入还必须先执行 **Owner-first Figma Mutation**：已有 Shared/Feature/Page Owner 时优先复用或修改真实 Owner，不通过 Detach、复制或页面级重画制造第二套公共组件。公共语义与局部业务变化的详细分支由 当前场景所需完整约束 维护。

```text
先确认 Finding 和根因
→ 找最小真实 Owner
→ 修改 Owner
→ 验证所有受影响消费者
→ Canvas-level Review（当前 Frame + Section + 相邻画板 + Annotation + zoom-out）
→ Fresh Screenshot
→ Prototype / Machine Audit
→ Design Context re-review（适用时）
```

这里的“确认 Finding 和根因”表示先自行从 Figma、系统事实和工具证据核验；普通局部设计修复不要求用户逐项批准。只有修复会改变业务语义、真实系统能力、公共 Contract 或其他上游决策时才提请 Owner 决策。

禁止逐页打补丁掩盖公共根因，也禁止只把当前 Frame 改正确却留下由本次修改造成的相邻画板、注释或说明拥挤问题。

## `baseline-ready`

用于判断 Figma 是否可作为实现方的正式开发基线。

最终只能是：

```text
READY
READY_WITH_NOTES
NOT_READY
```

必要验证没有实际执行时不得给 `READY`。

## 3.1 高频用户意图自动路由

用户不需要记住 `review-only`、`review-and-fix`、`baseline-ready` 这些模式名。先尊重用户显式模式和任务目标，再独立判断写入权限；没有显式模式时，再按自然语言目标自动路由。

优先级：

```text
用户显式指定模式 / 正式验收目标
→ 自然语言任务意图
→ 独立核验用户已经授予的 Figma / 代码 / Git 权限
→ 无法确认写权限时保持只读，不擅自写入
```

“核验授权”不是重新向用户索要已经明确给出的同一批准；当前请求已经明确授予的范围直接沿用，宿主/项目权限另行事实核验。

### A. “全面检查 / 审查 / 看看这个 Figma 有没有问题”

常见表达：

```text
全面检查这个 Figma 页面
看看是否美观、好用、符合用户习惯
看看是否符合当前仓库代码
找出这个页面的问题和改进点
```

这类普通审查无论是否存在目标仓库，都按：

```text
→ 默认 `review-only`
→ 有仓库时恢复当前系统/Contract/实现的最少充分事实
→ 审查设计、Prototype、设计系统、可用性和与真实系统的一致性
→ 输出 Findings、证据与未验证边界
→ 不为了“更全面”自动执行 baseline-ready 的完整开发交付门禁
```

没有实现仓库、只是 Design-only 原型时，当前尚不存在的实现边界标记 `implementation_required`，不伪造 API / Route / 数据库等系统事实。

### A2. “是否可交付开发 / 正式基线 / READY / 对照代码全面验收”

当用户明确询问：

```text
这个页面能不能直接交给开发
是否达到正式开发基线
这个 Figma 是否 READY
对照当前仓库全面验收这个 Figma
```

这类目标明确要求实现前完成正式基线判断：

```text
→ 默认 `baseline-ready`
→ 恢复当前仓库/Contract/实现事实（存在时）
→ 执行视觉 / 可用性 / Prototype / 系统能力 / Annotation / Design Context 等全部适用门禁
→ 输出 Findings + READY / READY_WITH_NOTES / NOT_READY
```

用户说“只检查、不修改”只表示不获得 Figma 写权限，不会把已经明确的 baseline-ready 验收降级成普通 review-only。

### B. “全面检查并修复 / 帮我改好 / 有问题直接改”

这些措辞本身可以视为本轮明确的 Figma 写授权：

```text
→ review-and-fix
→ 先核验 Finding / 根因
→ 修改最小真实 Owner
→ 验证公共消费者
→ Canvas-level Review
→ Fresh Screenshot + Prototype / Machine Audit + Design Context（适用时）
→ re-review
```

**review-and-fix 不因为“已经修完”自动升级成 baseline-ready。** 如果用户同时要求正式开发基线、READY 或 Design-to-Code，再在修复后执行 `baseline-ready`；否则在当前 Review Target 的 Findings 与写后验证闭环后结束。

如果宿主没有写权限，写入部分明确阻塞；不能把“给修改建议”描述成已经修复，但仍完成可以执行的只读审查。

### C. “按这个 Figma 替换 / 实现当前页面”

常见表达：

```text
按这个 Figma 替换仓库当前对应页面
把这个原型实现到现有代码
用这个设计重做当前页面
把这个 Figma 转成当前项目真正可用的页面
```

这不是第四种 Figma 模式，而是组合流程：

```text
恢复目标项目当前事实
→ 对正式 Figma 目标执行 baseline-ready
→ NOT_READY：
 - 已明确授权修改 Figma → review-and-fix 后重新 baseline-ready
 - 未授权修改 Figma → 报告基线阻塞，不把已知设计缺陷写入生产代码；其他不依赖该缺陷的只读事实仍可继续
→ READY / 可实施的 READY_WITH_NOTES
→ 如果已有对应页面：先执行 Existing Implementation Delta Gate
→ handoff 到目标项目 开发 工作流
→ 开发 负责最小增量实现 / 测试 / Review / CI / Git / 交付
→ 实现完成后执行 Implementation ↔ Figma Conformance
→ 正式长期 Drift + 有 Figma 写权限时执行授权 back-sync
→ 强制输出 Figma Sync & Human Review
```

“替换 / 实现 / 重做现有页面”本身表示用户要求修改该目标实现；但 commit、PR、merge、release 等 Git/交付权限仍按目标项目 开发 工作流和用户明确授权判断，不能从“实现页面”自动扩大。

进入 开发 handoff 后，本 规则 只提供已经确认的设计事实、动态数据来源、Shared/Feature/Page Owner、Prototype 和状态规格；**不得复制或替代 开发 规则 的 Change、TDD、验证、CI、Git、PR、Release 规则。**

详细 handoff、已有实现差异更新、back-sync 和人工复核输出见 当前场景所需完整约束。

### D. 短提示词应当足够

安装本 规则 后，以下输入应当可以直接工作：

```text
全面检查这个 Figma：<link>
→ review-only

全面检查并修好这个 Figma：<link>
→ review-and-fix

对照当前仓库全面验收这个 Figma：<link>
→ baseline-ready

按这个 Figma 替换当前对应页面：<link>
→ baseline-ready → 开发 handoff
```

这些短句只负责选择已有流程，**不在本节复制页面尺寸、组件复用、Prototype、动态数据、真实系统映射等详细规则**；详细规则继续由后续章节和 当前场景所需完整约束 单一维护。

---

---

# 4. 专项详细规则按需加载

从本节开始，Core **不再复制**已经由 当前场景所需完整约束 唯一拥有的详细检查表。这里保留的是不可延迟的加载责任：命中对应场景时，必须在执行该动作前读取完整 完整约束；不能用本 Core 的概括、历史记忆或模型经验替代 完整约束 正文。

## 4.1 所有正式 Figma 任务

至少读取：

- 当前场景所需完整约束：项目形态、平台边界与通用适用性；
- 当前场景所需完整约束：Review Target、设计/系统/运行事实源、证据等级、冲突分类和 review-and-fix 最小 Owner。

普通 review-only 只加载当前 Review Target 实际需要的后续专项 完整约束；不得为了“更全面”机械预加载 baseline-ready 的所有门禁。

## 4.2 业务能力、动态数据、Annotation、状态来源

只要页面包含真实业务字段、系统动作、动态选项、时间/调度、异步状态、数据库/持久化来源、权限/错误、示例数据或 Annotation 与机器事实映射，必须读取：

- 当前场景所需完整约束

该 完整约束 是 STATIC_UI / USER_INPUT / SYSTEM_DYNAMIC / RUNTIME_STATE / DESIGN_EXAMPLE / SYSTEM_FIXED、Capability/Contract 优先级、禁止虚构接口、时间/调度/异步/持久化/权限/示例数据等详细规则的唯一 Owner。

## 4.3 Design System、公共组件和业务逻辑 Owner

只要涉及公共组件、Component Property、Variant、Design Token、Auto Layout、Feature/Page/Shared Owner、公共业务逻辑复用，或本轮会修改 Figma，必须读取：

- 当前场景所需完整约束

所有写操作继续执行 Owner-first Figma Mutation；不得 Detach/复制/页面级重画制造第二 Owner。详细判断与例外只以该 完整约束 完整正文为准。

## 4.4 Prototype、状态和无代码验收

只要当前目标存在 Prototype、Flow、Reaction、Variable、Dropdown/Menu、Toast/Popover/Tooltip、Modal/Drawer/Sheet、交互状态，或用户要求可演示/无代码验收，必须读取：

- 当前场景所需完整约束

Prototype Interaction Completeness、Interaction Coverage Audit、Machine Audit、隐藏变量赋值、浮层交互和修复后验证全部由该 完整约束 唯一维护。

## 4.5 baseline-ready 与 Design-to-Code

只要目标是“是否可交付开发 / READY / 正式基线 / 按 Figma 实现或替换代码”，必须读取：

- 当前场景所需完整约束

它唯一维护 UI → Real-System Preflight、Annotation Development Readiness、NOT_READY / READY_WITH_NOTES / READY、Baseline Ready Checklist、开发 衔接、Existing Implementation Delta、Implementation ↔ Figma Conformance、Bidirectional Design Sync 与 Figma Sync & Human Review。

**NOT_READY 时禁止把已知设计缺陷写入生产实现。** 只有 READY / 可实施的 READY_WITH_NOTES 才能进入 开发 handoff；Ready 不等于代码、测试、PR 或 Release 已完成。

## 4.6 Findings、优先级与正式输出

任何正式审查都必须读取：

- 当前场景所需完整约束

P0/P1/P2、Finding 证据、修复 Owner、review-and-fix re-review 和 Ready 输出以该 完整约束 为准。没有足够证据的内容只能写风险/未验证项，不能伪装成确定 Finding。

## 4.7 页面布局、Canvas、Annotation 可读性与写后复核

只要任务涉及页面/Canvas 的视觉审查、创建、修改、整理、状态稿、Annotation、baseline-ready，或任意 Figma 写操作，必须读取：

- 当前场景所需完整约束

页面尺寸/响应式、App Shell、间距/对齐、图片/图表/表格/表单、浮层、真实使用习惯、Canvas 组织、Annotation 安全距离、Fresh Screenshot、Canvas-level Review、Geometry Collision Audit 和页面布局 Ready 门禁全部保留在该 完整约束。

任何 Figma 写操作完成前都必须按该 完整约束 检查当前 Frame + 所属 Section + 直接相邻画板/Annotation + zoom-out 整体视图；工具支持几何事实时执行 Geometry Collision Audit。

---

# 5. 模式到 完整约束 的最小充分组合

| 模式 / 真实边界 | 必需 完整约束 |
| --- | --- |
| review-only 基础 | 00 + 01 + 06；再按页面真实边界追加 02/03/04/07 |
| review-and-fix | 00 + 01 + 03 + 06 + 07；涉及业务/Prototype 时追加 02/04 |
| baseline-ready | 00 + 01 + 02 + 03 + 04 + 05 + 07；Finding 输出同时使用 06 |
| Figma → Code 初始 | 00 + 01 + 02 + 03 + 05；05 要求先进入 baseline-ready，随后按新任务事实追加 baseline-ready 专项规则；READY / READY_WITH_NOTES 后再 开发 handoff |
| Design-only、无实现仓库 | 仍按真实设计边界审查；不存在的系统事实标记 implementation_required，不虚构 API/数据库/Route |

完整约束 的 canonical routing metadata 继续负责 本地项目环境 的 required Context fixed-point；本表只提供 源码环境 人类可读入口，不是第二份静态分发白名单。

---

# 6. 完成与停止边界

- review-only：输出当前 Review Target 的 Findings、证据和未验证边界后停止；不自动写 Figma，不自动升级 baseline-ready。
- review-and-fix：修最小真实 Owner，验证受影响消费者，并完成 Canvas-level Review / Fresh Screenshot / Prototype 或 Machine Audit / Design Context（适用时）与 re-review；不自动获得代码/Git 权限。
- baseline-ready：必要门禁全部实际完成后，只能输出 READY / READY_WITH_NOTES / NOT_READY。
- Figma → Code：NOT_READY 阻止依赖缺陷的生产实现；READY / 可实施 READY_WITH_NOTES 才进入 开发 handoff。开发 继续独立承担 Change、TDD、Validation、Review、CI、Git、PR、Release。
- 缺少 Figma 读取能力、required Context 或必要验证能力时，只阻塞依赖该事实的 Finding/Ready 强结论；其他可验证审查继续。
- 设计与当前系统冲突时，不让设计迎合已知代码 Bug，也不让代码实现设计虚构能力；按 01/02/05 的冲突分类和 衔接 回到真实 Owner。

本 Core 的瘦身只删除与 当前场景所需完整约束 的重复正文；所有详细规则、例外、失败处理、验证责任和完成判据仍由上述 canonical 当前场景所需完整约束 完整承担。

## 面向用户的项目表达

向用户说明当前任务计划、进展、分工或结果时，用户明确提供的项目术语、计划和决定照常保留，并直接描述当前项目事实、工程动作、验证与真实状态。治理能力或规则的内部名称只服务执行，不把这些名称转写成用户可见的任务步骤、分工或计划；需要说明过程时，使用对应的项目工程动作表达。
