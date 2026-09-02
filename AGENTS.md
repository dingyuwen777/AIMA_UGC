# AIMA_UGC AI / Coding Agent 开发规范

本文件是 AIMA_UGC 所有 AI Coding Agent 和人工开发者的统一入口。

先记住一条原则：**不要从聊天、历史 Stage 或旧文档猜当前实现。先找到当前机器事实，再做最小、可验证的修改。**

精确机器事实由代码、Pydantic Contract、生成 OpenAPI/JSON Schema、Alembic Migration、测试和锁文件维护；长期架构由 `docs/blueprint/` 维护；未完成阶段与生产上线顺序由 `docs/roadmap/` 维护；专题实现和调试由 `docs/appendix/` 维护；开发工作流由 `docs/guides/` 维护；历史阶段原因和验收证据由 `changes/archive/` 维护。

<!-- agent-skills:managed:start -->
## 项目研发治理入口

本项目已接入项目级研发治理能力。项目自己的 `AGENTS.md`、`CONTRIBUTING`、正式需求、Contract、Schema/Migration、CI、代码、测试和设计事实负责说明“这个项目是什么”；已配置的治理能力负责提供通用研发约束。

处理本项目研发任务时：

1. **无论采用哪种通用治理执行方式，都必须先读取并遵守当前目录及上级适用的项目规则**，再依据当前真实文件恢复本任务所需的技术栈、架构、Contract、Schema/Migration、CI、部署、设计和运行事实；不得用通用示例、历史聊天、缓存或猜测覆盖项目事实。
2. 默认使用项目已配置的治理能力取得当前任务需要的通用约束。系统、开发者或用户级更高优先级指令若明确指定其他执行方式，**只改变通用治理约束的取得和呈现方式**；不得因此跳过、替代或降低目标项目自身规则、Contract、Schema/Migration、CI、正式设计、部署和验收边界。
3. 对用户正常说明项目调查、需求与风险、代码修改、测试、文档同步、复核、Git、CI、Release 和交付状态即可；**治理能力自身的运行与实现细节不属于项目进度或交付内容**。需要解释原因时，说明工程步骤本身的必要性、风险或证据。
4. 首次接入、项目治理状态尚未校准，或长期项目事实疑似漂移时，在实质性生产代码修改前执行有界的项目治理校准：调查当前仓库真实实现，只维护本区块外的项目自有 Overlay；完成后重新读取最终 `AGENTS.md`，再继续用户原始任务。
5. 必需治理约束无法可靠取得、完整性无法确认，或与更高优先级规则存在无法安全解决的冲突时，停止依赖对应约束并如实说明；不得用旧记忆、摘要或自行猜测替代。
6. 本区块由安装/升级流程维护。项目自己的长期规则继续写在本区块外；受管运行资产只服务治理能力运行，不作为项目自有长期规则直接手工维护。

<!-- agent-skills:managed:end -->

<!-- agent-skills:project-governance:v1 -->
## 项目治理校准状态

- 状态：已校准（2026-09-01）。后续只在长期规则或项目事实发生实际变化时做有证据的定向修正，不用普通功能任务重写整份文件。
- 本次校准依据：当前 `AGENTS.md`、根与模块 README、`docs/blueprint/`、`docs/roadmap/`、`docs/appendix/`、`docs/guides/`、Manifest/lock/版本文件、真实入口与模块实现、Pydantic Contract、生成 OpenAPI/JSON Schema、[`backend/src/aima_ugc/database_schema.py`](backend/src/aima_ugc/database_schema.py)、Alembic Migration、后端/前端测试、GitHub Actions、Dockerfile、Compose 和 Release 配置。
- 当前仓库未发现 `CONTRIBUTING*`、独立 RFC/ADR/PRD/Spec 目录或 `openspec/`；是否存在并行施工单元只以 `changes/active/` 当前真实内容为准，不在本文件复制易失效列表。

## 规则、事实和未确认事项的边界

### 规范性规则

- 本文件、适用的子目录 `AGENTS.md`、用户/业务 Owner 已确认决定，以及 Blueprint 中明确标为长期门禁的内容，是项目规范。当前实现违反规范时，应报告并修复实现或按正式决策流程变更规范，不能仅因代码尚未遵守就删除或弱化规则。
- Roadmap 中已批准但未完成的能力是未来约束和阶段状态，不得写成当前已实现，也不得因为代码暂时不存在而删除。
- 重大公共 Contract、Schema、权限、安全、数据保留、外部 Provider、费用、调度、SLO/RPO/RTO 或不可逆数据行为，仍按本文件的用户决策门禁处理。

### 描述性事实

- 当前代码、手写 Contract、生成 OpenAPI/JSON Schema、Alembic Migration、测试、锁文件、CI 与可复现的本轮命令输出，是“当前已经实现什么”的主要证据；README、模块文档和 Blueprint 中的现状描述必须与这些机器事实交叉验证。
- 描述性内容只有在充分证据证明过时后才修正。发现冲突时先判断是实现缺陷、文档漂移、待实现设计还是新决策，不能静默选择其中一方。
- 精确 patch 版本、Migration head、Job 注册、API/Schema 和生成 Client 等易变化事实以对应机器事实源为准，本文件只保留长期基线与必要导航。

### 未确认事项

