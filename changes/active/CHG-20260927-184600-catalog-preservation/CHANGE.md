---
schema: coding-change/v1
id: CHG-20260927-184600-catalog-preservation
title: 调整重置脚本的品牌车型目录保留语义
level: L3
status: ready_for_review
owner: codex
branch: fix/632-catalog-preservation
created: 2026-09-27
updated: 2026-09-27
completion_gate: required
depends_on: []
affected_areas:
  - deployment
  - release
  - operations
  - testing
affected_paths:
  - scripts/deploy/reset_keep_vehicle_catalog.sh
  - scripts/release/release_bundle.py
  - tests/unit/platform/test_reset_keep_vehicle_catalog.py
  - tests/unit/test_release_bundle.py
  - tests/integration/database/test_reset_keep_vehicle_catalog_script.py
  - docs/operations/01_生产部署与离线Release方案.md
contracts: []
data_changes:
  - 品牌车型目录允许任意当前内容状态并在业务数据重置时保持不变
---

# 变更摘要

- **要解决的问题**：现有脚本把品牌和车型都非空作为前置条件，会拒绝合法的“有品牌、无车型”目录状态。
- **拟议修改**：目录是否为空不再影响执行资格；五张目录表继续备份，并增加执行前后内容一致性校验；同步测试和运行说明。
- **预期结果**：无论当前品牌、车型和别名数量如何，目录按现状保留，其他既有重置和安全边界不变。

# 背景、现状与问题

## 背景

Issue #632 固化了用户要求：当前品牌/车型配置本身就是需要保留的事实，不应由维护脚本再判断“应该非空”。

## 当前现状

- 当前脚本固定保留五张品牌/车型目录表与 Alembic 状态。
- 原门禁额外要求 catalog version、brand、model 三者均非空。
- 用户只读查询确认目标环境目录计数为 `8|3|6|0|0`，其中车型为空是合法现状。
- Release workflow 已携带同名脚本，不需要调整打包结构。

## 问题、根因或约束

根因是“目录可读取、应被保留”与“目录内容必须非空”被错误绑定。正确安全边界应由表存在性、Alembic 状态、未知持久表、Extension、外键、挂载边界和执行后验收承担，而不是业务目录数量。

## 不修改的后果

合法目录状态会继续被拒绝，维护人员只能依赖额外绕过参数，增加误判和操作成本。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 目标环境目录计数为 `8|3|6|0|0` | 用户本轮只读 PostgreSQL 查询 | 车型为空是合法目录状态 |
| E2 | 原实现要求 catalog version、brand、model 均非空 | 原 `scripts/deploy/reset_keep_vehicle_catalog.sh` | 非空判断是本次根因 |
| E3 | Release bundle smoke 会调用同名脚本，原调用仍携带旧的空目录特例参数 | `scripts/release/release_bundle.py` / Release dry-run #426 | 必须同步真实 CLI 消费者但不改变 Release 结构 |
| E4 | 新增隔离回归覆盖品牌有数据/车型为空、停写后稳定基线、正常执行和内容变化失败关闭 | `tests/unit/platform/test_reset_keep_vehicle_catalog.py` | Shell 控制流和时序有可重复验证入口 |
| E5 | 正式目录指纹 SQL 可由测试直接从脚本提取并在隔离 PostgreSQL 执行 | `tests/integration/database/test_reset_keep_vehicle_catalog_script.py` | PostgreSQL 专属 SQL 不由 Fake 冒充 |
| E6 | 脚本头部与 help 已包含 dry-run、执行确认、保留范围和重启说明 | 当前分支脚本 | 使用方式已落到交付物 |

## 推断与待确认

无。真实业务环境的实际重置不属于本次验证范围，避免引入数据副作用。

# 目标、成功标准与非目标

## 目标

让品牌/车型目录的当前状态成为唯一保留事实：目录可以部分或全部为空，维护脚本仍按现状保留五张目录表。

## 成功标准

- [x] 品牌有数据、车型为空时 dry-run 可正常完成，且不停止业务容器。
- [x] 五张目录表继续纳入备份，执行后同时校验行数和内容一致性。
- [x] 既有安全检查、业务表范围和 Artifact 边界保持不变。
- [x] 脚本开头和 help 可直接指导 dry-run、执行确认和重启。
- [x] Operations 文档与当前行为一致。

## 范围

- 重置脚本的目录资格判断、目录一致性验收和内联使用说明。
- 对应隔离回归测试。
- 对应生产运行说明。

