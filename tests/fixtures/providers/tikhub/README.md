# TikHub 真实结构 Fixture

本目录用于固定 TikHub 当前真实响应的**结构证据**，供 Operation、分页、Mapper、Canonical 和兼容性测试使用。它不是业务数据样本库，也不保存 API Key 或可用于重新识别真实账号/内容的原值。

## 证据来源

2026-08-15 至 2026-08-16，在 GitHub-hosted Ubuntu Runner 上显式访问 `https://api.tikhub.io`，关键词使用“爱玛”，按最小结构验证原则执行：

- Search：每个平台最多一页；
- Detail：从 Search 返回项中选一条可用内容，最多请求一次详情；小红书分别验证图文与视频详情；
- Comments：每个平台最多一页一级评论；
- Sub-comments / Replies：只为验证结构选一个有回复的根评论，最多一页；
- 不做全量翻页，不追完整历史，不把真实响应直接提交到仓库。

对应 TikHub 业务 endpoint 共 21 个，均先通过官方 `get_endpoint_info` 核验 endpoint 与精确基础单价；真实业务请求全部受显式请求数/费用上限约束，不存在隐藏网络重试。

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
| 快手 | 非空 | 非空 | 非空 | endpoint 返回成功，但本次 `subComments=[]` |

因此快手 `sub_comments` 当前只证明 endpoint、响应 envelope 和空页语义，**没有非空回复项结构证据**；Capability 不得提前宣称已具备完整二级评论归一化能力。

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

禁止从微博 `rootid`、抖音其他回复字段、B站/快手无关 ID 猜测原内容或直接父评论关系。原内容 ID 缺失时由已知请求上下文显式提供 `external_content_id`。

## 维护要求

Provider endpoint/version 或响应字段发生变化时：

1. 先执行显式、受限的真实 Probe；
2. 在 Runner 内完成 Secret/PII 脱敏；
3. 用新的真实结构更新 Fixture；
4. 先观察 Operation/Mapper 测试因真实变化失败；
5. 再修改生产 Operation/Mapper/Capability；
6. 通过 Canonical、Secret Scan 与相关 Stage 回归后才能声明兼容。

不得根据 TikHub 文档示例、旧聊天或人工猜测直接制造“真实 Fixture”。
