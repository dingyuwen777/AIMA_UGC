# AIMA_UGC Blueprint 导航

`docs/blueprint/` 是爱玛舆情监控系统 Greenfield 重构的设计基线目录。这里描述系统应该如何实现、哪些决策已经确认、哪些条件尚未满足，以及各阶段何时允许继续推进。

本目录只维护长期有效的当前设计，不记录聊天过程，也不复制代码、Schema、Migration 或锁文件中的机器事实。

## 使用顺序

处理任何仓库任务时：

1. 先读取仓库根目录 [`AGENTS.md`](../../AGENTS.md)；
2. 按 `AGENTS.md` 读取 [`.agents/skills/reliable-vibe-coding/SKILL.md`](../../.agents/skills/reliable-vibe-coding/SKILL.md)；
3. 读取本文和 [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)；
4. 再按当前任务读取对应领域 Blueprint；
5. **涉及 Provider、TikHub、采集 Plan、关键词发现、详情/评论策略、Provider Billing/成本事实、未来 Budget/Cost Guard 扩展或平台 Operation 时，必须再读取 [`08-采集策略与平台能力.md`](08-采集策略与平台能力.md)，然后读取 [`../collection/README.md`](../collection/README.md) 和目标平台文档；**
6. 涉及 Scheduler、TikHub API family 验证或真实响应结构时，再分别读取 `09`—`12` 中与当前任务直接相关的文档；
7. **涉及帖子/评论数据 Excel、`.xlsx` 审阅、共享 Exporter、`tikhub_test` 或 `imports_test` Excel 复用时，必须读取 [`13-统一数据Excel导出与调试复用.md`](13-统一数据Excel导出与调试复用.md)。**
8. **涉及正式前端页面结构、页面级隔离、Shared/Feature 边界、Figma、Design-to-Code、Figma MCP、Design Token、公共组件或视觉验收时，必须读取 [`16-前端页面架构与Figma设计工作流.md`](16-前端页面架构与Figma设计工作流.md)。**
9. **涉及 Stage 8 的 Excel 主数据入口、Processing/Import Batch、统一入库、`imports_test`/`tikhub_test` 可选写库、采集运行中心或 Stage 8 子阶段实施时，必须读取 [`17-Stage8数据入口统一入库与业务前端实施.md`](17-Stage8数据入口统一入库与业务前端实施.md)。**
10. **涉及 AI 情感/一级/二级标签、Prompt、模型输入、分析结果版本、JSONL 回写或未来 Analysis 数据库存储时，必须读取 [`15-舆情AI打标与统一分析契约.md`](15-舆情AI打标与统一分析契约.md)。**
11. 进入具体实现后，只继续读取相关模块 README、Contract、Migration、依赖、Operation/Mapper、Fixture、实现和测试。

不要因为存在 Blueprint 就跳过代码和测试事实，也不要一次性读取所有文档代替针对当前任务的现状调查。

实际开发机配置、Windows x64 一键环境初始化、本地启动、Stage 2 PostgreSQL/readiness 配置以及生产部署当前状态见 [`../环境运行与部署.md`](../环境运行与部署.md)。该文档是操作入口，不替代本目录的架构和门禁事实。

人类可读的统一 HTTP API 说明入口固定为 [`../API接口说明.md`](../API接口说明.md)。该文档用于开发、联调和测试人员理解接口用途与调用方式；HTTP 的机器事实仍由 Pydantic Request/Response、FastAPI Route、固定 `contracts/openapi/openapi.json`、生成 Client 和测试维护，API 说明文档不得成为第二套字段 Schema。

人类可读的统一测试与调试入口固定为 [`../测试与调试说明.md`](../测试与调试说明.md)。它负责解释测试分层、独立验证方式、Fixture/Fake/Probe、运行入口和成功判据；测试代码、Contract、Fixture、Migration、本轮执行结果和 CI 才是验证事实，说明文档不得复制第二套断言或期望值清单。

