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
affected_areas: [collection, provider, testing, documentation, blueprint]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub/operations/weibo.py, tests/unit/collection/test_weibo_tikhub_operation.py, docs/collection/weibo.md, backend/src/aima_ugc/modules/collection/README.md, docs/blueprint/README.md, docs/blueprint/08-采集策略与平台能力.md]
contracts: []
data_changes: []
---

# 目标与最终结果

按 Blueprint 08 已批准并于 2026-08-15 重新核验的 TikHub 官方接口，建立微博首版四类 Operation：Web 搜索、App 详情、App 一级评论、Web V2 二级评论。只实现官方资料足以证明的请求构造和分页状态；没有合法脱敏非空真实 Fixture 的响应列表字段不猜、不提前写 Mapper，也不宣称微博平台兼容完成。

最终 main 已建立：

- Web Search 规范化业务参数映射与 page 状态；
- App Detail `status_id` 请求；
- App 一级评论请求与官方 `data.moreInfo.params.max_id` 游标；
- Web V2 二级评论请求与不猜响应路径的 max_id 状态转换；
- AIMA 上层统一使用 `latest` 业务语义，搜索映射 `search_type=61`，一级评论默认映射 `sort_type=1`；
- 微博平台文档、Collection README 和 Blueprint 当前机器状态同步。

Weibo Mapper、合法脱敏非空真实 Fixture、Real Provider Probe、Capability/默认 Registry 接线仍未实现，因此本 Change 的完成结论仅为“微博 Operation/有证据分页已实现”，不是“微博平台已兼容”。

# 成功标准

- [x] 搜索固定使用 `GET /api/v1/weibo/web/fetch_search`；页码从 1 开始；规范化 `general/latest/hot/video/image/article` 映射 `search_type=1/61/60/64/63/21`。
- [x] AIMA 关键词监控默认搜索使用 `latest`，映射 Provider “实时/最新优先” `search_type=61`，不引入第二套 `realtime` 上层语义。
- [x] 搜索时间 `all/hour/day/week/month` 中，`all` 不发送 `time_scope`；page 状态不猜搜索结果列表字段。
- [x] 详情固定使用 `GET /api/v1/weibo/app/fetch_status_detail`，参数为 `status_id`。
- [x] 一级评论固定使用 `GET /api/v1/weibo/app/fetch_status_comments`；默认 `latest → sort_type=1`，显式 `hot → 0`；首屏不传 `max_id`。
- [x] 一级评论只按官方 `$.data.moreInfo.params.max_id` 推进；空值结束，相同值停止。
- [x] 二级评论固定使用 `GET /api/v1/weibo/web_v2/fetch_post_sub_comments`；`id` 为根评论 ID，首屏 `max_id=''`，不覆盖可选 `count`。
- [x] 二级评论只对已经可靠提取的 returned max_id 做状态转换，不猜当前官方文档未提供的响应 JSON path。
- [x] Red 测试先因目标模块不存在而正确失败，Green 后目标和相关回归通过。
- [x] 不新增 Mapper、Capability、Registry、Migration、数据库、依赖、公共 HTTP API 或前端代码。
- [x] Blueprint README/08 与 Collection/微博文档同步当前事实；并行 B站机器事实只做兼容记录，不接管其独立 Change。
- [x] PR #40 在最新 main merge-ref 上通过完整 CI 后正常合并。
- [x] 合并后 main 再次通过 7 条相关 push workflow。

# 范围与非目标

本 Change 只负责 Weibo Operation 请求/分页机器边界、Unit Test 和受影响文档。明确不负责：

- Weibo Raw→Canonical Mapper；
- 未经脱敏的真实 Provider 响应；
- Weibo Capability/默认 Registry；
- Search 结果列表字段或 Web V2 二级评论返回 max_id JSON path 的猜测解析；
- Plan、Budget、Scheduler、Stage 8 API/前端；
- App/Web 静默 fallback；
- 并行 B站 Change 的代码、测试、Review、CI、文档或归档。

# 已确认 Provider 事实

2026-08-15 重新核验 TikHub 官方文档：

- Search: `https://docs.tikhub.io/381269400e0`
- Detail: `https://docs.tikhub.io/410358103e0`
- Comments: `https://docs.tikhub.io/410358104e0`
- Sub comments: `https://docs.tikhub.io/381269410e0`

当前实现只使用其中已能确定的请求与游标事实：Search page/search_type/time_scope；Detail status_id；一级评论 status_id/max_id/sort_type 与 `data.moreInfo.params.max_id`；二级评论 root `id`/max_id。二级评论响应 max_id 的稳定 JSON path 未由官方文档/合法 Fixture 证明，因此保持未实现。

# Red → Green 证据

## Red

PR #40 Red head `f71d48a19900b4af447494e034f654d6a811cb0a`，Stage 6 run `31857426164` / Unit job `94944721799`：

- 锁定 Python/uv 环境安装成功；
- pytest collection 因 `aima_ugc.adapters.providers.tikhub.operations.weibo` 不存在而失败；
- 1 个 collection error；
- pytest 退出码 2。

失败来自目标生产能力尚未实现，不是依赖、数据库或旧测试故障。

