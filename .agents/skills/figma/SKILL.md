---
name: figma
description: 面向 Figma 产品原型、设计系统和 Design-to-Code 正式开发基线的事实驱动审查与修复工作流。先恢复当前仓库、前端、后端 Contract/Capability/状态机等真实事实，再检查 Figma 的视觉、组件复用、Prototype、状态覆盖、用户术语、动态数据来源和 Codex 可实现性；禁止把 Figma 示例数据当服务器事实、把截图当结构证据、把后端实现名机械暴露给用户，或在后端不支持时由设计稿创造伪能力。支持 review-only、review-and-fix 和 baseline-ready。Use for Figma prototype review, Figma design audit, design-system consistency review, prototype QA, backend-contract alignment, Design-to-Code readiness, and Figma review-and-fix.
---

# Figma

Figma Skill 的职责不是单纯回答：

> “这个页面好不好看？”

而是判断：

```text
这个设计表达的业务能力是真的吗？
与当前后端 / Contract / Store / Route 一致吗？
动态数据到底从哪里来？
用户看到的是业务语言还是后端实现语言？
公共组件真的复用了吗？
Prototype 点击后是否仍然正确？
Codex 能否无歧义地把它实现成当前仓库代码？
这个 Frame 是否已经达到正式开发基线？
```

核心执行链：

```text
恢复当前事实
→ 明确 Figma Review Target
→ 建立设计事实 / 业务机器事实 / 运行事实边界
→ 审查静态结构
→ 审查 Prototype
→ 审查后端能力映射
→ 审查设计系统与组件复用
→ 审查状态完整性与产品语言
→ 从 Design Context 复核 Codex 视角
→ 输出 Findings
→ 有修复授权时修 Figma
→ Fresh Screenshot + Machine Audit + Design Context
→ 给出交付结论
```

详细方法位于 `references/`。命中对应情形时必须读取相关 reference；不能只读本文件后凭印象完成审查。

---

# 1. 上位规则与事实源

## 1.1 项目规则优先

进入任何仓库相关 Figma 任务前：

```text
适用 AGENTS.md / 项目本地规则
→ .agents/skills/coding/SKILL.md（同仓存在时）
→ 项目 Figma / Frontend Guide
→ 当前任务相关 Blueprint / Contract / Code / Test
→ 本 Skill
```

本 Skill 不复制 Coding 的研发、Change、Git、CI、测试、安全和交付规则。

如果当前任务发现需要修改生产代码：

```text
figma finding
→ code_issue_detected
→ 返回 Coding
→ Coding 修复并验证
→ Figma targeted re-review
```

Figma Skill 不因为发现代码问题自动获得生产代码修改权限。

如果需要同步正式技术文档，并且仓库存在 Docs Skill：

```text
Figma
→ docs_impact
→ .agents/skills/docs/SKILL.md
```

Figma Skill 不复制 Docs 的技术写作规范。

如果需要正式代码 Review，并且仓库存在 Review Skill：

```text
Figma → Design-to-Code 实施完成
→ Coding 完成实现与验证
→ Review Skill 独立复核
```

Figma Skill 不替代代码 Review。

详细事实源和路由见 [01_事实源与审查流程.md](references/01_事实源与审查流程.md)。

## 1.2 必须区分三类事实

任何审查先建立：

| 类型 | 事实源 | 例子 |
| --- | --- | --- |
| 设计事实 | Figma Component / Variable / Frame / Prototype | 布局、颜色、间距、交互意图 |
| 业务机器事实 | Contract / Schema / Backend / Generated Client | 字段、状态、能力、约束 |
| 当前运行事实 | API / 数据库 / 服务器状态 | 当前数量、当前渠道配置、真实时间 |

硬规则：

```text
Figma 有字段
≠ 后端支持该字段

Figma 有一个下拉选项
≠ 后端支持该行为

Figma 示例“18”
≠ 服务器当前就是 18

后端对象叫 Provider
≠ 用户 UI 必须显示 Provider
```

