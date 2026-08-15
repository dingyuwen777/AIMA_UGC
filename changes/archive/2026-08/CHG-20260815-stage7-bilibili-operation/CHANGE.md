---
schema: rvc-change/v1
id: CHG-20260815-stage7-bilibili-operation
title: 建立 Stage 7 B站 TikHub Operation 与分页状态机
level: L2
status: done
owner: dingyuwen777
branch: feature/stage7-bilibili-operation
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/bilibili.py, tests/unit/collection/test_bilibili_tikhub_operation.py, docs/collection/bilibili.md]
contracts: []
data_changes: []
---

# 结果

B站 TikHub App 分类搜索、视频详情、一级评论与二级回复的请求构造和保守分页状态已建立并通过 PR、Review、CI 与合并后 main 验证。当前只完成 Operation/分页机器事实；B站 Raw→Canonical Mapper、合法脱敏非空真实 Fixture、Real Provider Probe、Capability/默认 Registry 仍未完成，因此不能宣称 B站平台兼容完成。

# 关键边界

- 搜索固定 `GET /api/v1/bilibili/app/fetch_search_by_type`，当前 AIMA 只开放已验证视频搜索；业务排序 `general/latest/play_count/danmaku_count → totalrank/pubdate/click/dm`。
- 搜索结果列表 JSON path 未被真实 Fixture 证明，因此分页只消费可靠 `has_results` observation。
- 详情固定 `GET /api/v1/bilibili/app/fetch_one_video`，使用字符串 `bvid`。
- 一级评论固定 `GET /api/v1/bilibili/app/fetch_video_comments`，使用 `oid`，Provider 分页串只透传可靠返回值。
- 二级回复固定 `GET /api/v1/bilibili/app/fetch_reply_detail`，使用 `oid/root/next`；响应游标 path 未被真实 Fixture 证明，因此只处理可靠提取后的数字游标。
- 未新增 Mapper、Capability、Registry、Migration、数据库、依赖、公共 API 或前端代码。

# 验证与 Review

本 Change 按 Red→Green 执行：Red 先提交目标测试并观察目标 `operations.bilibili` 模块缺失导致 pytest collection 失败；Green 后建立唯一生产 Operation，并通过相关 Collection/Content/Provider Contract、Quality、PostgreSQL 和主 CI 回归。需求 Review 确认没有越界实现 Mapper/Capability/Plan/Budget/Scheduler；代码 Review 确认没有猜搜索/评论响应数组和回复游标 path。

# 文档

已同步 `docs/collection/bilibili.md`，明确 Operation 已实现而 Mapper/Fixture/Probe 尚未完成。Blueprint endpoint/业务设计未改变；Stage 7 多平台 Operation 的统一进度摘要在快手同类单元闭环后更新。

# 兼容与回滚

Contract/API/Schema、Migration/数据库、依赖/Lock 和部署均无变化。回滚只需回滚 B站 Operation/测试/平台文档提交，无数据回滚。

# Git

- 开发 PR：#42，已正常合并
- 合并后 main：相关 push workflow 已检查无失败/排队/执行中
- 生产部署：未执行
- Change：done，归档到 `changes/archive/2026-08/`
