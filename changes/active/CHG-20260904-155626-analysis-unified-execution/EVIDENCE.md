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
