---
schema: coding-change/v1
id: CHG-20260926-231200-export-admission-set
title: 用数据库集合操作冻结 Excel 导出目标
level: L3
status: proposed
owner: codex
branch: fix/618-export-admission
created: 2026-09-26
updated: 2026-09-26
completion_gate: required
depends_on: []
affected_areas:
  - reporting
  - content
affected_paths:
  - backend/src/aima_ugc/bootstrap/reporting_http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/reporting.py
  - tests/integration/content/
  - backend/src/aima_ugc/modules/reporting/README.md
contracts: []
data_changes:
  - Excel Export 创建时目标 Content ID、Version 与 Ordinal 的冻结执行方式
---

# 变更摘要

Issue #618 / AC3、AC5 的工作包。导出受理使用已有 Content 查询 SQL，以 `INSERT ... SELECT` 在同一事务冻结目标，消除把全部候选转成 Python 对象再逐条绑定插入的内存与往返放大。

# 背景、现状与问题

当前 `reporting_http.create_export()` 调用 `freeze_targets()` 物化所有 ContentTarget，随后 `PostgresDataExportRepository.create()` 构建等量字典列表；查询范围可大于 selected scope 的 1000 条上限。内存和请求延迟随目标数增长。既有 `freeze_target_statement()` 已提供同一过滤规则与版本选择 SQL，且 Analysis Run 已用其执行集合冻结。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 决策依据 |
| --- | --- | --- | --- |
| E1 | 导出受理两次在 Python 物化全部目标 | `reporting_http.py` 与 `reporting.py` 当前实现 | 改为数据库集合插入 |
| E2 | 共享 Content 查询已有 `freeze_target_statement()` | `content_queries.py` | 复用现有筛选，不造第二套规则 |
| E3 | selected scope 有序，过滤掉无效 Content 后 Ordinal 必须紧凑 | 现有 `freeze_targets()` 再 `enumerate(targets)` | SQL 使用结果集序号 |

推断与待确认：生产导出目标规模和 P95 待服务器日志；不阻塞当前根因修复。

# 目标、成功标准与非目标

目标：导出受理内存不随目标对象数线性增长，仍在提交事务内冻结 ID、Version 和连续 Ordinal。

- [ ] 空选择继续返回相同错误，且无 Job/Export 残留。
- [ ] query 与 selected 的顺序、过滤、版本冻结和 `target_count` 与旧行为一致。
- [ ] 真实 PostgreSQL 与相同数据性能对照证明集合插入减少 Python 对象化和受理开销。

范围：Reporting API Service、Repository、相关集成测试与模块文档。非目标：Worker Excel 渲染、列选择、公共 Contract、依赖或表结构。必须保持 Job 与 Export 原子提交、无效来源过滤及既有错误类型。

# 约束与意图决策

Reporting 仍是 Export 表唯一写 Owner；Content 查询仍是目标筛选唯一 Owner。新实现仅改变数据库执行路径，不改 API、Schema、权限、错误和发布顺序。空集异常需使同事务 Job 插入回滚。

# 修改方案与决策依据

`reporting_http` 取得共享 `freeze_target_statement()`；Repository 在创建 Export 父行后，以 `INSERT ... SELECT` 冻结项并返回数量，再保存 `request_snapshot.target_count`。SQL 对选中结果按既有顺序重新生成紧凑 Ordinal。一个事务里完成，空集抛 `ContentSelectionEmpty` 回滚。

## 备选方案与取舍

逐批从数据库取 ContentTarget 再插入能限制峰值内存，但仍保留重复序列化和多次往返。集合插入复用现成 SQL 且结果冻结语义更直接。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 集合冻结 ID/Version/Ordinal，空集/排序/错误不变 | #618 / AC3 | not_satisfied | 待 PostgreSQL 回归 |
| R2 | 回归与性能对照 | #618 / AC5 | not_satisfied | 待验证 |

# 计划改动

| 文件 / 模块 | 修改 | 原因 | 对应 |
| --- | --- | --- | --- |
| `reporting_http.py` | 提交选择语句而非目标元组 | 不在 API 进程物化候选 | R1 / E1 |
| `reporting.py` | 集合插入并记录数量 | 数据库内冻结 | R1 / E2 |
| 集成测试与 Reporting README | 验证行为、同步调用链 | 防语义漂移 | R1-R2 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Ordinal、空结果和快照字段 |
| 接口 / 契约 | required | 既有 API 结果和错误保持 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 同事务写入和版本冻结 |
| 用户 / 工作流验收 | required | 导出创建到 Worker 读取结果 |
| 跨组件关键路径 | required | Content Query → Reporting → Job |
| 外部依赖 / 供应方探测 | not_applicable | 无第三方网络调用 |
| 构建 / 打包 / 运行 | not_applicable | 无构建入口或依赖变化 |
| 文档 / 治理 / 其他 | required | Change、模块 README 与当前 CI |

# 风险、兼容性、迁移与回滚

风险是显式 ID 排序空洞和 query 条件不一致；通过真实 PostgreSQL 记录对照验证。无 Migration，回滚应用提交即可恢复旧受理执行路径；已创建 Export 的冻结项结构不变。

# 文档、依赖、部署与发布影响

Reporting 模块 README 更新目标冻结路径。依赖、Runtime、配置、Secret、公共 API 与消费者均不变；无单独部署步骤或生产数据操作。

# 完成审计

- [ ] upstream_re_read：Ready 前重读 #618 / AC3、AC5 与当前 Contract。
- [ ] change_coverage：核对空集、顺序、版本、数量、错误、原子性。
- [ ] reverse_audit：Content 查询入口到 Reporting Item、Job 和 Worker；前端导出动作仍有真实后端支持。
- [ ] unresolved_cleared：Ready 前清零 `not_satisfied`。

# 完成证据与状态

当前为早期 PR 施工记录；实现、测试、性能对照和当前 HEAD CI 待完成。生产服务器实测由用户后续提供。
