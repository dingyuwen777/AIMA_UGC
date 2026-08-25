# 两阶段复核与完成前验证

## 第一阶段：需求符合性

需求符合性必须分两层执行，不能只检查“当前 Change 写了什么”。

### Review A1：上游要求 → 当前 Change

先重新读取本轮用户已确认决定、正式 Roadmap/Spec/Stage/Feature 完成定义和适用规则，**不以当前 Change 的成功标准作为需求全集**。从这些上游事实源独立重建当前单元的完成定义，然后与 Requirement Traceability / 当前 Change 比较：

- 上游每一条适用要求是否都进入当前 Change；
- 是否有 requirement omission；
- `explicitly_deferred` 是否真的有正式批准依据；
- `not_applicable` 是否有事实依据，而不是为了缩小范围；
- 是否把当前 Change 自身、历史聊天或测试结果错误当成上游需求来源；
- 用户没有再次提醒的要求是否仍按正式事实源被主动纳入。

测试通过、CI 全绿、当前 Change checkbox 全勾选，都不能代替 A1。

### Review A2：当前 Change → 实现 / 测试 / 文档

在确认 Change 没有漏上游要求之后，再逐项检查：

- 目标行为是否真实存在；
- 范围内项目是否完成；
- 非目标是否未被实现；
- 必须保持不变的 public API/ABI/CLI、数据、配置、格式和合法行为是否保持；
- 用户确认的关键决策是否被执行；
- `satisfied` 项是否都有对应的实现和当前验证证据；
- Validation Matrix 中每个 `required` 层是否有与其证明范围匹配的新鲜证据；
- `not_applicable` 是否真的是无独立证明价值，而不是为了少跑测试；
- 行为/Unit 是否被错误写成 public consumer、真实 dependency、package 或跨组件证据；
- Mock/Fake 是否只证明实际运行的边界，没有被写成真实数据库、文件系统、设备、远端服务或其他未运行依赖的证据；
- Golden Path 是否聚焦少量关键真实接线，而没有无必要地复制全部状态空间；
- Build/Package/Runtime 是否因为局部测试绿色而被遗漏；
- 外部依赖 Probe 是否只有在当前真实事实需要确认时才执行，并且保持有界；
- 代码、测试、正式文档和 Change 是否一致。

通用分层见 [07_validation-strategy.md](07_validation-strategy.md)。项目真实存在 Web/API/PostgreSQL/Provider 边界时，再按 [08_testing-strategy.md](08_testing-strategy.md) 复核 Browser Mock、Backend/API/PostgreSQL、Contract、Real Full-stack 和 Real Provider Probe 的专项职责。

### Completion Audit 与反向审计

对带 `completion_gate: required` 的 Change，进入 `ready_for_review` 前还必须完成 `# Completion Audit`：

```text
upstream_re_read
change_coverage
reverse_audit
unresolved_cleared
```

`reverse_audit` 不机械套用固定架构；只在当前任务有对应边界时执行。例如：

前后端/异步：

```text
后端当前业务能力 → 前端是否应有入口、状态、错误和结果？
前端 Button / Action → 后端是否真实支持且业务状态允许？
异步任务 → queued/running/retry/success/failure/cancel 是否正确表达？
业务动作完成 → 用户能否找到最终结果？
失败页面 → 是否只显示可审计机器事实？
```

CLI：

```text
public command / flag / config
→ parser / handler
→ stdout / stderr / exit / 副作用
→ 文档和真实调用者工作流
```

Library / SDK：

```text
public API / ABI / exports
→ consumer compile / invoke
→ 返回、异常、兼容语义
→ package artifact / install smoke（有独立风险时）
```

Schema / Migration / Data：

```text
writer / producer
→ schema / migration
→ reader / consumer
→ 历史兼容 / rollback policy
```

Mobile / Embedded / Infra / Package：

```text
公开操作 / 配置 / source
→ runtime / target / render / build
→ simulator/device/artifact/plan/deploy boundary（适用且已授权时）
→ 最终可观察结果
```

同时复核 Validation Matrix：局部行为、公共 Contract、真实依赖、用户/调用者工作流、关键实链、外部依赖、构建/打包和治理事实是否分别由适合的证据层覆盖。没有对应边界时记录不适用依据，不为满足清单创造无价值机制或测试。

详细规则见 [10_completion-gate.md](10_completion-gate.md)。

## 第二阶段：代码质量

检查：

