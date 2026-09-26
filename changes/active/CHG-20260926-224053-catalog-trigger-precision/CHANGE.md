---
schema: coding-change/v1
id: CHG-20260926-224053-catalog-trigger-precision
title: 收窄声音广场目录更新触发的投影刷新
level: L3
status: ready_for_review
owner: codex
branch: fix/618-catalog-trigger
created: 2026-09-26
updated: 2026-09-26
completion_gate: required
depends_on: []
affected_areas:
  - content
  - vehicles
  - database
affected_paths:
  - migrations/versions/
  - tests/integration/content/
  - docs/operations/04_声音广场读模型回填与性能验证.md
contracts: []
data_changes:
  - vehicle_brands/vehicle_models UPDATE 后声音广场投影的同步刷新条件
---

# 目标与事实

Issue #618 的第一工作包。Migration 0061 的目录 UPDATE 语句级 Trigger 对任何变更都会枚举关联 Content；`_touch_brand()` 的版本更新也会触发这一过程。当前投影的车型维度计算实际使用 `vehicle_brands.role` 和 `vehicle_models.merged_into_id`。本工作包只在这些值发生真实变化时枚举和刷新受影响 Content。

# 成功标准与边界

- 别名、显示名、版本等无关字段更新后，已有投影行不发生写入。
- role / merged_into_id 变化后，受影响投影与筛选目录仍在同一事务内正确刷新。
- Migration 0069 可升级、降级；公共 API、数据含义、权限和依赖不变。
- 隔离 PostgreSQL 回归及大量关联 Content 的前后对照证明无关更新不再随 Content 数量放大。

非目标：真正影响投影的目录变更异步化；生产服务器部署或数据操作。

# 方案与取舍

使用 transition OLD/NEW TABLE 比较投影依赖字段，只有值变化的目录 ID 才进入原有集合刷新。保留语句级 Trigger 与同事务一致性。单纯跳过应用层 no-op UPDATE 无法覆盖其他写入口；把刷新改为异步会改变一致性语义，均不作为本工作包的根因修复。

Migration 只替换函数，降级恢复 0061 的函数逻辑；无需回填或改变表结构。新版应用与旧版 Schema 使用顺序遵循项目正式迁移流程。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 无关字段更新不刷新关联 Content | #618 / AC1 | satisfied | 真实 PostgreSQL：别名与车型显示名更新保持投影 `updated_at` 不变；1000 条 Content 对照重写 1000→0 |
| R2 | 真实依赖字段变化保持投影结果和事务一致 | #618 / AC1 | satisfied | 角色 owned→competitor 与车型 merge 后，同事务提交的投影维度变化；集成测试 2 passed |
| R3 | 功能、Contract、迁移兼容且性能有提升证据 | #618 / AC5 | satisfied | 0069 降级/升级成功，`alembic check` 无差异，品牌车型回归 6 passed；1000 条同数据基准三次耗时见下方 |

# 计划改动与验证矩阵

| 范围 | 动作 | 验证 |
| --- | --- | --- |
| Migration 0069 | 根据 transition table 差异筛选目录 ID | 升降级、PostgreSQL 投影回归 |
| Content 集成测试 | 无关更新、role 与合并更新 | 结果、更新时间、筛选目录 |
| 性能对照 | 大量关联 Content 的 alias touch | 同规模旧/新耗时与实际投影写入 |

| 验证层 | 是否要求 | 依据 |
| --- | --- | --- |
| 行为 / 组件 | required | 目录更新对投影的影响 |
| 接口 / Contract | not_applicable | 公共结构与语义不变 |
| PostgreSQL 集成 / Migration | required | Trigger、事务和可逆性 |
| 用户工作流 | required | 管理员别名保存及筛选结果 |
| 跨组件路径 | required | Catalog → Trigger → Projection → 查询 |
| 外部 Provider | not_applicable | 不调用供应商 |
| 构建 / 文档 / 治理 | required | 静态、迁移、Change、CI；文档影响复核 |

# 完成审计

- [x] upstream_re_read：重读 #618、Blueprint 的同事务投影约束和 0061/0067 当前函数；投影 SQL 使用品牌 `role` 与车型 `merged_into_id`。
- [x] change_coverage：R1–R3 分别有失败回归、修复后的真实数据库结果、迁移和同数据性能对照。
- [x] reverse_audit：管理员别名/角色、车型显示名/合并入口经 Catalog → Trigger → Projection → 声音广场维度覆盖；投影使用字段反查目录更新条件。无公共前端 Contract 变化。
- [x] unresolved_cleared：本工作包无 `not_satisfied`；服务器实际规模与 P95 仍待部署后实测，不把本地基准当生产结论。

# 新鲜证据与剩余边界

隔离 PostgreSQL 18.4、同一千条关联 Content：原 0068 目录版本 touch 三次事务为 33.919/36.879/43.920 ms，每次重写 1000 条投影；0069 为 9.370/4.399/6.105 ms，每次重写 0 条。测量脚本使用生产导入入口准备相同数据，位于本地忽略目录且不作为发布物。结果只证明无关目录更新的增长项被切断，不代表生产服务器的绝对时延。

Red：新增 PostgreSQL 回归在 0068 因别名 touch 改写投影时间而失败。Green：0069 后该测试和原有 Stage 5 纵切共 2 passed；品牌车型仓储回归 6 passed。Migration 降级至 0068、再升级 0069 成功；`alembic check` 报告无新升级操作。`ruff check`/`ruff format --check`、文档导航和事实检查通过。正式 PR 当前 HEAD CI 仍须验证。

公共 HTTP/Job Contract、依赖与业务表结构均未改变。部署只需遵循现有先 Migration 后应用/Worker 顺序；若回滚至 0068，目录无关更新的旧性能问题会重现，但业务事实和派生数据不丢失。生产部署、生产迁移与真实大规模 P95 尚未执行。
