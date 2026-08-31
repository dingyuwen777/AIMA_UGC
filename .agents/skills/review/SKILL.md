---
name: review
description: 面向不同项目形态、编程语言和工具链的独立代码审查与测试充分性验证工作流。Review 不维护第二套编码规范；同仓存在 Coding Skill 时，先读取 Coding 并以其为唯一研发规范源，再独立重建需求与风险、审查 diff/实现/测试/文档、从测试专家视角设计最少充分验证、输出有证据的 Findings。支持 review-only、review-and-test、review-and-fix，并在修复时返回 Coding、修复后 re-review。Use for code review, pull request review, audit, test adequacy analysis, independent verification, regression-risk analysis, and review-driven fix loops across languages and project types.
---

<!-- agent-routing:v1
{"协议":"Agent Skills Skill路由/v1","Skill":"review","触发":{"任一":[{"包含":{"维度":"执行模式","取值":["审查"]}},{"包含":{"维度":"意图","取值":["代码审查","Review-only","Review-and-test","Review-and-fix","独立复核"]}}]}}
-->

# Review

Review 的职责不是再写一遍“怎样开发”，而是作为**独立审查者 + 测试专家**回答：

```text
上游要求到底是什么？
实现真的满足了吗？
现有测试真正证明了什么？
还存在哪些可触发、可解释、可验证的问题？
这些问题是否会阻塞合并、发布或交付？
```

核心链路：

```text
恢复当前事实与 Review Target
→ 读取适用项目规则
→ 同仓有 Coding 时读取 Coding 作为唯一研发规范源
→ 独立重建需求、风险和应有证据
→ 审查实现 / diff / 测试 / 文档
→ 从测试专家视角主动验证高风险假设
→ 输出 Findings 与证据边界
→ 有修复授权时返回 Coding 修复
→ 新鲜验证
→ Review re-review
```

Review **不复制** Coding 的编码、TDD、Git、兼容、安全、Contract、Schema/Migration、Validation Matrix、时间、日志或注释规范。它只定义“怎样独立审、怎样判断测试是否充分、怎样报告问题”。

详细方法位于 `references/`；命中对应场景时必须读取相关 reference。

## 1. 规则事实源与集成边界

### 1.1 同仓存在 Coding Skill

如果存在：

[`.agents/skills/coding/SKILL.md`](../coding/SKILL.md)

必须在正式 Review 前读取，并把它及其按任务触发的 references 作为**唯一研发规范源**。Review 不得把 Coding 的详细规则复制成第二份，也不得用 Review 自己的偏好覆盖项目事实。

Review 负责增加：

- 独立重建上游要求，而不是相信作者 Change/checklist；
- 以审查者视角重新判断风险和影响面；
- 测试充分性审计与主动验证；
- Findings 严重度、证据和可触发条件；
- Review Only / Test / Fix 三种权限模式；
- 修复后 re-review。

如果 Coding 存在但无法读取，必须明确报告阻塞；**不得宣称已经按 Coding 规范完成 Review**。

### 1.2 同仓没有 Coding Skill

Review 仍可独立使用，但只能依据：

```text
系统/用户指令
→ AGENTS.md / CONTRIBUTING / 项目本地规范
→ 当前需求/Spec/Contract/Schema/代码/测试/锁文件/CI
→ Review 自己的审查方法
```

此时不得发明不存在的 Coding 规则，也不得声称“符合 Coding Skill”。

### 1.3 与 Docs Skill

Review 发现技术文档缺陷时：

- 只读 Review：作为 Finding 报告；
- 已授权修文档且存在 [`.agents/skills/docs/SKILL.md`](../docs/SKILL.md)：按 Docs 的工作流处理，不由 Review 复制 Docs 写作规则；
- Docs 发现实现问题后仍返回 Coding，不由 Review 越权直接改生产实现。

## 2. 三种工作模式

### `review-only`（默认）

允许：

- 读取目标代码、diff、PR、需求、测试、配置、CI 和必要事实源；
- 运行当前授权与环境允许的已有验证；
- 输出 Findings、风险、测试缺口和未验证项。

不允许因为 Review 本身自动获得：

- 修改生产代码；
- 新增永久测试；
- 修改文档；
- commit / push / PR / merge / release / deploy 权限。

### `review-and-test`

在已有测试修改授权时，可：

- 为已确认风险增加最小验证或回归测试；
- 运行目标测试和相关验证；
- 用测试证明或推翻 Finding。

规则：

- 有长期回归价值的测试进入项目正式测试体系；
- 一次性调查脚本/实验没有长期价值时，不为了“留下 Review 痕迹”塞进永久测试目录；
- 新增测试不能降低原门禁、绕过真实依赖或用 Mock 冒充未运行边界；
- 如果测试暴露生产实现缺陷，停止在 Review 模式里改生产代码，转入 `review-and-fix` 的 Coding 修复链。

### `review-and-fix`

只有用户/上游任务已经明确授权修改实现时使用。

流程：

```text
先完成 Review 并形成 Finding
→ 建立/确认失败证据
→ 返回 Coding
→ 重新读取 `.agents/skills/coding/SKILL.md`
→ 按 Coding 的完整需求/TDD/调试/验证/Git 门禁修复
→ 取得本轮新鲜 Green 证据
→ 回到 Review
→ 对原 Finding 和受影响边界执行 re-review
```

