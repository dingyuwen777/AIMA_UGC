---
schema: coding-change/v1
id: CHG-20260930-000659-content-labeling-v3
title: 收敛唯一内容打标 Prompt 与 v3.0 格式协议
level: L3
status: done
owner: assistant
branch: refactor/674-content-labeling-v3
created: 2026-09-30 00:06:59 +08:00
updated: 2026-09-30
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - administration
  - frontend
  - developer-tooling
  - testing
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/analysis
  - backend/src/aima_ugc/adapters/llm
  - frontend/src/features/admin-configuration
  - frontend/tests
  - frontend/e2e
  - scripts/dev
  - scripts/performance
  - tests/unit/analysis
  - tests/unit/test_validate_changed.py
  - tests/integration/content
  - tests/integration/database
  - tests/contracts
  - docs/appendix
contracts:
  - content-labeling.v3.0 prompt and output protocol
  - analysis scheme taxonomy definition
data_changes:
  - deployment prerequisite to clear legacy analysis schemes and labeling results
---

# 变更摘要

- **要解决的问题**：多份历史内容打标 Prompt、历史协议兼容和前端旧兜底标签注入形成多套事实，可能使 Git bootstrap、数据库 Scheme、模型输出校验和页面展示不一致。
- **拟议修改**：只保留 `content_labeling.md`，把当前唯一格式标记设为 `content-labeling.v3.0`，删除旧 Prompt/协议兼容和旧竞品筛选 Prompt；保留 `zhengfu_shaixuan.md`；前端原样显示当前 Scheme 的 9 个一级、39 个二级标签。
- **预期结果**：空库只从唯一 Prompt 建立 active Scheme，模型按业务 Owner 提供的完整规则打标，前端不解析或注入第二套标签事实。

# 背景、现状与问题

## 背景

Requirement Source 为 GitHub Issue #674，直接上游还包括本轮业务 Owner 已确认的 Prompt 正文、唯一文件决定、旧版本不兼容决定和服务器数据重置边界。任务跨后端协议、数据库 Scheme bootstrap、前端管理页、测试与部署兼容，按 L3 处理。

## 当前现状

- 旧基线保留 `content_labeling_v1/v2/v3/v4/v4.5/v4.6`、版本指针及多套解析/编译/Validator 分支。
- 旧运行路径仍可读取不同输出结构，并保留 Excel 合成兜底等历史行为。
- 管理员标签编辑器会给任何 Scheme 自动补入 `无法分类 / 无法判断`，与当前 Prompt 的闭集冲突。
- 运行时事实本应来自数据库唯一 active Scheme；空库才使用 Git Prompt bootstrap。

## 问题、根因或约束

根因不是 Markdown 文件名本身，而是 Prompt、Parser、Compiler、Validator、数据库 Scheme 和前端标签编辑器允许不同事实并存。永久解决必须让唯一 Git Prompt、唯一当前协议、结构化 Scheme 和前端展示共享同一 Taxonomy，并对旧版本 fail closed。

## 不修改的后果

代码升级后仍可能选择旧 Prompt 或接受旧响应；前端可能显示 Prompt 未声明的标签；服务器重置后无法证明最新镜像能以唯一基线恢复一致的打标系统。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 业务 Owner 只接受 `content_labeling.md`，内部格式号为 v3.0 | 本轮用户决定 / Issue #674 | 删除历史文件和兼容分支 |
| E2 | 服务器旧 Scheme/配置/结果会在部署前清除并重新打标 | 本轮用户决定 / Issue #674 | 不提供旧数据库 Scheme 读取兼容 |
| E3 | 运行时唯一业务事实源是数据库 active Scheme，空库由 Git Prompt bootstrap | `AGENTS.md` Contract 基线 | Git Prompt 必须可完整恢复 Scheme |
| E4 | 前端管理员页从 `version.definition` 读取 Prompt、枚举和标签 | `AnalysisSchemePanel.vue` | 前端不应解析 Markdown 或维护平行标签 |
| E5 | 旧标签编辑器会自动注入 `无法分类 / 无法判断` | `AnalysisLabelsEditor.vue` 修复前实现 | 必须删除前端平行兜底规则 |
| E6 | changed-scope 预检会把已删除 Python 路径传给 Ruff 并因文件不存在失败 | `python scripts/dev/validate_changed.py --base origin/main --execute` 的当前工作树失败输出 | 删除项继续参与影响面分类，但文件级工具只接收仍存在的文件 |
| E7 | 管理员可分别编辑 Scheme 的 Prompt、发声类型、情感和标签；只替换机器 JSON 会让模型正文与结构化定义冲突 | `AnalysisSchemePanel.vue` 与 `schemes.py` 的反向能力审计 | 当前 v3.0 Compiler 必须原子重写人类可读闭集和机器镜像 |
| E8 | 首轮 Ready CI 的 PostgreSQL 任务仍用旧 Scheme fixture 调用当前 Compiler，并错误要求 0038 历史 Migration 输出等于当前 Compiler | PR #675 CI run `36599716178` / PostgreSQL Integration | 生命周期 fixture 必须改用唯一当前 Prompt；历史 Migration 只能按其冻结算法验证，不得恢复运行时旧协议兼容 |