- 仓库外的实际生产服务器状态、已部署 Commit/镜像、运行时 Secret 与账号权限、真实数据量和性能、当前备份可恢复性、Provider/模型账户额度，以及托管平台上的实时保护规则，必须在相关任务中查询对应环境后才能下结论。
- 完整 Production Go-Live 仍未确认；认证授权、HTTPS、协调 Backup/Restore、正式 Deploy/Rollback、SBOM/签名/provenance、容量与完整生产验收等缺口继续以 Roadmap 和真实环境证据为准。

## 治理校准后的项目边界

- Worker 持久 Job 的精确注册以 [`backend/src/aima_ugc/bootstrap/worker.py`](backend/src/aima_ugc/bootstrap/worker.py) 为机器事实；当前正式架构文档已经同步八种 Job，不再保留旧四项摘要。
- 当前正式项目文档只维护 AIMA 自己的架构、Contract、Schema、测试、CI、部署和开发导航；不在 AIMA 文档树复制外部通用治理规则或其安装、运行实现说明。
- 永久 CI 只验证 AIMA 自己可维护的项目治理接线、文档/Secret、Change Ready 和产品质量；外部通用治理能力自身的源码回归不复制到业务仓库。
- 项目中由安装流程维护的受管文件不作为 AIMA 项目事实源；普通业务开发不直接改写，版本更新通过正式安装/升级流程完成。

## 1. 开始前

处理分析、设计、编码、Review、PR、CI 或交付前：

1. 先读本文件；
2. AIMA 项目规则和当前机器事实始终继续生效；通用研发方法不得覆盖或替代项目事实；
3. 再读 [`docs/blueprint/README.md`](docs/blueprint/README.md) 和 [`docs/blueprint/07_技术决策与实施门禁.md`](docs/blueprint/07_技术决策与实施门禁.md)；
4. 如果任务涉及“下一阶段做什么”、生产部署、认证、Release、Backup/Restore、回滚或旧数据迁移，必须再读 [`docs/roadmap/02_生产上线实施路线.md`](docs/roadmap/02_生产上线实施路线.md)；
5. 如果需要快速找到真实代码入口，读 [`docs/01_代码结构与修改导航.md`](docs/01_代码结构与修改导航.md)；
6. 按任务读取对应 Blueprint、Roadmap、Appendix/Guide、模块 README、Contract、Migration、依赖、实现和测试；
7. 只读取与任务直接相关的内容，不用“全仓全部读一遍”代替真正理解调用链；
8. 能从仓库确认的事实先自行确认；
9. 文档与机器事实冲突时，先判断是实现缺陷、文档过期、待实现设计还是新决策，再在同一任务修正正确的一方；
10. 不从旧系统、历史聊天、模型记忆或单个文件猜测当前实现。

常见任务导航：

| 任务 | 先读 |
| --- | --- |
| 不知道代码在哪、准备实际修改 | [`docs/01_代码结构与修改导航.md`](docs/01_代码结构与修改导航.md) |
| 总体架构/模块边界 | [`docs/blueprint/01_总体架构与技术选型.md`](docs/blueprint/01_总体架构与技术选型.md) |
| Provider、Raw、Mapper、Canonical、Ingestion | [`docs/blueprint/02_采集系统与数据标准化.md`](docs/blueprint/02_采集系统与数据标准化.md) |
| PostgreSQL、Schema、Migration、Artifact | [`docs/blueprint/03_数据库与文件存储.md`](docs/blueprint/03_数据库与文件存储.md)；需要直接 SQL 时再读 [`docs/appendix/01_PostgreSQL查询与调试实战.md`](docs/appendix/01_PostgreSQL查询与调试实战.md) |
| API、Job、Worker、前端 | [`docs/blueprint/04_后端任务API与前端.md`](docs/blueprint/04_后端任务API与前端.md) |
| 日志、安全、运行边界 | [`docs/blueprint/05_日志安全部署与运维.md`](docs/blueprint/05_日志安全部署与运维.md) |
| 当前开发环境怎么运行 | [`docs/02_环境运行与部署.md`](docs/02_环境运行与部署.md) |
| 下一阶段、生产上线、Release/Backup/回滚 | [`docs/roadmap/02_生产上线实施路线.md`](docs/roadmap/02_生产上线实施路线.md) + [`docs/appendix/11_生产部署与离线Release方案.md`](docs/appendix/11_生产部署与离线Release方案.md) |
| 开发/测试/CI/Git | [`docs/blueprint/06_开发约束与分阶段实施.md`](docs/blueprint/06_开发约束与分阶段实施.md) |
| 用户可见行为/前后端/Full-stack/Provider 测试分层 | [`docs/blueprint/06_开发约束与分阶段实施.md`](docs/blueprint/06_开发约束与分阶段实施.md) + 当前实际测试与 CI 配置 |
| 重大跨模块决定 | [`docs/blueprint/07_技术决策与实施门禁.md`](docs/blueprint/07_技术决策与实施门禁.md) |
| Collection Plan、Capability、Decision、评论 | [`docs/blueprint/08_采集策略与平台能力.md`](docs/blueprint/08_采集策略与平台能力.md) + [`docs/collection/README.md`](docs/collection/README.md) |
| Scheduler 运行/停机恢复 | [`docs/appendix/05_Scheduler调度执行与停机恢复.md`](docs/appendix/05_Scheduler调度执行与停机恢复.md) |
| TikHub 真实字段/Mapper | [`docs/appendix/02_TikHub五平台真实响应与字段映射.md`](docs/appendix/02_TikHub五平台真实响应与字段映射.md) + 目标平台文档 |
| TikHub API family / 备用接口 | [`docs/appendix/03_TikHub多接口验证与备用策略.md`](docs/appendix/03_TikHub多接口验证与备用策略.md)、[`docs/appendix/04_TikHub接口选型与真实验证台账.md`](docs/appendix/04_TikHub接口选型与真实验证台账.md) |
| Excel 导入/统一入库 | [`docs/appendix/08_数据入口与统一入库实现.md`](docs/appendix/08_数据入口与统一入库实现.md) |
| Excel 数据明细导出/离线调试 | [`docs/appendix/06_Excel统一数据导出与离线调试.md`](docs/appendix/06_Excel统一数据导出与离线调试.md) |
| AI 相关性/发声类型/情感/标签 | [`docs/appendix/07_AI舆情打标与分析实现.md`](docs/appendix/07_AI舆情打标与分析实现.md) + [`backend/src/aima_ugc/modules/analysis/README.md`](backend/src/aima_ugc/modules/analysis/README.md) + 当前 Prompt |
| Word 舆情报告 | [`docs/appendix/10_Word舆情报告生成与排版实现.md`](docs/appendix/10_Word舆情报告生成与排版实现.md) + [`backend/src/aima_ugc/platform/reporting/README.md`](backend/src/aima_ugc/platform/reporting/README.md) |
| Figma / Design-to-Code | [`docs/guides/01_Figma与前端设计开发工作流.md`](docs/guides/01_Figma与前端设计开发工作流.md) + [`docs/blueprint/04_后端任务API与前端.md`](docs/blueprint/04_后端任务API与前端.md) |

