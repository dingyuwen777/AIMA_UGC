---
schema: rvc-change/v1
id: CHG-20260821-diagnostic-logging
title: 诊断友好的运行日志格式与关键事件优化
level: L2
status: in_progress
owner: dingyuwen777
branch: fix/diagnostic-logging
created: 2026-08-21
updated: 2026-08-21
depends_on: []
affected_areas:
  - logging
  - scheduler
  - worker
  - collection
  - provider_transport
affected_paths:
  - backend/src/aima_ugc/platform/logging
  - backend/src/aima_ugc/entrypoints/scheduler_main.py
  - backend/src/aima_ugc/platform/jobs/worker.py
  - backend/src/aima_ugc/modules/collection/collection_run_executor.py
  - backend/src/aima_ugc/adapters/providers/tikhub/transport.py
  - tests
  - docs/blueprint/05-日志安全部署与运维.md
contracts: []
data_changes: []
---

# 目标

让 app/api、scheduler、worker 的文件日志优先服务于故障定位：每行开头直接显示北京时间毫秒时间、真实调用文件名和源码行号、日志级别；去掉由日志文件名即可判断的 `service=` 重复字段；减少周期性空轮询噪音，并补齐真正影响定位的外部 Provider、Job、Collection 异常信息。

目标行格式：

```text
[2026-08-21 16:48:14.113 _client.py L1090] [INFO] event=http.request.completed status_code=200 duration_ms=183 message="..."
```

# 成功标准

- [ ] 所有 AIMA Formatter 输出使用 Asia/Shanghai（北京时间）与 `YYYY-MM-DD HH:mm:ss.SSS` 格式。
- [ ] 第一段前缀同时包含 `filename` 与 `L<lineno>`，第二段为 `[LEVEL]`。
- [ ] `log_event()` 记录的 caller 跳过统一 helper，定位到实际调用代码。
- [ ] 每行不再输出 `service=api|scheduler|worker`；进程类型继续只由 `api.log / scheduler.log / worker.log` 文件名区分。
- [ ] `event=`、request/job/run/batch/scope/provider、状态、计数、耗时等诊断字段继续保持结构化且脱敏。
- [ ] Scheduler 空 tick 不再每 30 秒产生 INFO；发生初始化、入队、跳过或失败时仍保留一条汇总 INFO。
- [ ] Worker 的 Job 起止日志补充可用于性能定位的 `duration_ms`，失败/重试终态仍保留 `error_code`。
- [ ] Collection 未预期 Scope 异常保留 traceback，并携带 run/job/scope/platform/operation_group；retry checkpoint 有可追踪事件。
- [ ] TikHub Transport 的网络/协议失败记录安全诊断字段（method/path/error_code/duration_ms），不记录 Authorization、credential、query/body/raw payload。
- [ ] API 未预期 500 使用 traceback 日志并保留 request_id/method/path/error_type。
- [ ] 既有日志脱敏、换行转义、轮转 gzip、大小限制继续通过。
- [ ] Blueprint 05 与代码最终行为一致。

# 日志分层规则

## INFO：低频、能回答“系统做了什么”

- 进程启动/停止；
- Job 开始与终态；
- Collection Run 开始与终态；
- Collection Scope 终态；
- Scheduler 真正初始化/入队/跳过/失败后的 tick 汇总；
- 重要异步任务的稳定业务结果。

## WARNING / ERROR：能回答“为什么失败/为什么变慢”

- Provider 网络连接、读写、协议失败；
- Job heartbeat / lease 异常；
- Collection Scope 未预期异常与 retry checkpoint；
- API 未预期 500；
- 资源释放失败。

## DEBUG：正常情况下不需要看的轮询/细节

- Scheduler 空 tick；
- 未来如需 Provider 成功请求级跟踪，只放 DEBUG，不在默认 INFO 打每次 HTTP 请求。

# 禁止内容

- Secret、Authorization、Cookie、Token、API Key；
- Provider Raw body、完整 request body、完整 query 参数；
- 用户原始正文/评论正文；
- SQL 全文和数据库密码；
- 每条记录/每个 heartbeat 的正常 INFO；
- 仅重复文件上下文的 `service=` 字段。

# TDD / 验证

1. 先修改/新增测试，使当前实现因为旧前缀、`service=`、caller、空 tick INFO 等原因 Red。
2. 再做最小实现和异常路径补强。
3. 执行目标测试、相关 Collection/Job/API/Provider 回归、Ruff、Mypy 和仓库现有 CI。
4. 通过 PR 合并到 main，不绕过现有门禁。
