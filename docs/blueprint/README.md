# AIMA_UGC Blueprint 导航

`docs/blueprint/` 是爱玛舆情监控系统 Greenfield 重构的设计基线目录。这里描述系统应该如何实现、哪些决策已经确认、哪些条件尚未满足，以及各阶段何时允许继续推进。

本目录只维护长期有效的当前设计，不记录聊天过程，也不复制代码、Schema、Migration 或锁文件中的机器事实。

## 使用顺序

处理任何仓库任务时：

1. 先读取仓库根目录 [`AGENTS.md`](../../AGENTS.md)；
2. 按 `AGENTS.md` 读取 [`.agents/skills/reliable-vibe-coding/SKILL.md`](../../.agents/skills/reliable-vibe-coding/SKILL.md)；
3. 读取本文和 [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)；
4. 再按当前任务读取对应领域 Blueprint；
5. **涉及 Provider、TikHub、采集 Plan、关键词发现、详情/评论策略、成本控制或平台 Operation 时，必须再读取 [`08-采集策略与平台能力.md`](08-采集策略与平台能力.md)，然后读取 [`../collection/README.md`](../collection/README.md) 和目标平台文档；**
6. 进入具体实现后，只继续读取相关模块 README、Contract、Migration、依赖、Operation/Mapper、Fixture、实现和测试。

不要因为存在 Blueprint 就跳过代码和测试事实，也不要一次性读取所有文档代替针对当前任务的现状调查。

实际开发机配置、Windows x64 一键环境初始化、本地启动、Stage 2 PostgreSQL/readiness 配置以及生产部署当前状态见 [`../环境运行与部署.md`](../环境运行与部署.md)。该文档是操作入口，不替代本目录的架构和门禁事实。

人类可读的统一 HTTP API 说明入口固定为 [`../API接口说明.md`](../API接口说明.md)。该文档用于开发、联调和测试人员理解接口用途与调用方式；HTTP 的机器事实仍由 Pydantic Request/Response、FastAPI Route、固定 `contracts/openapi/openapi.json`、生成 Client 和测试维护，API 说明文档不得成为第二套字段 Schema。

人类可读的统一测试与调试入口固定为 [`../测试与调试说明.md`](../测试与调试说明.md)。它负责解释测试分层、独立验证方式、Fixture/Fake/Probe、运行入口和成功判据；测试代码、Contract、Fixture、Migration、本轮执行结果和 CI 才是验证事实，说明文档不得复制第二套断言或期望值清单。

采集逻辑的人类可读开发入口固定为 [`../collection/README.md`](../collection/README.md)。它负责讲清通用 Decision Pipeline、Provider Config/平台选择、成本短路、评论抽样、Deep Collection、Business Pipeline Probe，以及小红书/抖音/微博/B站/快手各自的 TikHub Operation、业务参数、内部分页、代码/Fixture/测试状态。平台文档不得把“已批准目标实现”写成“当前代码已完成”。

## 事实源优先级

仓库进入实现阶段后，发生冲突时按以下顺序处理：

```text
已批准的 OpenSpec change（仓库建立后）
→ 当前代码、Migration、Contract、锁文件、生成物和测试事实
→ 07 中的已确认跨文档决策和初始化版本快照
→ 01—08 对应领域设计
→ docs/collection/ 平台实现说明
→ README 导航和摘要
```

机器事实与已批准设计不一致时，不能静默覆盖任何一方。必须先确认是实现缺陷、文档过期还是新决策，再在同一任务中修正。

## 文档索引

| 文档 | 负责内容 | 什么时候读取 |
| --- | --- | --- |
| [`01-总体架构与技术选型.md`](01-总体架构与技术选型.md) | 模块化单体、运行组件、七个业务模块、目录结构、依赖方向、可替换边界 | 总体架构、目录、模块边界、技术路线、跨模块设计 |
| [`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md) | Plan/Run/Scope/Request/Attempt/Candidate、Provider Config/Adapter、Raw、Mapper、Canonical、分页、刷新基础 | Provider、Raw、Mapper、Canonical、来源链、通用采集基础 |
| [`03-数据库与文件存储.md`](03-数据库与文件存储.md) | PostgreSQL、表与约束、Owner、Current/Version/Metric、Artifact、Job、预算数据结构、备份一致性 | Schema、表、Migration、Repository、Artifact、数据历史、幂等、预算 |
| [`04-后端任务API与前端.md`](04-后端任务API与前端.md) | Router/Service/Repository、HTTP Contract、错误、Cursor、Auth、Job Runtime、前端调用边界 | API、Job、前端 Client、认证授权、业务服务、长任务 |
| [`05-日志安全部署与运维.md`](05-日志安全部署与运维.md) | 日志、审计、Secret、安全、Docker Compose、离线 Release、备份、回滚、运维 | 日志、安全、配置、部署、Release、服务器目录、备份恢复 |
| [`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md) | TDD、独立可验证能力、测试分层、验证命令、CI、Git、文档同步、Review、阶段 0—12 实施顺序 | 制定开发计划、测试/调试、CI、Git、交付、判断阶段顺序 |
| [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md) | 已确认跨文档决策、唯一初始化版本快照、未决门禁、阶段 Go/No-Go | 每个任务都先读；技术版本、重大决策、是否允许进入某阶段 |
| [`08-采集策略与平台能力.md`](08-采集策略与平台能力.md) | Stage 7 Provider Config/平台选择、五平台默认 Provider、Operation Matrix、Decision Pipeline、Capability、评论/成本/预算/Deep/Probe 业务规则 | TikHub/Provider、平台采集、Plan 参数、评论、预算、Capability、Real/Business Probe |