任务开始时按当前治理规则判定 L1–L3。L2/L3 先写计划并创建/认领要求的 Change。仓库存在 `openspec/` 后，涉及新能力、行为、数据、接口、架构或安全变化的任务必须按当前 OpenSpec 规则更新对应 change 并通过校验；纯机械文档/格式任务按当前治理规则的例外处理。不得自行创建与 OpenSpec 工具产物冲突的平行目录。

### 项目开工门禁（本地分支优先）

只读分析、方案、答疑或 Review 不自动获得 Issue、Change、分支、提交、push 或 PR 写权限。L1 机械修改和边界明确的隔离小修继续使用当前轻量路径，不为形式创建完整治理对象。

持久 gated L2 和 L3，或项目/用户已明确要求通过 PR 交付的实现任务，在生产代码修改前按以下顺序初始化：

```text
确认或创建 Requirement Source / Issue
→ 同步最新 main
→ 创建并切换本地任务分支
→ 在本地建立 Change / 失败测试 / 最小治理提交
→ 形成首个本地提交
→ 首次 push 创建同名远程跟踪分支
→ 创建早期 PR
```

硬规则：

1. 本地开发从**本地任务分支**开始；不得直接在 `main` 上开始正式实现；
2. 远程分支只能由已有本地分支的**首次 push**建立；不得先创建远程空分支，再把它当成本地开发起点；
3. **早期 PR**在首个可审查治理、Change 或失败测试提交推送后尽早创建，用于 Requirement Source、CI 和 Review 追溯，不表示实现已经 Ready；
4. 宿主已验证可自动完成 Draft → Ready 时使用 Draft PR；否则创建普通 PR，并明确“逻辑未就绪”，所有 Ready 门禁完成前禁止 merge；
5. 保持 `Issue ↔ Change ↔ branch ↔ PR` 稳定关联。PR 使用 `Requirement-Source:`，只有当前 PR 完成整个 Issue 时才使用关闭关键字；
6. 当前宿主没有相应外部写权限时，在依赖该权限的动作前停止并报告，不用远程空分支、口头关联或本地副本冒充已建立追溯链。

### 正式单元完成定义追溯门禁

对新建的 L2/L3 Change，尤其是 Stage / 子 Stage / Roadmap 正式开发单元，必须遵守：

```text
用户已确认决定 / 正式 Roadmap / Spec / Stage 完成定义
→ Requirement Traceability
→ 当前 Change
→ 实现 / 测试 / 文档
→ Completion Audit
→ 两阶段 Review
→ Ready Check / CI
```

硬规则：

1. 新 Change 模板默认 `completion_gate: required`；机制引入前没有该标记的历史/既有 `rvc-change/v1` 作为 legacy 保持兼容，不批量改写历史；
2. 当前 Change 是施工契约，**不能作为自身的上游需求全集**；编码前从本轮用户明确决定和仓库正式上游事实源逐条建立 `Requirement Traceability`；
3. 每条 Requirement 只能是 `satisfied / explicitly_deferred / not_applicable / not_satisfied`；Ready 前 `not_satisfied` 必须清零，延期/不适用必须有正式依据；
4. 进入 `ready_for_review` 前必须重新读取上游事实源，独立重建完成定义，再比较“上游要求 → Change”和“Change → 实现/测试/文档”；不能因为当前 Change checkbox、测试或 CI 全绿就跳过这一步；
5. 对存在前后端、生产者/消费者、异步状态或跨页面结果的任务，Completion Audit 还必须执行适用的反向能力审计，例如“后端能力 → 前端入口”和“前端动作 → 后端真实支持”；没有对应边界时记录不适用依据，不制造机制；
6. Agent 负责主动发现遗漏，不能把用户后续提醒当成完成定义检查机制；
7. Ready 前运行：

