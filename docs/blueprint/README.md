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
7. **涉及帖子/评论数据 Excel、`.xlsx` 审阅、共享 Exporter、`tikhub_test` 或 `imports_test` Excel 复用时，必须读取 [`13-统一数据Excel导出与调试复用.md`](13-统一数据Excel导出与调试复用.md)；该文档维护唯一 `UnifiedDataExcelV1`、raw/labeled 同契约和唯一共享 Exporter 的长期门禁。**
8. **当前临时 P1 未闭环期间，任何 Stage 8 开发前必须再读取 [`14-临时P1-Excel离线导入与舆情打标.md`](14-临时P1-Excel离线导入与舆情打标.md) 和对应 Active Change；只继续最前面的未完成 P1 子阶段。**
9. 进入具体实现后，只继续读取相关模块 README、Contract、Migration、依赖、Operation/Mapper、Fixture、实现和测试。

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
| [`13-统一数据Excel导出与调试复用.md`](13-统一数据Excel导出与调试复用.md) | 唯一 `UnifiedDataExcelV1`、raw/labeled 同契约、JSONL→Excel 边界、共享 Exporter 与调试复用门禁 | Excel、`.xlsx`、`openpyxl`、`tikhub_test`/`imports_test`、系统级统一导出 |
| [`14-临时P1-Excel离线导入与舆情打标.md`](14-临时P1-Excel离线导入与舆情打标.md) | Stage 8 前临时 P1 的无数据库 Excel→JSONL→LLM→Excel 实施边界和 P1A—P1H | **仅 P1 未闭环期间读取；P1 完成后删除本文和本索引项** |

## 当前开发状态

**Stage 1—7 已闭环；Stage 7 的实现、Review、PR 合并、合并后 `main` 新鲜 CI 和 Change 归档均已完成。Stage 8 仍是下一正式阶段，但当前业务最高优先级切换为临时 P1，P1 完成前暂停进入 Stage 8。**

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
- Worker 默认 Secret 从 `runtime.settings.secret_dir + validated secret_ref` 读取；默认 TikHub Transport 的自持 HTTP Client 在每次发送后关闭；TikHub Bearer Secret 出站 Origin 限制为批准的 `https://api.tikhub.io`；
- Real Provider Probe 与 API family A/B 的受控事实入口；真实 Probe 不进入普通 CI，也不能把一次 HTTP 200 当长期稳定性承诺。

Stage 7 的实现 PR 为 `#55`，最终实现 head 为 `056e8f5684b19f6b40c4e7c4755593aee3336a7a`，正常合并后的 `main` commit 为 `737151a179a4b941c8bdc553cc77c4286bcb6d27`；最终 PR head 和合并后 `main` 都取得了新鲜 11/11 workflow 成功证据。完整归档证据见：

```text
changes/archive/2026-08/CHG-20260815-stage7-completion/CHANGE.md
```

## 当前临时优先阶段

### P1：Excel 离线导入、关键词清洗、去重与舆情打标

P1 是 Stage 7 与 Stage 8 之间的临时优先插入，不改变任何正式 Stage 编号。当前目标和 P1A—P1H 只由 [`14-临时P1-Excel离线导入与舆情打标.md`](14-临时P1-Excel离线导入与舆情打标.md) 与对应 Active Change 维护。

P1 第一版固定为无数据库离线实现，业务数据中间产物使用 JSONL：

```text
source.xlsx
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl
→ analysis/results.jsonl
→ labeled_data.xlsx
```

`raw_data.xlsx` 只允许作为可选人工审阅旁路，不是 `label_sentiment()` 或默认 `run_all()` 的前置步骤。`label_sentiment()` 直接消费 `deduplicated/contents.jsonl`。

P1 完成并归档后必须：

- 删除 `14-临时P1-Excel离线导入与舆情打标.md`；
- 删除本文中的 P1 临时入口、索引项和当前优先级说明；
- 保留 13 中的唯一 Excel Contract/共享 Exporter 长期规则以及已经实现的可复用代码/测试；
- Stage 8 自动恢复为当前下一正式阶段。

P1 多网页对话恢复事实时至少读取：

```text
AGENTS.md
→ .agents/skills/reliable-vibe-coding/SKILL.md
→ docs/blueprint/README.md
→ docs/blueprint/07-技术决策与实施门禁.md
→ docs/blueprint/14-临时P1-Excel离线导入与舆情打标.md
→ docs/blueprint/13-统一数据Excel导出与调试复用.md
→ changes/active/CHG-20260818-p1-offline-excel-sentiment/CHANGE.md
→ 当前 feature branch / Draft PR / 实现 / 测试
```

## 下一正式阶段

### Stage 8：API / 正式业务前端