采集逻辑的人类可读开发入口固定为 [`../collection/README.md`](../collection/README.md)。它负责讲清通用 Decision Pipeline、Provider Config/平台选择、Provider Billing/成本审计、评论抽样、Deep Collection、Business Pipeline Probe，以及小红书/抖音/微博/B站/快手各自的 TikHub Operation、业务参数、内部分页、代码/Fixture/测试状态。平台文档不得把“已批准目标实现”写成“当前代码已完成”。

## 事实源优先级

仓库进入实现阶段后，发生冲突时按以下顺序处理：

```text
已批准的 OpenSpec change（仓库建立后）
→ 当前代码、Migration、Contract、锁文件、生成物和测试事实
→ 07 中的已确认跨文档决策和初始化版本快照
→ 对应领域 Blueprint
→ docs/collection/ 平台实现说明
→ README 导航和摘要
```

机器事实与已批准设计不一致时，不能静默覆盖任何一方。必须先确认是实现缺陷、文档过期还是新决策，再在同一任务中修正。

## 文档索引

| 文档 | 负责内容 | 什么时候读取 |
| --- | --- | --- |
| [`01-总体架构与技术选型.md`](01-总体架构与技术选型.md) | 模块化单体、运行组件、目录、依赖方向、可替换边界 | 总体架构、目录、模块边界、技术路线、跨模块设计 |
| [`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md) | Plan/Run/Scope/Request/Attempt/Candidate、Provider Adapter、Raw、Mapper、Canonical、分页、刷新基础 | Provider、Raw、Mapper、Canonical、来源链、通用采集基础 |
| [`03-数据库与文件存储.md`](03-数据库与文件存储.md) | PostgreSQL、表与约束、Owner、Current/Version/Metric、Artifact、Job、Provider Billing、历史预算回撤与备份一致性 | Schema、Migration、Repository、Artifact、数据历史、幂等、Provider Billing |
| [`04-后端任务API与前端.md`](04-后端任务API与前端.md) | Router/Service/Repository、HTTP Contract、错误、Cursor、Auth、Job Runtime、前端调用边界 | API、Job、前端 Client、认证授权、业务服务、长任务 |
| [`05-日志安全部署与运维.md`](05-日志安全部署与运维.md) | 日志、审计、Secret、安全、Docker Compose、离线 Release、备份、回滚、运维 | 日志、安全、配置、部署、Release、备份恢复 |
| [`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md) | TDD、独立验证、测试分层、CI、Git、文档同步、Review、正式阶段顺序 | 制定计划、测试/调试、CI、Git、交付、正式阶段判断 |
| [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md) | 已确认跨文档决策、唯一初始化版本快照、未决门禁、阶段 Go/No-Go | 每个任务都先读；技术版本、重大决策、阶段门禁 |
| [`08-采集策略与平台能力.md`](08-采集策略与平台能力.md) | Stage 7 Provider Config/平台选择、五平台 Operation、Decision/Capability、评论、Provider Billing、Deep/Probe、未来 Budget/Cost Guard 边界 | TikHub/Provider、平台采集、Plan、评论、Capability、Probe |
| [`09-Scheduler运行与恢复策略.md`](09-Scheduler运行与恢复策略.md) | `latest_only` Scheduler、Occurrence、停机恢复、并发和正式 Worker 闭环 | Scheduler、Occurrence、scheduled Run、Worker 调度链 |
| [`10-TikHub真实响应结构附录.md`](10-TikHub真实响应结构附录.md) | 五平台已脱敏真实响应结构的人类查询入口 | Mapper/Extractor、Fixture 字段定位、真实响应核查 |
| [`11-TikHub多接口验证与备用策略.md`](11-TikHub多接口验证与备用策略.md) | 同业务语义 API family A/B、候选状态、显式备用与禁止自动 fallback | App/Web/V1/V2/V3 候选验证、备用接口策略 |
| [`12-TikHub真实请求响应与接口选型台账.md`](12-TikHub真实请求响应与接口选型台账.md) | 五平台主 endpoint、真实请求/响应、价格事实和接口选型证据 | TikHub 主链核查、Real Probe、endpoint 选型与历史 A/B |
| [`13-统一数据Excel导出与调试复用.md`](13-统一数据Excel导出与调试复用.md) | 唯一 `UnifiedDataExcelV1`、raw/labeled 同契约、同源 JSONL→Excel、共享 Exporter 与调试复用门禁 | Excel、`.xlsx`、`openpyxl`、`tikhub_test`/`imports_test`、系统级统一导出 |
| [`15-舆情AI打标与统一分析契约.md`](15-舆情AI打标与统一分析契约.md) | 全平台通用 4 情感 + 9 一级 + 39 二级 taxonomy、最小模型输入、Markdown Prompt、Analysis Contract、JSONL 回写与数据库 Owner 边界 | AI 打标、Prompt 调优、模型 Adapter、Analysis 结果、数据库/Excel 消费 |
| [`16-前端页面架构与Figma设计工作流.md`](16-前端页面架构与Figma设计工作流.md) | Vue 页面级隔离、App/Shared/Feature/Page 边界、Figma 设计事实源、MCP Design-to-Code、Design Token、频繁改版与视觉验收 | Stage 8、前端页面、Figma、公共组件、设计系统、Design-to-Code、视觉验收 |
| [`17-Stage8数据入口统一入库与业务前端实施.md`](17-Stage8数据入口统一入库与业务前端实施.md) | Excel 主数据入口、TikHub 辅助补采、Processing/Import Batch、统一 Canonical→Ingestion→PostgreSQL、手工调试可选写库、UI 能力映射和 Stage 8A—8F | Stage 8、正式导入、统一入库、`imports_test`/`tikhub_test` 写库、采集运行中心 |

