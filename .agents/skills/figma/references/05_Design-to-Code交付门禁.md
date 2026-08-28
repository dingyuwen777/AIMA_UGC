# Figma Design-to-Code 交付门禁

这份 reference 负责判断一个 Figma 页面是否已经可以作为 Codex、Coding Agent 或人工开发者的正式开发基线，并定义用户要求“按这个 Figma 替换/实现现有页面”时如何安全交接到目标项目的研发工作流。

核心原则：

> 视觉接近不是 Ready；只有设计结构、真实系统能力、Prototype、状态、数据来源、复用边界和目标实现环境都能无歧义映射时，才可以交付。

---

# 1. 正式基线的四层一致性

必须同时成立：

```text
设计视觉和用户任务
↕
Figma 结构 / Component / Prototype
↕
真实系统 Contract / SDK / State / Runtime
↕
目标项目的 Shared / Feature / Page 实现边界
```

Design-only 项目如果还没有实现层，则把后三层中的“当前实现”替换为明确的 `implementation_required`，不能写成已存在。

---

# 2. 开发前重新读取当前项目

有仓库时重新读取：

```text
项目规则
→ 当前技术栈 / Design System
→ 目标 Screen / Route / Navigation
→ State / Store / ViewModel
→ API / SDK / CMS / Local Store / Runtime
→ Shared UI / Feature Public Layer
→ 目标 Figma Design Context
```

没有仓库时，至少重新读取当前 Product Spec / Design Guide / Component Library。

不能用历史聊天替代当前事实。

---

# 3. Design Context 是实现视角证据

正式实现前应读取目标 Node 的 Design Context（宿主支持时），确认：

- 实现方实际会看到哪些节点；
- 是否识别成公共 Component Instance；
- Component Property 是否正确；
- Annotation 是否可读；
- 是否有隐藏旧文案或重复结构；
- 布局意图是否能映射当前技术栈。

Screenshot 只能作为视觉证据，不能代替 Design Context/结构审计。

---

# 4. Figma 工具参考代码不能反向决定技术栈

宿主工具可能输出 React、Tailwind 或其它示例代码。

目标项目可能是：

```text
Vue
React
Angular
Flutter
SwiftUI
Jetpack Compose
Electron
原生 HTML/CSS
其它技术栈
```

必须适配当前项目事实。

禁止为了复制 Figma 示例：

- 安装不需要的框架；
- 引入第二套 UI Library；
- 绕过现有 SDK/Generated Client；
- 静默改变状态管理、路由或样式体系。

---

# 5. Shared / Feature / Page / Logic 映射

实现前建立最小映射：

| Figma Pattern / Rule | 代码/实现 Owner | 动作 |
| --- | --- | --- |
| App Shell / Navigation | Shared/App | 复用唯一 Owner |
| Button/Input/Select | Shared UI | 复用稳定公共实现 |
| Feature KPI / Feature Form | Feature Public | 不强行全局化 |
| 同一业务资格/动态字段规则 | Shared Domain / Feature Public / Service | 多页面只保留一个逻辑 Owner |
| Page Table / Composition | Page / Feature | 按业务语义实现 |

设计系统和代码组件不要求机械 1:1；以真实复用边界为准。

---

# 6. 动态数据门禁

Figma 中任何代表性数量、名称、状态、时间、版本、图片、价格、统计等，只决定设计排版。

实现必须追到真实来源：

```text
API / SDK / CMS / Store / Local DB / Device / Runtime / Config
```

禁止：

- 把示例数量硬编码成线上值；
- 把示例选项当机器枚举全集；
- 把示例 ID 当正式业务编号规范；
- 把示例图片比例当唯一真实比例。

---

# 7. Annotation 是设计与机器事实的翻译层

UI 使用产品语言；Annotation/开发规格可以说明机器映射。

例如：

```text
UI：执行频率
Annotation：提交 schedule_expr / interval（以当前 Contract 为准）
```