## 推断与待确认

- 无业务语义待确认项。
- 本机缺少 PostgreSQL 测试 Secret，空库 bootstrap 集成证据必须由具备正式测试数据库的 PR CI 补齐。

# 目标、成功标准与非目标

## 目标

建立唯一内容打标 Prompt 与唯一当前协议，使后端 bootstrap、打标校验和前端 Prompt/Taxonomy 展示保持原子一致。

## 成功标准

- [ ] #674 AC1—AC7 均有直接实现与 current-head/current-base 证据。

## 范围

- 唯一 Git Prompt、机器 Taxonomy 与语义闭集。
- Prompt Parser、Scheme Compiler、运行时 Validator 和 LLM 请求。
- 空库 Scheme bootstrap 与历史协议 fail-closed。
- 管理员 Prompt/标签展示及业务页面标签数据消费。
- 相关测试、模块 README、专题文档与项目长期规则。

## 非目标

- 不删除 `zhengfu_shaixuan.md`。
- 不修改 HTTP 字段、数据库 Schema 或 Alembic Migration。
- 不在本次代码合并中执行生产数据清除、部署或重新打标。
- 不调用真实付费模型或 TikHub。
- 不修复与本任务无关的本机 Edge 截图测试基线问题。

## 必须保持不变

- PostgreSQL active Analysis Scheme Version 继续是运行时唯一事实源。
- Scheme Version 的 Prompt、Taxonomy 和 Hash 继续原子冻结。
- `zhengfu_shaixuan.md` 和代表内容筛选能力继续保留。
- 现有 HTTP Contract、数据库 Schema、依赖和启动方式不变。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| Prompt 文件 | 仅 `content_labeling.md` | #674 / E1 | 删除所有历史内容打标文件和指针 |
| 格式版本 | 仅 `content-labeling.v3.0` | #674 / E1 | 版本号只校验当前格式，不代表兼容旧 V3 |
| 兼容性 | V3/V4/V4.5/V4.6 全部 fail closed | #674 / E1/E2 | 部署前必须清理旧 Scheme/结果 |
| 发声类型 | 独立三分类，未命中官方且未通过 A-F 时营销兜底 | 业务 Owner Prompt | 不再由 source/intent 派生 |
| 相关性 | 实质讨论任意电动车品牌/行业即 relevant | 业务 Owner Prompt | 竞品内容继续完成完整打标 |
| 前端标签 | 只显示 Scheme `definition.labels` | E3-E5 | 删除前端自动注入兜底标签 |
| 部署 | 代码合并与生产数据重置分离 | #674 / E2 | 本任务不执行不可逆生产动作 |

# 修改方案与决策依据

## 最小充分方案

1. 把业务 Owner 提供的完整规则按既有清晰章节写入唯一 `content_labeling.md`，保留机器 Taxonomy/Semantic Rules 标记区块。
2. Loader、Compiler 和 Validator 只识别当前 v3.0、Taxonomy v2 和 Semantic Rules v1.3；删除旧 Markdown/版本分支和 voice 派生逻辑。
3. LLM 请求始终携带 `platform` 和完整输入；严格校验固定输出、证据、三类发声类型与 9/39 标签父子关系。
4. 空库 bootstrap 从唯一 Prompt 恢复结构化 Scheme，并保证编译后与 Git 原文精确一致。
5. 前端 Scheme 编辑器只使用数据库 `definition`；删除 `无法分类 / 无法判断` 自动注入，并用真实 Prompt 直接验证 9/39 渲染。
6. 删除历史 Prompt、旧兼容测试和旧竞品筛选 Prompt；保留政负筛选 Prompt。
7. 同步 `AGENTS.md`、Analysis README 和实现专题文档，明确不兼容部署与回滚边界。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：唯一 Prompt + fail closed | E1-E3 | 从机制上切断多份 Git/协议事实 |
| D2：结构化标记区块 | E3/E4 | 人类排版可读，同时机器解析稳定 |
| D3：删除前端兜底注入 | E4/E5 | 页面必须投影 Scheme，不能改写 Scheme |
| D4：部署前清库而非代码兼容旧 Scheme | E2 | 符合明确迁移决定，避免永久兼容负担 |

