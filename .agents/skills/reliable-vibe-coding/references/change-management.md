# 轻量 Change 管理

## 原则

把一个重要变化作为一个可独立理解、实现和验收的工作单元。复杂度通过同一 `CHANGE.md` 的章节深度增加，不通过固定生成 proposal、spec、design 和 tasks 四套文件增加。

## 何时创建

- L1：行为不变的机械修改，或边界明确且影响隔离的极小修复。不要创建 Change。
- L2：新功能、业务行为变化、重要 Bug、多文件修改、多人并行或需要审计。创建一个 Change。
- L3：公共 API、Schema、Migration、跨模块 Contract、架构、认证授权、安全、部署、重大依赖或破坏性兼容变化。仍创建一个 Change，但补充方案比较、Migration、部署、回滚和风险。

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

不要用自然语言“可能改很多地方”代替影响元数据。路径尽量写仓库相对目录或文件；Contract 和数据资源使用仓库既有正式名称。

元数据必须来自仓库事实或已确认设计。仓库没有适用的 Contract、数据资源、模块 Owner 或 Migration 时，对应列表使用 `[]`，不得为显得完整而造名称。只有本次需求明确建立新接口或数据资源、且其名称和边界已通过设计门禁时，才记录计划中的新对象。

`rvc.py` 对 v1 schema、必需字段、状态、依赖 ID 和安全相对路径执行严格校验。任一 Active Change 损坏或使用不受支持的结构时，状态与冲突检查会失败并要求先修正记录；不要把无法解析的记录静默当成“无冲突”。

## 必需内容

每个 Change 至少写清：

1. 目标；
2. 可观察成功标准；
3. 范围与非目标；
4. 必须保持不变；
5. 已确认关键决策；
6. 小而完整的任务；
7. 验证计划和本轮新鲜证据；
8. 文档影响；
9. Commit、PR 和发布状态。

L3 追加：

- 2–3 个可行方案和推荐依据；
- 公共接口或数据兼容策略；
- Migration 与部署顺序；
- 回滚方式；
- 安全、性能和运维风险；
- 用户确认的上游决策。

方案比较从目标、硬约束和必要机制出发，至少包含保留现有路线的最小增量方案；推荐的是当前证据下的最优可行解，不宣称未经测量或无法证明的绝对最优。

## 状态

只使用：

```text
proposed → approved → in_progress → ready_for_review → done
                         └────────→ blocked
```

- 没有用户或项目要求的批准时，不伪造 `approved`。
- 仅在真实阻塞时用 `blocked`，并记录阻塞条件。
- 代码写完但尚未集成通常是 `ready_for_review`，不是 `done`。
- 完成声明必须有成功标准、测试、文档和 Git 状态证据。

## 需求变化

- 完成前改变同一目标：更新当前 Change，使其反映最新确认范围；在关键决策中记录重要取舍。
- 目标或范围根本改变：关闭或冻结原 Change，创建新 Change。
- 已归档后出现新需求：创建新 Change，不改写历史。

## 当前事实与历史

README、正式需求、Contract、Schema 和架构文档描述系统现在是什么。归档 Change 保存为什么改变、当时如何选择以及如何验证。不要要求维护者通过顺序阅读所有历史 Change 才能理解当前系统。

## 归档门禁

归档前逐项确认：

- 成功标准有证据；
- 目标和相关测试已运行；
- 静态检查、类型检查和构建按影响范围完成；
- 正式文档已同步或有无需同步的依据；
- 兼容、Migration、部署与回滚状态明确；
- Commit、PR、合并或发布状态如实记录。

归档仅移动 Git 文件，不自动代表代码已合并或发布。未经授权不要提交、推送、合并或部署。
