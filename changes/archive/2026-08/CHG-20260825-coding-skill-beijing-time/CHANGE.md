---
schema: rvc-change/v1
id: CHG-20260825-coding-skill-beijing-time
title: Coding Skill 重命名与全系统北京时间统一
level: L3
status: done
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
  - changes/archive/2026-08/
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

- [x] Skill 正式目录统一为 `.agents/skills/coding/`，`SKILL.md` name、标题、Agent display/default prompt、当前文档、CI 和测试不再把 `reliable-vibe-coding` 作为 live 名称。
- [x] live CLI 唯一入口为 `.agents/skills/coding/scripts/coding.py`，旧 `rvc.py` 不保留。
- [x] 项目缓存唯一正式路径为 `.agents/project-context.json`，schema 为 `coding-project-context/v1`；旧 `.reliable-vibe-coding/project-context.json` 不读取、不迁移、不兼容，下一次 discover 直接重建。
- [x] 项目缓存 `generated_at` 和 Coding 新建 Change 的日期使用 `Asia/Shanghai` 北京时间；时间戳保留 `+08:00`。
- [x] Coding Skill 明确全局规则：除第三方 Raw、外部协议必须保持原始时间语义的事实层外，系统/Agent 创建、存储、传输、序列化、记录、展示和解释的时间统一为 `Asia/Shanghai`。
- [x] AIMA 自有 HTTP datetime 输出统一为 ISO-8601 北京时间并带 `+08:00`，不再默认输出 UTC `Z/+00:00`。
- [x] PostgreSQL 继续使用 `timestamptz` 保存绝对时间点，同时应用数据库 Session 默认时区显式为 `Asia/Shanghai`，不依赖数据库主机/容器默认 timezone。
- [x] 系统自产“当前时间/今天”不依赖宿主本地时区或 UTC-now 作为业务默认；统一通过项目时间能力获得北京时间。
- [x] 第三方 Raw 和外部协议要求的原始 timestamp/epoch/timezone 仍按原协议保存和解释，不为了北京时间改写证据层。
- [x] 人类可读日志统一形如 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message`；北京时间、毫秒三位、真实源文件/行号、LEVEL 大写，且**不额外显示 timezone 字段**。
- [x] `changes/archive/**` 的历史叙事、Evidence、状态和 Review 不因本次 Skill 改名或时间策略批量改写；被 Ready Check 作为实时仓库路径校验的 Requirement Source 随 canonical Skill 路径做最小迁移；`rvc-change/v1` 因 Change 文件格式未变化继续保持原值，不引入兼容迁移层。
- [x] Contract/OpenAPI/generated client、API/Unit/数据库 Runtime、Skill self-tests 和文档治理回归覆盖新规则。
- [x] 最终 Ready HEAD 通过永久 CI/Runtime/Full-stack/Developer Tooling/Change Gate 后正常合并 main，并在 main merge commit 上再次通过五套 push 门禁；本 Change 由独立归档分支原子移动到 `changes/archive/2026-08/`。

# 范围

- `.agents/skills/coding/` 名称、CLI、缓存、时间、日志、Review 与规则保留映射。
- AIMA 当前 live `AGENTS.md`、CI、Blueprint 和测试导航。
- AIMA 系统时间基础能力、系统自产时间入口、PostgreSQL Session timezone。
- AIMA 自有 HTTP Response datetime 序列化和相应 OpenAPI/generated client 一致性验证。
- API/Unit/Contract/Runtime/Full-stack 中与时间偏移语义直接相关的回归。
- 因 canonical Skill 路径移动而失效的 gated 历史 Change `Requirement Source` 实时路径迁移；只改 Source 单元格，不改历史事实叙事。

# 非目标

- 不修改 PostgreSQL 时间字段类型，不新增 Migration，不重写已有业务数据的绝对时间点。
- 不修改第三方 Raw 原始响应或外部协议明确要求的 timestamp/epoch/UTC wire semantics。
- 不为日志增加 `timezone="Asia/Shanghai"` 或其他重复 timezone 文本。
- 不批量修改 `changes/archive/**` 历史 Change 的叙事、Evidence、状态、Review 或普通旧路径文本；只有 Ready Check 实时校验的 Requirement Source 随目标文件移动。
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
7. 供应商分时定价的 `timezone` 属于供应商价格协议事实：AIMA 记录请求时刻使用北京时间，但选价时把同一绝对时刻转换到模型配置的 `timezone`；不得把供应商 UTC/其他时区价格表强制解释成北京时间。
8. 日志前缀保持 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL]`，不输出 timezone 名称；现有 Formatter 若已满足，不做无意义修改。
9. OOXML/W3CDTF 等明确要求 UTC `Z` 的外部协议必须先把北京时间绝对时刻转换为 UTC，再写 `Z`，不得把北京时间墙钟直接伪装成 UTC。
10. `changes/archive/**` 的历史叙事/Evidence/状态/Review 不因当前路径迁移改写；只有 Ready Check 作为实时仓库路径校验的 Requirement Source 随 canonical 文件移动。`rvc-change/v1` 不改，因为 Change 文件格式没有变化。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 项目缓存路径固定为 `.agents/project-context.json` | user:2026-08-25-coding-cache-path | satisfied | `.agents/skills/coding/scripts/coding.py` 与 `tests/unit/test_coding_skill_time_and_naming.py` 固定新路径；Developer Tooling Compatibility run 32823858570 成功 |
| R2 | 项目缓存时间使用北京时间 | user:2026-08-25-coding-cache-beijing-time | satisfied | Coding CLI 通过 `Asia/Shanghai` 生成 `generated_at`；命名/时间回归已纳入 662 个 Unit 全绿 |
| R3 | Coding Skill 所有系统自产时间相关默认采用北京时间 | user:2026-08-25-coding-global-beijing-time | satisfied | `SKILL.md`、development workflow、verification review 与 AIMA `platform/time.py` 固化规则；`test_system_beijing_time_policy.py` 扫描生产源码禁止 UTC-now/宿主本地 now |
| R4 | 日志使用 `[2026-08-25 09:44:19.257 runtime.py L114] [INFO]` 同类格式 | user:2026-08-25-coding-log-format | satisfied | 现有 `AimaLogFormatter` 保持三位毫秒/真实文件行号/大写级别；`test_logging_timezone_policy.py` 固定北京时间前缀 |
| R5 | Skill 改名为 `coding` 并同步所有当前相关内容 | user:2026-08-25-rename-skill-coding | satisfied | `.agents/skills/coding/` 为唯一 live Skill，旧目录直接读取返回 404；AGENTS、README、CI、自测 live 引用已同步；Developer Tooling Compatibility 成功 |
| R6 | 旧缓存不需要兼容，重新生成即可 | user:2026-08-25-no-cache-compat | satisfied | `coding.py` 只读写 `.agents/project-context.json` + `coding-project-context/v1`，未增加旧缓存迁移/兼容层；相关 Unit 全绿 |
| R7 | `changes/archive/**` 历史内容不因改名批量重写；机器实时 Requirement Source 随 canonical Skill 路径迁移 | user:2026-08-25-archive-unchanged | satisfied | Ready Gate run 32824523183 精确暴露 5 个归档 Change 的旧 Skill Source；按 `docs/AGENTS.md` 只把这 5 个 Requirement Source 单元格迁到 `.agents/skills/coding/...`，未改历史 Evidence、状态、Review 或普通旧路径文本 |
| R8 | `rvc-change/v1` 因文件格式未变保持原标识，不建立兼容层 | user:2026-08-25-change-schema-unchanged | satisfied | 当前 Change、parser、Ready Check 继续使用 `rvc-change/v1`；只迁移 Skill 名称/CLI，不改 Change schema |
| R9 | 除第三方 Raw/外部协议原始事实层外，所有系统/Agent 时间统一 `Asia/Shanghai` | user:2026-08-25-system-wide-beijing-time | satisfied | AIMA 自有 HTTP `+08:00`、输入归一化、`beijing_now/beijing_today`、PostgreSQL Session `Asia/Shanghai`、LLM 审计北京时间、DOCX 外部 UTC 边界均已实现；CI run 32823858633 与 Full-stack run 32823858623 成功 |
| R10 | 日志不显示 `timezone="Asia/Shanghai"` | user:2026-08-25-log-no-timezone-field | satisfied | `test_logging_timezone_policy.py` 明确断言不存在 `timezone=` 与 `Asia/Shanghai` 文本；662 Unit 全绿 |
| R11 | 不从历史聊天猜实现，按当前仓库事实与门禁交付并合并 main | AGENTS.md | satisfied | Ready 前再次读取 AGENTS、Coding Skill、Blueprint 04/05/06；最终 PR HEAD 与 main merge commit 均通过永久门禁，且按独立归档流程收尾 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | CI run 32823858633：662 Unit 通过；覆盖 Coding 缓存/时间、HTTP 序列化、日志、LLM Pricing 北京时间生效日、供应商分时 timezone 与系统自产时间静态治理 |
| 接口 / Contract | required | CI run 32823858633：75 Contract + 34 API 通过；OpenAPI/Orval 重新生成后 `git diff --exit-code` 与 compatibility check 通过 |
| 集成 / Persistence / Runtime Dependency | required | CI run 32823858633：PostgreSQL Integration 全绿；历史 Migration compatibility、真实 readiness、Database/Job/Collection/Content/Ingestion 全部通过，Session timezone 回归验证 `Asia/Shanghai` |
| 用户 / Workflow Acceptance | required | Developer Tooling Compatibility run 32823858570 成功；CI 前端 39 Unit + 22 Browser Mock Acceptance 通过；AIMA HTTP/页面现有 workflow 未因 offset 变化失效 |
| 跨组件 Golden Path | required | Full-stack Acceptance run 32823858623 成功，真实 Frontend/API/PostgreSQL/Worker 接线保持可用 |
| 外部依赖 Probe | not_applicable | 未修改 TikHub/LLM Provider 接口、Mapper 或外部当前事实；第三方 Raw/供应商定价 timezone 只做稳定协议边界回归，不需要付费 Probe |
| Build / Package / Runtime | required | CI run 32823858633 Wheel build/install/import 成功；Runtime Acceptance run 32823858583 成功；Frontend lint/typecheck/build 成功 |
| Docs / Governance / Other | required | CI run 32823858633 Architecture/Table Ownership/Secret/Docs 全绿；Developer Tooling self-tests 全绿；Ready Gate run 32824523183 发现并完成 5 个 archive 实时 Source 最小迁移；最终 Ready HEAD Change Gate 32831298431 与 main push Change Gate 32831913880 均成功 |

# Completion Audit

- [x] upstream_re_read: Ready 前重新读取当前分支 `AGENTS.md`、`.agents/skills/coding/SKILL.md`、Blueprint 04/05/06、测试/Completion/Review 规则；合并后又重新读取 main `AGENTS.md` 并以当前 main 机器事实验证集成。
- [x] change_coverage: 逐条重建 R1-R11；Skill/CLI/cache、HTTP、DB Session、系统时间、日志、外部协议、Provider Pricing timezone、文档和测试均有实现与回归证据，`not_satisfied` 已清零。
- [x] reverse_audit: 从后端时间能力反查 HTTP/DB/日志/报告/LLM 消费边界，并从前端/Contract 反查后端真实支持；Full-stack、generated Client、真实 PostgreSQL 与 Runtime 均通过，无悬空消费者或第二套 UTC 假设；Skill canonical rename 还反向检查 gated 历史 Change 的实时 Source 并完成迁移。
- [x] unresolved_cleared: 误删 Migration 回归覆盖、旧 `datetime` 测试桩、OOXML 假 `Z`、Pricing 生效日 UTC 注释/语义、Ruff 导入问题及 5 个归档 Requirement Source 漂移均已修复；最终 Ready HEAD 与 merge 后 main 五套永久门禁均全绿，无未决业务/Contract/集成问题。

# Review A1：需求与完成定义审查

结论：**通过。**

- 用户已确认的 Skill 改名、缓存路径、北京时间、日志格式、旧缓存不兼容、历史 archive 不批量重写、Change schema 不变均已进入 R1-R10，没有依赖当前 Change 自身充当上游需求全集。
- AIMA 自有 HTTP datetime 明确改为 `+08:00`，输入归一到 `Asia/Shanghai`；Frontend generated Client 继续由 OpenAPI 单向生成，没有第二套时间 Contract。
- PostgreSQL 没有 Schema/Migration 或历史数据重写；`timestamptz` 绝对时刻保持，Session timezone 仅改变展示/解释上下文。
- 第三方 Raw、外部 wire protocol、供应商 Pricing timezone 被保留为协议事实；系统统一北京时间没有越界改写外部证据层。
- Skill canonical 路径改名触发的历史 archive 边界按仓库规则处理：普通历史叙事/Evidence/状态/Review 保持原样，只迁移 Ready Check 实时解析的 Requirement Source；没有恢复旧 Skill 或引入兼容层。
- Runtime/Full-stack/前端均有适用验收；Provider Probe 因未改变 Provider 接口/Mapper/当前外部事实而明确不适用。

# Review A2：实现与回归审查

结论：**通过，已修复审查中发现的问题。**

- 中央 `platform/time.py` 提供唯一系统时钟能力，生产源码静态回归禁止 `datetime.utcnow()`、naive `datetime.now()`、UTC-now 和 `date.today()` 重新成为业务默认。
- OOXML core-properties 在 W3CDTF `Z` 边界把北京时间绝对时刻转换到 UTC 后再格式化，避免把 `+08:00` 墙钟伪标为 `Z`。
- LLM 价格 `effective_date` 按 AIMA 北京时间日历判断；价格时段仍按每个模型 `timezone` 转换同一绝对时刻，避免破坏供应商定价规则。
- 历史 Migration 测试最初因 Session timezone 变化暴露 `16:30+08` 与 `08:30+00` 字符串差异；修复为 aware datetime 绝对时刻比较，没有修改历史 Migration。
- 审查曾发现一次整文件替换误删 `test_migration_data_lifecycle.py` 中 NFKC、downgrade、平台统一与冲突保护测试；已恢复原覆盖，当前相对 main 仅保留必要时间断言差异。
- 旧 LLM 测试仍 monkeypatch `datetime` 导致 4 个分时价格测试受 CI 当前时刻影响；已改为注入真实生产时钟 `beijing_now()`，fixture 使用北京时间，供应商 `timezone` 继续独立生效。
- Ready HEAD `54d9aa20a61a4f60e42c2c5e1fdc5072369c5b2b` 的 Change Gate 又精确暴露 5 个归档 Change 仍把已删除旧 Skill 路径作为机器实时 Source；已按 `docs/AGENTS.md` 只迁移 Source 单元格，未改写历史 Evidence/Review/状态。
- 最终 Ready HEAD `2fce7168119e9768600ee2e8a751514d09c3374f` 五套永久门禁全部成功；PR #230 正常合并后，merge commit `0ce475e47e88539610ef7528a17dce2e2fe20983` 的五套 main push 门禁再次全部成功。

# Code Quality Review

结论：**通过。**

- 产品/功能实现未保留临时迁移 Workflow/脚本，未升级依赖/锁文件，未引入 Schema/Migration。
- 5 个历史 archive 文件只迁移 Ready Check 实时 Requirement Source；历史叙事、Evidence、状态、Review 和普通旧路径文本保持不变，没有批量“洗历史”。
- Ruff format/check：501 files formatted / All checks passed；mypy：244 source files 无问题。
- Unit：662 passed；Contract：75 passed；API：34 passed。
- Frontend Unit：39 passed；Playwright Browser Mock Acceptance：22 passed；npm audit：0 vulnerabilities；Wheel build/install/import：0.1.0 成功。
- PostgreSQL Integration 全绿；Full-stack、Runtime、Developer Tooling 均成功。
- 已知 warnings 为现有 Pydantic `json_encoders` deprecation、XLSX duplicate-member 安全测试 warning 与 Starlette TestClient deprecation；无本 Change 新增失败或安全泄漏。
- Git 提交信息使用中文；新增/修改的本任务关键函数具备中文函数级说明；Secret/Docs/Architecture/Ownership 门禁通过。

# 任务

- [x] 取得原始 Skill/缓存/日志/命名需求的有效 Red：Ruff/mypy 先通过，Unit `650 passed / 5 failed`，5 个失败逐项命中旧名称、旧缓存、缺少北京时间、缺少日志格式和旧 live 导航。
- [x] 迁移 Skill 目录为 `.agents/skills/coding/`，建立 `coding.py` 并删除旧 `rvc.py`。
- [x] 实现 `.agents/project-context.json`、`coding-project-context/v1` 和 Coding 自身北京时间。
- [x] 迁移 Agent prompt、Change Completion Workflow、根 AGENTS、docs AGENTS、Blueprint 06 与 Skill 自测路径。
- [x] 针对“全系统北京时间”建立扩展 Red：HTTP datetime `+08:00`、Database Session timezone、系统自产时间入口和日志不含 timezone 字段。
- [x] 建立最小系统时间能力，迁移系统自产时间；保留第三方 Raw/外部协议原始时间例外。
- [x] 统一 AIMA 自有 HTTP datetime 序列化为北京时间，重新生成并验证 OpenAPI/generated client。
- [x] 显式设置 PostgreSQL Session timezone `Asia/Shanghai` 并完成真实 PostgreSQL Integration。
- [x] 收紧 Skill/Workflow/Review/规则保留映射和 AIMA Blueprint 04/05/06 的最终时间语义；移除“API UTC”旧规则和错误兼容表述。
- [x] 全量扫描 live `reliable-vibe-coding` / `rvc.py` 引用并修正当前事实；历史 archive 的叙事/Evidence/状态/Review 不改写，机器实时 Requirement Source 随 canonical Skill 路径最小迁移。
- [x] 执行目标测试、Skill self-tests、Unit/Contract/API、PostgreSQL、Frontend、Runtime/Full-stack、Docs/Secret/Architecture/Owner 等实现候选永久门禁。
- [x] 重新执行 Completion Audit、Review A1/A2、Code Quality Review，清零所有 `not_satisfied` 并转 Ready。
- [x] 最终 Ready HEAD `2fce7168119e9768600ee2e8a751514d09c3374f` 通过 CI `32831298114`、Runtime `32831298039`、Full-stack `32831298048`、Developer Tooling `32831298032`、Change Gate `32831298431`，PR #230 从 Draft 转 Ready。
- [x] PR #230 正常合并到 main；merge commit `0ce475e47e88539610ef7528a17dce2e2fe20983` 的 CI `32831914054`、Runtime `32831913930`、Full-stack `32831913873`、Developer Tooling `32831913879`、Change Gate `32831913880` 全部 success；随后由独立归档分支把本 Change 标记 `done` 并原子移入 archive。

# 文档影响

已同步：

- `.agents/skills/coding/SKILL.md` 及时间/开发/Review/规则保留 references；
- 根 `AGENTS.md`；
- `docs/blueprint/04_后端任务API与前端.md`；
- `docs/blueprint/05_日志安全部署与运维.md`；
- `docs/blueprint/06_开发约束与分阶段实施.md`；
- 当前 CI/测试中的 live Skill/CLI 路径；
- 5 个 gated 历史 Change 的机器实时 Requirement Source 路径。

`changes/archive/**` 的历史叙事、Evidence、状态、Review 与普通旧路径文本不因本次迁移改写。

# 兼容性、Migration、部署与回滚

- HTTP Contract：datetime 文本偏移从历史默认 UTC `Z/+00:00` 统一为北京时间 `+08:00`；表示同一个绝对时间点，属于客户端可观察序列化变化，已由 Contract/API/Frontend 回归覆盖。
- Database Schema/Migration：无变化；仍使用 `timestamptz`。
- Database Runtime：连接 Session timezone 改为 `Asia/Shanghai`；真实 PostgreSQL 已验证日期边界、读取偏移和现有查询。
- 产品历史数据：不回填、不重写绝对时间点。
- 外部 Raw/协议：不变；OOXML `Z` 与供应商 Pricing timezone 在显式协议边界转换。
- 依赖/Lock：无变化，使用 Python 标准库 `zoneinfo`。
- 旧 Skill/cache：旧 live Skill/CLI 不保留；旧缓存不读取，重新 discover 即可。
- Change schema：`rvc-change/v1` 不变，因为结构未变。
- 历史 gated Change：不建立旧 Skill 路径兼容层；Requirement Source 作为机器实时路径随 canonical 文件迁移，其他历史内容保留。
- 回滚：整体 revert 本 Change；HTTP 序列化和 DB Session timezone 恢复原策略即可，无 Migration downgrade/数据回填。

# 最终集成证据

## Final Ready HEAD

`2fce7168119e9768600ee2e8a751514d09c3374f`

```text
Change Completion Gate            32831298431  success
CI                                32831298114  success
Runtime Acceptance                32831298039  success
Full-stack Acceptance             32831298048  success
Developer Tooling Compatibility   32831298032  success
```

该 HEAD 与当时 `main` 比较 `behind_by=0`，PR #230 无 unresolved review thread，随后从 Draft 转 Ready 并以 expected HEAD 正常 merge。

## Merge / main push

- PR：#230 `统一 Coding Skill 名称、北京时间与日志格式`
- Merge commit：`0ce475e47e88539610ef7528a17dce2e2fe20983`
- Merge commit parents：原 main `5f9d125ae716d34295f8397b337248020069588a` + Final Ready HEAD `2fce7168119e9768600ee2e8a751514d09c3374f`
- main push 永久门禁：

```text
Change Completion Gate            32831913880  success
CI                                32831914054  success
Runtime Acceptance                32831913930  success
Full-stack Acceptance             32831913873  success
Developer Tooling Compatibility   32831913879  success
```

因此实现、真实 PostgreSQL、HTTP/Contract、Frontend、Full-stack、Compose Runtime、Developer Tooling 与治理门禁都已在 merge 后 main 再次验证。

# Git / PR

- Implementation branch：`refactor/coding-skill-beijing-time`
- Implementation PR：#230，已正常合并
- Final Ready HEAD：`2fce7168119e9768600ee2e8a751514d09c3374f`
- Merge commit：`0ce475e47e88539610ef7528a17dce2e2fe20983`
- Archive branch：`chore/archive-coding-skill-beijing-time`
- Archive：本文件由独立归档提交从 `changes/active/` 原子移动到 `changes/archive/2026-08/`；归档 PR/merge 由后续 GitHub PR 历史记录
- Release / Deploy：不适用；本任务只修改代码/Contract/Runtime 默认时间与开发治理，不发布 Release、不执行生产部署
