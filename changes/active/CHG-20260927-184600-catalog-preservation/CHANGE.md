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
  - operations
  - testing
affected_paths:
  - scripts/deploy/reset_keep_vehicle_catalog.sh
  - tests/unit/platform/test_reset_keep_vehicle_catalog.py
  - docs/operations/01_生产部署与离线Release方案.md
contracts: []
data_changes:
  - 重置脚本允许品牌/车型目录处于任意当前状态并原样保留五张目录表
---

# 变更摘要

- **要解决的问题**：部署重置脚本把“品牌/车型目录可保留”错误收紧为“catalog version、品牌、车型都必须非空”，导致合法的“有品牌、无车型”状态无法通过 dry-run。
- **拟议修改**：删除 `--allow-empty-catalog` 与非空资格门禁，按现状原样保留五张品牌/车型目录表；执行前后增加内容指纹一致性校验；补隔离回归与运行说明。
- **预期结果**：品牌、车型或别名无论当前是否为空，都不影响重置资格；其他业务数据重置范围和既有 fail-closed 安全边界保持不变。

# 背景、现状与问题

## 背景

Issue #632 固化了本轮用户决定：只重置其他业务数据，当前品牌/车型目录无论怎样配置都必须原样保留。

## 当前现状

- `scripts/deploy/reset_keep_vehicle_catalog.sh` 已保留 `vehicle_catalog_versions`、`vehicle_brands`、`vehicle_brand_aliases`、`vehicle_models`、`vehicle_model_aliases` 与 `alembic_version`。
- 原实现额外要求 `vehicle_catalog_versions > 0 AND vehicle_brands > 0 AND vehicle_models > 0`，否则拒绝继续。
- 用户在目标环境只读查询确认：`catalog_versions=8`、`brands=3`、`brand_aliases=6`、`models=0`、`model_aliases=0`；该状态是明确需要保留的合法状态。
- 现有 Release workflow 已包含同名 `scripts/deploy/reset_keep_vehicle_catalog.sh`，无需修改打包结构。

## 问题、根因或约束

问题不是数据库目录真的损坏，而是脚本把“保留对象存在且可读取”与“品牌、车型都必须非空”混成一个前置条件。目录是否为空属于合法业务状态，不应成为维护脚本的执行资格判断。安全边界仍应由表存在性、Alembic 状态、未知表/Extension/危险外键/嵌套挂载检查和执行后验收承担。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 目标环境真实目录计数为 `8|3|6|0|0`，车型为空但品牌存在 | 用户本轮只读 PostgreSQL 查询 | 空车型是合法现状，不能用非空门禁阻塞 |
| E2 | 原脚本显式要求 version、brand、model 三者都大于 0 | `scripts/deploy/reset_keep_vehicle_catalog.sh` 原实现 | 根因是脚本门禁过严 |
| E3 | Release workflow 已携带同名脚本 | `.github/workflows/release.yml` 当前事实 | 只需替换同名脚本，不改 Release 结构 |
| E4 | 隔离 fake Docker/psql harness 对品牌有数据、车型为空的 dry-run/execute/fingerprint-fail 三条路径通过 | 本轮临时验证：`pytest -q /mnt/data/test_reset_keep_vehicle_catalog.py` → 3 passed | 新语义和 fail-closed 指纹检查可执行 |
| E5 | Shell 语法与 help 已验证，help 明确确认文本和目录可为空 | 本轮临时验证：`bash -n /mnt/data/reset_keep_vehicle_catalog_repo.sh`、`--help` | 脚本语法与用户操作说明成立 |

# 目标、成功标准与非目标

## 目标

无论当前品牌/车型目录是“都有数据 / 只有品牌 / 只有车型（若数据库约束允许）/ 全空”，五张目录表都按当前状态原样保留；只重置其他既有业务数据和 Artifact 实体。

## 成功标准

- [x] `brands=3、models=0` 时 dry-run 成功，不再需要任何空目录绕过参数。
- [x] 五张目录表仍在 execute 前备份，清理后同时校验计数与内容指纹。
- [x] 原有未知持久表、Extension、危险外键、Artifact 嵌套挂载、Alembic 等安全门禁保持。
- [x] 脚本开头和 `--help` 明确 dry-run、execute、确认文本、保留/重置范围与重启方式。
- [x] Operations 文档同步“目录允许部分或全部为空”和内容指纹验收语义。
- [ ] PR current-head required CI 全部通过后才允许合并。

## 非目标

- 不改变数据库 Schema/Migration。
- 不新增完整 Backup/Restore。
- 不扩大或缩小其他 public 业务表的既有重置范围。
- 不执行真实环境 `--execute`。
- 不升级依赖、Runtime 或改造 Release 结构。