Review 不维护另一套“快速修复流程”。未经授权不得因为发现问题就自动修改、提交或合并。

## 3. Review Target 必须明确

开始前先确定本次真正审什么：

- PR / merge request；
- branch 与 base 的 diff；
- commit range；
- working tree；
- 一个模块/文件；
- 一个已实现功能；
- 一次测试充分性审计；
- 一次全局代码质量/安全审计。

至少记录：

```text
Review Target
Base / Head（适用时）
授权模式
上游需求/Change/Spec
项目形态与实际工具链
风险等级与影响边界
需要读取的 Coding references（存在 Coding 时）
允许执行的测试/外部动作
```

Review 不能只看一个文件就推断整个调用链，也不能默认 PR 描述等于完整需求。

## 4. 独立重建，而不是复述作者结论

复杂 Review 必须先做两个方向：

```text
A1 上游要求 → 当前 Change/实现
A2 当前 Change/实现 → 测试/文档/运行证据
```

同仓 Coding 已定义 Requirement Traceability / Completion Audit 时，Review 直接执行这些现有规则，不复制第二套。

独立性要求：

- 不把 PR 描述、Change checkbox、作者说明或 CI 全绿当作需求全集；
- 从用户已确认决定、正式 Spec/Roadmap/Contract/Schema 和当前机器事实重新建立预期；
- 从入口向下追调用链，也从最终用户/consumer 结果反向追支持能力；
- 测试通过只能证明它实际运行与断言的范围。

## 5. 测试专家审查是 Review 的核心职责

读取 [03_测试专家审查方法.md](references/03_测试专家审查方法.md)。

Review 不是问：

> “有没有测试？”

而是问：

```text
需求有哪些可观察行为？
最高风险失败模式是什么？
现有测试分别证明了哪些边界？
哪些风险完全没有证据？
最小增加哪一层验证，就能证伪关键假设？
```

对真实存在 Web/Full-stack 边界的项目，同仓 Coding 的分层规则如果适用，要特别复核：

```text
Browser Mock Acceptance
Backend / API / PostgreSQL Integration
Contract / Generated Client
Real Full-stack Golden Path
Real Provider Probe
```

其中 Browser Mock 可以非常适合广覆盖**用户可见行为、状态和请求语义**，但不能被写成真实后端/数据库/Worker/Provider 证明；各层完整语义以 Coding 的当前 reference 为准。

Review 不设置固定测试数量配额，也不把所有状态复制成昂贵 Real Full-stack。测试成本必须与风险和证据价值匹配。

## 6. Findings 必须可执行、可验证

读取 [02_Findings与严重度.md](references/02_Findings与严重度.md)。

每个确定性 Finding 至少回答：

```text
严重度
位置 / 影响范围
问题是什么
触发条件
实际影响
证据
为什么现有测试没有挡住（适用时）
建议修复方向
需要增加/调整什么验证（适用时）
```

没有足够证据时写成“风险/待验证假设”，不要伪装成确定 Bug。

默认优先报告会影响：

- 正确性和业务语义；
- 数据一致性/事务/并发；
- 安全和权限；
- public API/ABI/CLI/Contract/Schema 兼容；
- 用户可见行为；
- 错误处理与恢复；
- 资源生命周期/性能；
- 可维护性和项目明确编码规范；
- 测试真实性和覆盖充分性。

纯风格偏好只有在项目已有明确规范或会产生实际维护风险时才形成 Finding。

## 7. 审查执行顺序

完整流程见 [01_审查执行流程.md](references/01_审查执行流程.md)。默认顺序：

```text
1. 恢复规则与 Review Target
2. 读取 diff 及直接调用链
3. 独立重建上游要求
4. 识别高风险不变量/失败模式
5. 审查现有测试与证据等级
6. 运行最少充分验证
7. 形成 Findings
8. 复查误报和证据边界
9. 按模式：报告 / 补测试 / 返回 Coding 修复
10. 修复后 re-review
```

Review 应优先找“如果错了会造成什么”的高价值问题，不以发现数量作为质量指标。

## 8. 证据和结论边界

任何结论必须区分：

- 已确认事实；
- 当前证据支持的 Finding；
- 合理但未验证的风险；
- 未能执行的验证。

禁止：

- 只看代码就声称测试通过；
- 用旧 CI 结果冒充当前 HEAD；
- 用 Browser Mock 冒充真实 Full-stack；
- 用 Fake/SQLite 冒充任务真正依赖的 Runtime/Persistence；
- 用一条 Golden Path 声称所有错误状态覆盖；
- 用真实 Provider Probe 替代稳定回归测试；
- 因 CI 全绿跳过 Requirement Completeness；
- 因测试失败就删除/跳过/降低断言；
- 为了 Review 完成感引入无关重构、依赖或测试框架。

## 9. 完成输出

至少给出：

```text
Review Target / Base / Head
模式与授权
读取的关键事实源
Findings（按严重度）
测试充分性结论
实际执行的验证与证据等级
未验证项及原因
是否阻塞合并/发布
如果执行了修复：Coding 修复摘要 + re-review 结果
```

没有 Finding 时也不能只写 `LGTM`；应说明审查范围、实际证据和仍未覆盖的边界。
