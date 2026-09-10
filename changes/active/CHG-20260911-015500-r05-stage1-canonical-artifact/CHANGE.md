---
schema: coding-change/v1
id: CHG-20260911-015500-r05-stage1-canonical-artifact
title: Roadmap 05 Stage 1 Canonical Artifact 基础
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feat/r05-stage1-canonical-artifact
created: 2026-09-11
updated: 2026-09-11
completion_gate: required
depends_on: []
affected_areas:
  - platform
  - storage
  - database
  - contracts
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/platform/storage/
  - backend/src/aima_ugc/adapters/persistence/postgres/artifact_metadata.py
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions/
  - tests/unit/platform/
  - tests/integration/database/
  - tests/integration/content/
  - tests/integration/collection/
  - tests/integration/ingestion/
  - tests/contracts/
  - docs/blueprint/02_采集系统与数据标准化.md
  - docs/blueprint/03_数据库与文件存储.md
  - docs/roadmap/05_可重放数据底座与监测重分类实施路线.md
  - changes/active/CHG-20260911-015500-r05-stage1-canonical-artifact/CHANGE.md
contracts:
  - CanonicalContentV1 line contract
  - Canonical Artifact JSONL.gz file contract
  - canonical_artifact_links persistence contract
data_changes:
  - add canonical_artifact_links table
---

# 变更摘要

- **要解决的问题**：当前 Mapper 产生的 `CanonicalContentV1` 只在内存中继续进入 Filter/Content，既没有可复用的流式持久格式，也没有把 Canonical Artifact 强约束绑定到真实 Import/Collection 父事实的关系。
- **拟议修改**：使用标准库 `gzip` + 磁盘临时流建立共享 Writer/Reader；通过 ArtifactService/ArtifactStore 落盘并核对 SHA-256/byte size；新增一张只承担 Canonical Artifact 父级关系的最小强外键表。
- **预期结果**：后续 Stage 2/3 可以在不复制业务规则的前提下写入/读取同一份 `*.jsonl.gz`；本 Stage 不切换任何现有 Runtime。

# 背景、现状与问题

## 已确认事实

| 证据编号 | 已确认事实 | 来源 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Stage 1 只新增共享 Canonical Artifact 基础，不切换 Excel/TikHub/Voice Plaza Runtime | `docs/roadmap/05_可重放数据底座与监测重分类实施路线.md` Stage 1 | Stage 2–4 不进入实现 |
| E2 | `ArtifactService.store_stream()` 以 pending → stored 管理元数据，`LocalArtifactStore.put_stream()` 流式计算 SHA-256/byte size 并原子 no-overwrite 发布 | `backend/src/aima_ugc/platform/storage/service.py`、`backend/src/aima_ugc/adapters/storage/local/store.py` | Writer 必须复用正式生命周期，不重写 Store |
| E3 | 现有 `artifacts` 没有父级关系；Import Batch/Campaign Item 和 Provider Attempt 的 Artifact 外键均承担既有 Raw/Source 语义 | `backend/src/aima_ugc/platform/storage/tables.py`、`backend/src/aima_ugc/modules/ingestion/tables.py`、`backend/src/aima_ugc/modules/ingestion/historical_tables.py`、`backend/src/aima_ugc/modules/collection/tables.py` | 不得污染既有字段；确认需要最小 Schema/Migration |
| E4 | `CanonicalContentV1` 是当前逐行唯一 Contract，且 `extra=forbid` | `backend/src/aima_ugc/contracts/canonical/content.py`、`backend/src/aima_ugc/contracts/canonical/base.py` | Reader 直接调用当前 Pydantic Contract fail closed |
| E5 | 当前 `origin/main` 与开工 HEAD 均为 `e2df5e5bdbebe1712aaa9e74d6ed9afb7cf88069`，工作区开工时无未提交改动 | `git fetch`、`git status`、`git rev-parse` | 从最新 `main` 建立本地任务分支 |
| E6 | GitHub Issue #439 是本 Stage 的稳定 Requirement Source，包含 AC1–AC7 可回写 task list | `https://github.com/dingyuwen777/AIMA_UGC/issues/439` | `Issue ↔ Change ↔ branch ↔ PR` 稳定追溯 |

