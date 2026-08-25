# 轻量 Change 管理

## 原则

把一个重要变化作为一个可独立理解、实现和验收的工作单元。复杂度通过同一 `CHANGE.md` 的章节深度增加，不通过固定生成 proposal、spec、design 和 tasks 四套文件增加。

Change 是**施工契约**，不是自身的上游需求全集。正式 Stage / 子 Stage / Roadmap 单元必须保持：

```text
用户已确认决定 / 正式 Roadmap / Spec / Stage 完成定义
→ 当前 Change
→ 实现
→ 测试与运行证据
```

不能因为 Change 自己的成功标准全部勾选，就跳过对上游完成定义的重新核对。

## 何时创建

- L1：行为不变的机械修改，或边界明确且影响隔离的极小修复。不要创建 Change。
- L2：新功能、业务行为变化、重要 Bug、多文件修改、多人并行或需要审计。创建一个 Change。
- L3：公共 API/ABI/CLI/数据格式、Schema、Migration、跨模块 Contract、架构、认证授权、安全、部署、重大依赖或破坏性兼容变化。仍创建一个 Change，但补充方案比较、Migration、部署、回滚和风险。

发现隐藏影响时把 L1 升为 L2、把 L2 升为 L3。不要为了少写文档而降级。

## 目录和 ID

```text
changes/
├── active/
│   └── CHG-YYYYMMDD-short-name/
│       └── CHANGE.md
└── archive/
    └── YYYY-MM/
        └── CHG-YYYYMMDD-short-name/
            └── CHANGE.md
```

ID 使用 `CHG-YYYYMMDD-kebab-case`。一个 Change 默认只有一个 Owner 和一个主分支；协作者写进任务或决策区，不并列多个模糊 Owner。

## 必需元数据

保持 frontmatter 扁平，便于没有 YAML 依赖的工具读取：

- `id`、`title`、`level`、`status`；
- `owner`、`branch`、`created`、`updated`；
- `depends_on`；
- `affected_areas`、`affected_paths`；
- `contracts`、`data_changes`。

新模板还固定加入：

```text
completion_gate: required
```

它表示该 Change 在进入 Ready/Archive 时必须通过 Requirement Traceability 与 Completion Audit 门禁。机制引入前已经存在、没有该标记的 `rvc-change/v1` 作为 legacy 保持兼容，不要求批量改写历史。

不要用自然语言“可能改很多地方”代替影响元数据。路径尽量写仓库相对目录或文件；Contract 和数据资源使用仓库既有正式名称。

元数据必须来自仓库事实或已确认设计。仓库没有适用的 Contract、数据资源、模块 Owner 或 Migration 时，对应列表使用 `[]`，不得为显得完整而造名称。只有本次需求明确建立新接口或数据资源、且其名称和边界已通过设计门禁时，才记录计划中的新对象。

`rvc.py` 对 v1 schema、必需字段、状态、依赖 ID 和安全相对路径执行严格校验。任一 Active Change 损坏或使用不受支持的结构时，状态与冲突检查会失败并要求先修正记录；不要把无法解析的记录静默当成“无冲突”。

## 必需内容

每个新 Change 至少写清：

1. 目标；
2. 可观察成功标准；
3. 范围与非目标；
4. 必须保持不变；
5. 已确认关键决策；
6. Requirement Traceability；
7. Validation Matrix；
8. Completion Audit；
9. 小而完整的任务；
10. 验证计划和本轮新鲜证据；
11. 文档影响；
12. Commit、PR 和发布状态。

L3 追加：

- 2–3 个可行方案和推荐依据；
- 公共接口或数据兼容策略；
- Migration 与部署顺序；
- 回滚方式；
- 安全、性能和运维风险；
- 用户确认的上游决策。

方案比较从目标、硬约束和必要机制出发，至少包含保留现有路线的最小增量方案；推荐的是当前证据下的最优可行解，不宣称未经测量或无法证明的绝对最优。

## Requirement Traceability

对 `completion_gate: required` 的 Change，编码前从上游事实源提取当前单元要求并维护追溯表。来源可以是：

- 本轮用户明确批准决定：`user:<简短标识>`；
- 仓库内正式 Roadmap、Spec、Stage 完成定义、Blueprint/Guide/README 中适用的上游要求；
- 必要时显式外部事实源，但不能用当前 Change 自身代替正式需求来源。

状态只允许：

```text
satisfied
explicitly_deferred
not_applicable
not_satisfied
```

规则：

- `satisfied` 必须有实际实现/测试/运行证据；
- `explicitly_deferred` 必须有正式批准的延期依据；
- `not_applicable` 必须说明为什么当前单元不适用；
- `not_satisfied` 可以在开发中存在，但进入 `ready_for_review` 前必须清零；
- Source、Evidence 不得在 Ready 时保留 `TBD/TODO/待确认/待实现/尚未验证` 等占位内容；
- 机器检查只能验证结构、状态、占位符和仓库路径存在性，不能替代语义判断。

详细规则见 [completion-gate.md](completion-gate.md)。

## Validation Matrix

对 L2/L3 Change，在实现前根据当前任务的真实失败边界选择验证层，并在完成前补新鲜证据。

通用规则见 [validation-strategy.md](validation-strategy.md)。默认从以下语义维度判断：

