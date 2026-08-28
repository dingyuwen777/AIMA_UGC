# Figma Skill

`figma` 是 AIMA_UGC 中专门用于 **Figma 原型审查、设计系统一致性、Prototype QA 和 Design-to-Code 正式基线验收** 的 Skill。

它不是单纯做视觉 Review，也不替代 Coding、Docs 或 Review。

## 1. 定位

```text
Coding
→ 定义怎样可靠开发、验证、Review、Git 和交付

Docs
→ 负责技术文档事实同步与写作

Review
→ 负责代码独立审查与测试充分性

Figma
→ 负责设计事实、Prototype、后端能力映射、组件复用和 Design-to-Code Ready 审查
```

同仓存在 `.agents/skills/coding/SKILL.md` 时，Figma 先遵守 Coding 和项目规则；发现生产实现问题时返回 Coding，不自行建立另一套代码修复流程。

精确规则见 [`SKILL.md`](SKILL.md)。

## 2. 三种模式

### `review-only`

默认。只审查 Figma 与当前仓库事实，不修改设计。

适合：

- “检查这个 Figma 页面还有什么问题”；
- “这个页面能交给 Codex 吗”；
- “这个字段和后端真的对应吗”。

### `review-and-fix`

已明确授权修改 Figma 时使用。

固定流程：

```text
先审查根因
→ 修改最小 Owner
→ Fresh Screenshot
→ Prototype / Machine Audit
→ Design Context re-review
```

### `baseline-ready`

用于正式判断一个 Figma Frame 是否可作为 Codex/Agent 的开发事实源。

最终只输出：

```text
READY
READY_WITH_NOTES
NOT_READY
```

没有实际完成必要验证时不得给 `READY`。

## 3. 它会自动检查什么

### 事实和后端能力

- Figma 字段是否真的有 Contract/Store/API 支持；
- 动态数据来自 API、服务器还是只是设计示例；
- Capability/Provider/Scheduler 等是否真实支持设计行为；
- Figma 是否创造了后端不存在的选项。

### 产品语言

- 后端实现名是否无意义暴露给业务用户；
- 是否机械中文化 `v4`、产品型号等有真实使用价值的表达；
- UI 产品语言和机器字段之间是否有清晰 Annotation 映射。

### 设计系统

- Sidebar、TopBar、Button、Input、Select、Feedback 等是否真复用；
- Feature Component 是否被错误提升成万能 Shared；
- Component Property 是否被外覆 Text 绕过；
- Token、Icon、Auto Layout 是否一致。

### Prototype

- Flow Starting Point；
- Variable 默认值；
- Reaction / SET_VARIABLE；
- Toast / Overlay / Drawer / Dropdown；
- 旧测试数据回弹；
- 双文字、双图标、位置漂移；
- 失效 Destination。

### Design-to-Code

- Codex 实际读取到的 Design Context 是否正确；
- Figma 示例是否会被误实现成生产常量；
- Target IA 是否与当前真实 Route 分层；
- MCP 的 React/Tailwind 示例是否被正确当成参考，而不是反向改变仓库技术栈。

## 4. 常见使用方式

### 全面检查并修复

```text
@Figma @GitHub
使用 figma skill，以 review-and-fix 检查“采集策略”页面。
对照当前仓库真实 Contract、Store、Capability 和后端实现；有问题直接修 Figma，最后判断是否达到 Codex 正式开发基线。
```

### 只审查

```text
@Figma @GitHub
使用 figma skill，以 review-only 审查这个页面。
不要修改 Figma，只输出 P0/P1/P2 Findings 和 Readiness。
```

### 正式交付 Codex 前验收

```text
@Figma @GitHub
使用 figma skill，以 baseline-ready 验收这个页面。
必须检查 Prototype、动态数据、组件复用、后端能力映射、Fresh Screenshot 和 Design Context。
```

## 5. 文件结构

```text
figma/
├── SKILL.md
├── README.md
├── agents/
│   └── openai.yaml
└── references/
    ├── 01_事实源与审查流程.md
    ├── 02_业务能力与前后端映射.md
    ├── 03_设计系统与组件复用审计.md
    ├── 04_Prototype状态与交互审计.md
    ├── 05_Design-to-Code交付门禁.md
    └── 06_Findings与修复优先级.md
```

`README.md` 只用于说明和快速使用；真正约束以 `SKILL.md`、命中的 references、项目 `AGENTS.md` 和当前机器事实为准。

## 6. 不做什么

Figma Skill 不应该：

- 只看截图就宣称设计正确；
- 从历史聊天猜当前后端；
- 用 Figma 替代 Contract/Schema；
- 自动获得生产代码修改权限；
- 自动获得 commit/PR/merge 权限；
- 把所有业务块都抽成全局组件；
- 为了“全中文”机械翻译版本号/型号/必要专名；
- 因为 MCP 返回 React/Tailwind 就改变项目技术栈；
- 未验证 Prototype 和 Design Context 就说“可以交 Codex”。
