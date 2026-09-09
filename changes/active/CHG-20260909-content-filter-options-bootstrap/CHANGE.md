---
schema: coding-change/v1
id: CHG-20260909-content-filter-options-bootstrap
title: 声音广场动态筛选目录与空库 Analysis 基线
level: L3
status: ready_for_review
owner: dingyuwen777
branch: fix/content-filter-options-bootstrap
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - content
  - administration
  - api
  - contracts
  - frontend
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/contracts/http.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/voice-plaza/
  - frontend/src/features/admin-configuration/
  - tests/
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - backend/src/aima_ugc/modules/analysis/README.md
  - frontend/README.md
  - docs/03_API接口说明.md
  - docs/product/02_当前产品能力与用户流程.md
  - docs/appendix/07_AI舆情打标与分析实现.md
  - changes/active/CHG-20260909-content-filter-options-bootstrap/CHANGE.md
contracts:
  - Content Filter Options HTTP Contract
  - Analysis bootstrap Prompt selection
data_changes: []
---

# 变更摘要

- **要解决的问题**：声音广场把平台、相关性、状态和内容类型等选项写在前端，分类筛选只读取 active Scheme，导致数据库当前仍可见的历史分类无法选择；管理员页又优先展示草稿，容易把未生效规则误认为当前规则。空库 Prompt 路径与版本也在 Python 中固定为 V4。
- **拟议修改**：建立独立只读筛选目录，合并后端正式枚举、active Scheme 和当前有效内容投影；管理员页默认选择 active Version；空库 bootstrap 通过版本无关、受校验的基线指针选择版本化 Prompt。保留现有 Taxonomy 的“当前合法分类”语义。
- **预期结果**：前端筛选选项不再维护第二份业务值，历史有效值仍可筛选且明确标为历史；新空库基线进入数据库后由管理员页展示，已有数据库配置和历史结果保持不变。

# 背景、现状与问题

## 已确认事实

| 证据编号 | 已确认事实 | 来源 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | `list_analysis_schemes()` 会在数据库完全没有 Scheme 时调用 `bootstrap_default()`，从 Git Prompt 建立并发布首个数据库 Version | `backend/src/aima_ugc/bootstrap/administration_http.py`、`backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py` | Prompt 是空库输入，管理员页与运行时仍以数据库为事实源 |
| E2 | 管理员页当前在原选择失效时优先查找 `draft`，而不是 `active_version_id` | `frontend/src/features/admin-configuration/pages/AdminConfigurationPage.vue` | 首次进入可能展示未生效规则 |
| E3 | 声音广场平台、相关性、状态和内容类型存在前端业务值；情感、发声类型、标签只读取 active Taxonomy | `frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/VoicePlazaFilters.vue` | 前端存在重复维护，历史分类可能不可选 |
| E4 | 内容列表读取当前 Content Version、active source、最新 Analysis、人工相关性和人工分类锁的 effective 投影 | `backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py` | 筛选目录必须复用同一有效值语义，不能做无边界全表 DISTINCT |
| E5 | `content-analysis-taxonomy` 表示 active Scheme 的合法分类，并被人工分类纠正消费 | `backend/src/aima_ugc/bootstrap/analysis_taxonomy_http.py`、`frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue` | 历史值不能混入该接口冒充当前合法分类 |
| E6 | 当前 Python 常量直接指向 `content_labeling_v4.md` 并固定 `content-labeling.v4` | `backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py` | 后续基线版本容易遗漏同步，选择入口需要版本无关 |
| E7 | 当前 `main` 与 `origin/main` 均为 `975814ff`；工作区已有一份用户未提交的 Figma 指南修改 | `git status --short --branch`、`git rev-parse main origin/main` | 本次提交必须排除并保留该用户修改 |

## 推断与待确认

- 仓库外生产数据库的 active Scheme、历史 Taxonomy 和实际内容类型数量未读取；本次只实现对任意合法数据库状态都成立的投影，不声称已审计生产数据。
- 当前基线选择采用显式、版本无关的指针文件，而不是自动取最高版本号；这样新增实验 Prompt 文件不会未经批准自动成为空库基线。实现测试必须证明指针、文件名与 Prompt 内声明一致。

# 目标、成功标准与非目标

## 成功标准