## 当前开发状态

**Stage 1—7、临时 P1、Stage 8A 与 Stage 8B 已闭环。Stage 8C 当前 Active Change 已建立采集运行中心
机器实现；正式闭环仍以该 Change 的最终 PR Head CI、两阶段 Review、正常合并、归档和合并后 `main`
验证为准。在这些证据完成前不得仅凭页面或本文宣布 Stage 8C 已闭环。**

Stage 8A 与 Stage 8B 当前 `main` 机器边界：

- `processing_import_batches` 作为 Excel File Import 的最小业务父事实；
- `provider_requests` 支持 Collection Scope / Import Batch 恰好一个父级，既有 Collection 来源语义保持兼容；
- Excel 数据库模式使用 Input Artifact → Processing Import Batch → import-parent Provider Request / non-billable Attempt → Canonical → 正式 Content Ingestion，不伪造 Collection Run/Scope/Candidate；
- `imports_test` 默认 `WRITE_TO_DATABASE=False`，显式数据库阶段才装配 PostgreSQL Runtime；
- `tikhub_test` 五个平台 `run_*()` 默认 `write_to_database=False`，显式数据库模式要求稳定 `provider_config_id`，复用 manual Collection / Provider Dispatch / Raw / Candidate-before-Mapper / fenced Ingestion；
- TikHub 数据库模式同一次外部请求同时保留本地调试 Raw 和正式 Raw Artifact，不从 JSONL/Excel 二次回灌，也不因写库额外再发一次 Provider 请求；
- PostgreSQL 仍按 `(platform, external_content_id)` 与评论稳定身份收敛跨批次、跨来源 Current，并保留 Version/Metric/来源历史；
- Stage 8B 为单个 `.xlsx` 建立 multipart HTTP 上传、Source Artifact、Processing Import Batch 与持久化 `ingestion.import-excel.v1` Job；Router 不执行长任务，Worker 复用 Stage 8A 正式 Reader/Mapper/Ingestion；
- 系统全局唯一启用的 Relevance Keyword Pack 保存在 PostgreSQL，Import Job 和 Collection Run 冻结配置快照；所有渠道都在 Mapper 后、正式 Content Ingestion 前执行同一 Relevance Service；
- Import Batch 和 Import Job 支持按 ID 查询，固定响应、统一错误结构和 `request_id` 已进入 OpenAPI，并由现有 Orval 流程生成 TypeScript Client；
- Stage 8C 增加只读 Batch 列表、北京时间 Summary、查询绑定的 HMAC Cursor，以及通过 Feature
  API/Pinia/生成 Client 调用的 Vue 采集运行中心；页面只覆盖 Excel Import，不冒充 Content Center、
  TikHub 补采或 Relevance 配置页面；
