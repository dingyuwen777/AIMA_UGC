# TikHub 多接口验证与备用策略

本文只维护：

> **同一平台存在 App/Web/V1/V2/V3 等多个 API family 时，怎样验证它们、怎样定义候选状态、什么条件下允许切换生产主链。**

当前到底选了哪个 Endpoint、历史 Probe 返回了什么、当时价格是多少，统一由证据台账维护：

- [docs/appendix/04_TikHub接口选型与真实验证台账.md](04_TikHub接口选型与真实验证台账.md)

真实字段和 Mapper 路径统一看：

- [docs/appendix/02_TikHub五平台真实响应与字段映射.md](02_TikHub五平台真实响应与字段映射.md)

五个平台当前代码导航看：

- [docs/collection/README.md](../collection/README.md)

本文不再复制当前平台 Endpoint/价格矩阵。

## 1. 接口名相似不等于业务等价

TikHub 中可能同时存在：

~~~text
App
Web
V1
V2
V3
~~~

即使名字都叫 Search / Detail / Comments，也可能不同：

- 内容集合；
- 排序；
- 时间筛选；
- 分页；
- ID 类型；
- 评论层级；
- 字段完整度；
- 限流；
- 单次价格；
- 风控与稳定性。

所以不能因为“新版本号更大”或“单页看起来一样”就替换生产主链。

## 2. 三种状态

### production

当前正式 Collection/补采会使用的接口。

要求代码、Capability、Mapper、Fixture、测试和当前运维事实已经接线。

### verified_candidate

已经有足够真实证据表明它在某个明确 Operation 上可作为候选，但**不会自动进入生产 fallback**。

候选只能说明：

> 在已验证范围内值得继续比较或可以人工切换评估。

不能说明所有参数、所有分页、所有内容类型都等价。

### unverified / rejected

证据不足，或已经确认不满足当前业务语义。

这类接口不能因为生产接口暂时失败就临时接入。

## 3. 为什么当前不做自动 fallback

如果主接口失败后系统自动切另一个 family，需要同时证明：

- Request 业务语义等价；
- Pagination 可以安全续接；
- Mapper 能稳定解释两种结构；
- Content identity 不会漂移；
- Capability 对用户没有说谎；
- Pricing / 限流 / 费用风险可控；
- 重试不会造成重复计费或重复写入；
- 日志能明确说明真正使用了哪个 Operation。

这些条件缺一项，自动 fallback 可能把“可见失败”变成“静默写错数据”。

因此候选默认只用于显式验证或正式批准后的切换，不形成隐藏自动降级链。

## 4. A/B 验证先固定业务 Operation

比较必须是同一个业务目标，例如：

~~~text
平台 X 的关键词搜索
App Search vs Web Search
~~~

不能拿：

~~~text
Search
vs
Trending
~~~

然后因为都有帖子列表就宣布等价。

开始前至少固定：

- 平台；
- Operation；
- 关键词/目标 ID；
- 排序；
- 时间条件；
- 内容类型；
- 页数/停止条件；
- 运行时间；
- 当前 Provider Config；
- 候选 Endpoint；
- 需要对比的费用/限流事实。

## 5. 不只比较“有没有返回数据”

至少比较：

### 内容集合

- 总数；
- 稳定内容 ID；
- 交集/差集；
- 重复；
- 排序差异。

### 分页

- 首游标；
- 下一页游标；
- 游标是否稳定；
- 是否重复/漏页；
- 是否有最大页数或奇怪终止条件。

### 字段

- 内容身份；
- 作者身份；
- 时间；
-标题/正文；
-互动指标；
-媒体；
-评论 identity；
-二级回复 parent/root identity。

### 业务能力

- 原生时间筛选是否真的存在；
- 排序是否支持；
- 内容类型是否支持；
- 评论是否有可安全停止的时间/排序语义；
- Detail 是否补足 Search 缺失字段。

### 成本和稳定性

- 当前官方/Provider 定价；
- 限流；
- 超时；
- 错误码；
- 实际请求次数；
- 重试是否改变费用。

价格与限流必须记录核验日期，长期结果进入 [docs/appendix/04_TikHub接口选型与真实验证台账.md](04_TikHub接口选型与真实验证台账.md)，不留在方法文档。

## 6. 单页高度相似仍然不够

只比较第一页，最多说明：

> 在这一组输入、这一页数据、这次时间窗口里结果近似。

它不能证明：

- 下一页也一致；
- 深分页不会漏；
- 新旧内容排序一致；
- 时间筛选边界一致；
- 所有内容类型一致；
- 后续字段不会漂移。

需要切生产主链时，应按实际风险继续扩大验证到分页、字段、失败边界和稳定 identity。

## 7. Fixture 与 Probe 的职责

真实 Probe 用来确认外部事实。

Sanitized Fixture 用来把已确认结构固定成稳定回归证据。

正确顺序：

~~~text
真实 Probe
→ 脱敏保存必要结构
→ 更新/新增 Fixture
→ Mapper / Operation / Capability Test
~~~

不能手写一份“看起来像 TikHub”的 Fixture，然后据此宣布真实接口可用。

真实响应中 Secret、账号私密信息和不应提交的用户数据必须脱敏。

## 8. Candidate Builder 不能偷偷进入主链

项目可以保留 Candidate Builder 方便 A/B，但生产 Runtime 只有在正式决策后才切换。

需要同时确认：

- 正式 Builder/Operation；
- Capability；
- Mapper；
- Fixture；
- Pricing；
- Tests；
- Collection/平台文档；
- 相关 API/前端能力投影。

如果只是增加候选验证入口，不应该顺便改变生产接口。

## 9. 切换生产主链的最小证据

候选要升级为 production，至少回答：

1. 为什么现有主链接口需要切？
2. 新接口在哪些真实样本上验证？
3. Search/Detail/Comments/SubComments 的业务语义是否对应？
4. 稳定 ID 和分页如何保证？
5. Mapper/Canonical 是否需要变化？
6. Capability 是否需要变化？
7. 费用和限流影响是什么？
8. 哪些 Fixture/Test 能挡住回归？
9. 失败后如何回滚到旧 Operation？
10. 文档证据台账是否更新？

这不是固定测试数量要求，而是生产切换前必须解释的风险边界。

## 10. 什么时候允许“只切一个 Operation”

完全允许一个平台混合使用不同 family。

例如业务上可能出现：

~~~text
Search → Web
Detail → App
Comments → App
SubComments → Web
~~~

只要每个 Operation 都有自己的真实证据、稳定 identity 和 Mapper 适配即可。

不要为了版本整齐强制“一个平台全部用 App”或“全部用 Web”。

## 11. 当前验证结果去哪里查

本文故意不维护“小红书现在是哪条 Search”“微博评论当前哪个版本”之类状态。

当前/历史证据统一去：

- [docs/appendix/04_TikHub接口选型与真实验证台账.md](04_TikHub接口选型与真实验证台账.md)

当前生产代码和平台差异统一去：

- [docs/collection/01_xiaohongshu.md](../collection/01_xiaohongshu.md)
- [docs/collection/02_douyin.md](../collection/02_douyin.md)
- [docs/collection/03_weibo.md](../collection/03_weibo.md)
- [docs/collection/04_bilibili.md](../collection/04_bilibili.md)
- [docs/collection/05_kuaishou.md](../collection/05_kuaishou.md)

这样接口切换时：

~~~text
方法
→ 本文

真实证据
→ 04 台账

当前生产实现
→ collection 平台文档 + code
~~~

三层不会互相复制。