## 推断与待确认

- 本 Stage 使用每个 Canonical Artifact 恰好一个直接父级：Import Batch、Campaign Item、Collection Scope 或 Provider Attempt。Scope/Attempt 可继续追溯 Run/Request/Raw，Campaign Item 可继续追溯 Campaign/Source/Chunk，不冗余复制整条 lineage。
- 仓库外生产数据库和实际数量未读取；Migration 只新增空表，不重写旧数据，容量实测属于 Roadmap 03/后续 Runtime Stage。

# 目标、成功标准与非目标

## 成功标准

- [ ] 共享 Writer 以有界内存存储可复现 `*.jsonl.gz`，一行一个当前合法 `CanonicalContentV1`。
- [ ] 共享 Reader 在吐出 Canonical 前流式核对 Artifact SHA-256/byte size，再逐行使用当前 Contract fail closed。
- [ ] Canonical Artifact 经 ArtifactService/ArtifactStore 落盘，与真实父级关系及 `linked` 状态在同一 PostgreSQL 短事务内提交。
- [ ] Migration/Schema 强制一个 Artifact 恰好一个允许的父级，且不改公共 HTTP/Canonical Contract、依赖或现有业务表语义。
- [ ] 目标失败/完整性/流式/PostgreSQL/Migration/main-safe/打包/治理证据均闭环。
- [ ] 独立 Review、exact-head PR CI、guarded merge、main 新鲜验证、原生归档、Roadmap 状态和 Issue Closure 完成。

## 范围

- Platform Storage 的 Canonical Artifact Writer/Reader、完整性异常与 lineage 输入。
- Artifact metadata PostgreSQL 短事务绑定、新表和 Alembic Migration。
- 目标 Unit/Contract/PostgreSQL/Migration/main-safe/打包/文档/治理验证。
- Blueprint 记录已实现基础；Roadmap 状态只收口 Stage 1 并解锁 Stage 2。

## 非目标

- 不接入 Excel/TikHub 现有 Runtime，不实现 Replay/Backfill。
- 不实现 Stage 2/3/4，不新增 Monitoring Membership、Filter History、Platform Registry、第二数据库或消息总线。
- 不改 Brand/Vehicle Filter、Content identity/Owner、Provider Request/Attempt/Raw/Candidate/费用、Voice Plaza 行为。
- 不为尚不存在的旧数据增加兼容路径，不升级依赖/Runtime。

## 必须保持不变

- `CanonicalContentV1` 字段、校验、生成 JSON Schema 与公开导入路径不变。
- ArtifactStore 只处理字节；ArtifactService 处理身份、元数据和生命周期；文件 I/O 不置于长数据库事务。
- 现有 Excel/TikHub/Voice Plaza 代码、调用链和输出不切换。
- PostgreSQL 18、Python 3.14、uv/lock、模块化单体和单一持久 Job Runtime 不变。

# 修改方案与决策依据

## 方案比较

| 方案 | 优点 | 代价/风险 | 结论 |
| --- | --- | --- | --- |
| A. 专用 `canonical_artifact_links` 强外键表，每行恰好一个显式父列 | 父级存在性、类型和恰一语义可由 PostgreSQL 直接强制；不改旧表字段 | 新增一张表和 Migration；Platform 需要显式了解允许的父表 | **推荐**：满足当前 Stage 最小持久缺口，为 Stage 2/3 保留足够直接父级 |
| B. `parent_type + parent_id` 泛化字符串关系 | 列少、易扩展 | 无法用普通外键保证父级真实存在，需要 trigger/应用级核验，易形成通用但弱约束的平行元数据 | 不采用 |
| C. 复用现有 Raw/Source `artifact_id` 字段 | 无 Migration | 一个字段同时表示原始文件/Raw 和 Canonical，破坏当前 lineage 与恢复语义 | 不采用 |

## 实施步骤

