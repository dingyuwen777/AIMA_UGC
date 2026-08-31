# AIMA_UGC Agent 开发规范

本文件是目标项目自己的 Agent Overlay。它只记录当前项目真实规则、稳定事实入口、长期工程边界和特殊约束；通用研发方法由本项目已经配置的研发治理能力提供。源仓库维护入口不是目标项目规则，**不要复制到这里**；也不要把通用研发示例中的技术栈当作本项目事实。

<!-- agent-skills:managed:start -->
## 项目研发治理入口

本项目已接入项目级研发治理能力。项目自己的 `AGENTS.md` / `CONTRIBUTING` / Spec / Contract / Schema / Migration / CI / 代码与测试负责说明“这个项目具体是什么”；已配置的项目级 Runtime 负责提供“怎样可靠研发”的当前完整约束。

处理本项目研发任务时：

1. 先读取并遵守当前目录及上级适用的项目规则，并以当前项目真实文件恢复技术栈、架构、Contract、Schema/Migration、CI、部署和设计事实；不得用通用示例覆盖项目事实。
2. 使用当前项目已经配置的研发治理 MCP 获取本次任务需要的完整约束。任务事实只能来自当前项目真实内容和用户已确认决定；无法取得必需约束时，明确报告当前治理能力不可用并停止依赖对应约束的动作，不得用旧记忆、摘要或猜测替代。
3. Runtime Mode 不得根据受管运行资产中可能存在的源码维护导航去直接读取、本地枚举或猜测治理规则；这类导航只服务源码维护场景。当前任务需要的完整治理正文统一通过已配置的研发治理 MCP 获取。
4. 如果用户直接提出开发、修复、重构等自然语言研发任务，且这是首次接入、项目长期治理状态尚未校准，或本次任务暴露长期治理事实可能已经漂移，则在任何实质性生产代码修改前先执行有界的项目治理校准：调查仓库真实实现，只维护项目自有 Overlay；完成后重新读取最终 `AGENTS.md`，再继续用户原始任务。
5. 用户可见的处理过程可以正常说明项目调查、需求与风险判断、代码修改、测试、文档同步、复核、Git、CI 和交付状态；这些实际工程活动不需要隐藏。
6. Runtime Mode 的用户可见输出不得主动展示、枚举或复述治理系统内部分类、文件名、目录结构、规则标识、路由映射、内部凭据或加载明细。需要解释为什么执行某一步时，说明该工程步骤本身的原因，不引用内部治理资产。
7. 安装器认领的受管运行资产仅用于本项目治理能力运行，不属于项目自有长期规则，不应直接手工修改；项目自己的长期规则继续维护在项目正式事实源中。
8. 当前研发治理 MCP 不可用、返回的必需约束不完整，或与更高优先级规则存在无法安全解析的冲突时，明确报告并停止依赖对应治理要求的动作，不得假装已经遵守。

<!-- agent-skills:managed:end -->

<!-- agent-skills:project-governance:v1 -->
## 项目治理校准状态

- 状态：已校准（2026-08-31）
- 本节属于**项目自有 Overlay**，不是安装器受管区。本次校准已核对项目规则、README、长期架构与 Roadmap、Manifest/lock、真实入口和模块、Contract、Schema/Migration、测试、CI、Docker/Compose 与 Release 配置；未核实的外部状态继续明确保留为未确认。
- 后续普通开发不为形式重复全量调查；只有项目长期治理事实发生变化、现有 `AGENTS.md` 与当前事实疑似漂移，或用户明确要求刷新项目规则时，才做 targeted 校准。

## 项目 Overlay 维护规则

1. 项目语言、Runtime、框架、数据库、目录、模块职责、Contract、Schema/Migration、CI、部署和发布方式，只能依据当前仓库文件、实际运行结果或用户/Owner 已确认决定补充；
2. 自动发现到 Manifest、锁文件、README、Spec、Contract、Migration 或 CI 入口，只能作为“去哪里继续核实”的导航，不能直接推导未被证据证明的架构结论；**不能单凭文件名推出 React、FastAPI、PostgreSQL** 或其他具体技术路线；
3. 修改现有规则前先区分**规范性规则、描述性事实和未确认事项**：规范性规则不能因为当前实现没有遵守就被自动删除或弱化；描述性事实只有在当前仓库有充分反证时才修正；无法确认的内容保持未确认，不猜；
4. 项目规则新增、修改或删除时，应保持已有仍有效约束、例外、失败处理、验证责任、安全与兼容边界，禁止为了让文档更短而丢失原文语义；
5. 如果项目后续建立更具体的子目录 `AGENTS.md` 或同等规则，进入该目录工作时同时遵守更具体规则；
6. 项目级研发治理能力可以维护本地可失效导航缓存；该缓存不是项目事实源，不应提交 Git，当前代码、Contract、Schema/Migration、测试和运行结果始终优先。

