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
| [`02-采集系统与数据标准化.md`](02-采集系统与数据标准化.md) | Plan/Run/Scope/Request/Attempt/Candidate、TikHub Adapter、Raw、Mapper、Canonical、分页、刷新策略 | Provider、TikHub、采集、Raw、Mapper、Canonical、平台数据映射 |
| [`03-数据库与文件存储.md`](03-数据库与文件存储.md) | PostgreSQL、表与约束、Owner、Current/Version/Metric、Artifact、Job 数据结构、备份一致性 | Schema、表、Migration、Repository、Artifact、数据历史与幂等 |
| [`04-后端任务API与前端.md`](04-后端任务API与前端.md) | Router/Service/Repository、HTTP Contract、错误、Cursor、Auth、Job Runtime、前端调用边界 | API、Job、前端 Client、认证授权、业务服务、长任务 |
| [`05-日志安全部署与运维.md`](05-日志安全部署与运维.md) | 日志、审计、Secret、安全、Docker Compose、离线 Release、备份、回滚、运维 | 日志、安全、配置、部署、Release、服务器目录、备份恢复 |
| [`06-开发约束与分阶段实施.md`](06-开发约束与分阶段实施.md) | TDD、测试分层、验证命令、CI、Git、文档同步、Review、阶段 0—12 实施顺序 | 制定开发计划、测试、CI、Git、交付、判断阶段顺序 |
| [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md) | 已确认跨文档决策、唯一初始化版本快照、未决门禁、阶段 Go/No-Go | 每个任务都先读；技术版本、重大决策、是否允许进入某阶段 |

## 当前开发状态

**Stage 1 工程基线和 Stage 2 Platform 基础均已建立。** 当前代码已经具备：

- 根 Python/uv 工程、固定运行时与锁文件、FastAPI/Vue、OpenAPI → Orval Client、完整 Stage 1 CI；
- Windows PowerShell 5.1 开发环境引导和本地 Uvicorn + Vite 双服务联调；
- 显式 `AIMA_*` Config、只读 Secret 文件、统一 `.log`、同步 PostgreSQL Runtime；
- `GET /health/ready`；
- `ArtifactService` / `ArtifactStore` 边界和 Local ArtifactStore；
- API / Worker / Scheduler / Migration 的最小 Platform bootstrap；
- 隔离 PostgreSQL 18.4 的 Stage 2 Platform CI。

Stage 2 的机器事实以 `backend/src/aima_ugc/platform/`、`backend/src/aima_ugc/bootstrap/`、HTTP Contract、测试和 CI 为准；跨文档决定维护在 [`07-技术决策与实施门禁.md`](07-技术决策与实施门禁.md)。不要在其他 Blueprint 复制实现细节或版本表。

当前下一步分成两条并行路径。

### 阶段 0：继续补齐不能由技术人员猜测的业务事实

包括但不限于：

- 第一版页面、角色操作边界、字段和验收流程；
- 小红书、抖音、微博、B站、快手的 Operation/字段/分页/详情/评论/费用/限流能力矩阵；
- 每个平台合法取得并脱敏的真实 Fixture；
- Raw、个人信息、导出和审计的访问、保留和删除规则；
- 日请求量、数据量、并发、磁盘预算、SLO、RPO、RTO；
- Scheduler misfire/catch-up 业务策略。

### 阶段 3：Contract、数据库与 System/Audit

Stage 2 已完成，不再继续向 Platform 层堆业务能力。下一阶段应建立：

- Canonical Pydantic / JSON Schema 的正式机器 Contract；
- 核心 PostgreSQL Schema 与 Alembic Revision；
- Artifact 元数据 PostgreSQL Repository / Table，使 Stage 2 的 Metadata Port 有正式实现；
- System Settings、Provider 中立审计，以及未来第三方身份接入所需的 `Principal/AuthContext` 扩展边界；
- 当前不实现登录入口、本地密码、Session、CSRF、登录限流或 MFA；API 幂等的 actor 作用域跟随未来 Principal/认证语义冻结；
- 表 Owner、Migration 升降级和隔离 PostgreSQL 集成门禁。

阶段 0 未全部完成时，Stage 3 只推进已有明确设计支撑的共享基础，不得替用户猜测页面字段、五平台 Operation、隐私保留期、容量或 Scheduler 策略；更不得直接批量实现五个平台。

## 修改规则

- `01`—`06` 描述各领域当前设计；
- `07` 只保存跨文档已确认决策、唯一初始化版本快照和实施门禁；
- 实际代码、Contract、Migration、锁文件和测试建立后，不在 Blueprint 复制第二份机器事实；
- 设计发生实质变化时，按 `AGENTS.md` 和 Skill 的 L1/L2/L3 流程处理；
- 受影响的文档才更新，不为形式保持“所有文档都有变化”；
- 长期文档直接描述合并后的当前状态，不写成变更流水账。

## 关键原则

```text
先确定事实和边界
→ 再建立机器 Contract
→ 再实现最小纵切
→ 用真实测试验证
→ 最后扩展并行开发
```

不要一次猜测实现五个平台，不要让前端、后端、数据库和 Provider 分别定义同一个公共语义，也不要在没有测量证据时提前引入微服务、消息中间件或额外数据库。