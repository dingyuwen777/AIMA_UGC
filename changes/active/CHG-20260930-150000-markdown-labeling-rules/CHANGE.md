---
schema: coding-change/v1
id: CHG-20260930-150000-markdown-labeling-rules
title: 可读 Markdown 作为内容打标规则唯一编辑入口
level: L3
status: ready_for_review
owner: assistant
branch: feature/markdown-labeling-rules
created: 2026-09-30 15:00:00 +08:00
updated: 2026-09-30
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - administration
  - frontend
  - testing
  - documentation
  - developer-tooling
affected_paths:
  - backend/src/aima_ugc/modules/analysis
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py
  - frontend/src/features/admin-configuration
  - tests
  - docs/appendix/07_AI舆情打标与分析实现.md
  - scripts/dev/frontend.py
  - scripts/dev/local_runtime.py
contracts:
  - Markdown 表格编译格式
  - Analysis Scheme Definition
  - 内部模型准入判定
data_changes:
  - Scheme definition JSONB 保存派生编译快照；无数据库 Schema 变更
---

# 变更摘要

现有解析器依赖旧标题、手工机器 JSON 和独立分类编辑，不能加载用户的新表格文档。把可读 Markdown 作为编辑源，生成不可编辑的分类、父子关系和发声组合快照，复用 Scheme 发布与 Run 冻结，并通过受保护 PR 流程交付全部本地修改。不执行部署或生产数据操作。

# 背景、现状与问题

当前新稿 Loader 报“必须且只能包含一个人类可读标签闭集”；代码发送 platform，文档未列出；严格真实用户准入与普通咨询保底发生冲突。已存在 Scheme 草稿、发布、回滚、Git lineage 刷新和 Run 快照，可复用。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 影响 |
| --- | --- | --- | --- |
| E1 | 新稿无法被旧 Loader 解析 | 本轮 PromptTaxonomyLoader.load 检查 | 需要统一编译入口 |
| E2 | 正式请求包含 platform，Worker 每次传一个 Content | content_labeling.py / analysis_concurrent_worker.py | 文档与请求保持一致 |
| E3 | 数据库保存完整 Scheme 与 Run 版本身份 | scheme_tables.py / schemes.py | 复用现有生命周期 |

# 目标、成功标准与非目标

- [x] Markdown 定义表是唯一编辑源，机器 JSON 无需手工维护。
- [x] 发声类型、情感和两级标签增删改通过同一版本应用，程序直接使用实际值。
- [x] 输入含 platform；完整 Prompt + 单条内容组成请求。
- [x] 严格真实用户与普通个人表达可区分，证据和组合规则校验一致。
- [x] 历史版本、运行中任务、管理员发布和回滚保持可追溯。
- [x] 前端依赖目录不完整时自动重装，不再误报“依赖已是最新”后找不到 Vite。

非目标：付费模型调用、生产数据迁移、Release、部署和生产环境写入。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 规则编辑源 | `content_labeling.md` 是唯一人工维护入口 | #679 / R1 | Taxonomy 与语义快照只能由 Markdown 编译生成 |
| 固定与可编辑边界 | 版本行、六张标记表、表头、内部值和条件语法固定；分类名称、定义与判断原则可编辑 | #679 / R1-R2 | 编译器稳定解析，业务维护者仍可调整实际分类和规则 |
| 动态分类消费 | 保存、查询、Excel/报告通用分类分布使用 Scheme 的实际字符串值 | #679 / R2-R4 | 不维护正负向、真实用户或其他统计含义映射 |
| 请求粒度 | 每条内容一个模型请求，system 为完整冻结 Prompt，user 为含 `platform` 的单条输入 | #679 / R3 | 保持正式高并发执行边界与版本可追溯性 |
| 历史兼容 | 新版使用派生快照；legacy v3.0 使用冻结定义恢复 | #679 / R4 | 历史 Version/Run 不由新编译器重新解释 |
| 交付 | 全部本地修改通过 PR required checks、精确 head 合并和 main-fresh 收口 | #679 / R6 | 不绕过 Ruleset，不把合并后证据提前写成完成 |

