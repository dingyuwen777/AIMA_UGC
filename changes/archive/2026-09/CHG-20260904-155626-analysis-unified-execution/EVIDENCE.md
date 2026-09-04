# AI 统一执行与刷新验收记录

日期：2026-09-04。需求为 [Issue #344](https://github.com/dingyuwen777/AIMA_UGC/issues/344)，实现为 [PR #345](https://github.com/dingyuwen777/AIMA_UGC/pull/345)。本文归集同一任务此前本地测试和本轮提交前检查，不将本地目标测试冒充完整 CI。

## 已执行的本地验证

| 层 | 实际验证与结果 |
| --- | --- |
| 后端相关回归 | 本次统一执行修改累计验证 211 项后端相关用例，覆盖首批并发、跨页、配置身份、停止/重试、离线 checkpoint、内容版本与人工复核。首次本地 HTTP 检查暴露系统代理对本机地址干扰，隔离测试代理环境后重跑通过；未修改生产请求安全边界。 |
| 最新前端目标单测 | `npm --prefix frontend run test -- --run tests/task-center.spec.ts tests/voice-plaza.spec.ts`：26 项通过。覆盖同一在途请求、慢其他来源、每秒活动查询、创建/取消旧响应、静止进度不查内容、终态补读及失败重试。 |
| 最新 PostgreSQL 集成 | `pytest tests/integration/content/test_analysis_provider_concurrency.py -q`：14 项通过。使用独立 PostgreSQL、实际本地 HTTP 和正式 Worker，覆盖并发、提前可读、401 停止、取消、Lease/Deadline、接管、过期页与活动历史保留。 |
| Browser Mock | 声音广场及任务中心相关 9 项通过（8 项首轮通过，1 项消除“任务中心”按钮定位歧义后重跑通过）。未降低时间/状态断言。 |
| Real Full-stack | `analysis-streaming.spec.ts` 最新运行 1 项通过，用时 6.6 秒。真实 API/Worker/PostgreSQL、本地假 LLM；通过到达屏障证明首批实际并发，数据库完成后 2.5 秒内自动看到两份合法标签，没有人工刷新。 |
| 前端构建 | `npm --prefix frontend run build` 和目标 ESLint 通过；TypeScript/Vue 类型检查、Vite 构建完成。 |
| Python 静态检查 | 最终工作树 `ruff check backend tests scripts` 通过，`mypy backend/src`：294 个源文件无错误；`ruff format --check backend tests scripts`：597 个文件通过。格式检查发现三个本次修改文件的混合换行，仅统一这些文件的换行后通过，Git 内容无新增差异。 |
| CI 场景选择 | 新增两项回归首先失败，证明新全栈测试没有进入 AI 持久化定向选择；补齐正式测试清单和 Analysis 路径关联后，`pytest tests/unit/test_ci_scope.py -q`：19 项通过。Windows 沙箱阻止 pytest 临时目录访问，使用相同仓库环境取得正常测试权限后通过。 |
| 文档与差异 | `python scripts/quality/check_docs.py`、`git diff --check` 通过；Change Ready 检查在最终文档提交前运行。 |

## 可复现的行为判据

- 两条模型请求必须在受控 HTTP 屏障同时到达；串行执行不能通过。这证明物理调用并发，不只统计线程 Future 数量。
- 一条请求完成，另一条仍阻塞时，先完成的合法结果必须在 750 ms 验收窗口内由数据库/API 可读。旧一秒计时提交实现已被失败回归识别。
- 旧前端 5/15 秒轮询和重复读取被新增测试识别；最新实现每秒共享活动查询，不变统计不刷新内容，终态仍完成最后一次读取。
- 同一最新两条受控运行测得创建到完成 512.5 ms，物理 HTTP 峰值为 2、重试为 0；模型返回到结果插入时间戳约 13.2–13.8 ms。该数字只描述此次本地受控环境，不是承诺生产延迟上限。
- 正式取消禁止后续补充和重试，已经提交的结果保留；已发送同步 HTTP 收尾期间不能承诺即时断网或零计费。执行身份丢失不允许旧 Worker 写可见结果。
- 离线测试禁止创建数据库后仍从 imports_test 使用生产打标/Excel 导出，并验证 Ctrl+C checkpoint 恢复。没有复制一套调试业务实现。

## 两阶段 Review

审查基线为 `9b11d560c7e82344b87f4cfa77a2afb30456c808`，范围为 PR #345 的本次后端、前端、验收和文档差异。由本任务切换审查视角复核，没有声称另有独立人员或 Agent 签字。

第一阶段从用户决定、Issue #344、AGENTS 和 Analysis 正式说明重新建立 R1–R8，确认没有遗漏无数据库离线、启动取消、旧冻结身份、API 列表成本和最终可见结果；不以当前 Change 的勾选作为唯一需求来源。

第二阶段反查真实代码与验证：Worker registry → 并发核心 → 物理 HTTP → 事务/Fence → Run 统计 → 共享前端 Store → 终态内容刷新；另查 imports_test → 生产离线核心 → checkpoint/导出。核对错误和停止信号不会进入模型 Payload，模型线程不写数据库，旧执行分支/配置无生产残留，Prompt/Validator/锁文件/Migration/公共 Contract 无差异。

发现的验收遗漏是新 `analysis-streaming.spec.ts` 未加入 CI 定向场景清单。本轮以 Red → Green 修复并复核；未通过删除/跳过测试或降低时间/并发断言处理失败。当前在上述范围内无未解决阻断或高风险发现。完整 PR CI、主分支检查和归档是后续时序门禁，不能由本审查提前判定成功。

## 证据与运行边界

此前人工运行日志说明请求确实重叠，模型 HTTP 总时长包含服务排队、传输与推理，不能全部叫“思考时间”。新实现不调整 Prompt、模型参数或 Validator；保证的是既有规则与验证链继续执行，未进行新的真实模型质量对照或付费并发容量实验。

所有本地集成和全栈使用本任务独立容器/进程，已经核对身份并清理；用户开发库与运行服务未被替换。原始详细日志保存在忽略的本地任务目录，不提交 Secret、业务内容或环境配置。

## 交付门禁

最终候选 SHA 的 CI、Requirement Traceability and Completion Audit、Compose Golden Path 和其他触发的质量检查均成功后，方可按主分支规则合并。之后验证 implementation main；再归档 Change 并验证 archive main，回写 Issue 验收证据后关闭并清理本任务已合并分支。远程结果在实际发生后追加，当前不预填成功。

## 首轮远程 CI 反馈与修正

候选 `ce2f844baeadf3b14fb304d4de0b33ab80c7ffa5` 的 [CI run 33851750335](https://github.com/dingyuwen777/AIMA_UGC/actions/runs/33851750335) 暴露两项本地目标检查未识别的问题：

1. Analysis README 链接到了 Git 忽略的 `env.local`，本机有该文件而干净 CI checkout 没有。改为说明本地文件并链接已跟踪的 `env.local.example`；不提交运行 Secret。
2. Deadline 场景测试构造用三个 `clock_timestamp()` 调用；CI 中租约比截止时间晚 1 微秒，被 `lease_expires_at <= attempt_deadline_at` 约束正确拒绝。测试统一用 `statement_timestamp()` 建立同一语句时刻，仍模拟过期 Deadline 并保留“不重试、不越权写入”断言；不修改生产代码或数据库约束。[PostgreSQL 18 官方时间函数说明](https://www.postgresql.org/docs/18/functions-datetime.html#FUNCTIONS-DATETIME-CURRENT) 明确区分这两种时间语义。

修正后在新建的独立 PostgreSQL 容器重跑同一模块：14 项通过，用时 16.61 秒。首轮远程真实全栈与 Compose Golden Path 已通过，但仍须由包含修正的最新提交取得完整 CI，不能复用旧 SHA 的成功状态替代。

## 最终候选与实现主分支检查

最终候选 `47dbc0ca4ac002726ba894733f070cea9eca7553` 的 [CI run 33852345558](https://github.com/dingyuwen777/AIMA_UGC/actions/runs/33852345558) 已成功。其第一次 npm 审计遇到官方 endpoint HTTP 503，第二次遇到网络 timeout；第三次对同一 SHA 重跑，生产及全依赖审计均为零已知漏洞，随后所有质量门禁通过。未关闭审计、改变依赖或降低测试要求。

已读取该 run 的实际日志：Python 单元 807、Contract 104、API 53，共 964 项通过；前端单元 107 项、Browser Mock 60 项通过；PostgreSQL 各层共 214 项 pytest 通过；真实全栈 11 项通过（58.5 秒，AI streaming 场景 2.2 秒）。静态检查、Contract/Client 无漂移、Wheel 安装、前端构建和启动检查均通过。

同一候选的 [Runtime Acceptance](https://github.com/dingyuwen777/AIMA_UGC/actions/runs/33852345288)、[Linux/Windows Tooling](https://github.com/dingyuwen777/AIMA_UGC/actions/runs/33852345280)、[Release dry-run](https://github.com/dingyuwen777/AIMA_UGC/actions/runs/33852345408) 和 [需求完成检查](https://github.com/dingyuwen777/AIMA_UGC/actions/runs/33852451473) 全部成功。Release 仅构建并实际回放离线包，正式发布按 PR 模式跳过。

PR #345 于北京时间 2026-09-04 16:50:53 合并，实际 merge SHA 为 `42ab2c9e538187c29bd7a6987b0a7801e22302e7`。合并前重新核对 head、base、全部检查和实际仓库规则；使用 expected head 约束普通 PR merge。没有修改保护规则、使用管理员 merge 参数或强制推送。合并后本地 fast-forward 至 main，`git diff --quiet 47dbc0ca HEAD` 证明文件树与最终候选一致。

以下工作流均针对上述实际合并 SHA 的 main push，全部 success：

| 主分支检查 | 实际结果 |
| --- | --- |
| [CI 33855410461](https://github.com/dingyuwen777/AIMA_UGC/actions/runs/33855410461) | Repository Quality、PostgreSQL Integration、Docs and Governance、Real Full-stack、CI Gate 全部成功。 |
| [Runtime Acceptance 33855410237](https://github.com/dingyuwen777/AIMA_UGC/actions/runs/33855410237) | Compose Golden Path，包括启动、安全、持久化、恢复及 Windows overlay 场景成功。 |
| [Change Completion 33855410163](https://github.com/dingyuwen777/AIMA_UGC/actions/runs/33855410163) | 需求追溯与完成审计成功。 |
| [Developer Tooling 33855410156](https://github.com/dingyuwen777/AIMA_UGC/actions/runs/33855410156) | Linux 和 Windows 工具检查均成功。 |

## 本地 Windows 全量补跑的限制

本地完整 Python 补跑得到 947 passed、8 skipped、9 failed（49.16 秒）。失败的原有工具源码与测试对 main 无差异：6 项文档测试使用固定 `/` 断言，而 Windows 实际错误路径为 `docs\\guide.md`；3 项 Linux 权限测试直接替换 Windows 不存在的 `os.geteuid` / `os.chown`。将文档测试移到仓库外系统临时目录重跑仍有相同 6 项失败，并直接检查返回文本确认分隔符差异。未修改这些无关用例，未把本地全量称为全绿。上述最终候选和实现 main 的 Linux 完整 CI 均已通过；平台工具兼容检查也单独通过。

## 归档交接

在实现 main 四项检查全部成功后，才把当前 Change 改为 done 并移入同 ID archive。当前归档仅更新这两份记录。归档 PR 仍按实际文档范围运行 CI，合并后再取得 archive main 新鲜结果，随后更新并关闭 Issue #344、清理当前任务分支。最终收尾状态由 Issue #344 的实际回写记录承载，本文不预填尚未产生的归档 merge SHA 或检查结果。