## 当前开发状态

**Stage 1 工程基线、Stage 2 Platform 基础、Stage 3A 数据库基础、Stage 3B Canonical Contract、Stage 4 PostgreSQL Job Runtime、Stage 5A—5D Provider-neutral 基础、Stage 6 小红书纵切，以及 Stage 7 的 Decision/Capability、Provider Config/平台路由与抖音/微博请求分页 Operation 机器基础均已建立。** 当前代码已经具备：

- 根 Python/uv 工程、固定运行时与锁文件、FastAPI/Vue、OpenAPI → Orval Client、完整 Stage 1 CI；
- Windows PowerShell 5.1 开发环境引导和本地 Uvicorn + Vite 双服务联调；
- 显式 `AIMA_*` Config、只读 Secret 文件、统一 `.log`、同步 PostgreSQL Runtime；
- `GET /health/ready`；
- `ArtifactService` / `ArtifactStore` 边界和 Local ArtifactStore；
- API / Worker / Scheduler / Migration 的 Platform bootstrap；
- 隔离 PostgreSQL 18.4 的 Stage 2 Platform CI；
- Stage 3A 根 Alembic、`20260813_0001`、`artifacts/system_settings/audit_events`、PostgreSQL Repository 和独立 Migration CI；
- Stage 3B Provider/平台无关 Canonical V1 Pydantic Contract、生成 JSON Schema、固定脱敏帖子聚合示例、稀疏 `observed_fields`、评论树/coverage 语义与 Contract Test；
- Stage 4 `20260814_0002`、`jobs/job_attempt_events`、Job Registry、PostgreSQL Repository、Worker/Reaper、Lease/Fencing/Deadline/重试/取消/Attempt 事件审计和独立 PostgreSQL 18 Job Runtime CI；
- Stage 5A Provider-neutral Request/Attempt/Error/Billing Pydantic Contract、固定 JSON Schema、一次发送 Provider Client/Fake Transport，以及递归脱敏、gzip、SHA-256、不可覆盖和可回放的 Raw Artifact 独立 CI；
- Stage 5B 第三条 Revision、`collection_runs/collection_scopes`、真实 Job 唯一外键、Collection Service/Repository 和 PostgreSQL 18.4 独立 CI；
- Stage 5C 第四条 Revision、`provider_requests/provider_request_attempts`、最终 Scope/Request/Artifact 外键、幂等 Request 与未发送不计费 Attempt，以及 PostgreSQL 18.4 独立 CI；
- Stage 5D 第五条 Revision、受 Job Fencing 约束的 Dispatch CAS、每 Attempt 一次 Provider Client 调用、Raw/Artifact 终态关联、遗留 `dispatching` 恢复，以及 PostgreSQL 18.4 独立 CI；
- Stage 6 小红书 TikHub App V2 搜索/详情/评论 Operation 与分页、纯 Mapper、脱敏非空搜索 Fixture、Candidate/Ingestion 追加账本、Content/Comment Current+Version+Metric、已存 Raw Replay Job、第六至第九条 Revision，以及 PostgreSQL 18.4 独立 CI；
- Stage 7 版本化 `CollectionDecisionRequestV1` / `CollectionDecisionV1` / `ProviderPlatformCapabilityV1`、纯 `CollectionDecisionService`、当前 XHS TikHub Capability 和独立 Decision Probe；
- Stage 7 `ProviderConfigV1` / `ProviderPlatformRouteV1`、System `provider_configs`、`20260815_0010`、PostgreSQL Provider Config Repository、Secret 引用校验和当前只登记 `tikhub + xhs` 的 Provider Registry；同一种 Provider 可以有多个配置实例，实例不绑定平台，平台/Plan 后续选择具体 `provider_config_id`；
- Stage 7 抖音 TikHub `fetch_video_search_v2`、App V3 详情/一级评论/评论回复请求构造，以及 Search/cursor 基础分页状态机；该实现尚不包含 Douyin Mapper、合法脱敏非空真实 Fixture、Real Probe 或默认 Registry Capability 接线；
- Stage 7 微博 TikHub Web Search、App 详情/一级评论、Web V2 二级评论请求构造，以及仅基于已确认 `page/max_id` 事实的分页状态；该实现尚不包含 Weibo Mapper、合法脱敏非空真实 Fixture、Real Probe 或默认 Registry Capability 接线。