1. Canonical 文件 Contract
   → 修改范围：`backend/src/aima_ugc/platform/storage/`、目标 Unit 测试
   → 预期结果：磁盘临时流写入固定 `mtime=0` gzip，ArtifactStore 从头流式存储；Reader 先流式校验压缩字节再逐行 Contract 解析
   → 验证：语义往返、Unicode、大文本、空字段、可复现、gzip/JSON/Contract 错误、大数据生成器内存上界
2. Lineage 与生命周期
   → 修改范围：Storage model/port/service/table、PostgreSQL metadata gateway、Migration、集成测试
   → 预期结果：Artifact stored 后以一个短事务插入强外键关系并 CAS 为 linked；任一失败 fail closed
   → 验证：四种父级、恰一约束、外键、重复绑定、状态冲突、Migration upgrade/downgrade
3. Main-safe 与文档
   → 修改范围：既有 Excel/TikHub/Voice Plaza 回归，Blueprint/Roadmap/Change
   → 预期结果：现有入口无调用新 Writer；文档只把基础写成当前事实，后续 Stage 仍为未实现
   → 验证：Contract 生成物无 diff、目标与分层回归、Wheel、Docs/Owner/Change 门禁
4. 审查与交付
   → 修改范围：完成审计、独立 Review、PR/CI/merge/main/archive/Issue
   → 预期结果：每个 AC 都有直接证据，不以当前 Change 或 CI 代替上游完成定义
   → 验证：`check_change_completion.py`、exact-head required checks、REST expected-head merge、main fresh CI、repository-native archive、Issue 写后重读/关闭

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | AC1：流式、可复现 JSONL.gz Writer 并保持 Unicode/大文本/空可选字段语义 | https://github.com/dingyuwen777/AIMA_UGC/issues/439#AC1 | satisfied | `canonical.py` 使用磁盘临时流、固定 gzip `mtime=0`、逐条排序 JSON；目标 Unit 覆盖 Unicode、512 KiB 级文本、`None`、语义往返、字节/hash 可复现和 256 条生成器内存上界。 |
| R2 | AC2：有界 Reader 使用当前 Contract 并对 gzip/JSON/Contract 错误 fail closed | https://github.com/dingyuwen777/AIMA_UGC/issues/439#AC2 | satisfied | Reader 把压缩字节流式复制到磁盘临时文件，首遍完整预检 gzip/JSON/当前 Pydantic Contract，第二遍才逐条返回；损坏 gzip、截断合法前缀、非法 JSON、非法 Contract 均断言零输出。 |
| R3 | AC3：核对 SHA-256/byte size，完整性失配不得读取 | https://github.com/dingyuwen777/AIMA_UGC/issues/439#AC3 | satisfied | 复用 `ArtifactStore.copy_to()` 流式计算实体 SHA-256/byte size；目标测试分别伪造 hash 与大小并验证首条输出前拒绝。 |
| R4 | AC4：正式 Artifact 生命周期 + 真实父级强外键 + 恰一关系 | https://github.com/dingyuwen777/AIMA_UGC/issues/439#AC4 | satisfied | Writer 复用 `ArtifactService.store_stream()`；`link_canonical()` 在单一短事务 CAS `stored→linked` 并插入关系；新表有四类真实父级外键、artifact 主键和 `num_nonnulls(...)=1`。通用 `mark_linked()` 禁止旁路；绑定失败的 stored Canonical 进入既有 orphan cleanup。 |
| R5 | AC5：Migration 可升降级，不改公共 Contract/依赖/旧数据语义 | https://github.com/dingyuwen777/AIMA_UGC/issues/439#AC5 | satisfied | Migration `20260911_0048` 只新增/删除独立关系表与父级索引；`alembic heads` 返回唯一 head；Contract 生成/兼容检查无 diff，`uv lock --check` 通过，Manifest/lock 未修改。真实 upgrade/check/downgrade/upgrade 由 PR PostgreSQL 18 门禁执行。 |
| R6 | AC6：完成目标、持久化、main-safe、打包与仓库质量验证 | https://github.com/dingyuwen777/AIMA_UGC/issues/439#AC6 | explicitly_deferred | 本地目标 15/15、Unit 931 passed/8 skipped（另 3 个 Windows 缺少 POSIX API 的既有失败）、Contract+API 171/171、Frontend 139/139、Browser Mock 106/106、Ruff/Mypy/Wheel/Docs/Owner/Secret 均已验证；本机无 PostgreSQL/Docker，真实 Persistence/Migration 与 exact-head 全量证据按门禁只能由 Ready 后 PR CI 提供。 |
| R7 | AC7：完成追溯、审计、Review、CI、merge、main fresh、归档、Roadmap 与 Issue Closure | https://github.com/dingyuwen777/AIMA_UGC/issues/439#AC7 | explicitly_deferred | Requirement Traceability、Completion Audit、Deep Review 和 Roadmap 目标状态已完成；PR exact-head CI、expected-head merge、main fresh、原生归档、Issue Closure 与分支清理只能在 Ready 后按顺序执行，不在当前记录预先冒充。 |
| R8 | Stage 2–4 不实现，不新增列明的非目标，不为不存在的旧数据建兼容路 | https://github.com/dingyuwen777/AIMA_UGC/issues/439#AC5 | satisfied | `origin/main...a4b45287` 反向搜索确认现有 Excel/TikHub/Voice Plaza 无新 Writer/Reader 调用；无新 Job/API/UI/依赖，未出现 Monitoring Membership、Filter History、Platform Registry、第二数据库、消息系统或旧数据兼容路。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Writer/Reader 往返、Unicode、大文本、空字段、可复现、gzip/JSON/Contract 错误、有界生成器 |
| 接口 / 契约 | required | `CanonicalContentV1` 生成 Contract 不变；新文件 Contract 的 kind/content-type/encoding/suffix/line 语义 |
| 集成 / 持久化 / 运行时依赖 | required | Local ArtifactStore 真实文件 I/O；PostgreSQL 18 关系、状态、约束、外键、Migration |
| 用户 / 工作流验收 | required | 以后续 Runtime 调用者视角执行 Writer → ArtifactStore → Reader 语义往返；无 UI 新路径 |
| 跨组件 Golden Path | not_applicable | Stage 1 不接入 Excel/TikHub 或新 Job/API；真实文件 + PostgreSQL 边界由集成层直接证明 |
| 外部依赖 / Provider Probe | not_applicable | 无 Provider 调用、无外部当前事实需确认，不消耗 TikHub 费用 |
| 构建 / 打包 / 运行 | required | Ruff/mypy/Wheel；Migration upgrade/current/check/downgrade/upgrade；包导入 |
| 文档 / 治理 / 其他 | required | targeted Blueprint/Roadmap、表 Owner/架构/Secret/Change Ready、独立 Review、PR/main CI |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理方式 |
| --- | --- | --- |
| 主要风险 | 损坏/篡改 Artifact 被部分吐出；gzip 时间戳造成不可复现；lineage 父级或状态漂移；大 Dataset 聚合内存 | 读前压缩字节完整性预校验；`mtime=0`；恰一强外键 + CAS 短事务；磁盘临时流 + 逐行迭代 |
| 公共 Contract | 不变 | 不修改 `CanonicalContentV1`/HTTP/OpenAPI/JSON Schema；文件 Contract 是新增内部能力 |
| 数据 / Migration | 新增独立关系表，无旧数据 backfill | upgrade 创建，downgrade 删除；现有表和数据不改 |
| 依赖 / Runtime | 不变 | 只使用 Python/Pydantic/SQLAlchemy/Alembic 和当前 Store |
| 部署 | 需正常 Alembic 升级后随应用发布 | Stage 1 无 Runtime 调用新表；建表成功后对现有进程行为无影响 |
| 回滚 | 可先回滚应用代码再 downgrade | Stage 1 尚无生产 writer；删除新表不触碰旧表，未来 Stage 接入后需按当时数据保留要求另行评估 |