## 规则、事实与未确认事项的边界

### 规范性规则

1. 本文件、进入目标目录后适用的更具体 `AGENTS.md`、用户/Owner 已确认决定，以及 [`docs/blueprint/06_开发约束与分阶段实施.md`](docs/blueprint/06_开发约束与分阶段实施.md) 和 [`docs/blueprint/07_技术决策与实施门禁.md`](docs/blueprint/07_技术决策与实施门禁.md) 中仍有效的正式门禁，是项目规范性规则；
2. [`docs/roadmap/README.md`](docs/roadmap/README.md) 及其正式 Roadmap 记录已批准但未完成的范围、顺序和 Go/No-Go，不得因为当前代码尚未实现就删除或改写成“已完成”；
3. 当前实现违反正式规则时，应报告并修实现或发起正式决策，不能用“代码现在就是这样”删除、弱化或绕过规则；
4. 规范之间冲突时，先保留更严格且仍有效的约束，查明 Owner 和演进依据后再修改正式事实源，不静默选边。

### 描述性事实

1. 当前实现、Pydantic Contract、生成 OpenAPI/JSON Schema、Alembic Migration、测试、锁文件、CI 和可复现运行结果负责描述“现在是什么”；
2. [`README.md`](README.md)、[`docs/01_代码结构与修改导航.md`](docs/01_代码结构与修改导航.md) 和模块 README 是导航与现状说明，必须回到机器事实核验易变细节；
3. 文档与机器事实冲突时，先区分实现缺陷、文档过期、已批准待实现设计或新决策，再修正确的一方；单个文件不能单独推翻正式边界。

### 未确认事项

无法从仓库、实际运行结果或 Owner 决定确认的环境、平台和业务事实必须写成“未确认”。不得据此猜测生产状态、权限、容量、RPO/RTO、外部系统行为或完成结论。

## 开始任务时的稳定事实入口

- 总入口与当前能力：[`README.md`](README.md)
- 代码、Contract、表与测试导航：[`docs/01_代码结构与修改导航.md`](docs/01_代码结构与修改导航.md)
- 长期架构目录：[`docs/blueprint/README.md`](docs/blueprint/README.md)
- 当前正式技术决策：[`docs/blueprint/07_技术决策与实施门禁.md`](docs/blueprint/07_技术决策与实施门禁.md)
- 开发、测试、CI 与 Git：[`docs/blueprint/06_开发约束与分阶段实施.md`](docs/blueprint/06_开发约束与分阶段实施.md)
- 本地运行和部署入口：[`docs/02_环境运行与部署.md`](docs/02_环境运行与部署.md)
- 测试和调试入口：[`docs/04_测试与调试说明.md`](docs/04_测试与调试说明.md)
- 生产上线与剩余门禁：[`docs/roadmap/02_生产上线实施路线.md`](docs/roadmap/02_生产上线实施路线.md)
- 精确依赖与 Runtime：`pyproject.toml`、`uv.lock`、`.python-version`、`.uv-version`、`.node-version`、`frontend/package.json`、`frontend/package-lock.json`
- 机器 Contract：`backend/src/aima_ugc/contracts/`、`contracts/`、`scripts/contracts/generate.py`
- Schema/Migration：`backend/src/aima_ugc/database_schema.py`、各模块 `tables.py`、`migrations/`
- CI/交付：`.github/workflows/`、`Dockerfile`、`compose.yaml`、`compose.windows.yaml`
- 历史决策和当时证据：`changes/archive/`；它不是当前实现的替代事实源。

## 当前工程基线

以下均为当前仓库已确认的描述性事实；精确 patch 版本仍以上述版本文件和锁文件为准：

