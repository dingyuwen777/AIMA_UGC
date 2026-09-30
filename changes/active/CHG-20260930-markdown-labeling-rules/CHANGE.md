---
schema: coding-change/v1
id: CHG-20260930-markdown-labeling-rules
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

非目标：付费模型调用、生产数据迁移、Release、部署和生产环境写入。

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

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | changed-scope 后端 Unit/Contract/API 共 1694 passed、16 skipped；其中最新三分类 Prompt 的 Analysis + 单一事实 Contract 专项 193 passed；前端 36 files / 271 tests passed |
| 接口 / 契约 | required | OpenAPI 生成检查、兼容检查和 generated client 同步通过；完整 `tests/contracts` 专项 113 passed |
| 集成 / 持久化 / 运行依赖 | required | 最新三分类 Prompt 下隔离 PostgreSQL 内容集成 87 passed；隔离数据库已在前序验证达到 0075 head 且 `alembic check` 无操作 |
| 用户 / 工作流验收 | required | Playwright 171 passed；Markdown 导入、编译失败保留编辑状态、只读编译预览、保存和发布路径通过 |
| 跨组件关键路径 | required | 真实 Full-stack 动态改名核心用例 1 passed；旧 Run 身份不变，发布后保存/查询并回滚 |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 Provider 传输，无须付费探测；模型语义质量另需样本评估 |
| 构建 / 打包 / 运行 | required | Ruff format/check、mypy 414 files、前端 lint/typecheck/production build 通过；`frontend.py --prepare-only` 实际探测 Node 24.19.0 / npm 11.17.0；wheel 包含 Prompt 和编译器 |
| 文档 / 治理 / 其他 | required | docs/facts/architecture/table-owner/secret scan 通过；独立完整工作树 Review 的唯一 P2 已通过校准 #679 AC2 和本记录边界修复，限定 re-review 结论为 `NO_FINDINGS_WITHIN_SCOPE`；等待最终 Change checker |

# 风险、兼容性、迁移与回滚

新 Markdown 格式独立于内容修订号；旧发布快照不经新编译器重写。内部准入布尔字段仅新格式要求，不增加持久结果字段。Scheme JSONB 保存派生快照，不新增数据库列或 Migration。仅在隔离 PostgreSQL 验证，不操作生产。旧 Version 回滚复用冻结协议。

# 完成审计

- [x] upstream_re_read：重新核对用户六点要求及后续 `platform`、单条请求、动态实际值、删除统计用途，以及“合并全部本地修改”决定。
- [x] change_coverage：逐项核对 Markdown 编辑源、生成快照、管理流程、运行请求、保存/筛选和历史冻结证据。
- [x] reverse_audit：从文档反查模型请求、Validator、持久结果与筛选；从管理页反查后端编译、发布、Run 冻结与回滚。
- [x] unresolved_cleared：没有 `not_satisfied`；R6 只保留按时序必须在 Ready/merge 后取得的 required checks、guarded merge、main-fresh、原生归档与 Issue Closure，并明确由 PR / Actions / 仓库归档 / #679 Closure 持有。工作台正向率、报告正负向/真实用户专项汇总按用户决定不在本次重设计。

# 完成证据与状态

内容打标本地实现、最新三分类 Prompt 与前端启动器验证已完成。独立完整工作树 Review 仅发现 #679 AC2 曾把全文旧名称语义扫描写成自动门禁；已按用户保持当前编译器的决定，把自动失败关闭限定为定义表、组合引用和固定 JSON 示例，并明确自然语言正文/普通示例由维护者按联动要求同步。限定 re-review 已确认 finding 关闭，结论为 `NO_FINDINGS_WITHIN_SCOPE`。远程 current-head required checks、合并与 main-fresh 继续按交付时序收口。

最新 Prompt 生产编译结果：`content-labeling.v4.0`、协议 `content-labeling.tables.v1`、发声/情感/一级/二级数量 `3/4/9/39`、Prompt 逻辑 Hash `245d83f440f6e213a563df032b65dc5ff0c1aa0e77d6443e37bc18a86631dca8`、Taxonomy Hash `07fbdbf61ba0158ae50fc48cc1e31751543c3cb4ba51e0d3a1191408c442f95c`。本轮新鲜结果：Ruff format/check、mypy 414 files、changed-scope 后端 Unit/Contract/API 1694 passed / 16 skipped、OpenAPI generate/compat、前端 lint、36 files / 271 tests、production build、Playwright 171 passed、Secret scan 和 `frontend.py --prepare-only` 均通过；隔离 PostgreSQL 内容集成 87 passed。独立 Review 另以生产编译器恢复冻结快照，枚举 `5 × 8 × 2 = 80` 个主体、意图、准入组合并验证唯一覆盖，以 7 个代表性输出检查 Validator。真实 Full-stack 动态改名核心用例、wheel 打包、文档事实、架构与表 Owner 检查也已完成。首次本机全套测试因自动读取真实 Edge profile 启动 Playwright 并污染同进程事件循环；将测试进程的 `AIMA_EDGE_USER_DATA_DIR` 指向不存在的隔离路径后，同一 changed-scope 后端命令全部通过。Windows 下 `validate_changed.py` 直接启动裸 `npm` 因 `CreateProcess` 找不到扩展名而停止，已使用等价 `npm.cmd` 命令逐项取得完整前端结果；正式 Linux CI 仍会按仓库原命令重验。