- 数据库模式只连接开发者已经准备好的 PostgreSQL 18，不管理 Docker，不自动执行 Alembic Migration，Schema 不满足要求时关闭失败。

Stage 7 已完成并固化：

- 版本化 Collection Decision / Reply Decision / Provider Platform Capability Contract 与纯 Decision Service；
- 同一 Provider 类型多 Config、`provider_config_id` 路由、`secret_ref` Secret 边界；
- Keyword / Keyword Pack System 父事实与 PostgreSQL Repository；
- 五个平台 TikHub 主 Operation、Extractor/Mapper、合法脱敏真实 Fixture、Capability/Registry 和 Canonical/PostgreSQL 兼容证据；
- 快手正式评论主链为 App `fetch_video_comment` / `fetch_video_sub_comments`，Web 仅为显式 `verified_backup`，不存在自动 fallback；
- Provider Request/Attempt Billing、endpoint Pricing、成本快照与 `potential_duplicate_charge` 审计事实；
- 当前**没有**请求次数预算、金额预算、Budget Account、Reservation Ledger、Run/评论 Budget、发送预算门禁或 dormant Budget 接口；历史 `20260815_0012/0013/0014` 不改写，`20260817_0015` 负责向前删除已撤回预算结构，同时保留 Provider Billing/成本审计事实；
- Plan → Platform / Keyword Pack、Occurrence、Run/Scope Snapshot，首版固定 `Asia/Shanghai + latest_only + max_catch_up_runs=0`；
- Scheduler Runtime：更早到期 slot 写 `skipped/misfire_superseded`，只执行最新到期 slot；Occurrence / Job / scheduled Run / Scope / cursor 在正式 PostgreSQL 事务边界内编排；
- `collection.run.v1` 正式 Worker：`Production JobRegistry / JobWorker → CollectionRunJobHandler → CollectionRunExecutor → TikHubCollectionScopeExecutor → Provider Request/Attempt → Raw → Mapper → Canonical → fenced Ingestion`；
- Worker 默认 Secret 从 `runtime.settings.secret_dir + validated secret_ref` 读取；默认 TikHub Transport 的自持 HTTP Client 在每次发送后关闭；TikHub Bearer Secret 默认出站 Origin 为 `https://api.tikhub.dev`，显式兼容既有 `https://api.tikhub.io`，其他 Origin 在发送 Secret 前拒绝；
- Real Provider Probe 与 API family A/B 的受控事实入口；真实 Probe 不进入普通 CI，也不能把一次 HTTP 200 当长期稳定性承诺。

Stage 7 的实现 PR 为 `#55`，最终实现 head 为 `056e8f5684b19f6b40c4e7c4755593aee3336a7a`，正常合并后的 `main` commit 为 `737151a179a4b941c8bdc553cc77c4286bcb6d27`；最终 PR head 和合并后 `main` 都取得了新鲜 11/11 workflow 成功证据。完整归档证据见：

```text
changes/archive/2026-08/CHG-20260815-stage7-completion/CHANGE.md
```

P1 已固化的长期能力：

