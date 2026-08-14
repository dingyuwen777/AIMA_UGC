# AIMA_UGC Blueprint 导航

`docs/blueprint/` 是爱玛舆情监控系统 Greenfield 重构的设计基线目录。这里描述系统应该如何实现、哪些决策已经确认、哪些条件尚未满足，以及各阶段何时允许继续推进。

本目录只维护长期有效的当前设计，不记录聊天过程，也不复制代码、Schema、Migration 或锁文件中的机器事实。

## 使用顺序

处理任何仓库任务时：

1. 先读取仓库根目录 [`AGENTS.md`](../../AGENTS.md)；
2. 按 `AGENTS.md` 读取 [`.agents/skills/reliable-vibe-coding/SKILL.md`](../../.agents/skills/reliable-vibe-coding/SKILL.md)；
3. 读取本文和 [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)；
4. 再按当前任务读取对应领域 Blueprint；
5. 进入具体实现后，只继续读取相关模块 README、Contract、Migration、依赖、实现和测试。

不要因为存在 Blueprint 就跳过代码和测试事实，也不要一次性读取所有文档代替针对当前任务的现状调查。

实际开发机配置、Windows x64 一键环境初始化、本地启动、Stage 2 PostgreSQL/readiness 配置以及生产部署当前状态见 [`../环境运行与部署.md`](../环境运行与部署.md)。该文档是操作入口，不替代本目录的架构和门禁事实。

人类可读的统一 HTTP API 说明入口固定为 [`../API接口说明.md`](../API接口说明.md)。该文档用于开发、联调和测试人员理解接口用途与调用方式；HTTP 的机器事实仍由 Pydantic Request/Response、FastAPI Route、固定 `contracts/openapi/openapi.json`、生成 Client 和测试维护，API 说明文档不得成为第二套字段 Schema。

人类可读的统一测试与调试入口固定为 [`../测试与调试说明.md`](../测试与调试说明.md)。它负责解释测试分层、独立验证方式、Fixture/Fake/Probe、运行入口和成功判据；测试代码、Contract、Fixture、Migration、本轮执行结果和 CI 才是验证事实，说明文档不得复制第二套断言或期望值清单。

## 事实源优先级

仓库进入实现阶段后，发生冲突时按以下顺序处理：

```text
已批准的 OpenSpec change（仓库建立后）
→ 当前代码、Migration、Contract、锁文件、生成物和测试事实
→ 07 中的已确认跨文档决策和初始化版本快照
→ 01—06 对应领域设计
→ README 导航和摘要
```

机器事实与已批准设计不一致时，不能静默覆盖任何一方。必须先确认是实现缺陷、文档过期还是新决策，再在同一任务中修正。

## 文档索引

| 文档 | 负责内容 | 什么时候读取 |
| --- | --- | --- |
| [`01-总体架构与技术选型.md`](01-总体架构与技术选型.md) | 模块化单体、运行组件、七个业务模块、目录结构、依赖方向、可替换边界 | 总体架构、目录、模块边界、技术路线、跨模块设计 |
| [`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md) | Plan/Run/Scope/Request/Attempt/Candidate、Provider Adapter、Raw、Mapper、Canonical、分页、刷新策略 | Provider、TikHub/官方 API/Apify/导入、采集、Raw、Mapper、Canonical、平台数据映射 |
| [`03-数据库与文件存储.md`](03-数据库与文件存储.md) | PostgreSQL、表与约束、Owner、Current/Version/Metric、Artifact、Job 数据结构、备份一致性 | Schema、表、Migration、Repository、Artifact、数据历史与幂等 |
| [`04-后端任务API与前端.md`](04-后端任务API与前端.md) | Router/Service/Repository、HTTP Contract、错误、Cursor、Auth、Job Runtime、前端调用边界；公开 API 同时维护固定 OpenAPI、生成 Client 和人类可读接口说明 | API、Job、前端 Client、认证授权、业务服务、长任务 |
| [`05-日志安全部署与运维.md`](05-日志安全部署与运维.md) | 日志、审计、Secret、安全、Docker Compose、离线 Release、备份、回滚、运维 | 日志、安全、配置、部署、Release、服务器目录、备份恢复 |
| [`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md) | TDD、独立可验证能力、测试分层、验证命令、CI、Git、文档同步、Review、阶段 0—12 实施顺序 | 制定开发计划、测试/调试、CI、Git、交付、判断阶段顺序 |
| [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md) | 已确认跨文档决策、唯一初始化版本快照、未决门禁、阶段 Go/No-Go | 每个任务都先读；技术版本、重大决策、是否允许进入某阶段 |

