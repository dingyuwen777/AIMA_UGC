---
schema: rvc-change/v1
id: CHG-20260813-repository-bootstrap
title: Stage 1 仓库骨架与工具链初始化
level: L3
status: done
owner: dingyuwen777
branch: build/repository-bootstrap
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [toolchain, platform]
affected_paths: [pyproject.toml, uv.lock, .python-version, .node-version, backend/, frontend/, tests/, scripts/, contracts/, .github/, .gitignore, README.md, docs/blueprint/, changes/archive/2026-08/CHG-20260813-repository-bootstrap/CHANGE.md]
contracts: [HTTP OpenAPI]
data_changes: []
---

# 目标

把只有 Blueprint 的 Greenfield 仓库初始化为可安装、可测试、可构建、可生成前端 Client、可运行 CI 的 Stage 1 工程基线，为后续多人并行开发提供同一套机器事实和质量入口。

# 成功标准

- [x] 根目录是唯一 Python/uv 工程，Python 3.14.7 与 Node 24.19.0 有精确版本声明和锁文件。
- [x] `backend/src/aima_ugc/` 可以在 `uv sync --locked` 后直接导入，不使用 `PYTHONPATH`、`sys.path` 或第二套 backend 项目。
- [x] `uv build` 生成的 Wheel 可在隔离环境安装，并能直接 `import aima_ugc`。
- [x] 最小 FastAPI 应用提供 Blueprint 已定义的 `/health/live`，OpenAPI 中使用稳定 `operation_id`。
- [x] OpenAPI 可确定性生成到 `contracts/openapi/openapi.json`，并由 Orval 8.24.0 生成可调用 Fetch Client；生成结果通过 TS7 native、Vue SFC typecheck 和 Vite Build。
- [x] Vue 3 前端同时执行 TypeScript 7 原生 `.ts` 检查和 Vue SFC compatibility API 类型检查，并通过 Lint、Unit Test 和 Build。
- [x] Ruff、mypy、pytest、Contract/质量检查和前端检查已由 `linux/amd64` GitHub Hosted Runner 使用冻结运行时实际执行。
- [x] CI 只检查当前 Stage 1 已存在能力，不伪造尚未实现的 PostgreSQL、Migration、Docker Release、五平台业务或业务 E2E。
- [x] README 与 Blueprint 已同步为实际 Stage 1 机器事实，未决 Stage 0 门禁继续保留。

# 范围

- 建立方案 A 的根 Python 项目、最小 FastAPI package、测试入口和构建配置。
- 建立最小 Vue/TypeScript/Vite/Pinia 前端及其测试、Lint、类型和构建入口。
- 建立 OpenAPI 生成、兼容性基础检查和 TypeScript Fetch Client 生成。
- 建立 Stage 1 所需最小质量脚本、GitHub Actions CI、CODEOWNERS 和 PR 模板。
- 生成并提交 `uv.lock`、`frontend/package-lock.json`、固定 OpenAPI 和前端 generated client。
- 同步根 README、Blueprint 导航和 `07` 中已经通过 PoC 的 Stage 1 决策。

# 非目标

- 不实现 TikHub、五平台 Mapper、业务数据库表、Alembic Revision、Auth、Job Runtime、Scheduler 或业务页面。
- 不实现生产 Docker/Compose/Release/Backup；容器基础镜像 variant 仍属于未决门禁。
- 不提前创建七个业务模块的空文件或无真实用途的抽象层。
- 不修改 Stage 0 的产品、隐私、容量、SLO/RPO/RTO、平台能力和 Scheduler misfire 业务决策。
- 不用降级整个前端到 TypeScript 6 的方式规避 TS7 生态约束。

# 必须保持不变

- 方案 A：根目录唯一 Python/uv 项目，源码固定 `backend/src/aima_ugc/`。
- 模块化单体以及 API、Worker、Scheduler、Migration 分进程的长期架构不变；本 Change 只实现 API 的最小可运行入口。
- Python/Node/框架版本以 `docs/blueprint/07-技术决策与实施门禁.md` 的初始化冻结快照为目标，不自动追新。
- Pydantic 是 HTTP Contract 的手写事实源；OpenAPI 和前端 Client 是生成物，不手工维护生成目录。
- 不引入微服务、消息中间件、Redis、多数据库兼容层或运行时插件系统。

# 关键决策

## Python build backend

比较 `uv_build`、Hatchling 和 setuptools。当前项目是纯 Python、既定包管理器为 uv、没有 build hook/扩展模块/历史兼容约束，因此使用与冻结 uv 版本一致的 `uv_build 0.12.3`，显式设置 `module-root = "backend/src"`、`module-name = "aima_ugc"`。实际 CI 已验证 Wheel 构建、隔离安装和直接 import。

