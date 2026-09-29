---
schema: coding-change/v1
id: CHG-20260929-194448-analysis-scheme-cleanup
title: 优化 AI 分析规则归档与删除体验
level: L3
status: ready_for_review
owner: assistant
branch: feature/669-analysis-scheme-cleanup
created: 2026-09-29 19:44:48 +08:00
updated: 2026-09-29 19:44:48 +08:00
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - administration
  - frontend
  - persistence
affected_paths:
  - backend/src/aima_ugc/modules/analysis
  - backend/src/aima_ugc/adapters/persistence/postgres
  - backend/src/aima_ugc/bootstrap
  - frontend/src/features/admin-configuration
  - migrations/versions
  - tests
contracts:
  - analysis scheme lifecycle API behavior
data_changes:
  - analysis_schemes lifecycle tombstone
---

# 变更摘要

- **要解决的问题**：管理员创建和归档的 AI 分析规则会持续堆积；当前已发布/已使用规则只能归档，不能从管理视图删除。
- **拟议修改**：归档后统一允许删除。纯草稿继续物理删除；已发布/已使用规则改为管理视图 tombstone，历史 Version/Prompt/Hash 与 Analysis Run 引用保持不变。
- **预期结果**：管理员可以清理不再使用的规则，页面保持简洁，同时历史分析仍可复现。

# 背景、现状与问题

## 背景

Requirement Source 为 GitHub Issue #669。该需求涉及管理员可见生命周期、不可逆删除语义和 PostgreSQL Schema，因此按 L3 处理。

## 当前现状

- `PostgresAnalysisSchemeLifecycleRepository.delete_blockers()` 阻止删除任何已有发布历史或 Analysis Run 引用的 Scheme。
- 前端已归档规则默认折叠，但长期积累的历史规则只能一直留在该列表。
- `analysis_content_runs.analysis_scheme_version_id` 外键指向 `analysis_scheme_versions.id`，历史 Run 需要 Version/Prompt/Hash 保持可读。
- `analysis_schemes.name` 当前全局唯一，若历史保留删除只加 tombstone 而不调整唯一性，同名规则不能重新创建。

## 问题、根因或约束

真正约束不是“数据库不能删除”，而是“历史 Run 的不可变 Scheme Version 不能被物理破坏”。因此需要把管理员的“删除资源”与历史证据的“保留快照”分层。

## 不修改的后果

归档列表会继续随规则历史增长；管理员不能真正清理管理视图，页面可用性逐步下降。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 已发布 Scheme 当前只能归档、不能硬删 | `analysis_scheme_lifecycle.py` | 删除需要新增历史保留语义 |
| E2 | Analysis Run 外键引用 Scheme Version | Migration 0033 / `analysis_content_runs` | 被引用 Version 不可物理删除 |
| E3 | Scheme 名称当前全局唯一 | Migration 0033 / `scheme_tables.py` | tombstone 后应释放 live 名称 |
| E4 | 管理员归档列表已有恢复/删除入口 | `AnalysisSchemePanel.vue` | 可复用现有交互，不新增页面 |

## 推断与待确认

无阻塞待确认项。历史保留删除采用软删除/tombstone 是满足 #669 AC4 的最小充分方案。

# 目标、成功标准与非目标

## 目标

管理员可以通过“归档 → 删除”清理所有不再使用的 Analysis Scheme，而历史 Analysis Run 的不可变 Prompt/Taxonomy 快照保持可复现。

## 成功标准

- [ ] #669 AC1—AC7 均有直接实现与当前 revision 证据。

## 范围

- Analysis Scheme lifecycle Schema/Migration。
- PostgreSQL lifecycle repository 与 HTTP service。
- 管理员配置 AI 分析规则归档显示和删除交互。
- 相关 PostgreSQL / API / 前端自动化测试和当前事实文档。

## 非目标

- 不删除 Analysis Run/Result。
- 不改变 Prompt 内容、Taxonomy、Provider 或 Run 冻结语义。
- 不升级依赖/Runtime。

## 必须保持不变

