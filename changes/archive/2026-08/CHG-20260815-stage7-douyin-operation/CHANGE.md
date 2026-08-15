---
schema: rvc-change/v1
id: CHG-20260815-stage7-douyin-operation
title: 建立 Stage 7 抖音 TikHub Operation 与分页状态机
level: L2
status: done
owner: dingyuwen777
branch: feature/stage7-douyin-operation
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-decision-capability]
affected_areas: [collection, provider, testing, documentation, blueprint]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/douyin.py, tests/unit/collection/test_douyin_tikhub_operation.py, docs/collection/douyin.md, backend/src/aima_ugc/modules/collection/README.md, docs/blueprint/README.md, docs/blueprint/08-采集策略与平台能力.md]
contracts: []
data_changes: []
---

# 目标与结果

按 Blueprint 08 已批准并于 2026-08-15 重新核验的 TikHub 官方接口，建立抖音 Search V2、App V3 详情、App V3 一级评论、App V3 评论回复的正式请求构造与基础分页状态机。当前结果只证明 Operation/分页机器事实已经建立；Douyin Raw→Canonical Mapper、合法脱敏非空真实 Fixture、Real Provider Probe、Capability/默认 Registry 接线仍未完成，因此不能宣称抖音平台已经兼容。

# 成功标准

- [x] 搜索固定 `POST /api/v1/douyin/search/fetch_video_search_v2`，首屏 `cursor=0`、`search_id/backtrace=''`，后续继承 Provider 分页状态。
- [x] `general/most_liked/latest → sort_type=0/1/2`；`all/1d/7d/180d → publish_time=0/1/7/180`；时长和内容类型同样由规范化业务值映射 Provider 枚举。
- [x] Search 分页覆盖空页、完整重复页、Provider 结束和 cursor 不推进；重复页按 aweme_id 集合判断，不受返回顺序影响。
- [x] 详情固定 `GET /api/v1/douyin/app/v3/fetch_one_video_v3`。
- [x] 一级评论固定 `GET /api/v1/douyin/app/v3/fetch_video_comments`，评论回复固定 `GET /api/v1/douyin/app/v3/fetch_video_comment_replies`；两者均不覆盖 TikHub 官方要求保持默认的 `count`。
- [x] 评论/回复分页只依赖当前已确认的 `cursor + has_more`；没有在缺 Fixture 时猜评论数组字段或稳定增量停止语义。
- [x] 正确 Red、Green、两阶段 Review、PR CI、合并后 main CI 均有新鲜证据。
- [x] 没有新增 Migration、数据库、依赖、公共 API、Mapper、Capability、Registry 或前端代码。
- [x] 抖音平台文档、Collection README、Blueprint README/08 已同步当前机器状态。

# 范围与非目标

范围：抖音 TikHub Search V2 业务参数映射和分页；App V3 Detail/Comments/Replies 请求构造；Unit Test 与实现状态文档。

非目标：Douyin Mapper、真实 Fixture、Real Probe、Capability/Registry、Plan、Budget、Scheduler、Stage 8 API/前端、静默 fallback。

# 必须保持不变

- 每个业务 Operation 使用 Blueprint 08 批准的唯一主 endpoint，不做通用 fallback。
- cursor/search_id/backtrace 等 Provider 技术状态不进入前端业务 Contract。
- 评论/回复 `count` 使用 TikHub 默认值。
- Operation 不访问数据库、不写 Artifact、不做 Canonical Mapper。
- Secret 不进入请求描述、测试、日志或 Git。

# Red → Green

## Red

PR #38 Red head `f261da0ccec42abfcf34b2dca81ed879daed9153`，Stage 6 XHS Vertical Slice run `31856482313` / Unit job `94942102485`：锁定环境安装成功，pytest collection 因 `aima_ugc.adapters.providers.tikhub.operations.douyin` 不存在而失败，`1 error during collection`，退出码 2。失败来自目标生产模块尚不存在，不是依赖或旧测试故障。

## Green / Final PR

最终 PR head `eaec78c12dfb99da6f4222539c8de8b4c16eb7c1`：Stage 6 Unit 完整日志为 `69 passed`、0 failed、退出码 0；CI、Stage 5A、Stage 5B、Stage 5C、Stage 5D、Stage 6、Stage 7 Provider Config Routing 共 7 条相关 workflow 全部 success。PR 无 review thread、review submission 或讨论阻塞，随后正常 merge。

# 两阶段 Review

需求符合性：四个 endpoint 与批准主链一致；未越界实现 Mapper/Capability/Registry/Plan/Budget/Scheduler；文档没有把 Operation 完成写成平台兼容完成。

代码质量：Operation 是纯请求/分页逻辑；Search 只读取分页去重所需 aweme_id；评论分页不猜未证明字段。Review 发现最初重复页要求 ID 顺序完全一致，已改为同长度且 ID 集合相同即停止，并补乱序重复页回归测试。

# 文档同步

已更新：

- `docs/collection/douyin.md`
- `backend/src/aima_ugc/modules/collection/README.md`
- `docs/blueprint/README.md`
- `docs/blueprint/08-采集策略与平台能力.md`

Blueprint endpoint/业务设计未改变，只同步当前机器实现状态。

# 兼容、依赖、Migration、部署和回滚

- Contract/API/Schema：无变化。
- Migration/数据库：无变化。
- 依赖/Lock：无变化。
- 部署：无变化；未执行生产部署。
- 回滚：回滚本 Change 的 Operation/测试/文档即可，无数据回滚。

# Git 与集成证据

- 基线 main：`86bcafb84005858af865e506ed4885dbceb2ffb0`
- 开发分支：`feature/stage7-douyin-operation`（PR 合并后由仓库自动删除）
- PR：#38
- 最终 PR head：`eaec78c12dfb99da6f4222539c8de8b4c16eb7c1`
- merge commit / 合并后 main HEAD：`9a998a6fc1292c18370e2c9b54df0be05d53a467`
- 合并后 main：CI、Stage 5A、Stage 5B、Stage 5C、Stage 5D、Stage 6、Stage 7 共 7 条 push workflow 全部 `success`；主 CI run `31857049013` 的前端 lint/type/test/build、后端 checks、生成 Contract/Client、Wheel、本地双服务 smoke 均成功。
- Change：完成后由独立归档 PR 移入 `changes/archive/2026-08/`。
- 生产部署：未执行。

当前执行宿主无法取得用户本地 AIMA_UGC 工作树，因此没有本地 `git status`、未推送提交或本地测试证据；上述验证来自本轮 GitHub Actions。