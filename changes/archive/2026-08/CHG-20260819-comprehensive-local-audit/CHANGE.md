---
schema: rvc-change/v1
id: CHG-20260819-comprehensive-local-audit
title: Stage 1—7 与 P1 全面本地审计和性能验证
level: L3
status: done
owner: Codex
branch: main
created: 2026-08-19
updated: 2026-08-19
depends_on: []
affected_areas:
  - platform
  - jobs
  - collection
  - content
  - analysis
  - frontend
  - contracts
  - documentation
affected_paths:
  - backend/src/aima_ugc
  - frontend
  - tests
  - scripts
  - contracts
  - migrations
  - docs
  - .github/workflows
contracts: []
data_changes: []
---

# 背景与目标

当前长期事实声明 Stage 1—7 与临时 P1 已闭环，Stage 8 尚未开始。用户要求对本地代码做全面功能、质量和性能检查，发现问题后给出解决方案并在授权范围内修复，同时保证代码、Schema、Migration、生成物和阶段文档一致。审计完成后，用户另行明确授权：在完整验证通过的前提下，把全部本地有效差异直接提交并推送远程 `main`，同时确认其关键词配置已经包含在发布基线中。

# 成功标准

- [x] 运行仓库当前可执行的后端 Unit、Contract、API 和 PostgreSQL Integration 测试，记录退出码、通过/失败/跳过数量和环境限制。
- [x] 运行前端锁文件安装校验、Lint、双 TypeScript 类型检查、Unit、OpenAPI Client 漂移检查和 production Build。
- [x] 运行 Python 锁文件、格式、Lint、mypy、Wheel/import、Migration、架构、表 Owner、Secret、文档及工作区生成物门禁。
- [x] 运行仓库现有 P1 性能基准，报告数据规模、耗时、吞吐、内存/资源观测和既有阈值；没有批准阈值的维度只建立基线，不伪造达标结论。
- [x] 每个真实失败都保留原始错误、稳定复现和根因证据；行为缺陷先建立回归测试，再做最小兼容修复并复验。
- [x] 对照 Stage 1—7/P1 长期文档和机器事实，修正文档过期或实现漂移；Stage 8、Release 和未决阶段 0 能力不冒充已完成。
- [x] 最终工作树差异可追溯、无 Secret、无未经授权依赖升级；经用户后续明确授权后使用中文提交、无强推发布到远程 `main`，不创建 PR。

# 范围

- 当前 `main` 的 Stage 1—7 与 P1 已实现功能、测试、生成物、迁移链、前端构建和文档事实。
- 仓库已有且可在本机安全运行的性能/容量验证入口。
- 审计中确认的代码、测试、脚本、配置或文档缺陷的最小修复。

# 非目标

- 不开始 Stage 8 API/正式业务页面实现。
- 不运行付费 TikHub/Provider/LLM Probe，不上传本地数据，不写生产库。
- 不擅自定义日容量、SLO、RPO、RTO、中文搜索质量阈值或生产 Release 验收值。
- 不实现尚未批准的认证、保留/删除、预算、Release 备份屏障或生产镜像方案。
- 不升级/降级 Python、Node、PostgreSQL、框架、依赖或锁文件。
- 不创建 PR、不强制推送、不重写历史或部署；只有本地与远程 `main` 基线一致且发布前门禁通过时才直接推送。

# 必须保持不变

- 模块化单体、单一根 uv 工程、PostgreSQL 18、Provider→Raw→Mapper→Canonical→Ingestion、持久化 Job 和生成 OpenAPI Client 的既定边界。
- 公共 Contract、Migration 历史、数据 Owner、导入路径、合法默认行为和错误语义；发现必须改变时先单独完成设计门禁。
- 真实 Provider/LLM 默认关闭，Secret、Raw、正文和凭据不进入测试输出、日志或 Git。
- 当前工作区用户文件和运行产物不得被破坏或擅自清理。

# 方案比较与选择

## 方案 A：现有 CI 全矩阵 + 本地真实依赖 + 固定性能基准（采用）

复用仓库工作流、真实 PostgreSQL 测试、Fixture/Fake、构建和现有 90,000×13 基准。优点是与当前阶段事实一致、可重复、无付费外部副作用；限制是不能证明真实 Provider SLA 或未定义的生产容量。

## 方案 B：只运行静态检查和 Unit

