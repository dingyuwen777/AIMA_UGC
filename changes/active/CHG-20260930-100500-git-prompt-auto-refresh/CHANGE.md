---
schema: coding-change/v1
id: CHG-20260930-100500-git-prompt-auto-refresh
title: Git Prompt 标签变更自动刷新运行 Scheme
level: L2
status: in_progress
owner: assistant
branch: fix/676-git-prompt-auto-refresh
created: 2026-09-30 10:05:00 +08:00
updated: 2026-09-30
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - persistence
  - testing
  - documentation
affected_paths:
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py
  - backend/src/aima_ugc/bootstrap/analysis_identity.py
  - tests/integration/content/test_analysis_scheme_bootstrap.py
  - backend/src/aima_ugc/modules/analysis/README.md
  - docs/appendix/07_AI舆情打标与分析实现.md
contracts:
  - content-labeling.v3.0 Git Prompt activation lifecycle
data_changes: []
---

# 变更摘要

- **要解决的问题**：PR #677 已支持直接修改 Git Markdown 标签并自动解析/归一化 Taxonomy，但已有 Analysis Run 后，旧“仅首次打标前刷新”门禁会阻止 Git 变更进入 active Scheme。
- **拟议修改**：仅对纯 Git-managed 默认 Scheme 放宽刷新条件。Git Prompt 变化时在下一次分析预览/创建 Run 追加并激活新 Version；旧 Version 与历史 Run 保持不变。存在人工 Scheme 或人工 Version 时不自动覆盖。
- **预期结果**：用户以后直接修改 Git `content_labeling.md` 一级/二级标签，后续新打标能自动使用新标签，同时人工 Scheme 与历史审计不受破坏。

# 背景、现状与问题

## 背景

Requirement Source 为重新打开的 #676 / AC7。AC1—AC6 已由 PR #677 完成交付，本 Change 只修补合并后发现的生命周期遗漏。

## 当前现状

- `PromptTaxonomyLoader` 已把第 9 节人类可读标签区作为 Git 标签编辑源。
- 分析预览/创建 Run 已显式调用 `active_analysis_configuration(..., refresh_unused_git_bootstrap=True)`。
- `PostgresAnalysisSchemeRepository._refresh_unused_git_bootstrap()` 仍要求 `active.version == 1`、全库仅一个 Version 且没有 Analysis Run，因此正式使用过后不会应用新的 Git Prompt。

## 问题、根因或约束

解析链已动态，但 active Scheme 生命周期仍按“首次打标前一次性刷新”设计，两者不一致。必须让 Git-managed lineage 可滚动刷新，同时不能让 Git 覆盖管理员人工 Scheme。

## 不修改的后果

用户直接改 Git 标签后，代码层能识别新标签，但已有生产 Run 的环境仍继续使用旧 active Version，后续打标不会真正应用新标签。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Git Markdown 标签已由 Loader 自动解析 | `prompt_taxonomy.py` on main | 不需要再改标签解析机制 |
| E2 | 分析预览/创建 Run 已显式请求刷新 Git bootstrap | `bootstrap/content_http.py` | 刷新入口已存在，不增加热路径轮询 |
| E3 | 当前 Repository 刷新函数拒绝已有 Run / 多 Version | `analysis_schemes.py::_refresh_unused_git_bootstrap` | 根因在生命周期门禁 |
| E4 | Analysis Run 持久保存 `analysis_scheme_version_id` / Prompt/Taxonomy Hash | `modules/analysis/tables.py` | 追加新 Version 不破坏历史 Run 审计 |

## 推断与待确认

无阻塞待确认项。

# 目标、成功标准与非目标

## 目标

纯 Git-managed 默认 Scheme 在 Git Prompt 变化时可自动滚动到新 active Version，并保持历史 Run 与人工配置隔离。

## 成功标准

- [ ] #676 AC7 有实现与 PostgreSQL 集成证据。
- [ ] 已有历史 Analysis Run 不阻塞 Git-managed Scheme 刷新。
- [ ] 新 Version 递增、旧 active 退役、历史 Run 仍引用旧 Version。
- [ ] 存在人工 Version 或其他未删除 Scheme 时，Git 自动刷新不发生。
- [ ] current-head CI / Review / main-fresh / Change archive / Requirement Closure 完成。

## 范围

- Analysis Scheme Git bootstrap 刷新生命周期。
- 必要 PostgreSQL 集成回归与长期文档事实。

## 非目标

- 不改 Prompt 业务规则、Taxonomy 解析算法、HTTP Contract、Schema/Migration、前端。
- 不自动覆盖人工 Scheme 或人工 Version。
- 不部署生产、不修改生产数据。

## 必须保持不变