- 当前 active Scheme 不可删除。
- PostgreSQL 仍是运行时唯一 Scheme 事实源。
- 历史 Run 的 `analysis_scheme_version_id` 必须继续可解析。
- 发布/回滚/权限/审计语义保持兼容。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Analysis Owner + Admin UI | E1/E4 / #669 | 不扩展到其他资源生命周期 |
| 接口与契约 | 保持现有 DELETE 204 与 eligibility 结构 | #669 / 兼容性 | 不新增 public API |
| 数据与迁移 | 新增 Scheme 删除 tombstone，并将名称唯一性限定为未删除资源 | E2/E3 | 需要 Alembic Migration |
| 错误与失败语义 | active/未归档仍拒绝；已归档统一可删除 | #669 AC2/AC5 | 前后端提示同步 |
| 兼容性 | 历史 Version/Run 引用不变 | #669 AC4 | 不级联删除历史 |
| 部署与回滚 | 常规 Alembic upgrade；downgrade 恢复旧唯一约束前需先避免同名 tombstone/live 冲突 | Schema 事实 | 回滚风险需在 Migration 中 fail closed |

# 修改方案与决策依据

## 最小充分方案

1. 为 `analysis_schemes` 增加 `deleted_at`；live/archived 查询排除 tombstone。
2. 将名称唯一性从全表唯一改为 `deleted_at IS NULL` 的 PostgreSQL partial unique index，使删除后名称可复用。
3. 删除已归档 Scheme 时：无发布/Run 历史则物理删除；否则写 `deleted_at` tombstone 并保留 Version。
4. 删除后的 Scheme 不允许恢复、复制、发布或再次出现在管理列表；历史 Version 仍可按 ID 加载。
5. 前端归档区显示计数与更紧凑说明，删除按钮不再先因历史 blocker 阻止；确认文案明确历史规则会从管理视图移除但保留分析证据。
6. 增加 PostgreSQL lifecycle 回归、HTTP/前端交互覆盖，并同步 AI 分析实现文档。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：历史规则 tombstone | E1/E2 | 既能满足管理员删除，又不破坏 Run 引用 |
| D2：live partial unique name | E3 | 删除后允许重建同名规则 |
| D3：复用现有 DELETE API | E4 | 减少 public Contract 变化和前端复杂度 |

## 备选方案与取舍

- **直接级联物理删除 Version/Run**：拒绝，会破坏 #669 AC4 和既有审计/复现语义。
- **继续只允许归档**：拒绝，不能解决页面持续堆积的真实问题。
- **另建独立历史快照表再物理删除 Scheme/Version**：当前无必要，增加 Migration/复制/一致性机制；现有 Version 表本身已经是不可变快照 Owner。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 归档显示保持低干扰 | #669 / AC1 | satisfied | `AnalysisSchemePanel.vue` 按 Scheme 折叠版本并默认折叠归档；`admin-configuration-release2.spec.ts` 覆盖分组/折叠 |
| R2 | 所有非 active 已归档 Scheme 可删除并从管理视图消失 | #669 / AC2 | satisfied | `analysis_scheme_lifecycle.py` 统一允许归档非 active 删除；Browser Mock 覆盖删除后归档列表消失 |
| R3 | 纯草稿删除仍物理清理 | #669 / AC3 | satisfied | `test_unused_analysis_scheme_archive_delete_physically_removes_draft` 直接断言 Scheme/Version 均被物理删除 |
| R4 | 已发布/已使用删除保留历史 Version/Run 复现链 | #669 / AC4 | satisfied | `test_published_analysis_scheme_delete_hides_resource_but_preserves_run_snapshot` 建立真实 Run FK 并断言删除后 Version/Run 引用保持 |
| R5 | active Scheme 继续禁止删除 | #669 / AC5 | satisfied | lifecycle `archive_blockers/delete_blockers` 保留 active 守卫；删除仍要求先归档 |
| R6 | 权限、审计、前端提示与真实语义一致 | #669 / AC6 | satisfied | lifecycle HTTP 继续 `require_administrator()`，删除审计新增 `deletion_mode`；前端确认/成功文案同步历史保留语义 |
| R7 | Migration/后端/前端/生成 Contract/验证一致 | #669 / AC7 | satisfied | Migration 0075 + ORM lifecycle schema + repository/UI/tests/docs 同步；public lifecycle route/response 未新增字段 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| analysis lifecycle schema/repository | 增加 tombstone 生命周期 | 保留历史同时清理管理视图 | R2-R5 |
| Alembic migration | deleted_at + partial unique name | Schema 与名称复用 | R2/R7 |
| administration HTTP | 删除模式审计 | 可追溯删除 | R6 |
| AnalysisSchemePanel.vue | 归档信息密度和删除交互 | 页面整洁 | R1/R2/R6 |
| tests | PostgreSQL/UI/Contract 回归 | 直接证明 AC | R1-R7 |
| docs appendix | 更新删除生命周期事实 | 文档与实现一致 | R2-R4 |

