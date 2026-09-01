---
name: figma
description: 面向任意项目的 Figma 产品原型、设计系统、页面可用性和 Design-to-Code 正式开发基线的事实驱动审查、修复与实施交接工作流。支持从“全面检查这个 Figma”“检查并修复”“按这个 Figma 替换现有页面”等自然语言自动路由到 review-only、review-and-fix、baseline-ready 或 baseline-ready → Coding handoff。先识别项目形态和目标用户，再按实际边界读取需求、设计系统、代码、Contract/API/SDK/数据源/运行状态等事实；审查页面尺寸、布局、间距、Canvas 组织、图片与标注、公共组件与可复用业务逻辑、Prototype、状态覆盖、动态数据来源、用户习惯和实现可行性。禁止把 Figma 示例当生产事实、把截图当结构证据、机械暴露内部实现、复制可复用业务规则，或由设计稿创造系统不存在的能力。Use for Figma prototype review, design audit, design-system review, layout/usability QA, prototype QA, canvas readability, annotation hygiene, real-system capability alignment, Design-to-Code readiness, and handing a READY design to the target project's coding workflow for implementation across web, mobile, desktop, dashboards, admin tools, static sites, and other UI projects.
---

<!-- agent-routing:v1
{"协议":"Agent Skills Skill路由/v1","Skill":"figma","触发":{"任一":[{"包含":{"维度":"能力","取值":["Figma"]}},{"包含":{"维度":"意图","取值":["Figma review-only","Figma review-and-fix","Figma baseline-ready","设计转代码"]}}]}}
-->

# Figma

这个 Skill 不是“看起来好不好看”的主观点评器。

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
Prototype 点击之后是否仍然正确？
实现方能否无歧义地把设计接到当前项目？
```

核心流程：

```text
识别项目形态和目标用户
→ 明确 Review Target 与授权模式
→ 恢复当前需求 / 设计 / 系统事实
→ 审查页面尺寸、布局与真实使用习惯
→ 审查视觉层级、图片、标注、表格、表单
→ 审查 Canvas / Section / Annotation 的组织与间距
→ 审查公共组件和业务逻辑复用
→ 审查系统能力、动态数据和状态来源
→ 审查 Prototype Variable / Reaction / Flow
→ Figma 写操作后执行 Canvas-level Review
→ Fresh Screenshot / Machine Audit
→ Design Context / 实现视角复核（适用时）
→ Findings
→ review-and-fix 时修最小 Owner
→ re-review
→ READY / READY_WITH_NOTES / NOT_READY
```

详细方法位于 `当前场景所需完整约束/`。命中对应场景时必须读取相关 完整约束；不能只读本文件后凭经验完成审查。

---

# 1. 通用适用性

本 Skill 不绑定某个项目、某个页面或某一种技术栈。

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
Skill 提到了 API
≠ 每个项目都必须有 API

Skill 提到了 Route
≠ Mobile/Desktop 必须套 Web Route

Skill 提到了数据库
≠ 客户端应直接访问数据库
```

---

# 2. 上位规则与宿主工具

## 2.1 有仓库时

顺序：

```text
适用 AGENTS / CONTRIBUTING / 项目规则
→ 同仓 Coding Skill（存在时）
→ 产品 / 设计 / 前端 / 平台 Guide
→ 当前任务直接相关的 Spec / Contract / Code / Test
→ 本 Skill
```

本 Skill 不复制研发、Git、CI、文档或代码 Review 规则。

发现生产实现问题：

```text
code_issue_detected
→ 返回项目 Coding 工作流
→ 实现修复并验证
→ Figma targeted re-review
```

需要同步长期文档时，路由到项目现有 Docs 工作流。

## 2.2 宿主 Figma 工具优先

本 Skill 定义审查方法，不替代当前宿主的 Figma MCP、插件、写入 API、权限和前置技能。

```text
先遵守宿主工具规则
→ 再按本 Skill 决定读什么、查什么、怎样判定 Ready
```

如果环境只有读权限，`review-and-fix` 必须明确阻塞，不能假装已经改过设计。

详见 当前场景所需完整约束。

---

# 3. 三种工作模式

## `review-only`

在没有更具体的正式开发基线验收意图时，用于普通设计审查；Design-only 且没有目标实现事实时通常默认此模式。

允许读取 Figma、仓库/需求事实、截图、Metadata、Prototype、Design Context，并输出 Findings。