## 必须保持不变

- `--env-file`、`--dry-run`、`--execute`、`--yes` 语义。
- 执行阶段先停止 Frontend/API/Worker/Scheduler/Configure/Migrate；失败或成功后业务容器保持停止。
- 原始 Excel/历史导入源目录、PostgreSQL 数据目录、Secret、日志、env 文件不删除。
- Release 继续携带同名 `reset_keep_vehicle_catalog.sh`。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 合法目录状态 | 不要求品牌、车型或别名非空 | Issue #632、E1 | 删除 `--allow-empty-catalog` 与非空门禁 |
| 保留边界 | 五张品牌/车型目录表和 Alembic 原样保留 | 用户目标、原脚本设计 | 不修改保留表集合 |
| 安全验收 | 计数一致之外增加内容指纹一致 | L3 破坏性运维风险 | 目录内容意外变化时 fail closed |
| 测试边界 | 不执行真实数据重置，用 fake Docker/psql 隔离验证 Shell 工作流 | 非目标与数据安全约束 | 无真实环境副作用 |
| Release | 沿用同名脚本与现有打包入口 | E3 | 不改 workflow/产物结构 |

# 修改方案与决策依据

## 最小充分方案

1. 删除 `ALLOW_EMPTY_CATALOG`、`--allow-empty-catalog` 和三表必须非空的资格判断。
2. 保留表存在性、Alembic、未知 schema、Extension、危险外键和 Artifact mount 检查。
3. dry-run 前打印真实目录计数，并计算五张目录表稳定内容指纹。
4. execute 后继续校验目录计数，并新增内容指纹一致性校验；不一致立即失败并保持业务容器停止。
5. 在脚本 shebang 后和 `--help` 中写清安全使用流程；targeted 同步 Operations Owner。
6. 新增隔离回归，覆盖“品牌存在/车型为空”、执行成功和指纹变化 fail-closed。

## 决策依据

- 目录为空与否不决定是否应该保留，保留策略只依赖当前事实与用户目标。
- 不增加新的数据恢复机制；当前脚本仍不是 Backup/Restore。
- 内容指纹比只比较行数更直接证明“原样保留”，且不改变数据库 Schema 或持久状态。

# 备选方案与取舍

- **保留 `--allow-empty-catalog`**：未采用。合法业务状态不应要求额外绕过参数，且容易把真正异常和正常空状态混淆。
- **只允许 `vehicle_models=0`**：未采用。用户要求的是任意当前品牌/车型配置均原样保留，不应继续硬编码“哪些表必须非空”。
- **完全取消目录校验**：未采用。仍保留表存在、Alembic、计数和内容指纹验收，避免为了放宽合法状态而降低数据安全。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 任意当前品牌/车型目录状态都能进入 dry-run/execute 资格判断 | #632 / AC1-AC2 | satisfied | 脚本已移除非空门禁和 `--allow-empty-catalog`；隔离 dry-run 覆盖 `8|3|6|0|0` |
| R2 | 五张目录表继续备份并在 execute 后内容完全一致 | #632 / AC2 | satisfied | pg_dump 范围不变；新增 before/after fingerprint；成功与 fingerprint mismatch 回归均已建立 |
| R3 | 既有重置范围与安全边界不退化 | #632 / AC3 | satisfied | PR diff 只删除非空资格判断；未知表/Extension/外键/mount/Alembic/停机/事务/验收逻辑保留 |
| R4 | 脚本开头写明直接使用方法 | #632 / AC4 | satisfied | shebang 后新增 dry-run/execute/确认文本/保留范围/重启说明，`--help` 同步 |
| R5 | 运行文档和目标验证闭环 | #632 / AC5 | satisfied | Operations targeted 更新；本轮隔离 harness 3/3、Shell syntax/help 通过；PR current-head CI 作为合并硬门禁 |

# 计划改动

