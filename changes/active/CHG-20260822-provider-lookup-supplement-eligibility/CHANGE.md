---
schema: rvc-change/v1
id: CHG-20260822-provider-lookup-supplement-eligibility
title: 内容补采身份与相关性资格收口
level: L3
status: in_progress
owner: chatgpt
branch: feature/provider-lookup-supplement-eligibility
created: 2026-08-22
updated: 2026-08-23
depends_on: []
affected_areas:
  - contracts
  - ingestion
  - content
  - collection
  - frontend
  - reporting
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/providers/tikhub/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/bootstrap/
  - frontend/src/features/import-batches/
  - backend/src/aima_ugc/adapters/providers/imports_test/
  - tests/
  - docs/blueprint/
  - docs/appendix/
  - docs/collection/
contracts:
  - CanonicalContentV1.alternate_ids
  - CollectionEnrichmentTarget
  - CollectionBatchSupplementEligibilityResponse
  - ContentSupplementStatusResponse
data_changes: []
---

# 目标

在不删除审计事实、不伪造评论身份、不引入第二套 Content 表的前提下，收口 Excel → Content → TikHub 补采链的身份与资格语义：

1. AI Semantic Relevance 判定为 `irrelevant` 的 Content 继续保留 Content、Version、Analysis 和来源审计，但默认不进入声音广场，也不得成为普通 Batch Supplement 的付费补采目标；
2. Excel 对可确定的平台帖子 URL 解析原生 Content ID，并以 typed `alternate_ids` 明确 Provider lookup 类型；
3. 补采只对能证明具有当前 TikHub Operation 可用 lookup identity 的 Content 开放，不能把 `url_sha256:*`、任意文章编号或模糊 URL token 直接当 Provider ID；
4. 一级评论从 Content lookup identity 发起；Comment ID / Root Comment ID 必须来自 TikHub 评论响应，Excel 不生成评论身份；
5. B站明确区分 `av_id / bv_id`；微博常见 Base62 permalink 确定性转换为数字 status ID；快手真实 Detail/Comment 响应在保持原 Content 收敛的同时记录 Provider `photo_id`；
6. 人工最终 Excel 恢复 Content ID 展示，评论继续保留 Content/Comment/Root/Parent ID；
7. 声音广场详情公开最近一次补采业务状态，失败时明确“原始导入内容仍保留”，不把 Provider 名称或 Raw 错误直接暴露给普通用户。

# 可观察成功标准