- [x] 新空库从版本无关基线指针选择版本化 Prompt，写入数据库并由管理员接口返回；已有 active Scheme 不被覆盖。
- [x] 新的 Filter Options Contract 清楚区分当前 active 分类与仅来自当前有效历史结果的分类值，保持真实一级/二级父子关系。
- [x] 内容类型来自当前有效 Content；平台、相关性与分析状态由后端正式 Contract 投影，前端不再维护业务值数组或静态 `<option>`。
- [x] 声音广场筛选消费 Filter Options；人工分类纠正仍消费 active Taxonomy，旧接口语义不变。
- [x] 管理员页首次默认选择 active Version，明确展示“当前生效”和“草稿，尚未生效”，产品术语使用“AI 分析原则”。
- [x] 声音广场继续使用“相关性、情感、状态、发声类型、一级标签、二级标签”等无 `AI` 前缀术语，直接相关文档与实现一致。
- [x] Contract、PostgreSQL、浏览器模拟、真实跨层、生成客户端、构建、文档、完成审计和独立复核均已建立对应实现与检查；最新 PR HEAD 的 PostgreSQL/Full-stack/CI 结果仍是合并 `main` 前的硬门禁，不在 Ready 文档中预先冒充通过。

## 范围

- Analysis 空库 Prompt 基线选择与 bootstrap 回归。
- Content Filter Options 只读 Contract、查询投影和 HTTP 路由。
- 声音广场筛选数据源、历史标记和级联行为。
- 管理员配置默认 active Version 与相关产品文案。
- 直接相关测试、OpenAPI/Orval 生成物和技术文档。

## 非目标

- 不修改数据库 Schema 或历史 Migration。
- 不更新、映射或重写历史 Analysis Result/Label Pair。
- 不把历史分类加入当前 active Taxonomy 或人工纠正合法值。
- 不升级依赖、Runtime、框架或部署方案。
- 不审计或修改仓库外生产数据库。
- 不修改或提交用户现有的 `docs/guides/01_Figma与前端设计开发工作流.md` 工作区差异。

## 必须保持不变

- PostgreSQL 唯一 active Analysis Scheme 是运行时当前原则的唯一事实源。
- 既有数据库不因代码升级自动切换 Scheme；发布与回滚仍由管理员显式操作。
- Content 列表的 current Version、active source、latest Analysis、manual override 和 relevance review 语义不变。
- `GET /api/v1/content-analysis-taxonomy` 继续只返回当前合法 Taxonomy；车型继续读取 Vehicle Catalog API。
- Pydantic → OpenAPI → Orval generated client 类型链不变，生成目录不手改。

# 修改方案与决策依据

1. 基线选择
   → 修改范围：Prompt 选择器、版本化 Prompt 资产与测试
   → 预期结果：Python 不再固定 V4 文件名或 Prompt Version；显式指针选择当前空库基线并 fail closed
   → 验证：指针解析、路径约束、版本一致性、Wheel 包内容与 bootstrap 测试
2. 筛选目录
   → 修改范围：HTTP Contract、Content Query Repository、Content HTTP Service/API
   → 预期结果：后端返回正式枚举、实际 `content_type`、active + historical effective 分类及来源
   → 验证：Contract/API 与 PostgreSQL 集成，覆盖旧 Scheme、最新 Analysis、人工锁与 active source
3. 前端消费
   → 修改范围：OpenAPI/Orval、Voice Plaza API/Store/Filters、管理员页
   → 预期结果：筛选项不写死；历史值可见；管理员默认 active 并区分草稿
   → 验证：Vitest、Browser Mock、Full-stack 用户路径、TypeScript/Vue 构建
4. 文档与交付
   → 修改范围：Analysis README、AI Appendix、Frontend README、Change
   → 预期结果：说明 active Taxonomy 与可筛选数据空间的职责、空库基线和术语
   → 验证：Docs/链接/事实检查、完成审计、独立复核、CI、合并后 main 复验

## 备选方案与取舍