| 文件 / 模块 / 资产 | 修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| `scripts/deploy/reset_keep_vehicle_catalog.sh` | 放宽目录空状态、增加指纹校验和顶部使用说明 | 修复合法目录被误拒并加强原样保留验收 | R1-R4 |
| `tests/unit/platform/test_reset_keep_vehicle_catalog.py` | 新增 fake Docker/psql 的三条 Shell 工作流回归 | 无真实数据副作用地验证 dry-run/execute/fail-closed | R1-R3 |
| `docs/operations/01_生产部署与离线Release方案.md` | 说明目录可为空、确认文本和指纹验收 | 同步当前运维行为 | R4-R5 |
| 本 Change / PR | Requirement、Evidence、Review、CI 追溯 | L3 交付门禁 | R1-R5 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | fake Docker/psql：dry-run 合法空车型、execute 成功、指纹变化失败 |
| 接口 / 契约 | not_applicable | 无 HTTP/API/Schema Contract；Shell 参数除删除错误特例外保持 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不对真实 PostgreSQL 执行 destructive path；本轮不需要真实数据库写入证明 |
| 用户 / 工作流验收 | required | `bash -n`、`--help`、隔离 Shell 工作流 |
| 跨组件 Golden Path | not_applicable | 真实重置会产生数据副作用，不作为本次验证手段 |
| 外部依赖 Probe | not_applicable | 无第三方 Provider 变化 |
| Build / Package / Runtime | required | Release workflow 继续包含同名脚本；PR current-head CI |
| Docs / Governance / Other | required | Operations targeted、Change machine contract、Completion Audit、Review、PR CI |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理方式 |
| --- | --- | --- |
| 主要风险 | 破坏性脚本误改保留目录或扩大重置范围 | 保留所有原 fail-closed 边界，增加内容指纹和隔离回归 |
| CLI 兼容 | 移除 `--allow-empty-catalog` | 该参数只用于绕过错误非空门禁；合法空目录现在无需参数 |
| 数据 / Schema / Migration | 无 Schema/Migration 变化 | 不修改表结构和持久数据模型 |
| 部署 | 下一 Release 自动携带同名脚本 | 不修改 Release workflow |
| 回滚 | 代码回滚到上一版本 | 本任务不执行真实重置，因此没有生产数据回滚动作 |

# 文档、依赖、部署与发布影响

- **Docs Impact：targeted**。Operations 是该生产维护行为的单一解释 Owner，已同步“目录允许为空”和内容指纹验收。
- **依赖 / Runtime**：不新增、删除或升级。
- **配置 / Secret**：无变化。
- **部署 / Release**：同名脚本由现有 Release workflow 打包；本任务不执行 Release、Deploy 或真实重置。
- **Contract / Schema / Migration**：无。

# 完成审计

- [x] upstream_re_read：重新读取 Issue #632、用户本轮决定、当前脚本、Release workflow 和 Operations Owner。
- [x] change_coverage：AC1-AC5 已映射到 R1-R5、三个实现文件和验证矩阵，没有遗漏“无论当前配置如何都原样保留”。
- [x] reverse_audit：从参数→目录资格→dry-run→execute 停机/备份→事务重置→目录计数/指纹→Artifact→启动说明反查，既有安全边界仍可达。
- [x] unresolved_cleared：R1-R5 均为 satisfied；PR current-head CI 属于合并门禁，不伪造为已通过。

# 完成证据与状态

## 新鲜证据

| 证据 | revision / 环境 | 命令 / 检查 | 结果 | 证明范围 |
| --- | --- | --- | --- | --- |
| V1 | 本轮隔离临时目录 / Linux Bash | `bash -n /mnt/data/reset_keep_vehicle_catalog_repo.sh` | exit 0 | Shell 语法有效 |
| V2 | 本轮隔离临时目录 / Linux Bash | `bash /mnt/data/reset_keep_vehicle_catalog_repo.sh --help` | exit 0；包含确认文本、目录可为空和重启命令 | 用户操作说明 |
| V3 | 本轮隔离 fake Docker/psql | `pytest -q /mnt/data/test_reset_keep_vehicle_catalog.py` | 3 passed | 空车型 dry-run、execute 成功、fingerprint mismatch fail-closed |
| V4 | PR #633 diff | 逐文件 patch 复核 | 脚本、测试、Operations 仅覆盖 Issue #632 范围 | 无无关改动；既有安全边界保留 |
| V5 | PR #633 current head | GitHub Actions | 待 current-head required checks；合并前硬门禁 | 仓库正式 CI |

## 未验证内容与剩余风险

- 未对真实 PostgreSQL 或真实 Artifact 数据执行 `--execute`；这是刻意的安全边界，不把破坏性真实运行作为普通 CI 验证。
- current-head PR CI 尚需通过后才允许 merge。

## Git / PR / 交付状态

- Branch: `fix/632-catalog-preservation`
- Requirement Source: #632
- PR: #633
- Review: 待 current-head CI 后独立复核
- Merge: 待 required checks
- Main-fresh: 待 merge 后验证
- Change Archive: 待 repository-native archive
- Issue Closure: 待 post-merge Closure Audit
- Release / Deploy: 不在本次授权范围