- [x] 小红书 `/explore/{note_id}` / `/discovery/item/{note_id}` 映射为 `external_content_id={note_id}` 且记录 `alternate_ids.note_id`；
- [x] 抖音 `/video/{aweme_id}`、`/note/{aweme_id}`、实际 Excel 的 `/share/video/{aweme_id}` 与 `iesdouyin.com/share/video/{aweme_id}` 记录 `alternate_ids.aweme_id`；
- [x] 快手 `/short-video/{photo_id}` 与实际 Excel 的 `live.kuaishou.com/u/{user}/{photo_id}` 可解析 `photo_id`；
- [x] B站 `/video/BV...` 记录 `bv_id`，`/video/av...` 记录规范化 `av_id`，Operation 按 AV/BV 类型构造参数；
- [x] 微博常见 `weibo.com/{uid}/{base62_bid}` 本地确定性转换为数字 MID/status_id；`tv/show` 等不能直接用于评论的 URL 不冒充 status ID；
- [x] Excel 中“文章编号”存在时仍坚持平台 URL native ID 优先，文章编号仅保留为 `source_article_id`；
- [x] 只能用文章编号或 URL hash 构造数据库身份时仍允许导入/审计，但 Batch Supplement fail closed，不发 TikHub；
- [x] TikHub 原生采集产生的 Content 继续可正常 Detail / Comments / Replies；
- [x] 当前 Analysis identity 明确 `irrelevant` 的 Content 不进入 Batch Supplement；旧 Prompt/Taxonomy/Model 结果作为 stale，不永久阻断；
- [x] Voice Plaza 默认隐藏 irrelevant 的既有行为保持，按 Content UUID 读取详情的审计能力保持；
- [x] 前端通过专用 Batch Supplement eligibility API 读取真实平台目标数，不再查询 `relevance=irrelevant` 猜资格；
- [x] 首次 Batch Supplement 固定先 Detail；一级评论可选；二级回复依赖一级评论；本 Change 不实现 comment-only supplement；
- [x] Content Detail 可投影最近一次 Batch Supplement 状态；失败文案为“内容补充失败，暂时无法获取完整详情与评论。已保留原始导入内容，可在采集中心查看失败原因并重新发起补充。”；
- [x] Excel `内容` Sheet 人工默认视图恢复 `内容ID`，评论视图保留 `内容ID/评论ID/根评论ID/父评论ID`；
- [x] 不新增第三方依赖、不新增表、不新增 Migration；
- [x] Blueprint 02/08、统一入库 Appendix、TikHub 字段映射 Appendix、Stage8F 能力矩阵、Collection README 与实现同步；
- [x] 使用用户上传 `惠科data(0817-0819).xlsx` 的真实链接完成五平台 TikHub Detail + 一级评论真实 Probe；
- [x] 将真实 Probe 成功链接收敛为五个平台各 1 条固定样本，后续完整真实验证最多 10 次请求，不再搜索或候选遍历；
- [ ] 最新最终 PR HEAD 的相关 Unit/Contract/PostgreSQL Integration/Frontend Unit-E2E/永久 CI 全部通过；
- [ ] L3 两阶段 Review 无未解决严重/重要问题；
- [ ] 实现 PR #151 正常合并到 `main`，随后独立归档 Change。

# 已确认关键决策

用户确认：

- 从平台 URL 提取 native Content ID 是正确方向，例如小红书 `/explore/6a81...` → `note_id=6a81...`；
- Content lookup identity 同时可作为 Detail 和一级评论入口；Comment ID / Root Comment ID 来自 TikHub 评论响应，Excel 不生成评论身份；
- AI `irrelevant` 数据保留数据库审计，但不应因为“被保留”就参与默认展示或继续产生普通补采费用；
- 第一次 Batch Supplement 固定先补 Detail，评论/二级回复按现有选项控制；Comment-only 刷新如以后需要，建立独立 Change；
- 真实验证不要每次从头搜索/遍历多个链接。首次找到五个平台有效链接后，仓库只保留各平台一条固定有效样本，后续低成本复核直接使用固定样本。

# L3 方案

采用：稳定主身份不变，复用 `CanonicalContentV1.alternate_ids → content_external_ids` 保存 typed Provider lookup identity；标准 URL 本地解析，无法证明的 lookup fail closed；不新增 Provider Lookup 表，不在普通 Import 中调用付费 resolver。

拒绝：

- 无条件把 `external_content_id` 当 TikHub lookup ID；
- 普通 Import 自动联网解析所有短链并隐式合并历史 Content。

# 数据与兼容边界

```text
Content 稳定身份
(platform, external_content_id)

Provider lookup identity
CanonicalContentV1.alternate_ids
→ content_external_ids(content_id, id_type, external_id)

Comment 稳定身份
(content_id, external_comment_id)
```

- 外部 ID 始终按字符串处理；
- Provider Raw 与真实 Fixture 不因本 Change 改写；
- 新 Excel 标准 URL 显式写 typed alternate ID；
- 旧 Excel 数据无可靠 lookup identity 时不猜测；
- 不自动把两个已存在 Content 合并；
- 快手真实 Provider `photo_id` 可作为 alternate ID 保存，但 Detail/Comment 入库仍必须收敛到原目标 Content；
- 不新增 Schema/Migration，回滚为代码/Contract/前端/文档回滚。

# 用户上传 Excel 事实与真实验证

