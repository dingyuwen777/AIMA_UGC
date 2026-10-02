# 日期补采验证与复核证据

日期：2026-10-02，北京时间。目标基线 `62e8cc7264d1f9ef5aa999aeff60e5e0404b2153`；最终文件身份见同目录 `source-hashes.json`。canonical Agent_Skills 源码固定为 `041c9b60aae0f566553002794eb5fde4ed614c7f`，未改写项目受管治理资产。

## 环境与边界

Windows 本机独立 worktree；Python 3.14.7、Node 24.19.0，依赖由当前锁文件恢复。PostgreSQL 18.4 使用本任务容器和独立数据库 `aima_date_test`；全栈使用独立 `aima_date_fullstack`、API 18090、浏览器 14174 和正式 Fake TikHub Worker。浏览器 Mock 回归使用独立端口 14173。没有接入业务库、真实 TikHub 或生产环境。

## 实际结果

| 命令 / 检查 | 当前结果 | 证明范围 |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m pytest tests/unit tests/contracts tests/api -q --tb=short` | exit 0；1945 passed、16 skipped、12 subtests passed | 全部后端单元、公开 Contract 与 API；跳过项不计作通过 |
| `.venv/Scripts/python.exe -m pytest tests/integration/collection/test_collection_date_supplement.py tests/integration/collection/test_collection_repository.py tests/integration/collection/test_collection_run_execution_gateway.py tests/integration/collection/test_stage8e_collection_http_runtime.py tests/integration/collection/test_collection_supplement_target_eligibility.py -q --tb=short` | exit 0；95 passed | 日期边界/NULL/范围外/全来源、五平台身份、AI 与日期变化、万条 Scope 及末批回滚、旧模式、Worker 评论/回复/Raw 恢复与 fencing |
| `npm run test -- --run`，frontend 目录 | exit 0；36 files、276 tests passed | Store 竞态、组件、生成 Client Mock 与已有前端行为 |
| `npx playwright test --config .runtime/date-playwright.config.ts`，frontend 目录 | exit 0；175 passed | 全部现有浏览器 Mock 用户流程；专用配置只替换端口、禁止复用服务、workers 与输出目录 |
| `npx playwright test --config .runtime/date-fullstack.config.ts comment-supplement.spec.ts`，frontend 目录 | exit 0；1 passed | 浏览器日期选择→真实 API/PostgreSQL/Job/Worker→五平台 Detail/Comments/可选 Replies→运行详情→声音广场；六条输入仅范围内五条形成 Scope |
| `.venv/Scripts/python.exe -m mypy backend/src` | exit 0；435 files | 后端类型检查 |
| `scripts/contracts/generate.py --check` 与 `scripts/contracts/check_compatibility.py` | exit 0 | 手写 Contract、OpenAPI/Schema 与兼容边界；客户端由正式生成命令刷新 |
| changed Python 的 `ruff check` 与 `ruff format --check` | exit 0 | 当前改动的 Python 格式与静态规则 |
| `npm run lint` 与 `npm run build`，frontend 目录 | exit 0 | ESLint、两种 TypeScript/Vue 检查与生产构建 |
| `scripts/dev/validate_changed.py --base origin/main` | exit 0；profile full | 与正式 CI 同一 classifier，未增加 Workflow 或另建影响面映射 |

完整本地日志保留在 worktree 的 `.runtime/date-tests/`；平台 CI 的范围更广，结果以 PR 当前 head 的 Checks 为准。保留既有 Pydantic/Starlette 弃用提示及前端大 chunk 提示，未为取得通过修改依赖或提高阈值。

## 容量与 Red → Green

Contract Red：日期创建测试在实现前 1 failed / 10 passed，现有模式拒绝日期请求；当前 Contract/API 全部 Green。

容量 Red：旧 Scope Repository 一条 SQL 创建 10,000 个 Scope 时，PostgreSQL 报绑定参数超过 65,535；新增七万候选读取回归在逐 ID `IN` 版本为 1 failed。分别改为 SQLAlchemy `insertmanyvalues` 自动分批和 PostgreSQL UUID 数组参数。当前回归证明 70,000 候选能返回完整阻塞诊断；10,000 Scope 完整保存，且最后一批唯一约束失败时 Job/Run/全部 Scope 整体回滚。

`capacity.json` 记录 100,000 条测试内容中选择 10,000 条：生产形态日期 SQL 使用既有 `ix_contents_published_at_id_desc`，EXPLAIN 总执行 5.831 ms；正式创建包含资格读取、Job/Run/10,000 Scope，启用 tracemalloc 时耗时 3.855 s、Python 峰值 26.88 MiB。它是本机固定 Fixture 的测量，不是生产容量或 SLO 承诺；没有据此添加天数/条数限制或 Migration。

复现资产为 `date_capacity.py`，复用生产 Service/Repository 和既有测试 Fixture。只允许使用该专用本机数据库；从仓库根以 `python -c "import runpy; runpy.run_path('changes/active/CHG-20261002-100000-date-supplement/evidence/date_capacity.py')"` 运行。数据初始化和清理只作用于隔离测试库。

## 两阶段本地复核

第一阶段重新读取用户批准方案和 live #690，核对全部 AC1–AC6，不从当前 Change 推定需求完整。反向核对日期资格、创建、运行/Scope 状态和结果能力与页面入口；检查所有前端操作对应正式支持。`docs/blueprint/04` 仍是有效通用任务边界，无需修改；同步 Blueprint 08、Product 02、Collection 导航及模块 README。

第二阶段检查日期/相关性冻结、共享身份、全量评论覆盖、Provider Raw 恢复、fencing、事务、参数上限、旧模式和生成兼容。发现并修正大范围参数上限、详情旧批次文案与测试 Fixture 的唯一父 Job/相关性情感约束；重新验证后没有范围内阻塞项。既有 `_discovery_filter` 的 v2 检查仅用于 Discovery，不阻断 v3 日期任务；没有为日期模式放宽它。

复用既有 Worker 参数化测试，不另建日期 Provider、分页或 Mapper。Store、浏览器、数据库、全栈和容量分别证明不同边界。没有调用真实付费 TikHub，Provider endpoint/payload/Mapper/外部分页协议未改变。

本记录属于本地两阶段自查；GitHub 外部审批和当前 head 的正式 CI 不由本记录替代。交付止于 PR，未 merge、Release、Deploy、生产 Migration、Change Archive 或 Issue Closure。

## 用户追加的 Shell 换行修改

根 `.gitattributes` 只增加 `*.sh text eol=lf`。全部 tracked `.sh` 为 `scripts/setup_dev_environment.sh` 与 `scripts/deploy/reset_keep_vehicle_catalog.sh`：索引和工作树均验证为 LF；索引原本已是 LF，本次修复的是 Windows checkout 换行及后续保持规则。逐字节验证除换行外内容不变；未发现其他扩展名的已有 Bash/sh shebang 脚本。此项未增加 CI、部署文档或独立治理流程。
