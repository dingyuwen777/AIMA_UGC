---
schema: rvc-change/v1
id: CHG-20260821-diagnostic-logging
title: 诊断友好的运行日志格式与关键事件优化
level: L2
status: done
owner: dingyuwen777
branch: fix/diagnostic-logging
created: 2026-08-21
updated: 2026-08-22
depends_on: []
affected_areas:
  - logging
  - api
  - scheduler
  - worker
  - collection
  - provider_dispatch
affected_paths:
  - backend/src/aima_ugc/platform/logging
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/bootstrap/runtime.py
  - backend/src/aima_ugc/bootstrap/scheduler.py
  - backend/src/aima_ugc/entrypoints/scheduler_main.py
  - backend/src/aima_ugc/platform/jobs/worker.py
  - backend/src/aima_ugc/modules/collection/collection_run_executor.py
  - backend/src/aima_ugc/modules/collection/provider_dispatch.py
  - tests
  - docs/blueprint/05-日志安全部署与运维.md
  - docs/appendix/Scheduler调度执行与停机恢复.md
contracts: []
data_changes: []
---

# 归档说明

本 Change 的运行时代码已通过 PR #113 合并到 `main`，合并提交：

```text
a86b80a4d9c3246b9dcb3f5a688497c82565d084
```

原 Active Change 长期停留在 `ready_for_review`，属于文档状态遗漏，不代表代码仍未合并。2026-08-22 当前实现一致性审计按真实 Git 状态归档。

本 Change 实施时曾更新旧路径：

```text
docs/blueprint/09-Scheduler运行与恢复策略.md
```

后续文档治理已删除旧 Blueprint 09，并把当前有效 Scheduler 技术内容迁移到：

```text
docs/appendix/Scheduler调度执行与停机恢复.md
```

日志长期边界继续由：

```text
docs/blueprint/05-日志安全部署与运维.md
```

维护。旧路径只属于历史实施事实，不再是当前导航。

# 目标

让 api、scheduler、worker 的文件日志优先服务于故障定位：每行开头直接显示北京时间毫秒时间、真实调用文件名和源码行号、日志级别；去掉由日志文件名即可判断的 `service=` 重复字段；减少周期性空轮询和成功细节噪音，并补齐真正影响定位的 API、Scheduler、Job、Collection 与 Provider 失败信息。

目标行格式：

```text
[2026-08-21 16:48:14.113 provider_dispatch.py L184] [WARNING] event=provider.request.failed duration_ms=183 error_code=tikhub_connect_failed message="Provider Request 状态已持久化。"
```

# 成功标准

- [x] 所有 AIMA Formatter 输出使用 Asia/Shanghai（北京时间）与 `YYYY-MM-DD HH:mm:ss.SSS` 格式。
- [x] 第一段前缀同时包含 `filename` 与 `L<lineno>`，第二段为 `[LEVEL]`。
- [x] `log_event()` / `log_exception_event()` 的 caller 跳过统一 helper，定位到实际调用代码。
- [x] 每行不再输出 `service=api|scheduler|worker`；进程类型继续只由 `api.log / scheduler.log / worker.log` 文件名区分。
- [x] `event=`、request/job/run/scope/provider、状态、计数、耗时等诊断字段继续保持结构化且脱敏。
- [x] Scheduler 空 tick 不再每 30 秒产生 INFO；发生初始化、入队或跳过时 INFO，存在失败时 WARNING，并保留汇总计数与耗时。
- [x] Worker 的 Job 起止日志包含 `duration_ms`；成功/取消 INFO，可重试 WARNING，永久失败 ERROR；Handler/Heartbeat 未预期异常保留安全调用栈。
- [x] Collection 成功 Scope 降为 DEBUG；partial/failed/retry 提升到相应 WARNING/ERROR，并携带稳定关联 ID、计数和安全调用栈。
- [x] Provider Dispatch 作为外部请求唯一主要日志边界：开始/成功 DEBUG，失败 WARNING，保留 request/attempt/run/scope/provider/platform/operation/status/duration/error 等安全诊断字段，不记录 Authorization、credential、完整 query/body/raw payload。
- [x] API 未预期 500 使用安全调用栈日志并保留 request_id/method/path/error_type；正常 API/health 不增加逐请求 INFO 噪音。
- [x] 原始异常 message/source line 不进入 LogRecord；安全调用栈只保留文件名、行号、函数和异常类型，避免 Secret 经其他 Handler 泄露。
- [x] 既有日志脱敏、换行转义、轮转 gzip、大小限制继续通过。
- [x] 当时的长期文档已同步；当前 Scheduler 细节由 Appendix 承载，北京时间人工展示统一为 `YYYY-MM-DD HH:mm:ss.SSS`，机器交换时间仍保留时区信息。

