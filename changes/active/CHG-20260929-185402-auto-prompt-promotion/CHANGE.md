---
schema: coding-change/v1
id: CHG-20260929-185402-auto-prompt-promotion
title: 部署时自动发布镜像内置 Git Prompt
level: L3
status: proposed
owner: codex
branch: tech/667-auto-prompt-promotion
created: 2026-09-29
updated: 2026-09-29
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - runtime-configuration
  - docker-release
  - deployment-docs
affected_paths:
  - backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v4.6.md
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py
  - backend/src/aima_ugc/bootstrap/analysis_identity.py
  - backend/src/aima_ugc/entrypoints/internal_v1_configure_main.py
  - scripts/release/release_bundle.py
  - tests/unit/analysis/
  - tests/integration/content/
  - tests/unit/test_internal_v1_configure_main.py
  - tests/unit/test_release_bundle.py
  - AGENTS.md
  - backend/src/aima_ugc/modules/analysis/README.md
  - docs/appendix/07_AI舆情打标与分析实现.md
  - docs/blueprint/07_技术决策与实施门禁.md
  - docs/operations/01_生产部署与离线Release方案.md
  - docs/guides/06_本地Release离线包构建.md
contracts:
  - Analysis Scheme deployment promotion semantics
  - content-labeling.v4.6 prompt identity
  - Internal V1 configure exit and output contract
  - Offline release manifest analysis prompt identity
data_changes:
  - existing Analysis Scheme tables append a new version and move the active pointer without schema migration
---

# 变更摘要

- **要解决的问题**：镜像已经包含 Git 当前 Prompt，但服务器数据库的唯一 active Analysis Scheme Version 可能继续停留在旧版本，导致部署后新建 Analysis Run 仍冻结旧 Prompt。
- **拟议修改**：把部署期 `configure` 接入受锁、可审计的 Git Prompt 自动发布；系统 active 可按 Hash 幂等升级，人工 active 冲突时失败关闭；Release 验证并记录镜像实际 Prompt 身份，同时纳入用户当前工作区的 V4.6 Prompt 内容调整。
- **预期结果**：每次使用正式离线 Release 启动时，新业务进程只会在镜像 Prompt 已经成为可确认的 active Version 后启动；旧 Run 与人工配置不会被静默改写。

# 背景、现状与问题

## 背景

用户在 #667 明确要求每次构建镜像后自动使用镜像中显式选择的最新 Prompt，并确认系统 Git Scheme 可以自动升级、人工 active 不得静默覆盖。本轮又明确要求将当前工作区已有的 `content_labeling_v4.6.md` 行业相关性调整一并合入主分支。

## 当前现状

- `content_labeling_bootstrap.txt` 显式选择 V4.6，Docker wheel 已包含 Prompt 资产。
- PostgreSQL 中唯一 active Analysis Scheme Version 是运行时业务事实源；Analysis Run 创建时冻结当时的 Scheme Version、Prompt/Taxonomy Hash 与 Prompt Snapshot。
- `bootstrap_default()` 只允许空库或首次正式 Run 前的纯系统 bootstrap 刷新；存在历史 Run 后不会跟随新镜像。
- Compose 已按 `migrate → configure → API/Worker/Scheduler` 启动，但 `configure` 目前只处理 Provider/LLM 初始化。
- Release manifest 尚未记录 backend 镜像中实际安装的 Prompt 协议与 Hash。

## 问题、根因或约束

根因不是 Docker 未复制 Markdown，而是“镜像内 Git Prompt 身份”与“数据库 active Scheme”之间缺少部署期正式发布事务。仅修改首次 bootstrap 条件会混淆初始化与持续部署语义，也不能处理人工 active 冲突、审计、并发和镜像身份证明。

## 不修改的后果