# 文档影响

Docs Impact 为 `targeted`：Blueprint 02 解释 Raw/Source、Canonical Artifact、Filter 的新建但未接线关系；Blueprint 03 记录新表、生命周期和完整性边界；Roadmap 05 只在最终交付后更新 Stage 1/2/3/4 依赖状态。不改 Product/UI/API 文档，因为没有用户可见或 HTTP 行为变化。

# 执行清单

- [x] 读取项目规则、Roadmap/Blueprint、canonical Source Mode 治理与当前机器事实
- [x] 复核 `origin/main`、工作区、Issue #439 与本地任务分支
- [x] 建立 Requirement Traceability、验证矩阵、方案比较与回滚边界
- [x] 写入并验证 Red 失败测试
- [x] 完成最小 Green/Refactor 实现和目标回归
- [x] 完成本地 Schema/main-safe/打包/文档分层验证；PostgreSQL/Migration 真实执行交给 PR CI
- [x] 重读上游、完成 Completion Audit 和独立 Review，清零阻塞 Finding
- [ ] 在 exact-head CI 后 guarded merge，验证 main/归档，收口 Roadmap/Issue/分支

# 完成审计

- [x] upstream_re_read：2026-09-11 Ready 前重新读取 Issue #439 当前正文、Roadmap 05 Stage 1/直接验证/Main-safe/非目标、Blueprint 02/03、当前 Canonical Contract、ArtifactService/Store、Schema/Migration、CI 与 `origin/main@e2df5e5b`；Issue 仍 open，PR #440 仍明确未就绪。
- [x] change_coverage：从 AC1–AC7、Roadmap 必须完成 1–9、直接验证与 Main-safe 逐条反查；R1–R5/R8 已有实现或直接证据，R6/R7 仅保留必须发生在 Ready 后的真实 PostgreSQL/CI/交付生命周期。
- [x] reverse_audit：沿 Writer → 磁盘临时流 → ArtifactService/Store → PostgreSQL lineage/linked → Reader 反查；又从 orphan cleanup、通用 `mark_linked()`、四类父级、重复绑定和现有 Excel/TikHub/Voice Plaza consumer 反向检查。Review 发现并修复“父级绑定失败后的 stored Canonical 永不回收”缺口。
- [x] unresolved_cleared：全部 `not_satisfied` 已清零；无已知 blocker/high/medium Finding。R6/R7 的真实 PostgreSQL/CI/merge/main/archive/Closure 有明确外部 Owner 与强制时序，不冒充当前完成。

