---
schema: rvc-change/v1
id: CHG-20260825-coding-skill-beijing-time
title: Coding Skill 重命名与北京时间统一
level: L2
status: in_progress
owner: aima
branch: refactor/coding-skill-beijing-time
created: 2026-08-25
updated: 2026-08-25
completion_gate: required
depends_on: []
affected_areas:
  - developer-tooling
  - agent-workflow
  - testing-governance
affected_paths:
  - .agents/skills/
  - .agents/project-context.json
  - AGENTS.md
  - .github/workflows/change-completion-gate.yml
  - docs/blueprint/06_开发约束与分阶段实施.md
  - tests/unit/
contracts: []
data_changes: []
---

# 背景与目标

当前通用研发 Skill 的正式名称和目录仍为 `reliable-vibe-coding`，项目缓存写入 `.reliable-vibe-coding/project-context.json`，缓存 `generated_at` 和 Change 日期实现直接使用 UTC。用户要求把 Skill 正式名称统一改为 `coding`，把项目缓存固定到 `.agents/project-context.json`，并把 Skill/Agent 产生或规定的时间统一为北京时间，同时新增统一日志前缀格式。

本 Change 只调整通用 Skill、其脚本/测试和 AIMA 当前 live 导航/CI 引用，不改变 AIMA 产品 API、数据库 Schema/Migration、产品数据和业务功能。

# 成功标准