```bash
python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready
```

机器 Ready Check 只验证可机器判断的结构、状态、Source 路径、占位符和 Completion Audit checkbox；它不能证明业务语义完整，因此不能替代 Requirement Traceability 和语义 Review。

对应完整规则通过上方项目研发治理入口按当前任务取得。

## 2. 系统基线

以下长期方案不得被普通任务静默改变：

- 模块化单体；
- API、Worker、Scheduler、Migration 分进程；
- PostgreSQL 18；
- Python 3.14；
- FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、psycopg 3；
- 仓库根 `uv + pyproject.toml + uv.lock`；
- Vue 3 + TypeScript + Vite + Pinia；
- Pydantic/OpenAPI 生成前端 Client；
- Provider/File Reader → Raw/Input Artifact → Mapper → Canonical → Relevance → Ingestion Service → Owner Repository → PostgreSQL；
- PostgreSQL 持久化 Job；
- Local ArtifactStore 默认实现，可在真实需要时替换 S3；
- 应用 `.log` 为主要人工排障日志，Docker stdout/stderr 为辅助；
- Docker Compose 离线 Release 是长期部署方向。Internal V1-A 已提供根 [`Dockerfile`](Dockerfile)、[`compose.yaml`](compose.yaml) 与最小可部署容器基础；当前 [`.github/workflows/release.yml`](.github/workflows/release.yml) 已建立 Linux/AMD64 Backend/Frontend + 固定 PostgreSQL 的离线 `images.tar`、Release/Migration Manifest、`SHA256SUMS`、`DEPLOY.md`、no-build/no-pull 回放以及正式 GHCR digest/Tag/GitHub Release 基础；完整 Production 仍缺 SBOM/独立签名/完整 provenance、协调 Backup-Restore、正式服务器 Deploy/Rollback、认证授权/HTTPS 和完整生产验收。

采用方案 A：仓库根目录是唯一 Python/uv 工程根，保存 [`pyproject.toml`](pyproject.toml)、[`uv.lock`](uv.lock)、[`.python-version`](.python-version)、`tests/`、`scripts/` 和 `migrations/`；源码在 `backend/src/aima_ugc/`。禁止创建 `backend/pyproject.toml`、`backend/uv.lock`、`backend/tests/` 或用 `uv --project backend` 形成第二套命令。

Internal V1-A 已在仓库根建立唯一 [`Dockerfile`](Dockerfile) 与 [`compose.yaml`](compose.yaml)，Docker build context 继续固定在仓库根；后端/前端通过不同 target 构建，不把 `backend/` 或 `frontend/` 当独立 context。当前 Release Workflow 已经实现离线 Bundle、镜像身份/Manifest 和离线回放基础，但**不能把这些基础写成完整 Production Go-Live**；剩余 Production 强化仍由后续独立 Change 完成。

打包问题必须修根因：禁止用临时 `PYTHONPATH`、改变工作目录、修改 `sys.path` 或先删除产物来掩盖 package discovery/构建配置问题。

版本政策：精确版本以 [`.python-version`](.python-version)、[`.node-version`](.node-version)、[`.uv-version`](.uv-version)、[`uv.lock`](uv.lock)、[`frontend/package-lock.json`](frontend/package-lock.json) 和镜像/Release 锁定事实为准。禁止运行时或构建时解析 `latest`，禁止因为发现新版本就在普通功能任务里升级；升级是独立任务，必须核验官方发布、兼容/安全影响并执行完整门禁。

没有实际问题证据不得主动引入微服务、Redis、Kafka、RabbitMQ、MongoDB、OpenSearch、Kubernetes 或多数据库兼容层。

## 3. 编码前

复杂任务至少明确：

```text
背景与现状
目标
范围
非目标
成功标准
输入和输出
模块 Owner
必须保持不变
预计文件
兼容性
数据迁移
测试
验收
部署
回滚
```

步骤写清：

```text
[步骤]
→ 修改范围：[文件 / 模块]
→ 预期结果：[可观察行为]
→ 验证方式：[命令 / 检查项]
```

能从仓库确认的事实不反问；发现用户前提与当前代码冲突时先指出证据。

### 用户决策门禁

如果未决事项会实质影响业务语义、页面/验收、公共 Contract、Schema、权限/安全、隐私与保留/删除、外部 Provider/Operation、费用/预算、调度、SLO/RPO/RTO、兼容或不可逆数据行为，并且仓库没有已批准事实：

1. Agent 不得静默选择默认值后继续实现依赖该决定的行为；
2. 先完成能由仓库、官方资料、Fixture、测试自行确认的事实调查；
3. 在对话中先给明确推荐；存在实质取舍时再给 2–3 个真实备选及影响；
4. 由用户/业务 Owner 作最终决定；未决定前暂停依赖该决定的 Contract、Schema、业务语义、安全策略或不可逆实现；
5. 用户明确延期时，把延期本身写入长期事实源，不偷偷实现；
6. 用户决定后，同一任务同步 Blueprint/需求、OpenSpec（存在时）、Contract/Schema（形成机器事实时）及当前 Change；
7. 后续遇到已经固化的决定直接执行，只有新需求冲突时才重新提请决策。

## 4. 简单、精准、兼容

