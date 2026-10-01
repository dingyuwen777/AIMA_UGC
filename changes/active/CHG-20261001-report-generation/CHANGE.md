---
schema: coding-change/v1
id: CHG-20261001-report-generation
title: 数据库驱动报告生成与独立飞书发布
level: L3
status: ready_for_review
owner: Codex
branch: feature/report-generation
created: 2026-10-01
updated: 2026-10-01
completion_gate: required
depends_on: []
affected_areas:
  - reporting
  - administration
  - storage
  - analysis
affected_paths:
  - backend/src/aima_ugc
  - frontend/src/features/admin-configuration
  - frontend/src/generated
  - frontend/e2e
  - migrations
  - tests
  - docs
  - contracts/openapi
  - AGENTS.md
contracts:
  - reports HTTP API
  - reporting generation/publication Job v1
data_changes:
  - report runs
  - immutable report datasets
  - report artifact links
---

# 变更摘要

数据库直接形成冻结报告数据，复用现有统计、Markdown、DOCX、Excel 图表与飞书发布实现。管理员选择品牌、车型、日期，查看预检、生成进度及历史，下载文件或独立重试飞书发布。

# 背景、现状与问题

当前管理页上传本期与上期 Excel 后生成并发布；统一导出只冻结 Content 版本，读取时仍使用当前指标、评论及分析结果。正式报告需要冻结全部生成依据，而发布失败不能迫使重跑模型。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 统计、Word、可编辑图表及飞书发布已有正式实现 | platform/reporting；bootstrap/feishu_report_publication.py | 复用生产实现 |
| E2 | Job 提供 lease/fence/deadline/retry/cancel；Artifact 有到期清理 | platform/jobs；bootstrap/artifact_cleanup.py | 不创建平行运行系统 |
| E3 | 当前目录与正在运行的服务目录分离 | 当前工作目录 E:/Desktop/AIMA_UGC；运行服务 E:/work/03_Aima/code/AIMA_UGC | 直接修改当前目录，测试隔离 |

## 推断与待确认

本轮未调用付费模型或写真实飞书；使用可控 HTTP 传输、生产 Adapter 与真实 PostgreSQL 验证。真实账户权限、模型额度和远端实际响应仍需在线验收，不能由本地测试证明。

旧报告按 Excel 的“命中关键词”计数，离线导入词包匹配与 Provider Probe 搜索上下文并非同一来源。用户本轮已明确决定“采用数据库已保存的品牌、车型命中证据”。正式报告已复用按 Content Version 读取的有效 Brand/Vehicle 投影，使用标准名称（车型沿用现有合并目录映射），每条内容内去重后计数；不重扫正文或读取当前采集词包。本期和上期的关键词、名称及口径说明一并冻结，专项与完整工作流证据已取得。

# 目标、成功标准与非目标

成功标准与需求追溯逐条对应。范围为报告数据、任务、接口、管理员页面、产物与生命周期、必要日志及文档。非目标为依赖升级、生产部署和运行数据库迁移。当前远程交付授权已由 Issue #684 接管；原仅本地边界作为已完成里程碑保留。既有离线报告入口保持兼容。

# 约束与意图决策

ReportRun 保存品牌/车型/本期与相邻等长上期范围、安全 Provider 配置、Scheme 与 Prompt/Taxonomy 身份；完整数据一次性在一致读事务中冻结。报告下载与发布状态独立。默认保留 60 天，复用既有 Scheduler Artifact 清理。当前目录本地任务分支，不操作运行目录/容器。通用规则来自本轮 canonical Source 041c9b60aae0f566553002794eb5fde4ed614c7f。

# 修改方案与决策依据

1. 增加 ReportRun、快照数据、Artifact 关联及 Contract/Migration → 真实 PostgreSQL 验证品牌车型隔离、原子 enqueue、冻结。
2. 共用现有统计与渲染入口，直接消费 Dataset；选择/建议使用冻结管理员 Provider → 统计一致性、模型输入和失败恢复测试。
3. durable 生成及发布任务分离，fence 验证业务提交，下载校验所属与期限 → 取消、重试、部分失败、越权测试。
4. 管理员页面改为目录与日期输入、预检、历史和操作 → 组件验收、生成 Client/build、真实跨组件路径。
5. 同步正式文档并复核完成定义 → 项目质量检查及独立 Review。

