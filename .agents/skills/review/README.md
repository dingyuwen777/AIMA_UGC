# Review Skill

`review` 是一个通用代码审查 Skill，用于从**独立审查者和测试专家**视角检查实现是否满足需求、编码规范是否被遵守、测试是否真正覆盖关键风险，以及当前证据是否足以支持“可合并/可交付”等结论。

它的定位不是再维护一套开发规范。

## 1. 定位

```text
Coding
→ 定义怎样可靠开发：需求、TDD、调试、兼容、Contract、Schema、Git、验证、交付

Review
→ 独立检查 Coding 是否真的做到了，并主动验证测试充分性

Docs
→ 负责技术文档的事实同步、审查、编写和修复
```

同仓存在 `.agents/skills/coding/SKILL.md` 时，Review 必须读取 Coding，并把 Coding 作为**唯一研发规范源**。Review 不复制 Coding 的详细规则，只增加审查方法、Findings、测试专家分析和 re-review 闭环。

精确规则请看 [`SKILL.md`](SKILL.md)。

## 2. 三种模式

### `review-only`

默认模式。只审查、运行已有且允许的验证、输出 Findings，不自动获得改代码、写测试、提交或合并权限。

适合：

- PR Review；
- 分支/commit diff 审查；
- 代码质量审计；
- 测试充分性审计。

### `review-and-test`

在已有测试修改授权时，可以补充最小测试来证明或推翻风险，但不直接修改生产实现。

适合：

- “从测试专家角度检查这个功能”；
- “现有测试是不是漏了边界”；
- “帮我给这个 PR 补回归测试”。

### `review-and-fix`

已经明确授权修复时使用。

流程不是 Review 自己直接改生产代码，而是：

```text
Review 发现 Finding
→ 返回 Coding
→ Coding 按完整研发门禁修复并验证
→ Review re-review
```

这样避免 Review 和 Coding 形成两套实现规则。

## 3. Coding 怎样路由到 Review

在同时安装 Coding + Review 的仓库中：

```text
普通 Coding 实现任务
→ Coding 完成开发与验证
→ 进入完成前 Review
→ 强制读取 review/SKILL.md
→ Review 独立复核

显式 Code Review / Audit
→ Coding 先恢复仓库事实并完成四维路由
→ 立即切入 Review
```

如果 Review Skill 不存在，Coding 保留自己的原 Review 能力；如果 Review 文件存在但无法读取，则不能假装 Review 已完成。

这条硬路由写在 Coding Skill 正文和任务路由 reference 中，不依赖某个宿主是否读取 agent metadata。

## 4. 测试专家方法

Review 不是先问“测试有没有绿”，而是：

```text
需求有哪些可观察行为？
→ 最高风险失败模式是什么？
→ 现有测试分别运行了哪些真实边界？
→ 哪些风险没有证据？
→ 最小增加哪一层测试最能证伪关键假设？
```

详细方法见 [`references/03_测试专家审查方法.md`](references/03_测试专家审查方法.md)。

对真实 Web/Full-stack 项目，Review 会按项目现有 Coding 分层检查：

- `Browser Mock Acceptance`：非常适合广覆盖用户可见状态、交互和前端请求语义；
- `Backend / API / PostgreSQL Integration`：证明真实服务器规则和持久化；
- `Contract / Generated Client`：防止前后端机器接口漂移；
- `Real Full-stack Golden Path`：用少量关键路径证明真实组件接线；
- `Real Provider Probe`：只有确实需要验证外部供应商当前事实时才有界执行。

这些名称和完整职责以 Coding 当前规则为准；Review README 不复制第二套定义。

## 5. Findings 怎么写

Review 不是输出“建议优化”这种模糊意见。

一个有效 Finding 应回答：

```text
严重度
位置/范围
问题
触发条件
实际影响
证据
测试缺口
最小修复方向
验证建议
```

严重度和输出方法见 [`references/02_Findings与严重度.md`](references/02_Findings与严重度.md)。

## 6. 常见使用方式

### 审查 PR

```text
使用 review-only 审查当前 PR。
先恢复上游需求和 Coding 规则，再检查 diff、调用链、测试充分性和兼容风险。
只报告 Findings，不修改代码。
```

### 从测试专家角度验收前后端功能

```text
使用 review-and-test。
重点检查用户可见行为、Browser Mock、真实 Backend/API、Contract 与少量 Full-stack Golden Path 是否分别有匹配证据。
发现缺口时补最小长期回归测试；不要用 Browser Mock 冒充真实后端闭环。
```

### 审查并修复

```text
使用 review-and-fix。
Review 先形成有证据的 Finding；生产实现修改必须返回 Coding；修复并取得新鲜验证后再次 Review。
```

## 7. 文件结构

```text
review/
├── SKILL.md
├── README.md
├── agents/
│   └── openai.yaml
└── references/
    ├── 01_审查执行流程.md
    ├── 02_Findings与严重度.md
    └── 03_测试专家审查方法.md
```

`README.md` 只用于说明和导航；真正约束以 `SKILL.md`、适用 references、项目本地规则和同仓 Coding Skill 为准。

## 8. 不做什么

Review 不应该：

- 复制一套 Coding 编码规范；
- 因为“最佳实践”强迫项目更换框架、依赖或架构；
- 固定要求每个项目跑 Browser/数据库/Full-stack；
- 把所有场景做成昂贵端到端；
- 把 Mock/Fake 证据夸大成真实依赖证据；
- 为了 Finding 数量报告个人风格偏好；
- 未经授权改代码、提交、合并或发布。

Review 的目标是提高发现缺陷和验证不足的概率，同时保持流程按风险分层，不把开发工作机械加重。