1. 项目是全栈模块化单体。后端为 Python/FastAPI/Pydantic 2/SQLAlchemy 2/Alembic/psycopg 3，源码位于 `backend/src/aima_ugc/`；前端为 Vue 3/TypeScript/Vite/Pinia，位于 `frontend/`；
2. Runtime 锁定 Python `3.14.7`、uv `0.12.3`、Node.js `24.19.0`、npm `11.17.0`。Python 项目要求 `>=3.14,<3.15`，CI 与容器也使用对应锁定版本；
3. 仓库根是唯一 Python/uv 工程根，持有 `pyproject.toml`、`uv.lock`、`.python-version`、`tests/`、`scripts/` 和 `migrations/`。禁止创建 `backend/pyproject.toml`、`backend/uv.lock`、`backend/tests/` 或第二套 backend 工程命令；
4. PostgreSQL 18 是唯一业务事实库；当前本地开发、Compose 和 CI 的固定镜像版本为 PostgreSQL `18.4`；Alembic 仅支持连接真实 PostgreSQL 的 online Migration；
5. 后端有 API、Worker、Scheduler、Migration 四个正式进程入口：`entrypoints/api_main.py`、`worker_main.py`、`scheduler_main.py`、`migrate_main.py`；
6. 前端 Client 由 Pydantic/OpenAPI 经 Orval 生成，生成目录为 `frontend/src/generated/`；
7. 根 `Dockerfile` 以仓库根为唯一 build context，通过 backend/frontend target 构建；`compose.yaml` 是 canonical Runtime，`compose.windows.yaml` 只覆盖 Windows 存储，不建立第二套业务拓扑；
8. Internal V1-B / 公司内网 V1 的软件能力和 Stage 12 软件实现已有仓库记录，但这不等于完整 Production Go-Live。公网认证/授权与 HTTPS、协调 Backup/Restore、SBOM/独立签名/完整 provenance、正式服务器 Deploy/Rollback 和完整生产验收仍未完成。

## 架构与模块边界

### 当前模块与职责

- `modules/system/`：系统配置、关键词、Provider Config、审计等系统事实；
- `modules/collection/`：采集计划、调度、候选、Provider Request/Attempt 和采集运行；
- `modules/content/`：Canonical 内容/评论统一入库、Current/Version/Metric/Coverage 与查询；
- `modules/ingestion/`：Excel Import Batch 和历史数据 Campaign/Item/Chunk 编排；
- `modules/analysis/`：相关性、AI 打标、Analysis Run/Request/Result 与人工复核；
- `modules/reporting/`：正式统一 Excel 数据导出；离线 Markdown/Word 渲染能力位于 `platform/reporting/`，当前没有正式 Web Report Center 或 Word Report PostgreSQL Job/API；
- `platform/`：config、database、jobs、logging、security、storage、export、reporting 等共享基础能力；
- `adapters/`：PostgreSQL、TikHub/测试 Provider、LLM、ArtifactStore 等外部实现；
- `bootstrap/`：正式 API/Worker/Scheduler 依赖装配；`entrypoints/` 只负责进程入口；
- `frontend/src/features/`：当前业务 Feature；正式路由以 `frontend/src/router/index.ts` 为准，当前有 `/`、`/voice-plaza`、`/collection-runtime`、`/collection-strategy`。

### 强制调用与写入边界

```text
Router → Service → Model / Port → Repository / Adapter

Provider Adapter / File Reader
→ Raw / Input Artifact
→ Mapper
→ Canonical
→ Relevance
→ ContentIngestionService
→ Owner Repository
→ PostgreSQL
```

1. 每张业务表只有一个写 Owner，Owner 由 `Table.info["owner"]` 声明；跨 Owner 写入必须经过正式 Service/Port/Bootstrap，不能直接调用对方 Repository 或表；
2. Router/Entrypoint 不直接 SQL，Provider 不直接写业务表，Mapper 保持纯转换且不读数据库、不发 HTTP、不做 AI/业务分类；
3. 第三方 JSON 不能成为公共业务结构；前端不直接访问数据库，不复制另一 Feature 的 Store/API，不再造平行 Client、Mapper、Repository 或 Job；
4. 外部 HTTP 不放在数据库事务中；业务事实与必须触发的下游 Job 在同一 PostgreSQL Unit of Work 提交；
5. Collection 在 Raw 后保留 Candidate；文件导入使用真实 Import Batch 或 Campaign/Item/Chunk 父事实，不为目录对称伪造 Collection Run/Scope/Candidate；
6. 调试入口必须复用生产 Adapter、Operation、Mapper、Ingestion、Job Runtime、生成 Client 或 Renderer，不能复制第二套业务规则。

## Contract / Schema / Migration

