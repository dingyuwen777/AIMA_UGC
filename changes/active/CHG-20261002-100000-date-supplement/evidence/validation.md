# 统一内容补采验证与复核证据

日期：2026-10-02，北京时间。基线 main `62e8cc7264d1f9ef5aa999aeff60e5e0404b2153`；最终源文件的 LF 规范化 SHA-256 见 `source-hashes.json`。canonical Agent_Skills 当前源码 `041c9b60aae0f566553002794eb5fde4ed614c7f`，按其入口、Coding/Testing/Review/Docs 与 Delivery 规则执行，未改写受管资产。

## 环境与边界

直接在 `E:/work/03_Aima/code/AIMA_UGC` 修改，当前任务分支 `feature/date-supplement`。Python 3.14.7、Node 24.19.0、当前锁文件依赖。专用本机 PostgreSQL 18.4 容器 `aima-content-supplement-test` 使用数据库 `aima_content_test` 和 `aima_content_fullstack`，隔离业务库。API 18090、浏览器 14174、Mock 回归 14173；全栈使用生产 Worker 和既有 Fixture TikHub Transport。用户提供的 API Key 未保存、打印或使用，没有接入真实付费 Provider 或生产环境。

## 实际结果

| 命令 / 检查 | 当前结果 | 证明范围 |
| --- | --- | --- |
| `uv run pytest tests/unit tests/contracts tests/api -q` | exit 0；1954 passed、16 skipped、12 subtests passed | 全部后端单元、公开 Contract/API；跳过项不计通过 |
| `.venv/Scripts/python.exe -m pytest tests/integration/collection/test_collection_content_supplement.py tests/integration/collection/test_collection_date_supplement.py tests/integration/collection/test_collection_repository.py tests/integration/collection/test_collection_run_execution_gateway.py tests/integration/collection/test_stage8e_collection_http_runtime.py tests/integration/collection/test_collection_supplement_target_eligibility.py -q --tb=short` | exit 0；117 passed | 日期边界/NULL/全来源/身份；显式 AI irrelevant；同数量换目标和选项 409 零写入；冻结、历史兼容、七万候选、万条 Scope/末批回滚；五平台评论/回复/恢复/fencing |
| `npm.cmd --prefix frontend run test -- --run` | exit 0；37 files、284 passed | 共享表单竞态、409 手动确认、选项与 Capability；Voice 四种终态、退出迟到响应；既有前端行为 |
| `npm.cmd --prefix frontend run test:e2e -- --config .runtime/content-playwright.config.ts` | exit 0；175 passed（3.4 min） | 日期弹窗、平台保留、加载/空/失败/重开、窄窗口、既有页面流程；配置仅替换端口/noReuse/workers/输出目录 |
| `npm.cmd --prefix frontend run test:e2e:fullstack -- --config .runtime/content-fullstack.config.ts fullstack/comment-supplement.spec.ts` | exit 0；2 passed（57.7 s） | 日期五平台→真实 API/DB/Job/Worker→详情/评论/回复；Voice 两条勾选→4 个请求/无未选目标和回复→终态自动刷新→重复评论不新增 |
| `uv run mypy backend/src` | exit 0；435 files | 后端类型检查 |
| changed Python `ruff format --check`、`ruff check` | exit 0 | 当前 Python 格式与静态规则 |
| `uv run python scripts/contracts/generate.py --check`、`scripts/contracts/check_compatibility.py` | exit 0 | Contract/OpenAPI/Schema 一致与旧接口兼容；TypeScript Client 正式生成 |
| `npm.cmd --prefix frontend run lint`、`npm.cmd --prefix frontend run build` | exit 0 | ESLint、TypeScript/Vue 类型及生产构建 |
| `scripts/quality/check_docs.py`、`check_docs_facts.py`、`scan_secrets.py`、`check_change_completion.py --root . --require-active-ready` | exit 0 | 当前文档/机器事实、Secret 和全部 Active Change 完成门禁 |

正式 `scripts/dev/validate_changed.py --base origin/main --fix --execute` 在 Windows 无法解析 bare npm，未宣称该命令通过。忽略目录的本机启动器复用原 classifier/build_validation_commands，只解析为 npm.cmd；其后端/生成/ESLint 均通过，首次 frontend 单元失败于旧源码字符串断言。修正后按相同计划完成前端单元、构建和全部浏览器检查，没有改变 CI、影响面映射或断言强度。classifier 为 full；全量 PostgreSQL、全量 Full-stack、打包/Compose 等正式范围由 PR 当前 head 的现有 CI 完成。

