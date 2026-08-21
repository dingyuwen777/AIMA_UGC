# TikHub 接口验证与选型台账

这篇文档回答：**同一个平台可能有 App/Web、V1/V2/V3 等多个 TikHub API family，AIMA_UGC 为什么选当前生产接口；备用接口什么时候可以启用。**

它不维护第二份 endpoint 代码。精确生产 URL、参数、分页和响应解析仍以当前 Operation/Transport、测试 Fixture 和 `docs/collection/` 为准。

## 1. 为什么要有“选型台账”

如果只在代码里把 endpoint 换掉，过几个月很难回答：

- 为什么当时选这个接口？
- 另一个接口是真的不可用，还是只是没验证？
- 两个接口的业务含义是否完全一样？
- 备用接口能不能自动 fallback？
- 换接口后 Mapper/分页/费用语义会不会变化？

所以当前做法是把“生产选择”和“验证证据”分开：

```text
生产 Operation
→ 当前唯一实际调用路径

脱敏 Fixture / 测试 / 受控 Probe
→ 证明这个路径当前满足业务语义

本附录
→ 解释为什么这样选、什么时候允许换
```

## 2. 当前固定原则

### 2.1 不自动跨 API family fallback

当前不做：

```text
App V2 失败
→ 自动试 Web V3
→ 再自动试 V1
```

原因不是“备用接口没价值”，而是这些接口可能在以下方面不同：

- 参数语义；
- 排序；
- 时间过滤；
- 分页状态；
- 返回字段；
- 计费；
- 风控/稳定性；
- 详情与评论完整度。

一个接口失败后静默切到另一个接口，会让一次 Provider Request 的语义变得无法审计。

### 2.2 备用接口必须显式启用

如果主接口长期不可用，可以通过独立变更切换，但至少要重新确认：

```text
业务输入等价吗？
输出能映射到同一个 Canonical 吗？
分页和停止条件等价吗？
费用事实怎么记录？
现有 Fixture/测试要怎么更新？
是否影响历史回放？
```

## 3. 五个平台当前生产边界

最新的人类可读入口：

| 平台 | 当前说明 |
| --- | --- |
| 小红书 | [`../collection/xiaohongshu.md`](../collection/xiaohongshu.md) |
| 抖音 | [`../collection/douyin.md`](../collection/douyin.md) |
| 微博 | [`../collection/weibo.md`](../collection/weibo.md) |
| B站 | [`../collection/bilibili.md`](../collection/bilibili.md) |
| 快手 | [`../collection/kuaishou.md`](../collection/kuaishou.md) |

这些平台文档比历史探测表更接近当前生产代码；如果内容冲突，以当前 Operation/Fixture/测试为准，并在同一任务修正文档。

## 4. 一个接口候选怎么从“能调用”变成“可用于生产”

只拿到 HTTP 200 不够。

一个候选至少要经过：

```text
1. 能完成目标业务动作
2. 参数与业务语义明确
3. 有界分页可以停止
4. 能取得稳定内容/评论身份
5. 能映射当前 Canonical
6. Raw 可以保存和回放
7. 错误能归类
8. 费用/计费事实可记录
9. 有脱敏 Fixture
10. 有 Operation / Mapper / Contract 测试
```

如果其中某项未知，它只能叫“候选”，不能写成生产能力。

## 5. A/B 验证怎么做

真正需要比较两个 API family 时，比较的不是“哪个返回字段更多”，而是同一业务问题：

```text
给定相同关键词/内容/评论目标
A 能否完成？
B 能否完成？
数据身份是否稳定？
分页是否可控？
Canonical 信息是否完整？
请求次数和费用如何？
失败后的恢复语义如何？
```

建议保存的验证摘要：

```text
平台：xhs
业务动作：keyword_search
候选：A / B
验证时间：带时区时间
输入摘要：脱敏业务参数
请求次数：有界数字
结果：pass / partial / fail
主要差异：分页、字段、费用、错误
决定：primary / explicit_backup / rejected
证据：Fixture / test / Change / Probe artifact
```

不要在台账里保存 Secret 或完整敏感 Raw。

## 6. 为什么历史探测记录不能永远当当前事实

第三方 API 会变。2026 年 8 月某次探测成功，只能证明“那次请求在当时成功”，不能永久证明现在仍可用。

当前事实优先级：

```text
生产 Operation + 当前测试/Fixture
→ 近期受控 Real Probe（确有必要时）
→ docs/collection 平台说明
→ 历史验证记录
```

所以本附录不继续累积几十页“请求/响应截图”。详细历史理由已经有 `changes/archive/`；真正需要重新验证时，新建 Change 并更新当前事实。

## 7. 费用和接口选择

Provider Request/Attempt 会记录：

- estimated/actual cost；
- currency；
- unit price snapshot；
- billing status；
- potential duplicate charge。

这些字段用于**执行审计**，不是预算门禁。

当前系统没有：

```text
Budget Account
Reservation Ledger
请求次数预算
金额预算
发送前 Cost Guard
```

不要因为某个候选接口更便宜，就在没有业务等价验证的情况下自动切换。

## 8. 什么时候需要真实 TikHub Probe

优先级应是：

```text
当前代码/Fixture/测试能回答
→ 不发真实请求

一手资料能回答
→ 不发真实请求

只有真实返回才能确认
→ 才做有界 Probe
```

Probe 需要：

- 明确目标；
- 最小请求量和分页上限；
- 使用正式 Adapter/Operation，而不是复制一套临时代码；
- 不进普通 CI；
- 不打印 Secret；
- 产出脱敏 Fixture/结论，否则验证不能长期复用。

## 9. 切换生产接口前的检查表

```text
[ ] 当前主接口的问题有可复现证据
[ ] 候选接口完成同一业务动作
[ ] 参数/分页语义已确认
[ ] Canonical 映射已确认
[ ] Raw/Replay 仍成立
[ ] Billing/错误分类已确认
[ ] 新 Fixture 已脱敏
[ ] Operation/Mapper/Contract 测试已更新
[ ] docs/collection 对应平台说明已更新
[ ] 如果行为/Contract 变化，Change/OpenSpec/Migration 已按规则处理
```

## 10. 深入阅读

- 采集长期原则：[`../blueprint/08-采集策略与平台能力.md`](../blueprint/08-采集策略与平台能力.md)
- TikHub Raw/Mapper 排障：[`TikHub真实响应结构.md`](TikHub真实响应结构.md)
- 具体平台：[`../collection/README.md`](../collection/README.md)
- Provider/Collection 当前实现：`backend/src/aima_ugc/modules/collection/README.md`
- 历史决策：`changes/archive/`
