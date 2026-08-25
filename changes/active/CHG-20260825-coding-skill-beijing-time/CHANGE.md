---
schema: rvc-change/v1
id: CHG-20260825-coding-skill-beijing-time
title: Coding Skill 重命名与全系统北京时间统一
level: L3
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
  - platform-time
  - http-contract
  - database-runtime
affected_paths:
  - .agents/skills/coding/
  - .agents/project-context.json
  - AGENTS.md
  - .github/workflows/change-completion-gate.yml
  - backend/src/aima_ugc/
  - contracts/
  - frontend/src/generated/api/
  - docs/blueprint/
  - tests/unit/
  - tests/api/
  - tests/contracts/
contracts:
  - HTTP datetime serialization
  - coding-project-context/v1
data_changes: []
---

# 背景与目标

本 Change 最初只计划把通用研发 Skill 从 `reliable-vibe-coding` 重命名为 `coding`，把项目缓存迁到 `.agents/project-context.json`，并增加北京时间和日志格式规则。用户随后明确扩大时间要求：**除第三方 Raw、外部协议必须保持原始时间语义的事实层外，所有由系统或 Agent 创建、存储、传输、序列化、记录、展示和解释的时间，统一采用 `Asia/Shanghai` 北京时间。**

这会改变 AIMA 自有 HTTP datetime 的序列化偏移、数据库 Session 默认时区以及系统自产时间入口，因此本 Change 从 L2 升级为 L3。PostgreSQL `timestamptz` 字段类型和历史绝对时间点保持不变；第三方 Raw 与外部协议原始时间不改写。

日志继续使用现有简洁人类可读前缀，不增加 `timezone="Asia/Shanghai"` 之类冗余字段。

# 成功标准

