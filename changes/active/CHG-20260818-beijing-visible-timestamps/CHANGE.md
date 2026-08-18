---
schema: rvc-change/v1
id: "CHG-20260818-beijing-visible-timestamps"
title: "统一人工可见时间为北京时间"
level: L2
status: in_progress
owner: "dingyuwen777"
branch: "main"
created: 2026-08-18
updated: 2026-08-18
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

统一人工直接查看的时间为北京时间：TikHub 独立调试的自动运行目录使用
`Asia/Shanghai` 并在目录名中显式携带 `+0800`；应用日志行首继续输出北京时间毫秒，
并由固定时刻测试证明时区语义，而不是仅检查文本形状。

# 成功标准

- [ ] 固定 UTC 时刻 `2026-08-18T06:10:08.637851Z` 生成的默认调试运行目录名为
      `20260818T141008.637851+0800`，不再使用误导性的 UTC `Z` 后缀。
- [ ] 显式传入的自定义 `run_id` 保持原有行为；历史运行目录不重命名、不删除。
- [ ] 应用日志固定 UTC 时刻 `2026-08-18T06:10:08.637Z` 的行首为
      `[2026-08-18 14:10:08.637]`。
- [ ] Raw Artifact 日期目录和 TikHub 调试 Excel 展示时间继续按 `Asia/Shanghai`；
      数据库、API、Canonical、Job 与内部调度时间继续使用 UTC/`timestamptz`。

# 范围

- TikHub 独立调试默认 `run_id`/运行目录时间格式；
- 日志 Formatter 的固定时区回归测试；
- TikHub 调试 README 的运行目录时间说明；
- 与上述行为直接相关的单元测试和时间入口复核。

# 非目标

- 不改数据库列、Migration、API、OpenAPI、Canonical、Job Payload 或 Scheduler 时间语义；
- 不重命名或迁移已经生成的历史调试目录；
- 不修改第三方 Provider 原始时间字段，不新增依赖；
- 不处理当前工作区中与本 Change 无关的目录重构、Transport 或测试修改。

# 必须保持不变

- `run_*()` 公共调用参数、显式 `run_id`、输出目录层级和文件内容保持兼容；
- 日志格式、脱敏、转义、截断、轮转和服务文件名保持兼容；
- PostgreSQL `timestamptz`、UTC ISO-8601 Contract、Raw/Canonical 审计时刻和调度比较保持不变；
- 用户现有未提交修改全部保留。

# 关键决策

- 用户确认采用“人工可见时间使用北京时间，机器事实与公共 Contract 保持 UTC”的边界；
- 目录后缀使用无歧义的 `+0800`，不使用可能同时表示多个时区的 `CST`；
- 已确认应用日志 Formatter、Raw Artifact 日期目录和调试 Excel 已使用 `Asia/Shanghai`，
  本次对日志补强固定时刻断言，不重复实现第二套时区转换。

# 任务

- [x] 调查当前实现和事实源
- [ ] 建立失败测试或说明测试例外
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 取得新鲜验证证据

# 验证

## 计划

- 目标测试：固定时刻验证默认运行目录名和日志行首的北京时间转换；
- 相关测试：TikHub 调试输出、Platform logging、Raw Artifact 日期目录；
- 静态检查/构建：Ruff format/lint、mypy、架构/Secret/文档门禁中与变更直接相关的检查。

## 新鲜证据

- 尚未执行。

# 文档影响

- 更新 `backend/src/aima_ugc/adapters/providers/tikhub_test/README.md`，明确自动运行目录采用
  `Asia/Shanghai` 和 `+0800`；Blueprint 已明确日志显示时区与机器 UTC 边界，不制造重复修改。

# 交付

- Commit：未授权，未执行。
- PR：未授权，未执行。
- 发布：未执行；无 Migration 或部署配置变化。
