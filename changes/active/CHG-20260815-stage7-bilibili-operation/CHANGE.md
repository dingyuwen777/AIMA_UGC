---
schema: rvc-change/v1
id: CHG-20260815-stage7-bilibili-operation
title: 建立 Stage 7 B站 TikHub Operation 与分页状态机
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/stage7-bilibili-operation
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/bilibili.py, tests/unit/collection/test_bilibili_tikhub_operation.py, docs/collection/bilibili.md, backend/src/aima_ugc/modules/collection/README.md]
contracts: []
data_changes: []
---

# 目标

按 Blueprint 08 已批准并在 2026-08-15 重新核验的 TikHub B站 App 主链，建立分类搜索、视频详情、一级评论、二级回复的请求构造和有证据分页状态。只实现官方资料可证明的 Provider 请求事实，不在缺少合法脱敏真实 Fixture 时猜 Mapper/响应业务字段。

# 成功标准

- [ ] 搜索固定 `GET /api/v1/bilibili/app/fetch_search_by_type`，从 page=1 开始；业务排序映射 `general/latest/play_count/danmaku_count → totalrank/pubdate/click/dm`。
- [ ] 搜索内容类型只接受当前官方搜索分类值；Provider 私有 page/order/search_type 由 Operation 管理，不开放第三方枚举给业务层。
- [ ] 搜索 page 状态只消费未来可靠的 `has_results` observation；官方/当前仓库尚无可提交的合法非空真实 Fixture 时不猜结果数组路径。
- [ ] 详情固定 `GET /api/v1/bilibili/app/fetch_one_video`，使用稳定视频身份参数。
- [ ] 一级评论固定 `GET /api/v1/bilibili/app/fetch_video_comments`，请求只使用当前官方明确的业务视频身份、排序和分页参数；不在本单元解析评论业务字段。
- [ ] 二级回复固定 `GET /api/v1/bilibili/app/fetch_reply_detail`，按根评论和官方下一页状态推进；缺少稳定响应路径证据的字段不猜。
- [ ] Red 因 `operations.bilibili` 不存在正确失败；Green 后目标 Unit/Collection 回归/Quality/主 CI 成功。
- [ ] 不新增 Mapper/Capability/Registry/Migration/数据库/依赖/API/前端。
- [ ] B站平台文档与 Collection README 如实区分 Operation 与 Mapper/Fixture/Probe 状态。

# 非目标与不变项

不实现 Raw→Canonical Mapper、真实 Fixture、Real Probe、Capability/Registry、Plan/Budget/Scheduler、Stage8 UI；不做 Web endpoint fallback。外部 ID 保持字符串；Operation 不访问数据库、不写 Artifact、不读取 Secret。

# 一手资料

- Search: https://docs.tikhub.io/382707670e0
- Detail: https://docs.tikhub.io/382707662e0
- Comments: https://docs.tikhub.io/382707663e0
- Reply detail: https://docs.tikhub.io/382707664e0

# 实施步骤

[步骤 1：Red] → 修改范围：B站 Operation Unit Test → 预期结果：目标模块缺失导致正确失败 → 验证：PR Actions 完整 pytest 输出。

[步骤 2：Green] → 修改范围：`operations/bilibili.py` → 预期结果：唯一生产请求/分页实现 → 验证：目标与 Collection Unit。

[步骤 3：文档/Review] → 修改范围：B站平台文档、Collection README → 预期结果：当前状态准确 → 验证：quality/docs + 两阶段 Review。

# 验证

`uv lock --check`、Ruff、mypy、Collection Unit、架构/Table Owner/Secret/docs 门禁和相关主 CI。当前宿主无本地 AIMA checkout，真实 TikHub DNS 也不可用，因此不伪造本地/Real Probe 结果。

# Git

- 分支：`feature/stage7-bilibili-operation`
- PR/CI/合并：待本轮执行
- Change：in_progress
