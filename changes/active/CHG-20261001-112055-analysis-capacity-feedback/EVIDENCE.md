# 本地实现与验证证据

> 以下原验证记录保留为前一阶段证据。最新 Windows/Linux 机器适配续修的范围、回归和资源状态见本文件末尾；旧阶段的 Ready/清理结论不能替代续修门禁。

日期：2026-10-01，北京时间。基线：15dd366db6e1632535fadc615513636a4b22c639；本地分支：fix/analysis-capacity-feedback；没有新增提交。结果对应本次工作树中的 Python/文档/测试修改，包含最终 HTTP 审计和独立审查修复。原有用户 Prompt 修改保留，不把它记为本次作者改动。

## 根因与验证边界

原用户日志的 200 条执行为 216.788 秒、201 次 HTTP、物理峰值 20；一次 45.114 秒超时被错误当成并发边界，20→10 后到 10→15 相隔 117.334 秒。完成请求全耗时被计入单观察窗，也导致占用估计超出实际峰值。此次用真实在途区间积分、探测阶段归属、持续拥塞证据和按秒恢复切断这些误判。

官方限额只作端点/精确模型探测提示：[DeepSeek 限流说明](https://api-docs.deepseek.com/quick_start/rate_limit/) 的 Flash 2500 / Pro 500 是账户与模型范围的在途请求额度，不能当作 RPS 或本机必能达到的吞吐。代理与未知模型不继承官方提示。同账号多个独立 Provider 配置没有可核验的账号统一身份，不能声称已严格共享账号额度；仍由真实限流反馈保护。

没有调用真实收费模型，没有 Gold Set 准确率或真实 DeepSeek 吞吐对照。请求体不新增 thinking/effort/max_tokens 等参数，保留模型原配置/默认行为；没有通过禁用思考提速。[官方思考说明](https://api-docs.deepseek.com/guides/thinking_mode/) 与代码请求体复核共同确定该边界。

## 已执行命令和结果

所有 Python 最终检查使用仓库锁定的 `.venv/Scripts/python.exe`（Python 3.14.7），没有升级依赖。pytest 临时目录在本任务专用 scratch 内，关闭通用 pytest cache；Windows 沙箱对 pytest 新目录有 ACL 限制的调用使用已审查的窄范围提权重跑，不修改用户目录 ACL。

| 检查 | 实际执行与结果 |
| --- | --- |
| Red 回归 | 原控制器的跨窗/单超时/恢复三项失败后修正；最终新增本地许可等待审计用例也先失败，再修正为通过 |
| 后端当前范围 | `.venv/Scripts/python.exe -m pytest tests/unit/analysis tests/unit/content/test_stage12_analysis_planner.py tests/unit/content/test_analysis_runtime_configuration_hash.py tests/unit/platform/test_capacity.py tests/contracts/test_stage12_analysis_run_http.py tests/api/test_analysis_runtime_capability.py -q -p no:cacheprovider --basetemp=scratch-capacity-feedback-20261001/unit-repair-21` → **276 passed**（9.77 秒），83 项既有弃用警告 |
| 隔离 PostgreSQL 完整相关组 | `isolated-env.ps1` 校验 127.0.0.1:55478/aima_capacity_feedback/codex_test 后，执行 Alembic upgrade head 和 adaptive_capacity、capacity_reservations、retry_recovery、provider_concurrency 四个集成文件；pytest `-q -p no:cacheprovider --basetemp=scratch-capacity-feedback-20261001/pg-repair-20 --junitxml=scratch-capacity-feedback-20261001/pg-repair.xml` → **60 passed**（108.76 秒），81 项既有弃用警告 |
| 正式 Worker 许可组合 | `tests/integration/content/test_analysis_adaptive_capacity.py::test_worker_combines_rps_with_shrinking_physical_capacity`，隔离配置及 `pg-gate-23` 临时目录 → **1 passed**（3.91 秒）；这是前组之后新增的用例 |
| 前期生命周期/历史兼容补充 | 关闭异常清理修改后，历史 v1 用例与 retry_recovery 文件 → **27 passed**（44.99 秒）；前期独立 200 条及 v1 HTTP → **2 passed**（14.97 秒）；均与最终组有重叠，不累加 |
| Frontend 静态检查 | `npm --prefix frontend run lint` → exit 0 |
| Frontend 单元 | `npm --prefix frontend run test -- --run --maxWorkers=2 --no-cache` → **274 passed / 36 files** |
| Frontend 构建 | `npm --prefix frontend run build -- --outDir ../scratch-capacity-feedback-20261001/frontend-build` → exit 0；836 modules，既有 chunk 大小提示；输出不写用户 dist |
| 独立 Browser Mock | `node frontend/node_modules/@playwright/test/cli.js test --config scratch-capacity-feedback-20261001/playwright.isolated.ts` → **174 passed**（3.7 分钟）；专属端口、独立浏览器上下文 |
| 最终 Real Full-stack | 重启仅本次专属 API/Worker 加载最终代码后，`node frontend/node_modules/@playwright/test/cli.js test --config scratch-capacity-feedback-20261001/playwright.fullstack-isolated.ts analysis-streaming.spec.ts` → **1 passed**（10.0 秒）；真实页面/API/Planner/Worker/PG/本地 Fake LLM，无路由 Mock |
| Python lint/format | 对 Git 已改动及新增的 24 个 Python 文件运行 `ruff check` 和 `ruff format --check` → 全部通过 |
| Python 类型 | `.venv/Scripts/python.exe -m mypy backend/src/aima_ugc` → **422 source files 无问题** |
| Contract | `scripts/contracts/generate.py --check`、`scripts/contracts/check_compatibility.py` → exit 0；公共生成 Contract 没有漂移 |
| 文档/Secret | `scripts/quality/check_docs.py`、`check_docs_facts.py`、`scan_secrets.py` → exit 0 |
| 差异 | `git diff --check` → exit 0；无 commit/push/PR/远程 CI/merge/main-fresh/Archive/Issue Closure |

最终修复后的 200 条真实持久链使用本地 Fake HTTP 每次约 3 秒响应。安全聚合日志在 13:12:26.169 显示初值 50，13:12:30.390 升到 100（相隔 **4.221 秒**），13:12:35.780 升到目标 200，13:12:37.087 完成。实际物理峰值 **100**，HTTP **200** 次，新增成功入库 **200**，Worker 执行 **11.020 秒**，数据库 **1242 ms**、容量控制 **560 ms**、恢复控制 **168 ms**、初始化 **33 ms**；rate_wait_ms、retry_wait_ms 和 Transport Retry 都为 0。目标 200 是探测目标，不能写成实际峰值。该结果证明调度与持久链生效，不能与原真实 DeepSeek 日志直接计算提速倍数。

大任务事件模拟用 10–16 秒非匀速延迟及 200000 条工作项，复用生产 Profile/控制器。容量 100/500/2500 和 2500→800→2500 各稳定区间成功速率至少达到相同时延静态容量参照的 80%；200 条加一次 45 秒长尾在 80 秒虚拟时间内完成。虚拟时间不是机器实测。资源不足仍受本地上限约束，不承诺达到声明额度。

## 扩展扫描的问题与复核限制

此前扩展全后端扫描输出为 **12 failed / 1729 passed / 16 skipped / 12 subtests**，没有把它报告为通过。两项受本次 v2 参数影响的 Planner Fixture 已修正并在最终范围回归通过；三个 Health asyncio 失败在独立锁定环境重跑通过，原扫描受浏览器报告测试留下的事件循环影响。

另有六项 `tests/unit/test_docs_navigation.py` 对 DOC007/DOC008/DOC009 的失败，以及一个报告截图登录遮罩测试触发真实浏览器的失败。本轮未修改文档检查器及其测试，六项用最小临时文档树仍可复现；不是对本次正式文档的链接检查失败。当前仓库 `check_docs.py` 与 `check_docs_facts.py` 直接检查均通过。报告浏览器测试不再启动重复探测，避免触碰用户浏览器环境。以上全仓问题未修复，正式全量后端/远程 CI 不能据本轮局部证据宣称全绿。

本轮先完成两阶段自审，再由一个只读 Reviewer 独立审查，首次结果 CHANGES_REQUIRED。CAP-REV-001 的端点身份/声明上界问题与 CAP-REV-002 的并发/RPS 排队突发问题有独立纯内存复现，本轮修复后重新取得证据；同一 Reviewer 的独立修复复核为 PASS / NO_FINDINGS_WITHIN_SCOPE，两项均 CLOSED，没有新增阻塞项，完整记录见 [REVIEW.md](REVIEW.md)。公共 HTTP/输出 Contract、依赖和 Migration head 均无变更；0076 的 downgrade guard 覆盖 adaptive.v2。历史 v1 的 45 秒 Timeout/256 物理上限真实回归通过。原已运行的用户服务继续使用加载时的代码，用户新建 Run 需在自行结束当前工作并按原运行方式重启之后启用 v2。

## 独立审查修复包

- CAP-REV-001：`ensure` 区分省略声明与当前端点明确无声明；当前 Revision 才能替换提示；warm start 限制在新声明以内，旧 Reservation 不清空。官方→未知、未知→官方及旧 Revision/省略参数的生产 Repository 内存回归先失败后通过；两个端点切换的真实 PostgreSQL 用例也通过。
- CAP-REV-002：动态 RPS 的原子即时尝试复用既有 RateLimiter，C/RPS 都允许立即发送才开始 Meter；等待可取消、不积累速率预约；C/RPS 更新在同一 Condition 内生效。物理发送间隔组合回归先失败（后两请求约 0.0003 秒间隔）后通过（至少 0.19 秒，目标 5 RPS），C 和 RPS 零许可两种等待的取消也通过。正式 Worker→真实 Fake HTTP→PG 的缩容组合用例另外通过，以实际 HTTP 审计起点间隔断言，排除 HTTP Server 清理耗时。
- 修复后完整相关单元/Contract/API 命令与前表相同，临时目录改为 `unit-repair-21`，最终 **276 passed**（9.77 秒）；新增 6 个端点/许可组合用例。
- 修复后四文件 PostgreSQL 集成命令通过 `isolated-env.ps1` 验证目标后执行，临时目录 `pg-repair-20`，**60 passed**（108.76 秒）；正式 Worker 限速组合在 `pg-gate-23` 另有 **1 passed**（3.91 秒）。它是新用例，前述重复执行的旧组不能累加。
- 修复后 full mypy 仍为 **422 files 无问题**；Ruff 对当前 **24 个 Python 文件**通过。前端源码及公共生成 Contract 未增加变更，既有前端 274/174/构建证据仍有效；最终 Full-stack 接线再次运行，**1 passed**（10.0 秒）。

为了验证审查修复，第一次资源清理后另建同样隔离的 `aima-codex-capacity-feedback-20261001-repair` 容器（新 ID，任务 repair 标签）和同名任务 scratch，禁止复用用户数据库。修复阶段 API/Worker/Fake LLM 已逐个核对 PID 与完整命令行并退出，容器及其匿名卷已按唯一身份和归属验证后删除；四个专用测试端口均无监听。修复 scratch 的最终清理状态在下方另行记录。

## 隔离与资源清理

测试 PostgreSQL 18.4 容器：`aima-codex-capacity-feedback-20261001`，标签 `codex.task=analysis-capacity-feedback-20261001`；只绑定 127.0.0.1:55478，无用户卷，1 CPU、768 MiB 内存。只对该 DB 执行 Alembic/Fixture/清理。API/Fake LLM/Frontend 分别为 55480/55481/55479；所有数据、Secret 和构建输出都在带 ownership.txt 的本任务目录。

初次验证阶段：测试服务退出已用准确 PID 与完整命令行校验，仅停止本次 API/Worker/Fake LLM；浏览器测试由 Playwright 回收。任务 scratch 已核验绝对路径、非链接目录及 ownership.txt 后删除。容器完整 ID、标签、私有端口、无显式挂载，以及匿名卷准确名称、Docker anonymous 标签、同一创建时刻和唯一引用均已核验，仅删除本次容器与其匿名卷。容器/卷列表复核均不存在该资源，55478/55479/55480/55481 四个专用测试端口均无监听。后续修复验证另建了自己的资源，没有复用该初次清理记录。

修复验证阶段：专属容器完整 ID 为 `7d97be7570b171f3a3461c62d5509a37e8d384d1793f15b4f39c3252a646cde5`，匿名卷为 `5b1196e2a1de2106c8f5eaa9869d117387a8d7e8f821f2b411f91c441190892e`；两者均已删除。停止的专属 API/Worker/Fake LLM PID 为 74336/47092/40260；停止前逐项校验命令，未停止用户进程。重跑需先按项目现有隔离测试方法建立新的专属 DB/目录/端口，不能直接指向用户 .runtime。

最终任务 scratch 已再次核验固定绝对路径、直接位于项目根、非 ReparsePoint 以及 `ownership.txt=analysis-capacity-feedback-20261001` 后，用原生 PowerShell 删除并验证不存在。修复阶段的临时配置、虚拟测试 Secret、构建产物和缓存已清理；用户 `.runtime` 不是清理目标。

最终记录完成后的机器检查：`check_change_completion.py --root . --require-active-ready`、`check_docs.py`、`check_docs_facts.py`、`scan_secrets.py` 和 `git diff --check` 均 exit 0。本 Change 状态为 `ready_for_review`，仅表示本地工作树完成定义通过，不表示远程交付。分支和 HEAD 与开工基线一致，未新增提交；用户 Prompt SHA-256 仍为 `9E0489A330DD1A5BFFCDEA90703310E37EB1ABF4CDF7AA53224A44864E261741`，与任务开始时一致。

## Windows/Linux 机器适配续修（decision epoch 2）

用户明确要求两种系统均充分利用实际可用机器性能；本阶段恢复 14,418 条真实记录并修复调度链，未访问运行中服务的数据库。真实任务 `3c95e7d6-fdad-5331-9783-256080670beb` 的 9 片全部串行，共 1,231.628 秒，14,418 成功/0 失败。父池所见 Windows 启动器 PID 58480 与实际持有 Lease 的解释器 PID 42340 不同，导致忙碌数被计为零、队列 1 被解释为无需扩容。尾部目标 1024 仅约 111 在途仍被当成充足需求，错误回退到 782。Linux 容器原压力读宿主累计计数，不能可靠反映自身有效配额。这些是机制证据，不能把重叠的数据库/控制耗时相加估算收益。

修复复用现有六个生产文件：worker_main 使用父子继承的稳定 Lease ID，PID 仅用于进程控制并记录实际 PID；Analysis Repository 复用正式重试就绪条件，排除在途和未入库项；Worker 分开 ready 与 pending，并优先判断自身已完成，防止终态父 Run 的探活禁令卡住最后一个 Shard；共享 Profile 不从未装满的窗口学习模型上界，保留真实 429 反馈；Planner 的既有 Job 窗口增加一个有真实后续分片的衔接槽，HTTP 许可仍原子预留；CPU 压力按 Windows 系统计数或 Linux cgroup v1/v2 有效核数采样，配额变化、计数复位和未知均重建基线。思考、Prompt、Taxonomy、Validator/repair/judge、历史 v1、Fence/取消和持久恢复保持。

### 新鲜验证

Windows 使用 Python 3.14.7、锁定依赖和任务专属 runner：它剥离继承的 AIMA 配置，只向子进程注入 127.0.0.1:55478/aima_machine_test/aima_test，以及任务 Secret/data/log 目录。Linux 使用正式 Dockerfile backend wheel，Python 3.14.7、非 root UID 10001、锁文件哈希约束的相同测试依赖；只读挂载 tests/docs/scripts/pyproject，测试临时目录在容器 /tmp。测试数据库只在两系统间顺序使用，不并行 TRUNCATE。

| 检查 | 实际命令及结果 |
| --- | --- |
| 根因 Red | 首组 5 failed：启动包装层只生成 1 Worker、低占用回退 782、缺少配额压力采样。首次 PG 2 failed：无就绪查询、只能投放 1 片。新多分片测试另发现 36 结果已成功但最后 Job 不退出；仅取消本次测试 Run 的 Job 收回线程。修正退出顺序后通过。 |
| Windows 完整相关回归 | `.venv/Scripts/python.exe -B scratch-machine-adaptation-20261001/run_isolated.py pytest tests/unit/analysis tests/unit/jobs tests/unit/platform/test_capacity.py tests/unit/test_compose_auto_scripts.py tests/integration/content/test_analysis_adaptive_capacity.py tests/integration/content/test_analysis_provider_concurrency.py tests/integration/content/test_analysis_retry_recovery.py tests/integration/content/test_analysis_machine_adaptation.py tests/integration/jobs/test_job_runtime.py tests/integration/jobs/test_worker_process_lifecycle.py -q -p no:cacheprovider --basetemp scratch-machine-adaptation-20261001/pytest-regression-2` → **357 passed**, 102.13 秒，exit 0。 |
| Windows 最终进程池单元 | 同 runner 执行 `pytest tests/unit/analysis/test_machine_adaptation.py tests/unit/jobs/test_worker_entrypoint.py -q -p no:cacheprovider --basetemp scratch-machine-adaptation-20261001/pytest-pool-final` → **13 passed**, 1.19 秒，exit 0，包含最终新增的忙碌进程缩容保护与出生日志。 |
| Linux 完整相关回归 | `docker run --rm --pull never --name aima-codex-machine-linux-regression-20261001 --label codex.task=machine-adaptation-20261001 --network aima-codex-machine-net-20261001 --cpus 3 --memory 3g`，只读挂载上述四类目录及专属测试 Secret，注入专属 PG 地址，再执行 `python -B -m pytest tests/unit/analysis tests/unit/jobs tests/unit/platform/test_capacity.py tests/integration/content/test_analysis_adaptive_capacity.py tests/integration/content/test_analysis_provider_concurrency.py tests/integration/content/test_analysis_retry_recovery.py tests/integration/content/test_analysis_machine_adaptation.py tests/integration/jobs/test_job_runtime.py tests/integration/jobs/test_worker_process_lifecycle.py -q -p no:cacheprovider --basetemp /tmp/machine-linux` → **354 passed / 1 skipped**, 93.31 秒，exit 0。唯一 skip 为 Windows venv 启动器专属测试；Linux 正式 Worker 子进程实际执行，未跳过。 |
| Linux 真配额压力 | 独占 `docker run --rm --pull never --cpus 0.5 --memory 256m` 容器，生产 detect_resources/CpuPressureSampler 实际忙循环 → `{cpu_cores:0.5, source:cgroup_v2, pressure:1.0, memory_limit:268435456}`，压力断言 >0.85，exit 0。 |
| Linux 正式打包 | `docker build --pull=false --target backend -t aima-codex-machine-adaptation:20261001 .` → exit 0，正式 wheel 和 backend 构建成功；镜像 manifest list SHA-256 `b549d4fb2c06a751b663bc2127d66b078e2b760dd855a8b4e089b3a645a5a380`。测试镜像由该正式镜像派生，未用临时 PYTHONPATH/sys.path 掩盖包发现。 |
| 静态与文档 | 六个直接修改生产文件的 mypy → **6 files 无问题**；11 个续修 Python 文件 `ruff check`、`ruff format --check` → exit 0。check_docs.py、check_docs_facts.py、scan_secrets.py 和 git diff --check 均 exit 0。 |

Windows 扩展首次 351 passed/1 failed 暴露无后续 Shard 的 waiting Run 不应额外占槽，修正为仅有真实后续分片时衔接；原断言保留并包含于最终两系统完整组。Linux 首次 280 passed/2 failed 是 docs/scripts 未只读挂载，补齐后原测试 282 passed，完整组继续通过。两次手工选择不存在的测试节点未执行测试，已修正为真实路径；一次沙箱临时目录 ACL 导致 3 passed/3 errors，改用专属 basetemp 的窄范围提权重跑。没有删除、降低断言或修改用户目录 ACL。Pydantic/Starlette 弃用警告沿用现状，不升级依赖。

新增跨片验收保持一个真实 Fake HTTP 请求阻塞，其他 35 次请求仍能发出、至少 24 项在该请求完成前已经入库，最终恰好 36 请求/36 成功/0 失败。正式入口测试实际观察到至少两种稳定 Lease ID；Windows 独立生命周期测试持有原生解释器句柄，证明停止本次 venv 启动器后实际解释器已退出。新增缩容测试证明内存压力只能收缩空闲 Lease。请求体仍只有 model/messages/response_format；没有关闭思考或缩短输出。测试不是 DeepSeek 真实吞吐或 Gold Set 语义准确率实测。

续修审查冻结基线：HEAD `15dd366db6e1632535fadc615513636a4b22c639`，分支 `fix/analysis-capacity-feedback`；30 个相关 backend/tests/migrations/docs 文件逐文件原始字节 SHA-256 的有序 JSON 汇总为 `684963ecc6ec52b307bc198158480e827541ab1d29b1a68235c12101e5299e0c`，不包含用户 Prompt、scratch 和 Change 证据文件。格式收口仅规范换行和测试函数签名，没有改变已验证行为。Prompt SHA-256 保持 `9E0489A330DD1A5BFFCDEA90703310E37EB1ABF4CDF7AA53224A44864E261741`。独立续修审查及最终清理记录待下方补充；不能沿用旧 epoch 的 PASS 作为本阶段审查结论。

最终入口节点在上述完整组之后，仅新增产生日志和 Harness 异常清理位置调整，再执行 `run_isolated.py pytest tests/integration/content/test_analysis_machine_adaptation.py tests/integration/jobs/test_worker_process_lifecycle.py -q -p no:cacheprovider --basetemp scratch-machine-adaptation-20261001/pytest-final-runtime-2` → **4 passed**（13.99 秒），exit 0；共享容量 Repository 受影响边界另执行 `tests/integration/content/test_analysis_capacity_reservations.py` → **7 passed**（6.52 秒），exit 0。两组与原用例有重叠，不能直接累计到总测试数量。当前 `scripts/contracts/generate.py --check` 与 `scripts/contracts/check_compatibility.py` 均 exit 0，没有生成 Contract 漂移。

Windows 原生资源接口另作一次无压力探测：`.venv/Scripts/python.exe -B -c` 调用生产 `CpuPressureSampler`、等待 2.1 秒，再调用 `detect_resources()`；断言 host 来源、压力非未知且在 [0,1]，exit 0。当时读取 `{cpu_pressure_source:host, cpu_pressure:0.0833, effective_cpu_cores:12.0, memory_limit_bytes:33999949824, memory_available_bytes:13553434624}`。这是实际系统计数可用性的证据，不是 Windows 满载性能压测；没有人为占满用户机器。

清理前只读核验本次日志的实际解释器/启动器 PID 19768、20164、40964、67424、74160、77200，全部不存在。没有停止任何用户进程。


### 续修独立审查后的测试生命周期修复

首次独立审查为 CHANGES_REQUIRED，MACHINE-REV-001/002 均为新 Harness 失败收尾，未确认新增生产阻塞缺陷。只修改两个新测试文件，新的30文件汇总 SHA-256 `a0046db44b459ada498fa43997788d0716d4da42ae88c4e12ea6221cf007759f`；未改六个生产文件，既有完整回归/构建证据仍覆盖它们。

Windows 运行 `run_isolated.py pytest tests/integration/content/test_analysis_machine_adaptation.py tests/integration/jobs/test_worker_process_lifecycle.py -q -p no:cacheprovider --basetemp scratch-machine-adaptation-20261001/pytest-review-repair` → **6 passed / 1 skipped**（19.24秒），exit 0；skip 为 Linux 专属强制进程组回收。两种失败观测分别触发原始“第一片没有开始发送请求”“下一分片”断言；真实 HTTP 释放、正式 Cancel API 提交都在真实线程执行器等待之前，失败之后没有 running Job。没有放宽原成功断言。

Linux 专属纯进程组回收单独运行 `tests/integration/jobs/test_worker_process_lifecycle.py`，同一锁定测试镜像、任务独占容器 /tmp → **1 passed / 1 Windows 专属 skipped**（0.39秒），exit 0。真实父子进程忽略协作信号，记录/验证独占进程组；协作超时后只终止本组，父进程 returncode=-SIGKILL，子进程消失或已退出为Zombie（无CPU/连接/执行），若pytest是容器PID1则waitpid回收。原始 AssertionError 保留，未遗留活进程；测试没有连接数据库。

Linux 正式 Worker/PG 受影响节点随后顺序运行：独占 `aima-codex-machine-linux-repair-runtime-20261001` 容器（同镜像/网络、3CPU/3GiB、只读测试及专属Secret），`python -B -m pytest tests/integration/content/test_analysis_machine_adaptation.py tests/integration/jobs/test_worker_process_lifecycle.py -q -p no:cacheprovider --basetemp /tmp/machine-linux-repair-runtime` → **6 passed / 1 Windows 专属 skipped**（23.69秒），exit 0；两种断言失败路径、慢尾成功路径、正式多进程入口和独占组强制回收均通过。Windows PG 已结束后才运行此组；纯进程测试没有SQL，只有该组使用测试PG。两个修复测试文件 Ruff check/format-check 均 exit0。相同用例重复运行不累计测试总数。


最终摘要覆盖校准：最初的30项清单含29个Python文件及Analysis README。Git默认中文路径引号转义使两份中文文档未进入字节清单，它们已在正式文档语义审查和机器检查中覆盖。使用git `-z` +显式UTF-8补齐后，原30项哈希全部相同；最终32项汇总SHA-256为 `5d0f5b8e6f8211763d6a78deef6518469cc7d41d6205964b8a4fad43380c5aa4`，完整路径/哈希保留在[REVIEW_BASELINE.json](REVIEW_BASELINE.json)，重新解析并逐文件校验通过。本次只校准摘要范围，未改变实现或文档。

最后静态收口：所有29个改动/新增Python文件 Ruff check、format --check 全通过；全后端 mypy **422 source files无问题**。check_docs.py、check_docs_facts.py、scan_secrets.py与git diff --check均exit0。修复后只修改上述两测试文件，既有357/354完整生产链证据仍适用，受影响两平台正式节点及新增失败路径另有新鲜证据。


### 续修测试资源回收

全部测试结束后，已再次验证 PostgreSQL 容器完整 ID `b4611d199cec97c2a87139a358b8d513ea3be2de623372eb59dd89d3383e1863`、任务标签、AutoRemove、唯一匿名卷挂载/引用；只停止该容器，其匿名卷 `b6b94a2c773cd2567c786206f73f344b1bc7c6c05fb65467851bd79432ede182` 随容器自动回收，容器/卷列表验证不存在。任务网络完整 ID `7a0512bf84e3dbe8ad684dce15a01cb24bd61c4800456066d576d972555c61ce` 的名称/标签及空引用验证后删除。Linux各测试容器均 --rm 自动回收，没有对用户容器/网络/卷操作。任务测试镜像及其旧无标签版本只按已记录完整ID回收，官方基础镜像和共享构建缓存保留。


MACHINE-REV-003 是首次Review漏检的相邻Windows生命周期早期失败收尾，Reviewer内存复现原始断言被TimeoutExpired替换且Popen未停止。局部修复后执行 `run_isolated.py pytest tests/integration/jobs/test_worker_process_lifecycle.py -q -p no:cacheprovider --basetemp scratch-machine-adaptation-20261001/pytest-review-windows-early` → **2 passed / 1 Linux专属 skipped**（5.43秒），exit0。真实启动本次父子进程，只隐藏ready文件观测，直接调用原测试函数并持实际解释器原生句柄证明退出；原始ready断言保持，未连接DB。新增Windows代码不改变已验证Linux回收入口，未为此重建/重跑Linux容器。单文件Ruff check/format均通过。

第三项修复后的完整32项摘要为 `35e729e6b6bcfc01f9050141d0529a395d6878857925343dac174d955312aa38`，清单已更新并重新解析验证。前32项摘要保持为本阶段前次修复身份；本次仅一个Windows测试文件变化，生产实现保持冻结。


最终任务 scratch 清理：重新验证固定绝对路径 `E:/work/03_Aima/code/AIMA_UGC/scratch-machine-adaptation-20261001` 的父目录、非ReparsePoint、ownership.txt=machine-adaptation-20261001及全树无链接；所有本轮日志记录的21个Worker/启动器PID均已不存在后，用原生PowerShell仅删除该任务目录并核验不存在。专属PG端口55478无监听；临时Fake Secret/数据/缓存/测试镜像均回收。用户 `.runtime`、正在运行的代码/数据库和官方基础镜像/共享Docker缓存不属于清理目标。完整32文件审查清单已保留在Change中，清理后重新解析及逐字节校验仍通过，摘要 `35e729e6b6bcfc01f9050141d0529a395d6878857925343dac174d955312aa38`。


最终独立REPAIR_DIFF通过，MACHINE-REV-001/002/003全部CLOSED，无未关闭范围内阻塞。Review完整结果和独立内存失败投影见REVIEW.md；32文件当前身份由REVIEW_BASELINE.json持久保存。更新本地Change为ready_for_review，随后执行最终完成/文档/Secret/差异检查；远程交付继续不执行。


首次最终Ready检查发现R8–R12 Source只有用户决定定位，缺少机器可识别的稳定Acceptance，产生5条记录错误；未把shell后续检查的exit0误报成Ready通过。已按语义将五项分别关联正式Blueprint AC17/AC4/AC14/AC17/AC16，并保留用户决定来源；只更新追溯metadata，没有改变上游完成定义、实现、测试或正式文档。随后单独重跑Ready检查，以独立退出码确认最终结果。


Source校准中的双来源单元格不符合当前validator要求的“单Owner + 末尾稳定AC”语法，第二次检查仍明确exit1；改为正式Blueprint单Acceptance绑定，并在相邻正文保留用户决定来源后，单独运行 `.venv/Scripts/python.exe -B scripts/quality/check_change_completion.py --root . --require-active-ready` → **exit0**（gated150/strict150/legacy128），没有修改validator或降低检查。最终文档事实、文档入口/链接、Secret、Contract、Ruff与差异检查均exit0，相关实际测试和独立Review记录见上文。最终Change为ready_for_review，HEAD/分支保持开工值，无新增提交或远程动作。已完成本地代码和隔离验证目标；用户自行结束现有任务并按原入口重启后端后，新Run才加载新实现。

## 持续恢复与容量反馈续修（decision epoch 3）

上游为用户最新“正常内容全部处理、格式不合规持续重试”的目标，以及最终确认“连续五分钟真实网络不可用停止”。历史 v1 不改写。最新真实 Run 1897e971-5cc7-5360-9003-45c054e9fc6e 为 14618 目标、13988 成功、630 终态汇总未完成：412 已投放未完成、218 未投放。日志中的 343 个 429、1 个发送超时、27 个校验反馈是 Attempt/反馈口径，不能等同 412 个独立模型失败。没有恢复或写入该用户 Run，没有重新调用收费模型。

根因 Red 使用正式反馈/Repository：旧阶段 429 让 1000→500→250→125→62→31，等待 Future 使真实物理占用为零仍无法取许可，首组 2 failed。独立审查再发现 RPS 未切阶段、无 ready 仍 wanted=1、余数不可借，第二组 3 failed/10 passed。修复切换收紧后的发送阶段、暂停发送时原子采样物理占用、零 ready 归还份额及完整余数借额；原始错误保留诊断，control_* 只计实际参与决策的当前错误。健康 RPS 上升不切断长延迟请求的成熟证据。

v2 移除格式失败的五分钟截止，保留 Validator/repair/judge、思考及 Prompt；网络窗口只接受无 HTTP 响应的真实网络/发送超时失败，任何 HTTP 响应切断不可用窗口。本地排队与池等待不计断网，一次失败加五分钟本地等待不证明持续断网。Job 三次 Attempt/1800 秒不增加，耗尽后正式同类型后继 Job 原子绑定原 Request，保留 Item、断点和成功项；旧 Fence/回调、取消及已停止 Run 受到保护。

验证资源为独占 PostgreSQL 18.4：127.0.0.1:55488/aima_recovery_test/aima_test，容器完整 ID 091289bf5196535e268d01ca1ced7a2f28b2ab3e4297cb0a31129dbce0a9fdf6，标签 codex.task=analysis-recovery-20261001，2 CPU/1GiB。runner 剥离继承 AIMA_*、SSLKEYLOGFILE，只向子进程注入专属地址与 Secret/data/log，普通测试不连接用户业务 DB。Linux 专属网络 ID cb859af4fede9ee99cbbfc44f7187fe25a358a13a006874558d08e4929411a40。测试容器非 root UID10001、3CPU/3GiB；Windows/Linux 顺序使用本次库，不并行 TRUNCATE。

| 检查 | 实际执行与结果 |
| --- | --- |
| Windows 完整相关回归 | `.venv/Scripts/python.exe -B scratch-analysis-recovery-20261001/run_isolated.py pytest tests/unit/analysis tests/unit/jobs tests/unit/platform/test_capacity.py tests/unit/test_compose_auto_scripts.py tests/integration/content/test_analysis_adaptive_capacity.py tests/integration/content/test_analysis_capacity_reservations.py tests/integration/content/test_analysis_provider_concurrency.py tests/integration/content/test_analysis_retry_recovery.py tests/integration/content/test_analysis_machine_adaptation.py tests/integration/jobs/test_job_runtime.py tests/integration/jobs/test_worker_process_lifecycle.py -q -p no:cacheprovider --basetemp=scratch-analysis-recovery-20261001/pytest-windows-full` → **385 passed / 1 Linux专属 skipped**，170.16秒，exit0。 |
| 接续/Cancel 并发补测 | 同 runner 运行 `test_analysis_retry_recovery.py::test_v2_successor_and_cancel_api_race_preserves_results_and_cancels_current_job` 与 `::test_v2_deadline_exhaustion_continues_same_items_without_repeating_success` → **4 passed**，8.67秒，exit0。两个 Cancel 顺序使用实际 SQL 行锁等待，Reaper 先持旧锁时 Cancel 读取旧集合并等待，提交后重新取集合并取消后继；取消先提交时不生成后继。 |
| Linux 完整相关回归 | `docker run --rm --pull never --name aima-codex-recovery-linux-regression-20261001 --label codex.task=analysis-recovery-20261001 --network aima-codex-recovery-net-20261001 --cpus 3 --memory 3g`，只读挂载 tests/docs/scripts/pyproject 与本次 Secret，注入 recovery-pg:5432 独占 DB；运行与 Windows 完整组相同 pytest 文件集合 → **386 passed / 2 Windows专属 skipped**，133.53秒，exit0（包含随后新增 Cancel 两顺序）。 |
| 最终 Windows 受影响文件 | 同 runner 执行 `pytest tests/unit/analysis/test_capacity_diagnostics.py tests/unit/content/test_stage12_analysis_planner.py tests/integration/content/test_analysis_retry_recovery.py -q -p no:cacheprovider --basetemp=scratch-analysis-recovery-20261001/pytest-final-recovery` → **53 passed**，58.75秒，exit0；覆盖最终新增健康 RPS 成熟证据与提取的成功夹具。 |
| 正式 Linux wheel | `docker build --pull=false --target backend --label codex.task=analysis-recovery-20261001 -t aima-codex-recovery-backend-final:20261001 .` → exit0，manifest list SHA256 b6343c0bc92e61dbc774479897225bbc787e8d293b27d2f301209b336b7720dd。测试工具根据 uv.lock --frozen/--require-hashes 安装，最终测试镜像从正式 wheel 安装文件复制当前包，未使用 PYTHONPATH/sys.path/源码包替换。 |
| 静态与 Contract/文档 | 全后端 mypy → **422 source files 无问题**；全部38个修改/新增实现、测试、Migration、正式文档中的35个Python文件 Ruff check/format通过。`check_docs.py`、`check_docs_facts.py`、`scan_secrets.py`、`scripts/contracts/generate.py --check`、`scripts/contracts/check_compatibility.py` 和 `git diff --check` 分别exit0。 |

同用例重复执行不累计为更多独立测试。关键工作流：12条/3片中一条错误起点已超过十分钟，仍继续修复并最终12成功，11条正常项不重发；20条/2片缩容10→2后首批10个迟到429排空，最终20成功/0失败，物理30次（10拒绝+20合法）；C=1 时一片退避一小时，另一片4条全部成功，父Run running/pending4/failed0；Deadline 耗尽前一项已真实成功，后继仅发送剩余2项；插入后继后注入异常，旧Job终态、后继插入和绑定一起回滚；legacy/cancel/network/auth四种终态不续接。未完成正常内容不伪装成成功。

测试期间出现的环境/夹具问题保留：Windows basetemp ACL错误改用本任务目录的窄提权runner，未改用户ACL；模拟HTTP把respond置于记录锁内导致屏障不能并发，已移出锁并使用256监听队列，没有增加原等待预算；C=1场景曾在Job认领前查询active得到空集，改按同一Job UUID顺序冻结待认领片的退避事实；新阶段速率用完整墙钟六秒，修正错误的两秒测试计算，保持新拒绝必须收紧的断言。Linux测试镜像首次使用venv无pip，改用基础镜像自身pip安装固定uv；正式Dockerfile不变。最终静态只规范本次文件换行/导入/长行，没有降低检查。既有 Pydantic/Starlette 弃用警告保持，不升级依赖。

本轮文档 targeted：Blueprint AC4/AC12/AC13/AC15/AC18同步批准的恢复和完成定义；Analysis模块README导航机制，AI专题解释计时、接续、终态统计和legacy边界。无公共HTTP/输出字段或依赖/Schema/head变化；0077只增强downgrade guard兼容两恢复版本，upgrade DDL未变。用户Prompt SHA256仍为9e0489a330dd1a5bffcdea90703310e37eb1abf4cdf7aa53224a44864e261741。

最终审查基线为38文件，汇总SHA256 c92ef47ce4b9fd698167bc826909ddc1db544d347168a5d79968b977a3409d24；原始字节清单和epoch2历史完整保留于 REVIEW_BASELINE.json。仅本地工作树，HEAD/branch保持开工值；无commit/push/PR/远程CI/merge/deploy，不将FakeHTTP与容器验证称作真实DeepSeek收益或16核64GiB服务器实测。

最终Linux受影响文件：`docker run --rm --pull never --name aima-codex-recovery-linux-final-20261001` 使用相同3CPU/3GiB、非root、只读挂载和独占DB，镜像 aima-codex-recovery-test-final:20261001（manifest list SHA256 67afae9ca2baa917f6c82dd999427602bee834309e52de681acbe5dcb5904171），运行与最终Windows相同的三个pytest文件 → **53 passed**，51.44秒，exit0。当前格式/新增成熟证据/成功夹具提取均已两平台复验；其余文件保持完整组通过时的行为，复用有效结果，不机械重复全仓。

本轮资源清理完成：再次核验任务标签、完整ID和引用后，仅停止专属PG 091289bf5196535e268d01ca1ced7a2f28b2ab3e4297cb0a31129dbce0a9fdf6；AutoRemove使匿名卷e7e4ffa8946856305264c3afa482fa51723183d6ed70a15e03fafb91667dd4ec一同消失。网络cb859af4fede9ee99cbbfc44f7187fe25a358a13a006874558d08e4929411a40确认引用0后删除；四个专属镜像按完整ID删除，基础镜像和共享缓存保留。再次按codex.task标签列容器/网络/镜像及按卷名查询均为空；55488无监听。

scratch清理前验证固定绝对路径E:/work/03_Aima/code/AIMA_UGC/scratch-analysis-recovery-20261001、非ReparsePoint、ownership.txt=analysis-recovery-20261001、全树无链接，使用原生PowerShell仅删除该目录，核验不存在。Windows/Linux测试已退出，正式进程生命周期断言通过；没有停止用户进程或改其ACL。用户.runtime与其他项目的DB/容器/镜像不属于清理目标。持久38文件审查清单仍可解析并对应当前真实文件；用户Prompt哈希保持开工值。

## 最终审查速率分配修复（decision epoch 4）

epoch3 最终审查为 CHANGES_REQUIRED，003 属于 UNCHANGED_BASELINE / FIRST_REVIEW_ESCAPE。Red `test_idle_shard_does_not_dilute_available_send_rate` 实际得到5而期待10，1failed；修复后的 Owner 原子保存同 Fence C/RPS，Feedback 同事务读取。旧正速率承诺不被重复借出，未知记录保守保护，闲置/零 C 归还未来发送速率。本机 C 远小于全局 C 时唯一发送者仍得到完整可用 RPS；多片需求恢复、降档和小数速率均覆盖。控制版本升级保留未过期承诺，新增 shard_rps 仅作安全聚合日志。

测试资源重新创建：专属 `aima-codex-rps-pg-20261001`，完整ID `2f4ec5ea77d4cd7f99055d7ada8b622d97d4d9013a9cefa23fc72c2f8594727a`，标签codex.task=analysis-rps-20261001，回环55489/aima_rps_test，2CPU/1GiB，无用户卷；独占网络 `4c9c2fe93c7e204200fe51b5d9ada157e3bc342f098c685b8c893d4bb613f5ba`。临时目录scratch-analysis-rps-20261001有OWNER标记。隔离runner清除继承AIMA_*及SSLKEYLOGFILE/GITHUB_ACTIONS，只传本次假凭证和目录。第一次setup只覆盖external_secret_dir，初始化在缺少本地postgres_password文件时停止、未连接业务库；补齐独立secret_dir和正确文件后 Alembic upgrade head exit0。

首组真实PG测试16passed，新增C=1完整链因测试遗漏import两项失败，修正后继续验证。较大Windows组 `tests/unit/analysis` 加 adaptive_capacity、capacity_reservations、retry_recovery 三个集成文件：328passed/1failed，唯一失败是原C=1两片断言仍要求1RPS；批准行为应为唯一发送片使用全局2RPS，断言改为[0,2]并保留总额=2，没有降低保护断言。

追加小数速率和三片场景时，一次定位命令误与正在运行的本任务回归共享测试库，另一个Fixture的TRUNCATE干扰本次接续和缩容测试；该组4failed/86passed **整体不作为通过证据**。没有使用用户库或影响用户运行。后续所有PG验证严格顺序执行，不同时TRUNCATE。另两项测试配置错误分别是小数使用旧整数max_rps接口、三片只运行两个Planner/使用两Job显式窗口；均只修测试配置，没有改生产来迎合夹具。三片场景先以明确六核资源事实准入三任务，再降低模型速率；Linux真实容器仍维持3CPU/3GiB，其他资源边界不伪造。

最终Windows五文件命令：`.venv/Scripts/python.exe -B scratch-analysis-rps-20261001/run_isolated.py pytest tests/unit/analysis/test_capacity_diagnostics.py tests/unit/analysis/test_llm_rate_limit.py tests/integration/content/test_analysis_adaptive_capacity.py tests/integration/content/test_analysis_capacity_reservations.py tests/integration/content/test_analysis_retry_recovery.py -q -p no:cacheprovider --basetemp=scratch-analysis-rps-20261001/pytest-windows-sequential-final --junitxml=scratch-analysis-rps-20261001/windows-rps-final.xml` →90passed/1failed，126.62秒。剩余唯一失败为三片夹具仍受两Job窗口限制；只修对应显式窗口后，整个预留文件在pytest-windows-reservations-final中 **17passed**，18.54秒，exit0。随后三片用例明确资源事实，单项补验 **1passed**，2.02秒，exit0。其余四个文件74项在五文件组全通过且内容未再变化，不机械重复。完整JUnit可解析；不把重叠组累加。

真实事务覆盖：10/0.08 RPS 两片均分→空闲归还→唯一发送者借满→恢复者先0再收敛公平；旧HTTP仍占C而不占未来RPS；全局10→2与恢复10；第三新持有者不能绕过旧承诺；缺失/None旧记录；新Fence旧未知速率及TTL；reserve写入后异常整体回滚；旧控制版本升级保留承诺。C=1/一片格式退避一小时/一片4条正常的有限10RPS完整链成功入库4条、pending4、failed0，并验证实际HTTP间隔不越过保护。动态0.04RPS虚拟物理发送间隔25秒，没有最低速率抬高；真实长间隔等待取消一秒内退出且没有新物理占用。

Linux正式当前wheel验证镜像manifest list SHA256 `28ca2583b57f563814d617afe39e73e4f2a9b33287941922f34fb940fe659957`；scratch Dockerfile只追加验证stage，复用原backend-builder的wheel/锁定uv及--frozen/--require-hashes dev依赖，不改正式Dockerfile、不改变工作目录/PYTHONPATH/sys.path掩盖打包。当前两系统最终结果和独立修复复核在下方补充。

最终Linux：`docker run --rm --pull never --name aima-codex-rps-linux-final-20261001 --label codex.task=analysis-rps-20261001 --network aima-codex-rps-net-20261001 --cpus 3 --memory 3g`，非root、只读tests/docs/scripts/pyproject与本次假Secret，DB=rps-pg:5432/aima_rps_test；命令 `python -B -m pytest tests/unit/analysis tests/integration/content/test_analysis_adaptive_capacity.py tests/integration/content/test_analysis_capacity_reservations.py tests/integration/content/test_analysis_retry_recovery.py -q -p no:cacheprovider --basetemp=/tmp/pytest-rps-final` → **332passed**，97.32秒，exit0。没有和Windows同时执行数据库测试。实际Python3.14.7和已安装当前wheel，测试镜像工具依uv.lock，用户库/服务从未作为目标。

Windows JUnit重新解析：未再修改的四文件74项全部passed（diagnostics14、rate_limit7、adaptive_capacity14、retry_recovery39）；预留文件首次16passed/三片fixture1failed，最终整个预留17passed/0failure/0error，之后明确资源的三片单项1passed；不累加重复执行。实际全部受影响用例在当前实现上取得证据，而非将有失败的原组写成全绿。

最终静态runner逐条校验返回码：35个修改/新增Python文件 Ruff check 和 format --check均exit0；全后端mypy **422files无问题**；check_docs.py、check_docs_facts.py、scan_secrets.py、Contract兼容、Contract generate --check、git diff --check分别exit0。warning只有既有依赖弃用、Git换行及专属pytest目录沙箱ACL只读枚举提示；没有关闭检查、升级依赖或修改用户ACL。冻结38文件摘要 **4a43dab236787296d96c7189fe451b6fd311cd523139b60e046296d326b6a229**，10文件相对epoch3有变化，全部历史字节清单完整保留，Prompt SHA256不变。

Docker清理已逐项验证：只停止上述完整ID和标签的专属PG，AutoRemove回收匿名卷`88161d89c25008607f2ca68a2342e48b0638e2ee1329f5c56e482e1eb12a96da`；网络引用为空后删除完整ID；只删除专属镜像manifest list `28ca2583...`、`4e9ddb5d...`。按本任务标签查询容器、网络、镜像及按准确卷名查询均为空；55489没有监听。共享基础镜像/缓存保留，其他任务和用户容器未操作。scratch待最终审查及JUnit核验后按固定绝对路径和OWNER清理。

最终独立REPAIR_DIFF结论PASS / NO_FINDINGS_WITHIN_SCOPE，003 CLOSED，001/002与前序项继续CLOSED，没有残留范围内阻塞；A1/A2成立，38文件与Prompt开始/结束两次核验一致，初次漏检保留。持久REVIEW已写入本轮实际结论，Change为ready_for_review。`check_change_completion.py --root . --require-active-ready`首次发现历史epoch2与当前完成审计在同节造成四个重复字段；仅将历史记录移到单独顶层历史节，保留全部内容，重跑 **exit0**（gated150/strict150/legacy128），未改实现或冻结清单。

独立审查已实际解析Windows XML、全部验证进程退出后，cleanup只对固定绝对路径E:/work/03_Aima/code/AIMA_UGC/scratch-analysis-rps-20261001核验父目录/OWNER=analysis-rps-20261001、根与全树无ReparsePoint，再使用原生PowerShell Remove-Item -LiteralPath删除并确认不存在。临时Secret、Dockerfile验证stage、JUnit、测试目录均回收；用户.runtime和其他运行资源保持。本地分支与HEAD仍为原值，无Git提交/远程交付或部署。

清理后最终复核：require-active-ready、check_docs、check_docs_facts、scan_secrets、git diff --check均exit0；重新解析持久清单并读取38文件，原始哈希与汇总一致，Change状态ready_for_review且无not_satisfied，scratch不存在，用户Prompt哈希不变。仅本地交付，不宣称全仓或远程CI、付费模型吞吐、Gold Set或服务器实部署已验证。


# 远程 main 本地同步与组合验收（2026-10-01）

用户最新授权为拉取 main 同步到本地，保留两边功能；没有授权推送本地打标修改。已从15dd366d快进到64bfade1，当前任务分支与本地main均和origin/main一致，远程main经ls-remote再次核对仍为同一版本。没有新建实现提交、push、PR、远程merge或部署。

同步前外部目录逐文件备份43项，再stash含untracked、fast-forward、apply精确stash。唯一共同文件Blueprint自动合并，无unmerged/staged路径；除了该文档，其余42项原始字节恢复，Git的LF/CRLF转换也已核对。用户Prompt SHA256仍为9e0489a330dd1a5bffcdea90703310e37eb1abf4cdf7aa53224a44864e261741。正式报告决定与本地35/36节、AC1–AC18均保留，AC10仅补充本地main同步的新授权。

完整命令、首次失败和后续有效结果见 [changes/active/CHG-20261001-112055-analysis-capacity-feedback/MAIN_SYNC_EVIDENCE.json](MAIN_SYNC_EVIDENCE.json)。Windows行为/API/Contracts有效覆盖524个不同用例；首次523passed/1failed由临时runner全局external_secret_dir干扰fixture产生，删除该临时覆盖后原3个用例通过，其中2个重叠，不累计526。Windows独占PG/Worker/品牌9文件112passed/1Linux-only skip，180.84秒。

Linux正式当前wheel、非root10001:10001、3CPU/3GiB，复用本任务PG容器私有网络；有效384个不同用例通过，3个不同skip为2个Windows-only及1个显式opt-in真实报告浏览器用例。首次264passed/120setup errors是原CI凭据护栏拒绝；只修正独占测试账号后111passed/9报告setup errors源于只读Secret Root，再选可写子路径时因根目录不存在继续被严格校验拒绝。最终用镜像已有、独占、非root持有的/app/data作为Fake Provider Secret Store，原报告9passed/1skip，12.55秒。未改生产安全护栏、测试断言或依赖。GITHUB_ACTIONS标志只用于复现本地CI隔离布局，不代表远程CI执行。

前端独立源码/缓存副本全量unit先272passed/2环境路径错误，补齐相邻Guide、当前Prompt和锁定解释器路径后原2文件8passed；其中6项重叠，最终274个不同用例。当前副本的管理员数据库报告、发声规则和声音广场浏览器Mock14passed/37.5秒；lint、正式build及两套TS/Vue类型检查exit0，保留已有大chunk警告。没有连接用户8090后端，副本proxy指向未使用的55492；专用Vite使用55491和Playwright独立浏览器上下文。

Ruff check/format验证100个组合影响Python文件通过；mypy430source files通过；Contract生成check和兼容check通过；独占PG实际head0078、Alembic check无新upgrade差异。项目文档、机器事实、Secret、架构和git diff --check全部exit0。唯一CI classifier对旧基线至当前工作树142项选full；本地验收按组合风险选择以上回归，不宣称全部full CI、UI→真实API全栈、实际服务器性能或付费模型准确率。

38项冻结本地清单现绑定64bfade1，aggregate e90ee1e36245133a6bf8b230ba9e8c2e6170ad78dfa4990b4381a0bda829fb87，37项实现/测试字节与epoch4一致；前版本完整保留。测试目录、容器、镜像、stash及外部备份的收尾结果另在本节后记录。

最终独立审查为 **PASS / NO_FINDINGS_WITHIN_SCOPE**，38项清单和用户 Prompt 开始/结束均一致，前序 Finding 继续 CLOSED，范围与证据限制保留在 REVIEW.md。审查后没有生产代码、测试或冻结文档变化，仅补充本 Change 的审查及清理记录。

本任务测试资源已清理并查询确认不存在：仅停止完整ID `0ed8ffa00b7ccde718dde470def998ceff5ec9d3d10796a1b0fa4628b3451591`、标签 codex.task=main-sync-20261001 的专属PG；AutoRemove同时回收匿名卷 `71a5375508d692706b5c2e1fe602d937b9d2b5b04bb65bc3df4e597248781a8c`。只删除专属验证镜像manifest ID `sha256:ab9de6519813dcc58937618d3c24e1976749497172e96349c6fe45fccbe7a418`，共享基础镜像和缓存未清理；各 Linux --rm 测试容器已退出。按任务标签、准确卷名和镜像tag查询均为空，55490/55491/55492均无监听。

scratch-main-sync-20261001清理前核验固定绝对路径及 OWNER=codex-main-sync-20261001，先逐一验证并移除指向原 .venv 与 frontend/node_modules 的两个junction，确认原目标仍存在，再核验剩余树无ReparsePoint并用原生PowerShell LiteralPath删除本目录。清理后scratch不存在，原解释器和依赖目录仍存在。外部备份 C:/Users/YNND/AppData/Local/Temp/aima-main-sync-20261001-32qbh89l 的owner/root/43项恢复状态均复核后删除，确认不存在；仅精确核对后drop本次stash，stash list为空。

没有主动重启用户服务、操作用户数据库或运行业务库迁移，没有付费模型、TikHub或飞书真实请求。0078仅在本次独占测试库验证；用户业务库实际迁移/部署状态未验收。本地修改继续以未提交工作树保留，没有暂存或unmerged路径，没有push、远程CI、远程合并、Archive或Issue Closure。

清理后的最终 Ready Check 首次 exit1：新增 R18 Source 只写用户消息标识，不符合要求的稳定 Acceptance 引用；仅改本 Change 的 Source 为已同步授权的 Blueprint #AC10，并保留原用户消息追溯，没有改冻结文档或实现。重跑 `.venv/Scripts/python.exe -B scripts/quality/check_change_completion.py --root . --require-active-ready` **exit0**，gated152/strict152/legacy128。check_docs、check_docs_facts、scan_secrets均exit0；最终Git身份、38项文件哈希、Prompt、无暂存/无冲突/无stash、临时目录及备份不存在、原解释器和依赖存在、git diff --check均实际核验通过。没有用Ready Check代替完整远程CI。

## 2026-10-02 最新运行误判修复与逐条成功验收（decision epoch 8）

最新授权为本地修改、提高成功入库速度、每条成功才正常完整退出，保留思考与打标准确性机制。历史证据不代替本轮。最新健康日志的稀疏格式错误和短窗吞吐波动会重置探测或形成错误平台；修正为控制版本3同档成熟且充分负载的累计成功/墙钟证据，两个完整不足收益块才拒绝候选。明确请求/token配额429优先于静态模型并发声明；物理反馈保留分类。新recovery.v2只有succeeded等于target才能正常成功，stale显式非成功，旧版本不能应用到变化后的内容。

Controller/分类最初Red为5failed，stale成功门禁Red为1failed，空闲累计清理Red为1failed。独立审查epoch7发现CAPACITY-V3-REV-001：最后Fence释放和本地受限低样本早返回可遗留候选。新增生产控制器Red 1failed；真实隔离PG的last/peer/unknown三参数Red 1failed/2passed。修复后最后预留退出清除候选和尾窗，安全档保留；peer/未知未过期Fence继续保护C/RPS和共享证据；本地受限检查先于低样本返回。对应Green 3passed及feedback/workloads 27passed。新增PG从两个成熟2秒窗口真实产生4秒20成功候选，经1秒未闭尾窗、release、5分钟空闲、同身份ensure/reserve/observe，下一批不能借旧样本提前升档；墙钟可控而SQL事务/Owner与控制器真实。

最终冻结38文件aggregate为`3de577e65419ed45c4c77b44718d5eeef4ff8239ad1cea1c7a2c4f9afbc2d3a5`，基于`64bfade138e6cdf0f86e8d8961a0415b8f994ea8`的本地分支`fix/analysis-capacity-feedback`。epoch7相对修复只5文件；epoch5至本轮15文件变化，其余23文件原字节保留。用户Prompt SHA256仍为`9e0489a330dd1a5bffcdea90703310e37eb1abf4cdf7aa53224a44864e261741`。控制器当前SHA256为`656e3e7e6526c4c59d458ad353af9f1f76b48466540fd78adb9a3044e355e803`。

Windows最终实际命令：`.venv/Scripts/python.exe <本次隔离runner> -m pytest -q tests/unit tests/contracts tests/api -p no:cacheprovider --basetemp=<本次仓库外独占目录>`，**1843passed / 16skipped / 12subtests，93.14秒，exit0**。隔离runner清除继承的业务配置、只设置127.0.0.1:55493/aima_analysis_probe和本次数据/日志/Secret目录。四个PG组为`test_analysis_adaptive_capacity.py`、`test_analysis_capacity_reservations.py`、`test_analysis_retry_recovery.py`、`test_analysis_machine_adaptation.py`，**80passed / 139.70秒 / exit0**。这些组有重叠，不累计为独立用例总数。

201条跨3片混合负载中，1条连续六次非法JSON，第七次合法后成功；其余200条各调用一次。第七次修复前有pending、父Run不标succeeded；最终201success、0failed、0pending，全部预留释放。另有旧v2升级保留物理/RPS承诺、真实断网五分钟停止、402硬错误、取消、接管、续接、未投放片、慢尾部及stale显式非成功回归。没有降低业务校验或修改thinking请求参数。

页面验收通过既有两个正式spec：`analysis-streaming.spec.ts`、`stage12-historical-analysis.spec.ts`，**2passed / 38.1秒 / exit0**。实际Chrome经正式Vite、API、Worker、独立PG和既有FakeHTTP，验证页面提交两条内容的并发及合法结果，以及历史导入/selected与all打标。端口55494/55495/55496和数据库aima_analysis_probe_browser独占，退出后已验证全部测试服务端口释放。临时harness只替换地址和目录，不复制业务实现。最初本地ready失败来自父测试进程继承的SSL调试文件权限，清除该进程环境后原两spec通过；没有改生产代码或测试断言来绕过。

生产控制器/聚合规则的事件模拟：200条完整完成，44秒为虚拟时间、峰值112；200000条三种模型容量100/500/2500只运行1200模拟秒，稳定成功速率分别6.733/34.277/170.227，相对于同工作负载Oracle的7.692/38.462/192.308约87.5%/89.1%/88.5%。大模拟不是20万条全部完成，不是DeepSeek实测，不保证服务器具体提速倍数；准确率机制保持不等于Gold Set量化准确率已验收。

本轮命令还包括`ruff check`、`ruff format --check`（修复5文件对应4个Python）、`mypy backend/src`（430source files）、`scripts/contracts/generate.py --check`、`scripts/contracts/check_compatibility.py`、`check_docs.py`、`check_docs_facts.py`、`check_architecture.py`、`check_table_ownership.py`、`scan_secrets.py`和`git diff --check`，均exit0。Linux、独立关闭复核和最终精确资源清理结果在本节后补记及CAPACITY_PROBE_EVIDENCE.json保存。没有新的API字段、业务Schema、依赖或Migration head；recovery.v2的成功状态更严格，历史冻结语义保持。回退到旧控制代码前排空新协议Run/预留并重建派生Profile，保留业务结果。

隔离环境首次失败及更正完整保存在CAPACITY_PROBE_EVIDENCE.json：Windows临时目录权限和夹具位置、Linux测试上下文空间不足及缺测试环境资产、非root缓存路径均按本次独占环境修正；失败不宣称通过，没有升级生产依赖或降低断言。未重启用户API/Worker，未连接或迁移用户业务库，未调用收费模型或TikHub。没有commit/push/PR/remote CI/merge/main-fresh/Archive/Issue Closure/部署。

Linux最终epoch8：`docker run --name aima-analysis-probe-linux-epoch8-20261001 --label owner=analysis-probe-20261001 --network aima-analysis-probe-net-20261001 --cpus 3 --memory 3g --mount <本次上下文只读到/source> aima-analysis-probe-validation:20261001 python /source/linux-final.py`。脚本通过根工程`uv build --wheel`和`uv pip install --no-deps --reinstall-package aima-ugc`重新安装当前正式wheel，实际导入site-packages；非root10001:10001、Python3.14.7。`tests/unit/analysis`、Stage12 Planner与上述四PG组 **358passed / 132.54秒 / exit0**，控制器哈希与epoch8完全相同。测试缓存位于独占/app/probe，仅有缓存目录位于构建源内的提示，未更改package discovery或通过PYTHONPATH替代安装。

本次资源已精确清理：逐一检查owner=analysis-probe-20261001后移除五个准确容器ID；仅删除专属镜像sha256:de7747e168d9c8415424db47c61912259235272fd0b90da0b38a4b19049295f3和同owner网络。PG独占匿名卷30d039476ae1e392a3757fa9baa3331d70acbd5b7b2e629c138febfdbf0bc938随本次容器回收，准确卷名查询为空；task容器/镜像/network过滤结果均为空，55493–55496均无监听，没有global prune。

scratch-analysis-probe-20261001清理前核对固定绝对路径与ownership.json；九个仓库外临时目录按实际执行命令中的完整名字逐一核对。先核验三个测试junction均指向各自本次夹具内部，只删除链接并确认目标仍存在，再检查无ReparsePoint，以原生PowerShell Remove-Item -LiteralPath递归删除这十个明确目标。所有删除后Test-Path为false，原.venv解释器与frontend/node_modules仍存在。JSON保存当前结果、原始失败和清理事实；隔离临时runner不作为产品代码保留。

最终独立epoch8集中REPAIR_DIFF为 **PASS / NO_FINDINGS_WITHIN_SCOPE**，CAPACITY-V3-REV-001两个投影均CLOSED；没有新的范围内阻塞或UNCHANGED_BASELINE BLOCKING sibling。原CHANGES_REQUIRED与历史漏检事实保持。完成审计重新读取用户最新规则与AC1–AC20，R1–R21全部satisfied，当前Change为ready_for_review。`.venv/Scripts/python.exe -B scripts/quality/check_change_completion.py --root . --require-active-ready` **exit0 / gated152 / strict152 / legacy128**，只表示本地门禁，不代表远程CI。

收尾再次读取并逐字节核验38项冻结文件、aggregate、用户Prompt、当前JSON结果与清理状态；本地branch/HEAD与冻结身份一致，无暂存/无冲突。冻结清单中的35个Python文件`ruff check --no-cache`、`ruff format --check --no-cache`全部通过；当前Docs/Facts/Secret和git diff --check通过。审查后没有生产代码、测试或冻结文档变化，仅收口本Change Evidence/完成与审查资产。

## 2026-10-02 受保护Git交付准备

当前用户授权将全部现有本地修改经受保护PR集成main，然后清理已合并本地任务分支；之后另建Codex会话依次处理#591/#662。原epoch8“仅本地”状态保留为历史，不代表当前授权。正式Requirement Source采用Blueprint35/36节与AC1–AC20，未建立新的Issue。

实际逐字节核验epoch8清单：37项原字节一致，唯一变化为Blueprint AC10更新当前Git授权；生产代码和测试不变。用户Prompt仍为原SHA256 `9e0489a330dd1a5bffcdea90703310e37eb1abf4cdf7aa53224a44864e261741`，明确纳入全部本地修改。当前39项实现/文档/Prompt身份见[changes/active/CHG-20261001-112055-analysis-capacity-feedback/DELIVERY_BASELINE.json](DELIVERY_BASELINE.json)。旧冻结清单不改写。

实际运行本轮刚读取的canonical `governance_contract.py validate-change --path changes/active/CHG-20261001-112055-analysis-capacity-feedback/CHANGE.md`，exit0；canonical `prepare-pr`及`validate-pr --mode create --json`输出ok=true，平台live仍需写后重验。项目命令`.venv/Scripts/python.exe -B scripts/quality/check_change_completion.py --root . --require-active-ready` exit0（gated152/strict152/legacy128）；同解释器执行`check_docs.py`、`check_docs_facts.py`、`scan_secrets.py`均exit0。`git diff --check` exit0，仅已有LF/CRLF提示。

在子进程清除AIMA/数据库/PYTHONPATH/SSL调试环境后，使用原解释器运行`-B -m pytest tests/unit/analysis/test_markdown_prompt_source.py tests/unit/analysis/test_analysis_scheme_compilation.py -q -p no:cacheprovider --basetemp=<本任务独占目录>`，26passed/9条既有Pydantic弃用警告，0.22秒，exit0。纯内存生产Compiler/版本与合法输出链验证没有数据库或收费HTTP调用，没有修改用户Prompt。不能将Compiler成功冒充Gold Set语义准确率。

已读取实际main Ruleset：三个required check为CI Gate、Requirement Traceability and Completion Audit、Compose Golden Path，strict最新base与Review线程解决生效；当前账号为授权更新main的用户，不修改Ruleset或绕过质量保护。正式current-head CI、独立交付delta Review、guarded merge、main-fresh、原生Archive与cleanup此时尚未完成，后续分别核验。

### 首个远程Head的平台类型问题与单个修复包

正式PR #689首个Head为`12f9c3ec7f378ad814179ae7aa271bb16b872b49`，base为`64bfade138e6cdf0f86e8d8961a0415b8f994ea8`。CI run `36900807907`的质量Job在Linux mypy报告`platform/capacity.py:69 Module has no attribute windll [attr-defined]`；Ruff888文件与Contract此前通过。该run全量PostgreSQL Job及Real Full-stack Job（16passed）成功；Runtime Acceptance run `36900807439`成功；Developer Tooling run `36900807343`的Windows/Linux均成功。整体CI Gate失败，不能以其他绿层或旧本地mypy代替。PR退回Draft，继续同一个修复包。

本地Red：`.venv/Scripts/python.exe -m mypy --platform linux backend/src/aima_ugc/platform/capacity.py`实际1error/1source，exit1。原因是Windows专属ctypes属性以直接静态引用出现于跨平台源码，Linux类型定义不提供该属性。复用本文件内存探测已有的`getattr(ctypes, "windll", None)`能力读取；Windows系统计数API失败或缺失仍返回None，Linux仍读取/proc/stat，业务资源算法不变，没有ignore或关闭门禁。

Green：同解释器`-m mypy --platform linux backend/src`和`-m mypy --platform win32 backend/src`各430source，均exit0；该capacity文件`ruff check --no-cache`和`ruff format --check --no-cache`均exit0。第一次patch混合LF/CRLF的format-check失败保留，仅对该文件运行正式formatter后通过。第一次机器回归的Windows沙箱独占临时目录有4个setup Error和退出PermissionError；未改测试断言，改用本任务独占外部临时目录、清除AIMA/数据库/SSL/PYTHONPATH环境，原`tests/unit/analysis/test_machine_adaptation.py tests/unit/analysis/test_capacity_workloads.py -q -p no:cacheprovider`得到23passed/77条既有Pydantic弃用警告、7.04秒、exit0。该回归纯内存，不启动数据库或HTTP服务。

另直接调用生产CPU采样器验证：Windows真实ctypes参数经Fake系统计数输出(total300,idle120)、API返回0、API缺失均得到预期结果；本机实际采样为合法总/空闲计数或未知。四个直接边界PASS，exit0。临时探针不复制采样算法、不进入永久产品代码。新的DELIVERY_BASELINE嵌套首个交付baseline，保留修复前身份；当前代码修复与正式新Head CI/Review状态后续另取，不能将旧Head绿层冒充新Head完整通过。

### 归档导航修复与最终位置验证

独立首次集中审查返回DELIVERY-REV-001：原生归档只移动CHANGE.md，7个本地导航在active有效而在archive最终位置全部失效。修复只将当前Change的这7个目标改为已发布implementation checkpoint `69c39716b057a8171dba0041b596a877f250a9af` 的不可变Git permalink，显示完整仓库路径；添加快照时点说明与PR #689最终状态入口。该checkpoint包含CPU修复、实际Green、原平台失败和首次审查，不声称含尚未发生的最终CI/merge。没有改Archiver、移动附件、改产品算法或引入新的长期事实Owner。

实际逐个`git cat-file -e <checkpoint>:<目标路径>`验证全部7个blob；分别按active与原生archive/2026-10最终位置解析，7个不可变文件目标及PR导航均有效。远程`gh api .../commits/69c39716...`确认同SHA/tree已发布，任务分支删除不影响这些链接。本轮canonical validate-change exit0、项目Ready exit0（gated152/strict152/legacy128）、git diff --check exit0。此时导航已修复，Finding仍须独立REPAIR_VERIFY关闭；正式新Head/current-base CI、受保护merge、main-fresh与Archive尚未完成。