# 日志分层规则

## INFO：低频、能回答“系统做了什么”

- 进程启动/停止；
- Job 开始与成功/取消终态；
- Collection Run 开始与成功/取消终态；
- Scheduler 真正初始化、入队或产生 skip 后的 tick 汇总；
- 重要异步任务的稳定业务结果。

## WARNING / ERROR：能回答“为什么失败/为什么变慢”

- Provider 请求失败；
- Job retry、永久失败、Heartbeat/Lease 异常；
- Collection Scope partial/failed/retry 与 Run partial/failed；
- Scheduler rejected Plan 与失败 tick；
- API 未预期 500；
- 进程资源释放失败。

## DEBUG：正常情况下不需要看的轮询/成功细节

- Scheduler 空 tick；
- Provider request started / completed；
- Collection Scope succeeded；
- 未来需要请求级性能跟踪时的正常细节。

# 禁止内容

- Secret、Authorization、Cookie、Token、API Key；
- Provider Raw body、完整 request body、完整 query 参数；
- 用户原始正文/评论正文；
- SQL 全文和数据库密码；
- 每条记录/每个 heartbeat 的正常 INFO；
- 仅重复文件上下文的 `service=` / `source=` 字段；
- 未脱敏的异常原始 message 和 traceback 源代码行。

# TDD / 验证

## Red

CI run `32472487022` 的 Stage 2 Platform 在仅加入目标测试时实际得到：

```text
7 failed, 77 passed
```

失败与目标一一对应：旧前缀缺文件/行号、caller 指向 logging helper、仍输出 `service=`、Scheduler 空 tick 仍为 INFO、缺 `failed` 字段且失败 tick 未提升 WARNING。

## Green / 回归

生产实现完成后又发现两类质量问题并按门禁修正：

- Provider `duration_ms` 测试不再写死 fixture 不保证的 250ms，只约束为真实非负整数；
- 未预期异常初版使用 raw `exc_info`，CI 的 Secret 测试证明异常消息可在 Formatter 前被其他 Handler 看到，因此改为 `log_exception_event()` 安全调用栈，不降低 Secret 门禁。

代码 head `d21643eaa599f59b7deb194d684a0e0978edb4e6` 的新鲜 PR CI：

- CI run `32474371709`：success；Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全部通过；
- Stage 1–7 Audit Correctness `32474371778`：success；
- Stage 4 Job Runtime `32474371780`：success；
- Stage 5A Provider Raw `32474371732`：success；
- Stage 5B Collection Execution `32474372059`：success；
- Stage 5C Provider Persistence `32474371770`：success；
- Stage 5D Provider Dispatch `32474371847`：success；
- Stage 6 XHS Vertical Slice `32474371788`：success；
- Stage 7 Keyword Packs `32474371797`：success；
- Stage 7 Plan Occurrence Run Snapshot `32474371692`：success；
- Stage 7 Provider Config Routing `32474371886`：success；
- Stage 7 Scheduler Runtime `32474371795`：success。

本次没有新增依赖、Contract、Migration、数据库字段、API 响应或业务统计语义变化。

# Git / PR

- 分支：`fix/diagnostic-logging`
- PR：#113 `优化运行日志诊断信息与降噪`
- PR 最终状态：已合并。
- Merge commit：`a86b80a4d9c3246b9dcb3f5a688497c82565d084`。
- 当前长期文档：`docs/blueprint/05-日志安全部署与运维.md` + `docs/appendix/Scheduler调度执行与停机恢复.md`。