不自动获得：

- 修改 Figma；
- 修改代码；
- 修改文档；
- commit / PR / merge / release 权限。

“只检查、不修改”首先是写权限限制，不自动把用户已经明确要求的 `baseline-ready` 验收降级成 `review-only`。

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
→ 独立判断用户授予的 Figma / 代码 / Git 权限
→ 无法确认写权限时保持只读，不擅自写入
```

### A. “全面检查 / 审查 / 看看这个 Figma 有没有问题”

常见表达：

```text
全面检查这个 Figma 页面
看看是否美观、好用、符合用户习惯
看看是否符合当前仓库代码
这个页面能不能直接交给开发
```

如果同时存在目标仓库或当前实现，需要判断设计与真实系统是否一致：

```text
→ 默认 baseline-ready
→ 恢复当前仓库事实
→ 执行视觉 / 可用性 / Prototype / 系统能力 / Design Context 全量适用门禁
→ 输出 Findings + READY / READY_WITH_NOTES / NOT_READY
```

如果没有实现仓库、只是 Design-only 原型：

```text
→ 默认 review-only
→ 审查设计、Prototype、设计系统和可实施性
→ 当前尚不存在的实现边界标记 implementation_required
→ 不伪造 API / Route / 数据库等系统事实
```

用户说“只检查、不修改”时，只表示本轮不获得 Figma 写权限；如果任务本身是在问“是否可作为正式开发基线”，仍执行只读的 `baseline-ready`。

### B. “全面检查并修复 / 帮我改好 / 有问题直接改”

这些措辞本身可以视为本轮明确的 Figma 写授权：

```text
→ review-and-fix
→ 先确认 Finding / 根因
→ 修改最小真实 Owner
→ 验证公共消费者
→ Canvas-level Review
→ Fresh Screenshot + Prototype / Machine Audit + Design Context（适用时）
→ 再执行 baseline-ready 判定
```

如果宿主没有写权限，必须明确阻塞；不能把“给修改建议”描述成已经修复。

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
   - 未授权修改 Figma → 报告阻塞，不把已知设计缺陷写入生产代码
→ READY / 可实施的 READY_WITH_NOTES
→ 如果已有对应页面：先执行 Existing Implementation Delta Gate
→ handoff 到目标项目 Coding 工作流
→ Coding 负责最小增量实现 / 测试 / Review / CI / Git / 交付
→ 实现完成后执行 Implementation ↔ Figma Conformance
→ 正式长期 Drift + 有 Figma 写权限时执行授权 back-sync
→ 强制输出 Figma Sync & Human Review
```

“替换 / 实现 / 重做现有页面”本身表示用户要求修改该目标实现；但 commit、PR、merge、release 等 Git/交付权限仍按目标项目 Coding 工作流和用户明确授权判断，不能从“实现页面”自动扩大。

进入 Coding handoff 后，本 Skill 只提供已经确认的设计事实、动态数据来源、Shared/Feature/Page Owner、Prototype 和状态规格；**不得复制或替代 Coding Skill 的 Change、TDD、验证、CI、Git、PR、Release 规则。**

详细 handoff、已有实现差异更新、back-sync 和人工复核输出见 当前场景所需完整约束。

### D. 短提示词应当足够

安装本 Skill 后，以下输入应当可以直接工作：

```text
全面检查这个 Figma：<link>
全面检查并修好这个 Figma：<link>
对照当前仓库全面验收这个 Figma：<link>
按这个 Figma 替换当前对应页面：<link>
```

这些短句只负责选择已有流程，**不在本节复制页面尺寸、组件复用、Prototype、动态数据、真实系统映射等详细规则**；详细规则继续由后续章节和 当前场景所需完整约束 单一维护。

---

# 4. Review Target

每次正式审查至少确定：

```text
Figma File
Page / Section
目标 Frame / Node
Prototype Starting Point
项目形态
目标用户 / 核心任务
对应实现入口（有代码时）
模式与授权范围
```

如果同一文件中同时有：

```text
正式基线
历史参考
备份
废弃归档
```

必须先确定当前唯一事实源。

---

# 5. 事实分类与真实系统映射

任何业务相关 UI 内容至少判断属于：

```text
STATIC_UI
USER_INPUT
SYSTEM_DYNAMIC
RUNTIME_STATE
DESIGN_EXAMPLE
SYSTEM_FIXED
```

动态事实可能来自：