- 文件 Excel Provider 使用 Canonical/Provider-neutral 边界；Stage 8A 只在显式数据库阶段把已经生成的 Provider-neutral 记录接入正式 PostgreSQL 来源链；
- `UnifiedContentRecordV1` 承载关键词命中与可空 Analysis，Canonical 不承载 AI 标签；
- `UnifiedDataExcelV1` 与唯一共享 Exporter 同时服务 `imports_test`、`tikhub_test` 和后续正式导出；
- raw/labeled Excel 使用同一 Workbook Contract，业务中间处理不从 Excel 回读；
- 全平台内容 Analysis 复用同一 Prompt/Taxonomy、Runtime Validator、LLM Port/Adapter 和有界 Validation Retry；
- 成功 Analysis 先 checkpoint，再原子回写同一个 Provider-neutral JSONL；
- 具体长期 Excel 与 Analysis 规则分别由 Blueprint 13 和 15 维护；
- `imports_test` / `tikhub_test` 永久保留人工调试入口，默认 file-only；Stage 8A 的显式 PostgreSQL 模式不得反向破坏默认离线调试能力。

## 当前 Active Stage

### Stage 8C：采集运行中心首个完整前后端纵切

Stage 8B 已正常闭环；当前唯一 Active 最小正式单元是 **Stage 8C**。8C 只完成采集运行中心的首个正式
Vue 前后端纵切；系统全局 Relevance Keyword Pack 配置页面仍按已批准边界留到 Stage 8F。当前 Stage
经用户批准使用固定 PNG 作为一次性视觉例外；例外、资产哈希和未来 Figma 兼容边界只记录在当前
Change，不修改 Blueprint 16 的长期 Figma 规则。

开始 Stage 8C 时仍必须重新从当时 `main` 恢复事实：

```text
AGENTS.md
→ .agents/skills/reliable-vibe-coding/SKILL.md
→ docs/blueprint/README.md
→ docs/blueprint/07-技术决策与实施门禁.md
→ docs/blueprint/17-Stage8数据入口统一入库与业务前端实施.md
→ docs/blueprint/02-采集系统与数据标准化.md
→ docs/blueprint/03-数据库与文件存储.md
→ docs/blueprint/04-后端任务API与前端.md
→ docs/API接口说明.md
→ changes/active
→ 当前 main / Contract / Migration / OpenAPI / generated client / backend Router/Service / frontend 结构与测试
```

Stage 8C 的目标边界以 Blueprint 16 和 17 为准：先确认 Figma 事实源和页面验收标准，再补齐页面实际需要的 Batch 列表/KPI/Cursor Read Model，复用 Stage 8B 生成的 Orval Client 完成首个运行中心纵切，不提前进入 Content Center、TikHub 补采页面或 Stage 8D—8F。

### 独立于 Stage 8A 的后续门禁

以下事项仍需要未来阶段/Release 独立处理：

- Raw、个人信息、导出和审计的访问/保留/删除与合规规则；
- 已落地的共享 Excel Exporter 只是统一写出核心；正式系统级大批量导出仍需未来 API/Job/Artifact/权限/生命周期闭环；
- 已落地的是平台通用 Analysis 核心与无数据库验证入口；正式数据库 DDL/Migration、Analysis Job/API/页面仍需按 Blueprint 15 和对应正式阶段闭环；
- 日请求量、数据量、Worker 并发、Raw/数据库日增量、磁盘容量、SLO、RPO、RTO；
- 生产镜像 variant/digest、离线 Release、安全发布与恢复演练；
- Stage 8D+ 其余正式业务页面及 Provider 凭据写入能力；凭据仍必须通过安全
  SecretStore/SecretService，不能把数据库明文 Secret 当捷径；
- 未来如重新需要 Budget/Cost Guard，必须创建新的 L3 Change，不得复活当前已删除接口。

## 修改规则