- [ ] Skill 正式目录统一为 `.agents/skills/coding/`，`SKILL.md` name、标题、Agent display/default prompt、当前文档、CI 和测试不再把 `reliable-vibe-coding` 作为 live 名称。
- [ ] live CLI 唯一入口为 `.agents/skills/coding/scripts/coding.py`，旧 `rvc.py` 不保留。
- [ ] 项目缓存唯一正式路径为 `.agents/project-context.json`，schema 为 `coding-project-context/v1`；旧 `.reliable-vibe-coding/project-context.json` 不读取、不迁移、不兼容，下一次 discover 直接重建。
- [ ] 项目缓存 `generated_at` 和 Coding 新建 Change 的日期使用 `Asia/Shanghai` 北京时间；时间戳保留 `+08:00`。
- [ ] Coding Skill 明确全局规则：除第三方 Raw、外部协议必须保持原始时间语义的事实层外，系统/Agent 创建、存储、传输、序列化、记录、展示和解释的时间统一为 `Asia/Shanghai`。
- [ ] AIMA 自有 HTTP datetime 输出统一为 ISO-8601 北京时间并带 `+08:00`，不再默认输出 UTC `Z/+00:00`。
- [ ] PostgreSQL 继续使用 `timestamptz` 保存绝对时间点，同时应用数据库 Session 默认时区显式为 `Asia/Shanghai`，不依赖数据库主机/容器默认 timezone。
- [ ] 系统自产“当前时间/今天”不依赖宿主本地时区或 UTC-now 作为业务默认；统一通过项目时间能力获得北京时间。
- [ ] 第三方 Raw 和外部协议要求的原始 timestamp/epoch/timezone 仍按原协议保存和解释，不为了北京时间改写证据层。
- [ ] 人类可读日志统一形如 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message`；北京时间、毫秒三位、真实源文件/行号、LEVEL 大写，且**不额外显示 timezone 字段**。
- [ ] `changes/archive/**` 不因本次 Skill 改名或时间策略批量改写；`rvc-change/v1` 因 Change 文件格式未变化继续保持原值，不引入兼容迁移层。
- [ ] Contract/OpenAPI/generated client、API/Unit/数据库 Runtime、Skill self-tests 和文档治理回归覆盖新规则。
- [ ] 最终候选完成 Requirement Traceability、Validation Matrix、Completion Audit、两阶段 Review，并在同一最终 HEAD 通过永久 CI/Runtime/Full-stack/Change Gate 的适用门禁后正常合并 main，再独立归档本 Change。

# 范围

- `.agents/skills/coding/` 名称、CLI、缓存、时间、日志、Review 与规则保留映射。
- AIMA 当前 live `AGENTS.md`、CI、Blueprint 和测试导航。
- AIMA 系统时间基础能力、系统自产时间入口、PostgreSQL Session timezone。
- AIMA 自有 HTTP Response datetime 序列化和相应 OpenAPI/generated client 一致性验证。
- API/Unit/Contract/Runtime/Full-stack 中与时间偏移语义直接相关的回归。

# 非目标

- 不修改 PostgreSQL 时间字段类型，不新增 Migration，不重写已有业务数据的绝对时间点。
- 不修改第三方 Raw 原始响应或外部协议明确要求的 timestamp/epoch/UTC wire semantics。
- 不为日志增加 `timezone="Asia/Shanghai"` 或其他重复 timezone 文本。
- 不批量修改 `changes/archive/**` 历史 Change 的叙事、Evidence、状态或旧路径文本。
- 不升级依赖、Runtime、GitHub Actions 或锁文件。
- 不改变与时间无关的业务规则、页面功能、Provider 能力或部署拓扑。

# 必须保持不变

- 内容守恒优先于篇幅精简；Skill 重命名不能删除 Change/TDD/Review/验证/Git/安全/注释/日志等有效规则。
- 所有 Git 提交信息继续使用中文。
- 新增或修改的 public/exported 与 internal/private/helper 函数继续具有函数级中文说明。
- 当前 AIMA 文档治理、Requirement Traceability、Completion Gate 和两阶段 Review 机制继续有效。
- `rvc-change/v1` 的 Change 文件结构和 Ready Check 语义保持不变。
- PostgreSQL `timestamptz` 继续表达绝对时间点；时区统一不等于改成无时区字段或字符串时间。
- 第三方 Raw 必须继续可作为供应商原始事实证据。

# L3 方案比较与关键决策

## 方案 A：只统一展示层

数据库/内部仍 UTC，只在前端和日志转换北京时间。

- 优点：改动少。
- 缺点：API、脚本、报告、Agent、DB Session 仍混合时区，开发者必须持续判断边界，不满足“创建、存储、传输、序列化、记录、展示和解释统一北京时间”。
- 结论：不采用。

## 方案 B：系统默认全北京时间，保留外部事实层原语义

- 系统自有当前时间、日期、API datetime、DB Session、报告/日志/Agent 默认 `Asia/Shanghai`；
- PostgreSQL 仍为 `timestamptz`；
- 第三方 Raw / 外部协议必须原样的时间保持原语义；
- 边界转换显式进行。

优点：满足用户目标，规则单一，仍保留跨时区协议正确性和绝对时间语义。
缺点：属于 HTTP Contract 行为变化，需要完整回归。

**采用方案 B。**

## 方案 C：连第三方 Raw 都改写北京时间

- 优点：表面上“所有地方看起来一样”。
- 缺点：破坏供应商原始证据和协议语义，可能导致签名、epoch、审计和重放错误。
- 结论：禁止。

关键决策：

1. Skill、目录、CLI 和 Agent invocation 全部使用 `coding`，不保留第二套 live Skill。
2. 缓存只使用 `.agents/project-context.json` + `coding-project-context/v1`；旧缓存直接废弃重建。
3. `Asia/Shanghai` 是 AIMA/Coding 系统默认时区，系统自产时间不得依赖宿主本地时区。
4. AIMA 自有 API datetime 序列化使用 `+08:00`；这是本次明确批准的 Contract 行为变化。
5. PostgreSQL 保留 `timestamptz`，Database Runtime 连接显式设置 Session timezone 为 `Asia/Shanghai`。
6. 第三方 Raw 和外部协议必须保持原始时间语义的字段是唯一例外；进入系统自有展示/序列化边界时再按要求转换。
7. 日志前缀保持 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL]`，不输出 timezone 名称；现有 Formatter 若已满足，不做无意义修改。
8. `changes/archive/**` 不改；`rvc-change/v1` 不改，因为 Change 文件格式没有变化。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 项目缓存路径固定为 `.agents/project-context.json` | user:2026-08-25-coding-cache-path | not_satisfied | 已实现新路径，等待最终同 HEAD 回归证据 |
| R2 | 项目缓存时间使用北京时间 | user:2026-08-25-coding-cache-beijing-time | not_satisfied | `coding.py` 已改为 `Asia/Shanghai`，等待最终回归 |
| R3 | Coding Skill 所有时间相关默认采用北京时间 | user:2026-08-25-coding-global-beijing-time | not_satisfied | 主 Skill/Workflow/Review 已初步补规则，需按最新“全系统”语义收紧并验证 |
| R4 | 日志使用 `[2026-08-25 09:44:19.257 runtime.py L114] [INFO]` 同类格式 | user:2026-08-25-coding-log-format | not_satisfied | 现有 `AimaLogFormatter` 已满足核心格式，需回归保护且不增加 timezone 字段 |
| R5 | Skill 改名为 `coding` 并同步所有当前相关内容 | user:2026-08-25-rename-skill-coding | not_satisfied | 目录/CLI/部分 live 引用已迁移，仍需全量 live 扫描与 CI |
| R6 | 旧缓存不需要兼容，重新生成即可 | user:2026-08-25-no-cache-compat | not_satisfied | `coding.py` 已只读取新缓存路径，需补 schema/旧缓存拒绝回归 |
| R7 | `changes/archive/**` 不因本次改名批量修改 | user:2026-08-25-archive-unchanged | not_satisfied | 最终 diff 必须证明除当前 Change 归档动作外没有改写历史归档 |
| R8 | `rvc-change/v1` 因文件格式未变保持原标识，不建立所谓兼容层 | user:2026-08-25-change-schema-unchanged | not_satisfied | 当前 parser/Change 继续使用该 schema，需文档删除错误兼容表述 |
| R9 | 除第三方 Raw/外部协议原始事实层外，所有系统/Agent 时间统一 `Asia/Shanghai` | user:2026-08-25-system-wide-beijing-time | not_satisfied | 当前 AGENTS 仍声明 API UTC，DatabaseRuntime 未设置 Session timezone，需实现与回归 |
| R10 | 日志不显示 `timezone="Asia/Shanghai"` | user:2026-08-25-log-no-timezone-field | not_satisfied | 当前 Formatter 未输出 timezone，需测试固定该边界 |
| R11 | 不从历史聊天猜实现，按当前仓库事实与门禁交付并合并 main | AGENTS.md | satisfied | 已重新读取当前分支 AGENTS、Skill、L3 Change/Contract/测试规则及 main/branch HEAD |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Coding 缓存/时间、统一时间 utility、Formatter、系统自产时间静态治理、datetime 转换/序列化 |
| 接口 / Contract | required | AIMA 自有 HTTP datetime 输出从 UTC 语义统一为 `+08:00`；OpenAPI/generated client drift 检查 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL Session timezone 为 `Asia/Shanghai`，`timestamptz` 绝对时间语义不变 |
| 用户 / Workflow Acceptance | required | Coding CLI discover/status/new-change；API 返回的用户可见时间带 `+08:00`；前端现有 workflow 不因 offset 变化失效 |
| 跨组件 Golden Path | required | 现有 Real Full-stack Golden Path 验证真实 Frontend/API/PostgreSQL/Worker 接线未被时间策略破坏 |
| 外部依赖 Probe | not_applicable | 不修改 TikHub/LLM 外部协议或当前供应商事实；Raw/协议例外由稳定 fixture/代码审计保护，不需要付费 Probe |
| Build / Package / Runtime | required | Wheel、Frontend build、Runtime Acceptance、正式 CI 环境中的 ZoneInfo/DB timezone 行为 |
| Docs / Governance / Other | required | Skill self-tests、live 引用扫描、Change Gate、Docs/Secret/Architecture/Owner、历史 archive 未被改写 |

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 任务

- [x] 取得原始 Skill/缓存/日志/命名需求的有效 Red：Ruff/mypy 先通过，Unit `650 passed / 5 failed`，5 个失败逐项命中旧名称、旧缓存、缺少北京时间、缺少日志格式和旧 live 导航。
- [x] 迁移 Skill 目录为 `.agents/skills/coding/`，建立 `coding.py` 并删除旧 `rvc.py`。
- [x] 初步实现 `.agents/project-context.json`、`coding-project-context/v1` 和 Coding 自身北京时间。
- [x] 初步迁移 Agent prompt、Change Completion Workflow、根 AGENTS、docs AGENTS、Blueprint 06 与 Skill 自测路径。
- [ ] 针对“全系统北京时间”新增扩展 Red：HTTP datetime `+08:00`、Database Session timezone、系统自产时间入口和日志不含 timezone 字段。
- [ ] 建立/复用最小系统时间能力，迁移所有系统自产时间；保留第三方 Raw/外部协议原始时间例外。
- [ ] 统一 AIMA 自有 HTTP datetime 序列化为北京时间，重新生成并验证 OpenAPI/generated client。
- [ ] 显式设置 PostgreSQL Session timezone `Asia/Shanghai` 并完成真实 PostgreSQL Integration。
- [ ] 收紧 Skill/Workflow/Review/规则保留映射和 AIMA Blueprint 04/05/06 的最终时间语义；移除“API UTC”旧规则和错误兼容表述。
- [ ] 全量扫描 live `reliable-vibe-coding` / `rvc.py` 引用并修正当前事实；历史 `changes/archive/**` 不改写。
- [ ] 执行目标测试、Skill self-tests、Unit/Contract/API、PostgreSQL、Frontend、Runtime/Full-stack、Docs/Secret/Architecture/Owner 等永久门禁。
- [ ] 重新执行 Completion Audit、Review A1/A2、Code Quality Review，清零所有 `not_satisfied` 并转 Ready。
- [ ] 正常合并 PR #230 到 main；验证 main 后创建独立归档 PR，仅把本 Change `done` 后移动到 `changes/archive/2026-08/`，不修改其他历史 Change。

# 文档影响

需要同步：

- `.agents/skills/coding/SKILL.md` 及时间/开发/Review/规则保留 references；
- 根 `AGENTS.md`；
- `docs/blueprint/04_后端任务API与前端.md`；
- `docs/blueprint/05_日志安全部署与运维.md`；
- `docs/blueprint/06_开发约束与分阶段实施.md`；
- 当前 CI/测试中的 live Skill/CLI 路径。

`changes/archive/**` 历史内容不因本次迁移改写。

# 兼容性、Migration、部署与回滚

- HTTP Contract：datetime 文本偏移从历史默认 UTC `Z/+00:00` 统一为北京时间 `+08:00`；表示同一个绝对时间点，属于客户端可观察序列化变化，需 Contract/API/Frontend 回归。
- Database Schema/Migration：无变化；仍使用 `timestamptz`。
- Database Runtime：连接 Session timezone 改为 `Asia/Shanghai`；需真实 PostgreSQL 验证日期边界、读取偏移和现有查询。
- 产品历史数据：不回填、不重写绝对时间点。
- 外部 Raw/协议：不变。
- 依赖/Lock：计划无变化，使用 Python 标准库 `zoneinfo`。
- 旧 Skill/cache：旧 live Skill/CLI 不保留；旧缓存不读取，重新 discover 即可。
- Change schema：`rvc-change/v1` 不变，因为结构未变。
- 回滚：整体 revert 本 Change；HTTP 序列化和 DB Session timezone 恢复原策略即可，无 Migration downgrade/数据回填。

# Git / PR

- Branch：`refactor/coding-skill-beijing-time`
- PR：`#230`（Draft）
- 当前 main 基线：`5f9d125ae716d34295f8397b337248020069588a`
- Merge：未执行
- Release / Deploy：不适用；本任务授权最终正常合并 main 并完成 Change 归档闭环
