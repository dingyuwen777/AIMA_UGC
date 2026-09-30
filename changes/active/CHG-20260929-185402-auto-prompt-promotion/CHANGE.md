---
schema: coding-change/v1
id: CHG-20260929-185402-auto-prompt-promotion
title: 部署时自动发布镜像内置 Git Prompt
level: L3
status: ready_for_review
owner: assistant
branch: tech/667-auto-prompt-promotion
created: 2026-09-29 18:54:02 +08:00
updated: 2026-09-30
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - persistence
  - runtime-configuration
  - docker-release
  - testing
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/analysis/prompts/content_labeling.md
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py
  - backend/src/aima_ugc/bootstrap
  - backend/src/aima_ugc/entrypoints/internal_v1_configure_main.py
  - scripts/release/release_bundle.py
  - compose.yaml
  - tests/unit/analysis
  - tests/integration/content
  - tests/unit/platform/test_internal_v1_deployment.py
  - tests/unit/test_release_bundle.py
  - AGENTS.md
  - backend/src/aima_ugc/modules/analysis/README.md
  - docs/appendix/07_AI舆情打标与分析实现.md
  - docs/blueprint/07_技术决策与实施门禁.md
  - docs/operations/01_生产部署与离线Release方案.md
  - docs/guides/06_本地Release离线包构建.md
contracts:
  - content-labeling.v3.0 Prompt identity
  - Analysis Scheme deployment promotion semantics
  - Internal V1 configure exit and output contract
  - Offline release manifest analysis prompt identity
data_changes:
  - existing Analysis Scheme tables append a new version and move the active pointer without schema migration
---

# 变更摘要

- **要解决的问题**：PR #677 已让 Git `content_labeling.md` 的 Markdown 标签变化自动解析为新 Taxonomy，但数据库 active Scheme 是独立持久事实；已有历史 Run 后，部署新镜像仍可能继续使用旧 active Prompt。
- **拟议修改**：新增只由部署期 `configure` 调用的 Git Prompt promotion；系统 Git-managed active 按 Hash 幂等追加/发布，人工 lineage 冲突时失败关闭；Release 验证并记录 backend 镜像实际 Prompt 身份。
- **预期结果**：直接修改 Git Prompt 后，构建/部署新镜像即可自动应用到后续新 Analysis Run；旧 Run 和人工配置不被静默改写。

# 背景、现状与问题

## 背景

Requirement Source 为 #667。#676 / PR #677 已完成唯一 `content_labeling.md`、`content-labeling.v3.0`、Markdown 标签编辑源和 Taxonomy 自动归一化。本 Change 只补齐“部署时把镜像 Git Prompt 提升为数据库 active Scheme”的最后一段链路。

## 当前现状

- Git 内容打标 Prompt 唯一文件为 `backend/src/aima_ugc/modules/analysis/prompts/content_labeling.md`。
- 数据库唯一 active Analysis Scheme Version 是正式运行事实源，Run 创建时冻结 Version、Prompt/Taxonomy Hash 和 Prompt Snapshot。
- `bootstrap_default()` 负责空库/安全 bootstrap，不应在普通运行时读取路径无条件发布新 Version。
- Compose 已有 `migrate → configure → API/Worker/Scheduler` 启动门禁。
- Release manifest 尚未记录实际 backend 镜像内 Prompt 的协议和 Hash。

## 问题、根因或约束

根因是 Git Prompt 与数据库 active Scheme 之间缺少**部署期发布事务**。不能通过放宽普通 bootstrap 来解决，否则 API/Worker 的常规初始化可能产生业务配置副作用；必须把 promotion 限定在 `configure`。

## 不修改的后果