服务器一旦有历史 Analysis Run，新镜像中的 V4.6 仍可能不被激活；管理员页面继续显示旧 Version，新 Run 继续冻结旧 Prompt。人工手动切换虽然能暂时止血，但每次发布都需要额外操作，且容易漏做，Release 也无法证明实际镜像包含哪份 Prompt。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Run 创建时冻结 active Scheme Version 和 Prompt/Taxonomy 身份，历史 Run 不随 active 改变 | `analysis_runs.py`、Analysis 集成测试 | 自动发布只影响之后创建的 Run |
| E2 | 现有首次刷新以 `run_count == 0`、唯一系统版本且无额外 Scheme 为前提 | `analysis_schemes.py::bootstrap_default` | 不能把初始化逻辑直接冒充持续部署机制 |
| E3 | Compose 业务进程依赖一次性 `configure` 成功 | `compose.yaml` | `configure` 是部署期 fail-closed 接点 |
| E4 | Release builder 已能运行/检查实际镜像并生成 manifest | `scripts/release/release_bundle.py` | Prompt 身份应从实际 backend 镜像读取并与源码比较 |
| E5 | 当前工作区 Prompt 改动扩大了 V4.6 的相关性范围，但固定输出协议和 Taxonomy 结构仍需保持 | 用户决定与工作区 diff | Prompt 必须经过解析、协议和镜像 Hash 回归 |
| E6 | 用户授权完成代码修改并合并主分支，但没有授权生产部署或生产数据操作 | 当前会话 / #667 | 交付边界止于代码合并与 main-fresh 验证 |

## 推断与待确认

- 生产服务器当前 active Version 的 `created_by`、版本数和历史 Run 数属于仓库外环境事实；本任务不连接或修改生产数据库。部署时由新逻辑在事务内检查并给出明确结果。
- 当前工作区 Prompt 首尾四反引号是否属于有效业务正文尚需解析与模型输入测试确认；若会把外层围栏作为正文发送或破坏解析，将保留业务规则修改但去除非语义围栏，并在交付中说明。

# 目标、成功标准与非目标

## 目标

建立从源码显式 Prompt 指针、backend 镜像实际内容、部署期配置事务到数据库唯一 active Scheme 的可验证链路，让系统管理的 Prompt 随正式镜像自动、幂等、安全地发布。

## 成功标准

- [ ] 系统管理的 active Version 与镜像 Prompt 不同时，即使已有历史 Run，部署期仍原子追加并激活新 Version。
- [ ] 相同 Prompt/Taxonomy 身份重复部署不创建重复 Version。
- [ ] 人工 active Version 存在时明确失败且不发生 Scheme/审计写入。
- [ ] 旧 Run 保留旧快照，新 Run 冻结新的 active Version。
- [ ] `configure` 输出动作、Version、协议和 Hash；实际提升写不含正文的系统审计事件。
- [ ] Release 从实际 backend 镜像读取 Prompt 身份，与源码比较并写入 manifest；不一致时失败。
- [ ] 当前工作区 V4.6 行业相关性调整通过解析、协议、回归与镜像身份验证。
- [ ] 空库 bootstrap、管理员发布/回滚、API/Schema、旧 Scheme 历史均保持兼容。
- [ ] 当前头验证、独立审查、PR required checks、受保护合并和 main-fresh 门禁通过。

## 范围

- Analysis Scheme PostgreSQL 写 Owner 与部署期发布服务。
- Internal V1 `configure` 入口和 Compose 既有启动依赖。
- 离线 Release backend 镜像 Prompt 身份校验与 manifest。
- 当前工作区 `content_labeling_v4.6.md` 内容调整。
- 对应单元/真实 PostgreSQL 集成、构建、Release 和文档证据。

## 非目标

- 不扫描文件名选择“最大版本”，继续以 `content_labeling_bootstrap.txt` 为唯一 Git 指针。
- 不新增标签枚举、输出字段、数据库 Schema/Migration 或依赖。
- 不改写已有 Analysis Run 或自动重打历史内容。
- 不自动覆盖管理员人工 active Version，不删除 Scheme 历史。
- 不执行 Release 发布、服务器部署、生产 Migration 或生产数据写入。

## 必须保持不变

