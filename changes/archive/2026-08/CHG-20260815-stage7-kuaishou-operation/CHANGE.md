---
schema: rvc-change/v1
id: CHG-20260815-stage7-kuaishou-operation
title: 建立 Stage 7 快手 TikHub Operation 与分页状态机
level: L2
status: done
owner: dingyuwen777
branch: chore/archive-stage7-kuaishou-operation-final
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/kuaishou.py, tests/unit/collection/test_kuaishou_tikhub_operation.py, docs/collection/kuaishou.md, docs/collection/README.md, backend/src/aima_ugc/modules/collection/README.md, docs/blueprint/README.md, docs/blueprint/08-采集策略与平台能力.md]
contracts: []
data_changes: []
---

# 目标

按 Blueprint 08 已批准且本轮重新核验的 TikHub 快手主链，建立 App Search V2、App Detail、Web 一级评论、Web 二级评论的请求构造与保守 pcursor 状态。只实现一手资料可证明的请求事实，不在没有合法脱敏非空真实 Fixture 时猜 Mapper、响应 JSON path、评论列表字段或 Provider 结束哨兵。

# 成功标准

- [x] Search 固定 `GET /api/v1/kuaishou/app/search_video_v2`，只接受 `keyword + pcursor`；不伪造排序、发布时间、内容类型参数。
- [x] Detail 固定 `GET /api/v1/kuaishou/app/fetch_one_video`，使用 `photo_id`。
- [x] 一级评论固定 `GET /api/v1/kuaishou/web/fetch_one_video_comment`，使用 `photo_id + pcursor`；二级评论固定 `GET /api/v1/kuaishou/web/fetch_one_video_sub_comment`，使用 `photo_id + root_comment_id + pcursor`。
- [x] pcursor 状态只依据调用方可靠提取的返回值判断继续/不可用/不推进；未知非空游标继续传递，不猜响应 JSON path、评论列表字段或 `no_more` 等结束哨兵。
- [x] 第一轮契约 Red `32fe97466c874e3fc7cc658519caa0747fee7e60` 在 PR merge ref 上实际得到 `2 failed, 114 passed`、退出码 1，失败精确暴露 Web 参数名仍为 `photoId/rootCommentId`。
- [x] Review 继续发现未经一手资料证明的 `no_more -> provider_exhausted` 特例；第二轮 Red `9ee4eb7f17072ac2e91ce2d37180b555e03f7101` 实际得到 `3 failed, 113 passed`、退出码 1，第三个失败精确锁定该猜测语义。
- [x] Green `bc10e518556c94797ba2a9498f6082256abfc3d8` 只把 Web 参数改为官方 snake_case 并删除无证据 sentinel；PR CI `31868447755` 的 Stage 1 实际得到 Unit `116 passed`、Contract `33 passed`、API `3 passed`，Ruff/Mypy/Contract/Architecture/Table Owner/Secret/docs/Wheel/Frontend 均成功；该 head 的 7 个 PR workflow 全部成功。
- [x] 不新增 Mapper/Capability/Registry/Migration/数据库/依赖/API/前端，不接管后续 Stage 7 单元。
- [x] 功能 PR #44 已正常合并到 `main`，merge commit 为 `c66b055fe9fdf41a29618af6642e79a7f0c4c5bc`；合并后该提交的 7 个 push workflow 全部成功，主 CI `31868653033` 的 Stage 1 新鲜得到 Unit `116 passed`、Contract `33 passed`、API `3 passed`，并通过 Contract/兼容、Ruff、Mypy、Architecture、Table Owner、Secret、docs、Wheel、Frontend 与本地启动 smoke。
- [x] 快手平台文档、Collection 总览/模块 README 与 Blueprint 当前状态已在本 Change 收尾分支同步：明确 Operation 已进入 `main`，同时明确 Mapper、合法脱敏非空真实 Fixture、Real Probe、Capability/默认 Registry 尚未闭环，不把 Operation 通过等同于“快手已兼容”。

# 非目标与不变项

不实现 Mapper、真实 Fixture、Real Probe、Capability/Registry、Plan/Budget/Scheduler/Stage8 UI；不做其他 API family 静默 fallback。外部 ID 使用字符串；Operation 不访问 DB/Artifact/Secret；不执行付费真实 Provider 请求。

# 一手资料

- Search V2: https://docs.tikhub.io/467698481e0
- Detail: https://docs.tikhub.io/467698469e0
- Comments: https://docs.tikhub.io/336972174e0
- Sub comments: https://docs.tikhub.io/343506804e0

# 执行记录

[步骤 1：现状复核] → 修改范围：Blueprint、Active Change、PR #44、TikHub 官方文档 → 结果：确认 PR endpoint 选型与 Blueprint 一致，但 Web 参数 camelCase 与官方契约冲突，且 `no_more` 终止特判缺少当前一手资料/Fixture 证据。

[步骤 2：契约 Red] → 修改范围：`tests/unit/collection/test_kuaishou_tikhub_operation.py` → 结果：`32fe97466c874e3fc7cc658519caa0747fee7e60` 的 Stage 1 Unit 为 `2 failed, 114 passed`，退出码 1。

[步骤 3：分页 Review Red] → 修改范围：同一 Unit Test → 结果：`9ee4eb7f17072ac2e91ce2d37180b555e03f7101` 的 Stage 1 Unit 为 `3 failed, 113 passed`，退出码 1；新增失败只验证“不猜 Provider sentinel”。

[步骤 4：最小 Green] → 修改范围：`operations/kuaishou.py` → 结果：`bc10e518556c94797ba2a9498f6082256abfc3d8` 只修正 `photo_id/root_comment_id` 参数和删除 `no_more` 特判；Unit `116 passed`、Contract `33 passed`、API `3 passed`，7/7 PR workflow success。

[步骤 5：两阶段 Review] → 修改范围：PR #44 diff、Blueprint 08、官方请求参数 → 结果：需求范围与代码质量复核未发现新的严重/重要问题；不做无价值 Refactor。

[步骤 6：功能合并与 main 验证] → 修改范围：PR #44、最新 `main` → 结果：PR #44 正常 merge 为 `c66b055fe9fdf41a29618af6642e79a7f0c4c5bc`；该 merge commit 的 7/7 push workflow success，主 CI `31868653033` success。

[步骤 7：长期文档与 Change 收尾] → 修改范围：`docs/collection/kuaishou.md`、`docs/collection/README.md`、Collection 模块 README、Blueprint README/08、Change 生命周期 → 结果：长期文档按已进入 `main` 的机器事实更新，同时保留 Mapper/Fixture/Probe/Capability 未完成边界；本记录移动到 Archive。

# Git

- 功能分支：`feature/stage7-kuaishou-operation`
- 功能 PR：#44，已合并
- 最终功能 PR head：`e3e885070f6b536c862bcdaff0679765c724a319`
- 功能 merge commit：`c66b055fe9fdf41a29618af6642e79a7f0c4c5bc`
- 合并后 main push CI：7/7 workflow success；主 CI `31868653033` success
- 收尾分支：`chore/archive-stage7-kuaishou-operation-final`
- Change：done，归档到 `changes/archive/2026-08/CHG-20260815-stage7-kuaishou-operation/CHANGE.md`
