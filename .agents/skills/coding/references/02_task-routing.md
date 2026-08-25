# 跨项目研发任务路由

这份规则负责在任何仓库中回答一个前置问题：**本次任务到底应该加载哪些研发流程，而不是把所有规则机械套在所有项目上？**

它不是新的架构规范，也不是语言最佳实践清单。它把 Reliable Vibe Coding 的固定质量门禁与项目真实形态、当前研发阶段、实际编程语言/工具链和任务风险组合起来，使同一套 Skill 可以用于 Library、CLI、Web、Backend、Mobile、Data、Embedded、Infra、Monorepo 等不同项目。

## 1. 路由原则

每次独立任务在制定计划前必须先完成四维路由：

```text
项目形态
× 研发阶段 / 任务类型
× 编程语言 / 工具链
× 风险等级 L1 / L2 / L3
→ 本次必须读取的规则
→ 本次适用的验证维度
→ 本次需要的 Change / Review / Git 门禁
```

四个维度互相独立：

- Python 不等于 Backend；Python 也可能是 CLI、Library、Data Pipeline 或 Desktop；
- TypeScript 不等于 Frontend；它也可能是 Node Service、CLI、Library 或 Monorepo Tooling；
- Web 项目不等于 PostgreSQL；数据库、消息系统和外部依赖必须从仓库事实确认；
- 同一项目中的文档修正可能是 L1，Schema Migration 可能是 L3；
- 同一仓库可以同时匹配多个项目形态，例如 `Full-stack + Monorepo + Container/IaC`。

禁止因为 Skill 提供了某个 profile，就反向假设仓库一定具有该技术、目录、测试框架、数据库或部署方式。

## 2. 先建立任务路由卡

在内部计划、工作说明或 L2/L3 Change 中至少明确：

```text
执行模式：只读分析 / 诊断 / 方案 / 实现 / Review / Git / Release / 运维
项目形态：一个或多个实际形态
研发阶段：本次主要阶段；必要时附带相邻阶段
语言 / 工具链：实际版本事实、Manifest、锁文件、构建/测试入口
风险等级：L1 / L2 / L3
影响边界：模块、接口、数据、配置、运行时、外部依赖、用户行为
选中的 references：为什么适用
Validation Matrix：哪些证据维度 required / not_applicable
Git 授权：是否允许分支、提交、PR、合并、发布
```

这张卡的目的不是增加模板工作量，而是防止 Agent 在错误项目模型上直接编码。例如：

```text
看到 package.json
≠ 自动认定 npm
≠ 自动认定 React
≠ 自动认定 Browser 测试
```

必须继续读取锁文件、`packageManager`、workspace、构建脚本、真实源码和 CI。

## 3. 维度一：识别项目形态

项目形态不是互斥枚举。只选择仓库真实存在、且与本次任务有关的形态。

### Library / SDK

典型边界：

- exported/public API；
- package/module compatibility；
- serialization/ABI/semantic versioning；
- examples/docs；
- package artifact。

重点风险通常是 public contract、兼容性、打包和下游调用，不应机械要求 Browser、数据库或部署验证。

### CLI / Developer Tool

典型边界：

- command / argument / stdin/stdout/stderr；
- exit code；
- filesystem/process/environment；
- cross-platform behavior；
- installation/package artifact。

CLI 的用户验收可以是真实命令工作流，不需要为了“Acceptance”制造浏览器层。

### Service / Backend / API

典型边界：

- request/response 或 RPC/event contract；
- service/domain rule；
- persistence/runtime dependency；
- concurrency/transaction/retry；
- observability/security/runtime。

只有真实使用数据库、队列、缓存、第三方 API 等依赖时才加载对应专项验证。

### Frontend / Web UI

典型边界：

- route/state/component；
- user interaction；
- accessibility；
- network contract；
- build/runtime asset。

如果后端不是本次仓库的一部分，不应把前端 Mock 测试描述成真实 Backend 验证。

### Full-stack Application

至少存在两个真实组件边界，例如 UI + API、API + Worker、Client + Service。需要区分：

