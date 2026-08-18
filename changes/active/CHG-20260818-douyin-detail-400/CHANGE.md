---
schema: rvc-change/v1
id: "CHG-20260818-douyin-detail-400"
title: "抖音详情400不中断整批调试采集"
level: L2
status: ready_for_review
owner: "dingyuwen777"
branch: "main"
created: 2026-08-18
updated: 2026-08-18
depends_on: []
affected_areas:
  - "provider-debug"
  - "douyin"
affected_paths:
  - "backend/src/aima_ugc/adapters/providers/tikhub_test/operations/runner.py"
  - "tests/unit/collection/test_tikhub_test_douyin_http_errors.py"
  - "docs/collection/douyin.md"
contracts: []
data_changes: []
---

# 目标

TikHub 无数据库调试运行中，单个抖音搜索结果调用 `fetch_one_video_v3` 返回 HTTP 400
时，保存完整 Raw 和请求关联信息，将该内容标记为详情不可用并继续处理其余内容，不再让一个
内容级 Provider 失败中断整批关键词采集。

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

# 范围

- `tikhub_test` 调试运行器的抖音详情 HTTP 400 内容级容错；
- 无真实网络、无费用的回归测试；
- 抖音采集说明中的调试失败边界。

# 非目标

- 不修改抖音正式 Search/Detail/Comments/Replies Operation、参数、Mapper 或 Capability；
- 不增加自动重试，不切换 Web/V1/V2 或批量详情接口；
- 不改变生产 Worker 的 Provider Attempt、计费、重试或终态语义；
- 不重新发送用户本次失败的真实付费请求，不处理无关的北京时间实现。

# 必须保持不变

- `run_douyin()` 参数、返回类型、输出目录和已有 `run_summary.json` 字段保持兼容；
- 每次 `send` 仍然恰好一次网络请求，HTTP 400 Raw 先保存后决策；
- TikHub Secret 不进入日志、汇总、测试 Fixture 或 Change；
- 非目标平台以及抖音非详情 HTTP 错误的异常行为保持不变；
- 用户当前工作区的目录重构、域名修改和其他未提交变更全部保留。

# 关键决策

- 真实 Raw 证明请求只包含非空 19 位 `aweme_id`；同一运行中该详情 Endpoint 已成功 8 次，
  因而不是路径或必填参数构造错误。
- TikHub 返回自己的 HTTP 400 错误结构和 request ID，并明确“请求失败，请重试，本次不会扣费”；
  这属于单内容 Provider/上游失败，不应升级成整批调试运行失败。
- 不按提示在代码内自动重试：仓库要求 Transport 一次发送，且真实 Provider 重试与费用必须显式；
  本次选择可逆的“记录并继续”，下一次人工运行自然形成新的请求。
- 失败内容保留 Search 已映射结果但不写跨运行状态，避免暂时性详情失败被永久当成已成功处理。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败测试或说明测试例外
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据

# 验证

## 计划

- 目标测试：构造 Search 200 + Detail 400 Fake Transport，验证结果、Raw、汇总和下次重试。
- 相关测试：抖音 Operation、TikHub 调试运行器现有无数据库纵切。
- 静态检查/构建：Ruff 目标文件、mypy 目标模块、架构/Secret/文档门禁。

## 新鲜证据

- Red：`uv run pytest tests/unit/collection/test_tikhub_test_douyin_http_errors.py -q`，
  退出码 1；Fake Detail HTTP 400 在 `_send` 被升级为整批 `RuntimeError`，与真实报错一致。
- Green：同一目标测试退出码 0，`1 passed`；增强为两条内容后证明第一条 400 不阻塞
  第二条，并证明下一运行会重新请求失败内容。
- 最终相关测试：`uv run pytest tests/unit/collection/test_douyin_tikhub_operation.py
  tests/unit/collection/test_tikhub_test_douyin_http_errors.py -q`，退出码 0，`12 passed`。
- `uv run ruff check ...`：退出码 0；`uv run ruff format --check ...`：退出码 0，
  两个目标文件均已格式化。
- `uv run mypy backend/src/aima_ugc/adapters/providers/tikhub_test/operations/runner.py`：
  退出码 0，无类型问题。
- `uv run python scripts/quality/check_docs.py` 与 `scan_secrets.py`：退出码均为 0。
- 扩展调试测试集合被现有目录重构阻塞：`test_tikhub_test_debug.py` 仍从包根导入当前未
  re-export 的 `TikHubTestConfig`，收集阶段 ImportError；本 Change 未修改该重构边界。
- 架构门禁被现有 `backend/src/aima_ugc/operations/*` 迁移缺文件阻塞并报告 ARCH001；报告路径
  均不在本 Change 影响范围内，本次不扩大范围修复。

# 文档影响

- 更新 `docs/collection/douyin.md`，明确该容错只属于 `tikhub_test` 调试入口，不改变生产
  Provider 重试和 fallback 语义。

# 交付

- Commit：未授权，未执行。
- PR：未授权，未执行。
- 发布：不涉及数据库、Migration、配置或依赖；未执行。
