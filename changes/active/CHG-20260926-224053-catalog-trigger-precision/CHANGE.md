---
schema: coding-change/v1
id: CHG-20260926-224053-catalog-trigger-precision
title: 收窄声音广场目录更新触发的投影刷新
level: L3
status: in_progress
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
| R1 | 无关字段更新不刷新关联 Content | #618 / AC1 | not_satisfied | 待 PostgreSQL 失败用例与修复验证 |
| R2 | 真实依赖字段变化保持投影结果和事务一致 | #618 / AC1；项目投影规则 | not_satisfied | 待 PostgreSQL 回归 |
| R3 | 功能、Contract、迁移兼容且性能有提升证据 | 用户本轮要求；#618 | not_satisfied | 待迁移升降级、对照和 CI |

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

- [ ] upstream_re_read：重读 #618 与项目投影事实。
- [ ] change_coverage：逐项比较 R1–R3 与实现/测试。
- [ ] reverse_audit：从目录写入到声音广场结果、从投影维度反查目录依赖。
- [ ] unresolved_cleared：无未满足要求，记录剩余服务器验证边界。