## 当前开发状态

**Stage 1 工程基线、Stage 2 Platform 基础、Stage 3A 数据库基础、Stage 3B Canonical Contract、Stage 4 PostgreSQL Job Runtime 和 Stage 5A Provider/Raw 基础均已建立。** 当前代码已经具备：

- 根 Python/uv 工程、固定运行时与锁文件、FastAPI/Vue、OpenAPI → Orval Client、完整 Stage 1 CI；
- Windows PowerShell 5.1 开发环境引导和本地 Uvicorn + Vite 双服务联调；
- 显式 `AIMA_*` Config、只读 Secret 文件、统一 `.log`、同步 PostgreSQL Runtime；
- `GET /health/ready`；
- `ArtifactService` / `ArtifactStore` 边界和 Local ArtifactStore；
- API / Worker / Scheduler / Migration 的 Platform bootstrap；
- 隔离 PostgreSQL 18.4 的 Stage 2 Platform CI；
- Stage 3A 根 Alembic、`20260813_0001`、`artifacts/system_settings/audit_events`、PostgreSQL Repository 和独立 Migration CI；
- Stage 3B Provider/平台无关 Canonical V1 Pydantic Contract、生成 JSON Schema、固定脱敏帖子聚合示例、稀疏 `observed_fields`、评论树/coverage 语义与 Contract Test；
- Stage 4 `20260814_0002`、`jobs/job_attempt_events`、Job Registry、PostgreSQL Repository、Worker/Reaper、Lease/Fencing/Deadline/重试/取消/Attempt 事件审计和独立 PostgreSQL 18 Job Runtime CI。
- Stage 5A Provider-neutral Request/Attempt/Error/Billing Pydantic Contract、固定 JSON Schema、一次发送 Provider Client/Fake Transport，以及递归脱敏、gzip、SHA-256、不可覆盖和可回放的 Raw Artifact 独立 CI。

Stage 4 的机器事实以 `backend/src/aima_ugc/platform/jobs/`、`backend/src/aima_ugc/adapters/persistence/postgres/jobs.py`、第二条 Migration、测试和 CI 为准。Stage 5A 的机器事实以 `backend/src/aima_ugc/contracts/provider/`、`backend/src/aima_ugc/modules/collection/providers/`、`backend/src/aima_ugc/adapters/providers/fake.py`、`contracts/provider/`、测试和 CI 为准；跨文档决定维护在 [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)。不要在其他 Blueprint 复制实现细节或版本表。

当前下一步分成两条并行路径。

### 阶段 0：继续补齐不能由技术人员猜测的业务事实

包括但不限于：

- 第一版页面、角色操作边界、字段和验收流程；
- 小红书、抖音、微博、B站、快手的 Operation/字段/分页/详情/评论/费用/限流能力矩阵；
- 每个平台合法取得并脱敏的真实 Fixture；
- Raw、个人信息、导出和审计的访问、保留和删除规则；
- 日请求量、数据量、并发、磁盘预算、SLO、RPO、RTO；
- Scheduler misfire/catch-up 业务策略。

### 阶段 5：Provider Adapter、Provider Attempt 和 Raw