或：

```text
UI：用户头像
Annotation：图片 URL 来自当前用户 Profile API / Local Account Store
```

Annotation 不复制完整 OpenAPI/Schema，而只写实现所需的关键边界。

---

# 8. 导航和未来 IA

Figma 可以表达已确认的未来信息架构。

当前实现只接真实存在的：

```text
Route / Navigation Destination / Screen Registry / Command
```

未来入口不能因为设计存在就自动生成：

- 死链；
- 空页面；
- 假按钮；
- 无后端/系统支持的伪功能。

具体导航模型按 Web/Mobile/Desktop 项目事实映射。

---

# 9. 状态交付

实现方至少应能找到适用的：

```text
Normal / Data
Loading
Empty
Error
Disabled
```

复杂业务按真实状态机补充。

不要求所有状态都进入主 Prototype 流程，可以放在独立开发状态规格区，但必须能定位。

---

# 10. 页面尺寸和响应式实现

Figma Frame 是设计基准，不自动等于生产固定像素。

实现方必须能理解：

- 目标设备/Viewport；
- Sidebar/TopBar/Safe Area；
- Content Padding；
- Responsive breakpoint（存在时）；
- 图片容器策略；
- 表格/表单在窄宽度下的策略；
- Modal/Drawer 的最大尺寸和滚动方式。

如果设计只有一个桌面 Frame，但产品要求响应式，`baseline-ready` 必须有明确响应式规则或 Notes。

---

# 11. Ready 判定

## `NOT_READY`

存在任何会阻止正确实施的问题，例如：

- 真实系统不支持设计行为；
- 动态字段事实源不明；
- Prototype 会回弹旧数据；
- 关键公共组件是假复用；
- 相同业务逻辑被要求多页面复制；
- 页面尺寸/滚动/重叠导致关键任务不可用；
- 缺关键状态；
- 敏感信息泄露；
- Design Context 与正式视觉结构冲突。

## `READY_WITH_NOTES`

无阻塞项，但存在已经明确、不会影响正确实施的 Notes。

## `READY`

所有适用硬门禁有当前证据。

---

# 12. Baseline Ready Checklist

```text
[ ] Project Shape / Target User / Task 明确
[ ] 当前项目事实已重新读取
[ ] 用户输入/动作都有真实系统映射或 Future 标识
[ ] 动态数据来源明确
[ ] 示例数据不冒充生产事实
[ ] 页面尺寸 / Viewport / 响应式边界明确
[ ] 正常状态无图片/文字/标注/控件无意重叠
[ ] 公共组件真实复用
[ ] 可复用业务逻辑有唯一 Owner
[ ] Component Property 无外覆 Text
[ ] Token 无明确语义漂移
[ ] Prototype Variable / Reaction 无旧数据
[ ] Flow 无失效目标
[ ] Overlay / Scroll / Dropdown / Modal / Drawer 正确
[ ] 关键状态完整
[ ] 用户术语符合目标用户认知
[ ] 机器字段/敏感实现没有无价值暴露
[ ] Fresh Screenshot 已检查
[ ] Machine / Prototype Audit 已检查
[ ] Design Context / 实现视角已检查（适用时）
```

未实际执行必要验证时，不得用“应该没问题”补证据。

---

# 13. Coding Handoff

Ready 后交付给实现方至少包含：

```text
正式 Figma Node / Section
目标用户任务
对应实现入口
必须复用的 Shared Component
必须复用的业务逻辑 Owner
动态数据来源
系统动作来源
Feature/Page 边界
页面尺寸/响应式规则
Prototype / 状态规格入口
已知 Notes
```

Figma Skill 的 `READY` 只证明设计可以实施，不证明代码已经实现、测试已通过或 PR 可合并。

## 13.1 用户要求“按这个 Figma 替换/实现现有页面”时

