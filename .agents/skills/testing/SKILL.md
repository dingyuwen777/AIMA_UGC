---
name: testing
description: 面向不同项目形态、语言和工具链的独立测试策略与测试执行工作流。Testing 是 Test Strategy、Scenario-based Black-box Acceptance、User Journey、Exploratory Testing、Integration/Workflow/Golden Path/External Probe 与 Regression 方法的专业 Owner；Coding 保留开发期 TDD 与验证治理，Review 保留测试充分性和证据审查。Use for functional testing, black-box testing, user journey acceptance, exploratory testing, regression testing, test strategy, independent verification, test implementation, and test execution across project types.
---

<!-- agent-routing:v1
{"协议":"Agent Skills Skill路由/v1","Skill":"testing","触发":{"包含":{"维度":"意图","取值":["测试策略","功能测试","黑盒测试","用户场景验收","探索式测试","回归测试","测试充分性验证","Review-and-test","独立验证"]}}}
-->

# Testing

Testing 回答的核心问题是：

> **从真实调用者或用户可观察角度，这个功能、修复或系统行为到底能不能工作，现有证据还缺什么？**

Testing 不把“测试”收缩成单元测试，也不默认把所有场景升级成昂贵 E2E。它根据当前 Requirement、风险、项目形态、真实依赖和授权，选择最少但充分的验证层，并把测试结果与其实际证明边界严格对应。

**Testing 只在出现真实测试意图时命中。** `能力=测试` 只表示当前宿主具备测试能力，不等于每个开发任务都必须进入 Testing；`项目形态=Web/CLI/...` 只决定命中 Testing 后怎样映射公开入口，也不能单独触发 Testing。

核心链路：

```text
恢复 Requirement / 项目事实 / Test Target
→ 建立风险与可观察行为
→ 选择最小充分测试层
→ 设计 User Journey / Black-box / Integration / Regression 等场景
→ 执行或实现测试
→ 记录新鲜 Evidence 与未验证边界
→ 发现生产缺陷时 Handoff → Coding
→ 修复后 Regression
→ 需要独立合并判断时 Handoff → Review
```

## 1. Ownership 边界

### Testing 唯一负责的专业方法

- Test Strategy 与 Test Gap 设计；
- Scenario-based Black-box Acceptance；
- User Journey / Workflow Acceptance；
- Exploratory Testing；
- Integration / Runtime Dependency 测试方法；
- Contract/Consumer 验证的测试设计；
- Real Cross-component Golden Path 的测试设计与执行；
- External Dependency / Provider Probe 的测试设计与执行边界；
- Bug reproduction、Regression 与缺陷复测；
- 测试数据、Fixture、Fake、Mock、Harness 的测试工程方法；
- 测试执行证据与证据等级陈述。

### Coding 保留

Coding 仍负责：

- 开发期 `Red → Verify Red → Green → Refactor → Re-verify`；
- 实现代码和生产缺陷修复；
- Requirement Traceability / Validation Matrix / Completion Gate 等研发治理；
- 决定一次交付必须证明哪些独立失败边界；
- 在开发闭环中编写与实现紧耦合的最小单元/组件回归测试。

**Testing 不复制第二套 Coding 实现、Change、Git、CI、Release、Contract/Schema/Migration 或生产修复规则。**

### Review 保留

Review 仍负责：

- 独立重建上游要求；
- 审查实现、风险、Findings；
- 判断现有测试和 Evidence 是否充分；
- 判断哪些测试缺口会阻塞合并/发布；
- 修复后 re-review。

Review 需要新增测试、系统性黑盒/探索式测试或复杂测试设计时，Handoff 到 Testing；Review 不维护第二套测试工程方法。

## 2. Testing 工作模式

### `test-only`（默认）

允许读取需求、实现、Contract、测试、配置和必要运行事实，运行已有非破坏性测试并输出结果。默认不修改生产代码，不自动获得 Git/PR/merge/release/deploy 权限。

### `test-and-add`

在已授权修改测试资产时，可新增或调整：

- test code；
- fixture / fake / mock；
- test harness；
- 隔离的测试数据和测试配置。

新增测试必须进入项目已有测试体系；没有长期回归价值的一次性调查实验不为了留痕硬塞进永久测试目录。

### `test-and-fix`

Testing 自身不维护生产修复流程。发现确定生产缺陷后：

```text
可复现失败证据
→ Handoff Coding
→ Coding 最小修复并取得 Green
→ 返回 Testing 执行 Regression
→ 需要独立判断时返回 Review
```

只有用户明确授权完整修复链时才允许跨 Skill 继续；权限不会因为 Testing 发现 Bug 自动扩大。

## 3. Test Target 必须明确

至少恢复：

```text
Test Target：feature / bug / workflow / PR / build / release artifact / external boundary
Requirement Source / 预期可观察行为
项目形态与真实工具链
真实入口、依赖和环境
风险等级与失败边界
允许修改哪些测试资产
允许执行哪些真实依赖/外部 Probe
```

不能只看测试文件名称推断测试对象，也不能从 Mock 反向发明生产 Contract。

## 4. 先从用户/调用者行为出发

对用户可见 L2/L3 Feature 或 Bug，只要存在真实公开入口且没有明确不适用依据，应优先建立至少一个从真实入口出发的 Workflow/Black-box 证据。

Testing 先问：

```text
谁在使用？
他要完成什么目标？
前置状态是什么？
按什么步骤操作？
最终能观察到什么？
失败、空状态、重试、返回、刷新、重复操作时应怎样？
```

不要先从内部 class/function 调用顺序生成所谓“用户测试”。

详细场景方法见 当前场景所需完整约束。

## 5. 分层测试与证据

读取 当前场景所需完整约束。

Testing 依据真实风险选择：

```text
Behavior / Unit / Component
Contract / Consumer
Integration / Persistence / Runtime Dependency
User / Workflow Acceptance
Real Cross-component Golden Path
External Dependency Probe
Build / Package / Runtime
```

不是每个任务都必须具备所有层；任一层只允许声明它实际运行过的边界。

## 6. 缺陷、回归与回程

Bug、Review Finding、生产问题或 Testing 发现的确定缺陷，读取 当前场景所需完整约束。

Testing 的高价值结果不是“跑了很多 case”，而是：

- 可稳定复现风险；
- 可观察预期明确；
- 失败证据能区分代码、环境和外部依赖；
- 修复后同一路径回归；
- Evidence 不夸大。

## 7. 完成输出

至少说明：

```text
Test Target / Requirement Source
模式与授权
覆盖的 User Journey / Risk
实际执行的测试层
通过 / 失败 / 跳过数量（能取得时）
每类证据实际证明什么
Defects / Risks / Test Gaps
未验证项及原因
是否需要 Coding 修复
是否需要 Review 独立判断
```

禁止用 `E2E 全通过`、`系统完整验证`、`功能没问题` 等强结论覆盖未实际运行的边界。