---
schema: rvc-change/v1
id: "CHG-20260818-douyin-detail-400"
title: "抖音详情400不中断整批调试采集"
level: L2
status: in_progress
owner: "dingyuwen777"
branch: "fix/tikhub-test-default-paths"
created: 2026-08-18
updated: 2026-08-19
depends_on: []
affected_areas:
  - "provider-debug"
  - "douyin"
affected_paths:
  - "backend/src/aima_ugc/adapters/providers/tikhub_test/operations/runner.py"
  - "tests/unit/collection/test_tikhub_test_douyin_http_errors.py"
  - "tests/unit/collection/test_tikhub_test_debug.py"
  - "backend/src/aima_ugc/adapters/providers/tikhub_test/README.md"
  - "docs/collection/douyin.md"
contracts: []
data_changes: []
---

# 目标

TikHub 无数据库调试运行中，单个抖音搜索结果调用 `fetch_one_video_v3` 返回 HTTP 400
时，保存完整 Raw 和请求关联信息，将该内容标记为详情不可用并继续处理其余内容，不再让一个
内容级 Provider 失败中断整批关键词采集。

在该能力尚未归档前，继续收口 `tikhub_test` 目录重组后同一调试运行器的默认路径兼容：
默认 `.env` 必须来自 `tikhub_test/.env`，默认输出必须进入 `tikhub_test/output/`，不能因为
`runner.py` 移入 `operations/` 而漂移到当前工作目录的任意 `.env` 或 `operations/output/`。

# 成功标准

- [x] 抖音详情 V3 返回 HTTP 400 时 `run_douyin()` 不抛出整批异常，运行汇总状态为
      `completed_with_errors`。
- [x] 失败详情响应继续保存到 Raw，请求记录保留 HTTP 状态、TikHub request ID 和 Raw 路径，
      `content_failures` 能定位失败内容和 Operation。
- [x] 搜索阶段已经映射的内容继续进入人工可读结果，评论覆盖标记为 `unavailable`，不继续发送
      该内容的评论/回复请求。
- [x] 详情失败的内容不写入跨运行去重状态；下一次显式运行仍会重新尝试详情请求。
- [x] 其他 Operation 或其他 HTTP 错误仍保持原有 fail-fast 行为，不引入隐藏自动重试或备用
      Endpoint fallback。
- [ ] `env_file=None` 时直接使用 `TikHubTestConfig` 的固定默认 `tikhub_test/.env`，不扫描 CWD/父目录的任意 `.env`。
- [ ] `output_root=None` 时固定写入 `tikhub_test/output/`，不写入 `tikhub_test/operations/output/`。
- [ ] 显式 `env_file` / `output_root`、五平台入口、生产 Operation/Mapper/分页/Transport 单次发送语义保持兼容。

# 范围

- `tikhub_test` 调试运行器的抖音详情 HTTP 400 内容级容错；
- `tikhub_test` 目录重组后的默认配置/输出路径兼容；
- 无真实网络、无费用的回归测试；
- 必要的调试说明同步。

# 非目标

- 不修改五平台正式 Search/Detail/Comments/Replies Operation、参数、Mapper 或 Capability；
- 不增加自动重试，不切换 Web/V1/V2 或批量详情接口；
- 不改变生产 Worker 的 Provider Attempt、计费、重试或终态语义；
- 不重新发送真实付费请求；
- 不进入 Stage 8，不修改数据库、Migration、Analysis/Excel Contract 或依赖。

# 必须保持不变

- `run_douyin()` 及其他 `run_*()` 参数、返回类型和已有 `run_summary.json` 字段保持兼容；
- 每次 `send` 仍然恰好一次网络请求，HTTP 400 Raw 先保存后决策；
- TikHub Secret 不进入日志、汇总、测试 Fixture 或 Change；
- 非目标平台以及抖音非详情 HTTP 错误的异常行为保持不变；
- 用户确认保留的 `tikhub_test/core + operations + test.py` 目录结构与 TikHub 抓取逻辑保持不变；
- TikHub 默认 Origin 继续为 `https://api.tikhub.dev`，显式兼容既有 `.io`。

# 关键决策

- 真实 Raw 证明请求只包含非空 19 位 `aweme_id`；同一运行中该详情 Endpoint 已成功 8 次，
  因而不是路径或必填参数构造错误。
- TikHub 返回自己的 HTTP 400 错误结构和 request ID，并明确“请求失败，请重试，本次不会扣费”；
  这属于单内容 Provider/上游失败，不应升级成整批调试运行失败。
- 不按提示在代码内自动重试：仓库要求 Transport 一次发送，且真实 Provider 重试与费用必须显式；
  本次选择可逆的“记录并继续”，下一次人工运行自然形成新的请求。
- 失败内容保留 Search 已映射结果但不写跨运行状态，避免暂时性详情失败被永久当成已成功处理。
- 目录重组后默认路径必须相对 `tikhub_test` 包根，而不是相对移动后的 `operations/runner.py`；
  `TikHubTestConfig.load(None)` 已拥有固定 `.env` 默认，因此 `run_platform()` 不再自行扫描工作目录。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立抖音 400 失败测试
- [x] 完成抖音 400 最小实现
- [x] 同步抖音文档
- [x] 取得抖音 400 新鲜验证证据
- [ ] 建立目录重组默认路径 Red 回归
- [ ] 修复默认 `.env` / `output` 路径
- [ ] 取得目标、相关与整仓新鲜验证证据
- [ ] 两阶段复核并归档 Change

# 验证

## 已有抖音 400 证据

- Red：`uv run pytest tests/unit/collection/test_tikhub_test_douyin_http_errors.py -q`，
  退出码 1；Fake Detail HTTP 400 在 `_send` 被升级为整批 `RuntimeError`，与真实报错一致。
- Green：同一目标测试退出码 0，`1 passed`；增强为两条内容后证明第一条 400 不阻塞
  第二条，并证明下一运行会重新请求失败内容。
- 最终相关测试：`uv run pytest tests/unit/collection/test_douyin_tikhub_operation.py
  tests/unit/collection/test_tikhub_test_douyin_http_errors.py -q`，退出码 0，`12 passed`。

## 目录重组兼容计划

- Red：锁定 `_DEFAULT_OUTPUT_ROOT == tikhub_test/output`，并锁定 `run_platform(env_file=None)` 不调用 CWD `.env` 搜索。
- Green：只修改默认路径解析，不修改 Operation、Mapper、分页、HTTP 发送或费用语义。
- 相关回归：`tests/unit/collection`、Ruff、mypy、Architecture、Secret、Docs、Contract 和适用 GitHub Actions。

# 文档影响

- `docs/collection/douyin.md` 已说明 400 容错只属于 `tikhub_test` 调试入口，不改变生产 Provider 重试和 fallback 语义。
- `tikhub_test/README.md` 当前已经声明默认 `.env` 为 `tikhub_test/.env`、默认输出为 `tikhub_test/output/`；本次以代码修复对齐既有文档，不建立第二套规则。

# 交付

- 当前修复分支：`fix/tikhub-test-default-paths`。
- 完成前保持 `in_progress`；新鲜 CI、Review、合并和合并后验证完成后再归档。
- 不涉及数据库、Migration、依赖或 Stage 8。