- `01`—`06` 描述各领域基础设计和正式阶段顺序；
- `07` 保存跨文档已确认决策、版本快照和 Go/No-Go；
- `08` 保存 Stage 7 已完成的采集业务语义、Provider Config/Operation Matrix、Capability、Provider Billing 和未来 Budget/Cost Guard 边界；
- `09` 保存 Scheduler 当前唯一恢复语义；
- `10`—`12` 保存真实响应/API family/endpoint 证据的人类核查入口；
- `13` 永久保存唯一 `UnifiedDataExcelV1`、同源 JSONL→Excel、raw/labeled 同契约和共享 Exporter 复用门禁，并明确它不是 Report Renderer；
- `15` 永久保存全平台 AI taxonomy、最小模型输入、Markdown Prompt、Analysis Contract、JSONL 回写和数据库 Analysis Owner 边界；
- `16` 永久保存正式前端页面隔离、App/Shared/Feature/Page Owner、Figma 设计事实源、MCP Design-to-Code、Design Token、高频改版与视觉验收规则；
- `17` 永久保存 Stage 8 Excel 主数据入口/TikHub 辅助、Processing/Import Batch、统一 Canonical→Ingestion→PostgreSQL、调试入口可选写库、UI 能力映射和 8A—8F 实施顺序；
- `docs/collection/` 保存面向开发/调试的通用和平台抓取说明，并始终标记当前代码/Fixture/Probe 状态；
- 实际代码、Contract、Migration、锁文件和测试建立后，不在 Blueprint 复制第二份机器事实；
- 所有需要前端或其他受支持调用方使用的公开 HTTP API，都必须由 Pydantic Request/Response + FastAPI Route 生成固定 OpenAPI，再生成前端 TypeScript Client；内部 Repository、Mapper、Provider Adapter、Worker Runtime、Migration 等能力不因存在就自动暴露 HTTP API；
- 公开 HTTP API 新增、删除或实质变化时，除同步固定 OpenAPI 和生成 Client 外，还必须同步 [`../API接口说明.md`](../API接口说明.md)；完整字段 Schema 仍只由机器 Contract 维护；
- 前端业务功能默认采用“已确认 Figma Frame/页面需求 → UI/后端能力映射 → Pydantic HTTP Contract → FastAPI Route → API/Contract Test → 固定 OpenAPI → 生成 TypeScript Client → 后端与 Vue 并行 → E2E/视觉验收”的闭环；页面和按钮不得各自手写 URL 或重复定义 Request/Response Contract；页面结构、Figma/MCP 和设计资产的详细规则以 `16` 为准，Stage 8 首个页面的后端能力映射以 `17` 为准；
- 对具有明确输入输出、独立业务价值、独立失败边界或可以脱离完整系统验证的能力，必须建立与风险匹配的独立验证闭环；调试/Probe 复用生产实现；
- 修改 Provider Config/Provider/Operation/Mapper/分页/评论策略/Provider Billing/Capability 或未来 Budget/Cost Guard 时，必须按 08 的“文档同步规则”检查目标平台文档；
- 修改 Excel 契约、共享 Exporter、`.xlsx` 审阅格式、`tikhub_test` 或 `imports_test` Excel 时，必须按 13 检查是否出现平行实现；
- 修改 Stage 8 的 Import Batch、统一入库、手工调试可选写库、数据入口优先级或采集运行中心能力边界时，必须按 17 检查来源链、统一 Ingestion、数据库前置条件和 UI 能力映射；
- 修改 AI 标签、Prompt、模型输入、Analysis Contract 或 Analysis 持久化语义时，必须按 15 检查标签闭集、父子映射、Prompt Hash 和兼容性；
- 修改前端页面组织、Figma/MCP、Design Token、公共组件 Owner 或视觉验收规则时，必须按 16 检查是否引入平行组件、平行 Contract 或跨页面复制；
- 设计发生实质变化时，按 `AGENTS.md` 和 Skill 的 L1/L2/L3 流程处理；
- 受影响的文档才更新，不为形式保持“所有文档都有变化”；
- 长期文档直接描述合并后的当前状态，不写成变更流水账。

## 关键原则

```text
先确定事实和边界
→ 再建立机器 Contract
→ 再实现最小纵切
→ 让每个有价值的边界可以独立验证
→ 用真实 Fixture / PostgreSQL / Probe / CI 证据验证
→ 最后扩展并行开发
```

不要让前端、后端、数据库和 Provider 分别定义同一个公共语义，也不要在没有测量证据时提前引入微服务、消息中间件或额外数据库。