```text
API / RPC / SDK
CMS
本地数据库 / Local Store
设备能力
文件系统
后台任务
第三方服务
服务端数据库（经正式 Service/API 消费）
```

关键字段如果不知道来源、默认值、错误行为或真实系统支持方式，不能宣布基线闭环。

详细规则见 当前场景所需完整约束。

## 5.1 设计不能创造不存在的能力

一个 Select 里出现选项，不代表系统支持。

一个按钮被画出来，不代表真实 Action 存在。

一个“每 N 小时”的文案，不代表当前调度器能严格实现该语义。

规则：

```text
真实系统支持
→ 可以进入正式设计

系统不支持但已批准未来实现
→ 明确 Future / Implementation Required

既没有实现也没有批准决定
→ 不作为正式可用能力
```

Design-to-Code 的机器边界同样服从真实系统事实：**不得由 Figma / Design Context / Annotation 创建生产 Contract / API**；设计中的接口名、字段、枚举和示例机器值只能作为调查线索。冲突、缺失能力和真实机器边界的详细规则由 当前场景所需完整约束 维护。

## 5.2 数据库数据也要通过正式系统边界

如果设计展示的数据最终来自数据库：

```text
Database
→ Repository / Service / API / SDK
→ Client State
→ Page
```

实际链路按项目架构确定。

禁止把“数据来自数据库”理解成客户端直接查询数据库。

---

# 6. 页面尺寸、布局、美观和真实可用性

凡是任务涉及 Figma 页面/Canvas 的视觉审查、创建、修改、整理、状态稿维护或 `baseline-ready`，都必须读取 当前场景所需完整约束。这既是页面布局规则，也是 Canvas/Section/Annotation 可读性的唯一详细设计事实源。

`baseline-ready` 时这是硬审查域；`review-and-fix` 时也是所有视觉写操作的写后复核规则。

至少检查：

```text
目标设备 / 浏览器与 Frame 基准
响应式 / 安全区 / App Shell
Page Header / Content 左右边界
Section 对齐和间距节奏
Canvas / Section / 相邻画板的整体组织
Annotation / 开发说明与正式 Frame 的安全距离和归属
正式稿 / 状态稿 / 历史稿 / 废弃稿分区
图片比例 / 裁切 / 清晰度
图片、文字、按钮、Badge、Annotation 是否重叠
图表 Label / Legend / Tooltip 是否遮挡
真实长文本下表格列宽
表单字段依赖和用户操作顺序
Toast / Dropdown / Tooltip / Popover 安全区
Modal / Drawer 滚动
关键动作在目标 Viewport 是否可访问
zoom-out 整体视图是否仍然清晰可读
```

设计基准尺寸不是生产固定宽高。

如果 Prototype 需要用户每次手动缩放才能正常看全，应检查 Frame、Scaling、Viewport 和滚动设计，而不是把手动缩放当产品方案。

---

# 7. 公共组件与可复用业务逻辑

必须读取 当前场景所需完整约束。

## 7.1 视觉公共组件

真正跨页面稳定复用的基础 UI 应有唯一 Owner，例如：

```text
App Shell
Navigation
Page Header
Button
Input
Select
Checkbox
Switch
Tabs
Feedback
Empty State
Modal / Drawer Shell
```

具体名称以当前 Design System 为准。

Figma 修改遵循 **Owner-first Figma Mutation**：已有公共组件必须优先复用真实 Instance；公共语义变化改公共 Owner 并复核消费者，局部业务变化留在 Feature/Page，不用 Detach 或复制重画制造第二 Owner。详细门禁由 当前场景所需完整约束 维护。

## 7.2 业务逻辑也要复用

如果多个页面真正使用同一业务语义：

```text
同一资格判断
同一状态映射
同一动态字段生成规则
同一表单校验
同一默认值算法
同一数据转换
```

不能让实现方在多个页面复制多套逻辑。

应根据复用范围落到唯一 Owner：

```text
Feature Public Layer
Shared Domain / Shared UI
Service / Capability / SDK
```

但不要把业务规则塞进 Button/Input 等无业务基础组件。

## 7.3 不追求“所有东西都全局组件化”

判断顺序：

```text
只在一个页面稳定出现
→ Page-private / Page Pattern

同 Feature 多页面真实复用
→ Feature Public Component / Logic

跨 Feature 真正同语义复用
→ Shared / Domain Owner
```

共享的目标是**唯一事实和避免漂移**，不是追求组件数量。

