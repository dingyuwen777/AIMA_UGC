---
schema: coding-change/v1
id: CHG-20261002-100000-date-supplement
title: 统一日期与显式内容补采及弹窗
level: L3
status: ready_for_review
owner: Codex
branch: feature/date-supplement
created: 2026-10-02
updated: 2026-10-02
completion_gate: required
depends_on: []
affected_areas:
  - "collection"
  - "frontend"
affected_paths:
  - "backend/src/aima_ugc"
  - "frontend/src/features/import-batches"
  - "frontend/src/features/voice-plaza"
  - "frontend/src/features/collection-supplement"
  - "tests"
  - "contracts"
  - "docs"
contracts:
  - "http"
  - "generated-client"
data_changes: []
---

# 变更摘要

Requirement-Source: #690

用户最新批准方案将日期和声音广场勾选帖子统一为 content_supplement。复用本分支已经实现的日期弹窗、身份判断和冻结 Scope，增加 selected 入口、Preview count/fingerprint 校验、全来源补采状态和页面自动刷新。Requirement Source #690 已按最新决定更新，旧 AC1–AC6 保留对应目标并增加 AC7–AC11。

# 背景、现状与问题

原系统将补采绑定导入 Batch/Campaign，Worker 与详情状态查询也依赖该来源。最新方案要求日期和声音广场显式选择共用内容补采；日期只是创建时查询，执行必须消费冻结 Content Scope，显式选择不能被 AI 状态静默剔除。预览与确认之间的目标变化也必须阻止无确认的额外采集。

# 事实与证据

| 编号 | 事实 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | 最新批准方案统一为 content_supplement，日期与 selected 是互斥选择 | 引用会话最新方案与 live #690 AC1–AC11 | 两个入口共用 Contract/Preview/创建/执行 |
| E2 | 已有身份校验、评论链路与持久 Scope 能承载新来源 | collection_targets.py、collection_scope.py 与 117 项 PostgreSQL 回归 | 不复制 Provider 或 Mapper |
| E3 | 共享北京时间日历与 Modal 已存在 | beijingTime.ts、AimaDateRange、AimaModalContainer；浏览器截图 | 复用时间和弹窗机制 |
| E4 | 原大范围 INSERT / IN 会超过 PostgreSQL 65,535 个参数 | 万条 Scope 和七万候选 Red/Green；容量 JSON | 自动分批插入与 UUID 数组，保持原子事务 |

# 目标、成功标准与非目标

目标与验收以 live #690 AC1–AC11 和用户批准的最新《按日期补采方案》为上游；非目标是依赖升级、新 Provider family、预算、生产操作及无依据的日期天数/条数限制。显式 selected 沿用现有 1～1000 条请求边界，保持旧模式和历史任务兼容。

# 约束与意图决策

新增统一模式及 POST Preview；采用带时区的北京时间闭区间。已有 Content、Scope、Job 和 JSON 快照可以承载新行为，不新增 Schema/Migration。新任务部署需要 API、Worker、Frontend 同版本，回滚前暂停并结清日期任务，旧 Worker 不能处理新模式。

# 修改方案与决策依据

1. 统一 selected/date Contract 与 POST Preview → 真实数量、身份诊断、稳定指纹 → Contract/Target Reader/API 测试。
2. Confirm 事务内核验并冻结 → 409 不写任务、显式目标不重筛 AI、平台不遗漏 → PostgreSQL/共享 Worker/状态回归。
3. 共享补采选项及两个弹窗 → 日期入口、声音广场评论固定开启、轮询终态自动刷新 → 组件、浏览器、两个全栈关键路径。
4. 正式生成、文档、容量、Completion、Review、current-head CI → guarded merge → main-fresh/原生归档/Closure/清理。

## 备选方案与取舍