- 数据库唯一 active Analysis Scheme Version 仍是运行时事实源。
- Run 创建时冻结配置，历史 Run 的可复现性不变。
- 管理员现有发布/回滚能力和 HTTP/OpenAPI/generated client 形状不变。
- V3/V4/V4.6 既有 Scheme 输出协议兼容路径不变。
- `migrate → configure → API/Worker/Scheduler` 启动顺序和 fail-closed 依赖保持。
- CI、Branch Protection、Review、Release/Deploy 门禁不降低。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 由 Analysis Scheme Owner 完成持久化；`configure` 只做编排，Release 只做产物身份验证 | E1-E4 | 不在入口脚本直接写业务表，不建立平行状态 |
| 接口与契约 | HTTP/API 不变；新增内部部署发布结果和 manifest 的加性 Prompt 身份字段 | E4 | 无 generated client 变化，旧 manifest 消费者需保持兼容 |
| 数据与迁移 | 复用既有 Scheme/Version/审计表，仅追加版本和移动 active 指针 | E1-E2 | 无 Migration；发布事务必须原子且受锁 |
| 错误与失败语义 | 人工 active 冲突或源码/镜像身份不一致时非零失败，不降级使用旧 Prompt | #667 / AC3、AC6 | API/Worker/Scheduler 不得在不确定状态启动 |
| 兼容性 | 只有系统管理 active 可自动提升；历史 Run、人工 active 与管理员操作保持 | #667 / AC1-AC4、AC7 | 避免部署覆盖人工业务决定 |
| 部署与回滚 | 部署自动执行；回滚镜像不会改写旧 Run，Scheme 可由管理员显式回滚 | #667 风险/回滚 | 回滚仍保留版本与审计历史 |

# 修改方案与决策依据

## 最小充分方案

1. **建立部署期 Scheme 发布动作**
   → 在 Analysis Scheme PostgreSQL Owner 内复用 advisory transaction lock，比较当前 Git definition/compiled Prompt 与 active 身份；系统 active 不同则追加并激活，完全一致则 no-op，人工 active 则在写入前报错。
   → 用真实 PostgreSQL 覆盖创建、幂等、人工冲突、并发以及旧/新 Run 冻结边界。

2. **接入 `configure` 与审计输出**
   → 通过 Analysis bootstrap/application service 组装发布与系统审计，`internal_v1_configure_main.py` 输出不含 Prompt 正文的结构化身份；异常保持非零退出。
   → 用入口单测和 Compose 配置检查验证 fail-closed 接线。

3. **证明实际 backend 镜像内容**
   → Release 构建运行 backend 镜像内安装包读取 Prompt 身份，与源码身份比较后写入 manifest；比较失败中止构建。
   → 用 Release 单测与实际本地离线构建/校验覆盖成功和不一致路径。

4. **纳入并验证 V4.6 Prompt 调整**
   → 将用户当前工作区文件复制到任务分支，检查外层围栏、解析结果、固定输出协议与行业相关性规则；不改动显式 bootstrap 指针。
   → 用 Prompt/Taxonomy/Analysis 回归和最终镜像 Hash 证明实际内容。

5. **同步长期文档并完成交付**
   → 更新 Analysis、技术决定、部署与本地 Release 指南；通过完成审计、独立审查、current-head CI、受保护合并和 main-fresh 验证。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 分离首次 bootstrap 与部署发布 | E2 | 两者的安全前提不同，分离后不会放宽页面访问触发的 bootstrap 行为 |
| D2 只自动提升系统 active | E1、#667/AC3 | 自动化必须尊重管理员已发布的业务规则，冲突应显式处理 |
| D3 在 `configure` 执行 | E3 | 它已经是所有业务进程启动前的一次性门禁，可在失败时阻止旧 Prompt 静默运行 |
| D4 从实际镜像读取身份 | E4 | 仅检查源码不能证明 wheel/镜像打包内容，实际产物才是部署输入 |
| D5 Prompt 协议不因同名文件内容变更而复制平行枚举 | E5 | Scheme 的 Prompt/Taxonomy Hash 已承担精确内容身份，协议继续表达固定输出协议 |