---

# 2. 工作模式

## 2.1 `review-only`

默认模式。

允许：

- 读取 Figma；
- 读取仓库当前事实；
- 获取截图、Metadata、Design Context；
- 检查 Prototype Variable / Reaction / Flow；
- 输出 Finding 和 Ready 判断。

不因为审查请求自动获得：

- 修改 Figma；
- 修改代码；
- 修改文档；
- commit / PR / merge / release 权限。

## 2.2 `review-and-fix`

仅在用户明确要求修改 Figma 时使用。

流程必须是：

```text
先审查
→ 确认 Finding / 根因
→ 修改最小 Owner
→ Fresh Screenshot
→ 机器结构复查
→ Prototype 复查
→ Design Context 复查
```

禁止：

```text
看到错位
→ 随便移动一下
→ 结束
```

必须修根因。例如：

```text
Toast 漂移
→ 检查 Auto Layout / Absolute Position

双文本
→ 检查 Component Property + 外覆 Text

双图标
→ 检查 Variant 自带 Icon + Message 手写 Icon

保存后出现旧值
→ 检查 Prototype Reaction / Variable
```

## 2.3 `baseline-ready`

当用户希望把 Figma 交给 Codex 或作为正式开发基线时使用。

必须执行完整交付门禁，不允许只凭：

- 一张截图；
- 一个主 Frame；
- “看起来没问题”。

最终只能给出：

```text
READY
READY_WITH_NOTES
NOT_READY
```

并说明证据边界。

---

# 3. Figma Review Target 必须明确

开始前至少记录：

```text
Figma file
Page
正式 Section
目标 Frame / Node
Prototype starting point
目标代码 Page / Route（适用时）
授权模式
```

如果同一 Page 同时有：

```text
正式开发基线
历史参考
备份
废弃归档
```

必须明确哪一个才是当前事实源。

Codex 不得从历史 Frame 猜实现。

---

# 4. 后端能力映射是核心门禁

每一个会改变业务行为的 UI 字段，都必须回答：

```text
UI 字段是什么？
用户认为它做什么？
生产值来自哪里？
对应 Request / Response / Store / Service 是什么？
后端当前真正支持吗？
值由用户配置、服务器返回还是系统固定？
```

至少归类为：

```text
STATIC_UI
→ 纯视觉 / 固定产品文字

USER_INPUT
→ 用户输入并进入真实 Request

API_DYNAMIC
→ API / Store 返回

SERVER_RUNTIME
→ 当前服务器 / 数据库实时事实

DESIGN_EXAMPLE
→ 只为设计展示的代表值

SYSTEM_FIXED
→ 后端固定策略，只读
```

如果关键字段无法归类，不得宣称页面 Ready。

详细规则见 [02_业务能力与前后端映射.md](references/02_业务能力与前后端映射.md)。

## 4.1 不允许由 Figma 创造后端能力

例如设计出现：

```text
每9小时
```

必须先检查当前 Scheduler 是否真的能严格表达“每隔9小时”。

规则固定为：

```text
后端能支持
→ Figma 可以设计

后端不能支持
→ 不在正式基线承诺
→ 如业务需要，形成正式后端 Change
```

## 4.2 不机械推断“渠道”

必须区分：

```text
数据来源
采集渠道
目标平台
```

它们不自动是同一层。

例如：

```text
本地文件导入
≠
网络采集 Provider
```

除非当前 Contract / Registry 明确把两者抽象成同一渠道模型，否则 Figma 不得为了产品表面统一把它们塞进同一个 Select。

## 4.3 Capability 动态能力

存在后端 Capability 时：

```text
Capability
→ UI 可用平台
→ UI 可用选项
→ UI 默认值
→ 保存资格
```

必须动态驱动。

禁止从 Figma 示例反向维护第二套平台参数表。

Figma 可以展示代表性 Dynamic Form Pattern，但 Annotation 必须标明真实字段来源。