源文件：`惠科data(0817-0819).xlsx`

SHA-256：

```text
8199f1b025a556998c8daa3c8b087f43494a1b84b13d932c1b3fb392f61ef37b
```

该文件真实链接形态包含：

- 小红书：`/explore/{note_id}`、`/discovery/item/{note_id}`；
- 抖音：主要为 `douyin.com/share/video/{aweme_id}`，并存在 `iesdouyin.com/share/video/{aweme_id}`；
- 微博：主要为 `weibo.com/{uid}/{base62_bid}`；
- B站：视频 `/video/av...`，同时还有动态/专栏等非当前视频补采主链内容；
- 快手：`/short-video/{photo_id}` 与 `live.kuaishou.com/u/{user}/{photo_id}`。

真实 GitHub Runner Probe：Actions Run `32592521307`，使用 `https://api.tikhub.io`，API Key 通过一次性 RSA-OAEP 加密握手注入；明文未写入仓库、PR、Change 或日志。

验证链：

```text
用户上传 Excel 的公开帖子 URL
→ 生产 Excel Converter / identity parser
→ typed Provider lookup identity
→ 生产 TikHub Detail Operation + Transport + Extractor + Mapper
→ 生产 TikHub Comments Operation + Transport + Extractor + Mapper
→ 验证真实 Provider Comment ID
```

结果：

| 平台 | Excel 行 | Detail | 一级评论 | 首次发现阶段跳过失效候选 |
| --- | ---: | --- | --- | ---: |
| xiaohongshu | 3 | ok | ok | 0 |
| douyin | 10 | ok | ok | 0 |
| weibo | 14 | ok | ok | 0 |
| bilibili | 1770 | ok | ok | 0 |
| kuaishou | 101 | ok | ok | 2 |

首次发现共 12 次真实请求，计划费用 `0.030000 USD`。成功后 `tests/fixtures/imports/excel_provider_lookup_samples.json` 已收敛为上述五个平台各 1 条链接；长期 `scripts/dev/probe_excel_tikhub_supplement.py` 强制每个平台恰好一条样本，并设置 `max_requests=10`，因此后续完整五平台复核不再执行搜索/候选遍历。

# 实施与验证计划

1. Red 已通过永久 CI 观察到 typed lookup、B站 AV/BV、补采资格等预期失败；
2. Green 已完成 Excel identity、Batch target reader、TikHub Mapper/Operation、eligibility API、前端资格与失败状态展示、人工 Excel 身份列；
3. 已完成用户上传 Excel 的五平台真实 Provider Probe，并将样本收敛为固定 5 条；
4. 删除一次性密钥密文、临时 Runner/诊断 workflow 与施工脚本；
5. 运行最终 HEAD 的 Unit/Contract/API/PostgreSQL/Frontend/Stage 8F/全部永久 CI；
6. Review A：需求/Contract/文档/数据语义；
7. Review B：代码质量、身份收敛、费用/Secret、测试覆盖；
8. 全绿后转 Ready 并合并 PR #151；
9. 从新 `main` 创建独立归档 PR，将本 Change 标记 `done` 并移入 Archive。

# 文档同步

本 Change 同步：

- `docs/blueprint/02-采集系统与数据标准化.md`
- `docs/blueprint/08-采集策略与平台能力.md`
- `docs/appendix/数据入口与统一入库实现.md`
- `docs/appendix/TikHub五平台真实响应与字段映射.md`
- `docs/appendix/Stage8F前后端能力矩阵与真实验收.md`
- `docs/collection/README.md`
- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`

# Git 状态

开始 `main`：

```text
1bc2f3b2ad34b7e5211d0816061d57e42925e91f
```

实施分支：

```text
feature/provider-lookup-supplement-eligibility
```

实现 PR：#151 `收口内容补采身份与相关性资格`，当前保持 Draft，待最终 HEAD 永久 CI 与两阶段 Review 完成后转 Ready。
