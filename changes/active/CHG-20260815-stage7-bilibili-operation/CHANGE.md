---
schema: rvc-change/v1
id: CHG-20260815-stage7-bilibili-operation
title: 建立 Stage 7 B站 TikHub Operation 与分页状态机
level: L2
status: ready_for_review
owner: dingyuwen777
branch: chore/archive-stage7-bilibili-operation
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/bilibili.py, tests/unit/collection/test_bilibili_tikhub_operation.py, docs/collection/bilibili.md, docs/collection/README.md, backend/src/aima_ugc/modules/collection/README.md]
contracts: []
data_changes: []
---

# 目标

按 Blueprint 08 已批准的 TikHub B站 App 主链和 2026-08-15 当前官方文档，建立分类搜索、视频详情、一级评论、二级回复的请求构造与有证据分页状态。只实现官方资料可证明的 Provider 请求事实，不在缺少合法脱敏真实 Fixture 时猜 Mapper、评论响应字段或稳定增量停止语义。

原 PR #42 已把首版 Operation 合入 `main`，但本轮收尾复核发现其搜索分页/排序和评论/回复请求参数与当前 TikHub 官方契约不一致，因此不能直接归档。本 Change 继续作为同一 Stage 7 正式单元，先建立回归 Red，再做最小 Green 修复、兼容性 Review 和文档同步。

# 成功标准

- [x] 搜索固定 `GET /api/v1/bilibili/app/fetch_search_by_type`，首屏不发送空 cursor；业务排序映射 `general/latest/play_count/danmaku_count → 0/1/2/3`，首版只允许 `search_type=video`，并保留原有 `general` 默认排序。
- [x] 搜索下一页只解析当前官方明确的 `$.data.data.pagination.next`；缺失/空时 `provider_exhausted`，重复 cursor 时 `pagination_not_advanced`，不猜搜索结果数组/业务字段。
- [x] 详情固定 `GET /api/v1/bilibili/app/fetch_one_video`，`av_id` / `bv_id` 必须二选一且保持字符串身份。
- [x] 一级评论固定 `GET /api/v1/bilibili/app/fetch_video_comments`，`av_id` / `bv_id` 二选一，`latest/hot → mode=2/3`，后续页只发送调用方可靠提取的 `next_offset`；不猜评论响应分页路径。
- [x] 二级回复固定 `GET /api/v1/bilibili/app/fetch_reply_detail`，使用 `root + av_id/bv_id + 可选 next_offset`，不覆盖 Provider 默认 `ps`，不猜回复响应分页路径。
- [x] 首轮回归 Red 提交 `6c250a99aca736e1deb9ed653570fdc2592c0f3b` 仅修改测试；Stage 6 Unit 实际得到 `10 failed, 84 passed`、退出码 1，失败均来自旧请求契约。
- [x] 首轮 Green 提交 `5b5392529e03e626f00b32e1ddf627e872843354` 只做最小生产修复；同一 Stage 6 Unit 命令实际得到 `94 passed`、退出码 0。
- [x] 两阶段 Review 发现首轮 Green 无必要地把默认排序从 `general` 改为 `latest`，并把数字 offset 的“回退即停止”放宽为“仅相等停止”；第二轮 Red `6e35d296c63a77d3fb727ffcdcce266e8db02102` 实际得到 `2 failed, 93 passed`、退出码 1。
- [x] Review 修复提交 `7f687316a74a052295dda723935aac4f28b9e2ba` 恢复原有默认排序和保守游标语义；同一 Stage 6 Unit 命令实际得到 `95 passed`、退出码 0。
- [x] 不新增 Mapper/Capability/Registry/Migration/数据库/依赖/API/前端，不接管并行快手实现。
- [x] B站平台文档、Collection 总览和 Collection 模块 README 已同步 Operation 与 Mapper/Fixture/Probe/Capability 的真实边界。
- [ ] PR #43 正常合并后，最新 `main` 包含修复且相关 CI 新鲜成功；随后才允许把 Change 标记 `done` 并移动到 Archive。

# 非目标与不变项

不实现 Raw→Canonical Mapper、真实 Fixture、Real Probe、Capability/Registry、Plan/Budget/Scheduler、Stage 8 UI；不做 Web endpoint fallback。外部 ID 保持字符串；Operation 不访问数据库、不写 Artifact、不读取 Secret。真实付费 Provider Probe 不进入普通 CI，本单元不产生付费请求。

# 一手资料

- Search: https://docs.tikhub.io/382707670e0
- Detail: https://docs.tikhub.io/382707662e0
- Comments: https://docs.tikhub.io/382707663e0
- Reply detail: https://docs.tikhub.io/382707664e0

# 实施与验证记录

[步骤 1：事实复核] → 修改范围：PR #42、当前 Operation、TikHub 当前官方文档 → 结果：确认首版实现与当前官方 Search/Comments/Reply 请求契约不一致，禁止直接归档。

[步骤 2：Regression Red] → 修改范围：`tests/unit/collection/test_bilibili_tikhub_operation.py` → 结果：只改测试后 CI 真实失败，`10 failed, 84 passed`，退出码 1；失败命中旧 `page/order`、缺少官方 cursor 解析及旧详情/评论/回复参数签名。

[步骤 3：Green] → 修改范围：`operations/bilibili.py` → 结果：修正当前官方请求契约和保守分页边界；同一 Unit 集合 `94 passed`，退出码 0。

[步骤 4：兼容性 Review Red] → 修改范围：B站 Operation Unit Test → 结果：只增加“默认仍为 general”和“offset 回退必须停止”断言后，CI 得到 `2 failed, 93 passed`、退出码 1，证明首轮 Green 存在无需求支撑的行为扩大。

[步骤 5：兼容性 Review Green] → 修改范围：`operations/bilibili.py` → 结果：只恢复 `general` 默认值和 `returned_cursor <= previous_cursor` 停止规则；同一 Unit 集合 `95 passed`、退出码 0，TikHub 当前请求契约修复保持不变。

[步骤 6：文档/Review] → 修改范围：B站平台文档、Collection README、Collection 模块 README、本 Change → 结果：长期文档只描述当前机器事实，不把 Operation 等同平台兼容；等待 PR #43 最终 CI 与合并后 main 验证。

# 验证

PR Actions 使用仓库锁定环境执行 `uv lock --check`、`uv sync --locked`、Ruff、mypy、Collection Unit、架构/Table Owner/Secret/docs 等既有门禁。当前宿主没有可访问的用户本地 AIMA 工作区，因此不把远端干净等同于用户本地 `git status`；本单元没有合法脱敏非空 B站 Fixture，也不伪造 Real Provider Probe 结果。

# Git

- 原实现 PR：#42，已合并，但本轮发现请求契约缺陷后继续修复同一 Change。
- 当前收尾/修复分支：`chore/archive-stage7-bilibili-operation`
- 当前 PR：#43 `chore/archive-stage7-bilibili-operation → main`
- 分支同步：`a30498caad12fb763bc4b8b90b3aa816a8f244c5`，非强制 merge 当前基线 main。
- 首轮 Regression Red：`6c250a99aca736e1deb9ed653570fdc2592c0f3b`
- 首轮 Green：`5b5392529e03e626f00b32e1ddf627e872843354`
- Review Red：`6e35d296c63a77d3fb727ffcdcce266e8db02102`
- Review Green：`7f687316a74a052295dda723935aac4f28b9e2ba`
- Change：`ready_for_review`；只有 PR #43 合并、合并后 main CI 验证成功后才转 `done`/Archive。
