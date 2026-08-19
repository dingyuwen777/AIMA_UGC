---
schema: rvc-change/v1
id: "CHG-20260818-beijing-visible-timestamps"
title: "统一人工可见时间为北京时间"
level: L2
status: done
owner: "dingyuwen777"
branch: "main"
created: 2026-08-18
updated: 2026-08-19
depends_on: []
affected_areas:
  - "observability"
affected_paths:
  - "backend/src/aima_ugc/adapters/providers/tikhub_test/core/core.py"
  - "backend/src/aima_ugc/adapters/providers/tikhub_test/README.md"
  - "backend/src/aima_ugc/platform/logging"
  - "tests/unit/collection/test_tikhub_test_debug_runtime.py"
  - "tests/unit/platform/test_logging.py"
contracts: []
data_changes: []
---

# 目标

统一人工直接查看的时间为北京时间，同时保持机器事实和公共 Contract 的 UTC 边界：

- TikHub 独立调试自动 `run_id` 使用 `Asia/Shanghai`，目录名显式携带 `+0800`；
- 应用日志行首使用北京时间毫秒；
- 数据库、API、Canonical、Job、Scheduler 和审计内部时间继续使用 UTC / `timestamptz`。

# 最终结果

- [x] 固定 UTC 时刻 `2026-08-18T06:10:08.637851Z` 的默认调试 `run_id` 为 `20260818T141008.637851+0800`；
- [x] 显式 `run_id` 行为保持兼容，历史目录不迁移；
- [x] 固定 UTC 时刻 `2026-08-18T06:10:08.637Z` 的日志行首为 `[2026-08-18 14:10:08.637]`；
- [x] Raw/Excel 人工可见时间继续按 `Asia/Shanghai`，机器事实 UTC 边界未改变；
- [x] README 已说明默认运行目录为北京时间并显式带 `+0800`。

# 当前机器事实

`backend/src/aima_ugc/adapters/providers/tikhub_test/core/core.py`：

```text
_BEIJING_TZ = ZoneInfo("Asia/Shanghai")
default_run_id() -> actual.astimezone(_BEIJING_TZ).strftime("%Y%m%dT%H%M%S.%f%z")
```

`tests/unit/collection/test_tikhub_test_debug_runtime.py` 固定时刻断言 `20260818T141008.637851+0800`；`tests/unit/platform/test_logging.py` 固定时刻断言 `[2026-08-18 14:10:08.637] [INFO]`。

# 关键决策

- 人工可见时间使用北京时间，机器事实与公共 Contract 保持 UTC；
- 目录偏移使用无歧义 `+0800`，不使用 `CST`；
- 不修改数据库、Migration、API、OpenAPI、Canonical、Job Payload 或 Scheduler 时间语义；
- 不重命名历史调试目录，不新增依赖。

# 验证与完成依据

原 Active Change 在实现发生时没有把独立 Red 命令写入文档，因此归档时不补造不存在的 Red 运行记录。完成判断基于当前机器事实、固定时刻回归测试和新鲜整仓集成验证。

PR #73 合并后的 main 文件树通过 PR #74 的 post-merge 验证候选 `ab29f4783972e72d105460971d21bd6ffdc39c28` 重新触发全部正式 Stage workflow并取得 **12/12 success**：CI、Stage1–7 Audit、Stage4、Stage5A/5B/5C/5D、Stage6、Stage7 Keyword/Plan/Provider/Scheduler 均成功。

其中总 CI Run `32209959634` 的 Stage1、Stage2 Platform、Stage3A Database、Windows bootstrap 全部 success；Stage5A 覆盖 TikHub 调试回归，Stage2/全局质量门禁覆盖 logging 行为。

# 两阶段复核

## 需求符合性

- TikHub 默认运行目录时间和应用日志均满足北京时间要求；
- 显式 `run_id`、输出目录层级和历史文件不受影响；
- UTC 数据/Contract/调度语义保持不变。

## 代码质量

- 时区转换集中在既有时间入口，没有建立第二套时间模型；
- `ZoneInfo("Asia/Shanghai")` 与固定时刻测试共同锁定语义；
- 无 Schema、Migration、依赖或公共 API 变化。

# 交付

- 实现早已集成于 `main`；
- 本次只修正 Change 生命周期，不修改业务代码；
- post-merge 12/12 正式 workflow 已成功；
- `status: done`，归档于 `changes/archive/2026-08/`。