- 正确性和边界条件；
- 错误处理和异常传播；
- 安全、隐私与输入边界；
- 兼容性、Migration、部署和回滚；
- 并发、性能和资源生命周期；
- 测试是否验证真实行为；
- 测试层级是否与它声称证明的事实一致；
- public API/ABI/CLI、serialization/file format 和 consumer compatibility；
- 命名、注释和维护成本；
- **新增或修改的 public/exported 与内部/private/helper 函数是否都有必要的中文函数级说明**；简单函数可以是一句简短职责说明，复杂函数还应解释关键意图、约束、状态转换、兼容原因或副作用边界；不能因函数是 internal/private/helper 就省略，也不能用逐行翻译代码的冗余注释凑数；
- 对**非显然内部/private/helper** 逻辑，除函数级职责说明外，还要确认关键业务规则、不变量、状态转换、算法取舍、兼容原因或副作用边界已经被中文注释解释清楚；
- 新增或修改的 Agent 自有时间戳、日期、缓存、Change 元数据、脚本默认时间、报告或用户可见时间是否统一使用 `Asia/Shanghai` 北京时间；外部协议/原始数据/机器 Contract 使用 UTC 或其他时区时，是否保持原始语义并只在展示边界正确转换；不得把宿主本地时间或 UTC 值冒充北京时间；
- 仓库已有 logging/event/telemetry 体系且本次功能重要/难排障时，关键生命周期、异步阶段、外部 I/O、Retry/部分失败/终态是否具备最小充分可观测性；反之是否存在 INFO 高频刷屏、重复异常日志或无排障价值消息；
- 新增或修改的人类可读日志是否使用 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message`，并满足北京时间、三位毫秒、真实源文件/调用行号和大写 LEVEL；外部 wire-format Contract 强制结构化序列化时是否提供等价字段而不是静默退回 UTC；
- 新增观测是否复用现有 logger/event/level/关联 ID 与脱敏机制，且没有 Secret/Token/密码/敏感 Raw/PII 泄露，也没有用日志替代正式业务事实；
- 无关改动、重复实现和失效内容；
- 用户未提交修改是否被保留；
- 方案是否从真实目标和硬约束推导，是否存在没有证据支持的复杂度或“最佳实践”套用；
- Runtime、Package Manager、Build Tool 和依赖是否保持仓库锁定事实，没有被普通功能任务静默升级或替换。

严重或重要问题必须先解决；不要用“后续优化”掩盖当前正确性问题。

## Ready Check 机器门禁

带 `completion_gate: required` 的 Change 在 Ready 前执行：

```bash
python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready
```

PR CI 使用 `--changed-since <base-sha>`，只要求本 PR 实际改动的 gated Active Change Ready，避免并行中的其他 Change 互相阻塞；`main` push 要求所有 gated Active Change Ready。

机器门禁只验证：

- gated Active/Archive Change 的合法集成状态；
- Traceability 表结构、Requirement ID、四种允许状态；
- Ready/Archive 没有 `not_satisfied`；
- 仓库 Source 路径存在且 Change 不引用自身；
- Evidence/依据不是占位内容；
- Completion Audit 四项已完成。

它不能判断是否漏抄了一个业务要求，不能判断 Evidence 的语义是否充分，也不自动判断 Validation Matrix 的测试层选择是否正确，因此脚本通过不能替代 Review A1/A2。

## 证据门禁

每个结论先回答：什么命令或检查能证明？然后在本轮：

1. 运行完整命令；
2. 读取完整输出；
3. 检查退出码、失败数、警告和跳过项；
4. 对照原始症状、上游完成定义、成功标准、Validation Matrix 和影响范围；
5. 只陈述证据直接支持的状态。

### 通用证据表

| 结论 | 必需证据 | 不足以证明 |
| --- | --- | --- |
| 行为/Component 测试通过 | 当前目标测试输出、退出码 0、失败数 0，并确实断言目标行为 | 昨天日志、Mock 调用次数、“代码看起来对” |
| Public Contract/Compatibility 一致 | 当前 schema/API/ABI/CLI/格式/consumer 兼容检查或生成漂移证据 | 手写 Mock 字段刚好一致、只跑内部 Unit |
| Runtime/Persistence Integration 通过 | 当前项目真实依赖的 integration 证据 | 更弱 Fake、静态检查、另一个语义不同的数据库/runtime |
| 用户/调用者工作流通过 | 当前真实入口的 Workflow Acceptance 输出和可观察断言 | private helper Unit、只断言函数被调用 |
| 跨组件接通 | 当前关键真实组件链 Golden Path 成功 | 各组件 Mock/Unit 各自单独通过 |
| 外部依赖当前真实可用 | 当前有界真实 Probe，并说明环境/费用/权限/数据范围 | 历史 fixture、旧 Raw、Mock、上次运行 |
| 构建/打包/安装/启动成功 | 当前正式 build/package/install/startup 命令退出码 0，必要时核对 artifact | Lint 通过、源码 Unit 通过 |
| Bug 修复 | 原始症状不再出现，回归测试经历正确 Red/Green | 只修改代码、测试仅在修复后运行一次 |
| Change 需求完成 | 当前 Change 成功标准逐项证据 + Validation Matrix | 测试全部绿色 |
| Stage/正式单元完成 | 上游 Requirement Traceability + Validation Matrix + Completion Audit + Change 实现证据 | 只检查当前 Change、CI 全绿 |
| 子 Agent 完成 | 主 Agent 检查实际 diff 并重新验证 | 子 Agent 的成功报告 |
| 可发布 | 完整交付门禁、正式 artifact/runtime 验证、部署与回滚状态 | 本地目标测试通过 |

### Web / API / PostgreSQL / Provider 项目的专项证据示例

这些示例继续保留，但只有对应项目边界真实存在时才使用：

| 结论 | 必需证据 | 不足以证明 |
| --- | --- | --- |
| Browser 用户行为通过 | 当前 Browser Mock/Acceptance 输出 + 实际用户可见断言/请求断言 | 后端单测、Mock 被调用一次 |
| PostgreSQL/服务器规则通过 | 当前 Backend/API/PostgreSQL Integration 证据 | Browser Mock、SQLite（当语义依赖 PostgreSQL 时）、静态代码检查 |
| Contract / Generated Client 一致 | 当前 Pydantic/OpenAPI/generated client 生成/漂移检查 | 手写 Mock 字段刚好一致 |
| Real Full-stack 接通 | 当前真实关键组件链 Golden Path 运行成功 | Browser Mock、API Integration 各自单独通过 |
| Provider 当前真实可用 | 当前有界 Real Provider Probe | 历史 Raw、Fixture、Mock |

专项表不能反向证明所有项目都必须有 Browser、PostgreSQL 或 Provider。

命令无法运行时，保留原错误，说明未验证内容、原因和风险。不要删除、跳过或篡改失败测试，不要吞掉异常或降低检查标准。

## 条件式边界验证

只有仓库存在相应事实或本次变更明确建立它们时，才执行以下检查：

- 前后端或生产者/消费者是否使用同一 API、事件、消息、ABI、CLI、serialization 或文件 Contract；
- Schema、空值、枚举、时间、单位、错误、ordering/default 和兼容语义是否一致；
- 数据写入是否遵守既有 Owner、完整性和 Migration 顺序；
- 共享 Contract 的契约测试、生成物检查或兼容门禁是否通过；
- 并行冻结点和依赖基线是否仍是当前版本；
- package/build/runtime 是否使用仓库正式版本、wrapper、lock 和 target；
- 外部环境、设备或远端系统是否真的属于本次所需证据，而不是为了“更真实”无界调用。

未发现这些机制且任务不依赖它们时，记录“不适用”并跳过。若任务依赖但关键事实缺失，不得用自创约定完成验证。

## 生成文件验证

生成或修改非源码文件时，按格式实际验证后再交付：确认文件存在且路径可访问，检查扩展名、大小和容器结构，用可用解析器或目标应用重新打开，并核对关键内容、版式或数据。无法使用目标应用时说明替代验证、未覆盖项和剩余风险；不能只凭生成命令退出码宣称文件可用。

生成代码还应按项目正式事实源执行 drift/regen 检查，避免手工修改生成目录或让生成物与 Schema/Contract/IDL 漂移。

## 文档与 Change

确认正式文档描述当前系统；Change 保存当次原因、取舍、任务和证据。检查元数据状态、Owner、分支、依赖和影响范围仍与实际一致。带 Completion Gate 的 Change 还要检查 Requirement Source、Traceability、Validation Matrix 和 Completion Audit。不要提前把 Active Change 归档。

项目的文档编号、命名、Blueprint/ADR/Roadmap 分工等本地规则继续由项目 Overlay 决定；Git 提交信息、代码注释、北京时间和日志前缀要求属于本 Skill 通用规则，不再委托给项目 Overlay。通用 Review 负责检查项目本地规则与通用规则是否同时满足。

## Git 检查

在交付前检查：

- 当前分支和工作区；
- 任务相关 diff；
- 是否混入用户或其他 Change 的修改；
- 未跟踪文件和生成物；
- 用户实际授权的 Git 操作边界；
- **Commit message 必须使用中文**；项目额外提交格式也必须同时满足；
- Commit、PR、CI、合并和部署的真实状态。

没有实际执行的外部操作必须写“未执行”，不能推测成功。

## 完成报告

按以下顺序报告：

1. 结果与范围；
2. 逐文件变更及目的；
3. 本次项目形态、研发阶段、语言/工具链和风险等级；
4. 上游 Requirement Traceability 与成功标准状态；
5. Validation Matrix 与各层实际证据；
6. Completion Audit / 两阶段 Review 结果；
7. Contract/API/ABI/Schema/Migration/数据变化；
8. 文档同步及依据；
9. 实际验证命令、退出码、通过/失败数量和关键输出；
10. 未验证内容及剩余风险；
11. 兼容性、依赖、Migration、部署和回滚影响；
12. Git 分支、提交、PR、合并和清理状态。

如果没有任何文件变化或任务仍被阻塞，也使用相同结构如实说明。