- 不采用“自动选择目录中最高 V 号”：未完成或实验 Prompt 一旦进入包就可能静默成为空库生产基线。
- 不采用“把历史值并入 content-analysis-taxonomy”：会让仅用于历史查询的值重新成为当前 AI/人工纠正合法值。
- 不采用“前端读取 Prompt 文件”：绕过数据库唯一 active Scheme，并在部署与既有数据库之间形成双事实源。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 空库基线版本无关地选择版本化 Prompt，写入数据库后由管理员页读取；已有 active Scheme 不覆盖 | #412 / AC1 | satisfied | `content_labeling_bootstrap.txt`、`resolve_content_labeling_prompt_path()` 与指针/版本 fail-closed 测试；PostgreSQL 集成测试把指针所选 Prompt 按生产函数编译后与空库 Version 的 definition、compiled prompt 和两个 hash 完整对照；既有 `bootstrap_default()` 仍先返回 active Version。 |
| R2 | 新增独立 Filter Options API，保持 active Taxonomy 的当前合法分类语义 | #412 / AC2 | satisfied | 新增 `GET /api/v1/content-filter-options`、Pydantic/OpenAPI/Orval Contract；人工纠正与 `ContentDetailDrawer` 仍消费 `GET /api/v1/content-analysis-taxonomy`。 |
| R3 | 后端合成正式枚举、active Scheme 与当前数据库有效历史值，历史值标记，内容类型来自当前有效 Content | #412 / AC3 | satisfied | `PostgresContentQueryRepository.list_filter_values()` 复用 current Version、active source、latest Analysis 与 manual override 投影；集成测试覆盖旧 Scheme 值、人工锁替换和 `note` 内容类型；API/前端断言 `active`/`historical` 来源。 |
| R4 | 声音广场不硬编码业务选项；车型与人工纠正各自继续消费既有正确事实源 | #412 / AC4 | satisfied | 八个动态下拉均由 Filter Options 响应生成；车型仍使用 Vehicle Catalog，人工纠正仍使用 active Taxonomy；筛选目录不可用时动态下拉全部禁用而内容列表保持可用。 |
| R5 | 管理员页默认 active Version，区分生效/未生效，使用“AI 分析原则” | #412 / AC5 | satisfied | `loadSchemes()` 按 `active_version_id` 选中；`schemeVersionStateLabel()` 区分“当前生效”与“草稿，尚未生效”；管理员组件、Browser Mock 与 Full-stack 定位同步。 |
| R6 | 保留无 AI 前缀的声音广场产品术语，并同步直接相关文档 | #412 / AC6 | satisfied | 声音广场继续展示“相关性、情感、状态、发声类型、一级标签、二级标签”；Analysis/Frontend README、API、Product 与 AI Appendix 已同步事实源职责。 |
| R7 | 无 Schema/历史结果/依赖变化；完整验证、审计、复核与 CI 后合并 main | #412 / AC7 | satisfied | 最终 diff 无 Migration/依赖/历史结果改写；本地 Contract 104、API 55、目标后端 25、Vitest 134、Browser Mock 105、lint/typecheck/build、mypy、Ruff、生成物、Wheel 与质量门禁已执行；PR current-head PostgreSQL/Full-stack/CI 仍作为合并硬门禁。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Prompt 指针 fail-closed、分类合并顺序/来源、管理员默认选择、筛选级联与清理 |
| 接口 / 契约 | required | 新 Response、路由 operation_id、OpenAPI、Orval、旧 Taxonomy 兼容 |
| 后端 / API / PostgreSQL 集成 | required | current/effective/latest/manual/active-source 历史值与内容类型真实投影 |
| 浏览器 / 界面模拟验收 | required | 所有声音广场下拉由接口驱动、历史标记、管理员生效/草稿表达 |
| 真实跨组件关键路径 | required | 空库 bootstrap → 管理员展示；新旧 Scheme 结果 → 声音广场筛选 |
| 外部依赖 / 供应方探测 | not_applicable | 不调用真实 LLM/Provider，目标只涉及本地 Prompt、数据库、API 与前端消费 |
| 构建 / 打包 / 运行 | required | Python 静态检查与 Wheel、前端 lint/typecheck/build、相关运行测试 |
| 文档 / 治理 / 其他 | required | targeted 文档、生成物一致性、Change Completion、独立 Review、CI 与 Git 结果 |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理方式 |
| --- | --- | --- |
| 主要风险 | 筛选目录与列表 effective 语义漂移，或大数据量查询退化 | 复用列表基础投影与数据库 DISTINCT；PostgreSQL 集成覆盖人工锁、历史值和来源可见性，并审查查询形状 |
| 兼容性 | 新增接口；旧 Taxonomy 和既有列表参数保持兼容 | 不删改旧字段、路径和状态；前端只切换筛选数据源 |
| 数据 / Migration | 不需要 | 只读聚合与空库既有 bootstrap 行为，不修改表结构或历史数据 |
| 依赖 / Runtime | 不变 | 只使用标准库与现有 SQLAlchemy/Vue 能力 |
| 部署 / 运行 | 随正常应用发布 | 新空库读取包内基线指针；既有库仍使用数据库 active Scheme |
| 回滚 / 恢复 | 可回滚代码 | 新接口和前端消费可随提交回滚；没有不可逆数据变更 |

# 文档影响