用户直接修改 Git Markdown 标签或 Prompt 规则，即使代码能正确解析，已存在历史 Run 的服务器仍可能继续让新 Run 使用旧 active Scheme，需要人工发布，容易漏做。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Git Markdown 标签变化已经由 Loader 自动归一化 Taxonomy | #676 / PR #677 / current main | promotion 只需消费当前 Git Prompt，不再维护第二标签事实 |
| E2 | Run 冻结 Scheme Version/Prompt Hash，后续 active 切换不会改写历史 Run | Analysis Run/Schema 现有实现 | 可安全追加新 Version |
| E3 | `bootstrap_default()` 是初始化语义 | `analysis_schemes.py` | 持续部署 promotion 应独立 |
| E4 | Compose 已有 configure 启动门禁 | `compose.yaml` / internal configure entrypoint | promotion 应在业务进程前执行 |
| E5 | Release builder 已有 manifest/checksum/镜像构建验证 | `scripts/release/release_bundle.py` | Prompt identity 应绑定实际 backend 镜像 |
| E6 | 用户明确要求 Git Markdown 修改自动识别并应用，且完成后合并 main | 当前会话 | AC1-AC8 |

## 推断与待确认

无业务决策待确认。生产服务器当前 active lineage 属于部署时动态事实，本任务不读取或修改生产环境。

# 目标、成功标准与非目标

## 目标

建立：

```text
Git content_labeling.md
→ backend 镜像实际 Prompt identity
→ configure deployment promotion
→ PostgreSQL active Scheme Version
→ 后续新 Analysis Run
```

并保证人工配置与历史 Run 安全。

## 成功标准

- [x] #667 AC1—AC8 均有实现/验证载体；current-head CI、独立 Review、merge 与 main-fresh 继续作为平台交付门禁。

## 范围

- Analysis Scheme persistence Owner 的 deployment promotion。
- configure 编排/输出/审计。
- Release backend Prompt identity 校验与 manifest。
- PostgreSQL/Unit/Release/Compose 回归。
- 受影响长期文档和交付门禁。

## 非目标

- 不改变 Prompt 业务规则、默认标签、JSON 输出 Contract。
- 不改写历史 Run，不自动重打历史数据。
- 不覆盖人工 active。
- 不新增 Schema/Migration/依赖。
- 不执行生产部署、生产数据操作或正式 Release 发布。

## 必须保持不变

- 数据库 active Scheme 是运行时唯一事实源。
- 历史 Run 冻结身份可复现。
- 管理员发布/回滚能力。
- HTTP/OpenAPI/generated client。
- 普通 bootstrap 不承担持续发布。
- Branch Protection/CI/Review/Release/Deploy 门禁。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | persistence Owner 写 Scheme；configure 编排；Release 只验证产物 | E3-E5 | 不建立平行写路径 |
| 接口与契约 | HTTP 不变；configure/manifest 加性内部身份 | #667 | 无客户端 Migration |
| 数据与迁移 | 只追加 Version、切 active、写 audit | E2 | 无 Schema Migration |
| 错误与失败语义 | 人工 active 冲突 / 镜像身份不一致时 fail closed | #667 AC3/AC6 | 业务进程不以不确定 Prompt 启动 |
| 兼容性 | 只自动提升 Git-managed lineage | E2/E6 | 尊重管理员规则 |
| 部署与回滚 | configure 自动 promotion；历史 Version 保留，可人工回滚 | E4 | 可审计、可恢复 |

# 修改方案与决策依据

## 最小充分方案

1. 在 Analysis Scheme repository 增加 deployment promotion 方法，复用 advisory transaction lock：
   - 无 active → 复用 bootstrap 建首版；
   - active 与 Git identity 一致 → no-op；
   - active lineage 全为系统 Git-managed → 追加并发布新 Version，即使已有 Run；
   - 任一人工 Version / 人工 Scheme 冲突 → 写前失败。
2. 通过 configure/application service 调用 promotion，输出 action/version/protocol/prompt/taxonomy hash，并写不含正文的审计事件。
3. Release 从实际 backend 镜像/安装包读取唯一 Prompt identity，与源码计算结果比较，写入 manifest；不一致则失败。
4. 保持 `bootstrap_default()` 原有初始化语义，不把 deployment promotion 扩散到普通运行时读取。
5. 用真实 PostgreSQL 覆盖历史 Run、幂等、人工冲突、并发；用 Release/Configure 单测覆盖产物和 fail-closed。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：promotion 与 bootstrap 分离 | E3 | 避免普通运行初始化产生发布副作用 |
| D2：只自动提升 Git-managed lineage | E2/E6 | 自动应用 Git 同时尊重人工配置 |
| D3：configure 执行 | E4 | 已是业务进程前 fail-closed 门禁 |
| D4：实际镜像 identity | E5 | 源码不能证明部署产物内容 |
| D5：历史 Run 保留 | E2 | Version append 天然保持可复现 |

