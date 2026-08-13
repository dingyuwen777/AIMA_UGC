# AIMA_UGC

AIMA_UGC 是爱玛舆情监控系统的 Greenfield 重构仓库。目标是从零建立一个可长期维护、可验证、支持多人并行开发的多平台舆情系统。

## 当前状态

**Stage 1 仓库骨架与工具链已经建立。** 当前仓库已经具备可安装 Python package、最小 FastAPI/Vue 工程、固定 OpenAPI、生成 TypeScript Fetch Client、Python/Node 锁文件、基础测试和 CI 质量门禁。

仍未进入业务功能批量开发阶段。Stage 0 的页面/角色、五平台能力矩阵、真实 Fixture、隐私/保留、容量/SLO/RPO/RTO 和 Scheduler misfire 等业务事实继续约束后续实现；Stage 2 可以并行推进不依赖这些业务选择的 Platform 基础。

事实源规则：

- 代码、Pydantic Contract、生成 OpenAPI/Client、锁文件和测试是已落地机器事实；
- Blueprint 描述系统长期设计和尚未满足的门禁；
- 文档与机器事实冲突时，必须先判断是实现缺陷、文档过期还是新决策，再在同一任务中修正；
- 不从旧系统、历史聊天或单个文件猜测当前实现。

## 开发前必须读取

任何分析、设计、编码、Review、PR、CI 或交付任务，都从以下入口开始：

1. [`AGENTS.md`](AGENTS.md)：仓库统一开发规范和硬约束；
2. [`.agents/skills/reliable-vibe-coding/SKILL.md`](.agents/skills/reliable-vibe-coding/SKILL.md)：任务分级、Change、开发、协作和验证流程；
3. [`docs/blueprint/README.md`](docs/blueprint/README.md)：Blueprint 导航和当前阶段；
4. [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md)：已确认决策、初始化版本快照和阶段 Go/No-Go；
5. 再按当前任务读取对应 Blueprint、模块 README、Contract、Migration、依赖、实现和测试。

只读取与当前任务直接相关的内容，不把整套文档机械加载为上下文。

## 已建立的 Stage 1 工程事实

### Python / 后端

- Python `3.14.7`，由 `.python-version` 固定；
- 仓库根目录是唯一 uv 工程，依赖由 `pyproject.toml + uv.lock` 固定；
- build backend 为 `uv_build 0.12.3`；源码固定在 `backend/src/aima_ugc/`；
- `uv sync --locked` 后可直接 `import aima_ugc`；
- Wheel 已验证可构建、在隔离环境安装并再次直接 import；
- 最小 FastAPI 入口已提供 `GET /health/live`，公开 Route 使用显式稳定 `operation_id`。

### Contract / 前端

```text
Pydantic Request/Response
→ FastAPI OpenAPI
→ contracts/openapi/openapi.json
→ Orval Fetch Client
→ frontend/src/generated/api/
```

- OpenAPI 和前端生成 Client 禁止手工修改；
- Node `24.19.0`、npm `11.17.0` 由仓库声明固定；所有 npm 依赖由 `frontend/package-lock.json` 锁定；
- Vue 3 + Vite + Pinia 已建立最小可构建应用；
- TypeScript 7.0.2 native compiler 检查普通 `.ts` 代码；Vue SFC 在 TypeScript 7.0 尚无 programmatic API 的过渡期，按 `07` 的双安装模型使用 `@typescript/typescript6` compatibility API 驱动 `vue-tsc`；
- `npm run typecheck` 同时执行 TS7 native 和 Vue SFC 两条类型门禁；
- Lint、Vitest、Vite Build 和 Playwright CLI 均已纳入 Stage 1 验证。

## 开发环境初始化

从仓库根执行：

```bash
uv sync --locked
npm ci --prefix frontend
```

核心检查：

```bash
uv lock --check
uv run python -c "import aima_ugc"
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/api -q
uv run python scripts/contracts/generate.py --check
uv run python scripts/contracts/check_compatibility.py
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
npm --prefix frontend audit --omit=dev --audit-level=high
npm --prefix frontend audit --audit-level=high
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

修改 HTTP Contract 后，先重新生成固定 OpenAPI 和前端 Client，再提交生成物：

```bash
uv run python scripts/contracts/generate.py
npm --prefix frontend run generate:api
```

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

## 下一阶段

实施顺序由 [`docs/blueprint/06-开发约束与分阶段实施.md`](docs/blueprint/06-开发约束与分阶段实施.md) 和 `07` 的 Go/No-Go 共同约束：

```text
阶段 0：继续补齐产品、页面、五平台能力、真实 Fixture、容量/SLO/RPO/RTO 等业务事实
        ↘ 与不依赖业务选择的工作并行
阶段 2：Config / Secret / Logging / DB Connection / Artifact / 四进程基础
→ 阶段 3：Contract、数据库与 System/Auth
→ 阶段 4：Job Runtime
→ 阶段 5：TikHub Client 与 Raw
→ 阶段 6：先完成一个平台的端到端纵切
→ 后续阶段按蓝图逐步扩展
```

Stage 0 未全部完成不阻止与业务选择无关的 Stage 2，但不得绕过上游门禁直接批量实现五个平台或生产能力。

## 多人协作

行为变化、新功能、多文件修改和高风险任务按 Skill 使用 `changes/active/<change-id>/CHANGE.md` 记录 Owner、分支、影响路径、Contract、数据变化和依赖；共享 Contract、Schema、Migration 和数据语义必须有明确 Owner，不允许多个分支分别猜测同一公共语义。

Git 和 CI 的具体要求以 `AGENTS.md`、Skill 和 `06` 为准。没有本轮实际执行的验证证据，不得宣称功能完成、测试通过或可发布。

## Blueprint 导航

所有领域设计入口见：

- [`docs/blueprint/README.md`](docs/blueprint/README.md)

版本初始化的唯一文档快照和 Stage 1 已验证工具链见：

- [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md)