Stage 4 的机器事实以 `backend/src/aima_ugc/platform/jobs/`、`backend/src/aima_ugc/adapters/persistence/postgres/jobs.py`、第二条 Migration、测试和 CI 为准。Stage 5A 的机器事实以 Provider Contract/Client/Fake/Raw、生成 Schema、测试和 CI 为准；Stage 5B 以 `modules/collection/execution.py`、Collection Table/Repository、第三条 Migration、PostgreSQL 测试和 CI 为准；Stage 5C 以 `modules/collection/provider_persistence.py`、Provider Repository、第四条 Migration、PostgreSQL 测试和 CI 为准；Stage 5D 以 `modules/collection/provider_dispatch.py`、`modules/collection/provider_recovery.py`、PostgreSQL Dispatch Adapter、第五条 Migration、测试和 CI 为准；Stage 6 以 TikHub XHS Operation/Mapper、Candidate/Content Owner 实现、Raw Replay、第六至第九条 Migration、Fixture、测试和 CI 为准；Stage 7 当前机器事实以 `aima_ugc.contracts.collection`、`modules/collection/decision.py`、`modules/collection/provider_routing.py`、System `provider_configs`/Repository、`adapters/providers/registry.py`、`adapters/providers/tikhub/capabilities.py`、`adapters/providers/tikhub/operations/douyin.py`、`adapters/providers/tikhub/operations/weibo.py`、`contracts/collection/`、第十条 Revision、对应测试和 CI 为准。Stage 7 采集业务语义维护在 [`08-采集策略与平台能力.md`](08-采集策略与平台能力.md)。

## 当前下一步

### Stage 7：当前进度与剩余实现单元