## Green 与 Review

首次 Green head `4555d0cd32e84efd9a012709e53625451409bb72`：

- Stage 6 Unit：`82 passed in 2.91s`，0 failed；
- CI、Stage 5A、Stage 5B、Stage 5C、Stage 5D、Stage 6、Stage 7 共 7 条 workflow success。

两阶段 Review 修正：

1. 把最初的 AIMA `realtime → 61` 改为跨平台统一 `latest → 61`；
2. 把 Search/一级评论默认值从 `general/hot` 对齐为已批准的“最新优先”默认；
3. 清理 Blueprint 全文件写回造成的 EOF 噪声；
4. 开发期间 main 并行出现 B站 Operation 后，只在微博本就触及的共享 README/Blueprint 中兼容记录“B站机器代码已在 main、B站 Active Change 尚未闭环”，没有接管 B站生产代码或生命周期。

最终 PR head `91db8726781be58c04b71527ccf44c614d863eb7` 在 `main=0e4a74674dc5027a9b65bddace49cb50974e4f7a` 的 merge-ref 上：

- Stage 6 Unit：`93 passed`，0 failed；
- CI、Stage 5A—5D、Stage 6、Stage 7 共 7 条 workflow 全部 success；
- 主 CI Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全部 success；
- PR 无 review thread、review submission 或 conversation comment 阻塞。

# 合并后 main 新鲜验证

PR #40 以 merge commit 正常合并：

```text
5e35eeccd1e476dd0a57f482ff70d48dd44a8909
```

合并后 main HEAD 确认为该提交，并触发 7 条 push workflow；最终全部 `success`：

- CI run `31865263862`；
- Stage 5A Provider Raw run `31865263868`；
- Stage 5B Collection Execution；
- Stage 5C Provider Persistence；
- Stage 5D Provider Dispatch；
- Stage 6 XHS Vertical Slice run `31865263852`；
- Stage 7 Provider Config Routing run `31865263858`。

主 CI 四个 Job 全部 success：Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap。Stage 1 中锁文件、生成 Contract/Client、Backend/Repository checks、Wheel、Frontend checks 均成功。

合并后 Stage 6 Unit job `94965186345` 完整日志：

```text
93 passed in 3.07s
```

0 failed，退出码 0。Stage 6 PostgreSQL/Quality 同时 success，包括 Migration round trip。

# 文档同步

已同步：

- `docs/collection/weibo.md`：endpoint、AIMA→Provider 参数映射、已证明分页边界和未验证边界；
- `backend/src/aima_ugc/modules/collection/README.md`：微博生产入口/独立验证/限制，并兼容记录并行 B站机器状态；
- `docs/blueprint/README.md`：Stage 7 当前机器进度、并行 B站 Active Change 与剩余单元；
- `docs/blueprint/08-采集策略与平台能力.md`：Operation Matrix、微博当前状态、B站并行机器状态与 Stage 7 门禁。

微博主 endpoint/业务设计未改变；Blueprint 仅同步实现状态并统一既有 `latest` 业务语义。

# 并行 B站 Change

微博开发/合并期间，B站 Operation merge commit `0e4a74674dc5027a9b65bddace49cb50974e4f7a` 已进入 main。归档微博时，`changes/active/CHG-20260815-stage7-bilibili-operation/CHANGE.md` 仍为：

```text
status: in_progress
```

本 Change 没有修改 B站 Operation、测试、平台文档或 Change 生命周期，也没有替其宣称完成。后续应由 B站 Change 自己完成 Review、CI、文档和归档。

# 未验证内容与剩余风险

- 当前执行宿主无法解析 TikHub 域名，因此本 Change 没有新增真实微博 Provider Probe，也没有产生 Provider 请求费用；
- 没有合法脱敏非空微博 Fixture，因而 Search 结果数组位置、二级评论返回 max_id path、Mapper 字段和真实兼容性均未验证；
- 没有 Weibo Capability/默认 Registry；前端/生产链不能把本 Change 当作“微博平台可运行”证据；
- 无法确认用户本地工作区状态，GitHub PR/Actions 只证明仓库远端集成状态。

# 兼容、依赖、Migration、部署与回滚

- 公共 Contract/API/Schema：无变化；
- Migration/数据库：无变化；
- 依赖/锁文件：无变化；
- 生产部署：未执行；
- 回滚：回滚微博 Operation/测试/文档差异即可，无数据迁移或数据回滚；共享文档中的并行 B站事实必须以回滚时的 main 为准，不能机械删除。

# Git

- 创建分支时基线 main：`d12bcfcb454609b37408f8ff98531d6fd2a4e125`
- 并行 B站 merge：`0e4a74674dc5027a9b65bddace49cb50974e4f7a`
- 开发分支：`feature/stage7-weibo-operation`，PR 合并后已自动删除
- PR：#40
- 最终 feature head：`91db8726781be58c04b71527ccf44c614d863eb7`
- merge commit / 合并后已验证 main：`5e35eeccd1e476dd0a57f482ff70d48dd44a8909`
- Change：done，归档于 `changes/archive/2026-08/`
- 生产部署：未执行