速度快、环境要求低，但无法验证 Migration、Repository、Worker/Scheduler 并发恢复、前端生成物和真实性能，不满足“全面检查”。不采用。

## 方案 C：生产等价 Soak + 真实 Provider/LLM

能覆盖更真实的外部延迟和费用，但当前缺少日容量/SLO/成本上限/生产拓扑决策，并涉及付费和本地数据出站；超出授权与阶段门禁。不采用，作为未来独立 L3/Release 任务。

# 实施步骤

1. `[基线] → 规则/阶段/依赖/CI/测试入口 → 形成可执行矩阵 → rvc status + 清单核对`
2. `[功能] → 后端/前端/Contract/DB/构建 → 找出真实失败 → 完整命令与退出码`
3. `[性能] → P1 benchmark 与现有性能测试 → 建立实测基线 → 固定输入、重复运行和资源观测`
4. `[修复] → 失败相关最小文件 → Red/Green/Refactor → 目标及相关回归`
5. `[一致性] → Schema/Migration/生成物/Blueprint/README → 当前事实一致 → 生成/文档门禁`
6. `[交付] → 全量复验与两阶段 Review → 问题/方案/风险/本地差异报告 → Git status + 全部门禁`

# 兼容、Migration、部署与回滚

- 审计本身不改变 Contract、Schema 或 Migration；若失败证据要求变更，必须先更新本节并完成对应 L3 决策。
- 不部署。代码修复优先保持现有接口和数据兼容。
- 未提交变更可按文件级差异人工回滚；禁止使用破坏性 Git 命令覆盖其他修改。

# 风险

- PostgreSQL/Docker/浏览器或端口不可用可能限制本地集成/E2E；此类项目单独标记环境阻塞，不冒充功能缺陷。
- Windows 防病毒、文件系统和进程调度会影响微秒级基准；性能结果记录运行环境和测试规模，避免与 Linux 生产值直接等同。
- 全量测试可能较久；按功能边界分批运行并保留每批结果，失败时先定位根因再扩大范围。

# 验证证据

## 已确认并修复的问题

1. Windows 锁定环境只有 `psycopg` Python 包、没有可加载的 `libpq`/binary wrapper，真实 PostgreSQL Migration 在导入阶段失败。按平台标记让 Windows 安装同版本 `psycopg-binary==3.3.4`，其他平台保持普通 `psycopg==3.3.4`；锁文件同步后真实 PostgreSQL 18.4 连接、Migration 和 Integration 均通过。
2. `imports_test/test.py` 提交了个人绝对输入路径，并把真实付费 LLM 默认设为开启，与“真实 Probe 默认关闭”长期规则冲突。恢复占位输入路径、默认关闭真实 LLM，并增加回归测试。
3. `uv_build` 会递归打包 Provider 调试目录中的本地 `.env` 与 `output/`，既可能泄露本地数据，也会被不可读运行产物直接阻断构建。按 `uv_build 0.12.3` 官方配置增加 `source-exclude = [".env", "output"]`，增加回归测试，并实际验证 Wheel 内无禁入文件。
4. 默认 pytest 导入模式无法在同一进程收集 Unit/Integration 中的同名测试文件。按 pytest 9.1.1 官方建议启用 `--import-mode=importlib`，完整 `pytest tests` 可收集并执行。
5. 三个 Content Integration 入口未清理自己创建的 Raw/Job/Candidate/Content 来源链，导致后续 Job 测试出现外键错误；关键词 Repository 测试也未清理词包关联。把清理责任放回写入测试，Content 套件结束后业务表零残留，Job Fixture 保持只清理自身表。
6. LocalArtifactStore 的 symlink 逃逸测试在未开启 Windows 开发者模式时无法创建 symlink。增加目录 Junction 等价验证回退；若两种能力都被系统策略禁用才明确跳过。

## 实际命令和结果