## 备选方案与取舍

- **每次部署无条件新建 Version**：会让相同镜像重启制造重复历史，破坏幂等，未采用。
- **无条件覆盖任何 active Version**：会静默覆盖管理员决策，风险不可接受，未采用。
- **继续人工在管理员页面发布**：不能满足自动使用镜像 Prompt 的目标，且无法形成 Release 产物身份链，未采用。
- **运行时绕过数据库直接读 Markdown**：会破坏唯一 active Scheme 与 Run 冻结设计，未采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 系统 active 不同时在部署期原子追加并激活，历史 Run 不阻塞 | #667 / AC1 | not_satisfied | 待实现与验证 |
| R2 | 相同身份重复部署保持幂等 | #667 / AC2 | not_satisfied | 待实现与验证 |
| R3 | 人工 active 冲突时失败且不改写 Scheme/审计 | #667 / AC3 | not_satisfied | 待实现与验证 |
| R4 | 旧 Run 保留旧快照，新 Run 冻结新 active | #667 / AC4 | not_satisfied | 待实现与验证 |
| R5 | `configure` 输出完整身份，提升写安全审计 | #667 / AC5 | not_satisfied | 待实现与验证 |
| R6 | Release 验证实际镜像 Prompt 并记录 manifest | #667 / AC6 | not_satisfied | 待实现与验证 |
| R7 | 空库、管理员操作、历史与公共 Contract 保持兼容 | #667 / AC7 | not_satisfied | 待实现与验证 |
| R8 | 完成目标/集成/构建、审查、CI 与 main-fresh 门禁 | #667 / AC8 | not_satisfied | 待实现与验证 |
| R9 | 当前工作区 V4.6 内容进入镜像且解析/协议/Hash 一致 | #667 / AC9 | not_satisfied | 待复制、检查并验证 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `analysis_schemes.py`、Analysis bootstrap/application service | 新增系统 Git Prompt 部署发布与结果模型 | 原子持久化、身份判定、人工冲突 | R1-R5、R7 |
| `internal_v1_configure_main.py` | 接入发布并输出结构化结果 | 在业务进程前 fail closed | R1-R5 |
| `release_bundle.py` | 读取并比较 backend 镜像 Prompt，写 manifest | 证明实际部署产物 | R6、R9 |
| `content_labeling_v4.6.md` | 纳入用户现有行业相关性调整 | 让本次镜像实际包含用户要求的 Prompt | R9 |
| Analysis/Release/Configure tests | 建立失败回归与真实边界验证 | 锁定并发、幂等、快照和产物身份 | R1-R9 |
| Analysis/Blueprint/Operations/Guide 文档 | 同步新的持续部署规则和排障/回滚 | 避免继续按首次 bootstrap 解释服务器行为 | R5-R9 |

执行过程中保持最小闭环：

- [x] 调查当前实现和事实源，建立 Requirement Source #667
- [x] 建立与风险相称的任务路由和验证矩阵
- [ ] 行为变化建立失败证据
- [ ] 完成最小实现，不静默扩大范围
- [ ] 同步受影响的长期文档
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和独立复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 发布决策、人工身份判定、入口输出、镜像身份解析、V4.6 Prompt 规则 |
| 接口 / 契约 | required | `configure` 退出/输出、release manifest 加性字段、HTTP/OpenAPI/generated client 无漂移 |
| 集成 / 持久化 / 运行依赖 | required | 真实 PostgreSQL 的受锁事务、并发幂等、审计、Run 快照 |
| 用户 / 工作流验收 | required | 本地 Release 构建后 Compose `configure` 自动使用镜像 Prompt；人工冲突给出明确操作错误 |
| 跨组件关键路径 | required | Prompt 指针 → wheel/backend 镜像 → manifest → configure → active Version → 新 Run |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 LLM/TikHub 外部协议；无需付费调用即可验证部署和 Scheme 语义 |
| 构建 / 打包 / 运行 | required | wheel、backend/frontend Docker、离线 bundle、checksum/no-build/no-pull 回放或等价正式验证 |
| 文档 / 治理 / 其他 | required | #667、Change、技术决定、Analysis/部署/Release 指南、独立审查与 current-head/main-fresh 证据 |