```text
各组件自己的行为证据
vs
跨组件真实接线证据
```

Golden Path 只证明必要的跨组件连接，不要求所有状态都做昂贵端到端。

### Mobile / Desktop Client

典型边界：

- View/ViewModel/State；
- platform SDK；
- device/simulator/emulator；
- permissions/storage/network；
- signing/build/package。

不要把 Web Browser 测试术语强加给原生应用；用户验收应使用项目真实 UI/runtime 工具。

### Data / Batch / ETL / ML

典型边界：

- input schema；
- deterministic transform；
- data quality；
- partition/checkpoint/idempotency；
- model/artifact/version；
- batch orchestration/reproducibility。

数据任务不能只用“函数返回值测试”替代真实格式、数据边界和运行管线；也不应在没有必要时调用昂贵在线模型或真实生产数据。

### Embedded / Systems

典型边界：

- compiler/toolchain/target；
- memory/concurrency/timing；
- hardware abstraction；
- protocol/binary format；
- simulator/HIL/device。

Host Unit、模拟器、Target/HIL 分别证明不同事实；不能用 Host 测试冒充目标硬件行为。

### Infra / IaC / Build / Release Tooling

典型边界：

- declarative config；
- build graph；
- image/package；
- plan/diff；
- environment/secret；
- deploy/rollback。

`validate`、`plan`、dry-run 与真实 apply/deploy 是不同证据等级。没有明确授权不得为了验证直接改生产环境。

### Monorepo / Polyglot

重点先确认：

- repository root 与各 workspace/module root；
- 共享 Contract/Schema；
- root 与子项目的规则优先级；
- 语言/包管理器/构建系统是否一套或多套；
- changed scope 对哪些下游消费者有影响。

不要因为一个子项目使用某种工具，就把整仓命令全部替换成该工具。

### Documentation / Configuration / Migration-only Task

这描述的是当前任务形态，而不一定是整个项目形态。此类任务允许 TDD 例外，但仍需要与格式匹配的解析、链接、schema、dry-run、生成差异、构建或运行验证。

## 4. 维度二：识别研发阶段 / 任务类型

同一任务可能跨两个阶段，但必须确定主阶段，避免流程混杂。

### A. Repository Onboarding / Fact Recovery

必须：

1. 先读适用 `AGENTS.md` 或同等规则；
2. 读取 [01_project-discovery.md](01_project-discovery.md)；
3. 识别 Manifest、锁文件、版本文件、构建、测试、CI、架构/需求/Contract 入口；
4. 不先重构，不先升级，不从聊天猜当前实现。

输出重点是事实地图、未知项和本次任务所需最小读取范围。

### B. Requirement / Design / Technical Decision

适用：新能力、行为变化、架构选择、接口/数据设计、重要兼容或安全决定。

必须：

- 先恢复现状和上游需求；
- L2/L3 读取 [04_change-management.md](04_change-management.md)；
- 带 Completion Gate 的 Change 读取 [10_completion-gate.md](10_completion-gate.md)；
- 存在实质取舍时比较真实方案；
- 关键业务语义无法从仓库确认时才提请用户/Owner 决策；
- 不能在设计未闭环时静默写依赖该决定的实现。

### C. Feature / Behavior Implementation

必须读取 [05_development-workflows.md](05_development-workflows.md)，默认：

```text
Red
→ Verify Red
→ Green
→ Verify Green
→ Refactor
→ Verify Again
```

并按 [07_validation-strategy.md](07_validation-strategy.md) 建立与项目形态匹配的验证证据。

### D. Bug / Failure / Incident Diagnosis

必须优先根因调试：

```text
完整错误/日志/栈
→ 稳定复现
→ 近期变化/环境差异
→ 数据流/组件边界
→ 正常参照差异
→ 可证伪根因假设
→ 单变量实验
→ 回归失败用例
→ 单一修复
```

详细规则在 [05_development-workflows.md](05_development-workflows.md)。连续三次修复假设失败时停止叠补丁，重新检查架构、前提和观测手段。