---

# 8. Component Property、Token 和结构

审查：

- Instance 是否真来自公共 Component；
- 是否被 Detach 后手画；
- 可变文本是否使用 Component Property；
- 是否存在公共组件 + 外覆 Text；
- Property 引用是否断开；
- Variant 是否用于稳定视觉轴；
- Token 是否按语义复用；
- 同语义是否存在多套 Raw Color/Spacing；
- Auto Layout / Constraints 是否能承受真实文案长度。

公共组件源修改后必须复核消费者。

---

# 9. Prototype 审计

必须读取 当前场景所需完整约束。

静态画布正确不代表点击后正确。

检查：

```text
Flow Starting Point
Prototype Variable 默认值
Reaction / SET_VARIABLE
Open / Close / Change To
Overlay / Dropdown / Toast
Absolute Position
Auto Layout
Scroll / clipsContent
Hidden Layer
Destination Node
```

重点发现：

- 旧数据回弹；
- 双文字；
- 双图标；
- 相同 Toast 在不同页面漂移；
- Dropdown 被裁切；
- 失效 Flow；
- 演示伪造服务器/系统成功。

---

# 10. 状态完整性

所有页面按真实业务检查：

```text
Normal / Data
Loading
Empty
Error
Disabled
```

异步或复杂工作流按真实状态机补：

```text
Creating
Uploading
Running
Partial
Retry
Cancelled
Permission
Unavailable
Historical Compatibility
```

不机械要求每个项目拥有所有状态。

---

# 11. 产品语言与用户习惯

审查的不是“英文是否存在”，而是用户是否需要理解它。

可以保留：

```text
版本号
产品型号
标准名称
用户熟悉的品牌 / 协议 / 专名
```

通常不直接暴露：

```text
机器字段名
内部 ID 类型
调试对象名
内部状态码
Secret / Raw / Stack Trace
```

除非目标用户角色确实需要。

用户界面优先表达业务概念；机器字段通过 Annotation/开发规格与实现建立映射。

---

# 12. 动态数据和 Annotation

凡是会随系统变化的数据，正式基线应能说明：

```text
字段是什么
类型：SYSTEM_DYNAMIC / RUNTIME_STATE / SYSTEM_FIXED / DESIGN_EXAMPLE
来源：API / SDK / CMS / Store / Runtime / ...
示例值仅用于排版
刷新时机（有业务意义时）
空态
错误态
```

baseline-ready 必须执行 Annotation Sufficiency Review。只给实现无法从设计结构、Design Context 和正式事实源可靠推导的关键动态/非显然语义提供最小充分说明；不要用注释数量替代质量，也不要把完整 Contract / Schema 复制进 Canvas。详细充分性门禁由 当前场景所需完整约束 维护。

`baseline-ready` 还必须执行 **Annotation Development Readiness**：检查必要注释是否完整、正确并与当前真实系统机器事实一致；在 `review-and-fix` 且有 Figma 写权限时补齐/修正关键缺失并收敛重复说明，再重新复核。详细 Coverage、权限分支和去重规则由 当前场景所需完整约束 与 当前场景所需完整约束 维护。

当真实 Backend/Contract 与前端/Figma Annotation 发生漂移时，先确认当前正式机器事实 Owner：符合正式 Contract 的后端/SDK/consumer 变化要同步前端并在有权限时同步 Figma Annotation；后端违反正式 Contract/已批准需求时修后端，不能让 Figma 迁就 Bug。无写权限时记录 `Pending Figma Sync`。详细分支由 当前场景所需完整约束 维护。

开发 Annotation 不应压在正式 UI 上，也不能被实现方误读成产品文案。Annotation 与正式 Frame、相邻画板、说明容器之间的间距、归属、分区和 Canvas-level Review 统一由 当前场景所需完整约束 维护；本 Skill 不再维护第二套具体数值。

---

# 13. Design-to-Code / 实现交付

进入 `baseline-ready` 时读取 当前场景所需完整约束。

有代码仓库时必须重新确认当前技术栈，不假设：

```text
React / Vue / Angular
Flutter / SwiftUI / Compose
Tailwind / CSS Modules
任何状态管理 / UI Library
```

Figma MCP/工具返回的参考代码只表达结构意图，不得反向改变项目技术栈。