- [ ] Skill 正式目录统一为 `.agents/skills/coding/`，`SKILL.md` name、标题、Agent display/default prompt、live 文档、CI 和测试不再使用 `reliable-vibe-coding` 作为当前名称。
- [ ] 项目缓存唯一正式路径为 `.agents/project-context.json`；`coding.py discover` 的创建、读取、刷新全部使用该路径。
- [ ] 项目缓存中的 `generated_at` 使用 `Asia/Shanghai`（UTC+8）北京时间并保留明确时区偏移。
- [ ] Skill 增加全局北京时间规则：由 Skill/Agent 新建、输出或默认解释的时间戳、日期、日志、缓存、Change 元数据、报告/脚本默认时间等统一采用 `Asia/Shanghai`；外部协议/原始事实明确规定其他时区时保留原始语义，并在展示/日志/Agent 输出边界转换为北京时间。
- [ ] Skill 增加全局日志格式规则：人类可读日志统一使用 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message`，其中时间为北京时间、毫秒固定三位、源文件名和行号来自真实调用点、级别大写。
- [ ] live CLI 从 `rvc.py` 迁移为 `coding.py`，当前命令和 CI 全部使用新路径；`rvc-project-context/v1` / `rvc-change/v1` 仅作为既有协议 schema ID 保持兼容，不批量改写历史归档。
- [ ] 新增/更新回归测试，能够保护 Skill 重命名、缓存路径、北京时间和日志格式规则。
- [ ] 最终候选完成 Requirement Traceability、Validation Matrix、Completion Audit、两阶段 Review，并在同一 HEAD 上通过 Change Completion Gate、CI、Runtime/适用 fast-path。

# 范围

- 重命名 `.agents/skills/reliable-vibe-coding/` 为 `.agents/skills/coding/`。
- 重命名 live CLI `scripts/rvc.py` 为 `scripts/coding.py`，同步当前命令和测试。
- 修改项目发现缓存路径和时间实现。
- 修改 Skill 主规则、项目发现、开发工作流、Review、规则保留映射和 Agent 默认提示中的当前名称/时间/日志规则。
- 同步 AIMA 根 `AGENTS.md`、Blueprint 06、Change Completion Gate 和当前仓库 live 测试/导航。
- 只迁移历史归档 Change 中仍被 Ready Check 当作实时仓库路径解析的 Source；不为品牌改名批量重写历史叙事、Evidence 和结论。

# 非目标

- 不修改产品日志实现、业务数据库时间字段或外部 Contract 的既有时间语义；本 Change 建立通用 Skill 规则和 Skill 自身脚本行为。
- 不改变 `rvc-project-context/v1` / `rvc-change/v1` 既有协议 schema ID；避免无业务价值的历史 Change 批量迁移。
- 不升级依赖、Runtime、GitHub Actions 或锁文件。
- 不修改 AIMA 产品 API、Canonical、Schema/Migration、前端业务行为或部署拓扑。

# 必须保持不变

- 内容守恒优先于篇幅精简；Skill 重命名不能删除现有 Change/TDD/Review/验证/Git/安全/注释/日志等有效规则。
- 所有 Git 提交信息继续使用中文。
- 新增或修改的 public/exported 与 internal/private/helper 函数继续具有函数级中文说明。
- 当前 AIMA 文档治理、Requirement Traceability、Completion Gate 和两阶段 Review 机制继续有效。
- 历史归档 Change 的历史状态、Evidence、Review 和结论不因当前名称迁移被改写。

# 关键决策

1. Skill 的当前品牌、目录、CLI 和 Agent invocation 全部使用 `coding`，不保留第二套 live `reliable-vibe-coding` Skill。
2. 缓存直接固定到项目根 `.agents/project-context.json`，不再创建独立 `.reliable-vibe-coding/` 状态目录。
3. 北京时间使用 IANA `Asia/Shanghai`，不以宿主本地时区或固定字符串模拟；ISO 时间戳保留 `+08:00` 偏移。
4. 既有 `rvc-*` schema ID 属于持久协议兼容标识，不等同于当前 Skill 名称，本次保持读取兼容。
5. 日志规范统一人类可读前缀；项目若受更高优先级外部 wire-format Contract 强制使用 JSON/其他格式，仍必须保留等价的北京时间、source、line、level 字段，不得静默改回 UTC。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 项目缓存路径固定为 `.agents/project-context.json` | user:2026-08-25-coding-cache-path | not_satisfied | 当前 `01_project-discovery.md` 和 `rvc.py` 仍使用 `.reliable-vibe-coding/project-context.json` |
| R2 | 项目缓存文件中的时间使用北京时间 | user:2026-08-25-coding-cache-beijing-time | not_satisfied | 当前 `scan_project()` 的 `generated_at` 使用 `datetime.now(timezone.utc)` |
| R3 | Skill 中所有时间相关默认采用北京时间 | user:2026-08-25-coding-global-beijing-time | not_satisfied | 当前 Skill 尚无全局 `Asia/Shanghai` 时间不变量，Change 日期实现也取 UTC date |
| R4 | 日志使用 `[2026-08-25 09:44:19.257 runtime.py L114] [INFO]` 同类格式 | user:2026-08-25-coding-log-format | not_satisfied | 当前日志规则只有级别/安全/事件要求，没有统一前缀格式 |
| R5 | Skill 改名为 `coding` 并同步所有当前相关内容 | user:2026-08-25-rename-skill-coding | not_satisfied | 当前目录、Skill name、Agent prompt、AGENTS、CI 和测试仍使用 `reliable-vibe-coding` |
| R6 | 不从历史聊天猜实现，按当前仓库事实与门禁交付到 main | AGENTS.md | satisfied | 已从当前 main 重新读取 `AGENTS.md`、Skill、项目发现、Change 管理、开发工作流、CI 与相关测试后建立本 Change |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 对 `coding.py` 缓存路径、北京时间 `generated_at`/Change 日期、Skill 名称和日志规则建立回归 |
| 接口 / Contract | not_applicable | 不修改产品 API/ABI/HTTP/Canonical；`rvc-*` schema ID 保持兼容 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改产品持久化/Runtime 依赖；缓存是 Skill 本地文件，由 Unit/临时目录验证即可 |
| 用户 / Workflow Acceptance | required | `coding.py discover/status/new-change` 当前命令路径可运行，Agent/AGENTS/CI live 导航可达 |
| 跨组件 Golden Path | not_applicable | 不修改产品跨组件接线 |
| 外部依赖 Probe | not_applicable | 无外部 Provider/付费事实需要验证 |
| Build / Package / Runtime | required | Skill self-tests、Ready Check、仓库 CI/Runtime fast-path 或适用门禁证明 rename 后工具入口可执行 |
| Docs / Governance / Other | required | 扫描 live 引用、Change Completion Gate、文档链接、Secret/Docs gate 及最终 Completion Audit |

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 任务

- [x] 重新读取当前 main `AGENTS.md`、Skill、项目发现、Change 管理、开发工作流、CI 和现有回归。
- [ ] 先新增本次需求回归并取得因旧名称/旧缓存路径/UTC/缺少日志格式而失败的有效 Red。
- [ ] 实施 Skill/目录/CLI/live 引用迁移和北京时间/日志规则。
- [ ] 修复 Ready Check 暴露的所有实时 Source 路径。
- [ ] 执行目标测试、Skill self-tests、仓库 Unit/Docs/Secret/CI 及适用 Runtime 验证。
- [ ] 重新执行 Completion Audit、Review A1/A2、Code Quality Review并转 Ready。
- [ ] 正常合并 PR 到 main；合并后验证 main，再独立归档本 Change。

# 文档影响

需要同步根 `AGENTS.md`、Blueprint 06、Skill references、Agent prompt、CI 命令及当前测试中的 live 路径。历史归档只在实时 Source 必须随文件移动时调整路径。

# 兼容性、部署与回滚

- 产品 API/Contract/Schema/Migration/数据：无变化。
- 依赖/Lock/Runtime：无变化。
- Skill 当前 invocation/path：有明确迁移，旧 `reliable-vibe-coding` live 路径不再保留。
- `rvc-project-context/v1` / `rvc-change/v1` schema ID：保持兼容。
- 旧 `.reliable-vibe-coding/project-context.json`：不再作为正式缓存读取；下一次 discover 在 `.agents/project-context.json` 重建。
- 回滚：整体 revert 本 Change 的 Skill/path/docs/tests/CI diff；不涉及产品数据回滚或 Migration downgrade。

# Git / PR

- Branch：`refactor/coding-skill-beijing-time`
- PR：尚未创建
- Merge：未执行
- Release / Deploy：不适用
