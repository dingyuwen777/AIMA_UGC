# Figma Findings 与修复优先级

Figma Review 的 Finding 必须能解释：

```text
问题在哪里
为什么是真的问题
触发后会怎样
影响用户还是影响 Codex
应该改哪个 Owner
怎样证明修好了
```

不要用“这里感觉不够高级”“建议优化一致性”代替可执行 Finding。

---

# 1. P0 — 阻塞正式开发基线

出现以下任意一类，`baseline-ready` 默认判定 `NOT_READY`：

- Figma 字段/按钮对应的后端能力不存在；
- UI 文案承诺的语义与机器实现不一致；
- 用户输入没有真实 Request 映射；
- 动态数据事实源不明或被设计为常量；
- Prototype Variable/Reaction 会把当前状态回退到旧数据；
- 公共组件结构会让 Design Context 产生重复 DOM；
- 关键 Normal/Loading/Empty/Error 或真实状态机状态缺失；
- Flow Destination 失效；
- Toast/Overlay/Drawer 在正式路径中不可见、重叠或被裁切；
- 暴露 Secret、Token、Provider Raw、内部异常栈等敏感实现；
- Target IA 被要求直接生成当前不存在的生产 Route；
- Design Context 与截图/正式结构表达冲突，无法无歧义实施。

P0 Finding 示例：

```text
级别：P0
Frame：新建采集计划 / 执行频率
问题：UI 提供“每9小时”，当前五字段 Cron 不能严格保证跨天每隔9小时。
事实：Scheduler 当前只支持五字段 Cron；*/9 会在日界重新对齐。
影响：Codex 按设计实现后，用户看到的产品语义与实际调度行为不一致。
修复：移除该选项，或先通过 Coding Change 增加 interval 调度 Contract。
验证：重新读取 Scheduler + Figma option/reaction + Design Context。
```

---

# 2. P1 — 应在正式交付前修复

不会直接造成业务错误，但会明显增加误实现或维护风险：

- 中英文/术语无意义混杂；
- 同一示例对象跨页面名称或版本不一致；
- Feature Component 仍手画重复基础控件；
- 公共 Component Property 绑定丢失；
- Raw Color 与明确语义 Token 不一致；
- Prototype 次级状态不一致；
- 页面存在多个模糊正式 Flow 起点；
- 产品 UI 暴露无价值内部对象名；
- 同类 Toast / Empty / Feedback 位置或样式不一致。

P1 通常应在宣布 `READY` 前修掉；如果明确不会妨碍正确实现，可以 `READY_WITH_NOTES`，但必须解释原因。

---

# 3. P2 — 非阻塞视觉/体验优化

例如：

- 信息密度偏低；
- 大卡片留白过多；
- 次要文案过长；
- 列宽分配可以更合理；
- 标题/副标题层级还可优化；
- 次要说明位置可更紧凑。

P2 不能伪装成业务正确性问题。

---

# 4. Finding 模板

```markdown
### [P0] 执行频率包含后端不能严格表达的选项

- Frame / Node：`...`
- 问题：...
- 触发条件：...
- 当前事实：...
- 用户影响：...
- Codex / 实施影响：...
- 最小修复 Owner：...
- 修复方向：...
- 验证：...
```

没有足够证据时写成：

```text
Risk / 待验证假设
```

不要强行定性。

---

# 5. 修复 Owner 优先级

找到最小真实 Owner：

```text
Variable / Token
→ Shared Component
→ Feature Component
→ Page Pattern
→ Single Frame
→ Prototype Variable / Reaction
```

不是固定按这个顺序修改，而是判断问题真正属于哪一层。

例如：

## 三页 Button 样式不一致

如果三页都用同一 Button Instance：

→ 检查 Variant/Instance Property，不要新建 Button。

如果三页是手画 Frame：

→ 迁移到公共 Button。

## 三页 KPI 都太松散

如果 KPI 只属于一个 Feature：

→ 改 Feature KPI Component，不要创建全局 MetricCard。

## Toast 三页漂移

→ 检查 Toast Pattern、Absolute Position 和父级 Auto Layout，不逐页硬改坐标掩盖根因。

---

# 6. review-and-fix 后的 re-review

修复后至少复核：

```text
原 Finding 是否消失？
是否引入新的布局回归？
公共 Owner 的其它消费者是否仍正确？
Prototype Variable/Reaction 是否同步？
默认状态是否恢复？
旧字符串/旧组件扫描是否清零？
Design Context 是否看到正确结构？
```

如果修复公共组件影响多个页面，必须抽查所有关键消费者，不允许只看原问题页面。

---

# 7. Ready 输出

## `NOT_READY`

- 任意未解决 P0；
- 必需证据没有执行；
- 关键事实源无法读取。

## `READY_WITH_NOTES`

- P0 清零；
- 剩余问题不会阻止正确实施；
- Notes 已明确边界和后续处理。

## `READY`

- P0/P1 中影响正式实施的问题已清零；
- 必需 Screenshot / Prototype / Machine Audit / Design Context 有当前证据；
- 动态数据、组件和后端能力映射无未决项。

Figma `READY` 只代表设计可实施，不代表代码已完成、测试已通过或 PR 可合并。
