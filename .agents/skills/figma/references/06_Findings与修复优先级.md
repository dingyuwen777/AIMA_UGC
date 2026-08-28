# Figma Findings 与修复优先级

Figma Review 的 Finding 必须能解释：

```text
问题在哪里
为什么是真问题
什么条件会触发
影响用户还是影响实现方
应该改哪个 Owner
怎样证明修好了
```

不要用“感觉不高级”“建议优化一致性”代替可执行 Finding。

---

# 1. P0 — 阻塞正式开发基线

出现以下任意一类，`baseline-ready` 默认 `NOT_READY`：

- Figma 字段/按钮对应的真实系统能力不存在；
- UI 文案承诺的语义与机器实现不一致；
- 用户输入没有真实系统映射；
- 动态数据事实源不明或被设计成常量；
- Prototype Variable/Reaction 会回退到旧数据；
- 公共组件结构会让实现方生成重复或错误结构；
- 相同业务规则被设计成多个页面各实现一套，并会产生漂移；
- 关键 Normal/Loading/Empty/Error 或真实状态缺失；
- Flow Destination 失效；
- 页面尺寸、滚动、重叠、裁切导致关键用户任务无法完成；
- 暴露 Secret、Token、内部异常栈、敏感数据等；
- 未来 IA 被要求直接生成当前不存在的可用功能；
- Design Context 与正式设计表达冲突，无法无歧义实施。

P0 示例：

```text
级别：P0
Frame：订阅设置 / 执行频率
问题：UI 提供“每9小时”，当前系统调度模型不能严格表达该语义。
事实：当前调度器会在日界重新对齐。
影响：实现方照设计接线后，用户看到的频率与实际执行不一致。
修复：删除该选项，或先扩展正式调度能力。
验证：重新读取调度 Contract + Figma 选项/Reaction + Design Context。
```

---

# 2. P1 — 应在正式交付前修复

不会立即破坏核心系统能力，但会明显增加误实现、可用性或维护风险：

- 术语混乱；
- 示例数据跨页面不一致；
- 公共组件复用不彻底；
- 可复用业务逻辑没有唯一 Owner；
- Component Property 绑定丢失；
- Raw Token 与明确语义 Token 不一致；
- 图片/标注间距或重叠风险；
- 表格列宽只适配理想短文本；
- Modal/Drawer/Toast 次级状态不一致；
- 多个模糊正式 Flow 起点；
- 产品 UI 暴露无价值内部对象名。

P1 通常应在正式 `READY` 前修掉；确实不影响正确实施时才可 `READY_WITH_NOTES`。

---

# 3. P2 — 非阻塞体验优化

例如：

- 信息密度偏低；
- 大卡片留白过多；
- 次要文案过长；
- 次级视觉层级可更清晰；
- 局部空间利用可更好。

P2 不能伪装成业务正确性问题。

---

# 4. Finding 模板

```markdown
### [P0] <一句话问题>

- Frame / Node / Pattern：`...`
- 问题：...
- 触发条件：...
- 当前事实：...
- 用户影响：...
- 实现影响：...
- 最小修复 Owner：...
- 修复方向：...
- 验证：...
```

没有足够证据时写：

```text
Risk / 待验证假设
```

不要强行定性。

---

# 5. 修复 Owner 优先级

定位问题真正属于：

```text
Variable / Token
Shared Component
Feature Public Component
Reusable Business Logic
Page Pattern
Single Frame
Prototype Variable / Reaction
```

不是固定按顺序修改，而是找真实 Owner。

## 多页面 Button 样式不一致

如果都是同一 Instance：检查 Variant/Property。

如果是手画：迁移公共 Button。

## 多页面都复制同一业务资格

收敛到唯一业务 Owner，让多个页面消费同一规则。

## 同类 Toast 漂移

检查定位模式、Parent Auto Layout、安全区，不逐页硬改坐标。

## 图片与标注重叠

检查容器布局、文本长度、Annotation 所属层和响应式边界，而不是只把某一个标注挪开。

---

# 6. review-and-fix 后的 re-review

修复后至少复核：

```text
原 Finding 是否消失？
是否引入新布局回归？
公共 Owner 的其它消费者是否正确？
业务逻辑消费者是否都仍使用同一 Owner？
Prototype Variable/Reaction 是否同步？
默认状态是否恢复？
旧字符串/旧组件扫描是否清零？
Fresh Screenshot 是否覆盖关键状态？
Design Context 是否看到正确结构？
```

公共组件或公共业务 Owner 修改后，必须抽查关键消费者。

---

# 7. Ready 输出

## `NOT_READY`

- 任意未解决 P0；
- 必需事实源无法读取；
- 必需 Screenshot/Prototype/系统能力验证没有执行。

## `READY_WITH_NOTES`

- P0 清零；
- 剩余问题不会阻止正确实施；
- Notes 已明确边界。

## `READY`

- 影响正式实施的 P0/P1 已清零；
- 必需视觉、Prototype、系统能力和实现视角证据完整；
- 动态数据、组件和业务逻辑 Owner 无未决项。

Figma `READY` 只代表设计可实施，不代表代码已完成或可合并。