## 验证计划

- 目标测试：Analysis Scheme 部署发布、入口输出、Release 镜像身份、V4.6 Prompt 解析与规则。
- 相关回归：Analysis Scheme 管理/rollback、Run creation/freeze、Release manifest/checksum、Compose config/start order。
- 静态检查或构建：Ruff、mypy、wheel build、generated contract drift、受影响 CI。
- 专项真实边界：PostgreSQL 并发/事务；实际本地离线镜像构建与验证。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 错认人工作为系统版本、并发重复、镜像/源码身份漂移、外层 Prompt 围栏进入模型正文 | 明确 created_by 白名单、事务 advisory lock、镜像内读取/比较、Prompt 回归 |
| 兼容性 | 公共 API/Schema 不变；系统 active 部署语义改变，人工 active 保持优先 | #667 AC1-AC7 与 E1-E5 |
| 数据 / Migration | 无 Schema/Migration；只追加 Scheme Version、切 active 并写审计 | 使用既有 Owner 和表结构，真实 PostgreSQL 验证 |
| 部署 / 运行 | `configure` 新增硬门禁；人工冲突会阻止业务进程启动 | fail closed 是用户确认的安全语义，文档提供诊断/恢复步骤 |
| 回滚 / 恢复 | 回滚镜像不会改写旧 Run；管理员可显式回滚 Scheme，系统版本保留审计历史 | 现有版本化/rollback 能力与部署顺序 |

# 文档、依赖、部署与发布影响

- **长期文档**：定向同步 AGENTS 长期规则、决策 P、Analysis README/Appendix、生产部署和本地 Release 指南。
- **依赖 / Runtime**：不新增、不升级依赖或 Python/Node/PostgreSQL/镜像版本。
- **配置 / Secret**：不新增环境变量或 Secret；输出/审计禁止包含 Prompt 正文和敏感数据。
- **部署 / Release**：Release manifest 增加 Prompt 身份；既有 Compose `configure` 自动执行发布，人工 active 冲突需要管理员先显式处理。
- **兼容 / 消费方通知**：管理员界面继续读取数据库 active Version；旧 manifest 消费者需要容忍加性字段，公共 API 消费方无需改动。

# 完成审计

- [ ] upstream_re_read：进入 Ready 前重新读取 #667、用户 Prompt 决定、项目长期规则和所有受影响机器事实。
- [ ] change_coverage：逐条比较 AC1-AC9 与实现、测试、文档，当前 Change 不作为自身需求全集。
- [ ] reverse_audit：执行 Prompt→镜像→manifest→configure→Scheme→Run 以及管理员 active→部署冲突的双向审计并复核验证矩阵。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零，延期或不适用均有正式依据。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 任务分支建立前 | #667 live body 与技术变更模板校验 | 通过 | 上游范围、风险与 AC1-AC9 已持久化 |

## 未验证内容与剩余风险

- 实现、测试、构建、独立审查、PR CI 与 main-fresh 尚未完成；当前 Change 仅处于 proposed。
- 生产服务器状态和实际部署不在本任务授权范围，不能用仓库验证冒充生产已切换。

## 交付状态

- 提交：待首个 Change 提交。
- 拉取请求：待创建早期 PR。
- CI：待执行。
- 合并：用户已授权；仅在 current-head required checks 与独立审查无阻塞问题后执行。
- Change 归档：合并后由仓库原生自动化归档并验证。
- 发布 / 部署：不执行；本任务只完成代码合并和发布能力验证。

## 备注

原始 `main` 工作区中的 Prompt 修改由用户持有；任务分支仅复制其内容，不覆盖、暂存或清理原工作区文件。