Docs Impact 为 `targeted`：只更新 Analysis 模块 README、AI 实现 Appendix 和 Frontend README 中直接描述 Prompt bootstrap、Taxonomy/筛选事实源或旧筛选术语的段落；不改用户当前未提交的 Figma 指南，也不重写无关 Blueprint、Roadmap 或 Operations。

# 执行清单

- [x] 恢复当前实现、上游需求、Git 状态和相关事实源
- [x] 建立 Issue、任务分支、需求追溯和验证矩阵
- [x] 为新增行为建立失败测试并确认按目标失败
- [x] 完成最小实现与生成物，不扩大范围
- [x] 同步直接相关文档并复核事实链接
- [x] 取得当前合并态的目标、相关和本地可运行门禁证据
- [x] 完成 Requirement/Completion Audit 与独立 Review
- [ ] CI 全绿后合并 main、复验并清理任务分支

# 完成审计

- [x] upstream_re_read：已重新读取 #412 AC1–AC7、用户关于未来 V5 不得硬编码的补充、系统性核对结论、Analysis/Content/Frontend 实现与直接相关文档，并在最新 `origin/main@bd3e6c1b` 合并态重建完成定义。
- [x] change_coverage：已从 #412 的七条 Acceptance 逐项反查指针、数据库 bootstrap、Filter Options、管理员默认选择、声音广场数据源、产品术语、测试与文档，没有用本 Change 代替上游需求。
- [x] reverse_audit：已执行 Prompt 指针 → Prompt loader → 空库 DB Version → 管理员页、Content current/effective 投影 → Filter Options API → 动态下拉 → 既有查询参数，以及 active Taxonomy → 人工纠正的反向能力审计。
- [x] unresolved_cleared：所有 Requirement 均有实现与本地证据，PostgreSQL/真实 Full-stack 由于本机缺少隔离数据库 Secret 明确交由 PR current-head CI 验证，CI 失败时禁止合并。

# 两阶段 Review

