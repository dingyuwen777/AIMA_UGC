---
schema: rvc-change/v1
id: CHG-20260822-provider-lookup-supplement-eligibility
title: 内容补采身份与相关性资格收口
level: L3
status: approved
owner: chatgpt
branch: feature/provider-lookup-supplement-eligibility
created: 2026-08-22
updated: 2026-08-22
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
data_changes: []
---

# 目标

在不删除审计事实、不伪造评论身份、不引入第二套 Content 表的前提下，收口 Excel → Content → TikHub 补采链的身份与资格语义：

1. AI Semantic Relevance 判定为 `irrelevant` 的 Content 继续保留 Content、Version、Analysis 和来源审计，但默认不进入声音广场，也不得成为普通 Batch Supplement 的付费补采目标；
2. Excel 对可确定的官方长链接解析平台原生 Content ID，并以 typed `alternate_ids` 明确其 Provider lookup 类型；
3. 补采只对能证明具有当前 TikHub Operation 可用 lookup identity 的 Content 开放，不能把 `url_sha256:*`、任意文章编号或模糊 URL token 直接当 Provider ID；
4. 一级评论仍从 Content lookup identity 发起；Comment ID / Root Comment ID 必须来自 TikHub 评论响应，Excel 不生成评论身份；
5. B站明确区分 `av_id` / `bv_id`；微博只把有证据的 status identity 当 lookup ID；
6. 人工最终 Excel 恢复 Content ID 展示，评论继续保留 Comment/Root/Parent ID。

# 可观察成功标准

- [ ] 小红书官方长链接 `/explore/{note_id}` / `/discovery/item/{note_id}` 映射为 `external_content_id={note_id}` 且记录 `alternate_ids.note_id`；
- [ ] 抖音官方长链接 `/video/{aweme_id}` / `/note/{aweme_id}` 记录 `alternate_ids.aweme_id`；
- [ ] 快手官方长链接 `/short-video/{photo_id}` 记录 `alternate_ids.photo_id`；
- [ ] B站 `/video/BV...` 记录 `bv_id`，`/video/av...` 记录规范化 `av_id`，补采 Operation 按 ID 类型选择参数；
- [ ] 微博仅对当前可证明能直接用于 TikHub status detail/comments 的 URL 身份记录 `status_id`，不把不确定 token 标成可补采；
- [ ] Excel 只能用文章编号或 URL hash 构造稳定数据库身份时仍允许导入/审计，但 Batch Supplement 对该 Content fail closed，不发 TikHub；
- [ ] TikHub 原生采集产生的 Content 继续可正常 Detail / Comments / Replies；
- [ ] AI 当前结果为 `irrelevant` 的 Content 不进入 Batch Supplement target；未分析、stale 或 relevant 的资格按当前业务规则保持；
- [ ] Voice Plaza 默认隐藏 irrelevant 的既有行为保持；直接按 Content UUID 读取详情的审计能力保持；
- [ ] 前端不再通过第二次 `relevance=irrelevant` 探测把无关内容视为补采资格；
- [ ] Excel `内容` Sheet 人工默认视图恢复 `内容ID`，评论视图保留 `内容ID/评论ID/根评论ID/父评论ID`；
- [ ] 不新增依赖；除非实现证据证明必要，不新增表或 Migration；
- [ ] Blueprint 02/08、统一入库 Appendix、TikHub 字段映射 Appendix、Stage8F 能力矩阵、Collection README 与最终代码一致；
- [ ] 相关 Unit/Contract/PostgreSQL Integration/Frontend Unit-E2E/永久 CI 全部通过；
- [ ] L3 两阶段 Review 无未解决严重/重要问题；
- [ ] 实现 PR 正常合并到 `main`，随后独立归档 Change。

# 范围

## 修改

- Excel 平台 URL → 稳定 Content identity / typed Provider lookup identity；
- Batch Supplement target eligibility；
- TikHub Detail/Comments 的 lookup ID 选择，重点修正 B站 AV/BV；
- 前端 Batch Supplement 平台资格探测；
- `imports_test` 最终 Excel 身份列；
- 相关测试与正式文档。

## 非目标

- 不让 Excel 生成或猜测 Comment ID；
- 不改变 TikHub 评论 Mapper 当前 `external_comment_id/root_comment_id/parent_comment_id` 来源；
- 不在普通 Excel Import 中调用付费 TikHub Resolver；
- 本 Change 不实现短链接联网解析后再自动合并历史 `url_sha256:*` Content；
- 不重做 Content UUID、Version/Metric、Candidate、Raw/Artifact 或 Analysis 表；
- 不删除 irrelevant Content 或 Analysis 审计事实；
- 不改变 AI Prompt / taxonomy / LLM 费用策略；
- 不新增自动 API family fallback。

# 必须保持不变

