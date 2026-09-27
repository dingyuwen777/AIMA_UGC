---
schema: coding-change/v1
id: CHG-20260927-184600-catalog-preservation
title: 调整重置脚本的品牌车型目录保留语义
level: L3
status: in_progress
owner: codex
branch: fix/632-catalog-preservation
created: 2026-09-27
updated: 2026-09-27
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - operations
  - testing
affected_paths:
  - scripts/deploy/reset_keep_vehicle_catalog.sh
  - tests/unit/platform/test_internal_v1_deployment.py
  - docs/operations/01_生产部署与离线Release方案.md
contracts: []
data_changes:
  - 重置脚本允许品牌/车型目录处于任意当前状态并原样保留五张目录表
---

# 变更摘要

## 要解决的问题

当前 `scripts/deploy/reset_keep_vehicle_catalog.sh` 把“目录可保留”错误收紧为“catalog version、品牌、车型都必须非空”。已确认合法环境可以只有品牌、没有车型；用户要求无论品牌/车型当前如何配置，都必须原样保留，只重置其他业务数据。

## 目标

- 五张品牌/车型目录表无论当前数据状态是否为空，都按执行前状态原样保留。
- 保留现有业务数据重置范围、Artifact 删除边界、事务和失败停机安全边界。
- 执行前备份五张目录表；执行后同时校验计数和内容指纹。
- 脚本开头直接写明使用方法、保留/重置范围、确认文本和执行后启动方式。
- 用自动化回归证明“brands=3、models=0”时 dry-run 成功且不会停止业务容器。

## 非目标

- 不改变数据库 Schema/Migration。
- 不新增全库 Backup/Restore。
- 不改变其他业务表的既有重置范围。
- 不执行真实环境 `--execute`。
- 不升级依赖、Runtime 或修改 Release 结构。

## 必须保持不变

- `--env-file`、`--dry-run`、`--execute`、`--yes` 的既有语义。
- 非 public 持久表、Extension 管理表、危险外键、Artifact 嵌套挂载等 fail-closed 检查。
- 执行阶段先停止业务写入方，失败或成功后都保持业务容器停止。
- 原始 Excel、Secret、env、日志和 PostgreSQL 数据目录不在删除范围。
- Release 继续使用同名 `reset_keep_vehicle_catalog.sh`。

# 方案与取舍

## 采用方案

删除 `--allow-empty-catalog` 及“品牌/车型都必须非空”的资格判断；保留目录表存在性、Alembic 合法性与所有删除边界检查。对五张目录表计算稳定内容指纹，执行后必须与执行前一致。

## 备选方案

1. 保留 `--allow-empty-catalog` 并要求用户显式绕过：拒绝。合法业务状态不应被标记为异常，也不应要求额外危险开关。
2. 只放宽 `vehicle_models=0`：拒绝。用户已明确要求目录无论当前配置如何都原样保留，脚本不应替业务判断目录应该非空。
3. 完全取消目录校验：拒绝。仍需校验表存在、Alembic 状态、计数和内容指纹，避免保留目录被意外改写。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 任意当前品牌/车型目录状态都可进入 dry-run/execute 资格判断 | #632 / AC1-AC2 | not_satisfied | 待实现与目标回归 |
| R2 | 五张目录表继续备份，并在重置后内容完全一致 | #632 / AC2 | not_satisfied | 待实现指纹校验与审查 |
| R3 | 既有业务数据重置范围和安全边界不退化 | #632 / AC3 | not_satisfied | 待 diff/review/targeted validation |
| R4 | 脚本开头包含可直接操作的使用说明 | #632 / AC4 | not_satisfied | 待实现和 help 检查 |
| R5 | 运行文档、目标测试、Shell/质量/CI 门禁通过 | #632 / AC5 | not_satisfied | 待验证 |

# Validation Matrix

| 维度 | 状态 | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 模拟 catalog_versions=8、brands=3、models=0 的 dry-run |
| 接口 / Contract | not_applicable | 不改 HTTP/API/CLI 参数名称；Shell CLI 由行为测试与 help 覆盖 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 本任务不执行真实 PostgreSQL destructive path；SQL/Compose 边界保持原实现并做代码审查 |
| 用户 / Workflow Acceptance | required | `bash -n`、`--help`、模拟 dry-run |
| 跨组件 Golden Path | not_applicable | 不执行真实重置，避免不必要的数据副作用 |
| 外部依赖 Probe | not_applicable | 无外部 Provider 变化 |
| Build / Package / Runtime | required | Release workflow 仍包含同名脚本；CI current-head gate |
| Docs / Governance / Other | required | Operations 文档、Change Completion、Review、PR CI |

# 计划

- [x] 建立 Requirement Source 与任务分支。
- [x] 创建本 Change。
- [ ] 替换重置脚本并保持文件名不变。
- [ ] 补“品牌有数据、车型为空”的 dry-run 回归。
- [ ] targeted 同步生产运行文档。
- [ ] 执行目标验证、Completion Audit、两阶段 Review。
- [ ] PR current-head CI 通过后合并 main。
- [ ] 验证 main fresh CI、Change Archive 与 Issue Closure。

# 风险、兼容、部署与回滚

- **风险**：这是破坏性运维工具；测试禁止执行真实 `--execute`。
- **兼容**：移除 `--allow-empty-catalog`；其他正式参数保持。该参数只用于绕过原有错误门禁，不再有存在价值。
- **Schema/Migration**：无。
- **依赖/Runtime**：无。
- **Release**：Release workflow 已包含同名脚本，替换后随下一 Release 进入部署包。
- **回滚**：代码回滚即可；本任务不执行真实数据重置。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 Issue #632、用户决定、脚本与 Operations Owner。
- [ ] change_coverage：确认 AC1-AC5 全部映射到实现/测试/文档。
- [ ] reverse_audit：从 Shell 参数→资格检查→dry-run/execute→目录保留→业务数据重置→启动说明反查。
- [ ] unresolved_cleared：R1-R5 清零 not_satisfied。

# 新鲜证据

开发完成后填写。

# Git / PR / 交付状态

- Branch: `fix/632-catalog-preservation`
- Requirement Source: #632
- PR: 待创建
- Merge: 待执行
- Main-fresh: 待验证
- Change Archive: 待验证
- Issue Closure: 待验证