# 修改方案与决策依据

统一 Markdown 表格编译 → 完整模型文本与机器快照 → Scheme 草稿/发布 → Run 冻结 → Validator、保存和查询按版本消费实际分类值。

## 备选方案与取舍

保留结构化编辑器并导出 Markdown 可减少解析改动，但不能满足直接编辑文件的目标；手工维护 JSON 与正文会持续产生漂移。选择表格为编辑源，派生数据不可独立修改。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 可读表格、章节改名、版本仅开头、移除手工机器 JSON，并标明固定模板与可编辑规则 | #679#AC1 | satisfied | `content_labeling.md` 的维护边界说明及六张标记表；生产编译输出 3/4/9/39；`test_current_prompt_is_a_clean_markdown_source` |
| R2 | 修改分类与规则后能进入实际打标及消费者；定义表、组合引用和固定 JSON 示例按闭集失败关闭 | #679#AC2 | satisfied | 单元改名覆盖发声/情感/一二级标签；真实 Full-stack 发布后保存并按“消费者体验/积极”筛选成功；自然语言正文和普通示例按 Prompt/README 的联动要求由维护者同步，不宣称全文旧值语义扫描 |
| R3 | 保留 platform 与每条帖子完整提示词请求 | #679#AC3 | satisfied | Worker `label_one` + OpenAI system/user 组合；Fake LLM 强制一个含 platform 的 item；真实 Worker 记录 1 logical/1 HTTP request |
| R4 | 版本发布、历史冻结和回滚保持闭环，不维护分类含义映射 | #679#AC4 | satisfied | Markdown 编译快照/双 Hash/legacy 恢复测试；管理页保存发布回滚；残留扫描无统计用途或角色映射 |
| R5 | 前端启动器保留当前本地 npm 直接执行行为 | #679#AC6 | satisfied | `_npm_command` 直接返回 npm 命令及参数；Ruff 和本机锁定 Node/npm 版本探测通过后进入 Ready |
| R6 | 全部本地修改按受保护 PR 流程合并远程主分支 | #679#AC7 | explicitly_deferred | 本地实现与验证完成；commit 后的 PR current-head required checks、精确 head guarded merge、main-fresh、仓库原生 Change 归档与 Issue Closure 只能按交付时序取得，不作为 Ready 前的伪造证据，也不豁免任何门禁 |
| R7 | `node_modules` 不完整时自动重装并恢复 Vite 启动 | #679#AC8 | satisfied | 依赖状态额外验证当前平台的 `.bin/vite` 或 `.bin/vite.cmd`，缺失时进入 `npm ci`；平台运行时单元测试 12 passed / 1 skipped；同一启动命令已实际执行 Vite，当前 5173 页面返回 200 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 |
| --- | --- | --- | --- |
| `prompts/content_labeling.md` / `markdown_prompt.py` | 建立六表 Markdown 编辑源、编译器、闭集与组合校验 | 消除手工 Taxonomy JSON 和正文双写 | R1-R3 |
| `prompt_taxonomy.py` / `schemes.py` / `content_labeling.py` | 编译并冻结快照，恢复历史 Version，校验准入与发声组合 | 让实际打标、保存与查询使用同一 Scheme | R2-R4 |
| Administration Contract / OpenAPI / generated client / Scheme Panel | 支持 Markdown 导入、编辑、预览、保存、发布和回滚 | 给管理员提供同一编辑入口 | R2/R4 |
| Analysis 测试、PostgreSQL Integration、Fake LLM、Playwright / Full-stack | 覆盖编译、动态改名、历史冻结、单条请求与 UI 工作流 | 直接验证跨组件闭环 | R1-R4 |
| `scripts/dev/frontend.py` / `scripts/dev/local_runtime.py` / 平台运行时单元测试 | Windows 直接执行解析出的 `npm.CMD`；识别缺少 `.bin/vite` 的不完整依赖安装并自动运行 `npm ci` | 纳入用户要求交付的现有本地修改，并修复“依赖已是最新”误判后找不到 Vite | R5/R7 |
| Analysis README、Appendix、Blueprint、项目规则与 Change | 同步当前事实、维护边界和交付证据 | 防止文档恢复第二套事实 | R1-R6 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | changed-scope 后端 Unit/Contract/API 共 1694 passed、16 skipped；其中最新三分类 Prompt 的 Analysis + 单一事实 Contract 专项 193 passed；前端 36 files / 271 tests passed |
| 接口 / 契约 | required | OpenAPI 生成检查、兼容检查和 generated client 同步通过；完整 `tests/contracts` 专项 113 passed |
| 集成 / 持久化 / 运行依赖 | required | 最新三分类 Prompt 下隔离 PostgreSQL 内容集成 87 passed；隔离数据库已在前序验证达到 0075 head 且 `alembic check` 无操作 |
| 用户 / 工作流验收 | required | Playwright 171 passed；Markdown 导入、编译失败保留编辑状态、只读编译预览、保存和发布路径通过 |
| 跨组件关键路径 | required | 真实 Full-stack 动态改名核心用例 1 passed；旧 Run 身份不变，发布后保存/查询并回滚 |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 Provider 传输，无须付费探测；模型语义质量另需样本评估 |
| 构建 / 打包 / 运行 | required | Ruff format/check、mypy 414 files、前端 lint/typecheck/production build 通过；`frontend.py --prepare-only` 实际探测 Node 24.19.0 / npm 11.17.0；平台运行时单元测试 12 passed / 1 skipped；同一用户命令已进入 Vite，现有 5173 服务返回 200 且页面包含 Vite client；wheel 包含 Prompt 和编译器 |
| 文档 / 治理 / 其他 | required | docs/facts/architecture/table-owner/secret scan 通过；独立完整工作树 Review 的唯一 P2 已通过校准 #679 AC2 和本记录边界修复，限定 re-review 结论为 `NO_FINDINGS_WITHIN_SCOPE`；等待最终 Change checker |