- 数据库 active Analysis Scheme 仍是运行时唯一事实源。
- 历史 Analysis Run 固定引用创建时 Scheme Version，不回写历史。
- 管理员显式发布/回滚优先于 Git 自动刷新。
- Git 自动刷新只在分析预览/创建 Run 的现有显式刷新入口执行，不增加普通页面热路径写入。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 接口与契约 | 不变 | E1-E4 | 无 HTTP/Schema 变化 |
| Git-managed 判定 | 当前非删除 Scheme 仅一个，且默认 Scheme 全部 Version 的 created_by 均为系统 Git actor | 防止覆盖人工配置 | 有人工 Version 即停止自动刷新 |
| 历史数据 | 追加 Version，不改旧 Run | E4 | 审计/回滚安全 |
| 触发时机 | 复用 analysis preview/create Run 显式刷新 | E2 | 避免每次页面读取写 DB |

# 修改方案与决策依据

## 最小充分方案

1. 将一次性 `_refresh_unused_git_bootstrap` 收敛为纯 Git-managed lineage 刷新。
2. Hash/compiled Prompt 未变化时保持无写入。
3. 仅当 active 为 published、当前只存在一个未删除 Scheme、该 Scheme 所有 Version 均由 `system/system:git-bootstrap` 创建时允许刷新。
4. 新 Version 使用 `max(version)+1`，旧 active 退役，新 Version published/active；历史 Run 不修改。
5. PostgreSQL 集成测试覆盖“已有历史 Run 仍刷新”和“人工 Version 阻止刷新”。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E2 | 复用现有显式刷新入口，不增加运行时轮询 |
| D2 | E4 | 追加 Version 保留历史 Run 审计 |
| D3 | E3 | 移除 run_count/version_count==1 限制，改为 Git-managed lineage 判定 |
| D4 | 用户要求 | 直接 Git 修改必须能用于后续打标 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 直接 Git 修改标签后续打标自动应用 | #676 / AC7 | not_satisfied | 待实现/集成测试 |
| R2 | 历史 Run 保留旧 Version | #676 / AC7 | not_satisfied | 待集成测试 |
| R3 | 人工 Scheme/Version 不被 Git 覆盖 | #676 / AC7 | not_satisfied | 待集成测试 |
| R4 | 交付门禁完整 | #676 / AC7 | not_satisfied | 待 CI/Review/main-fresh |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `analysis_schemes.py` | 放宽为 Git-managed lineage 自动滚动刷新 | 根因修复 | R1-R3 |
| `test_analysis_scheme_bootstrap.py` | 增加已有 Run / 人工 Version PostgreSQL 回归 | 直接证明生命周期 | R1-R3 |
| `analysis_identity.py`、README/Appendix | 更新“首次打标前”文字为 Git-managed 显式刷新事实 | 防止文档与代码漂移 | R1-R3 |

- [x] 调查当前实现和事实源
- [x] 建立任务路由与验证矩阵
- [ ] 建立失败回归
- [ ] 实现最小修复
- [ ] targeted/PostgreSQL 验证
- [ ] Completion/Review/CI/merge 收尾

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Git-managed 判定与不变 Hash 行为 |
| 接口 / 契约 | not_applicable | 无公共 Contract 变化 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL Version/Run/active 指针 |
| 用户 / 工作流验收 | required | Git Prompt 变化后下一次分析预览/Run 使用新 active Version |
| 跨组件关键路径 | required | Git Prompt → bootstrap refresh → active Version → 后续 Run |
| 外部依赖 / 供应方探测 | not_applicable | 不调用真实 LLM |
| 构建 / 打包 / 运行 | not_applicable | 无构建/依赖变化；常规 CI 仍执行 |
| 文档 / 治理 / 其他 | required | Change Ready、Review、CI、main-fresh、Issue Closure |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | Git 自动刷新误覆盖人工配置 | 全 Version actor + 单一未删除 Scheme 双门禁 |
| 兼容性 | 保持 | 仅新增 Version，不改旧 Contract/Run |
| 数据 / Migration | 无 | 使用现有表与 Version 状态 |
| 部署 / 运行 | 无额外步骤 | 新镜像在下一次分析预览/创建 Run 时检查 |
| 回滚 / 恢复 | 可回滚代码；已生成 Version 保留审计 | 管理员可回滚历史 Version |

# 文档、依赖、部署与发布影响

- 长期文档：更新 Git Prompt 自动应用边界。
- 依赖/Runtime/配置/Secret：不变。
- Release/Deploy：不执行。

# 完成审计

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 待填写 | PostgreSQL targeted integration | 待执行 | AC7 |

## 未验证内容与剩余风险

当前尚未实现。

## 交付状态

- 提交：待建立。
- PR：待创建。
- CI：待执行。
- 合并：待执行。
- Change archive：待 merge 后自动化。
- Release/Deploy：不适用。
