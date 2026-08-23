# Stage / Change 完成定义追溯门禁

这份规则解决一个特定失败模式：实现、测试和当前 Change 都看起来完整，但 Change 在一开始就漏掉了上游正式要求，导致 CI 全绿仍过早宣布 Stage 完成。

## 核心关系

需求事实的方向固定为：

```text
用户已确认决定 / 正式 Roadmap / Spec / Stage 完成定义
→ 当前 Change
→ 实现
→ 测试与运行证据
```

`CHANGE.md` 是施工契约，不是自身需求全集。不能用“当前 Change 的成功标准全部完成”证明“上游 Stage 已完整完成”。

## Requirement Traceability

新建的 L2/L3 Change 默认带：

```text
completion_gate: required
```

并维护 `# Requirement Traceability` 表。每一条上游要求只允许四种状态：

- `satisfied`：已有当前实现和验证证据；
- `explicitly_deferred`：已有用户/正式事实源批准的延期依据；
- `not_applicable`：有明确事实证明对当前单元不适用；
- `not_satisfied`：尚未满足，不能进入 Ready。

`Source` 优先引用仓库内正式事实源；本轮用户明确批准决定可以使用 `user:<标识>`。当前 Change 不得把自己作为 Requirement Source。

机器检查只能验证表结构、状态、占位内容和仓库路径存在性。Agent/Reviewer 仍必须判断：上游要求是否被完整提取、Evidence 是否真的证明对应语义。

## Validation Matrix

L2/L3 Change 还必须按 [testing-strategy.md](testing-strategy.md) 建立 `# Validation Matrix`，明确各验证层是 `required` 还是 `not_applicable`。

默认考虑：

```text
Browser Mock Acceptance
Backend/API/PostgreSQL Integration
Contract / Generated Client
Real Full-stack Golden Path
Real Provider Probe
Docs / Governance / Other
```

核心边界：

- Browser Mock 用于广覆盖用户可见行为、状态、请求和错误表达；它不能证明真实 API、数据库、Worker 或 Provider 链；
- Backend/API/PostgreSQL Integration 证明服务器业务规则、事务、持久化和异步运行边界；
- Contract 证明生产者/消费者的机器接口一致；
- Real Full-stack 用少量关键 Golden Path 证明真实组件接通，不负责穷举所有 UI 状态；
- Real Provider Probe 只在外部供应商当前事实需要确认时有界执行，默认不作为普通 CI 主力。

Matrix 不要求每个任务机械执行全部层，也不设固定测试数量配额。`not_applicable` 必须有事实依据；`required` 必须在 Ready 前有新鲜证据。

当前 `ready_check.py` 不自动判断 Matrix 的语义充分性，因此 Agent/Reviewer 必须在 Completion Audit 和 Review 中人工核对；不能因为机器 Ready Check 通过就跳过。

## Completion Audit

进入 `ready_for_review` 前必须重新读取上游事实源，不先看当前 Change 的 checklist 来反推需求。至少完成：

```text
upstream_re_read
→ 从上游正式事实源独立重建完成定义

change_coverage
→ 比较“上游要求 vs 当前 Change”，寻找 requirement omission

reverse_audit
→ 对适用边界做反向审计，并复核 Validation Matrix 的层级选择和证据等级

unresolved_cleared
→ not_satisfied 清零；延期/不适用都有正式依据
```

对于前后端/异步业务，反向审计通常包括：

```text
后端当前 V1 能力 → 是否应有前端入口/状态/结果？
前端 Button / Action → 后端是否真实支持且状态允许？
异步 Job → queued/running/success/failure/cancel/retry 是否正确表达？
业务动作完成 → 用户是否能找到最终结果？
错误/失败页面 → 是否只展示机器事实，不伪造历史阶段？
```

同时检查：用户可见 Requirement 是否有适用的 Browser 证据，服务器规则是否有适用的 Backend/DB 证据，公共边界是否有 Contract 证据，关键跨组件链是否有足够的 Real Full-stack Golden Path。没有对应边界时记录为什么不适用，不为填清单制造新架构或无价值测试。

## 两层 Review

需求符合性 Review 分成两层：

```text
Review A1：上游要求 → Change
→ 检查 Change 是否漏需求

Review A2：Change → 实现 / 测试 / 文档
→ 检查已承诺要求是否真实实现，并核对 Validation Matrix 的证据层级
```

第二阶段再做代码质量 Review。CI 绿色不能代替 A1；某一测试层绿色也不能替代另一层独立风险的验证。

## 机器 Ready Check

本地最终检查：

```bash
python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready
```

PR CI 使用 `--changed-since <base-sha>`，只强制当前 PR 改动的 gated Active Change，避免并行 Change 互相阻塞。`main` push 使用 `--require-active-ready`。

机器门禁验证：

- gated Active Change 在需要集成时必须 `ready_for_review`；
- gated Archive Change 必须 `done`；
- Traceability 至少一条，ID 唯一，状态合法；
- Ready/Archive 不允许 `not_satisfied`；
- Source 仓库路径存在，当前 Change 不能引用自身作为 Source；
- Evidence、延期/不适用依据不得为占位值；
- Completion Audit 四项全部完成。

它**不验证业务语义本身，也不自动证明 Validation Matrix 是否充分**，因此不能用脚本通过替代 Completion Audit。

## 兼容策略

历史 `rvc-change/v1` 和本机制引入前已经存在的 Change 没有 `completion_gate: required`，作为 `legacy` 保持可读、可归档，不要求批量回写历史。

新 Change 模板默认启用门禁。不得为了绕过 Ready Check 删除 `completion_gate`；如果发现门禁不适用于某类任务，应修改治理规则并给出证据，而不是在单个 Change 中静默关闭。