- 只写满足当前需求的最少代码；
- 优先标准库和现有依赖；
- 不增加未要求功能、CLI、配置、兼容层或未来占位抽象；
- 不顺手重构、改名、格式化无关文件；
- 默认保持公共 API、Contract、导入路径、配置、环境变量、数据格式、数据库、启动方式、合法行为、错误类型和关键错误信息；
- 破坏性变化必须先设计版本、Migration、兼容期、部署和回滚。

### 注释语言

- 除专有名词、标识符、协议、库和标准名外，代码注释使用中文；
- Python 文档字符串遵循 PEP 257；其他语言沿用项目既有文档注释规范；
- 注释解释原因、约束、风险和非直观规则，不机械复述代码；公共接口以及承载非显然业务规则、关键不变量、状态转换、兼容原因或重要副作用的内部/private/helper 按实际需要补充说明。

## 5. 模块边界

模块化只为四件事：

```text
输入明确
输出明确
变化隔离
可以独立验证
```

允许调用链：

```text
Router
→ Service
→ Model / Port
→ Repository / Adapter
```

外部数据：

```text
Provider Adapter / File Reader
→ Raw / Input Artifact
→ Mapper
→ Canonical
→ Relevance
→ Ingestion Service
→ Owner Repository
→ PostgreSQL
```

Collection 外部来源在 Raw 后还保留 Candidate；文件导入使用 Processing Import Batch 或 Data Import Campaign/Item/Chunk 等真实父事实，不为了目录对称伪造 Collection Run/Scope/Candidate。

数据库读取：

```text
PostgreSQL
→ Query Repository / Read Model
→ Query/Application Service
→ Router / API
```

禁止：

- Router 直接 SQL；
- Provider 直接写业务表；
- Mapper 读数据库、发 HTTP 或做 AI/业务分类；
- 第三方 JSON 成为公共业务结构；
- 一个模块绕过 Owner 写另一个模块的表；
- 多个 Repository 写同一张业务表；
- 前端直接访问数据库；
- Feature 复制另一个 Feature 的 Store/API；
- 为同一能力再造平行 Client、Mapper、Repository 或 Job；
- 每个函数机械增加 Interface/Facade/Factory/Manager；
- 万能 BaseRepository；
- 运行时任意插件加载。

只有外部基础设施、跨模块边界或独立 Fake 明显受益时才创建 Port。

## 6. 独立调试

调试入口必须复用生产实现。

- Provider Probe 调生产 Adapter/Operation；TikHub 只是一个 Provider 实现；
- Mapper 测试调用生产 Mapper；
- Ingestion 使用 Canonical Fixture 和隔离 PostgreSQL；
- Worker 使用生产 Job Runtime 和 Fake Handler；
- Frontend 使用生成 Client 的 Mock；
- Renderer 使用固定 Report Context；
- `tikhub_test` / `imports_test` 可以提供人工入口，但不能复制 endpoint、分页、字段映射、去重、AI、Exporter 或业务写库规则。

真实付费 Provider/模型 Probe 默认关闭；显式运行时明确费用和请求上限，不进普通 CI，不默认写生产库，不打印 Secret。

## 7. 数据