只改表单不能让现有 Worker 执行无导入来源的 Run；运行时再次日期查询会让目标漂移。采用创建时 Content Scope 冻结、执行时按 ID 恢复。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 北京时间日期闭区间、全来源、NULL/当前不相关排除及共享身份 | #690 / AC1 | satisfied | Target Reader；日期 PostgreSQL 边界、五平台、直接/解析/阻塞测试 |
| R2 | 互斥选择、原子冻结 v3/Scope/Job 与历史兼容 | #690 / AC2 | satisfied | Contract/API；Content/Date/Repository 测试，万条 Scope 与末批整体回滚 |
| R3 | 冻结执行及完整详情/评论/回复、恢复/fencing/去重 | #690 / AC3 | satisfied | collection_scope.py；三模式共享 Worker 回归与两个全栈流程 |
| R4 | 日期居中弹窗及加载/空/错误/竞态/重开/平台收敛 | #690 / AC4 | satisfied | TikHubSupplementDialog；共享组件单元、collection-runtime 浏览器与实链截图 |
| R5 | 统一运行投影、名称/详情/任务中心及生成 Client | #690 / AC5 | satisfied | Runtime Query/Cursor/UI/任务中心；正式生成、兼容检查与全栈详情 |
| R6 | 分层验证、容量、正式说明、Review 与正式交付门禁 | #690 / AC6 | satisfied | evidence/validation.md、capacity.json；本地两阶段复核完成；PR current-head CI、guarded merge、main-fresh/原生归档/Closure 是随后平台门禁，Issue AC6 在收尾前保持未勾选 |
| R7 | 显式 1～1000 UUID 去重、保留不相关、缺失/能力/平台不静默漏掉 | #690 / AC7 | satisfied | Selected Contract/PG；缺失 404、遗漏平台拒绝、阻塞 Scope 保留、零外部发送测试 |
| R8 | Preview count/fingerprint 与 Confirm 409 零写入、重预览后再次确认 | #690 / AC8 | satisfied | 同数量换 ID/选项变化 PG；HTTP 独立错误码；共享前端 409 手动重确认测试 |
| R9 | 声音广场按钮顺序/样式/禁用、固定评论及默认回复、共享逻辑 | #690 / AC9 | satisfied | VoicePlazaPage、CommentSupplementDialog、collection-supplement；selected 全栈 |
| R10 | 全来源 Scope 状态、终态刷新列表/详情/评论、筛选和退出清理 | #690 / AC10 | satisfied | content_queries.py；Voice Store 四种终态及迟到响应测试；全栈无需手动刷新 |
| R11 | Shell LF 保持正文且无新增 CI/部署文档/流程 | #690 / AC11 | satisfied | .gitattributes 与两个现有 .sh 的索引/工作树逐字节核验 |

# 计划改动

Collection Contract/HTTP/Target Reader/Scope/Runtime Query；collection-runtime UI/Store/API/详情；generated client；相关测试；Blueprint §25 与当前产品说明。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 输入与资格竞态、空/错误/重开、评论层级 |
| 接口 / 契约 | required | 日期/Selected 合法性、Preview/409、旧模式、生成检查 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 日期边界、身份诊断、冻结、Worker |
| 用户 / 工作流验收 | required | 新建弹窗、运行中心及详情 |
| 跨组件关键路径 | required | 页面→API→PostgreSQL→Worker→结果 |
| 外部依赖 / 供应方探测 | not_applicable | Provider endpoint/mapper 不变；使用现有 Fake，无需付费 Probe |
| 构建 / 打包 / 运行 | required | 前端构建、后端静态检查、changed preflight |
| 文档 / 治理 / 其他 | required | 当前文档、Change、Completion、Review、CI |

# 风险、兼容性、迁移与回滚

主要风险是日期边界、执行漂移、身份缺口和请求竞态。测试只使用隔离数据库。无依赖、配置、Secret 或 Migration 变更；旧运行快照 v2 保留，新内容补采任务 v3。发布和回滚须 API/Worker/Frontend 协调。

# 文档、依赖、部署与发布影响

Docs Impact: targeted。同步统一补采行为的正式说明；不改受管治理资产。用户本轮授权验证后合并 main 和完整收尾，未授权 Release、Deploy 或生产操作。

# 完成审计

- [x] upstream_re_read：2026-10-02 重新读取引用会话最新统一方案、本轮取消新建批次入口的明确决定及 live #690 AC1–AC11，独立重建完成定义。
- [x] change_coverage：日期/显式选择、预览校验、原子冻结、Worker、两个弹窗、运行和 Scope 状态、自动刷新、生成、兼容、容量、Shell 与说明逐条映射。
- [x] reverse_audit：从后端日期/Selected/Preview/创建/Run/Scope/结果检查前端入口和状态；从日期、勾选、平台、评论/回复、409 和终态刷新反查正式 API/Worker；两条真实全栈读取详情与新评论，未选目标无请求。
- [x] unresolved_cleared：本地阻塞清零。修正大 SQL 参数量、日期控件中间态导致平台丢失、Selected 打开竞态、partial_success 终态遗漏、重新启动轮询清空刚创建任务及过时源码断言；正式平台合入/归档/Closure 继续使用 live 状态。

Validation Asset Redundancy: clean。复用三模式共享 Worker 参数化测试。Contract、前端竞态、浏览器用户状态、PostgreSQL 持久边界、实链与容量分别承担不同证明，不复制 Provider、分页或 Mapper。

两阶段本地复核：第一阶段重建上游→Change→实现/测试/文档覆盖；第二阶段检查身份、日期/AI 冻结、事务、409、Capability、全量评论、Raw 恢复/fencing、轮询生命周期、兼容及 Secret。修正后范围内未发现阻塞项；本地自查不等于 GitHub 外部审批。

# 完成证据与状态

最初日期 Contract Red 为 1 failed / 10 passed，原 Contract 拒绝新增模式。后续统一 Selected/Preview 与生命周期回归证明并修正实际失败路径，最终结果和环境见 [evidence/validation.md](evidence/validation.md)。正式 CI 以 PR #691 当前 head 为准；在本记录提交时尚未 merge、归档、关闭 Issue 或部署。直接在用户指定目录开发，不保留独立 worktree。
