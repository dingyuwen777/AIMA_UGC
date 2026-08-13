---
schema: rvc-change/v1
id: CHG-20260813-repository-bootstrap
title: Stage 1 仓库骨架与工具链初始化
level: L3
status: in_progress
owner: dingyuwen777
branch: build/repository-bootstrap
created: 2026-08-13
updated: 2026-08-13
depends_on: []
affected_areas: [toolchain, platform]
affected_paths: [pyproject.toml, uv.lock, .python-version, .node-version, backend/, frontend/, tests/, scripts/, contracts/, .github/, .gitignore, README.md, docs/blueprint/, changes/active/CHG-20260813-repository-bootstrap/CHANGE.md]
contracts: [HTTP OpenAPI]
data_changes: []
---

# 目标

把当前只有 Blueprint 的 Greenfield 仓库初始化为可安装、可测试、可构建、可生成前端 Client、可运行 CI 的 Stage 1 工程基线，为后续多人并行开发提供同一套机器事实和质量入口。

# 成功标准

- [ ] 根目录是唯一 Python/uv 工程，Python 3.14.7 与 Node 24.19.0 有精确版本声明和锁文件。
- [ ] `backend/src/aima_ugc/` 可以在 `uv sync --locked` 后直接导入，不使用 `PYTHONPATH`、`sys.path` 或第二套 backend 项目。
- [ ] `uv build` 生成的 Wheel 可在隔离环境安装，并能直接 `import aima_ugc`。
- [ ] 最小 FastAPI 应用提供 Blueprint 已定义的 `/health/live`，OpenAPI 中使用稳定 `operation_id`。
- [ ] OpenAPI 可确定性生成到 `contracts/openapi/openapi.json`，并生成可调用的 TypeScript SDK；生成结果可通过当前 Vue/TypeScript 工具链检查和构建。
- [ ] Vue 3 前端同时执行 TypeScript 7 原生 `.ts` 检查和 Vue SFC compatibility API 类型检查，且可 Lint、Unit Test 和 Build。
- [ ] Ruff、mypy、pytest、Contract/质量检查和前端检查可由 CI 在 `linux/amd64` GitHub Hosted Runner 上使用冻结运行时实际执行。
- [ ] CI 只检查当前 Stage 1 已存在能力，不伪造尚未实现的 PostgreSQL、Migration、Docker Release、五平台业务或 E2E 业务流。
- [ ] README 与 Blueprint 同步为实际 Stage 1 机器事实，未决 Stage 0 门禁继续保留。

# 范围

- 建立方案 A 的根 Python 项目、最小 FastAPI package、测试入口和构建配置。
- 建立最小 Vue/TypeScript/Vite/Pinia 前端及其测试、Lint、类型和构建入口。
- 建立 OpenAPI 生成、兼容性基础检查和 TypeScript SDK 生成 PoC。
- 建立 Stage 1 所需最小质量脚本和 GitHub Actions CI。
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

比较 `uv_build`、Hatchling 和 setuptools。当前项目是纯 Python、既定包管理器为 uv、没有 build hook/扩展模块/历史兼容约束，因此使用与冻结 uv 版本一致的 `uv_build`，显式设置 `module-root = "backend/src"`、`module-name = "aima_ugc"`；以实际 Wheel 内容、隔离安装和直接 import 为验收。

## OpenAPI TypeScript SDK

`@hey-api/openapi-ts 0.99.0` 在冻结 Node 24.19.0 + TypeScript 7.0.2 实验中运行时崩溃，读取 `ts.SyntaxKind.AnyKeyword` 时对象为 `undefined`，因此否决。Orval 8.23.0 可成功生成但开发依赖存在 npm 高危漏洞；升级到 Orval 8.24.0 后生产与完整 npm audit 均为 0，Fetch SDK 生成成功，因此当前候选为 Orval 8.24.0，仍以最终 Typecheck/Build 通过为冻结条件。

## TypeScript 7、Vue SFC 与 Lint

实际 CI 证明 `vue-tsc 3.3.9` 直接配 `typescript 7.0.2` 会因 TS7 不导出 `./lib/tsc` 而失败。TypeScript 7.0 官方同时说明其尚无 programmatic API，Vue/Volar 等嵌入式语言工具现阶段需要 TypeScript 6 API；Vue Language Tools 3.3.8 起采用 TS7 + `@typescript/typescript6` 双安装并修复 shim 解析。