## 备选方案与取舍

- 放宽 `bootstrap_default()` 在任何启动自动发布：拒绝，会扩大普通运行副作用。
- 无条件覆盖人工 active：拒绝，破坏管理员业务决定。
- 继续人工发布：拒绝，不满足“Git 修改自动应用”。
- 运行时直接绕过数据库读 Markdown：拒绝，破坏 Run 冻结和唯一 active 设计。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 系统 Git-managed active 不同时部署期原子追加并激活，历史 Run 不阻塞 | #667 / AC1 | satisfied | `promote_git_prompt()` + `test_deployment_promotion_applies_git_prompt_after_historical_run` |
| R2 | 相同身份重复 configure 幂等 | #667 / AC2 | satisfied | 同一 PostgreSQL 回归二次 promotion 返回 `unchanged`；并发回归只创建一个 v2 |
| R3 | 人工 lineage 冲突 fail closed 且不写 | #667 / AC3 | satisfied | 人工 Version 在 Hash 比较前拒绝；同内容/变内容两条回归保持人工 active |
| R4 | 旧 Run 旧 Version，新 Run 新 Version | #667 / AC4 | satisfied | promotion 集成回归证明旧 Run 仍绑 v1、active 已切 v2；既有 Analysis Run 创建回归负责冻结 current active |
| R5 | configure 输出身份并写安全审计 | #667 / AC5 | satisfied | `promote_git_analysis_scheme()` 审计 + configure 输出单测；审计断言不含 `prompt_text` |
| R6 | Release 校验实际 backend Prompt 并写 manifest | #667 / AC6 | satisfied | `_backend_prompt_identity()` 运行实际 backend 镜像并比较源码 SHA；manifest/verify 正反例回归 |
| R7 | bootstrap/管理员/Markdown 标签/历史语义兼容 | #667 / AC7 | satisfied | 保留 `bootstrap_default()` 初始化路径；PR #677 标签解析回归 + Scheme/Run 既有回归由 CI 复核 |
| R8 | Review/CI/build/main-fresh/归档/Closure 全部闭环 | #667 / AC8 | satisfied | #668 已接入 current-head required checks、Review、guarded merge、main-fresh、Archive/Closure 门禁；实际结果必须在合并前/后补入本 Change 与 Issue |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `analysis_schemes.py` + Analysis bootstrap/service | deployment promotion / identity result | R1-R5/R7 |
| `internal_v1_configure_main.py` | 接入 promotion 与 fail-closed 输出 | R1-R5 |
| `release_bundle.py` | 镜像 Prompt identity / manifest | R6 |
| Analysis/Configure/Release tests | PostgreSQL/Unit/产物回归 | R1-R7 |
| AGENTS + Analysis/Decision/Deploy/Release docs | 当前长期事实 | R5-R8 |

执行过程中保持最小闭环：

- [x] 重读 #667 与 current main，清理旧 V4.6/bootstrap pointer 事实
- [x] 建立当前 L3 验证矩阵
- [x] 建立 Red/失败证据
- [x] 完成最小实现
- [x] 同步长期文档
- [x] 已建立覆盖当前 Head 的自动化验证载体；平台 current-head CI 待 PR Ready 事件执行
- [x] Completion Audit 已完成；Review / CI / merge / main-fresh 作为交付阶段外部门禁待执行

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | promotion 判定、configure 输出、manifest identity |
| 接口 / 契约 | required | configure exit/output、manifest 加性字段、HTTP 无漂移 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 追加/切 active/人工冲突/历史 Run/并发 |
| 用户 / 工作流验收 | required | Git Prompt 改动部署后自动成为后续 Run active |
| 跨组件关键路径 | required | Git → image → configure → Scheme → new Run |
| 外部依赖 / 供应方探测 | not_applicable | 不依赖 LLM/TikHub 当前事实 |
| 构建 / 打包 / 运行 | required | wheel/backend image/release manifest/compose config |
| 文档 / 治理 / 其他 | required | #667、Change、Review、CI、main-fresh、Archive、Closure |

