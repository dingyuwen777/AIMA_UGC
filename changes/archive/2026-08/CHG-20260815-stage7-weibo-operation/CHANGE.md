---
schema: rvc-change/v1
id: CHG-20260815-stage7-weibo-operation
title: 建立 Stage 7 微博 TikHub Operation 与分页状态机
level: L2
status: done
owner: dingyuwen777
branch: feature/stage7-weibo-operation
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py, tests/unit/collection/test_weibo_tikhub_operation.py, docs/collection/weibo.md, backend/src/aima_ugc/modules/collection/README.md]
contracts: []
data_changes: []
---

# 目标与结果

按 Blueprint 08 已批准并在 2026-08-15 重新核验的 TikHub 官方接口，建立微博 Web 搜索、App 详情、App 一级评论、Web V2 二级评论的正式请求构造与有证据的分页状态。当前结果只证明 Operation/分页机器事实；Weibo Raw→Canonical Mapper、合法脱敏非空真实 Fixture、Real Provider Probe、Capability/默认 Registry 仍未完成，不能宣称微博平台兼容完成。

# 成功标准

- [x] Web Search 使用 `/api/v1/weibo/web/fetch_search`，page 从 1 开始，`general/realtime/hot/video/image/article → search_type=1/61/60/64/63/21`；`all` 不发送 `time_scope`，其余支持 hour/day/week/month。
- [x] Detail 使用 `/api/v1/weibo/app/fetch_status_detail`，参数为当前官方 `status_id`。
- [x] 一级评论使用 `/api/v1/weibo/app/fetch_status_comments`，参数为 `status_id/max_id/sort_type`；只按官方 `data.moreInfo.params.max_id` 提取游标，空值停止、相同值不推进、路径缺失 fail-closed。
- [x] 二级评论使用 `/api/v1/weibo/web_v2/fetch_post_sub_comments`，根评论参数为 `id`，首屏 `max_id=''`，不覆盖可选 `count`；响应 max_id 路径未被真实 Fixture 证明，因此只处理调用方可靠提取后的游标状态，不猜 JSON path。
- [x] 搜索结果列表字段未被官方资料/真实 Fixture证明，因此 Operation 只消费可靠 `has_results` observation 推进 page，不猜第三方列表路径。
- [x] Red→Green、两阶段 Review、PR CI、合并后 main CI 均完成；PR 无未解决 Review/讨论阻塞。
- [x] 不新增 Mapper、Capability、Registry、Migration、数据库、依赖、公共 API 或前端代码。
- [x] `docs/collection/weibo.md` 与 Collection README 同步当前机器事实和未验证边界。

# Red → Green

Red：PR #40 初始 head `f71d48a19900b4af447494e034f654d6a811cb0a`，Stage 6 run `31857426164` / Unit job `94944721799` 在锁定环境正常的情况下，仅因 `aima_ugc.adapters.providers.tikhub.operations.weibo` 尚不存在而 pytest collection 失败，1 error，退出码 2。

Green：实现后相关 Unit/Quality/PostgreSQL/主 CI 回归成功；最终 PR head 无 failure、queued 或 in-progress workflow，且没有 review thread/review submission/讨论阻塞，随后正常合并。合并后最新 main 的相关 push workflows 再次检查为完成且无失败/挂起后归档本 Change。

# 两阶段 Review

需求符合性：四个 endpoint 与批准主链一致；Detail/一级评论使用当前官方 `status_id`，二级评论使用根评论 `id`；没有静默 fallback，也没有越界实现 Mapper/Capability/Plan/Budget/Scheduler。

代码质量：搜索不猜结果数组；一级评论游标路径缺失时明确失败；二级评论将“游标提取”和“游标状态转换”解耦，真实 Fixture 到位前不引入虚假解析；无依赖/锁文件/Migration/API 变化。

# 文档同步

已同步 `docs/collection/weibo.md` 与 Collection 模块 README。Blueprint endpoint/业务设计本身未变化；Stage 7 多平台 Operation 进度将在 B站/快手同类 Operation 闭环后统一更新 Blueprint README/08，避免多个内部 PR 反复重写同一导航摘要。

# 兼容、Migration、部署与回滚

- Contract/API/Schema：无变化。
- Migration/数据库：无变化。
- 依赖/Lock：无变化。
- 部署：无变化，未执行生产部署。
- 回滚：回滚微博 Operation/测试/文档提交即可，无数据回滚。

# Git

- 开发分支：`feature/stage7-weibo-operation`
- PR：#40，已正常合并
- Red head：`f71d48a19900b4af447494e034f654d6a811cb0a`
- 合并后 main：相关 push workflow 已完成且无失败/挂起
- Change：done，归档到 `changes/archive/2026-08/`
- 生产部署：未执行

当前执行宿主无法取得用户本地 AIMA_UGC 工作树，因此没有本地 `git status`、未推送提交或本地测试证据；上述验证来自本轮 GitHub Actions。