## 备选方案与取舍

- **保留旧版本 Parser 但删除文件**：拒绝，仍允许数据库旧 Scheme 成为隐式运行路径。
- **前端直接解析 Markdown**：拒绝，会形成第二套 Parser 和标签事实。
- **保留 `无法分类 / 无法判断` 作为前端兜底**：拒绝，违反当前 Prompt 闭集和业务 Owner 原则。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 只保留 `content_labeling.md` 这一份内容打标 Prompt，保留政负筛选，删除竞品筛选和历史 Prompt | #674 / AC1 | satisfied | Prompt inventory Contract 测试；生产目录当前文件清单 |
| R2 | 使用业务 Owner 提供的完整原则并沿用清晰格式，内部版本为 v3.0 | #674 / AC2 | satisfied | `content_labeling.md`；必要章节与枚举单测 |
| R3 | 删除全部旧版本兼容，旧 V3/V4/V4.5/V4.6 fail closed | #674 / AC3 | satisfied | Loader/Compiler/Validator 实现；obsolete version 参数化测试 |
| R4 | 空库从唯一 Prompt bootstrap，打标输入/输出和独立三分类语义正确 | #674 / AC4 | satisfied | 唯一 Prompt 精确 roundtrip、165 项 Analysis 单测、空库 PostgreSQL bootstrap 集成用例；真实 PostgreSQL 执行仍是 merge 前 required CI gate |
| R5 | 前端显示数据库 Scheme Prompt 和当前 9/39 标签，不注入旧兜底值 | #674 / AC5 | satisfied | `AnalysisSchemePanel.vue`、`AnalysisLabelsEditor.vue`、真实 Prompt SSR 回归、前端全量测试 |
| R6 | 前后端静态、单元、契约、构建与 required CI 通过 | #674 / AC6 | satisfied | 当前实现与本地稳定层已通过；PR current-head PostgreSQL/Full-stack/CI Gate 仍是合并前交付门禁，不由本状态替代 |
| R7 | 文档明确不兼容迁移、部署清理和重新打标边界 | #674 / AC7 | satisfied | `AGENTS.md`、Analysis README、Appendix 07 |
| R8 | 生产服务器清除旧 Scheme/配置/打标结果并重新打标 | user:2026-09-30-analysis-reset-deployment-decision / AC1 | explicitly_deferred | 本次只合并代码；生产数据动作由后续授权部署操作执行 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `prompts/content_labeling.md` 与旧 Prompt | 建立唯一 v3.0 Prompt，删除旧文件 | 单一 Git bootstrap 基线 | R1-R3 |
| `prompt_taxonomy.py` / `schemes.py` | 收敛单协议解析编译，并同步人类可读闭集与机器镜像 | fail closed、精确 roundtrip 和管理员编辑原子一致 | R2-R5 / E7 |
| `content_labeling.py` / LLM adapter | 收敛当前完整输入输出和错误传播 | 正确应用 Prompt | R3/R4 |
| `AnalysisLabelsEditor.vue` / Scheme Panel | 原样显示结构化标签和 Prompt | 消除前端平行 Taxonomy | R5 |
| `scripts/dev/validate_changed.py` | 删除项保留影响面分类，但不传给要求文件存在的 Ruff | 让本次和后续文件删除能通过同一正式预检 | R6 / E6 |
| 后端/前端测试 | inventory、roundtrip、fail-closed、bootstrap、9/39 渲染 | 直接证明关键行为 | R1-R6 |
| PostgreSQL 集成测试 | 当前 Scheme 生命周期改用 v3.0 基线；0038 数据迁移按其冻结算法自证 | 修正旧测试事实但不恢复生产兼容 | R3/R6 / E8 |
| 项目文档 | 更新唯一事实与迁移边界 | 防止后续恢复旧路径 | R7/R8 |

执行过程中保持最小闭环：