## 验证计划

- 目标：promotion repository/service、configure、release identity。
- 回归：Analysis Scheme bootstrap/publish/rollback、Run freeze、Prompt Loader/Compiler。
- 静态：Ruff/mypy、changed-scope quality。
- 持久化：真实 PostgreSQL。
- 构建：Wheel/Release builder/Compose config。
- 就绪：`python scripts/quality/check_change_completion.py --root . --changed-since <base>`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 人工误判、重复发布、并发、镜像/源码漂移 | lineage + advisory lock + hash +真实集成 |
| 兼容性 | public Contract 不变；部署行为增强 | #667 |
| 数据 / Migration | 无 Schema；追加 Version / active pointer / audit | 既有表和 Owner |
| 部署 / 运行 | configure 新硬门禁 | 明确 fail closed |
| 回滚 / 恢复 | 旧 Version 保留，管理员可回滚 | 版本化设计 |

# 文档、依赖、部署与发布影响

- **长期文档**：AGENTS、Analysis README/Appendix、技术决策、生产部署、本地 Release。
- **依赖 / Runtime**：不新增、不升级。
- **配置 / Secret**：不新增；日志/审计/manifest 不写 Prompt 正文或 Secret。
- **部署 / Release**：configure 自动 promotion；manifest 增加 Prompt identity；不执行真实发布/部署。
- **兼容 / 消费方通知**：manifest 加性字段保持兼容；HTTP 调用方无变化。

# 完成审计

- [x] upstream_re_read：已重读 live #667、current main、#676/#677、当前实现、测试与 CI Workflow。
- [x] change_coverage：AC1—AC7 已有实现与直接测试载体；AC8 的平台交付门禁已接入且不得在实际通过前合并。
- [x] reverse_audit：已核对 Git→backend image identity→configure→promotion→active→Run，以及 manual lineage→fail closed；普通 runtime bootstrap 未被扩大。
- [x] unresolved_cleared：R1—R8 已有实现/验证或平台门禁承载，不存在未处理业务决策。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | current main `25ffb2ae` | #667 + #676/#677 + repository fact recovery | 已完成 | 当前需求与事实基线已校准 |
| V2 | PR #668 implementation head（CI 前） | 代码/调用链反向审计 | promotion 与 bootstrap 分离；人工 lineage 在身份比较前 fail closed；Release 从实际镜像取 identity | 实现机制覆盖 AC1—AC7 |
| V3 | PR #668 implementation head（CI 前） | 新增 PostgreSQL / configure / Release 回归代码 | 已建立历史 Run、幂等、并发、人工冲突、安全审计、镜像漂移测试 | current-head CI 可直接执行高风险边界 |

## 未验证内容与剩余风险

- 生产实现与回归代码已完成，但本宿主未直接运行仓库 pytest/ruff；自动化执行证据由 PR #668 current-head CI 提供，当前尚未声称通过。
- 独立 Review、main-fresh、Change Archive 与 Issue Closure 尚未发生，合并前后必须按门禁补证据。
- 不验证生产服务器实际 active 状态；部署时由新逻辑判定。

## 交付状态

- 提交：实现、测试和长期文档已推送至 `tech/667-auto-prompt-promotion`；最终 revision 以 PR #668 current head 为准。
- 拉取请求：#668，准备进入 Ready。
- CI：待 `ready_for_review` 事件在最终 Head 执行。
- 合并：用户已授权；只在 required gates 通过后执行。
- Change 归档：merge 后仓库自动化。
- 发布 / 部署：不执行。

## 备注

#668 是 #667 的唯一现有 Draft PR；本次不创建重复 PR。
