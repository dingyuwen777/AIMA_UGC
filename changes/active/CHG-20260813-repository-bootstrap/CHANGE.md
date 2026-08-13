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
- [ ] OpenAPI 可确定性生成到 `contracts/openapi/openapi.json`，并生成可调用的 TypeScript SDK；生成结果在 TypeScript 7.0.2 下可编译。
- [ ] Vue 3 + TypeScript 前端最小应用可 Lint、Typecheck、Unit Test 和 Build。
- [ ] Ruff、mypy、pytest、Contract/质量检查和前端检查可由 CI 在 `linux/amd64` GitHub Hosted Runner 上使用冻结运行时实际执行。
- [ ] CI 只检查当前 Stage 1 已存在能力，不伪造尚未实现的 PostgreSQL、Migration、Docker Release、五平台业务或 E2E 业务流。
- [ ] README 与 `07` 同步为实际 Stage 1 机器事实，未决 Stage 0 门禁继续保留。

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
- 不因工具兼容问题静默降低 Blueprint 冻结的 TypeScript 7.0.2 或其他已批准版本。

# 必须保持不变

- 方案 A：根目录唯一 Python/uv 项目，源码固定 `backend/src/aima_ugc/`。
- 模块化单体以及 API、Worker、Scheduler、Migration 分进程的长期架构不变；本 Change 只实现 API 的最小可运行入口。
- Python/Node/框架版本以 `docs/blueprint/07-技术决策与实施门禁.md` 的初始化冻结快照为目标，不自动追新。
- Pydantic 是 HTTP Contract 的手写事实源；OpenAPI 和前端 Client 是生成物，不手工维护生成目录。
- 不引入微服务、消息中间件、Redis、多数据库兼容层或运行时插件系统。

# 关键决策

## Python build backend

比较：

1. `uv_build`：与既定 uv 工具链同源，支持显式 `module-root`/`module-name`，当前项目为纯 Python，机制最少。
2. Hatchling：成熟且布局灵活，但当前没有 build hook、扩展模块或复杂打包需求，会增加一套额外构建配置。
3. setuptools：兼容面广，但本 Greenfield 项目没有历史兼容需求，配置和旧式语义更多。

决定：使用与冻结 uv 版本一致的 `uv_build`，显式设置 `module-root = "backend/src"`、`module-name = "aima_ugc"`，以实际 Wheel 内容和隔离安装为验收。

## OpenAPI TypeScript SDK

比较：

1. `@hey-api/openapi-ts 0.99.0`：官方定位直接生成 typed SDK，但在本 Change 的冻结 Node 24.19.0 + TypeScript 7.0.2 实验中运行时崩溃，读取 `ts.SyntaxKind.AnyKeyword` 时对象为 `undefined`，因此否决。
2. `orval 8.23.0`：MIT，官方支持从 OpenAPI 生成类型安全客户端，并有原生 Fetch Client；不增加浏览器运行时 HTTP 依赖。当前作为第二个 PoC 候选，以实际生成、Typecheck 和 Build 结果决定是否冻结。
3. OpenAPI Generator：能力成熟，但需要额外 Java/JAR 工具链，对当前单一 Fetch Client 需求更重。
4. 手写 Fetch Client + 类型生成：会形成手写 HTTP 语义和 OpenAPI 两个事实源，不符合生成 Client 的既定边界。

当前决定：否决 Hey API，不降级 TypeScript；对 Orval 做单变量 PoC，只有实际通过生成、TypeScript 7 编译和前端构建后才把它写入长期 Blueprint。

## TypeScript 7 Lint

比较：

1. `typescript-eslint`：当前官方版本尚不支持 TypeScript 7，强行使用会产生不支持警告或版本约束问题。
2. 降级 TypeScript：会违反 `07` 已冻结 TypeScript 7.0.2，且不是本任务授权的升级/降级决策。
3. ESLint + `eslint-plugin-vue`/`vue-eslint-parser` + Babel TypeScript syntax parser，类型正确性独立由 `vue-tsc` 负责：保持 TS7，Lint 和 typecheck 职责清晰。