凡是 DatePicker / DateRange / Today / Now 等时间相关 UI，必须映射目标项目当前**真实 Runtime / Contract 时间语义**；设计日期和生成代码时的本机时间不构成生产默认值。详细时间事实源、时区和日期区间规则见 当前场景所需完整约束。

实现前确认：

```text
正式 Frame
→ Shared / Feature / Page Owner
→ 动态数据来源
→ 系统动作来源
→ Prototype / 状态规格
→ 当前项目实现入口
```

如果当前项目已经有目标 Page/Screen，必须先执行 Existing Implementation Delta Gate：以现有正确实现为基线，只实现新 Figma 经 Requirement/Contract/Owner 确认的真实差异，**不默认整页重写**。

生产实现由 Coding 工作流完成后，还必须执行 **Implementation ↔ Figma Conformance**，对实际页面、正式 Figma 与真实 Contract/Backend/SDK/Store 的 Visual、Interaction、State、Data/Contract、Responsive、Component/Owner 六个域做 targeted re-review；代码验证通过本身不等于 Design-to-Code 已闭环。

发现 Figma 已经过期且差异已经被确认成长期正式事实时，在有 Figma 写权限的任务中按 **Bidirectional Design Sync Gate** 回写真实 Figma Owner；不能把偶然实现偏移或 Bug 自动设计化。任何自动回写完成后先标记 `SYNCHRONIZED_PENDING_HUMAN_REVIEW`，并强制输出 `Figma Sync & Human Review`。详细 Drift Owner、back-sync 和人工复核规则由 当前场景所需完整约束 维护。

---

# 14. Baseline Ready 硬门禁

一个页面只有通过适用项才能判定 `READY`：

```text
[ ] Review Target 和项目形态明确
[ ] 目标用户和核心任务明确
[ ] 当前需求 / 系统事实已恢复
[ ] 用户输入和动作都有真实系统支持或明确 Future 标识
[ ] 动态数据都有真实来源
[ ] DESIGN_EXAMPLE 不冒充线上当前事实
[ ] Annotation Development Readiness 已完成，必要机器事实已校验
[ ] 必要 Annotation 最少充分，无会误导实现的缺失/错误/无意义重复
[ ] 页面尺寸与目标设备/Viewport 有依据
[ ] 设计基准没有诱导固定像素生产实现
[ ] 页面区块对齐、间距、信息密度合理
[ ] Canvas / Section / 相邻画板形成清晰稳定的组织和阅读顺序
[ ] Annotation / 开发说明与正式 Frame 有明确边界、归属和安全距离
[ ] 正式稿 / 状态稿 / 说明 / 历史或废弃稿分区清楚
[ ] zoom-out 整体视图没有明显拥挤、遮挡或归属混乱
[ ] 图片/文字/按钮/标注无无意重叠
[ ] 图片比例、裁切、长文本和图表极端状态有策略
[ ] 表格/表单适配真实数据长度和用户操作顺序
[ ] 公共视觉组件真实复用
[ ] Figma 修改遵守 Owner-first，没有 Detach/复制形成第二公共 Owner
[ ] 可复用业务逻辑有唯一 Owner
[ ] 不同语义没有为了“复用率”被错误合并
[ ] Component Property 无覆盖 Text
[ ] Token 无明确语义漂移
[ ] Prototype Variable / Reaction 无旧数据
[ ] Flow 无失效目标
[ ] Overlay / Toast / Dropdown / Modal / Drawer 无漂移、裁切、双层滚动
[ ] Normal / Loading / Empty / Error 覆盖
[ ] 其它状态按真实业务覆盖
[ ] 用户术语符合目标用户认知
[ ] 敏感内部实现没有无价值暴露
[ ] Fresh Screenshot 覆盖主要状态和关键浮层
[ ] Machine Audit / Prototype Audit 已执行
[ ] Design Context / 实现视角复核已执行（适用时）
```

存在阻塞正确实施的问题：`NOT_READY`。

只有非阻塞 Notes：`READY_WITH_NOTES`。

全部适用门禁通过：`READY`。

---

# 15. Findings

读取 当前场景所需完整约束。

## P0

会导致系统能力错误、关键用户任务不可完成、严重误实现、敏感信息泄露或正式基线不可实施。

## P1

不会立即破坏核心能力，但会造成明显可用性、复用、视觉一致性、状态完整性或维护风险。

## P2

非阻塞的信息密度、空间、文案和次级视觉优化。

每个确定 Finding 至少包含：

