---
schema: coding-change/v1
id: CHG-20260930-180000-adaptive-analysis-capacity
title: LLM 自适应容量、失败恢复与声音广场筛选调整
level: L3
status: ready_for_review
owner: assistant
branch: perf/adaptive-analysis-capacity
created: 2026-09-30 18:00:00 +08:00
updated: 2026-10-01
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - administration
  - frontend
  - testing
  - documentation
affected_paths:
  - backend/src/aima_ugc
  - migrations/versions
  - frontend/src
  - tests
  - docs
contracts:
  - LLM 管理参数拒绝与只读容量投影
  - 新 Run 可恢复失败保持待重试
  - Run 列表及详情增加 execution_settling
data_changes:
  - 新增 analysis_llm_capacity_profiles 派生学习状态表
  - Analysis Run 和 Request Item 持久恢复字段与有界失败事实
---

# 变更摘要

按用户引用会话《自适应并发调节方案》最后一轮简化 P0/P1 实施。用户最新授权在充分验证后提交、推送并合并远程 main；不部署、不修改用户运行配置或数据库，不调用付费 Provider。

用户追加《内容类型为空原因》最后一轮方案：声音广场移除内容类型筛选并清理隐藏旧状态；可恢复 Validation/Transport 失败持续重试，退避与五分钟无进展停止连接已有容量控制。本次作为同一实现单元收口。仅使用专用隔离 PostgreSQL 和临时测试服务，不复用、迁移或重启用户服务及其数据库。

# 背景、现状与问题

基线 Worker 按人工固定并发/限速和次数上限执行。Provider 容量与当前机器资源变化后，固定值无法反馈实际成功入库吞吐；失败 Item 在恢复前可能被终结。声音广场内容类型控件及旧状态可能施加空值隐藏条件。维持原行为会继续留下上述容量利用和失败恢复缺口。

# 事实与证据

基线 `3e3752c51a5270100fb511b7920be2cf14b039f4` 的 `analysis_concurrent_worker.py`、`concurrent_labeling.py`、管理 Contract 与声音广场 Store 是原调用链事实源；正式 Run/Request Item/Job 已持久化，足以承载恢复，不需要第二套任务系统。启动脚本 `scripts/deploy/start_compose.py` 已生成 Worker 配额并投影给 API；真实资源探测由 `platform/capacity.py` 维护。当前运行和复发路径的直接证据见后文测试清单。

真实付费 Provider 吞吐尚未验证，明确延期；当前机器外的生产服务、Secret、数据与部署状态不作推断。

# 目标、成功标准与非目标

成功标准为 Blueprint 第 35/36 节 AC1–AC17：容量以实际入库反馈调整；可恢复失败只处理未成功 Item；连续五分钟无进展或系统错误停止整个 Run；前端筛选和收尾表达与后端事实一致。现有历史协议、Job Fence/Deadline/取消、业务语义和成功去重保持。

范围为 Analysis/LLM Adapter/管理与内容 API、声音广场与任务中心、生成 Contract、两项 Migration、分层测试和正式文档。不执行生产迁移、Deploy/Release、付费 Probe、依赖升级或无关重构。

# 约束与意图决策

用户最终授权提交、推送并使用管理员权限合并，早期本地限制不再适用；CI/Review/归档门禁仍执行。机器资源复用现有生成预算及 cgroup，不修改在用服务。后端内容形态事实保持，LLM 四个人工参数显式拒绝，Collection 保持原行为。新 Run 冻结恢复协议；历史 Snapshot 不补写新 marker。0076/0077 部署先升级；回滚必须排空父 Run 及关联 Planner/Shard。

# 修改方案与决策依据

控制器与失败测试 → 单表/Migration/共享观察窗 → Executor/RPS/Worker → Run 冻结与动态投放 → 管理 Contract/UI/生成物 → 集成、模拟、回归与独立 Review → 同步正式文档。

追加实施：前端旧筛选回归 → Item/Run 持久重试与健康窗口 → 同一有界 Executor 轮询可发送项 → Worker 短事务反馈、系统停止和同批成功保留 → 隔离 PostgreSQL/HTTP、浏览器与静态/构建回归 → 两份上游完成审计及独立 Review。