- [x] 调查当前实现和事实源；新建项目则确认现有资料、目标和硬约束
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据或说明测试例外
- [x] 完成最小实现，不静默扩大范围
- [x] 同步受影响的长期文档或明确不适用依据
- [x] 取得仍覆盖当前版本的验证证据
- [x] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Prompt Parser/Validator、当前 9/39 标签组件渲染、错误传播 |
| 接口 / 契约 | required | Prompt inventory、Scheme definition/roundtrip、现有 HTTP/TS Contract 无漂移 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 空库 bootstrap 和 active Scheme 运行时读取 |
| 用户 / 工作流验收 | required | 管理员打开当前 Scheme 后 Prompt/标签原样显示且不产生虚假未保存状态 |
| 跨组件关键路径 | required | Git Prompt → Scheme Version → Taxonomy API/前端 definition → 打标/展示 |
| 外部依赖 / 供应方探测 | not_applicable | Prompt 与 Contract 可由确定性 Fixture 验证；不需要付费模型或 TikHub 当前事实 |
| 构建 / 打包 / 运行 | required | Python 静态检查、Frontend lint/typecheck/build、Wheel Prompt inventory |
| 文档 / 治理 / 其他 | required | Change Ready、Issue/PR 追溯、current-head/current-base CI 与两阶段 Review |

## 验证计划

- 目标测试：`tests/unit/analysis`、`tests/contracts/test_user_voice_single_source_contract.py`、`frontend/tests/analysis-labels-editor.spec.ts`、`frontend/tests/analysis-scheme-prompt-display.spec.ts`。
- 相关回归：后端全部 Unit/Contract、前端全量 Vitest、Analysis Scheme/Workbench PostgreSQL Integration。
- 静态检查或构建：Ruff、mypy、ESLint、TypeScript/Vue typecheck、Vite build、Wheel package inventory。
- 专项真实边界：PR CI PostgreSQL 空库 bootstrap。
- changed-scope preflight：`python scripts/dev/validate_changed.py --base origin/main`。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | Prompt 原则遗漏、结构化区块漂移、旧协议残留、前端改写标签 | 精确 inventory/roundtrip/fail-closed/真实 Prompt 9/39 回归 |
| 兼容性 | 明确不兼容旧 Prompt/Scheme | 部署前清理旧 Scheme/结果，禁止静默读取 |
| 数据 / Migration | 无 Schema/Migration；生产数据重置是独立部署前置 | 本任务不执行不可逆数据动作 |
| 依赖 / Runtime | 不新增、不升级 | 继续使用锁定 Python/Node/npm/uv |
| 部署 / 运行 | 最新镜像从唯一 Prompt bootstrap 空库后重新打标 | 由后续部署操作验证 |
| 回滚 / 恢复 | 数据重置前可回滚代码/镜像；重置后需从备份恢复或用回滚镜像重新 bootstrap/打标 | 旧 Scheme 不由新代码兼容读取 |

# 文档、依赖、部署与发布影响

- **长期文档**：同步 `AGENTS.md`、Analysis README 和 `docs/appendix/07_AI舆情打标与分析实现.md`。
- **依赖 / Runtime**：不新增、不升级。
- **配置 / Secret**：代码配置不变；生产数据清理不在本任务执行。
- **部署 / Release**：合并代码不等于部署；上线前必须执行已确认的旧 Scheme/结果清理方案。
- **兼容 / 消费方通知**：旧 Scheme 是明确破坏性边界；前端/后端当前版本必须原子升级。

# 完成审计

- [x] upstream_re_read：已在 `origin/main@3f6b4f4c` 和 PR head 上重读 live #674、用户最终决定、当前 `AGENTS.md`、Analysis README、Appendix 07、唯一 Prompt 与实际代码。
- [x] change_coverage：脱离当前 checklist 从 #674 重建 AC1—AC7；文件收敛、原则/格式、fail-closed、bootstrap/运行时、前端 9×39 展示、验证门禁和文档边界均有实现与测试承载；生产清库仍由 R8 正式延期，不冒充本 PR 验收。
- [x] reverse_audit：已核对 `content_labeling.md → bootstrap definition → Compiler/Version/Hash → RuntimeTaxonomyValidator/LLM → API/UI`，并反向核对 `AnalysisSchemePanel 编辑 → Compiler → 人类可读闭集与机器 JSON 同步 → 新 Version/发布`；发现初版 Compiler 只更新机器 JSON 后已在 `1b55acda` 修复并新增回归。
- [x] unresolved_cleared：R1—R7 已有当前实现/测试承载，R8 具有用户明确延期依据；首轮 Ready CI 发现的 3 个旧测试事实已完成根因修复，修复后 current-head CI、独立 Review 和 current-base merge preflight 继续作为交付门禁，不把它们伪装成已完成。

## 两阶段需求复核

