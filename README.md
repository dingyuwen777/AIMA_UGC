# AIMA_UGC

AIMA_UGC 是爱玛舆情监控系统的 Greenfield 重构仓库。目标是从零建立一个可长期维护、可验证、支持多人并行开发的多平台舆情系统。

## 当前状态

当前仓库处于 **Greenfield 初始化阶段**：架构、数据、采集、API、任务、前端、安全、部署和开发门禁已经由 `docs/blueprint/` 定义，但正式业务代码、Contract、Migration、锁文件、CI 和运行环境需要按阶段逐步落地。

因此：

- 当前 Blueprint 是开发设计基线，不代表对应实现已经存在；
- 进入编码后，代码、Pydantic Contract、生成的 OpenAPI/JSON Schema、Alembic Migration、锁文件和测试是机器事实；
- 文档与机器事实出现冲突时，必须先判断是实现缺陷、文档过期还是新决策，再在同一任务中修正；
- 不从旧系统、历史聊天或单个文件猜测当前实现。

## 开发前必须读取

任何分析、设计、编码、Review、PR、CI 或交付任务，都从以下入口开始：

1. [`AGENTS.md`](AGENTS.md)：仓库统一开发规范和硬约束；
2. [`.agents/skills/reliable-vibe-coding/SKILL.md`](.agents/skills/reliable-vibe-coding/SKILL.md)：任务分级、Change、开发、协作和验证流程；
3. [`docs/blueprint/README.md`](docs/blueprint/README.md)：Blueprint 导航和按任务阅读入口；
4. [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md)：已确认决策、初始化版本快照和阶段 Go/No-Go；
5. 再按当前任务读取对应 Blueprint、模块 README、Contract、Migration、依赖、实现和测试。

只读取与当前任务直接相关的内容，不把整套文档机械加载为上下文。

## 系统目标架构

系统采用模块化单体，API、Worker、Scheduler 和 Migration 分进程运行。核心数据链路固定为：

```text
TikHub / 其他 Provider
→ 不可变 Raw Artifact
→ 平台 Mapper
→ Canonical Contract
→ Ingestion
→ PostgreSQL
→ API / Analysis / Monitoring / Reporting
```

主要技术基线：

- Python 3.14 + FastAPI + Pydantic 2 + SQLAlchemy 2 + Alembic + psycopg 3；
- 根目录唯一 Python/uv 工程，Python 源码位于 `backend/src/aima_ugc/`；
- PostgreSQL 18 作为业务事实库和当前规模的持久化 Job 基础设施；
- Vue 3 + TypeScript + Vite + Pinia；
- Pydantic → OpenAPI/JSON Schema → TypeScript Client；
- Local ArtifactStore 为默认字节存储，可在真实需求出现后替换为 S3 类实现；
- Docker Compose 离线 Release，生产服务器不现场 `git pull` 或构建。

完整架构与目录目标见 [`docs/blueprint/01-总体架构与技术选型.md`](docs/blueprint/01-总体架构与技术选型.md)。

## 开发阶段

实施顺序由 [`docs/blueprint/06-开发约束与分阶段实施.md`](docs/blueprint/06-开发约束与分阶段实施.md) 和 `07` 的 Go/No-Go 共同约束。当前首先需要推进：

```text
阶段 0：产品、页面、五平台能力、真实 Fixture、容量/SLO/RPO/RTO 等业务事实
        ↘ 可与不依赖业务选择的工作并行
阶段 1：仓库骨架、锁文件、Python/Node 工具链、OpenAPI Client 与前端 Lint PoC、CI
→ 阶段 2：Platform 基础
→ 阶段 3：Contract、数据库与 System/Auth
→ 阶段 4：Job Runtime
→ 阶段 5：TikHub Client 与 Raw
→ 阶段 6：先完成一个平台的端到端纵切
→ 后续阶段按蓝图逐步扩展
```

阶段 0 未全部完成不阻止与业务选择无关的阶段 1 和部分阶段 2，但不得绕过上游门禁直接批量实现五个平台或生产能力。

## 多人协作

行为变化、新功能、多文件修改和高风险任务按 Skill 使用 `changes/active/<change-id>/CHANGE.md` 记录 Owner、分支、影响路径、Contract、数据变化和依赖；共享 Contract、Schema、Migration 和数据语义必须有明确 Owner，不允许多个分支分别猜测同一公共语义。

Git 和 CI 的具体要求以 `AGENTS.md`、Skill 和 `06` 为准。没有本轮实际执行的验证证据，不得宣称功能完成、测试通过或可发布。

## Blueprint 导航

所有领域设计入口见：

- [`docs/blueprint/README.md`](docs/blueprint/README.md)

版本初始化的唯一文档快照见：

- [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md)
