# Figma Skill

`figma` 是一个**跨项目通用**的 Figma 原型审查、设计系统一致性、页面可用性、Prototype QA 和 Design-to-Code 正式基线 Skill。

它可以安装在任意项目中使用，不依赖某个业务页面、某个后端实现或某一种前端技术栈。

它不是单纯做视觉点评，也不替代项目已有的 Coding、Docs 或 Code Review 工作流。

## 1. 定位

```text
项目研发规则 / Coding
→ 定义怎样开发、验证、Git 和交付

Docs
→ 负责长期文档事实同步

Code Review
→ 负责实现和测试的独立审查

Figma
→ 负责设计事实、页面可用性、Prototype、真实系统能力映射、组件/业务逻辑复用和 Design-to-Code Ready 审查
```

有代码仓库时，Figma Skill 先读取项目规则和当前机器事实；没有代码仓库时，也可以用于 Design-only 原型审查，但不能把未来实现假设成“系统当前已支持”。

精确规则见 [`SKILL.md`](SKILL.md)。

## 2. 适用项目

包括但不限于：

- Web 应用；
- 移动端 App；
- 桌面端 App；
- 内部管理系统；
- 数据看板；
- 表单/工作流；
- 内容/媒体产品；
- 电商/交易产品；
- 营销/品牌站；
- 静态站；
- 设计系统/组件库；
- 尚未编码的产品原型。

Skill 会先识别项目形态，再决定哪些审查项适用，不会机械要求所有项目都有 API、数据库、Route 或后台任务。

## 3. 三种模式

### `review-only`

用于普通设计审查，不修改设计；Design-only 且没有目标实现事实时通常默认此模式。

“只检查、不修改”首先限制的是写权限。如果用户明确要求判断“是否可作为正式开发基线”，仍然执行只读的 `baseline-ready`，不会因为只读要求而降级成普通 `review-only`。

### `review-and-fix`

用户明确要求“检查并修好 / 有问题直接修改 Figma”时使用。

```text
确认根因
→ 修改最小公共 Owner
→ 验证所有消费者
→ Fresh Screenshot
→ Prototype / Machine Audit
→ Design Context re-review（适用时）
```

### `baseline-ready`

用于正式判断一个页面是否能成为实现方的开发事实源。

最终只输出：

```text
READY
READY_WITH_NOTES
NOT_READY
```

没有实际完成必要验证时不得给 `READY`。

## 3.1 不需要记模式名

高频自然语言会自动路由：

| 你说的话 | 默认流程 |
| --- | --- |
| `全面检查这个 Figma：<link>` | 有实现仓库时 `baseline-ready`；Design-only 时 `review-only` |
| `全面检查并修好这个 Figma：<link>` | `review-and-fix` → re-review → Readiness |
| `对照当前仓库全面验收这个 Figma：<link>` | `baseline-ready` |
| `按这个 Figma 替换当前对应页面：<link>` | `baseline-ready` → 项目 Coding handoff → 实现后 targeted re-review |

模式和权限分开判断：

- 说“只检查、不修改”就不写 Figma，但不改变已经明确的正式验收目标；
- 说“有问题直接改”才获得本轮 Figma 写授权；
- 说“按这个 Figma 替换/实现现有页面”表示需要修改目标实现，但 commit、PR、merge、release 仍按项目 Coding 工作流和用户授权判断；
- Design-to-Code 进入生产代码后，Change/TDD/Review/CI/Git 继续服从目标项目自己的 Coding 工作流。

因此后续通常只需要提供：

```text
Figma 链接
+
目标仓库/实现上下文（需要对照代码或实施时）
+
一句自然语言目标
```

不需要重复粘贴页面尺寸、组件复用、Prototype、动态数据和后端接线等长约束。

## 4. 它会自动检查什么

### 页面美观和真实可用性

- Frame 尺寸是否符合目标设备/浏览器；
- 设计基准是否被误当成生产固定宽高；
- Page Header、Content、Card、Table 是否对齐；
- 区块、按钮、字段之间间距是否稳定；
- 图片比例、裁切和清晰度是否合理；
- 图片、文字、按钮、Badge、开发标注是否重叠；
- 图表 Label、Legend、Tooltip 是否遮挡；
- 长文本、极端数据、空数据是否会把布局撑坏；
- Modal/Drawer/Toast/Dropdown 是否裁切、漂移或双层滚动；
- Prototype 是否需要人工缩放才能正常查看。