- PostgreSQL 是业务事实库；
- Content 稳定业务身份仍以 `(platform, external_content_id)` 收敛；
- Comment 稳定身份仍以 `(content_id, external_comment_id)` 收敛；
- Provider Raw 与真实 Fixture 不因本 Change 改写；
- Mapper 只翻译事实，不查数据库、不发 HTTP；
- HTTP/Worker/Scheduler/Provider Request/Attempt/Raw 审计边界保持；
- 一个 Attempt 最多一次真实 Provider HTTP 发送；
- 普通 CI 不调用真实付费 TikHub。

# 已确认关键决策

用户已确认：

- 从标准平台 URL 提取 native Content ID 是正确方向，例如小红书 `/explore/6a81...` → `note_id=6a81...`；
- 该 Content lookup identity 可用于 TikHub Detail，也用于一级评论列表；
- Comment ID / Root Comment ID 来自 TikHub 评论响应，Excel 没有评论数据，不应生成评论身份；
- AI `irrelevant` 数据要留在数据库审计，但不应因为“被保留”就继续参与默认展示或付费补采；
- 方案应同步写入正式文档并最终合并远程 `main`。

# L3 方案比较

## 方案 A：继续把 `external_content_id` 无条件当 TikHub lookup ID

优点：改动最少。

缺点：`url_sha256:*`、来源文章编号、B站 BV/AV 和微博多 ID 语义会继续混淆；可能向 TikHub 发送不可用 ID。

结论：拒绝。

## 方案 B：稳定主身份不变，复用 `alternate_ids/content_external_ids` 保存 typed lookup identity

优点：不新增平行 Content 表；标准长链接可在本地确定；B站能保留 AV/BV 类型；评论身份继续来自 Provider；对无法证明的 lookup identity fail closed。

代价：需要同步 Excel identity、target reader、TikHub runtime、前端资格和测试。

结论：采用。

## 方案 C：新增独立 Provider Lookup 表并在补采时自动联网解析所有 URL

优点：未来可表达 resolver 生命周期。

缺点：当前需求不需要新表；普通导入会耦合外部付费网络；短链接解析后的原生 ID 与既有 `url_sha256:*` Content 还涉及身份合并/迁移问题。

结论：本 Change 不采用；未来若确需自动 resolver，建立独立 Change。

# 兼容与数据边界

本 Change 优先复用现有：

```text
CanonicalContentV1.alternate_ids
→ content_external_ids(content_id, id_type, external_id)
```

因此预计无需 Schema Migration。

旧数据兼容原则：

- TikHub 原生 Content 的 `external_content_id` 本身就是 Provider 原生 ID，继续允许按平台安全解释；
- 新 Excel 标准长链接会显式写 typed alternate ID；
- 旧 Excel 数据如果没有可证明 lookup identity，不通过猜测或 `url_sha256` 反推，补采 fail closed；
- 不自动把两个已存在 Content 合并成一条。

# 实施计划

1. Red：为 Excel typed identity、B站 AV/BV、不可补采 fallback、AI irrelevant target exclusion 和前端资格增加失败测试；
2. Green：最小修改 Excel identity 解析和 typed alternate IDs；
3. Green：让 Batch target reader 读取当前 AI relevance 与可用 lookup identity，irrelevant / unresolved fail closed；
4. Green：TikHub Detail/Comments 按 typed lookup identity 构造正确参数；Comment/Reply ID 链保持 Provider 响应驱动；
5. Green：前端移除 irrelevant 二次资格探测；
6. Green：人工 Excel 默认列恢复内容/评论身份；
7. Refactor：只在测试通过后消除必要重复，不扩大架构；
8. 同步 Blueprint / Appendix / Collection README；
9. 运行目标测试、相关 PostgreSQL/Frontend/full-stack 与永久 CI；
10. L3 两阶段 Review，Ready 后合并；
11. 从新 `main` 独立归档 Change。

# 验证计划

至少包含：

```text
uv run pytest <本 Change 目标 unit tests> -q
uv run pytest <本 Change PostgreSQL collection/content integration tests> -q
uv run ruff format --check backend tests scripts migrations
uv run ruff check backend tests scripts migrations
uv run mypy backend/src
uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/api -q
uv run pytest tests/integration/collection -q
uv run pytest tests/integration/content -q
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

若 Stage 8F 受补采资格/Excel 输出影响，永久 Stage 8F 必须继续通过。最终以最新 PR HEAD 的永久 GitHub Actions 结果为合并门禁。

# 文档影响

计划同步：

- `docs/blueprint/02-采集系统与数据标准化.md`
- `docs/blueprint/08-采集策略与平台能力.md`
- `docs/appendix/数据入口与统一入库实现.md`
- `docs/appendix/TikHub五平台真实响应与字段映射.md`
- `docs/appendix/Stage8F前后端能力矩阵与真实验收.md`
- `docs/collection/README.md`
- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`（若人工 Excel 默认列说明受影响）

# Git 状态

开始 `main`：

```text
1bc2f3b2ad34b7e5211d0816061d57e42925e91f
```

实施分支：

```text
feature/provider-lookup-supplement-eligibility
```

当前尚未创建实现 PR；编码、验证、Review、合并和归档状态必须随实际执行更新。