```text
级别
Frame / Node / Pattern
问题
真实事实或设计原则
触发条件
用户影响 / 实现影响
最小修复 Owner
验证方式
```

---

# 16. review-and-fix 原则

```text
发现问题
→ 找真正 Owner
→ 改 Owner
→ 验证所有消费者
→ Canvas-level Review
```

例如：

```text
所有页面 Button 都不一致
→ 修公共 Button

多个页面都复制同一动态业务规则
→ 收敛到唯一业务 Owner

图片和标注在多个状态重叠
→ 修容器 / Auto Layout / 标注规则

Toast 在不同页面漂移
→ 修公共定位模式 / Parent Layout
```

不逐页打补丁掩盖公共问题。

Canvas-level Review 不是无边界重排整个文件。最小修复范围是：

```text
当前目标节点
+
本次修改直接造成的相邻布局/可读性问题
```

如果页面内部已经正确，但整个 Canvas 仍然拥挤、贴边、遮挡、难以判断 Annotation 归属或正式稿与历史稿混杂，**不得声明 Figma 修改完成**。

---

# 17. 正式输出

至少包含：

## Review Target

项目形态、目标用户、Figma 目标和模式。

## Confirmed Facts

只写已由需求、Figma、代码/Contract/SDK/Runtime 等确认的事实。

## Findings

P0 → P1 → P2。

## System/Data Mapping

重要 UI 字段、动作和动态数据的真实来源。

## Component & Logic Reuse

Shared / Feature Public / Page-private 的视觉与业务 Owner。

## Layout & Usability

页面尺寸、位置、间距、Canvas/Section、图片/标注、表格/表单、滚动和用户任务路径。

## Prototype Audit

Variables / Reactions / Flow / Overlay / Scroll / Hidden State。

## Readiness

`READY / READY_WITH_NOTES / NOT_READY`。

## Figma Sync & Human Review

凡是 Design-to-Code 任务，此项为**强制输出**。本轮实际修改过 Figma 时必须列出具体 File/Page/Section/Frame/Node、Before → After、事实来源/原因、关联实现/Contract、受影响消费者、验证证据和人工复核重点；未修改时也必须说明 `NO_FIGMA_CHANGE_REQUIRED` 或 `Pending Figma Sync` 的依据。

自动回写过 Figma 但尚未取得人工/等价设计审批时，状态必须为 `SYNCHRONIZED_PENDING_HUMAN_REVIEW`；只有明确人工确认或项目已有等价审批证据才能描述为 `HUMAN_VERIFIED`。详细字段和状态定义由 当前场景所需完整约束 唯一维护。

---

# 18. 常见禁止事项

禁止：

1. 只看截图就宣称设计正确；
2. 把某个项目的页面、平台、字段、尺寸或技术栈写成通用规则；
3. Figma 有字段就假设系统支持；
4. 为了设计方便创造不存在的能力；
5. 把示例值写成生产事实；
6. 机械翻译所有英文或机械保留所有技术词；
7. 把所有重复视觉都升级成全局组件；
8. 复制同一业务逻辑到多个页面；
9. 把业务规则塞进 Button/Input 等基础组件；
10. 用页面级补丁代替公共 Owner 修复；
11. 忽略页面尺寸、真实 Viewport、滚动和响应式；
12. 允许图片、标注、文字和操作控件无意重叠；
13. 只检查单个 Frame/Node，不检查本次修改直接影响的 Section、相邻画板和 Annotation；
14. 只看局部 100% 视图，不检查 zoom-out 整体 Canvas 节奏；
15. 为了画布整洁擅自删除历史参考、备份或废弃稿；
16. 只设计理想短文本和理想数据；
17. 只检查静态 Frame，不检查 Prototype；
18. 用 Figma 替代 Contract / API / SDK / Runtime；
19. 让客户端绕过正式架构直接访问数据库；
20. 把 MCP 参考代码直接当目标项目实现；
21. 因为演示好看伪造系统执行成功；
22. 未执行必要验证就宣称“可以交给实现方”；
23. 已有公共组件时 Detach、复制或重画制造第二 Owner；
24. 代码实现完成后跳过 Implementation ↔ Figma Conformance，让设计与生产实现长期漂移；
25. 把未批准的实现 Bug、临时 workaround 或偶然像素偏移自动回写成 Figma 长期事实；
26. 实际修改过 Figma 后只说“已同步”，却不输出 `Figma Sync & Human Review` 供人工复核。