### 用户任务和操作习惯

- 用户来这里要完成什么；
- 高频操作是否容易找到；
- 字段顺序是否符合依赖关系；
- 固定选项是否错误设计成自由输入；
- 默认值是否有真实依据；
- 危险操作是否有清晰反馈；
- 操作完成后用户能否找到最终结果。

### 真实系统能力和动态数据

- 字段、按钮、状态是否有真实系统能力支持；
- 动态值来自 API、SDK、CMS、本地状态、设备能力还是后台任务；
- 最终来自数据库的数据是否通过正式 Service/API/SDK 链路进入客户端；
- 示例数据是否被明确标为设计示例；
- 是否由设计稿创造了系统当前不存在的选项或状态。

### 公共组件和业务逻辑复用

- Button、Input、Select、Feedback、Modal 等稳定模式是否真正复用公共组件；
- Component Property 是否被外覆 Text 绕过；
- 同一业务资格、状态映射、动态字段生成、校验或默认值规则是否被多个页面重复实现；
- 业务逻辑是否有唯一 Owner；
- Feature 内公共逻辑是否被错误提升成全局万能组件；
- 不同语义是否为了“复用率”被错误合并。

### Prototype

- Flow Starting Point；
- Variable 默认值；
- Reaction / SET_VARIABLE；
- Toast / Overlay / Drawer / Dropdown；
- 旧数据回弹；
- 双文字、双图标；
- 浮层位置漂移；
- 失效 Destination；
- 演示是否伪造真实系统成功。

### Design-to-Code

- 实现方实际读取到的 Design Context 是否正确；
- 正式 Frame 与历史/备份是否分清；
- 动态数据是否有 Annotation；
- Shared / Feature / Page Owner 是否明确；
- 目标技术栈是否来自当前项目，而不是 Figma 工具示例代码；
- 用户要求实现/替换现有页面时，是否先通过 Ready 门禁，再交给目标项目 Coding 工作流。

## 5. 最短使用方式

### 全面检查

```text
@Figma @GitHub
全面检查这个 Figma：<链接>
```

### 检查并直接修好

```text
@Figma @GitHub
全面检查并修好这个 Figma：<链接>
```

### 对照仓库做正式开发基线验收

```text
@Figma @GitHub
对照当前仓库全面验收这个 Figma：<链接>
```

### 用 Figma 替换现有页面

```text
@Figma @GitHub
按这个 Figma 替换当前对应页面：<链接>
```

如果目标仓库、分支或最终是否需要 PR/merge 无法从当前上下文确定，再补这些真正影响执行边界的信息；不要重复 Skill 已经固化的审查清单。

## 6. 文件结构

```text
figma/
├── SKILL.md
├── README.md
├── agents/
│   └── openai.yaml
└── references/
    ├── 00_通用适用性与项目形态.md
    ├── 01_事实源与审查流程.md
    ├── 02_业务能力与真实系统映射.md
    ├── 03_设计系统与组件复用审计.md
    ├── 04_Prototype状态与交互审计.md
    ├── 05_Design-to-Code交付门禁.md
    ├── 06_Findings与修复优先级.md
    └── 07_页面布局与真实可用性审计.md
```

`README.md` 只用于快速说明；真正约束以 `SKILL.md`、命中的 references、当前项目规则和当前机器事实为准。

## 7. 不做什么

Figma Skill 不应该：

- 把某个项目的字段、平台、尺寸或技术栈当通用标准；
- 只看截图就宣称设计正确；
- 从历史聊天猜当前系统能力；
- 用 Figma 替代 Contract/API/SDK/Runtime；
- 自动获得未明确授予的 Figma、commit、PR、merge 或 release 权限；
- 在用户未要求修改目标实现时自动改生产代码；
- 为了“公共化”把所有业务组件升成全局组件；
- 把同一业务逻辑复制到多个页面；
- 把业务规则塞进 Button/Input 等基础视觉组件；
- 忽略页面尺寸、滚动、图片/标注重叠和真实长文本；
- 机械翻译所有英文或机械暴露所有技术名；
- 因为 Figma 工具返回某种示例代码就改变目标项目技术栈；
- 未验证 Prototype、关键视觉状态和真实系统边界就说“可以交付实现”。