- PostgreSQL 是唯一业务事实库；
- 外部 ID 使用字符串；
- 数据库时间继续使用 `timestamptz` 表达绝对时间点，应用 PostgreSQL Session 默认 timezone 固定为 `Asia/Shanghai`；
- AIMA 自有 API 时间统一使用带 `+08:00` 偏移的 ISO-8601 北京时间；第三方 Raw、外部协议必须保持原始时间语义的事实层按原协议处理；
- 人工日志使用北京时间 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message`；前缀不额外输出 `timezone` 字段或 `Asia/Shanghai` 文本；
- 关系使用外键/关联表，不用逗号字符串；
- 稳定字段用列，确实灵活的扩展元数据才用 `jsonb`；
- Content/Comment 使用 Current + Version + Metric Observation；
- 一张表只有一个写 Owner；
- 外部 HTTP 不放在数据库事务中；
- 内容版本只与当前 Business Hash 比较，允许 `A → B → A` 形成新版本；
- Collection Candidate/Ingestion 来源账本必须能追溯 Run、Scope、Attempt、Raw 和来源项；兼容单文件 Import 追溯 Import Batch/Input Artifact；统一 Data Import 追溯 Campaign/Source Item/Chunk/Artifact/Batch/逐行账本；
- Artifact ID/元数据/业务关系由 `ArtifactService` 管理，`ArtifactStore` 只按 `storage_key` 存取；
- 业务事实与必须触发的下游 Job 在同一 PostgreSQL Unit of Work 提交；
- 可重试操作必须有明确、受数据库约束的幂等身份；
- 正常业务写入优先走正式 Service/Owner，不把手工 SQL 当第二套写入接口。

## 8. Contract

手写事实源：

- HTTP：Pydantic Request/Response；
- Canonical：Pydantic Canonical Model；
- Job：版本化 Pydantic Payload；
- AI taxonomy/输出业务规则：数据库中唯一 active Analysis Scheme Version；空库由当前 Git Prompt bootstrap。

生成：

- OpenAPI；
- JSON Schema；
- TypeScript Client。

生成目录禁止手工修改。Contract 删除字段、改名、改类型、改语义、可选变必填、改默认排序或错误都按破坏性变化处理。

AI taxonomy 不允许在 Python、Blueprint、Excel 文档和前端各维护一份平行列表；运行时唯一业务事实源是数据库中唯一 active Analysis Scheme Version，[`backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md`](backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md) 只负责空库 bootstrap/灾备基线。Prompt 模板、`relevance` 规则、情感、`voice_type`、标签和 Validator 所需 Taxonomy 必须作为同一 Scheme Version 原子发布或回滚。

## 9. Job、Scheduler 与 Provider 恢复

当前 Worker 实际注册的持久长任务以 [`backend/src/aima_ugc/bootstrap/worker.py`](backend/src/aima_ugc/bootstrap/worker.py) 为准。当前机器事实包括：

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

三个 `ingestion.historical-*` 是统一 Data Import Campaign 沿用的物理 Job type；`analysis.content-run-plan.v1` 是新版 Analysis Run Planner。物理名称保留兼容，不构成平行任务系统。未来把其他长任务产品化时也必须走同一持久 Job Runtime，而不是在 HTTP 请求中长时间执行。

Job 必须支持：

- Payload Version；
- 幂等；
- Lease；
- Fencing Token；
- Heartbeat；
- Attempt Deadline；
- 取消；
- 分类重试；
- 进度；
- 结果/错误。

Worker 必须原子认领 `queued` 或接管 Lease 已过期的 `running`，并生成新 Fencing Token。完成、失败、进度、续租和业务可见提交都必须验证当前 Token；只扫描 `queued` 不合格。

Heartbeat 不能无限延长 Attempt Deadline；Reaper 使用 CAS 处理 Deadline 超时、取消和次数耗尽。

Scheduler 使用唯一 `(plan_id, schedule_version, scheduled_for)` Occurrence，在同一事务创建 Run/Job 并推进 `next_run_at`。当前策略固定 `Asia/Shanghai + latest_only + max_catch_up_runs=0`。

Provider 恢复：

- 已校验完整 Raw 存在时禁止再次调用 Provider；
- 同一 Attempt 最多一次外部发送；
- 真正重发创建新 Attempt；
- `not_sent` 与 `unknown` 必须区分；
- 网络结果未知时不能承诺零重复计费，保留 `potential_duplicate_charge`；
- Transport 禁止在一次调用中隐藏自动网络重试；
- 当前不自动跨 TikHub App/Web/V1/V2/V3 API family fallback。

当前版本**不实现请求/金额预算、Budget Account、Reservation Ledger 或发送前 Budget/Cost Guard**。Provider Request/Attempt 可以保存持久 Billing/成本审计事实；LLM 离线/运行调用可以产生 token/cost 元数据，但当前 `analysis_content_results` 不保存 token/cost 列。成本记录不等于预算控制。未来预算能力必须通过新的 L3 Change 明确 Contract、Schema、Migration、发送前边界和验证。

进入正式协调 Backup/Restore 实现后，业务写 Unit of Work、Artifact 生命周期和文件 rename/delete 必须参与统一共享/独占 advisory 写屏障，并在取得共享锁后复核维护 epoch；Backup Set 持有独占锁直到数据库与文件捕获完成。**当前完整 Release 写屏障/协调 Backup-Restore 尚未实现**，不得在文档、测试或交付中伪造为已完成。

正常 Heartbeat 不写 INFO。Secret 不进 Job Payload。

## 10. 日志

应用日志用于人工排障。当前 API/Worker/Scheduler 使用统一北京时间毫秒格式，核心规则：

- UTF-8；
- 一行一个事件；
- 前缀包含时间、真实调用文件名和源码行号；
- 稳定 `event`；
- 关联 request/job/run/scope/provider/content 等 ID；
- 默认按当前配置执行大小轮转和 gzip；
- 同时允许 stdout 作为容器辅助日志；
- 不记录完整 Payload、Raw、Token、Cookie、密码、Secret 和用户完整正文；
- 统一转义换行、引号、反斜杠和控制字符，并限制字段/整行长度；
- 健康检查、空 Scheduler tick、普通成功细节不刷 INFO；
- 高价值业务/管理操作需要数据库审计时写 `audit_events`。

默认语义：

```text
INFO    → 低频重要生命周期/结果
WARNING → Retry、部分失败、需要关注的异常
ERROR   → 永久失败/未预期错误
DEBUG   → 正常轮询和成功细节
```

## 11. 安全

- Secret 不提交 Git、不写数据库明文、不进 Raw、日志、Job；
- 使用只读 Secret 文件/批准的运行时 Secret 边界；
- Provider Config 只保存 `secret_ref`；
- 当前第一版不实现本地账号密码、登录入口、MFA、Session、CSRF 或登录限流；真实企业身份接入需要独立 L3 Change；
- 未来飞书/OIDC/其他身份源通过 Identity/Authentication Adapter 进入统一 `Principal/AuthContext`；业务模块不得直接依赖飞书 SDK、`open_id`、`union_id` 等 Provider 私有身份；
- Authentication 与 Authorization 解耦，后端执行权限判断；
- 当前业务 API/页面已经存在，但第三方认证尚未接入，因此不得宣称敏感/写 API 已具备公网生产认证能力；
- 如果未来采用 Session，按方案实现 Session 哈希、Cookie、CSRF、撤销/过期；如果采用 OAuth/OIDC/飞书授权，按协议验证 `state`、`nonce`，支持时使用 PKCE；
- CORS、Allowed Hosts、Provider 出站 Origin 使用显式 Allowlist；
- TikHub Bearer Secret 只发送到批准的 TikHub HTTPS Origin；
- 使用参数绑定 SQL；
- 防路径穿越、SSRF、命令执行、不安全反序列化、公式注入、Zip Bomb、超大上传、日志注入；
- Raw 和导出按实际授权模型保护并记录必要审计；
- Artifact 下载执行对象级授权；出站 SSRF 校验覆盖 DNS 和每次重定向；
- 已实现并批准的安全检查不得为方便调试而关闭。

## 12. 测试

新功能、修复和行为变化默认：

```text
Red
→ Green
→ Refactor
```

缺陷修复必须有回归测试。测试验证真实行为，不只验证 Mock 被调用。

文档、生成物、纯配置或无法合理 TDD 的任务，明确测试例外，改用链接检查、解析、生成差异、构建、实际运行和仓库级一致性检查；不要伪造 Red。

验证顺序：

```text
目标测试
→ 模块测试
→ Contract/DB/Provider 专项
→ 前后端集成
→ 完整 CI
```

对 L2/L3 且存在用户可见、前后端/数据库/异步、公共 Contract 或 Provider 边界的任务，必须按上方项目研发治理入口取得当前分层验证规则并建立 Validation Matrix。固定职责是：

```text
Browser Mock Acceptance
→ 广覆盖用户可见行为、状态、请求和错误表达

