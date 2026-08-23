# TikHub 真实结构 Fixture

本目录用于固定 TikHub 当前真实响应的**结构证据**，供 Operation、分页、Mapper、Canonical 和兼容性测试使用。它不是业务数据样本库，也不保存 API Key 或可用于重新识别真实账号/内容的原值。

人类可读的五平台查询附录见 [`docs/appendix/02_TikHub五平台真实响应与字段映射.md`](../../../../docs/appendix/02_TikHub五平台真实响应与字段映射.md)。多 API family 的验证与备用判定见 [`docs/appendix/03_TikHub多接口验证与备用策略.md`](../../../../docs/appendix/03_TikHub多接口验证与备用策略.md)。

## 证据来源

2026-08-15 至 2026-08-16，在 GitHub-hosted Ubuntu Runner 上显式访问 `https://api.tikhub.io`，关键词使用“爱玛”，按最小结构验证原则执行：

- Search：每个平台最多一页；
- Detail：从 Search 返回项中选一条可用内容，最多请求一次详情；小红书分别验证图文与视频详情；
- Comments：每个平台最多一页一级评论；
- Sub-comments / Replies：只为验证结构选一个有回复的根评论，最多一页；
- 不做全量翻页，不追完整历史，不把未经脱敏的真实响应提交到仓库。

首轮对应 TikHub 业务 endpoint 共 21 个，均先通过官方 `get_endpoint_info` 核验 endpoint 与精确基础单价；真实业务请求全部受显式请求数/费用上限约束，不存在隐藏网络重试。

2026-08-16 对快手评论链额外执行同样本 Web/App A/B：同一个 Search 命中的真实作品、同一个具有 `displaySubCommentCount/subCommentCount` 正向回复证据的根评论分别请求 Web/App 一级和二级评论。两套二级接口均返回 HTTP 200 且 `data.subComments[]` 非空，因此早先一次快手 Web 空页只说明当时样本没有取得回复，不能解释为 TikHub 不支持快手二级评论。

同次 A/B 后用户批准把快手一级、二级正式主 Operation 切换到 App；Web 结构证据继续保留为 `verified_backup`，不形成运行时自动 fallback。App 一级/二级 endpoint-info 单价均已进入正式版本化 Pricing。

## 脱敏规则

提交仓库前只保留 Mapper/分页需要的结构和少量代表字段：

- API Key、Authorization、Cookie、Token、签名等 Secret 不进入 Fixture；
- 用户名、正文、标题、简介、地区等直接文本使用人工脱敏值；
- URL 改为 `example.invalid`；
- 字符串 ID 使用稳定测试 ID；
- 数值型 ID 使用测试整数，保持“Provider 原字段是数字”的类型事实；
- 数值指标、布尔值、容器层级、字段名和分页结构按测试需要保留；
- 大数组裁剪为最少代表项。

Fixture 只证明其保留的字段与层级真实存在，不代表 Provider 不会返回其他字段。

## 已证明结构

| 平台 | Search | Detail | 一级评论 | 二级评论/回复 |
|---|---|---|---|---|
| 小红书 | 非空 | 图文、视频非空 | 非空 | 非空 |
| 抖音 | 非空 | 非空 | 非空 | 非空 |
| 微博 | 非空 | 非空 | 非空 | 非空 |
| B站 | 非空 | 非空 | 非空 | 非空 |
| 快手 | 非空 | 非空 | **Web 与 App 同样本均非空** | **Web 与 App 同样本均非空** |

快手现有 `comments_page1.sanitized.json` / `sub_comments_page1.sanitized.json` 的来源事实仍按生成它们时的 Web 响应保留，不能因为生产主链后来切到 App 就篡改 Fixture provenance。生产主链现在使用 App；Web Fixture 继续证明备用 family 的兼容结构。App 同样本 A/B 证据证明主链可用，但若未来需要把新的 App 原始结构提交成独立 Fixture，仍必须按真实来源重新脱敏并明确 provenance，不能复制 Web Fixture 冒充 App。

## 统一数据结构结论

真实响应目前可以落入既有 Canonical V1，无需新增 Provider 私有公共字段：

```text
TikHub Raw
→ 平台 Operation extractor
→ 平台 Mapper
→ CanonicalContentV1 / CanonicalCommentV1
→ Ingestion Service
```

评论树统一规则：

```text
一级评论:
root_comment_id = external_comment_id
parent_comment_id = null

二级/更深回复:
root_comment_id = 所属一级评论 ID
parent_comment_id = Provider 明确给出的直接父评论 ID；没有明确字段时保持 null
```

禁止从微博 `rootid`、抖音其他回复字段、B站/快手无关 ID 猜测原内容或直接父评论关系。快手 Web 二级响应虽然存在 `reply_to`，当前证据不足以证明它一定是另一个评论 ID，因此不把它猜成 `parent_comment_id`。原内容 ID 缺失时由已知请求上下文显式提供 `external_content_id`。

## 维护要求

Provider endpoint/version 或响应字段发生变化时：

1. 先执行显式、受限的真实 Probe；
2. 在 Runner 内完成 Secret/PII 脱敏；
3. 用新的真实结构更新 Fixture；
4. 先观察 Operation/Mapper 测试因真实变化失败；
5. 再修改生产 Operation/Mapper/Capability；
6. 通过 Canonical、Secret Scan 与相关 Stage 回归后才能声明兼容。

同一平台出现新的 App/Web/V1/V2/V3 候选时，还必须按 Blueprint 11 记录同关键词/同内容的结果数量、稳定 ID 重合、分页/排序语义与 endpoint-level 价格；未真实 A/B 的候选保持 `candidate_pending_probe`。

不得根据 TikHub 文档示例、旧聊天或人工猜测直接制造“真实 Fixture”。