---

# 5. 示例数据与服务器事实

Figma 可以使用代表性示例数据，但必须符合以下规则。

## 5.1 示例数据真实感不等于生产事实

允许：

```text
爱玛品牌词包
v4
28 词

计划编号：20260828001
```

但不得因为 Figma 写了：

```text
启用计划：18
```

就把 `18` 当服务器当前事实或前端常量。

## 5.2 示例数据必须跨页面一致

同一对象在：

```text
列表
详情
创建表单
关联页面
```

出现时，应使用同一代表性身份和版本，除非明确设计的是不同状态。

## 5.3 不机械中文化

产品语言以用户理解为目标，不是“所有拉丁字母都消失”。

通常可以保留：

```text
v1 / v2 / v3 / v4
Q7
合法产品型号
确有用户认知价值的品牌 / 标准名 / 专名
```

通常不应直接暴露：

```text
provider_config_id
Run ID
Job ID
Campaign
Scope
Capability
Scheduler
Raw
Secret
内部 error_code
```

除非目标用户就是管理员/开发者，且该信息确有产品价值。

审查时问：

> 这个词用户真的需要知道吗？

而不是：

> 它是不是英文？

---

# 6. 产品语言审计

用户界面优先表达业务语言。

检查：

```text
后端内部对象名是否直接暴露？
中英文是否无意义混杂？
技术实现是否被误当产品概念？
同一概念是否有多个叫法？
```

可以做产品映射，例如：

```text
Provider Config
→ 采集渠道

schedule_expr
→ 执行频率 / 执行周期

Job
→ 后台任务

keyword_pack.version
→ v4
```

但 Annotation / Contract Mapping 中仍应保留机器名，方便 Codex 正确接线。

原则：

```text
UI 产品语言
≠
Contract 字段命名

但二者必须建立明确映射。
```

---

# 7. 设计系统与组件复用审计

必须区分：

```text
Global Shared Component
Feature Component
Page Pattern
Page-private Composition
```

详细规则见 [03_设计系统与组件复用审计.md](references/03_设计系统与组件复用审计.md)。

## 7.1 跨页面公共组件

稳定跨页面模式优先复用，例如：

```text
Sidebar
TopBar
Page Header
Button
Input
Select
Checkbox
Switch
Tabs
Feedback
Empty State
Modal Shell
Drawer Shell
```

同一种稳定模式只允许一种公开实现路径。

## 7.2 不做万能组件

以下不能因为“看起来会复用”就自动进入 Global Shared：

```text
Feature KPI
特定业务表格
特定业务表单
某业务筛选组合
```

判断顺序：

```text
页面内复用
→ Page Pattern

同 Feature 真实复用
→ Feature Component

跨 Feature 稳定复用
→ Shared
```

## 7.3 Component Property 审计

可变值必须由真正的 Component Property 表达。

错误：

```text
AIMA/Select
内部：小红书

+
页面覆盖 Text：全部平台
```

正确：

```text
AIMA/Select
文本 = 全部平台
```

重点扫描：

- Instance 外覆 Text；
- Component Property 引用断开；
- Detach 后重新手画；
- Variant 与业务状态不一致。

---

# 8. Prototype 审计

静态画布正确不代表 Prototype 正确。

必须同时检查：

```text
Flow Starting Point
Reaction
Variable
Variable 默认值
SET_VARIABLE Action
Overlay
Open / Close
Change To
Absolute Position
Auto Layout
Overflow / Scroll
Hidden Layer
Destination Node
```

详细规则见 [04_Prototype状态与交互审计.md](references/04_Prototype状态与交互审计.md)。

重点寻找：

## 8.1 旧数据回弹

例如：

```text
画布 = 28词
点击添加
→ Prototype Variable = 4词
```

这是 Finding。

## 8.2 重复 UI

例如：

```text
Success Variant 自带 ✓
+
Message = "✓ 保存成功"
```