Backend/API/PostgreSQL Integration
→ 服务器业务规则、事务、持久化、Job/Worker

Contract / Generated Client
→ Pydantic/OpenAPI/generated client 或其他正式机器 Contract 一致性

Real Full-stack Golden Path
→ 少量关键路径证明真实 Browser/Frontend/API/DB/Worker 等组件接通

Real Provider Probe
→ 仅在外部 Provider 当前真实事实需要确认时有界执行，默认不进普通 CI
```

硬规则：

- Browser Mock 可以是用户可见行为覆盖最宽的一层，但不能被描述为真实后端、数据库、Worker 或 Provider 端到端证明；
- Backend/DB 行为必须由真实后端/数据库测试承担，不能只靠 Browser Mock；
- 公共接口变化必须保留 Contract/generated 漂移检查，不能让 Mock 手写第二套接口事实；
- Real Full-stack 默认只保留足够证明接线的高价值 Golden Path，不用它穷举所有 queued/running/error/empty 等 UI 状态；
- 不要求每个任务机械执行全部层；`not_applicable` 必须有真实依据，`required` 必须在 Ready 前有新鲜证据；
- 测试数量按实际行为边界与风险决定，不设置固定 Mock/Integration/Full-stack 数量配额。

涉及公共边界时还必须运行当前存在的架构、表 Owner、Secret、文档和项目治理检查：

```bash
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
uv run python scripts/quality/check_agent_governance.py
```

门禁失败修根因，不能修改门禁放行违规实现。失败输出应让开发者知道规则、文件/位置、原因和修复方向。

可靠性/安全专项按实际已实现能力使用真实 PostgreSQL 和生产调用链验证，例如：

- Worker 在 claim、HTTP、Raw、业务提交和终态边界崩溃后的恢复，旧/新 Lease 并发受 Fencing；
- Attempt Deadline、Reaper 超时/取消/次数耗尽 CAS，Heartbeat 不续 Deadline；
- 多 Scheduler 对同一 Occurrence 不重复、不丢失；
- Provider 新发送必须新 Attempt，完整 Raw takeover 不重发，429/5xx/网络未知保留来源/费用事实；
- 认证接入后再按实际协议补身份/授权/CSRF/OIDC/IDOR 等专项，不对当前未实现认证伪造“已通过”测试；
- 中文搜索质量/性能、容量、协调 Backup/Restore 等能力只有进入对应正式阶段后才建立相应门禁。

禁止：

- 删除或跳过失败测试；
- 降低断言和门禁；
- 吞异常；
- 针对测试硬编码；
- 盲目更新 Snapshot；
- 用旧结果冒充本轮验证；
- 局部测试冒充完整回归；
- Browser Mock 冒充 Real Full-stack；
- 为了覆盖状态空间把所有场景都复制成昂贵 Full-stack；
- 把真实付费 Provider Probe 偷塞进普通 CI。

## 13. 依赖

- 精确依赖版本以实际版本文件、[`uv.lock`](uv.lock)、[`frontend/package-lock.json`](frontend/package-lock.json) 和镜像/Release 锁定事实为准，Blueprint 不维护第二份 patch 版本表；
- Python 依赖只改 [`pyproject.toml`](pyproject.toml)，同步 [`uv.lock`](uv.lock)；
- CI 使用 `uv sync --locked`；
- Frontend 提交 [`frontend/package-lock.json`](frontend/package-lock.json)，CI 使用 `npm ci`；
- 不同时使用多个包管理器；
- 普通功能不升级依赖；
- 新增依赖说明必要性、许可证、维护、体积和替代方案；
- 镜像和 Release 使用可审计的固定版本/digest；
- 不得因有新版本擅自升级；升级必须是独立任务并完整回归。

## 14. 文档

文档职责：

```text
docs/blueprint/
→ README + 当前实际编号的核心长期架构、为什么这样设计、稳定门禁

docs/roadmap/
→ 当前阶段状态、未完成开发、生产上线顺序和 Go/No-Go

模块 README
→ 当前代码具体实现、Owner、入口、常见修改点

docs/appendix/
→ PostgreSQL、Scheduler、TikHub、Excel、AI、Word 报告、生产 Release 等专题实现和调试