# 两阶段 Review

- **需求与风险重建**：Deep Review Target 为 `e2df5e5b...a4b45287`。A1 从 Issue #439、Roadmap 05、Canonical/Artifact/Schema 当前事实独立重建；A2 对 Writer/Reader、生命周期、lineage、Migration、测试、文档和既有 Runtime 逐项对照，不使用本 Change 作需求全集。
- **实现与证据对照**：发现一项 MEDIUM 资源生命周期 Finding：父级绑定失败后，`stored` Canonical 不在既有 orphan cleanup allowlist，会无限保留。已把 kind 纳入原有 orphan 窗口并新增 PostgreSQL 回归；re-review 后原触发路径消失。未发现剩余 blocker/high/medium Finding。
- **测试充分性结论**：Unit/Contract/Package/Main-safe Browser Mock 能直接证明文件 Contract、内存和既有 UI/API 不变；Fake/静态 Schema 不冒充 PostgreSQL。四父级、事务回滚、恰一约束、重复绑定、旁路拒绝、orphan cleanup 和 Migration 升降级仍由 exact-head PostgreSQL 18 CI 证明，证据边界已明确。

# 完成证据与状态

实现候选 `a4b45287894eb0431d2c22b67ecf0d9030d1293b` 已完成本地验证与 Deep Review，Change 进入 `ready_for_review`。本机无可用 PostgreSQL 18/Docker；PR exact-head CI、guarded merge、main fresh、原生归档与 Issue Closure 仍未执行，禁止提前宣称完成。
