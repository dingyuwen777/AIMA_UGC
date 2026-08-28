# Figma Design-to-Code 交付门禁

这份 reference 负责判断一个 Figma 页面是否已经可以作为 Codex 或其他 Coding Agent 的正式开发基线。

核心原则：

> 视觉接近不是 Ready；只有设计结构、真实业务能力、Prototype、状态和目标代码边界都可无歧义映射时，才可以交付。

---

# 1. 正式基线的四层一致性

必须同时成立：

```text
设计视觉
↕
Figma 结构 / Component / Prototype
↕
后端 Contract / Capability / 状态机
↕
目标仓库 Page / Store / API / Shared UI
```

缺任一层都不能直接宣称 Ready。

---

# 2. 开发前必须重新读取当前仓库

Design-to-Code 开始时重新读取：

```text
AGENTS.md / 项目规则
→ Coding Skill
→ 当前 Route / Page
→ Feature Store / API
→ Generated Client / Public Contract
→ Shared UI / App Shell / Token
→ 目标 Figma Design Context
```

不能因为 Figma 审查是在昨天完成，就用聊天记忆替代当前仓库事实。

---

# 3. Design Context 是主结构证据

正式实现前必须对目标 Node 获取 Design Context。

它主要用于确认：

- Codex 实际会看到哪些节点；
- 是否识别成公共 Component Instance；
- Component Property 是否正确；
- Annotation 是否可读；
- 是否仍有隐藏旧文案或重复 DOM 结构；
- Figma 返回的参考代码表达了什么布局意图。

Screenshot 只能作为视觉补充，不能代替 Design Context。

---

# 4. MCP 参考代码不能反向改变技术栈

Figma MCP 可能输出：

```text
React
Tailwind
某个示例 UI Library
```

目标仓库如果是 Vue/CSS Modules/原生 CSS/其它技术栈，必须适配当前真实栈。

禁止：

```text
为了复制 MCP 代码
→ 安装 Tailwind
→ 新增 React
→ 绕过当前 generated client
```

除非有独立技术决策批准。

---

# 5. Shared / Feature / Page 映射

实现前建立映射表：

| Figma Pattern | 代码 Owner | 动作 |
| --- | --- | --- |
| App Shell | app/shared | 复用或升级唯一 Owner |
| Button/Input/Select | shared | 复用同一公共实现 |
| Feature KPI | feature | 不升成万能全局组件 |
| Page Table | feature/page | 按业务语义实现 |

如果两个待替换页面使用同一 Figma 公共组件，代码侧也不应各写一套近似实现。

但设计系统和代码组件不要求机械 1:1；以真实复用边界为准。

---

# 6. 动态数据门禁

Design Context 中的示例：

```text
24 条
v4
主采集渠道
2026/8/28 09:00
```

只能决定排版。

实现时必须追到：

```text
Store / API / generated client / server runtime
```

禁止：

- 把示例数量硬编码；
- 把示例 Provider 名写成固定渠道；
- 把示例 UUID 写成业务 ID 规则；
- 把 Figma 下拉选项当后端枚举全集。

---

# 7. Annotation 应承担“翻译层”

Figma UI 使用产品语言，Annotation 可以写机器映射。

例如 UI：

```text
采集渠道
```

Annotation：

```text
display_name 来自 provider_configs
提交 provider_config_id
```

这能让设计不暴露内部实现，同时让 Codex 有明确接线证据。

Annotation 不应复制完整 OpenAPI Schema。

---

# 8. Target IA 与 Route

Figma 可以表达未来信息架构。

代码只接当前真实 Route：

```text
Figma future nav item
→ 不自动创建 Route
→ 不生成 placeholder page
→ 不生成死链
```

未来 Feature 真正实现后，再同步：

```text
Feature → Page → Route → App Shell → Test
```

---

# 9. 状态交付

Codex 至少应能找到：

```text
Normal / Data
Loading
Empty
Error
Disabled（业务需要时）
```

异步 Feature 按真实状态机补：

```text
Creating / Uploading / Running / Partial / Retry / Cancelled
```

不要求所有状态都进入主 Prototype 流程；可以放在独立开发状态规格区，但必须可见、可定位。

---

# 10. Ready 判定

## `NOT_READY`

存在任何 P0，例如：

- 后端不支持设计行为；
- 字段事实源不明；
- Prototype 会回弹旧数据；
- 关键公共组件是假复用；
- Codex 读取到重复 Text/错误 DOM；
- 缺关键状态；
- 有 Secret/内部敏感信息泄露风险。

## `READY_WITH_NOTES`

无 P0，但存在不会阻塞正确实现的 P1/P2，并且已经明确落地注意事项。

## `READY`

必须有当前轮证据支持全部硬门禁。

---

# 11. Baseline Ready Checklist

```text
[ ] Review Target 唯一明确
[ ] 当前仓库事实已重新读取
[ ] 用户输入全部有真实后端支持
[ ] 动态字段都有 API/Runtime 来源
[ ] SYSTEM_FIXED 不伪装成可编辑字段
[ ] 示例数据不冒充服务器事实
[ ] 关键示例跨页面一致
[ ] 公共组件真实复用
[ ] Component Property 无外覆 Text
[ ] Token 无明确语义漂移
[ ] Prototype Variable 默认值正确
[ ] Reaction 无旧数据/旧术语
[ ] Flow 无失效目标
[ ] 浮层定位和滚动正确
[ ] 关键状态覆盖完整
[ ] 产品语言不暴露无价值实现细节
[ ] Target IA / Route 边界明确
[ ] Fresh Screenshot 已检查
[ ] Machine Audit 已检查
[ ] Design Context 已从 Codex 视角检查
```

任何必需项没有实际执行时，不能用“应该没问题”补证据。

---

# 12. 后续 Coding Handoff

Ready 后给 Coding Agent 的交付说明至少包含：

```text
正式 Figma Node
对应 Route / Feature
必须复用的 Shared Component
必须保持的 Store/API/Contract 行为
动态数据来源
Feature Component 边界
Prototype/状态规格入口
已知非阻塞 Notes
```

然后 Coding 重新进入自己的 Change/TDD/Validation/Review/CI 门禁。

Figma Skill 的 READY 只证明设计基线可以实施，不证明代码已经实现或可合并。