6. 补齐已批准的关键词口径 → `report_runs.py` 在当前/上期冻结数据中保存品牌和车型标准名称的去重并集；`report_runs_http.py` 冻结口径说明及报告模板，Worker 把同一说明写入数据 Excel 属性。真实 PostgreSQL 验证有效/无效及跨版本证据、重复命中、创建后目录改名或证据变化，并重新解析下载的 Markdown、DOCX 与 Excel。

## 备选方案与取舍

继续以临时 Excel 为中间输入会保留第二层事实和重复读取；新增独立队列或文件元数据会绕过已有 Owner，因此不采用。

# 需求追溯

当前团队可访问的上游 Owner 为 [Issue #684](https://github.com/dingyuwen777/AIMA_UGC/issues/684)，其 AC1–AC7 保持原报告完成定义，AC8 记录新增的分批远程交付与合并后收尾。原引用会话及当前用户决定继续作为 Issue 的上游依据。AC1–AC7是对这些已批准要求的稳定定位编号，依次对应数据、快照、产物、发布、AI、前端与本地运行约束；编号不代表新增需求或新增用户决定。

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 数据库直接生成，品牌车型日期过滤，保持统计与上期比较；关键词按已保存品牌/车型命中证据 | #684 / AC1 | satisfied | tests/integration/reporting/test_database_reports.py 验证有效标准名称、重复来源去重、无效证据排除、本期/上期冻结，以及目录改名/证据停用后下载的计数、分母、Excel字段和口径说明不变；完整工作流22项通过 |
| R2 | 冻结 Content/Version/评论/指标/分析身份及 Provider | #684 / AC2 | satisfied | tests/integration/reporting/test_database_reports.py：创建后改变实时数据仍使用冻结输入；正式 Contract/历史页显示当前选择模型与实际分析身份；仅报告引用的 Provider 禁止删除 |
| R3 | DOCX/XLSX/Markdown/图表保存并下载，默认可配置60天清理 | #684 / AC3 | satisfied | 同一 PostgreSQL 工作流下载并重新解析 DOCX ZIP/Office 图表、统一数据 Excel；61 天到期返回410并清理；中途文件失败的一天孤儿窗口与已关联完整文件互斥；Word属性标题跟随实际品牌标题，特殊字符与旧入口兼容有独立复现和回归证据 |
| R4 | 独立发布 Word、Excel 图表及多维表；重试不重跑模型 | #684 / AC4 | satisfied | tests/unit/platform/test_report_publication_guards.py：生产 Publisher/外表/内嵌表 Adapter + MockTransport 验证上传、三 Client 守卫、读回错误；PG 工作流验证持久发布重试、文件仍可下载且 LLM 调用不增加；真实飞书在线验收未执行 |
| R5 | 管理员 Provider、模型可追溯，粉丝和互动参与代表性选择，失败不产出错误案例 | #684 / AC5 | satisfied | tests/unit/analysis/test_report_selection.py；PG 工作流验证冻结当前粉丝数与管理员配置、严格模型输出及断点复用；前端生成依据显示配置修订和规则摘要 |
| R6 | 预检、进度、历史、取消/重试、下载与飞书链接 | #684 / AC6 | satisfied | frontend/e2e/admin-configuration-release2.spec.ts：迟到历史 GET 不覆盖创建，503 后继续轮询、生成下载、发布失败独立恢复；真实浏览器连接正式 API/Worker 下载 Word；tests/api/test_database_reports.py 验证8个入口权限 |
| R7 | 必要安全日志、有界计划重试及超时取消；本地实施与隔离测试不影响运行服务和容器 | #684 / AC7 | satisfied | PG 工作流分别覆盖503、ReadTimeout、连续429有界耗尽、取消 fence、已成功步骤复用；HTTP120秒上限与单次Job1800秒；安全日志/Secret扫描；测试专用库55437和独立端口，运行目录与原容器未操作 |

# 计划改动

| 文件 / 模块 / 资产 | 改动及目的 | 对应要求 |
| --- | --- | --- |
| reporting 模块、PostgreSQL Repository、报告 HTTP/Worker、Migration、生成 Contract 和管理员页面 | 数据冻结、生成下载、独立发布及可追溯历史；实际文件见本 Change 的 LOCAL_VALIDATION | R1–R7 |
| scripts/quality/classify_ci_scope.py、.github/workflows/ci.yml、报告 PG fixture 与测试 | 报告持久化工作流纳入现有 CI，并保持破坏性 fixture 的隔离保护 | R1–R7；Issue AC8 的合并前证据责任 |
| docs/blueprint/07_技术决策与实施门禁.md | 同步两种报告入口及 Renderer 的事实边界 | R1、R4 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 统计、输入、重试、管理页面 |
| 接口 / 契约 | required | OpenAPI/Schema/生成 Client |
| 集成 / 持久化 / 运行依赖 | required | 独立 PostgreSQL18、迁移、事务、fence、Artifact |
| 用户 / 工作流验收 | required | 预检→创建→生成→下载→发布恢复 |
| 跨组件关键路径 | required | 生产装配及可控 LLM/飞书 |
| 外部依赖 / 供应方探测 | not_applicable | 用户限定本地；不写真实飞书、不调用付费模型 |
| 构建 / 打包 / 运行 | required | 前端构建及后端静态检查 |
| 文档 / 治理 / 其他 | required | 正式文档、Owner、Secret、Change 检查 |

# 风险、兼容性、迁移与回滚

新增报告专属表，升级仅在独立测试数据库执行。旧接口与离线入口兼容。回滚需先停止新增报告任务、导出需要保留的报告，再撤销新表；本次不部署。未知网络结果不承诺飞书零重复，复用已有持久 checkpoint 对账。

# 文档、依赖、部署与发布影响

同步报告模块、报告 Appendix 和 API/运行导航；不升级依赖。新增保留天数配置；Secret 只存引用。线上部署和迁移由后续授权完成。

# 完成审计

- [x] upstream_re_read：重新读取会话最终方案、本轮仅本地要求、直接修改当前文件夹的更正，以及本轮明确采用数据库已保存品牌/车型命中证据的决定；历史聊天只作为用户需求源，当前实现以机器事实核验。
- [x] change_coverage：逐条核对上游报告输入、数据冻结、统计分层、输出、发布、模型选择、管理页与生命周期；R1关键词按已批准口径补齐，正式代码、报告及数据Excel均有当前工作流证据，未改变旧离线统计与导出。
- [x] reverse_audit：8个管理员 API均有 Client/页面入口或下载链接；生成与发布分别显示 Job；已生成文件在发布失败后可下载；取消/恢复使用同一持久 Job Runtime；孤儿与到期清理使用既有 Scheduler。真实浏览器路径补足仅 Mock 无法证明的接线。
- [x] unresolved_cleared：R1–R7均有范围匹配证据，所有 not_satisfied 清零；真实账户在线验收、远程CI和部署不属于本轮仅本地范围，仍明确保留限制。

# 完成证据与状态

已取得关键词补齐后的当前证据：真实隔离 PostgreSQL、生产装配与可控外部 HTTP 传输下22项工作流通过，下载的Word关键词说明/排名和Excel数据/批注/属性均重新解析；后端1742项及12项子测试通过，16项跳过。前端源码未变，沿用组件274项与浏览器174项通过证据。原5项Review Finding均关闭，独立复核重新读取上游要求后未发现遗漏的产品能力或新增blocking实现问题。已完成上游和反向能力审计，按本轮仅本地边界进入ready_for_review；完整正式CI及远程集成未执行。实际命令、各验证对应的修订范围、迁移往返和剩余限制见同目录 [LOCAL_VALIDATION.md](LOCAL_VALIDATION.md)。仅本地分支；不 push、不创建 PR、不 merge、不部署，也未执行运行数据库迁移。

## 当前远程交付接管

2026-10-01 用户新增授权：两批均完成本地修改和验证后，按报告功能、品牌车型整改的顺序通过 PR 合并远程 main，必要时可用管理员权限。管理员权限不替代 Review、当前 head/base 或 required CI。Issue #684 已创建、读回并通过当前 canonical create Contract；R1–R7 的产品实现和本地里程碑继续成立。

Issue AC8 保持未勾选：当前尚未执行 PR required CI、merge、main 新鲜验证、仓库原生 Change 归档、Issue 关闭和分支清理。上述动作是实现 Ready 之后的交付阶段，不能由本地测试推导为已完成；交付过程与最终 Evidence 回写 Issue AC8，完整目标仍未完成。原文中的“不 push、不创建 PR、不 merge”仅描述前一轮本地里程碑，已不作为当前授权边界。

报告 CI 修正取得两条失败测试复现后，CI scope、workflow 和不安全数据库拒绝测试共 82 项通过。独立新建 PostgreSQL 容器、端口 55437 的报告工作流 9 项通过，1 项显式浏览器用例跳过；该浏览器用例原实际验收证据继续覆盖未修改的生产 UI/API/Worker 源码。正式 CI 报告 PG 的实际执行仍需当前 PR 结果确认。