1. HTTP Request/Response、Canonical、Job Payload 和导出/Provider/Collection/Analysis 模型的手写事实源位于 `backend/src/aima_ugc/contracts/` 及对应模块；`scripts/contracts/generate.py` 生成/校验 `contracts/openapi/openapi.json` 与版本化 JSON Schema；生成文件和 `frontend/src/generated/` 禁止手工修改；
2. Contract 删除字段、改名、改类型/语义、可选变必填、改变默认值/排序/错误均按破坏性变化处理，必须设计版本、兼容期、调用方迁移和验证；
3. 当前 Schema 机器注册入口是 `backend/src/aima_ugc/database_schema.py`，表定义分属各模块和 Platform；Schema 变化必须按 `tables.py → Alembic Revision → 真实 PostgreSQL 测试`，不得在 API 启动时 `create_all()`；
4. `migrations/versions/` 当前从 `20260813_0001` 演进到单一已确认最新 revision `20260828_0030`，其 `down_revision` 为 `20260827_0029`。已发布 Migration 不改写、不改名；新增变化创建新 Revision，并验证 upgrade、head、兼容和必要 downgrade 边界；
5. 外部 ID 使用字符串；关系使用外键/关联表；稳定字段用列，真正灵活的扩展元数据才用 `jsonb`；Content/Comment 使用 Current + Version + Metric Observation；
6. 数据库时间点使用 `timestamptz`，应用 PostgreSQL Session 默认 `Asia/Shanghai`；AIMA 自有 API 时间使用带 `+08:00` 的 ISO-8601，北京时间以外的第三方 Raw/外部协议保持原始时间语义；
7. Artifact ID、元数据和业务关系由 `ArtifactService` 管理，`ArtifactStore` 只按 `storage_key` 存取；正常业务写入走正式 Service/Owner，不把手工 SQL 发展成第二写入接口；
8. AI taxonomy 的唯一业务事实源是 `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md`，不得在 Python、Blueprint、Excel 文档和前端维护平行列表。

## 开发与验证入口

### 开发入口

```bash
uv run python scripts/dev/backend.py
uv run python scripts/dev/frontend.py
uv run python scripts/dev/check_local_stack.py
```

`backend.py` 负责本地 PostgreSQL、Migration、Worker、可选 Scheduler、API 和 readiness；`frontend.py` 负责锁定 Node/npm、必要时 `npm ci` 和 Vite。日常开发不得用临时 `PYTHONPATH`、修改 `sys.path` 或切换工作目录掩盖打包问题。真实 Provider/LLM Probe 默认关闭，显式运行时必须限定请求与费用，不进普通 CI、不默认写生产库、不输出 Secret。

### 后端与仓库质量入口

```bash
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/api -q
uv run pytest tests/integration -q
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
uv run python scripts/contracts/generate.py --check
```

Integration 依赖真实 PostgreSQL，不能用 SQLite 代替 PostgreSQL 行为证明。新功能、修复、重构和行为变化默认 Red → Green → Refactor；缺陷修复必须有回归测试。文档、治理、生成物和纯配置可声明 TDD 例外，但必须执行相应解析、链接、漂移、结构和仓库级检查，不伪造 Red。

### 前端入口

```bash
npm --prefix frontend run generate:api
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend run test:e2e:fullstack
```

具体任务按风险选择目标测试、模块测试、Contract/数据库/Provider 专项、Browser Mock、真实 Full-stack 和 Runtime；不机械执行全部层，但任何 `not_applicable` 都要有事实依据。不得用 Browser Mock 冒充真实 API/数据库/Worker，也不得用局部测试或旧 CI 结果冒充完整回归。

### Change 与完成门禁

1. 按正式项目规范判定 L1–L3；L2/L3 先形成可执行计划并创建或认领 `changes/active/` Change。仓库当前未发现 `openspec/`；若以后正式引入，涉及能力、行为、数据、接口、架构或安全变化时同时遵守其当前规则，不创建平行规范目录；
2. 正式 L2/L3 单元必须建立“上游需求/Owner 决定 → Requirement Traceability → Change → 实现/测试/文档 → Completion Audit → Review → Ready/CI”的闭环；当前 Change 不能充当自身上游需求全集；
3. 前后端、数据库、异步、公共 Contract 或 Provider 边界按实际风险建立 Validation Matrix；进入 Ready 前重新读取上游事实源，独立核对完成定义；
4. 门禁失败修根因，不删除/跳过测试、不降低断言、不吞异常、不盲目更新快照、不为测试硬编码成功路径。