Stage 5A 已建立 Provider Client/Transport Port、Provider Request/Attempt、错误与费用的版本化 Contract、Raw Artifact Envelope 和 Fake Transport，但没有建立 Provider PostgreSQL 表。选择该拆分是因为最终 `provider_requests.scope_id → collection_scopes`，而 Collection Run/Scope 父事实尚未建立；本阶段禁止使用无外键 `scope_id`、临时父表或其他弱约束 Schema 绕过依赖。

Stage 5 整体仍在进行中。Provider Request/Attempt 持久化必须等待 Collection 父事实，并通过后续独立 L3 决策按 `03` 的最终 Schema 一次建立；在此之前 Stage 6 的 Candidate/来源链仍是 No-Go。最终多级预算表继续等待 Provider、Content、Collection/Run 父事实全部齐全后建立，不在 Stage 5A 提前实现。

如果 Stage 5 要接入某个真实平台的具体 Operation、费用或真实 Fixture，仍受阶段 0 对应业务事实门禁；Provider 中立的基础边界可以在不猜测平台语义的前提下继续推进。

Stage 1—5A 已建立的 Schema/Repository/Contract/Job Runtime/Raw 边界不重复设计；登录、Role/Permission、Principal 和 actor-bound API 幂等继续等待真实第三方身份需求。

## 修改规则

- `01`—`06` 描述各领域当前设计；
- `07` 只保存跨文档已确认决策、唯一初始化版本快照和实施门禁；
- 实际代码、Contract、Migration、锁文件和测试建立后，不在 Blueprint 复制第二份机器事实；
- 所有需要前端或其他受支持调用方使用的公开 HTTP API，都必须由 Pydantic Request/Response + FastAPI Route 生成固定 OpenAPI，再生成前端 TypeScript Client；内部 Repository、Mapper、Provider Adapter、Worker Runtime、Migration 等能力不因存在就自动暴露 HTTP API；
- 公开 HTTP API 新增、删除或实质变化时，除同步固定 OpenAPI 和生成 Client 外，还必须同步 [`../API接口说明.md`](../API接口说明.md)，说明接口用途、方法/路径、稳定 `operation_id`、主要输入输出、重要错误、权限、分页/幂等/异步 Job 等人类需要理解的语义；完整字段 Schema 仍只由机器 Contract 维护，禁止在 Markdown 中复制第二套字段事实；
- 前端业务功能默认采用“后端业务能力 → Pydantic HTTP Contract → FastAPI Route → API/Contract Test → 固定 OpenAPI → 生成 TypeScript Client → Feature API/Store → Vue 页面/组件 → E2E”的闭环，页面和按钮不得各自手写 URL 或重复定义 Request/Response Contract；
- 对具有明确输入输出、独立业务价值、独立失败边界或可以脱离完整系统验证的能力，必须建立与风险匹配的独立验证闭环：测试/调试/Probe 复用生产实现，明确测试位置、Fixture/Fake/隔离依赖、运行命令、预期结果和未覆盖项；项目公共方法写入 [`../测试与调试说明.md`](../测试与调试说明.md)，模块特有入口写入对应模块 README，不为每个小函数机械创建测试文件或测试文档；
- 设计发生实质变化时，按 `AGENTS.md` 和 Skill 的 L1/L2/L3 流程处理；
- 受影响的文档才更新，不为形式保持“所有文档都有变化”；
- 长期文档直接描述合并后的当前状态，不写成变更流水账。

## 关键原则

```text
先确定事实和边界
→ 再建立机器 Contract
→ 再实现最小纵切
→ 让每个有价值的边界可以独立验证
→ 用真实测试和集成证据验证
→ 最后扩展并行开发
```

不要一次猜测实现五个平台，不要让前端、后端、数据库和 Provider 分别定义同一个公共语义，也不要在没有测量证据时提前引入微服务、消息中间件或额外数据库。