### E. Refactor / Performance / Maintainability

先证明行为基线，再改变内部结构。要求：

- Refactor 不偷偷改变 public behavior；
- 性能优化先有可复现基线和瓶颈证据；
- 不顺手升级依赖或更换框架；
- 用与风险匹配的回归证明外部行为保持不变。

### F. Code Review / Audit

读取 [11_verification-review.md](11_verification-review.md)。复杂任务按：

```text
上游 Requirement Completeness
→ Change / Spec 符合性
→ 实现与测试证据
→ 代码质量 / 安全 / 兼容 / 可维护性
```

Review 默认只报告，不等于授权修改、提交或合并。

### G. Integration / PR / Release / Delivery

必须：

- 使用本轮新鲜证据；
- 对照 Requirement Traceability、Validation Matrix、Completion Audit；
- 检查分支、工作区、diff、CI、生成物、文档；
- 不绕过 Branch Protection/CI；
- 发布/部署/合并必须有对应授权。

详细见 [11_verification-review.md](11_verification-review.md) 与适用项目本地 Release 规则。

### H. Maintenance / Dependency / Runtime Migration

这类任务不能被普通 Feature 顺手完成。必须先确认：

- 当前锁定版本和支持范围；
- upstream release/security/compatibility；
- breaking changes；
- Migration / rollback；
- full regression 范围。

包管理器、运行时、框架或数据库升级通常至少 L2；重大版本、公共兼容或数据迁移通常 L3。

### I. Security / Permission / Irreversible Data Operation

即使代码量小也按高风险边界处理。认证授权、安全策略、Secret、不可逆删除/迁移、生产数据写入等通常至少 L2，涉及公共/数据/权限语义时通常 L3。

## 5. 维度三：识别编程语言 / 工具链

读取 [03_language-and-toolchain-profiles.md](03_language-and-toolchain-profiles.md)。先确认仓库实际事实，再选择 profile；没有列出的语言使用同一发现算法，不得因为 Skill 没有列名就跳过版本、Manifest、锁文件、构建和测试调查。

语言 profile 只提供“去哪里找事实、常见验证是什么”的导航，不授权：

- 升级版本；
- 更换包管理器；
- 把示例命令当仓库命令；
- 引入新的测试/格式化框架；
- 重排目录结构。

## 6. 维度四：风险等级 L1 / L2 / L3

风险分级仍以主 [SKILL.md](../SKILL.md) 为准。项目形态和语言不能降低风险：

```text
L1
→ 行为不变机械修改，或极小且隔离的修复

L2
→ 新功能、行为变化、重要 Bug、多文件/多人并行、需要追踪的工作

L3
→ 公共 API/ABI/Schema/Migration、跨模块 Contract、架构、认证授权、安全、部署恢复、重大依赖或破坏性兼容变化
```

规则：

- 行数少不等于低风险；
- 配置字段改名、CLI public flag、序列化字段、数据库列、公开函数签名、权限语义都可能升级等级；
- 调查中发现隐藏复杂度时必须升级；
- 不允许为了减少 Change/测试工作量静默降级。

## 7. 组合加载矩阵

下面是路由，不是固定配额。

| 触发条件 | 必须读取 |
| --- | --- |
| 新仓库 / 缓存缺失或可能过期 | `01_project-discovery.md` |
| 任意任务需要确认语言/构建/包管理 | `03_language-and-toolchain-profiles.md` |
| L2/L3 / Active Change | `04_change-management.md` |
| `completion_gate: required` | `10_completion-gate.md` |
| Feature / Bug / Refactor / Performance | `05_development-workflows.md` |
| 需要决定测试层与证据 | `07_validation-strategy.md` |
| Web/API/PostgreSQL/Provider 边界实际存在 | `08_testing-strategy.md`，作为专项 profile，不作为所有项目默认 |
| 跨模块 / Contract / Schema / 数据 Owner / Migration | `06_repository-constraints.md` |
| 多人 / 多 Agent / 多分支 / 多 Active Change | `09_collaboration.md` |
| Review / Ready / 交付 / 完成结论 | `11_verification-review.md` |
| 本次在做 Skill 重组或规则迁移审计 | `12_rule-preservation-map.md` |