## 非目标

- 不改变数据库 Schema/Migration。
- 不增加完整 Backup/Restore 能力。
- 不改变既有业务表重置范围。
- 不在真实业务环境执行数据重置。
- 不升级依赖或 Runtime。

## 必须保持不变

- `--env-file`、`--dry-run`、`--execute`、`--yes` 语义。
- 现有表/schema/Extension/外键/挂载/Alembic fail-closed 检查。
- 失败或成功后业务容器保持停止。
- 原始 Excel、PostgreSQL 数据目录、Secret、日志和 env 文件不在重置范围。
- Release 继续使用同名脚本。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 仅调整部署维护脚本、测试和 Operations Owner | E1-E5 | 不进入业务 API/页面实现 |
| 接口与契约 | HTTP/API 不变；移除不再需要的空目录特例参数 | E1、E2 | 合法空目录无需额外参数 |
| 数据与迁移 | Schema/Migration 不变 | E3 | 无迁移和回填 |
| 错误与失败语义 | 目录内容变化仍失败关闭 | E4 | 不降低数据保护 |
| 兼容性 | 既有正式参数和保留/重置边界保持 | E2-E4 | 仅移除错误限制 |
| 部署与回滚 | 随下一 Release 携带；代码回滚即可 | E3 | 本任务不执行部署 |

# 修改方案与决策依据

## 最小充分方案

1. 移除目录必须非空的判断和对应特例参数。
2. 保留现有结构、安全和范围校验。
3. 对五张目录表计算执行前后稳定内容指纹，并继续比较行数。
4. 在脚本头部和 help 写明安全操作流程。
5. 用 fake Docker/psql 隔离测试覆盖合法空车型和失败关闭路径。
6. targeted 更新 Operations Owner。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：目录为空不影响资格 | E1、E2 | 用户要保留的是当前事实，不是某个预设非空状态 |
| D2：增加内容指纹 | E4 | 比只比较行数更直接证明目录内容未变化 |
| D3：不改 Release 结构 | E3 | 现有流程已打包同名脚本 |

## 备选方案与取舍

- 保留空目录特例参数：未采用；合法状态不应依赖绕过参数。
- 只特判车型为空：未采用；会继续把其他合法组合硬编码进脚本。
- 取消目录验收：未采用；会降低现有保护强度。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 品牌有数据、车型为空时 dry-run 成功且不停止业务容器 | #632 / AC1 | satisfied | `test_reset_keep_vehicle_catalog_dry_run_accepts_brand_only_catalog` |
| R2 | 任意当前目录状态都按现状保留，并验证内容一致 | #632 / AC2 | satisfied | 非空门禁已移除；停写后重新冻结 count + fingerprint；execute 时序/一致性回归 + PostgreSQL 指纹 SQL 集成验证 |
| R3 | 既有安全检查和重置范围不退化 | #632 / AC3 | satisfied | PR diff 保留原有安全检查，仅调整目录资格与新增验收 |
| R4 | 脚本开头写明使用方法 | #632 / AC4 | satisfied | 当前脚本头部与 `--help` |
| R5 | 运行文档与验证入口同步 | #632 / AC5 | satisfied | Operations targeted 更新；新增独立回归文件；正式 PR CI 作为合并门禁 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `scripts/deploy/reset_keep_vehicle_catalog.sh` | 放宽目录状态、增加内容指纹和使用说明 | 修复根因并加强验收 | R1-R4 / E1-E4 |
| `tests/unit/platform/test_reset_keep_vehicle_catalog.py` | 增加四条隔离 Shell 工作流回归 | 无真实数据副作用地验证行为与停写基线时序 | R1-R3 / E4 |
| `scripts/release/release_bundle.py`、`tests/unit/test_release_bundle.py` | 移除 Release smoke 对旧空目录特例参数的调用与期望 | 同步真实 CLI 消费者 | R3-R5 / E3 |
| `tests/integration/database/test_reset_keep_vehicle_catalog_script.py` | 在隔离 PostgreSQL 运行正式指纹 SQL | 验证真实 PostgreSQL 语义 | R2-R3 / E5 |
| `docs/operations/01_生产部署与离线Release方案.md` | 同步合法目录状态和验收语义 | 保持运维说明一致 | R4-R5 / E6 |

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立回归证据
- [x] 完成最小实现，不静默扩大范围
- [x] 同步受影响的长期文档
- [x] 建立当前实现的直接验证入口
- [x] 完成需求追溯和完成审计

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | fake Docker/psql 覆盖 dry-run、正常执行、内容变化失败关闭 |
| 接口 / 契约 | required | Shell CLI 的正式参数和 help 行为；HTTP/API/Schema 不受影响 |
| 集成 / 持久化 / 运行依赖 | required | 在 CI 隔离 PostgreSQL 中直接执行从正式脚本提取的目录指纹 SQL，不执行业务数据重置 |
| 用户 / 工作流验收 | required | Bash syntax/help + 隔离脚本工作流 |
| 跨组件关键路径 | not_applicable | 真实数据维护操作有副作用，不作为常规 PR 验证 |
| 外部依赖 / 供应方探测 | not_applicable | 无外部 Provider 变化 |
| 构建 / 打包 / 运行 | required | Release bundle smoke 使用新 CLI 参数；PR Release dry-run 与 CI 验证当前 head |
| 文档 / 治理 / 其他 | required | Operations、Change Completion、Review、PR CI |