结果双对号。

或者：

```text
Feedback Component
+
额外 Text
```

结果文字重叠。

## 8.3 同一状态不同页面位置漂移

例如 Toast：

```text
Page A → x=540
Page B → x=1080
Page C → y=910
```

需要统一定位规则，而不是逐页目测调整。

Auto Layout 页面中的浮层要检查 Absolute Position，否则坐标可能被布局系统重新计算。

## 8.4 Prototype 不伪造服务器结果

以下行为依赖真实 API：

```text
创建任务成功
保存数据库成功
后台 Worker 完成
Provider 请求成功
```

Prototype 不应为了演示把它们伪造成真实服务器执行证据。

可以设计“成功后的视觉状态”，但必须明确：

```text
Representative State
≠
真实执行结果
```

---

# 9. 状态完整性审计

至少检查：

```text
Normal / Data
Loading
Empty
Error
Disabled
```

按真实业务补充：

```text
Partial Success
Permission
Unavailable
Creating
Uploading
Running
Cancelled
Retry
Historical Compatibility
```

状态不是越多越好。

原则：

> 后端状态机真实存在并且用户需要理解或操作，才设计。

异步任务必须核对真实状态枚举，不能只设计“成功 / 失败”。

---

# 10. Design Token 与视觉一致性

审查：

```text
Color
Typography
Spacing
Radius
Border
Control Height
Layout
Icon
```

已有语义 Token 时必须复用。

禁止为了 Token 覆盖率：

```text
看到相近 Hex
→ 强行合并
```

只有确认语义相同时才能绑定。

还要检查：

- 同一页面不同 Raw Color；
- 两套 Primary；
- 字体与代码实施策略冲突；
- Unicode Icon 被误当正式产品 Icon。

---

# 11. 信息密度与视觉层级

视觉 Review 不能只看“是否对齐”。

至少检查：

```text
信息密度
主次层级
留白
控件权重
表格宽度
状态颜色
重复信息
用户决策负担
```

例如：

```text
三张巨大 KPI 卡
但每张只有一行数字
```

可以判断是否应该收敛成摘要条。

但视觉优化不能改变真实业务字段或后端行为。

---

# 12. Target IA 与真实 Route

固定检查：

```text
Figma Target IA
≠
当前 Production Route
```

设计可以提前表达已经确认的未来信息架构。

Design-to-Code 时：

```text
当前真实 Route
→ 接通

未来 Target IA
→ 不生成死链
→ 不创建假页面
→ 不制造伪功能
```

---

# 13. Codex Design-to-Code Readiness

进入 `baseline-ready` 时必须从 Codex 视角重新读取目标 Frame 的 Design Context。

必须确认：

```text
Codex 看到的是正式 Frame
不是历史 Frame

Codex 看到公共 Component Instance
不是手画拷贝

动态文本是 Component Property
不是叠加 Text

Annotation 说明真实 API / Contract 来源

动态数据没有被写成常量事实

Feature Pattern 与 Shared Component 边界清晰
```

Figma MCP 输出的 React / Tailwind 等代码只能视为结构参考；目标仓库使用什么技术栈，必须重新读取当前仓库事实。

详细门禁见 [05_Design-to-Code交付门禁.md](references/05_Design-to-Code交付门禁.md)。

---

# 14. Baseline Ready 硬门禁

一个页面只有同时通过以下检查才能判定 `READY`：

```text
[ ] 已恢复当前仓库事实
[ ] 已读取相关 Contract / Store / API / Capability
[ ] 所有用户输入都对应真实后端能力
[ ] 所有动态字段都有事实来源
[ ] 示例数据明确不是服务器事实
[ ] 没有 Figma 创造的伪能力
[ ] 公共组件真实复用
[ ] Component Property 无覆盖文本
[ ] Prototype Variable / Reaction 无旧数据
[ ] Prototype 无失效目标
[ ] Flow 起点唯一且明确
[ ] Normal / Loading / Empty / Error 已覆盖
[ ] 其它状态按业务真实需要覆盖
[ ] Toast / Overlay / Drawer / Modal 无重叠和漂移
[ ] 没有双图标 / 双文本 / 重复 Feedback
[ ] 用户术语符合产品认知
[ ] 没有不必要暴露内部实现
[ ] Design Token 无明确语义漂移
[ ] Fresh Screenshot 通过
[ ] Design Context 从 Codex 视角通过
```