如果多个条件同时满足，就叠加读取；不要只选其中一个。

## 8. Validation 路由

所有项目先使用 [07_validation-strategy.md](07_validation-strategy.md) 的通用风险维度，再按项目真实形态加载专项 profile。

例如 Web/API/PostgreSQL/Provider 项目可以映射：

```text
用户 / Workflow Acceptance
→ Browser Mock Acceptance

集成 / Persistence / Runtime Dependency
→ Backend/API/PostgreSQL Integration

接口 / Contract
→ Contract / Generated Client

跨组件 Golden Path
→ Real Full-stack Golden Path

外部依赖 Probe
→ Real Provider Probe
```

CLI、Library、Mobile、Embedded、IaC 不需要为了匹配这个名字制造 Browser/PostgreSQL/Provider 层；它们使用自己的真实运行边界。

## 9. 规则优先级与项目 Overlay

Reliable Vibe Coding 是通用工作流，具体项目规则通过项目本地 Overlay 进入。优先级始终是：

```text
系统 / 平台约束
→ 开发者指令
→ 用户明确要求
→ 目标路径适用的 AGENTS.md / CONTRIBUTING / 仓库规则
→ 当前仓库机器事实与已批准正式设计
→ Reliable Vibe Coding 通用流程
→ 语言/项目 profile 中的候选做法和示例
```

如果某项目规定：

- Git commit 使用中文；
- 文档必须编号；
- PostgreSQL 是唯一数据库；
- 只允许某个包管理器；
- 特定 CI 是 merge gate；

这些是该项目 Overlay，不应写成所有项目的全球规则；但在该项目中仍然必须严格执行。

## 10. 路由示例

### Python Library 的 public API 修复

```text
项目形态：Library
阶段：Bug Fix
工具链：Python + 仓库实际 pyproject/lock/test
风险：若 public API 变化则 L3；纯兼容修复可能 L2
加载：01_project-discovery + language profile + 05_development-workflows
      + change/completion（按等级）+ validation + verification
验证：Unit/behavior + public Contract/API + package/build + related regression
不适用：Browser/PostgreSQL/Provider，除非仓库真实存在对应边界
```

### Go CLI 新增命令

```text
项目形态：CLI
阶段：Feature
工具链：Go + go.mod/go.sum + 仓库命令
风险：通常 L2；破坏 public flags/config 时可升 L3
验证：核心逻辑 + CLI invocation/exit/stdout/stderr + build/package
```

### Java Service 的数据库 Migration

```text
项目形态：Service
阶段：Migration
工具链：Java/Kotlin + Maven/Gradle 真实 wrapper/lock policy
风险：L3
加载：06_repository-constraints + change/completion + validation + verification
验证：Migration forward/compat + real persistence integration + API/contract（受影响时）+ rollback strategy
```

### Swift iOS 页面状态修复

```text
项目形态：Mobile
阶段：Bug Fix
工具链：Swift/Xcode/SwiftPM（按仓库事实）
验证：状态逻辑 + UI workflow + simulator/device（风险需要时）+ build
不制造 Browser Mock 层
```

### Terraform 模块变更

```text
项目形态：Infra/IaC
阶段：Behavior/Delivery
风险：通常 L2；生产权限/破坏性资源/关键安全边界可 L3
验证：fmt/lint/validate + plan/policy + sandbox/fixture（适用时）
没有明确授权不得 apply 到生产
```

## 11. 无法识别项目时

不要猜。

按顺序：

1. 读取仓库根与目标路径规则；
2. 找 Manifest、锁文件、版本文件、build/test/CI；
3. 找入口代码、README、Contract、配置；
4. 根据真实文件建立临时 project profile；
5. 只有会改变范围、接口、数据、兼容或验收的上游问题仍无法确认时，才向用户提一个最关键问题。

“Skill 没列出这个框架/语言”不是停止工作的理由，也不是引入新框架的理由。