## CI / Git / Release / 部署

1. `.github/workflows/ci.yml` 按 `docs_only`、`governance_only`、`full` 分流；根/子目录 `AGENTS.md` 属于 `governance_only`。Full profile 覆盖 Python/Frontend 质量、Contract/生成漂移、PostgreSQL Integration、架构/表 Owner、安全和构建；
2. `.github/workflows/fullstack.yml` 证明少量 Browser → Vue → API → PostgreSQL → Worker → Browser 真实黄金路径；`.github/workflows/runtime.yml` 证明 Dockerfile/Compose/Secret/non-root/readiness/持久化/recovery；`.github/workflows/tooling.yml` 验证本地开发和 Windows 工具；
3. `.github/workflows/change-completion-gate.yml` 验证需求追溯与完成审计；`.github/workflows/release.yml` 提供 Linux/AMD64 离线候选、Bundle replay、GHCR digest/tag 和 GitHub Release 基础。Release 基础不等于 Production 已获准；
4. 任务从最新 `main` 创建小写英文/数字/连字符分支，可用 `feature/`、`fix/`、`hotfix/`、`refactor/`、`perf/`、`docs/`、`test/`、`build/`、`chore/`、`migration/`、`revert/` 前缀，不使用工具/模型/人员身份前缀；
5. 禁止 `git reset --hard`、`git clean -fd`、强推、覆盖用户修改、重写共享历史、绕过 Branch Protection/质量门禁；未经授权不提交、推送、建 PR、合并或删分支；提交信息使用中文；
6. 完成结论必须基于当前工作树/HEAD 的新鲜验证和 PR 最新 HEAD 的实际 CI。queued/cancelled/旧 commit 绿灯不能当通过；无法验证的内容必须列出原因和风险；
7. canonical Linux/服务器运行使用 `compose.yaml`；Windows Docker Desktop 使用 `compose.yaml + compose.windows.yaml`。部署、回滚、备份恢复和生产验收只能按当前正式 Roadmap 与实际服务器证据执行，不能根据本地 Compose 成功推断生产就绪。

## 项目特殊长期约束

### 持久 Job、Scheduler 与 Provider 恢复

当前 Worker 的唯一事实源是 `backend/src/aima_ugc/bootstrap/worker.py`，实际注册 8 个 Job type：

```text
collection.run.v1
ingestion.import-excel.v1
ingestion.historical-discover.v1
ingestion.historical-snapshot.v1
ingestion.historical-import-chunk.v1
analysis.content-run-plan.v1
analysis.content-label.v1
reporting.content-export-excel.v1
```

1. 长任务使用同一 PostgreSQL Job Runtime，不在 HTTP 请求中长期执行；Payload 版本、幂等、Lease、Fencing Token、Heartbeat、Attempt Deadline、取消、分类重试、进度和结果/错误语义必须保持；
2. Scheduler 使用唯一 `(plan_id, schedule_version, scheduled_for)` Occurrence，在同一事务创建 Run/Job 并推进 `next_run_at`；当前策略是 `Asia/Shanghai + latest_only + max_catch_up_runs=0`；
3. Provider 已有完整 Raw 时不再次发送；同一 Attempt 最多一次外部发送，真正重发创建新 Attempt；`not_sent` 与 `unknown` 分开，网络结果未知保留潜在重复计费事实；Transport 不隐藏自动网络重试，当前不自动跨 TikHub API family fallback；
4. 当前只有 Billing/成本审计事实，没有请求/金额预算、Budget Account、Reservation Ledger 或发送前 Cost Guard；未来预算能力属于新的 L3 决策，不得把成本记录描述成预算控制；
5. 完整协调 Backup/Restore 写屏障尚未实现。进入该阶段后，数据库 UoW、Artifact rename/delete 和维护 epoch 必须按正式设计统一协调；当前不得声称已完成。

### 日志、安全与依赖