docs/guides/
→ Figma 等开发过程指南

docs/collection/
→ 五个平台当前采集实现

docs/01_代码结构与修改导航.md
→ 常见开发任务如何定位到真实代码、Contract、表和测试

Contract / Migration / tables.py / generated / tests / locks
→ 精确机器事实

changes/archive/
→ 历史为什么改过、已完成阶段/Change 的当时验证证据
```

核心 Blueprint 的数量、文件名和编号范围不在本规则写死；以 `docs/blueprint/` 当前实际文件集合、[`docs/blueprint/README.md`](docs/blueprint/README.md) 和 [`docs/AGENTS.md`](docs/AGENTS.md) 为准。当前已有稳定编号不得为了插入新主题静默重排。新增主题先判断应该进入现有核心 Blueprint、Roadmap、Appendix、Guide 还是模块 README；只有确实形成新的核心长期领域时才新增 Blueprint，避免把阶段性实现说明无限堆进核心长期架构目录。

未完成但仍批准的 Stage/生产设计不能因为当前代码不存在而删掉；必须放在 `docs/roadmap/` 或当前适用的核心长期设计中，并明确“待实现”。历史方案若被后续正式决策替代，则保留演进说明并明确“禁止照旧实现”。

迁移/删除旧详细文档前，必须证明：

```text
当前有效事实已有新承载
+ 相关测试/链接已经迁移
+ 未完成阶段已进入 Roadmap
+ 历史原因可从 changes/archive 追溯
```

不能为了目录整洁先删除知识再补。

代码完成前检查系统事实是否变化：

- 模块职责；
- 调用链；
- 输入输出；
- API/Canonical/Job；
- 数据库；
- 配置；
- 日志；
- 启动部署；
- 调试测试；
- 用户行为；
- Roadmap 阶段状态/生产 Go-No-Go。

受影响就在同一任务更新，不受影响不制造文档差异。长期文档描述合并后的当前系统；阶段状态和待实现路线放 Roadmap；历史过程留在 Change/Archive。

正式文档的写法必须从实际问题出发：

```text
为什么需要
→ 输入是什么
→ 输出是什么
→ 数据/调用怎么走
→ 当前代码在哪里
→ 要改这个行为应该改哪里
→ 如何验证/调试
→ 限制/未实现
→ 精确事实源
```

写作要求：

- 假设读者基础一般；
- 面向开发者，也面向需要理解系统技术方案的人；
- 必要术语第一次出现用白话解释；
- 能不用术语就不要为了显得专业而堆术语；
- 是否引用代码、表名、类名、命令，以是否帮助理解/调试为判断标准；
- 允许给短、真实、可验证的例子；
- Provider 真实 JSON 路径、状态机、执行流程、关键 SQL、恢复边界、部署/回滚机制等理解实现必须知道的内容可以在 Appendix 直接展开；
- 固定且精确的数据结构优先导航到 `tables.py`、Contract、Prompt、Migration，避免复制第二套会漂移的 Schema；
- 不复制第二套完整 OpenAPI、Prompt taxonomy 或 Migration SQL；
- 不用“企业级、先进、高可用”等空泛词替代具体机制；
- “当前已实现/当前未实现/已批准待实现/已被替代/默认行为/限制”必须有仓库事实或正式决策依据；
- 迁移文档职责时只迁移位置和结构，不得因为“精简”删除仍然有效的技术细节；
- 用户确认的长期业务/技术决定或明确延期，必须在同一任务落到正式事实源，不能只存在于聊天或 Change 历史。

## 15. Git

任务从最新 `main` 创建分支，前缀可用：

```text
feature/
fix/
hotfix/
refactor/
perf/
docs/
test/
build/
chore/
migration/
revert/
```

名称使用小写英文、数字和连字符，只表达任务内容。禁止工具/模型/人员身份前缀。

禁止：

- `git reset --hard`；
- `git clean -fd`；
- 强制推送；
- 覆盖用户修改；
- 重写共享历史；
- 未授权提交、推送、PR、合并或删分支；
- CI 失败、冲突或结果未确认时强行推进；
- 绕过 Branch Protection 或仓库现有质量门禁。

提交信息使用中文。

## 16. Review 和交付

复杂任务先执行上游 Requirement Completeness Review，再检查当前 Change 的需求符合性，最后检查代码质量。严重和重要问题未解决不得合并。

对 `completion_gate: required` 的 Change，`ready_for_review` 前必须完成 Requirement Traceability、Validation Matrix、Completion Audit，并取得 [`.agents/skills/coding/scripts/ready_check.py`](.agents/skills/coding/scripts/ready_check.py) 与 CI 的机器门禁证据。测试或 CI 绿色不能单独证明正式 Stage / Roadmap 单元完成；某一测试层绿色也不能替代另一层独立风险的验证。

完成结论必须有本轮实际证据。交付至少报告：

- 变更摘要；
- 逐文件/按类别目的；
- 上游 Requirement Traceability 与成功标准；
- Validation Matrix 与各层实际证据；
- Completion Audit / 两阶段 Review；
- Contract/数据库变化；
- 文档同步及依据；
- 实际验证命令、退出码和结果；
- 未验证内容及风险；
- 兼容、依赖、Migration、部署、回滚；
- Roadmap 当前阶段与下一正式单元；
- 分支、提交、PR、CI、合并和清理状态。

禁止只说“已完成”“测试通过”。