执行过程中保持最小闭环：

- [x] 调查当前实现和事实源；新建项目则确认现有资料、目标和硬约束
- [x] 建立与风险相称的任务路由和验证矩阵
- [ ] 行为变化建立失败证据或说明测试例外
- [ ] 完成最小实现，不静默扩大范围
- [ ] 同步受影响的长期文档或明确不适用依据
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | lifecycle 分支、前端归档展示与删除提示 |
| 接口 / 契约 | required | 现有生命周期 OpenAPI operation 保持兼容，generated client 无漂移 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL Migration、partial unique、Run→Version 历史引用 |
| 用户 / 工作流验收 | required | 管理员归档→删除→列表消失的 Browser Mock 工作流 |
| 跨组件关键路径 | not_applicable | 不新增跨进程协议；API/Persistence 与 UI 分层证据足以覆盖本次行为 |
| 外部依赖 / 供应方探测 | not_applicable | 不涉及外部 Provider 当前事实 |
| 构建 / 打包 / 运行 | required | 后端静态/测试入口与前端 build |
| 文档 / 治理 / 其他 | required | Change Ready、文档同步、PR/current-head CI |

## 验证计划

- 目标测试：`tests/integration/database/test_product_resource_lifecycle.py`。
- 相关回归：Analysis Scheme bootstrap/compile、admin configuration Browser Mock。
- 静态检查或构建：仓库正式 Python/Frontend quality/build 命令。
- 专项真实边界：PostgreSQL integration。
- 就绪检查：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 历史版本误删或 tombstone 仍被管理入口读取 | fail closed 查询过滤 + PostgreSQL 回归 |
| 兼容性 | public lifecycle route/response 保持 | 复用现有 API |
| 数据 / Migration | 新增 nullable deleted_at；旧数据默认 live | 向前兼容，无回填 |
| 部署 / 运行 | 常规 Migration 后滚动重启 | 不新增配置 |
| 回滚 / 恢复 | 代码可回退；Schema downgrade 在存在同名 live/tombstone 时需拒绝或先人工消歧 | 防止恢复全局 unique 时数据冲突 |

# 文档、依赖、部署与发布影响

- **长期文档**：同步 `docs/appendix/07_AI舆情打标与分析实现.md` 的 Scheme 生命周期说明；Blueprint 决策 P 不改变。
- **依赖 / Runtime**：不新增、不升级。
- **配置 / Secret**：不变。
- **部署 / Release**：需要执行新增 Alembic Migration；无额外环境变量。
- **兼容 / 消费方通知**：前端复用既有 lifecycle API，无外部消费方迁移。

# 完成审计

- [x] upstream_re_read：重新读取 #669、Blueprint 决策 P、AI 分析实现文档、当前 lifecycle/repository/UI/Run Schema，从上游重新建立 AC1—AC7 完成定义。
- [x] change_coverage：R1—R7 已逐项映射到实现与回归资产；没有用当前 Change 自身替代 Requirement Source。
- [x] reverse_audit：执行“后端删除能力 → 前端归档删除入口”“前端删除 → 后端 active/归档守卫”“历史 Run → Version/Prompt/Hash”“删除 → 同名重建”反向审计，主要投影均有实现与测试。
- [x] unresolved_cleared：R1—R7 均已进入 satisfied；没有延期、不适用或未解决 Requirement。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | PR #670 current branch | 静态实现/Contract/Schema 复核 | 已完成，等待 CI 执行动态证据 | 删除语义、历史快照、名称复用、UI Journey 已形成直接回归资产 |

## 未验证内容与剩余风险

- PR current-head CI / PostgreSQL Integration / Frontend Browser Acceptance 尚未由 Runner 执行；本 Change 进入 Ready 以触发这些 required evidence，失败则按同一 Repair Batch 修复后重新验证。

## 交付状态

- 提交：实现与回归资产已推送到任务分支。
- 拉取请求：PR #670 已建立并绑定 #669。
- CI：准备通过 ready_for_review 事件执行 current-head required evidence。
- 合并：待执行。
- Change 归档：待合并后由仓库自动化处理。
- 发布 / 部署：不执行生产部署；本任务只交付代码到 main。

## 备注

无。
