# 两阶段复核与完成前验证

## 第一阶段：需求符合性

需求符合性必须分两层执行，不能只检查“当前 Change 写了什么”。

### Review A1：上游要求 → 当前 Change

先重新读取本轮用户已确认决定、正式 Roadmap/Spec/Stage 完成定义和适用规则，**不以当前 Change 的成功标准作为需求全集**。从这些上游事实源独立重建当前单元的完成定义，然后与 Requirement Traceability / 当前 Change 比较：

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
- 必须保持不变的接口、数据、配置和行为是否保持；
- 用户确认的关键决策是否被执行；
- `satisfied` 项是否都有对应的实现和当前验证证据；
- Validation Matrix 中每个 `required` 层是否有与其证明范围匹配的新鲜证据；
- `not_applicable` 是否真的是无独立证明价值，而不是为了少跑测试；
- Browser Mock 是否只被用于证明用户可见行为，没有被写成真实 API/DB/Worker/Provider 端到端证据；
- Real Full-stack 是否聚焦少量关键 Golden Path，而没有无必要地复制全部状态空间；
- 代码、测试、正式文档和 Change 是否一致。

详细测试分层见 [testing-strategy.md](testing-strategy.md)。

### Completion Audit 与反向审计

对带 `completion_gate: required` 的 Change，进入 `ready_for_review` 前还必须完成 `# Completion Audit`：

```text
upstream_re_read
change_coverage
reverse_audit
unresolved_cleared
```

`reverse_audit` 不机械套用固定架构；只在当前任务有对应边界时执行。例如前后端/异步业务至少反向检查：

```text
后端当前业务能力 → 前端是否应有入口、状态、错误和结果？
前端 Button / Action → 后端是否真实支持且业务状态允许？
异步任务 → queued/running/retry/success/failure/cancel 是否正确表达？
业务动作完成 → 用户能否找到最终结果？
失败页面 → 是否只显示可审计机器事实？
```

同时复核 Validation Matrix：用户可见状态空间、后端规则/持久化、公共 Contract、关键实链和外部 Provider 当前事实是否分别由适合的证据层覆盖。没有对应边界时，记录不适用依据，不为满足清单创造无价值机制或测试。

详细规则见 [completion-gate.md](completion-gate.md)。

## 第二阶段：代码质量

检查：

- 正确性和边界条件；
- 错误处理和异常传播；
- 安全、隐私与输入边界；
- 兼容性、Migration、部署和回滚；
- 并发、性能和资源生命周期；
- 测试是否验证真实行为；
- 测试层级是否与它声称证明的事实一致；
- 命名、注释和维护成本；
- 无关改动、重复实现和失效内容；
- 用户未提交修改是否被保留；
- 方案是否从真实目标和硬约束推导，是否存在没有证据支持的复杂度或“最佳实践”套用。

严重或重要问题必须先解决；不要用“后续优化”掩盖当前正确性问题。

## Ready Check 机器门禁

带 `completion_gate: required` 的 Change 在 Ready 前执行：

```bash
python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready
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

| 结论 | 必需证据 | 不足以证明 |
|---|---|---|
| 测试通过 | 当前完整测试输出、退出码 0、失败数 0 | 昨天日志、局部测试、“应该通过” |
| Browser 用户行为通过 | 当前 Browser Mock/Acceptance 输出 + 实际用户可见断言/请求断言 | 后端单测、Mock 被调用一次 |
| PostgreSQL/服务器规则通过 | 当前 Backend/API/PostgreSQL Integration 证据 | Browser Mock、SQLite、静态代码检查 |
| Contract 一致 | 当前 Pydantic/OpenAPI/generated client 生成/漂移检查 | 手写 Mock 字段刚好一致 |
| Real Full-stack 接通 | 当前真实关键组件链 Golden Path 运行成功 | Browser Mock、API Integration 各自单独通过 |
| Provider 当前真实可用 | 当前有界 Real Provider Probe | 历史 Raw、Fixture、Mock |
| 构建成功 | 当前构建命令退出码 0 | Lint 通过、代码看起来正确 |
| Bug 修复 | 原始症状不再出现，回归测试经历正确 Red/Green | 只修改代码、测试仅通过一次 |
| Change 需求完成 | 当前 Change 成功标准逐项证据 + Validation Matrix | 测试全部绿色 |
| Stage/正式单元完成 | 上游 Requirement Traceability + Validation Matrix + Completion Audit + Change 实现证据 | 只检查当前 Change、CI 全绿 |
| 子 Agent 完成 | 主 Agent 检查实际 diff 并重新验证 | 子 Agent 的成功报告 |
| 可发布 | 完整交付门禁、部署与回滚状态 | 本地目标测试通过 |

命令无法运行时，保留原错误，说明未验证内容、原因和风险。不要删除、跳过或篡改失败测试，不要吞掉异常或降低检查标准。

## 条件式边界验证

只有仓库存在相应事实或本次变更明确建立它们时，才执行以下检查：

- 前后端或生产者/消费者是否使用同一 API、事件、消息或文件 Contract；
- Schema、空值、枚举、时间、单位、错误和兼容语义是否一致；
- 数据写入是否遵守既有 Owner、完整性和 Migration 顺序；
- 共享 Contract 的契约测试、生成物检查或兼容门禁是否通过；
- 并行冻结点和依赖基线是否仍是当前版本。

未发现这些机制且任务不依赖它们时，记录“不适用”并跳过。若任务依赖但关键事实缺失，不得用自创约定完成验证。

## 生成文件验证

生成或修改非源码文件时，按格式实际验证后再交付：确认文件存在且路径可访问，检查扩展名、大小和容器结构，用可用解析器或目标应用重新打开，并核对关键内容、版式或数据。无法使用目标应用时说明替代验证、未覆盖项和剩余风险；不能只凭生成命令退出码宣称文件可用。

## 文档与 Change

确认正式文档描述当前系统；Change 保存当次原因、取舍、任务和证据。检查元数据状态、Owner、分支、依赖和影响范围仍与实际一致。带 Completion Gate 的 Change 还要检查 Requirement Source、Traceability、Validation Matrix 和 Completion Audit。不要提前把 Active Change 归档。

## Git 检查

在交付前检查：

- 当前分支和工作区；
- 任务相关 diff；
- 是否混入用户或其他 Change 的修改；
- 未跟踪文件和生成物；
- 用户实际授权的 Git 操作边界；
- Commit、PR、CI、合并和部署的真实状态。

没有实际执行的外部操作必须写“未执行”，不能推测成功。

## 完成报告

按以下顺序报告：

1. 结果与范围；
2. 逐文件变更及目的；
3. 上游 Requirement Traceability 与成功标准状态；
4. Validation Matrix 与各层实际证据；
5. Completion Audit / 两阶段 Review 结果；
6. 文档同步及依据；
7. 实际验证命令、退出码、通过/失败数量和关键输出；
8. 未验证内容及剩余风险；
9. 兼容性、依赖、Migration、部署和回滚影响；
10. Git 分支、提交、PR、合并和清理状态。

如果没有任何文件变化或任务仍被阻塞，也使用相同结构如实说明。