这类请求必须视为 **Figma 基线验收 + 项目 Coding 实施** 的组合任务，而不是让 Figma Skill 直接承担生产研发。

标准流程：

```text
用户提供 Figma 链接 + 目标仓库/实现上下文
→ 恢复当前项目规则和实现事实
→ 确定正式 Figma Node / Starting Point
→ baseline-ready
→ NOT_READY：
   - 用户已授权修改 Figma → review-and-fix → re-review
   - 用户未授权修改 Figma → 停止生产实现并报告阻塞
→ READY / 可实施的 READY_WITH_NOTES
→ 形成 Coding Handoff
→ 立即切入目标项目 Coding 工作流
→ Coding 按项目规则实施、验证、Review、CI、Git/交付
→ 实现完成后用 Figma 做 targeted re-review
```

### Handoff 前必须重新定位现有实现

有代码仓库时，不允许只凭页面名称或历史聊天猜目标文件。至少按项目形态确认适用的：

```text
Route / Screen / Navigation Destination
Page / View / Feature
Store / State / ViewModel
API / SDK / Generated Client / CMS / Local Store
Contract / Schema / Runtime Capability
Shared UI / Feature Public / Shared Domain Owner
相关测试 / Acceptance 入口
```

找不到某一层时记录 `not_applicable` 或 `implementation_required`；不要为了填表制造不存在的架构层。

### Figma 和当前实现发生冲突时

先分类，不机械“Figma优先”或“代码优先”：

```text
旧前端视觉落后，但真实系统已经支持正式 Figma
→ Coding 更新前端实现，保留正确机器行为

Figma 示例值与真实动态数据不同
→ 实现使用真实数据源，示例只服务排版

Figma 行为当前系统不支持，也没有批准未来能力
→ NOT_READY / implementation_required，不伪造实现

当前代码违反正式 Contract / 已批准设计
→ 作为 Coding Finding 修实现，不让 Figma 迎合已知 Bug

长期设计决定与当前机器事实冲突且无法判断谁过期
→ 先按项目决策门禁调查/提请 Owner，不静默选择
```

### 实施层必须保持真实 Owner

Design-to-Code 的目标是替换/实现**页面表现和交互组合**，不是重建第二套系统事实。

```text
Figma Shared Component
→ 映射项目真实 Shared UI / Design System Owner

Figma Feature Pattern
→ 映射 Feature Public / Page Composition

动态数据
→ 继续沿当前正式 API / SDK / Store / Runtime 链路

业务资格 / 状态映射 / 默认值 / 校验
→ 继续复用当前唯一 Domain / Feature / Service Owner
```

禁止为了“还原设计”：

- 在页面硬编码 Figma 代表性数据；
- 复制已有业务规则到新页面；
- 绕过 generated client / SDK / Repository / Service 等当前正式边界；
- 因工具参考代码引入第二套框架、UI Library 或状态管理；
- 把未来 IA 直接实现成当前死链/空页面；
- 删除正确的 Loading/Error/Permission/兼容状态只为了截图更像。

### Coding 细则只引用，不复制

一旦进入生产实现：

```text
Change / Requirement Traceability
TDD / 根因调试
Validation Matrix
Code Review
CI
Git / PR / Merge / Release
```

全部服从目标项目自己的 Coding / CONTRIBUTING / AGENTS 等研发规则。

本 reference 只负责把**已经 Ready 的设计事实**完整交过去，不再维护第二套研发流程。

### 实现完成后的 Figma 回验

目标项目的代码验证完成后，至少按适用边界做 targeted re-review：

```text
实际运行页面 / Screen
↔ Fresh Figma Screenshot
↔ 关键 Prototype / 状态规格
↔ Shared Component / 业务 Owner
↔ 动态数据和真实系统动作
```

如果实现过程中因为真实系统约束需要改变已批准设计，应同步回设计/长期事实源，不能让 Figma 和生产实现长期分叉。