本轮日志保留 `.runtime/content-test-runtime/`；截图 `.runtime/content-fullstack/results/`。保留既有 Pydantic/Starlette 弃用、Vite 大 chunk 及测试临时 configLoader 提示，没有调整依赖或阈值。

## 容量与失败修复

最初日期 Contract Red 为 1 failed / 10 passed。大范围 Red 发现原单条 INSERT 的 PostgreSQL 参数上限、逐 ID IN 的七万候选参数上限，改为 SQLAlchemy 自动分批和 UUID 数组参数；相同事务末批失败仍全部回滚。

最新 `capacity.json`：100,000 条内容中选择 10,000 条，既有 `ix_contents_published_at_id_desc`；EXPLAIN 总执行 7.189 ms。正式 Preview + 冻结创建的创建阶段在 tracemalloc 下 10.333 s，Python 峰值 26,536,575 bytes（25.31 MiB），10,000 Scopes 完整保存。本机固定 Fixture 测量不是生产容量或 SLO 承诺；未凭测量增加硬编码日期天数/条数上限。

复现 `date_capacity.py` 调用生产 Service/Repository，仅允许本机专用测试库；从仓库根 `python -c "import runpy; runpy.run_path('changes/active/CHG-20261002-100000-date-supplement/evidence/date_capacity.py')"`。运行脚本拒绝其他数据库地址/库名。

本轮测试实际发现并修正日期范围分步更新丢失平台、Selected 打开 watch 竞态、partial_success 终态缺口及重排轮询清空刚创建任务。全栈旧断言曾读取公开 Scope 不存在的 source_value 字段，改为正式 Content source_identifier 和 Provider Request 数量证明精确目标；旧品牌回归的源码断言改为同时约束 Discovery 提交品牌、补采分支不提交品牌，未放宽业务行为。

首次全部浏览器回归 174 passed / 1 failed，单独复核确认历史导入断言等待五秒恰等于现有轮询周期。用 Playwright 受控时钟明确触发该周期，保留原等待预算和断言，八项历史导入及最终全部 175 项通过。最终 Review 还修正统一类型的列表副标题，避免将显式评论补采描述成日期补采。

## 两阶段本地复核与文档

第一阶段重新读取引用会话最新统一方案、本轮取消新建批次补采入口的要求与 live #690 AC1–AC11，独立重建完成定义；反查两个页面每个操作的正式支持与后端能力的页面入口。第二阶段检查日期/AI 冻结、显式目标保留、身份诊断、预览/409 原子边界、Capability、评论层级、Raw 恢复、fencing、状态投影和轮询退出。最终修复后范围内没有阻塞项。本记录是本地自查，不替代平台规则或外部审批。

Docs Impact: targeted。同步 Blueprint 08 §25、Product 02、Collection 导航、模块 README、代码导航和运行中心开发基线；Blueprint 04 通用 Job 边界仍有效。开发基线记录用户确认弹窗决定，Figma 文件未改。无 Provider endpoint/payload/Mapper/外部分页协议变化，无真实付费 Probe。

## Shell 与交付状态

根属性只有 `*.sh text eol=lf`。tracked Shell 为 `scripts/setup_dev_environment.sh` 和 `scripts/deploy/reset_keep_vehicle_catalog.sh`，索引原本 LF，工作树修复为 LF并保持；除换行正文不变。未发现其他已有 Bash/sh shebang 文件；未新增 CI、部署文档或额外流程。

无依赖/配置/Secret/Schema/Migration 变更；新任务使用 v3 审计与冻结 Scope，旧 v2/history 兼容。未来发布或回滚需 API/Worker/Frontend 同版本，并先结清新内容补采任务。本轮用户授权验证后合并 main、原生归档和 Issue Closure，未授权或执行 Release/Deploy/生产操作。提交本记录时正式 CI、merge、main-fresh、Archive 与 Closure 尚未完成，以 PR #691、Issue #690 及原生自动化实时状态和后续证据为准。