# 风险、兼容性、迁移与回滚

新 Markdown 格式独立于内容修订号；旧发布快照不经新编译器重写。内部准入布尔字段仅新格式要求，不增加持久结果字段。Scheme JSONB 保存派生快照，不新增数据库列或 Migration。仅在隔离 PostgreSQL 验证，不操作生产。旧 Version 回滚复用冻结协议。

# 文档、依赖、部署与发布影响

- **文档**：同步项目 Contract 基线、Analysis README、AI 打标实现专题和技术决策，明确 Markdown 固定模板、可编辑规则、动态分类及历史冻结边界。
- **依赖 / Runtime**：不新增或升级 Python、Node、npm、前端或后端依赖；继续使用仓库锁定版本。
- **Contract / 数据**：Administration Request、OpenAPI 和 generated client 增加可选编译快照表达；不新增数据库表、列或 Migration。
- **部署 / Release**：本 PR 只交付代码与文档，不执行 Release、Deploy、生产 Scheme 更新或重新打标；上线仍走既有 Analysis Scheme 与 Release 运维边界。
- **回滚**：代码可回滚 PR merge；已发布 Scheme 继续使用现有版本回滚能力，历史 Run 保持冻结。

# 完成审计

- [x] upstream_re_read：重新核对用户六点要求及后续 `platform`、单条请求、动态实际值、删除统计用途，以及“合并全部本地修改”决定。
- [x] change_coverage：逐项核对 Markdown 编辑源、生成快照、管理流程、运行请求、保存/筛选和历史冻结证据。
- [x] reverse_audit：从文档反查模型请求、Validator、持久结果与筛选；从管理页反查后端编译、发布、Run 冻结与回滚。
- [x] unresolved_cleared：没有 `not_satisfied`；R6 只保留按时序必须在 Ready/merge 后取得的 required checks、guarded merge、main-fresh、原生归档与 Issue Closure，并明确由 PR / Actions / 仓库归档 / #679 Closure 持有。工作台正向率、报告正负向/真实用户专项汇总按用户决定不在本次重设计。