因此保留 TypeScript 7.0.2 原生编译器为项目普通 `.ts` 代码门禁，通过 `@typescript/native = npm:typescript@7.0.2` 明确路径执行；`typescript` 名称按官方过渡模式指向 `@typescript/typescript6@6.0.2`，仅供 `vue-tsc` 等需要 JS compiler API 的 Vue SFC 工具使用。不得把后者描述为项目降级到 TS6。两条检查都必须在 CI 成功。

Lint 继续使用已经实际通过的 ESLint + `eslint-plugin-vue`/`vue-eslint-parser` + Babel TypeScript syntax parser；Stage 1 不宣称 type-aware ESLint，类型正确性由上述双类型门禁负责。

# 任务

- [x] 调查当前仓库、AGENTS、Skill、Blueprint、版本快照与 Stage 1 门禁。
- [x] 核验构建后端、SDK 生成器和 TS7/Vue 工具兼容边界的一手资料。
- [x] 建立最小后端/package/测试/Contract/质量脚本。
- [ ] 完成前端双类型门禁、SDK 生成、Lint/typecheck/unit/build。
- [ ] 生成 Python/npm 锁文件和固定生成物。
- [ ] 建立并运行 Stage 1 CI，修复真实失败。
- [ ] 两阶段 Review：需求符合性 → 代码质量。
- [ ] 同步受影响 README/Blueprint 决策。
- [ ] 合并到 `main` 后重新验证集成状态并归档 Change。

# 验证

## 计划

- Python：精确运行时、`uv lock --check`、`uv sync --locked`、直接 import、Ruff、mypy、pytest、`uv build`、隔离 Wheel 安装/import。
- Contract：OpenAPI 生成 `--check`、基础兼容性/operationId 检查、SDK 重新生成后无 diff。
- Frontend：精确 Node/npm、`npm ci`、完整和生产依赖 audit、TS7 原生 `.ts` 检查、Vue SFC compatibility typecheck、Lint、Vitest、Vite Build。
- CI：GitHub Actions `linux/amd64` runner 完整执行上述 Stage 1 门禁并读取 job/log 结果。
- 文档：固定入口、链接、版本/术语和 Stage 1 状态检查。

## 新鲜证据

- Run `31676428866`：冻结运行时与 Python 依赖成功；Red 按正确原因失败，`/health/live` 为 404。
- Run `31676509961`：health Green 通过；`@hey-api/openapi-ts 0.99.0` 在 TS7 下运行崩溃，因此否决。
- Orval 8.23.0 可生成，但 npm audit 暴露 `js-yaml` 高危；按审计修复线改测 8.24.0，不执行 `audit fix --force`。
- Run `31677513245`：Orval 8.24.0 完整/生产 npm audit 均 0；SDK 生成成功；Ruff、mypy、Unit/Contract/API、OpenAPI、架构、Secret、文档检查全部通过；Wheel 构建、隔离安装、直接 import 成功；ESLint 通过。唯一阻塞为 `vue-tsc 3.3.9` 直接读取 TS7 `typescript/lib/tsc` 失败，确认需要官方双安装过渡模式。

# 文档影响

- `README.md`：从“Stage 1 待建立”更新为实际可用工程入口和命令。
- `docs/blueprint/README.md`：更新当前开发状态。
- `docs/blueprint/07-技术决策与实施门禁.md`：修正被实际 CI 推翻的 TS7/vue-tsc 兼容判断，并在最终 PoC 通过后记录 build backend、Orval 和前端 Lint/双类型门禁。
- `docs/blueprint/01-总体架构与技术选型.md`、`04-后端任务API与前端.md`、`06-开发约束与分阶段实施.md`：仅同步受本次实际工具链结果影响的长期事实和验证命令，不改业务架构。

# 交付

- Commit：实现中；最终以 PR head 为准。
- PR：待最终 CI 通过后创建。
- 发布：不涉及生产发布；目标是合并到 `main` 的 Stage 1 工程基线。
