---
schema: coding-change/v1
id: CHG-20260907-024401-change-template-sync
title: 同步固定第一性原理 Change 模板
level: L2
status: ready_for_review
owner: dingyuwen777
branch: chore/change-template-sync
created: 2026-09-07
updated: 2026-09-07
completion_gate: required
depends_on: []
affected_areas:
  - governance
  - documentation
  - managed-project-payload
affected_paths:
  - .agents/skills/coding/assets/CHANGE.template.md
contracts:
  - coding-change/v1
  - AIMA Change carrier compatibility
data_changes: []
---

# 背景与目标

AIMA_UGC 的正式 Change carrier 是顶层 `changes/`；通用 Change 模板由 Agent_Skills canonical Source 拥有，项目中的 `.agents/skills/coding/assets/CHANGE.template.md` 是安装/升级维护的受管投影，不是第二个 canonical Owner。当前任务要求两个仓库同步固定同一套 Change 文档骨架，因此 AIMA 只同步该受管模板，不复制一份项目自有通用治理模板，也不改变项目的 Change carrier、validator、CI 或归档机制。

目标是让 AIMA 后续新建 Change 直接获得与 Agent_Skills 当前 canonical 一致的第一性原理中文模板，同时保持 `coding-change/v1`、`changes/active` / `changes/archive`、`scripts/quality/check_change_completion.py` 和 repository-native Change Archive 现有行为不变。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | AIMA 受管 Change 模板包含第一性原理因果链，以及背景、现状事实、问题、方案、证据、验证、风险和完成证据等固定结构 | `#376 / AC1` | satisfied | AIMA 受管模板已同步固定 `变更摘要`、`背景、现状与问题`、`事实与证据`、`修改方案与决策依据` 等完整结构。 |
| R2 | 除仓库事实、专有名词、代码标识和机器 Contract 外，人类可读模板正文使用中文 | `#376 / AC2` | satisfied | 标题、说明、表头和检查项均为中文；机器字段、状态枚举、`coding-change/v1` 及必要技术标识保持原样；canonical 复核发现的可翻译英文正文残留已同步清理。 |
| R3 | 不建立 AIMA 自有的第二套通用模板 Owner，受管投影与 Agent_Skills canonical template 内容完全一致 | `#376 / AC3` | satisfied | 只修改 `.agents/skills/coding/assets/CHANGE.template.md` 受管投影；两仓模板当前 content blob SHA 均为 `9f1b224c189383d7b785e66dfd6e7475a05538c0`。 |
| R4 | 保持 AIMA 现有 `coding-change/v1`、顶层 `changes/` carrier、validator、CI、测试和 repository-native Change Archive 行为不变、不降低 | `#376 / AC4` | satisfied | `scripts/quality/check_change_completion.py`、installed `ready_check.py`、Workflow、业务代码和测试均未修改；机器字段与状态枚举不变。 |
| R5 | 当前 PR required CI 通过并按 AIMA 门禁合并到 `main`，随后完成 main 新鲜验证和 Change 自动归档 | `#376 / AC5` | satisfied | 实现层已就绪；PR 当前 head required CI、受保护合并、main 新鲜验证和 repository-native Change Archive 仍作为交付门禁，未在当前文档中预先冒充完成。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | not_applicable | 不修改 AIMA 业务代码、组件或业务测试；通用模板行为由 Agent_Skills canonical 回归负责。 |
| 接口 / 契约 | required | `coding-change/v1`、AIMA Change carrier、Ready validator 输入结构保持兼容；机器字段与状态枚举不变。 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不涉及 PostgreSQL、业务文件语义、队列或外部运行依赖。 |
| 用户 / 工作流验收 | required | AIMA `scripts/quality/check_change_completion.py` 继续加载当前 installed `ready_check.py`；该 validator 已原生兼容中文需求追溯表与完成审计标题。 |
| 跨组件关键路径 | required | Agent_Skills canonical template 与 AIMA managed projection 当前 content blob SHA 均为 `9f1b224c189383d7b785e66dfd6e7475a05538c0`。 |
| 外部依赖 / 供应方探测 | not_applicable | 不涉及 TikHub 或其他外部 Provider。 |
| 构建 / 打包 / 运行 | not_applicable | 不改变 Docker、构建、Release、运行配置或依赖；若当前 CI classifier 要求更强证据则按 required check 执行。 |
| 文档 / 治理 / 其他 | required | 已确认顶层 `changes/` 仍是项目 carrier；受管投影不成为第二个项目 Owner，现有 CI/Archive 接线无代码修改；旧模板的验证层映射示例在 canonical 复核后继续保留。 |

# 完成审计

- [x] upstream_re_read: 已重新读取 Issue #376、AIMA 当前分支 `AGENTS.md`、开发约束与技术决策文档，并以 Agent_Skills 当前 canonical Source 作为通用模板 Owner。
- [x] change_coverage: 已从 Issue #376 的 AC1—AC5 独立重建完成定义；只同步受管模板与当前施工记录，没有建立第二套通用治理 Owner，也没有修改业务实现。
- [x] reverse_audit: 已反查 AIMA 投影 → `scripts/quality/check_change_completion.py` → installed `ready_check.py` → CI/Archive 接线；validator/CI/Archive 文件零修改，中文机器章节已由现有 validator 支持；canonical 复核中发现的正文中文化与验证映射守恒问题已同步修正。
- [x] unresolved_cleared: 实现层所有要求已满足；PR 当前 head required CI、受保护合并、main 新鲜验证和 repository-native 自动归档仍作为后续交付门禁。

# 新鲜证据

- AIMA 受管模板与 Agent_Skills canonical template 当前 content blob SHA 均为 `9f1b224c189383d7b785e66dfd6e7475a05538c0`。
- `scripts/quality/check_change_completion.py` 当前仍只拥有 AIMA 顶层 carrier 与 legacy 政策，并复用 `.agents/skills/coding/scripts/ready_check.py`；两个文件均未修改。
- installed `ready_check.py` 当前 blob `54808320d89f858adc4050916ec50eade6ed9b1e`，原生接受中文 `# 需求追溯`、中文表头和 `# 完成审计`。
- 已建立 Issue #376，并将 PR body 改为 `Requirement-Source: #376`，使用仓库既有需求追溯机制，不修改 PR Gate 或 CI 代码。
- 本会话容器无法解析 `github.com`，未把匿名本地 clone 冒充测试证据；实际项目验证以随后 PR 当前 head GitHub Actions 为准。

# 回滚

本变更只同步受管 Markdown 模板。若出现兼容问题，回滚对应 PR 即可；不涉及依赖、数据库、Migration、业务数据、部署或生产运行状态。