决定：采用方案 3。Stage 1 不宣称具备 type-aware ESLint 规则；真实类型门禁由 `vue-tsc` 执行。未来 `typescript-eslint` 正式支持 TS7 后，如需引入，作为独立工具链变更评估。

# 任务

- [x] 调查当前仓库、AGENTS、Skill、Blueprint、版本快照与 Stage 1 门禁。
- [x] 核验 `uv_build`、OpenAPI SDK 生成器和 TypeScript 7 Lint 的官方当前能力。
- [x] 建立最小后端/package/测试/Contract/质量脚本。
- [ ] 建立最小前端、SDK 生成、Lint/typecheck/unit/build。
- [ ] 生成 Python/npm 锁文件和固定生成物。
- [ ] 建立并运行 Stage 1 CI，修复真实失败。
- [ ] 两阶段 Review：需求符合性 → 代码质量。
- [ ] 同步受影响 README/Blueprint 决策。
- [ ] 合并到 `main` 后重新验证集成状态并归档 Change。

# 验证

## 计划

- Python：精确运行时、`uv lock --check`、`uv sync --locked`、直接 import、Ruff、mypy、pytest、`uv build`、隔离 Wheel 安装/import。
- Contract：OpenAPI 生成 `--check`、基础兼容性/operationId 检查、SDK 重新生成后无 diff。
- Frontend：精确 Node/npm、`npm ci`、生产依赖安全审计、Lint、`vue-tsc --noEmit`、Vitest、Vite Build。
- CI：GitHub Actions `linux/amd64` runner 完整执行上述 Stage 1 门禁并读取 job/log 结果。
- 文档：固定入口、链接、版本/术语和 Stage 1 状态检查。

## 新鲜证据

- CI Run `31676428866`（job `94371888881`）：Python 3.14.7、Node 24.19.0、npm 11.17.0、uv 0.12.3 均实际成功；`uv lock` 解析 34 个包并成功 `uv sync --locked`。Red 测试按正确原因失败：`GET /health/live` 返回 404，断言要求 200；1 failed。
- 增加最小 health route 后，CI Run `31676509961`（job `94372141578`）目标测试通过：1 passed；OpenAPI 生成成功；npm 依赖安装成功。
- 同一 Run 在 `@hey-api/openapi-ts 0.99.0` SDK 生成阶段失败：`TypeError: Cannot read properties of undefined (reading 'AnyKeyword')`。该候选因此被证伪，不通过补丁或降低 TypeScript 版本规避。
- CI 的首次完整 npm 安装还报告 4 个 high severity 漏洞；当前增加生产依赖 audit 门禁和完整 audit 诊断，待新的 Orval 依赖树实际结果决定处理，不运行 `npm audit fix --force`。
- 当前执行宿主的 Python/Node/uv 版本与冻结版本不一致且无法联网安装依赖，因此最终依赖、构建和运行时验证以本 Change 的 GitHub Actions 新鲜结果为准，不用本地较旧工具结果代替。

# 文档影响

- `README.md`：从“Stage 1 待建立”更新为实际可用工程入口和命令。
- `docs/blueprint/README.md`：更新当前开发状态。
- `docs/blueprint/07-技术决策与实施门禁.md`：仅在对应 PoC 实际通过后记录 build backend、OpenAPI SDK 和前端 Lint 的已确认 Stage 1 决策，并移除已解决的未决项。
- `01`—`06` 的长期架构和阶段定义不因本次实现而重写；发现真实冲突才最小同步。

# 交付

- Commit：实现中；已创建 `a96b9f5`、`cb6db1b`、`be7eeb8`。
- PR：待最终 CI 通过后创建。
- 发布：不涉及生产发布；目标是合并到 `main` 的 Stage 1 工程基线。