Stage 8 仍是下一正式阶段，但在 P1 完成、临时 Blueprint 清理和 P1 Change 归档之前不得开始。P1 收口后的新 Stage 8 对话/Change 必须重新从当时 `main` 事实出发，并按 `AGENTS.md`、Skill 和 Stage 8 相关 Blueprint 完成需求/Contract/接口/验收门禁。

开始 Stage 8 时至少按以下顺序恢复事实：

```text
AGENTS.md
→ .agents/skills/reliable-vibe-coding/SKILL.md
→ docs/blueprint/README.md
→ docs/blueprint/07-技术决策与实施门禁.md
→ docs/blueprint/04-后端任务API与前端.md
→ docs/blueprint/08-采集策略与平台能力.md（若页面/接口涉及采集配置）
→ docs/blueprint/13-统一数据Excel导出与调试复用.md（若涉及基础数据 Excel/导出）
→ docs/API接口说明.md
→ changes/active
→ 当前 main / Contract / OpenAPI / generated client / backend Router/Service / frontend 结构与测试
```

不得把 Stage 7 或 P1 历史聊天当作 Stage 8 当前机器事实，也不得因为上游已闭环就跳过 Stage 8 自己的需求决策和 Contract 门禁。

### 独立于 Stage 7/P1 的后续门禁

以下事项仍需要未来阶段/Release 独立处理：

- Raw、个人信息、导出和审计的访问/保留/删除与合规规则；
- P1 的共享 Excel Exporter 只是统一写出核心；正式系统级大批量导出仍需未来 API/Job/Artifact/权限/生命周期闭环；
- 日请求量、数据量、Worker 并发、Raw/数据库日增量、磁盘容量、SLO、RPO、RTO；
- 生产镜像 variant/digest、离线 Release、安全发布与恢复演练；
- Stage 8 正式业务 API/页面及 Provider 凭据写入能力；凭据仍必须通过安全 SecretStore/SecretService，不能把数据库明文 Secret 当捷径；
- 未来如重新需要 Budget/Cost Guard，必须创建新的 L3 Change，不得复活当前已删除接口。

## 修改规则

- `01`—`06` 描述各领域基础设计和正式阶段顺序；
- `07` 保存跨文档已确认决策、版本快照和 Go/No-Go；
- `08` 保存 Stage 7 已完成的采集业务语义、Provider Config/Operation Matrix、Capability、Provider Billing 和未来 Budget/Cost Guard 边界；
- `09` 保存 Scheduler 当前唯一恢复语义；
- `10`—`12` 保存真实响应/API family/endpoint 证据的人类核查入口；
- `13` 永久保存唯一 `UnifiedDataExcelV1`、JSONL→Excel 边界、raw/labeled 同契约和共享 Exporter 复用/删除门禁，并明确它不是 Report Renderer；
- `14` 只保存当前临时 P1 的实施边界，P1 完成后必须删除，不能演变为第二套永久阶段体系；
- `docs/collection/` 保存面向开发/调试的通用和平台抓取说明，并始终标记当前代码/Fixture/Probe 状态；
- 实际代码、Contract、Migration、锁文件和测试建立后，不在 Blueprint 复制第二份机器事实；
- 所有需要前端或其他受支持调用方使用的公开 HTTP API，都必须由 Pydantic Request/Response + FastAPI Route 生成固定 OpenAPI，再生成前端 TypeScript Client；内部 Repository、Mapper、Provider Adapter、Worker Runtime、Migration 等能力不因存在就自动暴露 HTTP API；
- 公开 HTTP API 新增、删除或实质变化时，除同步固定 OpenAPI 和生成 Client 外，还必须同步 [`../API接口说明.md`](../API接口说明.md)；完整字段 Schema 仍只由机器 Contract 维护；
- 前端业务功能默认采用“后端业务能力 → Pydantic HTTP Contract → FastAPI Route → API/Contract Test → 固定 OpenAPI → 生成 TypeScript Client → Feature API/Store → Vue 页面/组件 → E2E”的闭环，页面和按钮不得各自手写 URL 或重复定义 Request/Response Contract；
- 对具有明确输入输出、独立业务价值、独立失败边界或可以脱离完整系统验证的能力，必须建立与风险匹配的独立验证闭环；调试/Probe 复用生产实现；
- 修改 Provider Config/Provider/Operation/Mapper/分页/评论策略/Provider Billing/Capability 或未来 Budget/Cost Guard 时，必须按 08 的“文档同步规则”检查目标平台文档；
- 修改 Excel 契约、共享 Exporter、`.xlsx` 审阅格式、`tikhub_test` 或 `imports_test` Excel 时，必须按 13 检查是否出现平行实现；共享 Exporter 建成后删除调试目录内重复导出代码是验收条件；
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