## 验证计划

- 目标测试：`tests/unit/platform/test_reset_keep_vehicle_catalog.py`。
- 集成测试：`tests/integration/database/test_reset_keep_vehicle_catalog_script.py`。
- 相关回归：仓库 unit/quality gate 按 CI changed-scope 执行。
- 静态检查或构建：Bash syntax、Ruff、Release bundle smoke、仓库 CI。
- 专项真实边界：隔离 PostgreSQL 只验证正式指纹 SQL；不执行真实业务数据维护。
- 就绪检查：仓库 Change Completion gate 与 PR required checks。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 维护脚本误改变保留目录 | 保留原有 fail-closed 边界并增加内容指纹 |
| 兼容性 | 保持现有正式操作方式 | 空目录特例参数因根因消失而移除 |
| 数据 / Migration | 不适用 | Schema 和 Migration 均不变化 |
| 部署 / 运行 | 下一 Release 携带同名脚本 | Release workflow 已有该入口 |
| 回滚 / 恢复 | 代码可回滚 | 本任务不执行真实业务环境维护动作 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 更新 Operations 单一 Owner。
- **依赖 / Runtime**：不适用；无新增、删除或升级。
- **配置 / Secret**：不适用；配置与 Secret 边界不变。
- **部署 / Release**：不修改流程；同名脚本随正式 Release 携带。
- **兼容 / 消费方通知**：人工维护流程以脚本头部与 Operations 为准，无 API 消费方变化。

# 完成审计

- [x] upstream_re_read：已重新读取 Issue #632、用户决定、脚本、Release workflow 和 Operations Owner。
- [x] change_coverage：AC1-AC5 均显式映射到 R1-R5。
- [x] reverse_audit：已从参数、目录资格、dry-run、执行、备份、目录验收、Artifact 和重启说明反查当前链路。
- [x] unresolved_cleared：R1-R5 无 `not_satisfied`、延期或无依据的不适用项。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 本轮 Linux Bash 隔离副本 | `bash -n` + `--help` | exit 0 | Shell 语法与帮助入口有效 |
| V2 | 本轮 fake Docker/psql 隔离环境 | 目标 pytest 文件 | 永久回归资产覆盖 4 条路径 | 合法空车型、停写后基线、正常执行、内容变化失败关闭 |
| V3 | CI 隔离 PostgreSQL | 指纹 SQL Integration | 永久集成测试资产已纳入当前 head | 正式脚本中的 PostgreSQL SQL 有真实依赖验证入口 |
| V4 | PR #633 当前 diff | 逐文件 patch 复核 | 第一轮 Review Finding 已修复并加回归 | 停写前目录变化不会造成事后误判 |
| V5 | GitHub PR current-head | 仓库 required checks | 由合并门禁强制 | 正式 CI 不被本地证据替代 |

## 未验证内容与剩余风险

- 未在真实业务数据上执行维护动作；这是有意的安全边界。
- 正式 PR CI、独立 Review、main-fresh 和 repository-native Change archive 由交付阶段继续验证。

## 交付状态

- 提交：实现、测试、文档与 Change 已推送到 `fix/632-catalog-preservation`。
- 拉取请求：#633。
- CI：required checks 作为 merge 前硬门禁。
- 合并：仅在 current-head Review/CI 满足后执行。
- Change 归档：合并后由 repository-native 自动化处理。
- 发布 / 部署：不在本次授权范围。

## 备注

无。