- **A1（上游要求 → Change）**：#674 AC1—AC7 均有唯一 R 行；服务器清库/部署决定单列 R8，并明确排除在当前代码 PR 外，没有把它静默删掉或伪装完成。
- **A2（Change → 实现/测试/文档）**：R1—R7 均能追到具体生产路径、直接回归和长期文档；反向审计发现并修复了 Scheme 编辑时模型正文与机器 Taxonomy 可能分叉的问题。独立代码质量 Review 和平台 CI 仍待 PR Ready 后完成。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 本地任务工作区，基于 `origin/main@3f6b4f4c` | Ruff format/check；`uv run mypy backend/src` | 19 个 changed Python 文件格式通过；Ruff 通过；mypy 413 个源文件通过 | 当前 changed Python 静态质量成立 |
| V2 | 本地任务工作区，基于 `origin/main@3f6b4f4c` | `uv run pytest tests/unit tests/contracts tests/api -q --deselect ...::test_douyin_screenshot_skips_login_overlay` | 1667 passed，16 skipped，1 deselected，12 subtests passed；被剔除项在未改代码上独立失败 | 除已确认本机 Edge 基线项外，后端 Unit/Contract/API 回归成立 |
| V3 | 本地任务工作区，基于 `origin/main@3f6b4f4c` | `uv run pytest tests/api/test_health.py -q` | 3 passed | 全量同进程出现的 Health 失败是前序环境污染，不是 Health Contract 回归 |
| V4 | 本地任务工作区，基于 `origin/main@3f6b4f4c` | Contract generate `--check` 与 compatibility | 均 exit 0 | 生成 Contract 无漂移且兼容检查通过 |
| V5 | 本地任务工作区，基于 `origin/main@3f6b4f4c` | Frontend ESLint、Vitest、build、Playwright | lint 通过；36 files/271 tests 通过；typecheck/build 通过；170 E2E 通过 | Prompt/9×39 标签展示和前端相关回归成立 |
| V6 | 本地任务工作区 | PostgreSQL Integration | 本机缺少 `.runtime/secrets/postgres_password`，连接前失败 | 本机未取得持久化证据；由 PR CI 补齐 |
| V7 | 本地任务工作区，Draft Review 修复后 | 当前 Scheme 编译、roundtrip、编辑镜像和旧模板拒绝回归 | 43 passed；Ruff/mypy 通过 | 当前 v3.0 Compiler 会同步模型正文与机器 Taxonomy，并拒绝旧模板 |
| V8 | `1b55acda`，基于 `origin/main@3f6b4f4c` | `uv run pytest tests/unit/analysis -q` | 165 passed | Review 修复后的 Analysis 全量单元回归通过 |
| V9 | PR #675 head `5bd7fe66` | CI run `36599716178` | Runtime Acceptance、Developer Tooling、Real Full-stack Golden Path 已通过；PostgreSQL Integration 因 3 个过期测试 fixture 失败 | 证明生产迁移和数据库本身可用，并定位测试仍假设旧 Compiler 兼容 |
| V10 | PostgreSQL 测试修复工作区 | 两个修复文件 Ruff；Pytest collect-only | Ruff 通过；35 个相关集成测试成功收集 | 当前 fixture/历史迁移测试源码可加载，完整数据库行为待修复后 CI 验证 |

## 未验证内容与剩余风险

- PostgreSQL 过期测试事实修复尚待提交并触发新的 current-head CI；首轮失败 run 不作为可合并证据。
- changed-scope 稳定层已执行；原始全量命令受一项未改动的本机 Edge 截图基线失败阻断，剔除该项后的完整稳定套件已通过。
- 仍需修复后 PR current-head PostgreSQL/Full-stack CI、独立 Review 与 current-base merge preflight。
- 生产清库、镜像部署、空库 bootstrap 和重新打标未执行，仍是部署阶段责任。

## 交付状态

- 提交：`1b0212e5`（主实现）+ `1b55acda`（Review 修复）+ `5bd7fe66`（Ready/文档）；PostgreSQL 测试事实修复待提交。
- 拉取请求：PR #675 已绑定 #674 并处于 Ready；合并仍受修复后同一 head 的 required CI 与 Review 门禁约束。
- CI：首轮 Ready run `36599716178` 暴露 3 个旧测试事实；修复后必须用新 head 重跑，不能重用失败 run。
- 合并：待 Review、Ready Check、CI、current base/head 复核后执行。
- Change 归档：待合并后由仓库自动化处理。
- Issue Closure：只有本 PR 完成 #674 全部代码验收时随合并关闭；生产部署动作不由本 Issue 伪装完成。

## 备注

本 Change 记录的是代码与配置基线交付；生产服务器不可逆数据操作需要独立执行证据。
