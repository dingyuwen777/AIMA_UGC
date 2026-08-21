# TikHub 真实响应结构

这篇文档不是 TikHub API 的第二份官方文档。它的作用是：**当生产 Mapper 或测试 Fixture 对不上字段时，告诉开发者应该沿什么路径确认真实返回。**

当前正式支持的小红书、抖音、微博、B站、快手都通过 Provider Adapter/Operation 进入同一条主链：

```text
TikHub HTTP
→ 原始响应 Raw Artifact
→ 平台 Operation / Extractor
→ Mapper
→ Canonical
→ Ingestion
```

## 1. 为什么不能把 TikHub JSON 当成系统业务结构

第三方接口字段会变化，不同平台也不会使用同一套字段。

例如同一个“作者昵称”，真实 Provider 字段可能出现在完全不同的位置。AIMA_UGC 不让这些私有路径扩散到 API、数据库和前端，而是在 Mapper 前消化掉。

所以排查字段问题时要区分两件事：

```text
Provider 返回了什么？        → 看 Raw / Fixture / Operation
系统最后需要什么？           → 看 Canonical Contract
中间怎么对应？               → 看 Mapper
```

## 2. 五个平台的人类入口

当前平台级说明集中在：

- [`../collection/xiaohongshu.md`](../collection/xiaohongshu.md)
- [`../collection/douyin.md`](../collection/douyin.md)
- [`../collection/weibo.md`](../collection/weibo.md)
- [`../collection/bilibili.md`](../collection/bilibili.md)
- [`../collection/kuaishou.md`](../collection/kuaishou.md)

这些文档记录当前生产 Operation、主要业务参数和已验证边界。精确字段仍以当前代码和脱敏 Fixture 为准。

## 3. 真实响应通常分成哪几类

不管平台字段叫什么，业务上主要需要确认下面几类信息。

### 3.1 搜索/发现列表

主要回答：

```text
返回了哪些内容？
内容的稳定外部 ID 是什么？
有没有下一页？
下一页需要什么 cursor/page/search_id？
搜索卡片已经带了哪些指标？
```

搜索结果只负责“发现”。如果列表没有足够字段，后续 Detail Operation 会补全；不要在 Mapper 里凭空猜字段。

### 3.2 内容详情

主要确认：

- 内容稳定 ID；
- 内容类型；
- 标题/正文；
- 作者公开身份；
- 发布时间；
- 当前互动指标；
- URL/分享链接；
- 媒体、话题、@、位置等可观察子实体；
- Provider 明确给出的评论总量。

### 3.3 一级评论

主要确认：

- 评论稳定 ID；
- 所属内容 ID；
- 评论作者；
- 文本；
- 发布时间；
- 点赞数；
- 回复数；
- 下一页游标；
- 是否还有更多评论。

### 3.4 二级回复

除了上面的信息，还要确认：

- root comment ID；
- parent comment ID；
- 当前回复是否由内容作者发出；
- thread 的下一页状态。

## 4. Mapper 为什么必须基于真实 Fixture

一个典型错误是：开发者看到第三方文档写了某个字段，就直接写代码，但真实返回在当前 API family 中位置不同、类型不同或有空值。

正确流程：

```text
1. 找现有脱敏 Fixture
2. 找生产 Operation/Extractor
3. 找 Mapper
4. 找 Mapper/Contract 测试
5. 只有以上仍不能确认时，才做受控 Real Probe
```

普通 CI 不应该发真实付费请求。

## 5. Raw Artifact 为什么不能被“整理后再保存”

Raw 的意义是保留外部证据。如果先把第三方 JSON 改成自己喜欢的格式再保存，后面字段映射出问题时就无法回答：

> Provider 当时到底返回了什么？

因此主链是：

```text
先持久化不可变 Raw
→ 校验 Raw 完整性
→ 再 Extract / Mapper
```

回放旧 Raw 时也不再次调用 Provider。

## 6. 时间字段特别容易出错

第三方可能返回：

- Unix 秒；
- Unix 毫秒；
- ISO 时间；
- 没有时区的文本；
- 只有日期；
- 根本没有可靠发布时间。

规则是：**没有真实证据就不猜。**

Canonical/数据库时间必须经过 Mapper 明确解释后再写入；不能因为“这个数字看起来像时间”就乘/除 1000。

## 7. 数字指标也要区分“缺失”和“0”

例如 Provider 没返回 `comment_count`，不等于明确返回了 0。

AIMA_UGC 使用稀疏观察和字段 freshness，目的就是避免一次字段缺失把旧的已知值错误清零。

## 8. 评论完整度不是一个布尔值

抓了 50 条评论不代表“评论已抓全”。当前 Content/Collection 会保存 Coverage：

```text
当前拿了多少
Provider 报告总数是多少
是否完整
为什么停止
root thread 是否完整
```

Provider 的分页字段只负责告诉 Operation “还有没有下一页”，最终 Coverage 由业务边界统一保存。

## 9. Real Probe 的使用边界

只有以下情况才值得真实请求：

- 现有 Fixture 与生产行为冲突；
- Provider 官方/一手资料无法确认字段；
- API family 是否仍可用必须重新验证；
- 新平台/新 Operation 要建立第一份真实 Fixture。

Real Probe 必须：

- 人工显式触发；
- 有请求/分页上限；
- 不进入普通 CI；
- 不打印 Secret；
- 不把未脱敏 Raw 提交 Git；
- 请求成功后仍要落 Fixture/测试，不能把“我刚才调通了”当长期事实。

接口选择与备用规则见 [`TikHub接口验证与选型台账.md`](TikHub接口验证与选型台账.md)。

## 10. 调试一个 Mapper 的最短路径

假设“小红书评论昵称为空”：

```text
1. 打开 docs/collection/xiaohongshu.md 找当前评论 Operation
2. 找该 Operation 的生产实现
3. 找对应脱敏 Fixture
4. 确认真实昵称字段是否存在
5. 找 Mapper 当前读取路径
6. 跑 Mapper/Contract 测试
7. 如果 Fixture 本身过期，再做一次受控真实验证
```

不要先改 Canonical，也不要让前端直接适配 TikHub 字段。

## 11. 精确事实源

优先级：

```text
当前生产 Operation / Mapper / Contract / 脱敏 Fixture / 测试
→ 当前 docs/collection 平台说明
→ 本附录的人类解释
→ 历史 Change / 旧探测记录
```

本附录只帮助人定位，不复制完整 Provider JSON Schema。