## OpenAPI TypeScript Client

`@hey-api/openapi-ts 0.99.0` 在冻结 Node 24.19.0 + TypeScript 7.0.2 实验中运行时崩溃，因此否决。Orval 8.23.0 可生成但开发依赖存在 npm 高危漏洞；升级到 Orval 8.24.0 后完整与生产 npm audit 均为 0。最终使用 Orval 8.24.0 的 Fetch Client，单文件生成到 `frontend/src/generated/api/client.ts`，仅启用 `includeHttpResponseReturnType: false`。`forceSuccessResponse` 在真实 FastAPI OpenAPI 下会产生未定义成功类型别名，已按 Orval 默认语义移除。生成代码通过 TS7、Vue typecheck 和 Vite Build。

Orval 为开发期工具，不增加浏览器运行时 HTTP 依赖；采用 Fetch 是因为浏览器已有原生实现。替代方案 OpenAPI Generator 会额外引入 Java/JAR 工具链；手写 Fetch Client 会形成第二套 HTTP 事实源。Orval 及当前直接前端工具依赖由 `package-lock.json` 固定，本轮完整 npm audit 为 0。

## TypeScript 7、Vue SFC 与 Lint

实际 CI 证明 `vue-tsc 3.3.9` 直接配 `typescript 7.0.2` 会因 TS7 不导出 `./lib/tsc` 而失败。TypeScript 7.0 官方说明其暂时没有 programmatic JS API，Vue/Volar 等嵌入式语言工具仍需 TypeScript 6 API；Vue Language Tools 当前采用同类双安装过渡模型。

因此保留 TypeScript 7.0.2 native compiler 为普通 `.ts` 代码门禁，通过 `@typescript/native = npm:typescript@7.0.2` 明确路径执行；包名 `typescript` 指向 `@typescript/typescript6@6.0.2`，只供 `vue-tsc` 等需要 JS compiler API 的 Vue SFC 工具使用。`npm run typecheck` 同时执行两条检查，不能把 compatibility API 描述为项目降级到 TS6。

Lint 使用 ESLint 10.8.0 + `eslint-plugin-vue` 10.10.0 + `vue-eslint-parser` 10.4.1 + Babel TypeScript syntax parser。当前 `typescript-eslint` 尚未正式支持 TS7，因此不强行引入；Stage 1 不宣称 type-aware ESLint，类型正确性由双类型门禁负责。

## 安全与依赖

- Python 与 npm 直接依赖均精确声明，传递依赖由 Lock 固定；
- Orval 8.23.0 的开发依赖高危问题未通过 `audit fix --force` 绕过，而是切换到 8.24.0 后重新完整验证；
- 最终 bootstrap CI、正式 PR CI 和合并后 `main` CI 的生产与完整 npm audit 都为 0 vulnerabilities；
- npm 安装仍提示上游传递依赖 `glob@10.5.0` 已 deprecated，以及 `esbuild` install script allow-scripts 提示；当前完整 audit 为 0 且 Vite production Build 成功。这些是上游工具链告警，不通过无依据 overrides/强制升级掩盖，后续只有出现可验证风险或上游正式替代时再独立处理。

# 任务

- [x] 调查当前仓库、AGENTS、Skill、Blueprint、版本快照与 Stage 1 门禁。
- [x] 核验构建后端、SDK 生成器和 TS7/Vue 工具兼容边界的一手资料。
- [x] 建立最小后端/package/测试/Contract/质量脚本。
- [x] 完成前端双类型门禁、SDK 生成、Lint/typecheck/unit/build。
- [x] 生成 Python/npm 锁文件和固定生成物。
- [x] 用 bootstrap CI 建立并验证 Stage 1 机器事实。
- [x] 同步受影响 README/Blueprint 决策。
- [x] 用正式只读 PR CI 再验证最终 diff。
- [x] 两阶段 Review：需求符合性 → 代码质量。
- [x] 合并到 `main` 后重新验证集成状态并归档 Change。

# 验证

## 计划

- Python：精确运行时、`uv lock --check`、`uv sync --locked`、直接 import、Ruff、mypy、pytest、`uv build`、隔离 Wheel 安装/import。
- Contract：OpenAPI 重新生成无漂移、基础 operationId 检查、Orval Client 重新生成无漂移。
- Frontend：精确 Node/npm、`npm ci`、完整和生产依赖 audit、TS7 native `.ts` 检查、Vue SFC compatibility typecheck、Lint、Vitest、Vite Build。
- CI：正式 GitHub Actions PR workflow 使用只读权限执行完整 Stage 1 门禁；合并后在 `main` push 上再次执行同一门禁。
- 文档：固定入口、链接、版本/术语和 Stage 1 状态检查。

## 新鲜证据

