---
schema: rvc-change/v1
id: CHG-20260815-stage7-kuaishou-operation
title: 建立 Stage 7 快手 TikHub Operation 与分页状态机
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/stage7-kuaishou-operation
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/kuaishou.py, tests/unit/collection/test_kuaishou_tikhub_operation.py, docs/collection/kuaishou.md, backend/src/aima_ugc/modules/collection/README.md]
contracts: []
data_changes: []
---

# 目标

按 Blueprint 08 已批准且本轮重新核验的 TikHub 快手主链，建立 App Search V2、App Detail、Web 一级评论、Web 二级评论的请求构造与保守 pcursor 状态。只实现一手资料可证明的请求事实，不在没有合法脱敏非空真实 Fixture 时猜 Mapper/响应列表字段。

# 成功标准

- [ ] Search 固定 `GET /api/v1/kuaishou/app/search_video_v2`，只接受 keyword + pcursor；不伪造排序、发布时间、内容类型参数。
- [ ] Detail 固定 `GET /api/v1/kuaishou/app/fetch_one_video`，使用 `photo_id`。
- [ ] 一级评论固定 `GET /api/v1/kuaishou/web/fetch_one_video_comment`，使用官方 photo/comment 游标参数；二级评论固定 `GET /api/v1/kuaishou/web/fetch_one_video_sub_comment`。
- [ ] pcursor 状态只依据可靠返回值判断继续/不可用/不推进；响应 JSON path 和评论列表字段留待真实 Fixture。
- [ ] Red 因 `operations.kuaishou` 缺失正确失败；Green 后 Unit/Quality/相关 CI 成功。
- [ ] 不新增 Mapper/Capability/Registry/Migration/数据库/依赖/API/前端。
- [ ] 快手文档与 Collection README 如实区分 Operation 与 Mapper/Fixture/Probe 状态。

# 非目标与不变项

不实现 Mapper、真实 Fixture、Real Probe、Capability/Registry、Plan/Budget/Scheduler/Stage8 UI；不做其他 API family 静默 fallback。外部 ID 使用字符串；Operation 不访问 DB/Artifact/Secret。

# 一手资料

- Search V2: https://docs.tikhub.io/467698481e0
- Detail: https://docs.tikhub.io/467698469e0
- Comments: https://docs.tikhub.io/336972174e0
- Sub comments: https://docs.tikhub.io/343506804e0

# 流程

Red 测试 → 正确失败 → 最小 Operation → Unit/Quality → 文档 → 两阶段 Review → PR CI → merge → main CI → archive。

# Git

- 分支：`feature/stage7-kuaishou-operation`
- PR/CI/合并：待执行
- Change：in_progress