1. API/Worker/Scheduler 的人工日志使用 UTF-8、北京时间毫秒、真实调用文件/行号、稳定 event 和关联 ID；默认大小轮转并 gzip。正常 Heartbeat、健康检查、空 Scheduler tick 和普通成功细节不刷 INFO；
2. 不记录完整 Payload、Raw、Token、Cookie、密码、Secret 或用户完整正文；Secret 不提交 Git、不写数据库明文、不进 Raw/Job/日志，Provider Config 只保存 `secret_ref`；
3. 当前未实现第三方认证/企业身份接入，不能宣称敏感/写 API 具有公网生产认证能力。未来认证、授权和身份 Provider 通过独立 L3 Change 与统一 Principal/AuthContext 接入；
4. 保持参数绑定 SQL、显式 CORS/Allowed Host/Provider Origin allowlist，以及路径穿越、SSRF、命令执行、不安全反序列化、公式注入、Zip Bomb、超大上传、日志注入和对象级 Artifact 授权防护；
5. 依赖精确版本只由 Manifest/lock/镜像/Release 事实维护。Python 依赖改 `pyproject.toml` 并同步 `uv.lock`，Frontend 提交 `package-lock.json` 且 CI 使用 `npm ci`；普通任务不升级依赖，不解析 `latest`，新增依赖先说明必要性、许可证、维护、体积和替代方案；
6. 没有实际问题证据不得主动引入微服务、Redis、Kafka、RabbitMQ、MongoDB、OpenSearch、Kubernetes 或多数据库兼容层。

### 文档与用户决策

1. `docs/blueprint/` 承载长期架构与稳定门禁，`docs/roadmap/` 承载阶段状态/待实现/Go-No-Go，模块 README 承载当前实现入口，`docs/appendix/` 承载专题实现与调试，`docs/guides/` 承载开发过程，`docs/collection/` 承载平台采集事实；
2. `docs/` 下同时遵守 [`docs/AGENTS.md`](docs/AGENTS.md)：同类文档使用两位数字稳定编号，README 不编号；已有编号不因插入主题静默重排；
3. 未完成但仍批准的设计必须明确标成待实现，不能因代码不存在而删除；迁移/删除旧文档前必须证明有效事实有新承载、链接/测试已迁移、未完成项进入 Roadmap、历史原因可追溯；
4. 不复制第二套完整 OpenAPI、Prompt taxonomy、Migration SQL 或易漂移 Schema；文档涉及已实现/未实现/限制/默认行为必须有机器事实或 Owner 决定；
5. 会影响业务语义、公共 Contract、Schema、安全/权限、隐私/保留、Provider/费用、调度、SLO/RPO/RTO、兼容或不可逆数据行为且仓库无正式决定时，先给推荐和取舍，由用户/Owner 决定；未决定前暂停依赖该决定的实现，并把最终决定同步到正式事实源。

## 已确认的偏差与仍未确认事项

### 已确认、待单独修正的偏差

1. [`docs/blueprint/01_总体架构与技术选型.md`](docs/blueprint/01_总体架构与技术选型.md) 仍写旧的 4-Job Registry；当前 `bootstrap/worker.py`、README、Blueprint 07 和 Roadmap 02 均证明实际为上述 8 个 Job。后续 targeted 文档任务应修正 Blueprint 01，不能反向删减实现或测试去匹配旧清单；
2. 部分正式文档仍保留首次接入前的治理入口导航。运行时以本文件受管入口为准；这些旧导航不构成项目技术事实，后续应在独立文档同步任务中清理，不能据此手工修改受管运行资产；
3. `ci.yml` 的 governance-only profile 与 `change-completion-gate.yml` 仍调用一套当前安装后不存在的治理回归测试；按 Workflow 原命令执行会在测试发现阶段以退出码 1 失败。修复安装产物与 Workflow 的一致性前，不得声称这两个门禁已通过，也不得删除门禁或伪造空测试目录绕过失败。

### 当前未发现

- 仓库内未发现 `CONTRIBUTING`、独立 RFC/ADR/需求规格目录或 `openspec/`；需求、正式决策和阶段状态当前主要由 Blueprint、Roadmap、用户/Owner 决定、Contract、Migration、Change 与测试承载；
- 当前未发现 `changes/active/`，只有历史 `changes/archive/`。后续 L2/L3 任务必须先按正式规则创建或认领当前 Change。

### 当前无法由仓库确认

- GitHub Branch Protection / Ruleset 的平台侧实际配置和必需 checks；执行 Git/PR 前必须查询平台现状；
- 目标服务器当前部署 SHA、运行状态、数据规模、Secret/证书配置、备份可恢复性和外部 Provider/LLM 账户状态；
- 完整 Production 的认证授权方案、HTTPS/域名、RPO/RTO、保留策略、容量/SLO、正式回滚窗口与验收签字；这些必须由对应 Roadmap/Change 和 Owner 决策后才能固化。