Stage 7 仍然是 [`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md) 定义的一个正式阶段。下面列的是为了独立开发、验证和 Review 而拆出的**实现单元**，不是新的 `Stage 7A/7B/...` 阶段名称；后续 Agent 不得自行发明新的正式阶段层级。

已完成并进入 main：

- Collection Decision/Reply Decision 的版本化 Contract 与纯 `CollectionDecisionService`；
- Provider Platform Capability Contract 与当前 `XHS_TIKHUB_CAPABILITY`；
- `contracts/collection/*.schema.json` 生成/漂移门禁；
- `scripts/dev/probe_collection_decision.py` 独立 Decision Probe；
- Provider Config/Platform Route Contract、`provider_configs` System 父事实、PostgreSQL Repository、Secret 引用边界和当前 `tikhub + xhs` Provider Registry；
- 抖音 TikHub Search V2 + App V3 Detail/Comments/Replies 请求构造和基础分页状态机；
- 微博 TikHub Web Search + App Detail/Comments + Web V2 Sub-comments 请求构造和有证据的分页状态；
- 对应 Unit/Contract/PostgreSQL/Stage 5A—5D/Stage 6/主 CI 回归；
- 已完成的 Change 以 `changes/archive/` 中 Stage 7 记录为准。

Stage 7 剩余实现单元应继续从仓库事实中选择一个边界完整、无上游阻塞的单元推进，主要包括：

- 关键词/词包、Plan 平台配置、Occurrence 与 Run Snapshot 等剩余父事实；
- 在父事实完整后建立最终多级预算 Ledger 和并发 reserve/settle/release/audit；
- B站、快手各自的 TikHub Operation/分页状态机；
- 抖音、微博、B站、快手分别取得合法脱敏真实 Fixture 后完成 Mapper/Ingestion 纵切与可运行 Capability/Registry 接线；
- 统一 Operation Real Probe，以及复用生产 Decision/Mapper 的完整 Business Pipeline Probe（Raw/Canonical/Decision/XLSX）；
- Scheduler 只在 `misfire_policy`、`max_catch_up_runs` 和停机补跑费用/容量保护获得批准后实现/启用。

**这不表示抖音、微博或其余两平台已经兼容完成。** 当前 main 只有小红书拥有 Operation + Mapper/Ingestion 完整纵切；抖音和微博只有 Operation/分页，B站、快手仍没有正式 Operation。四个平台仍必须分别取得合法脱敏非空真实 Fixture、通过 Mapper Contract Test 和 Real Provider Probe 后，才能标记平台纵切完成。

### 新对话 / 新 Agent 如何恢复 Stage 7

新会话**不得依赖上一段聊天记录或模型记忆来判断 Stage 7 做到哪里**。固定恢复流程：

```text
AGENTS.md
→ .agents/skills/reliable-vibe-coding/SKILL.md
→ docs/blueprint/README.md
→ docs/blueprint/07-技术决策与实施门禁.md
→ docs/blueprint/08-采集策略与平台能力.md
→ docs/collection/README.md
→ changes/active（如存在）
→ 与候选 Stage 7 单元直接相关的代码 / Contract / Migration / Fixture / Test / CI
```

恢复后先以机器事实复核本文的进度摘要；若代码与本文不一致，先把它判定为实现缺陷或文档过期并同步修正，不能从旧聊天补猜。没有 Active Change 时，从上面的“Stage 7 剩余实现单元”中选择一个当前无阻塞、可以独立 Red→Green→Review→CI→合并的单元；一次会话只推进当前确认的一个 Stage 7 实现单元，不自动进入 Stage 8。

### 仍然阻塞的上游事项

- Scheduler `misfire_policy`、`max_catch_up_runs` 和停机补跑费用/容量保护仍未批准，因此不能启用 Stage 7 自动 Scheduler；
- Raw、个人信息、导出和审计的访问/保留/删除规则仍待批准；
- 日请求量、数据量、并发、磁盘预算、SLO、RPO、RTO 仍是生产容量/Release 门禁；
- Stage 8 正式业务页面不在当前 Stage 7 实现范围。Stage 7 先建立 Provider Config/Capability/Plan 的后端机器 Contract，Stage 8 再通过 OpenAPI 生成 Client 实现页面；Provider 凭据编辑还需要正式安全 SecretStore/SecretService，不能把数据库明文 Secret 当捷径。

## 修改规则

- `01`—`06` 描述各领域基础设计；
- `07` 保存跨文档已确认决策、版本快照和 Go/No-Go；
- `08` 保存 Stage 7 采集业务语义、Provider Config/Operation Matrix、Capability 和成本策略；
- `docs/collection/` 保存面向开发/调试的通用和平台抓取说明，并始终标记当前代码/Fixture/Probe 状态；
- 实际代码、Contract、Migration、锁文件和测试建立后，不在 Blueprint 复制第二份机器事实；
- 所有需要前端或其他受支持调用方使用的公开 HTTP API，都必须由 Pydantic Request/Response + FastAPI Route 生成固定 OpenAPI，再生成前端 TypeScript Client；内部 Repository、Mapper、Provider Adapter、Worker Runtime、Migration 等能力不因存在就自动暴露 HTTP API；
- 公开 HTTP API 新增、删除或实质变化时，除同步固定 OpenAPI 和生成 Client 外，还必须同步 [`../API接口说明.md`](../API接口说明.md)，说明接口用途、方法/路径、稳定 `operation_id`、主要输入输出、重要错误、权限、分页/幂等/异步 Job 等人类需要理解的语义；完整字段 Schema 仍只由机器 Contract 维护，禁止在 Markdown 中复制第二套字段事实；
- 前端业务功能默认采用“后端业务能力 → Pydantic HTTP Contract → FastAPI Route → API/Contract Test → 固定 OpenAPI → 生成 TypeScript Client → Feature API/Store → Vue 页面/组件 → E2E”的闭环，页面和按钮不得各自手写 URL 或重复定义 Request/Response Contract；
- 对具有明确输入输出、独立业务价值、独立失败边界或可以脱离完整系统验证的能力，必须建立与风险匹配的独立验证闭环：测试/调试/Probe 复用生产实现，明确测试位置、Fixture/Fake/隔离依赖、运行命令、预期结果和未覆盖项；项目公共方法写入 [`../测试与调试说明.md`](../测试与调试说明.md)，Provider/平台特有入口同时写入 [`../collection/`](../collection/) 对应文档；
- 修改 Provider Config/Provider/Operation/Mapper/分页/评论策略/预算/Capability 时，必须按 08 的“文档同步规则”检查目标平台文档；
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

不要一次猜测实现五个平台，不要让前端、后端、数据库和 Provider 分别定义同一个公共语义，也不要在没有测量证据时提前引入微服务、消息中间件或额外数据库。