# 完成证据与状态

内容打标本地实现、最新三分类 Prompt 与前端启动器验证已完成。前端启动失败的根因是 `node_modules` 目录存在但 `.bin/vite` 和 npm 安装元数据缺失，旧检查只比较目录与锁文件哈希而误判为依赖完整；当前检查会把该状态判为 stale 并自动执行 `npm ci`。独立完整工作树 Review 仅发现 #679 AC2 曾把全文旧名称语义扫描写成自动门禁；已按用户保持当前编译器的决定，把自动失败关闭限定为定义表、组合引用和固定 JSON 示例，并明确自然语言正文/普通示例由维护者按联动要求同步。限定 re-review 已确认 finding 关闭，结论为 `NO_FINDINGS_WITHIN_SCOPE`。远程 current-head required checks、合并与 main-fresh 继续按交付时序收口。

最新 Prompt 生产编译结果：`content-labeling.v4.0`、协议 `content-labeling.tables.v1`、发声/情感/一级/二级数量 `3/4/9/39`、Prompt 逻辑 Hash `245d83f440f6e213a563df032b65dc5ff0c1aa0e77d6443e37bc18a86631dca8`、Taxonomy Hash `07fbdbf61ba0158ae50fc48cc1e31751543c3cb4ba51e0d3a1191408c442f95c`。本轮新鲜结果：Ruff format/check、mypy 414 files、changed-scope 后端 Unit/Contract/API 1694 passed / 16 skipped、OpenAPI generate/compat、前端 lint、36 files / 271 tests、production build、Playwright 171 passed、Secret scan 和 `frontend.py --prepare-only` 均通过；隔离 PostgreSQL 内容集成 87 passed。独立 Review 另以生产编译器恢复冻结快照，枚举 `5 × 8 × 2 = 80` 个主体、意图、准入组合并验证唯一覆盖，以 7 个代表性输出检查 Validator。真实 Full-stack 动态改名核心用例、wheel 打包、文档事实、架构与表 Owner 检查也已完成。首次本机全套测试因自动读取真实 Edge profile 启动 Playwright 并污染同进程事件循环；将测试进程的 `AIMA_EDGE_USER_DATA_DIR` 指向不存在的隔离路径后，同一 changed-scope 后端命令全部通过。Windows 下 `validate_changed.py` 直接启动裸 `npm` 因 `CreateProcess` 找不到扩展名而停止，已使用等价 `npm.cmd` 命令逐项取得完整前端结果；正式 Linux CI 仍会按仓库原命令重验。

启动器故障修复后的新鲜证据：平台运行时单元测试 12 passed / 1 skipped；用户的同一 `uv run python scripts/dev/frontend.py` 命令已成功调用 `vite`，随后只因 5173 已有服务而退出；现有页面实测 HTTP 200 且包含 `/@vite/client`。

最终 Full-stack CI `36710290673` 的 Markdown 动态改名链通过，但历史导入后重复分析的旧用例失败：Fake LLM 适配动态闭集时一直返回首个情感值，破坏了该用例验证“第二次结果更新为负面”的既有响应序列。保留原浏览器断言，修复 Fake 按当前冻结情感表第 1/3 行交替响应；这是验收 Fixture 的确定性序列，不是生产分类含义映射。新增正式 HTTP Handler 回归覆盖原名称和改名后值，两种情况均先取得正确 Red（连续两次返回首值），修复后 3 passed，所有返回继续通过生产 Validator。Ruff format/check 通过；完整 Full-stack 与 current-head required CI 在修复提交后重验。