- **需求与风险重建**：PASS。以 #412 AC1–AC7、用户 V5 补充、数据库 Scheme/Run 冻结、Content effective 投影和前端消费边界重新确认范围；主要风险是历史值泄漏旧 Content/失效来源、人工锁失真、Filter Options 与人工纠正 Taxonomy 混用、异步旧响应覆盖新目录及辅助 API 阻塞内容列表。
- **实现与证据对照**：首轮发现并修复四项问题：Filter Options 不可用时四个后端驱动下拉仍可操作、并发刷新可能被旧响应覆盖、慢人工纠正 Taxonomy 阻塞首屏内容、Full-stack 管理员用例仍定位旧文案。首次 Ready CI 又发现新增 PostgreSQL 测试错误地把原始 Prompt 文件 Hash 与生产编译快照 Hash 直接比较；第二轮进一步暴露管理员安全响应本就不包含内部 `compiled_prompt`。测试现已调用生产编译函数，通过管理员响应核对页面可见 definition/hash，并通过 Owner Repository 核对数据库内部 compiled prompt，未修改生产实现。
- **测试充分性结论**：指针选择与 fail-closed、接口错误、active/historical 合并、人工锁、异步竞态、目录降级、管理员 active 默认、动态下拉及 Browser Mock 用户路径均有直接断言。修正后的隔离 PostgreSQL 与真实 Full-stack 仍由下一轮 PR current-head CI 提供最终证据。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 失败测试提交前工作树 / Windows | `npm --prefix frontend run test -- --run tests/voice-plaza.spec.ts`；`npm --prefix frontend run test:e2e -- voice-plaza.spec.ts` | 新增断言按预期失败：动态下拉仅 4 个禁用而预期 8 个、旧 Filter Options 响应覆盖新响应、慢 Taxonomy 阻塞列表、Filter Options 失败后平台仍可操作 | 先直接暴露首轮实现的竞态、首屏依赖和降级缺口，再完成修复 |
| V2 | `c44763fa` 合并态 / Python 3.14.7 / Windows | `uv run pytest tests/unit/analysis/test_analysis_relevance_voice_v4.py tests/contracts/test_user_voice_single_source_contract.py tests/api/test_stage8d_contents.py -q` | 25 passed | Prompt 指针/V5 演进、Taxonomy Contract、Filter Options API 与错误语义通过目标回归 |
| V3 | `c44763fa` 合并态 / Python 3.14.7 / Windows | `uv run pytest tests/unit -q` | 903 passed、8 skipped；仅 `tests/unit/test_prepare_host.py` 3 个 POSIX 专用用例因 Windows 无 `os.geteuid/os.chown` 失败 | 本次 Analysis/Content 单元回归全部通过；保留与当前 diff 无关且 CI Linux 可判定的宿主差异，不修改测试伪造全绿 |
| V4 | `c44763fa` 合并态 / Python 3.14.7 / Windows | `uv run pytest tests/contracts -q`；`uv run pytest tests/api -q` | 104 passed；55 passed | 完整 Contract 和 API 回归通过，新接口未破坏现有 HTTP Contract |
| V5 | 当前工作树 / 锁定 Ruff、mypy | CI 同款 `ruff format --check` + `ruff check`；`uv run mypy backend/src` | 647 个文件格式通过、lint 通过；319 个 source 无类型错误 | Python 格式、静态质量和类型边界通过；首轮发现的 16 个混合换行文件已定向格式化 |
| V6 | `c44763fa` 合并态 / Node 24.19.0 / npm 11.17.0 | `npm --prefix frontend run test -- --run`；`lint`；`typecheck`；`build` | 23 files / 134 tests、lint、TS7 + vue-tsc、Vite build 全通过；172 modules transformed | Store 竞态、下拉降级、管理员默认选择、生成客户端消费和正式构建通过 |
| V7 | `c44763fa` 合并态 / Chromium / Playwright | `npm --prefix frontend run test:e2e` | 105 passed | 全量 Browser Mock 验证动态目录、历史标记、首屏依赖、失败降级和现有用户路径 |
| V8 | 当前工作树 / Contract 与 Wheel | `uv run python scripts/contracts/generate.py --check`；`uv build --wheel`；归档目录检查 | 生成物一致；Wheel 构建成功并包含 `content_labeling_bootstrap.txt` 与 V1–V4 Prompt | Pydantic → OpenAPI → Orval 链一致，新空库基线选择资产进入发布包 |
| V9 | 当前工作树 / 项目质量脚本 | `check_architecture.py`、`check_table_ownership.py`、`check_docs.py`、`scan_secrets.py` | 均退出码 0 | 架构、表 Owner、文档和 Secret 边界未发生违规漂移 |
| V10 | 当前工作树相对 `origin/main@bd3e6c1b` | `git diff --check`、两阶段 Review、反向调用链审计 | diff check 通过；首轮 4 项 Finding 已修复，复查无剩余范围内阻塞 Finding | 修改保持增量、无 Migration/依赖/历史结果改写，且覆盖最新 main 合并态 |
| V11 | PR heads `f462d692`、`639a015c` / GitHub Actions PostgreSQL 18.4 | CI runs `34331967733`、`34333368591` 的 PostgreSQL Integration | 两轮均 49 passed、1 failed；先后暴露 raw/compiled Prompt Hash 混淆，以及安全 HTTP Response 不暴露内部 `compiled_prompt` 的错误测试假设；首轮真实 Full-stack 已通过 | 生产空库 bootstrap 已执行，失败均位于本次新增断言；最终测试改为分别验证管理员安全投影与 Owner Repository 内部快照，等待下一轮 current-head CI |

## 未验证内容与剩余风险

- 本机缺少 `.runtime/secrets/postgres_password`，没有启动或重置用户数据库，因此 PostgreSQL 集成与真实 Full-stack 未在本机执行；PR current-head CI 必须提供隔离 PostgreSQL 18 和真实跨层的最终证据，任何失败都会阻止合并。
- 仓库外生产数据库的 active Scheme、历史分类种类、内容类型规模和查询性能未审计；本次实现对合法数据库状态建模，不声称已量化生产数据，也不操作生产环境。
- 完整后端单元在 Windows 的 3 个失败只涉及既有 Linux host preparation 测试对 `os.geteuid/os.chown` 的直接 monkeypatch；本次未改该模块，最终以 Linux CI 同命令为准。

## 交付状态

- 提交：治理 `7190107f`、实现 `d944c9f7`、审查修复 `4c43fc1d`、最新 main 合并态 `c44763fa`、完成证据 `f462d692`；PostgreSQL 测试期望修复随下一提交推送。
- 拉取请求：Draft PR #413，`Requirement-Source: #412`。
- CI：前两轮 Ready 的质量阶段、Compose 与开发工具链均通过；PostgreSQL 先后由新增 raw/compiled Prompt Hash 混淆及安全 Response 字段误用阻塞，均已按真实生产边界修正，等待下一轮 current-head 全量复验。
- 合并：任务分支已无冲突同步 `origin/main@bd3e6c1b`，待 current-head required checks 全绿后执行受保护合并。
- Change 归档：待合并后由 repository-native Change Archive 处理。
- 发布 / 部署：不在本次请求范围；无额外 Migration 或停机步骤。