- Run `31676428866`：冻结运行时与 Python 依赖成功；Red 按正确原因失败，`/health/live` 为 404。
- Run `31676509961`：health Green 通过；`@hey-api/openapi-ts 0.99.0` 在 TS7 下运行崩溃，因此否决。
- Orval 8.23.0 可生成，但 npm audit 暴露 `js-yaml` 高危；按审计修复线改测 8.24.0，不执行 `audit fix --force`。
- Run `31677513245`：Orval 8.24.0 完整/生产 npm audit 均 0；SDK、后端、Wheel、ESLint 已通过，暴露 `vue-tsc` 直接消费 TS7 programmatic API 不成立。
- Run `31678378543` / job `94377944065`：最终 bootstrap 全绿。Python 3.14.7、Node 24.19.0、npm 11.17.0、uv 0.12.3；Ruff/mypy、Unit 1、Contract 1、API 1、OpenAPI/架构/Secret/文档检查；Wheel 构建与隔离安装；完整和生产 npm audit 均 0；Orval 8.24.0 SDK；ESLint；TS7 native；`vue-tsc` compatibility；Vitest 1 file/2 tests；Vite 8.2.1 production Build；Playwright 1.62.1 CLI 全部通过。
- 同一 Run 生成并提交机器事实 commit `6aad0c139bf08cc2573003eeb40cbb53924e3d40`：`uv.lock`、`frontend/package-lock.json`、固定 OpenAPI、生成 Fetch Client。
- PR #1 正式只读 CI Run `31679196892` / job `94380511793` 全绿：从已提交 Lock 使用 `uv sync --locked` 与 `npm ci` 安装；完整/生产 npm audit 通过；OpenAPI 与 Orval Client 重新生成后 `git diff --exit-code` 无漂移；后端/仓库检查、Wheel、前端双类型检查、Vitest、Vite Build 和 Playwright CLI 全部通过。
- PR #1 head `9226afba488ea6432144b3d4548b9efd002a9476` 的只读 CI Run `31679370068` / job `94381059683` 全绿；Review 记录更新后的最终 head `0ec3949a9475ea6d473a7b6cc4eb5d626b4d2d93` 的 CI Run `31679712922` / job `94382150503` 再次全绿，所有 Stage 1 业务步骤 success。
- 两阶段 Review（基于最终 `main...build/repository-bootstrap` diff）：需求符合性未发现 Stage 2、TikHub、Schema、Auth、Job/Scheduler 等越界实现；成功标准均有代码/测试/CI/文档对应。代码质量复核了 `pyproject.toml`、只读 CI、FastAPI health Contract、Orval 配置、TypeScript 双类型链、生成脚本和完整 diff；未发现严重或重要问题，未引入并行实现、无关重构或凭据。
- PR #1 以 squash 方式合并，`main` 提交 `bcc920650d7b868830497b9d6c32d02aa74ac54b`。合并后主分支 CI Run `31679816136` / job `94382471521` 全绿：锁定环境、audit、生成物零漂移、后端/仓库检查、Wheel 与前端检查全部 success。

# 文档影响

- `README.md`：已更新为 Stage 1 实际工程入口、命令和下一阶段。
- `docs/blueprint/README.md`：已更新为 Stage 1 完成、Stage 0 + Stage 2 并行的当前状态。
- `docs/blueprint/07-技术决策与实施门禁.md`：已从 1.1 更新为 1.2，修正 TS7/vue-tsc 假设，并记录 `uv_build`、Orval、双类型门禁和 Lint 的已验证方案。
- `docs/blueprint/01-总体架构与技术选型.md`：复核后无需修改；其“Vue 3 + TypeScript”“根 Python 工程”“生成 Client”等架构级描述仍然正确，精确工具链应只在 `07`/Lock 维护。
- `docs/blueprint/04-后端任务API与前端.md`：复核后无需修改；其 Pydantic → FastAPI OpenAPI → 固定 OpenAPI → TypeScript Client 的契约边界与本次实现一致。
- `docs/blueprint/06-开发约束与分阶段实施.md`：复核后无需修改；统一命令仍是 `npm run typecheck`，具体双编译器实现属于 `package.json` 与 `07` 的工具链事实；阶段定义不改写成历史流水账。

# 交付

- Commit：PR #1 squash merge commit `bcc920650d7b868830497b9d6c32d02aa74ac54b`；机器事实生成 commit `6aad0c1` 保留在 PR 历史与本 Change 证据中。
- PR：#1 `建立 Stage 1 仓库骨架与工具链` 已合并。
- CI：PR 最终 CI `31679712922` 全绿；合并后 `main` CI `31679816136` 全绿。
- 发布：不涉及生产发布；本 Change 建立可继续开发的 Stage 1 工程基线并完成归档。
