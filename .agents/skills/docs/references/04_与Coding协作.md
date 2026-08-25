# 与 Coding 协作

Docs 和 Coding 解决的是两个不同问题：

```text
Coding
→ 怎样可靠地完成软件研发、验证和交付

Docs
→ 怎样保证技术文档与正确事实同步，并让读者真正看懂
```

不要把两套规则复制到彼此内部。Coding 只负责判断是否存在文档影响和何时路由；Docs 负责文档事实、写作和审查方法。

## 1. Coding 先做轻量 Docs Impact

代码、配置、Contract、数据或运行行为变化后，Coding 先判断：

```text
这次变化是否改变了人类需要理解、使用、维护、部署或排障的事实？
```

### 没有影响

记录：

```text
Docs Impact: not_applicable
Reason: <具体事实依据>
```

然后结束文档分支，不加载 Docs，不制造无意义 Markdown diff。

### 有影响

Coding 读取：

```text
.agents/skills/docs/SKILL.md
```

并提供最少充分交接信息：

```text
变化目标
实际变更边界
已确认事实源
可能受影响的模块/接口/配置/用户行为
候选文档（如果已知）
```

Coding 给出的候选文档只是线索，不是必须修改清单。

## 2. Docs 决定 targeted 还是 full

默认：

```text
Docs Impact: targeted
```

只有 Docs 根据真实变化判断影响跨越完整长期文档域时，才升级为：

```text
Docs Impact: full
```

这样可以避免“每改一行代码都扫全仓文档”。

## 3. Docs 自己确定需要读和改什么

Docs 不接受这样的机械逻辑：

```text
Coding 猜 README、Blueprint、API 文档都可能受影响
→ 三份都必须改
```

正确流程：

```text
逐份确认它是否承担这个事实
→ 已经正确：不改
→ 与正确事实不一致：改
→ 不负责这个事实：不改
→ 机器事实已有唯一来源：必要时只改解释/导航
```

## 4. Docs 发现代码问题时返回 Coding

典型情况：

```text
正式 Contract / 已批准设计要求 A
当前代码实现 B
文档写 A
```

Docs 不应为了表面一致把文档改成 B。

必须先输出：

```text
code_issue_detected
→ 正确事实及其来源
→ 当前实现冲突位置
→ 返回 Coding 的原因
```

然后执行反向硬路由：

- 如果同仓存在 `.agents/skills/coding/SKILL.md`，在任何实现代码修改之前**必须读取**该 Skill，并切回 Coding 的完整需求、风险、调试/TDD、验证、Review、Git 和完成门禁；
- Docs 自己不得用文档规则直接修实现，也不得因为用户同时要求“修文档”就绕过 Coding；
- 如果 `.agents/skills/coding/SKILL.md` 不存在、无法读取，或当前任务没有代码修改授权，则只报告 `code_issue_detected` 和证据，不修改实现；
- Coding 完成修复并取得新鲜验证后，再执行：

```text
Docs targeted re-review
```

只复核原受影响内容，不重新做无边界 full review。

## 5. 防止无限循环

默认最多形成一次明确回交：

```text
Coding
→ Docs
→ code_issue_detected
→ 读取 .agents/skills/coding/SKILL.md
→ Coding 修复
→ Docs targeted re-review
```

如果第二次复核仍发现新的业务决定、Contract 冲突或范围扩大，不继续自动往返，而是回到上游需求/决策流程重新界定任务。

## 6. Coding 的完成门禁保持原样

Docs 不替代 Coding 已有的：

- Requirement Traceability；
- Change / Completion Audit；
- TDD / 根因调试；
- Validation Matrix；
- Code Review；
- Git / PR / CI；
- 安全、兼容、部署与回滚；
- 新鲜证据要求。

Coding 现有“文档与代码/Contract 尚未同步时不得 Ready/完成”的规则仍然有效。

Docs 只补充：**怎样判断影响、怎样正确审查/编写文档、怎样避免第二套事实、怎样让文档真正可读。**

## 7. 直接使用 Docs

用户也可以不经过代码开发，直接要求：

```text
检查现有技术文档
补一个模块 README
把一份架构说明改得更容易理解
核对文档和代码是否一致
```

这种情况下直接执行 Docs 的 Review Only / Review + Fix / Write / Update。

但项目如果通过 `AGENTS.md` 或其他上位规则要求所有仓库任务先经过 Coding 的事实恢复/风险/Git 路由，仍先遵守项目规则；直接使用 Docs 不等于绕过项目门禁。

如果 Docs 在直接任务中发现实现问题，也仍遵守第 4 节：存在 Coding Skill 时先切回 Coding，再允许修改实现。

## 8. 推荐交接结果

不要求固定 YAML Contract，但语义上至少清楚表达：

```text
Docs Impact: not_applicable | targeted | full
事实源：实际读取了什么
受影响文档：实际确认了什么
修改：哪些文件为什么改
无修改：哪些候选文档为什么不需要改
code_issue_detected：有/无；有则给事实源和冲突位置
Coding route：不适用 / 已读取并切回 / 不可用而停止实现修改
验证：实际执行了什么
未验证：还剩什么
```

这足以让 Coding 在 Completion Audit 中判断文档是否真正闭环，同时不会引入一套新的复杂协议。
