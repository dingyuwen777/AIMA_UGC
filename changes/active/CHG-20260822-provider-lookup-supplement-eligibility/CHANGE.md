---
schema: rvc-change/v1
id: CHG-20260822-provider-lookup-supplement-eligibility
title: 内容补采身份与相关性资格收口
level: L3
status: ready_for_review
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
- [x] 最终业务 HEAD `74bc0f80c417fb6db879e1003a7c8bf5b9226c9f` 的相关 Unit/Contract/PostgreSQL Integration/Frontend Unit-E2E/12 个永久 CI 全部通过；
- [x] L3 Review A / Review B 无未解决严重/重要问题；
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
- 当前普通 Batch Supplement Runtime 只接受 typed lookup 与稳定 Content identity 可证明一致的目标；二者不同的 resolver/身份合并能力留给独立 Change；
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

真实 GitHub Runner Probe：Actions Run `32592521307`，使用 TikHub 正式 HTTPS Origin；API Key 通过一次性受控方式注入，明文未写入仓库、PR、Change 或日志。

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

首次发现共 12 次真实请求，计划费用 `0.030000 USD`。成功后 `tests/fixtures/imports/excel_provider_lookup_samples.json` 已收敛为上述五个平台各 1 条链接；长期 `scripts/dev/probe_excel_tikhub_supplement.py` 强制每个平台恰好一条样本，并设置 `max_requests=10`、计划费用上限 `0.10 USD`，因此后续完整五平台复核不再执行搜索/候选遍历。

# 最终永久 CI

业务实现最终 HEAD：

```text
74bc0f80c417fb6db879e1003a7c8bf5b9226c9f
```

该 HEAD 的 12 个永久 PR Workflow 全部成功：

- CI #2150 / Run `32607733180`；
- Stage 5A Provider Raw #1527 / Run `32607733159`；
- Stage 5B Collection Execution #1485 / Run `32607733163`；
- Stage 5C Provider Persistence #1482 / Run `32607733167`；
- Stage 5D Provider Dispatch #1542 / Run `32607733170`；
- Stage 6 Xiaohongshu Vertical Slice #148 / Run `32607733162`；
- Stage 1-7 Audit Correctness #1039 / Run `32607733161`；
- Stage 7 Keyword Packs #1760 / Run `32607733187`；
- Stage 7 Scheduler Runtime #2100 / Run `32607733154`；
- Stage 7 Provider Config Routing #1873 / Run `32607733173`；
- Stage 7 Plan Occurrence Run Snapshot #1758 / Run `32607733157`；
- Stage 8F Full-stack Acceptance #277 / Run `32607733165`。

总 CI 的 Stage 1 / Stage 2 / Stage 3A / Windows bootstrap 均成功；Stage 1 覆盖 generated Contract/client、Ruff、mypy、Unit/Contract/API、架构/Table Owner/Secret/Docs、Wheel、前端 lint/typecheck/unit/build/Playwright E2E。

# L3 两阶段 Review

## Review A：需求 / Contract / 数据语义

逐项核对本 Change、Blueprint 02/08、HTTP Contract、Excel identity、Collection target、TikHub Operation/Mapper、前端资格与展示：

- 修复 typed Provider lookup 与稳定 Content ID 不一致时可能“资格接口允许、Worker 实际用另一 ID”的超报；当前普通 Runtime 对不一致身份 fail closed；
- 将 Stage 8E 旧测试 seed 迁移为真实现代 Excel 入库事实，补 `content_external_ids.note_id`，不通过放宽生产资格迁就旧测试；
- 区分内部平台机器别名与真实外部短链域名，平台标识门禁继续禁止内部 `xhs`，仅允许真实外部域名 literal；
- 前端 E2E 从旧 `/contents` 存在性 Mock 迁移到正式 Batch Supplement eligibility Contract；
- 确认 Comment ID / Root ID 仍只来自 Provider 评论响应，Excel 不生成评论身份；
- 确认当前 irrelevant 保留审计但默认不展示、不进入普通付费补采；stale Analysis 不永久阻断。

Review A：无未解决 Serious / Important 问题。

## Review B：代码质量 / 安全 / 可维护性

- PR 最终 diff 不包含一次性密钥密文、临时 Runner workflow、诊断脚本或施工脚本；
- 未新增第三方依赖、数据库表或 Migration；
- OpenAPI 与 Orval generated client 无漂移；
- Secret 扫描、Docs、架构、Table Owner、mypy、Ruff、Wheel、前后端测试均通过；
- 固定真实 Probe 样本为五平台各 1 条，源 Excel SHA-256 可追溯；Probe 不做 Search/候选遍历，最大 10 请求、最大计划费用 0.10 USD；
- PR 无 inline review thread、无已提交 review 阻塞；
- 补采失败只向业务用户公开稳定业务状态，不泄露 Provider Secret 或 Raw 错误详情。

Review B：无未解决 Serious / Important 问题。

# 回滚

本 Change 无 Schema/Migration/依赖升级。若需要回滚，在正常 Git/PR 流程回退实现 PR 即可恢复原有资格与展示逻辑；数据库中既有 Content/Version/Analysis/来源审计数据无需迁移或删除。固定真实 Probe fixture 与调试脚本不参与生产运行。

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

实现 PR：#151 `收口内容补采身份与相关性资格`。业务实现 HEAD 已完成两阶段 Review 与永久 CI；本证据提交后需以新的最终 HEAD 再跑永久 CI，全部成功后转 Ready 并正常合并。