```text
行为 / Unit / Component
接口 / Contract
集成 / Persistence / Runtime Dependency
用户 / Workflow Acceptance
跨组件 Golden Path
外部依赖 Probe
Build / Package / Runtime
Docs / Governance / Other
```

每一层只写：

```text
required
not_applicable
```

规则：

- `required`：写清这层要证明的独立风险和 Scope，完成前补当前测试/运行证据；
- `not_applicable`：写明为什么该层对当前任务没有独立证明价值；
- 不要求每个任务机械执行全部层；
- Unit/Component 不能冒充 public consumer、真实 persistence/runtime、package 或跨组件接线；
- Mock/Fake 不能声称证明没有实际运行的数据库、文件系统、外部服务、设备或进程；
- Golden Path 默认只保留少量关键真实接线，不用它穷举全部状态；
- 外部依赖 Probe 只有真实第三方/硬件/远端事实需要确认时才执行，并保持有界、可审计、默认不进普通 CI；
- Build/Package/Runtime 在源代码测试无法证明产物或启动事实时承担独立证据；
- 测试数量由行为边界与风险决定，不设固定配额。

项目真实存在 Web/API/PostgreSQL/Provider 边界时，再叠加 [testing-strategy.md](testing-strategy.md) 的专项层：

```text
Browser Mock Acceptance
Backend/API/PostgreSQL Integration
Contract / Generated Client
Real Full-stack Golden Path
Real Provider Probe
```

这些专项细节全部保留：Browser Mock 负责广覆盖用户可见状态但不能冒充真实 API/DB/Worker；Backend/PostgreSQL 负责服务器规则、事务和持久化；Contract 防机器接口漂移；Real Full-stack 只用少量 Golden Path；Provider Probe 只有真实外部事实需要确认时有界执行。

CLI、Library、Mobile、Embedded、Data、IaC 等没有这些边界的项目不为了模板制造 Browser/PostgreSQL/Provider 层，而应使用通用矩阵中真实对应的 Workflow、Runtime、Build、Device、Plan 等证据。

Validation Matrix 是语义验证计划，不由 `ready_check.py` 自动判断测试是否充分；Agent/Reviewer 必须检查每个 `required` 层的 Evidence 是否真的证明对应风险。

## Completion Audit

进入 `ready_for_review` 前，不先按当前 Change 的 checklist 验收，而是重新读取上游事实源并执行：

1. `upstream_re_read`：独立重建上游完成定义；
2. `change_coverage`：比较上游要求和当前 Change，寻找 requirement omission；
3. `reverse_audit`：对适用边界做反向能力审计，并复核 Validation Matrix 的 required/not_applicable 与证据等级；
4. `unresolved_cleared`：确认 `not_satisfied` 清零，延期/不适用都有依据。

反向审计按项目真实边界选择，例如：

- 前后端：`后端能力 → 前端入口` 与 `前端动作 → 后端真实支持`；
- CLI：`public command/flag → handler → stdout/stderr/exit/副作用`；
- Library/SDK：`public API → consumer`；
- 异步：`请求 → 状态/错误/恢复 → 最终结果`；
- Schema/Migration：`writer → migration → reader/consumer`；
- Package/Release：`source → artifact → install/startup`；
- Infra：`config → render/plan → runtime/deploy boundary`（仅在授权范围）。

没有对应边界时记录不适用依据，不制造新机制。

## 状态

只使用：

```text
proposed → approved → in_progress → ready_for_review → done
                         └────────→ blocked
```

- 没有用户或项目要求的批准时，不伪造 `approved`。
- 仅在真实阻塞时用 `blocked`，并记录阻塞条件。
- 代码写完但尚未集成通常是 `ready_for_review`，不是 `done`。
- 对 gated Change，进入 `ready_for_review` 前必须完成 Traceability、Validation Matrix、Completion Audit 和机器 Ready Check；CI 全绿不能替代上游需求完整性复核。
- 完成声明必须有成功标准、测试、文档、Requirement Traceability、Validation Matrix、Completion Audit 和 Git 状态证据。

本地最终检查：

```bash
python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready
```

PR CI 只要求当前 PR 改动的 gated Change Ready，避免其他并行 Change 阻塞；`main` push 要求所有 gated Active Change Ready。

## 需求变化

- 完成前改变同一目标：先回到上游要求，更新 Traceability，再更新当前 Change；在关键决策中记录重要取舍。
- 目标或范围根本改变：关闭或冻结原 Change，创建新 Change。
- 已归档后出现新需求：创建新 Change，不改写历史。
- 不得通过删除 `completion_gate` 或把未满足项静默改成“后续优化”绕过门禁。

## 当前事实与历史

README、正式需求、Contract、Schema 和架构文档描述系统现在是什么。归档 Change 保存为什么改变、当时如何选择以及如何验证。不要要求维护者通过顺序阅读所有历史 Change 才能理解当前系统。

## 归档门禁

归档前逐项确认：

- gated Change 状态已改为 `done`，Requirement Traceability、Validation Matrix 和 Completion Audit 仍完整；
- 成功标准有证据；
- 目标和相关测试已运行；
- 静态检查、类型检查和构建按影响范围完成；
- 正式文档已同步或有无需同步的依据；
- 兼容、Migration、部署与回滚状态明确；
- Commit、PR、合并或发布状态如实记录。

归档仅移动 Git 文件，不自动代表代码已合并或发布。未经授权不要提交、推送、合并或部署。