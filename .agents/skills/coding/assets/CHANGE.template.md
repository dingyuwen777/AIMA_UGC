---
schema: rvc-change/v1
id: $change_id
title: $title
level: $level
status: proposed
owner: $owner
branch: $branch
created: $created
updated: $updated
completion_gate: required
$depends_on
$affected_areas
$affected_paths
$contracts
$data_changes
---

# 目标

描述用户或系统最终获得的结果。

# 成功标准

- [ ] 使用可观察行为描述验收结果。

# 范围

- 列出本次允许修改的内容。

# 非目标

- 列出本次明确不做的内容。

# 必须保持不变

- 列出需要兼容的接口、数据、配置和既有合法行为。

# 关键决策

记录已经确认的取舍、依据和影响；L3 变更还应覆盖迁移、部署与回滚。

# Requirement Traceability

从用户已确认决定、正式 Roadmap/Spec/Stage 完成定义或其他上游事实源独立提取要求。**当前 Change 不能把自身作为 Requirement Source，也不能把本表当作上游需求全集。**

状态只允许：

- `satisfied`：已有实现/验证证据；
- `explicitly_deferred`：已有正式批准的延期依据；
- `not_applicable`：有明确事实证明不适用；
- `not_satisfied`：尚未满足，进入 `ready_for_review` 前必须清零。

`Source` 优先写仓库相对事实源路径；本轮用户明确决定可写 `user:<简短标识>`。`Evidence` 必须写实际实现、测试、运行或正式延期/不适用依据，Ready 时不得保留占位内容。

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 写明第一条上游要求 | user:current-request | not_satisfied | 尚未验证 |

# Validation Matrix

先按当前任务的**真实失败边界**选择通用验证维度。每层只使用 `required` 或 `not_applicable`：`required` 写明本次要证明的 Scope，并在完成前补当前 Evidence；`not_applicable` 必须说明该层为什么没有独立证明价值。

不要为了填模板机械执行所有层，也不要因为某一层已经绿色就推断另一层已经被证明。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 有局部业务规则、算法、状态或组件行为时验证目标行为和边界；纯文档等任务说明不适用依据 |
| 接口 / Contract | not_applicable | public API/ABI/CLI/Schema/格式/生产者消费者边界受影响时验证兼容和机器一致性 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 真实数据库、文件、队列、OS、SDK、runtime service 等语义受影响时验证真实依赖边界 |
| 用户 / Workflow Acceptance | not_applicable | 有用户/调用者可观察工作流时验证入口、输入、输出、状态和错误闭环 |
| 跨组件 Golden Path | not_applicable | 存在多个真实组件的关键接线时，用少量高价值路径证明组装后的真实链路 |
| External Dependency / Provider Probe | not_applicable | 只有需要确认第三方服务/硬件/远端环境当前真实事实时才有界执行 |
| Build / Package / Runtime | not_applicable | 构建、打包、安装、镜像、target 或启动行为可能受影响时验证正式产物/运行入口 |
| Docs / Governance / Other | not_applicable | 文档、配置、生成物、架构/Owner、Secret、Policy、Change/Ready 等专项证据 |

通用规则见 `.agents/skills/coding/references/07_通用验证与证据策略.md`。

项目存在专项 profile 时在保持语义责任不变的前提下使用更具体层名。例如 Web/API/PostgreSQL/Provider 项目继续按 `.agents/skills/coding/references/08_分层测试与验收策略.md` 使用：

```text
用户 / Workflow Acceptance
→ Browser Mock Acceptance

集成 / Persistence / Runtime Dependency
→ Backend/API/PostgreSQL Integration

接口 / Contract
→ Contract / Generated Client

跨组件 Golden Path
→ Real Full-stack Golden Path

External Dependency / Provider Probe
→ Real Provider Probe
```

Browser Mock 不能冒充真实 Backend/DB；一条 Full-stack 不能冒充全部状态；真实 Provider Probe 默认有界且不进普通 CI。

# Completion Audit

进入 `ready_for_review` 前必须**重新读取上游事实源**，不要从当前 Change 的 checklist 反推需求。

按当前项目形态和任务边界执行正向/反向审计。例如：

- 前后端：后端能力 → 前端入口，前端动作 → 后端真实能力；
- CLI：public command/flag → handler → stdout/stderr/exit/副作用；
- Library：public API → consumer；
- 异步：请求 → 状态 → 错误/恢复 → 最终结果；
- Schema/Migration：writer → migration → reader/consumer；
- Package/Release：source → build artifact → install/startup；
- Infra：config → plan/render → runtime/deploy boundary（在授权范围内）。

同时复核 Validation Matrix：每个 `required` 都有足够的新鲜证据，每个 `not_applicable` 都有真实依据。

- [ ] upstream_re_read：已重新读取所有上游正式事实源，并从它们独立重建完成定义。
- [ ] change_coverage：已确认当前 Change 覆盖全部上游要求，没有把 Change 自身当作需求全集。
- [ ] reverse_audit：已执行适用的反向能力/边界审计，并复核 Validation Matrix；不适用项已有明确依据。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；延期/不适用项均有正式依据。

# 任务

- [ ] 调查当前实现和事实源
- [ ] 建立四维任务路由：项目形态 / 研发阶段 / 语言工具链 / 风险等级
- [ ] 建立失败测试或说明测试例外
- [ ] 建立并维护 Validation Matrix
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 取得新鲜验证证据
- [ ] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- Validation Matrix：按 `.agents/skills/coding/references/07_通用验证与证据策略.md` 选择通用维度；存在专项 profile 时再叠加专项策略
- 目标测试：
- 相关测试：
- 静态检查/构建：
- Ready Check：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`

## 新鲜证据

- 尚未执行。

# 文档影响

- 待确认。

# 交付

- Commit：
- PR：
- 发布：