存在 P0 Finding：

```text
NOT_READY
```

只有非阻塞问题：

```text
READY_WITH_NOTES
```

全部通过：

```text
READY
```

未实际执行必要验证时，不得给 `READY`。

---

# 15. Findings 与严重度

详细格式见 [06_Findings与修复优先级.md](references/06_Findings与修复优先级.md)。

## P0 — 阻塞正式开发基线

例如：

- Figma 字段后端不存在；
- UI 行为后端不能实现；
- 动态数据被写成生产常量；
- Prototype 与真实状态机冲突；
- 公共组件结构会让 Codex 生成错误 DOM；
- 关键状态缺失；
- 设计会泄露 Secret / 内部敏感信息；
- Design Context 与画面表达冲突。

## P1 — 应在交付前修复

例如：

- 术语混乱；
- 示例数据跨页面不一致；
- 组件复用不彻底；
- Raw Token 漂移；
- 次要状态遗漏；
- Prototype 小范围不一致。

## P2 — 非阻塞优化

例如：

- 信息密度；
- 空间利用；
- 文案精简；
- 次级视觉层级。

每个确定性 Finding 至少包含：

```text
级别
Node / Frame
问题
真实事实
用户影响 / Codex影响
建议修复
验证方式
```

---

# 16. Review + Fix 修复原则

有修复授权时：

```text
发现问题
→ 找到真正 Owner
→ 改 Owner
→ 不逐页面打补丁
```

例如：

```text
三个页面 KPI 一样难看
→ 改 Feature KPI Component 源

三个页面 Toast 错位
→ 统一 Toast Pattern / Position

所有 Select 文本叠加
→ 改公共 Select Component Property

多个页面图标不一致
→ 修公共 Icon 规则
```

修改基础组件后必须重新验证所有受影响消费者。

---

# 17. 正式输出格式

每次正式审查至少输出：

## Review Target

```text
Figma File:
Page:
Frame / Node:
Mode:
Related Route:
```

## Confirmed Facts

只写已经由 Figma / Repo / Contract / Runtime 明确确认的事实。

## Findings

按 P0 → P1 → P2。

## Backend / Contract Mapping

列出重要 UI 能力对应的真实事实源。

## Component Reuse

说明 Shared / Feature / Page-private 的边界是否正确。

## Prototype Audit

说明 Variables / Reactions / Flow / Overlay / Scroll / Hidden State 结果。

## Readiness

只能是：

```text
READY
READY_WITH_NOTES
NOT_READY
```

如果未执行 Fresh Screenshot / Prototype / Design Context 等必要验证，不得给 READY。

---

# 18. 常见禁止事项

禁止：

1. 只看截图就宣称 Figma 正确；
2. 从历史聊天猜后端能力；
3. Figma 有字段就假设后端有字段；
4. 为了设计方便创造后端不存在的选项；
5. 把示例值写成服务器事实；
6. 机械把所有英文翻成中文；
7. 把所有重复视觉都升级成 Shared Component；
8. 用业务页面复制修复代替公共 Owner 修复；
9. 只检查静态 Frame，不检查 Prototype；
10. 把 MCP 返回的 React/Tailwind 示例直接交付到不同技术栈项目；
11. 用 Figma 替代 Contract / Schema；
12. 用代码现状强迫设计迎合已经确认的实现 Bug；
13. 因为“演示好看”伪造成功的 API / Worker / Provider 结果；
14. 未实际验证就宣称“可以交 Codex”。