| 验证 | 本轮结果 |
| --- | --- |
| `uv lock --check` / `uv sync --locked` / 源码 import | 退出码 0；解析 40 个包；`aima_ugc 0.1.0` 可直接导入 |
| `pytest tests -q`（隔离 PostgreSQL 18.4） | 退出码 0；`520 passed, 1 skipped`，跳过项是当前 Windows 文件系统策略不允许 Secret symlink 测试创建 symlink |
| `pytest tests/integration -q` | 退出码 0；`107 passed` |
| Content Integration + 残留统计 | `19 passed`；`NONEMPTY_TABLES {}` |
| Ruff / mypy | 321 个文件格式通过；Ruff 无错误；mypy 171 个源文件无错误 |
| Contract / 生成 Client | OpenAPI 与 Analysis/Canonical/Provider/Collection/Export Schema 兼容检查通过；Orval 重生成后 Git diff 为 0 |
| 架构 / Owner / Secret / 文档 | 四项质量脚本均退出码 0；`git diff --check` 退出码 0 |
| Alembic | `20260818_0018 (head)`；`alembic check` 无新操作；`head → base → head` 通过；实际 40 张表与生产 Metadata + `alembic_version` 完全一致 |
| Wheel | 构建成功；隔离虚拟环境安装并从 `site-packages` 导入；226 个 Wheel 文件中无 `.env` 或 `output/` |
| 本地 HTTP smoke | FastAPI live、Vite 首页、Vite `/health/live` 代理通过；ready 返回 200，database/artifact_store/log_directory 均为 `ok` |
| 前端 | Lint、TS7/Vue 双类型检查、2 个 Vitest、production Build 均退出码 0；产物 JS 86.80 kB（gzip 33.84 kB） |
| npm audit | 生产依赖和全部依赖均为 0 vulnerabilities |
| P1 90,000×13 基准 | 退出码 0；生产离线主链 346.719 秒，259.576 行/秒，峰值 RSS 285,663,232 bytes；最终 Excel 90,000 数据行、33 列、3 个工作表，所有关键 JSONL 均 90,000 行 |

性能分阶段：转换 38.013 秒（2,367.633 行/秒）、关键词过滤 9.047 秒（9,947.870 行/秒）、稳定身份去重 14.308 秒（6,290.157 行/秒）、Fake LLM 写回 45.699 秒（1,969.429 行/秒，峰值在飞 250）、最终 Excel 导出 239.653 秒（375.544 行/秒）。当前没有批准的生产吞吐或内存阈值，因此这些数字只作为 Windows 11 / Python 3.14.7 本机基线；最主要性能成本是最终 Excel 导出。

## 未修改的问题与边界

- 对全部历史 Migration 额外运行 Ruff 会报告 57 个既有格式/长行问题；当前正式 CI 只检查 `backend tests scripts` 和当期指定 Migration。它不影响本轮 Migration 执行或 Schema 正确性，不在综合审计中批量改写历史 Migration；如需清零，应建立独立机械格式 Change 并复验全迁移链。
- 本机 Docker Engine 29.6.2 / Compose 5.3.1 低于 Blueprint 的 Release 核验快照 29.7.2 / 5.4.0。Stage 8/Release 尚未开始，本轮只用 PostgreSQL 18.4 临时容器验证开发功能；进入 Release 验证前应更新宿主工具或按届时批准版本重新核验。
- npm 安装有上游 `glob@10.5.0` deprecated 和 esbuild lifecycle script 提示，但锁定版本的 Lint、类型、测试、Build 和 audit 均通过。本轮不擅自升级依赖；后续依赖升级应独立核验发布说明和完整回归。
- 未运行真实 TikHub/LLM、Stage 8 业务 E2E、生产镜像、离线 Release、Backup/Restore 或中文搜索容量验收；这些均未进入当前已批准阶段，不能由 Fake/本地 smoke 冒充。

# 文档影响

已同步 `README.md`、`docs/环境运行与部署.md`、`docs/测试与调试说明.md`、Blueprint 07 与 `imports_test/README.md`，记录 Windows psycopg binary wrapper、Wheel 排除边界、pytest importlib 全套件入口和真实 LLM 默认关闭。Stage 1—7/P1/Stage 8 状态、Contract、数据库和 Migration 语义均未改变。

# Git 与发布

- 分支：`main`。
- Commit：本 Change 与全部工作区有效差异由本次中文提交统一记录；最终哈希以 Git 历史为准。
- Push/PR/CI：用户已明确授权直接推送远程 `main`；不创建 PR、不强推。本地发布前重新验证 `520 passed, 1 skipped`、前端与全部质量门禁；远端 CI 状态仍须与本地证据区分。
- 关键词配置：`imports_test/keyword_pack.py` 与 `keyword_pack.txt` 发布前均与 `HEAD` 一致；实际关键词调整已包含在远程 `main` 的提交 `c1cd453`，本次发布不会遗漏或回退。
- 部署：未执行。