选择已有 Item/Run 扩展稳定列，既避免内存重试循环在接管时丢失五分钟窗口，也不引入第二套 Job/恢复表。旧 Snapshot 不补写新 marker；新 Run 冻结 recovery.v1 协议，历史失败数据不自动重新提交。迁移与回滚在隔离库验证，用户数据库本轮不执行任何迁移。

## 备选方案与取舍

纯内存重试无法保存跨重启/Lease 接管的五分钟窗口，不能满足已批准恢复要求。新增恢复 Job/账本会复制已有 Owner/状态机，没有必要。全局硬发送许可账本能进一步抑制瞬时超目标，但与本轮单 Profile、允许短窗反馈的决定不符，因此采用持久 Profile + 活跃分片份额，并明确瞬时误差边界。

# 需求追溯

上游：[引用方案](chatgpt-conversation://6abce1b4-4288-83e8-b746-e8a5d9d970d9) 最后一轮方案、追加引用方案及本轮最新授权；团队可访问的正式需求 Owner 为 `docs/blueprint/07_技术决策与实施门禁.md` 第 35/36 节、`docs/product/02_当前产品能力与用户流程.md` 和 `docs/appendix/07_AI舆情打标与分析实现.md`。当前 Change 仅为施工契约，不作为需求全集。

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 全局 C 主搜索，指数探索、有限区间收敛、拥塞退避、恢复重探、硬上限 | docs/blueprint/07_技术决策与实施门禁.md#AC1 | satisfied | 控制器静态容量与漂移模拟、单元回归；硬上限、指数/区间、拥塞/冷却/重探直接断言 |
| R2 | 单表持久学习、重启恢复、Revision/Prompt 保守热启动，多 Shard 同窗只推进一次 | docs/blueprint/07_技术决策与实施门禁.md#AC2 | satisfied | 隔离 PG Profile 重启、Revision/Prompt、跨 Shard 单观察窗回归 |
| R3 | 跨 Run 共享 C/RPS；动态本地目标与物理上限分离，允许零份额；不取消已发请求 | docs/blueprint/07_技术决策与实施门禁.md#AC3 | satisfied | 跨 Run/Shard 共享 C/RPS、整数零份额、legacy 排空、动态 Executor 回归 |
| R4 | 真实成功入库吞吐、物理 429/timeout/transport 与最终 Validation 分母独立 | docs/blueprint/07_技术决策与实施门禁.md#AC4 | satisfied | 批次仅读取当前 Item；实际 persisted_success 反馈与 HTTP 物理审计回归 |
| R5 | 运行中 Job window 跟随容量、CPU/内存/DB；新 Run 冻结学习的 Shard size/timeout | docs/blueprint/07_技术决策与实施门禁.md#AC5 | satisfied | 隔离 PG 运行中扩窗、DB 零余量、机器 CPU/内存压力与恢复；新 Run 冻结参数回归 |
| R6 | Transport 每逻辑请求有界，历史 Run 保持冻结协议，预览/幂等不受学习漂移影响；新 Run Validation 次数限制由追加方案 R12 替代 | docs/blueprint/07_技术决策与实施门禁.md#AC6 | satisfied | 历史冻结协议回归、新恢复 marker、hash/幂等、每逻辑请求五次物理发送边界回归 |
| R7 | LLM 前后端拒绝人工参数、只读状态；Collection 原行为保持 | docs/blueprint/07_技术决策与实施门禁.md#AC7 | satisfied | 管理 Contract/API 拒绝四参数；浏览器只读轮询保持草稿；Collection 手工参数保存回归 |
| R8 | Simulator 100/500/2500 和 2500→800→2500，Fixed/Oracle 对照；正式持久链验证 | docs/blueprint/07_技术决策与实施门禁.md#AC8 | satisfied | 可控模拟 100/500/2500 的稳态 Oracle 比例 90.105%/89.603%/88.4%；2500→800→2500 末段 84.1036%；正式浏览器→API→Planner/Worker→Fake LLM→PG 黄金链通过 |
| R9 | 真实付费 Provider 性能对照 | docs/blueprint/07_技术决策与实施门禁.md#AC9 | explicitly_deferred | 本轮仅本地实现，无付费调用授权/预算；模拟结果不证明实际模型收益 |
| R10 | 早期仅本地约束已由最新远程提交合并授权替代 | docs/blueprint/07_技术决策与实施门禁.md#AC10 | not_applicable | 最新授权生效；合并仍须当前 head/base Review/CI、main-fresh 与原生归档 |
| R11 | 移除声音广场内容类型控件、草稿/应用字段和请求；清除旧 Session/Route 隐藏条件，保留后端事实 | docs/blueprint/07_技术决策与实施门禁.md#AC11 | satisfied | 旧 Session/Route 清理及列表/计数/AI/导出请求浏览器断言；Backend content_type 与详情事实保留 |
| R12 | Validation 失败只重试尚未成功的 Item，不限固定次数，继续 repair/judge；同一条连续五分钟无合法结果停止 Run | docs/blueprint/07_技术决策与实施门禁.md#AC12 | satisfied | 超过旧次数的 Validation repair/judge 恢复、仅失败 Item 重试、空 2xx 五分钟停止及持久窗口回归 |
| R13 | 临时 Transport 耗尽后 pending，退避上限 30 秒及探活；Run 任意 HTTP 2xx 重置窗口，五分钟无恢复停止 | docs/blueprint/07_技术决策与实施门禁.md#AC13 | satisfied | 五次 Transport 失败后 pending、第六次探活恢复；任意 2xx reset、两种跨事务顺序、4096 压缩窗口与 300 秒停止回归 |
| R14 | 系统错误立即停止整个 Run；取消、Fence、Deadline、崩溃接管及完成统计维持正确 | docs/blueprint/07_技术决策与实施门禁.md#AC14 | satisfied | 401 同 Run 多 Shard/Planner 停止；取消、Lease、Deadline、Job→Run 锁序、父停止统计及真实 execution_settling API 回归 |
| R15 | 重试与 C/RPS 联动、队列及线程有界，复用现有 Durable Job/Request Item，无第二套任务系统 | docs/blueprint/07_技术决策与实施门禁.md#AC15 | satisfied | 复用 Item/Run 与现有 Job；ready-at 有界分页、批量提交、动态 C/RPS、single probe；独立 Review REC01..07/AC01..04 全闭合 |
| R16 | 本地验证不影响其他正在运行代码及数据库 | docs/blueprint/07_技术决策与实施门禁.md#AC16 | satisfied | 所有 PG 验证仅专用容器标签 codex.task=adaptive-analysis-capacity、127.0.0.1:55476 和任务库；浏览器/API/Worker/Fake LLM 使用私有端口/上下文，未重启用户服务或迁移用户库；任务资源清理在验证完成后执行 |
| R17 | 复用机器资源文件和有效配额，综合实时内存、CPU 与数据库预算 | docs/blueprint/07_技术决策与实施门禁.md#AC17 | satisfied | compose.auto.yaml→cgroup/API Worker 预算链 21 项资源回归；生产 Planner 低 CPU、小内存、压力/恢复回归 |

# 计划改动

- `modules/analysis`、LLM Adapter 与 `bootstrap/analysis_*`：控制算法、动态发送和恢复协议，覆盖 R1–R8/R12–R15。
- `postgres/analysis_*`、Job Owner、Migration 0076/0077：共享状态、时窗、统计、锁序与安全回滚，覆盖 R2–R6/R12–R15。
- 管理/内容 Contract、OpenAPI/Client、前端管理/声音广场/任务中心：拒绝人工参数、移除隐藏筛选、实际收尾，覆盖 R7/R11/R14。
- `tests`、前端组件/浏览器测试、Blueprint/Product/Appendix/README：分层验证与正式事实同步；机器资源文件链回归覆盖 R17，隔离约束覆盖 R16。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 控制算法、动态并发、动态限速、HTTP timeout、Contract、hash |
| 接口 / 契约 | required | 管理请求拒绝、生成 OpenAPI/Client、一致性 |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL、跨 Run、同窗推进、Fence、动态投放 |
| 用户 / 工作流验收 | required | LLM 只读状态与 Collection 保存回归 |
| 跨组件关键路径 | required | 正式 Worker/本地 Fake LLM/成功结果持久化 |
| 外部依赖 / 供应方探测 | not_applicable | 本轮不验证付费性能收益；R9 有明确延期，模拟与 Fake LLM 不冒充 Provider 实测 |
| 构建 / 打包 / 运行 | required | Python/前端静态检查、测试与构建 |
| 文档 / 治理 / 其他 | required | 机器事实与正式文档同步、Completion/独立 Review |

# 风险、兼容性、迁移与回滚

新 Run 使用 adaptive.v1，历史冻结 Snapshot 继续按旧固定参数恢复。学习值不改变模型、Prompt、Taxonomy、generation config 或 Job timeout。Schema 新增派生容量表及既有 Run/Item 恢复字段、bounded failure spans 和查询索引；0076/0077 升级先于代码启用，回滚前停止新建并排空新协议 Run 及其关联 Planner/Shard Job，父 Run 失败但子 Job 未终态仍拒绝 downgrade。短控制窗内允许瞬时超目标，不承诺强全局发送信号量。无依赖升级或生产操作。

# 文档、依赖、部署与发布影响

同步 Analysis README、Blueprint 05/07、产品能力和 AI 实现专题，生成 OpenAPI/Client。未新增或升级依赖/Runtime；不更改用户配置或 Secret，不触发付费 Provider。新 Schema 需要部署时先升级，回滚条件见上节；本轮只合并代码，Release/Deploy 不适用，用户没有要求执行。LLM 管理调用方须停止传四个人工参数；前端已同步，Collection 不受影响。

# 完成审计

- [x] upstream_re_read：2026-10-01 重新读取两份最新引用方案和本轮 Git/隔离/机器资源授权；冻结语义由 Blueprint 35/36 与当前专题维护。
- [x] change_coverage：逐条比较 R1–R17 与实现/测试/正式文档；R9 延期有付费边界依据，R10 旧约束已正式替代。
- [x] reverse_audit：管理字段→后端拒绝/只读投影；容量→Worker/跨 Run 分片；入库→反馈；恢复→统计/任务中心；旧筛选→全部提交入口；资源文件→cgroup/API→Planner。
- [x] unresolved_cleared：当前代码范围无 not_satisfied 或 blocking Findings；真实付费收益未实测，远程 CI、merge/main-fresh/归档仍由平台后续证据闭合，不能由本 Change checkbox 冒充。

# 完成证据与状态

基线 `3e3752c51a5270100fb511b7920be2cf14b039f4`。所有数据库命令仅在任务容器/库执行；未修改用户数据库、启动配置或在用服务。没有依赖升级。

- `.venv/Scripts/python.exe -m pytest tests/unit tests/contracts tests/api -q -p no:cacheprovider`：1720 passed、16 skipped、12 subtests；报告截图测试固定到私有不存在的 Profile。后加资源文件回归单独执行并通过。
- `.venv/Scripts/python.exe -m pytest tests/unit/test_compose_auto_scripts.py tests/unit/platform/test_capacity.py -q -p no:cacheprovider`：21 passed；所有 Compose 调用为 Fake，不执行真实服务启停。
- 新容量/恢复与原并发、Stage12/8D 组合 PostgreSQL 回归：67 passed。新恢复共覆盖输出/网络、持久时窗、跨事务迟到事件、取消锁序、正常批量、列表收尾与 downgrade gate。
- 全 PostgreSQL 回归：database 119、jobs 20、collection 143、content 124、ingestion 95、vehicles 2、platform 56，共 559 passed；随后 alembic check 无 Schema 漂移。
- `npm run test -- --run`：36 files、274 passed；`npm run build`、`npm run lint` exit 0。当前浏览器全量 173 passed，唯一导入完成轮询超时在同一独立配置 targeted 重跑 1 passed；相关布局 27 passed。远程完整浏览器 CI 仍必需。
- 本地真实 Full-stack `analysis-streaming.spec.ts`：1 passed（真实 API、Planner、Worker、PostgreSQL 与本机 Fake LLM；无真实付费 Provider）。
- `.venv/Scripts/mypy.exe backend/src/aima_ugc`：420 source files PASS；Ruff、`git diff --check` PASS。生成 OpenAPI/Client，安装构建 wheel 后 root import/Prompt/新模块资源检查 PASS。
- 独立 Review：AC-REV-01～04、REC-REV-01～07 已全部 closed；最后有界 re-review PASS，无 blocking/nonblocking Findings。静态 Review 不替代测试。
- 0076/0077 head→0075→head 往返、完整历史正式 Revision/base→head 兼容及各 checkpoint Schema 断言通过，测试仅使用独立迁移库。

最终提交需绑定同一已审代码；平台 Review/CI 与 main-fresh、原生 Change Archive 的结果由 PR/Actions 维护，尚未发生的动作不记为成功。
