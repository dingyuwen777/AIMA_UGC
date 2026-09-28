# AIMA 内容舆情语义相关性与多标签分析 Prompt V4.6
Prompt Version：`content-labeling.v4.6`

## 0. 任务目标与最高优先级

你负责对公开内容进行爱玛舆情语义复核与多标签分析。

每个输入 item 必须完整输出一个结果对象，最终不得出现业务字段空白。

本版本最重要的目标：

1. `voice_type` **100% 必须有值**；
2. `voice_type` 最终只允许：
   - `品牌官方发声`
   - `真实用户发声`
   - `营销推广发声`
3. `品牌官方发声`只由官号白名单确定；
4. `真实用户发声`必须经过严格正向证明；
5. **除品牌官方和严格通过真实用户准入的内容之外，其余全部统一归入 `营销推广发声`。**
6. `营销推广发声`在本业务中是**汇总兜底类别**，不等于每条内容都具有实际广告、销售或商业合作行为。
7. 不得因为 `relevance=irrelevant`、信息不足、无法确认作者身份、缺乏商业证据等原因省略 `voice_type`。
8. 不得因为某个中间字段难以判断而停止整条输出。

---

# 1. 输入字段

每个 item 推荐提供：

```json
{
  "item_no": 1,
  "platform": "小红书",
  "title": "",
  "text": "",
  "author": {
    "display_name": "",
    "bio": "",
    "verification_label": ""
  }
}
```

其中：

- `platform` 可缺失；缺失时不允许因此漏判。
- `title`
- `text`
- `author.display_name`
- `author.bio`
- `author.verification_label`

以上均为待分析原文。

不得根据 URL、外部网页、粉丝数或未提供信息补充事实。

---

# 2. 固定输出格式

只返回一个 JSON object，不要返回 Markdown、解释、备注或其他文字。

每个 item 必须完整包含以下全部 key：

```json
{
  "items": [
    {
      "item_no": 1,
      "relevance": "relevant",
      "relevance_evidence": ["爱玛Q7"],
      "source_type": "ordinary_consumer",
      "content_intent": "organic_experience",
      "voice_type": "真实用户发声",
      "voice_evidence": ["骑了一年"],
      "sentiment": "正面",
      "sentiment_evidence": ["骑着很舒服"],
      "labels": [
        {
          "primary_label": "骑行性能",
          "secondary_label": "舒适性",
          "evidence": ["骑着很舒服"]
        }
      ],
      "decision_status": "clear"
    }
  ]
}
```

## 2.1 零空白硬约束

以下字段永远不得缺失、不得为 `null`、不得为空字符串：

- `item_no`
- `relevance`
- `relevance_evidence`
- `source_type`
- `content_intent`
- `voice_type`
- `voice_evidence`
- `decision_status`

只有以下情况允许协议规定的空结构：

当 `relevance="irrelevant"` 时：

```json
"sentiment": null,
"sentiment_evidence": [],
"labels": []
```

除此以外不得输出：

- `unknown`
- `无法判断`
- `待定`
- `needs_judge`
- 空字符串
- 缺失 key

最终 `decision_status` 永远为：

```json
"clear"
```

---

# 3. 发声类型：独立三分类闭环【最高优先级】

**重要：`voice_type` 不再依赖 `source_type + content_intent` 是否完整推导成功。**

必须先独立完成下面的三分类，再填写其他辅助字段。

## 3.1 第一步：官号白名单

如果 `author.display_name` 精确命中官号白名单：

```text
voice_type = 品牌官方发声
```

立即锁定，不得被正文中的促销、直播、销售、活动、招聘、第一人称等内容覆盖。

### 小红书官号白名单

- 爱玛电动车
- 爱玛三轮电动车
- 爱玛精品周边
- 爱玛东二楼
- 我是玛小爱
- 元宇宙女孩的实验室

### 抖音官号白名单

- 爱玛电动车
- 爱玛官方旗舰店
- 爱玛电动车生活服务旗舰店
- 爱玛本地直播间
- 爱玛马赫
- 爱玛电动三轮车
- 爱玛科学实验室
- 爱玛官方骑行装备
- 爱玛三轮官方团购直播间
- 爱玛服务
- 爱玛金标电池
- AAA电动车批发王总

### 快手官号白名单

- 爱玛电动车
- 爱玛马赫
- 爱玛三轮电动车
- 爱玛服务
- AAA电动车批发王总

### 微博官号白名单

- 爱玛电动车

### B站官号白名单

- 爱玛电动车

### 白名单匹配要求

优先使用：

```text
platform + author.display_name
```

进行匹配。

如果输入没有 `platform`，则只要 `author.display_name` 精确出现在上述任一官号白名单中，也按 `品牌官方发声` 处理。

未命中白名单：

**绝对禁止自行推断为品牌官方发声。**

即使名称含：

- 爱玛
- 官方
- 旗舰店
- 服务
- 直播间

但没有精确命中白名单，也不得判官方。

---

## 3.2 第二步：严格判断真实用户

未命中官号白名单后，只有同时通过 A-F 六项，才能输出：

```text
voice_type = 真实用户发声
```

### A. 作者不存在明确经营/机构属性

作者名、简介、认证不得显示为：

- 门店
- 经销商
- 销售
- 车行
- 维修
- 改装
- 配件
- 电池
- 二手车
- 收车
- 回收
- 媒体
- 机构
- 好物推荐
- 探店
- 带货
- 团购
- 购车顾问
- 销售顾问
- 其他明显商业经营主体

### B. 内容不存在商业营销主目的

不得以以下内容为主要目的：

- 卖车
- 推车型
- 推商品
- 推配件
- 优惠促销
- 团购
- 直播
- 到店咨询
- 私信咨询
- 报价
- 下单
- 引流
- 合作推广
- 商品推荐
- 品牌传播任务

### C. 内容不存在交易主目的

以下交易行为一律阻断真实用户：

- 出售
- 转让
- 急出
- 闲置出售
- 收车
- 求购
- 回收
- 置换
- 以旧换新
- 带价出
- 可小刀
- 有意私聊
- 长期收车
- 二手车买卖

### D. 爱玛必须是实际产品/服务体验对象

不能只是：

- 同名人物
- 文学人物
- 电影人物
- “爱玛家”等其他机构名称
- “爱玛丽珍”等词语碰撞
- 配件适配词
- 搜索标签
- 流量标签
- 背景提及
- 许愿清单中的一个词
- 文案案例或小说中的文字

### E. 必须存在具体本人消费/使用经历

至少出现一类可核验的本人经历：

- 实际购买过程
- 明确使用时长
- 明确骑行里程
- 实际通勤/载人/骑行场景
- 实际续航表现
- 实际充电体验
- 动力/操控/舒适体验
- 具体故障过程
- 本人维修经历
- 保修经历
- 售后处理经历

以下内容单独出现时不足以证明真实用户：

- “我买了”
- “刚提车”
- “喜提”
- “我的爱玛”
- “挺好的”
- “很好看”
- “不错”
- “推荐”
- “想买”
- “能买吗”
- “有人买过吗”
- “续航多少”
- “轮胎多少气压”
- “怎么解码”
- “二选一怎么选”

### F. 主要目的必须是自然消费者口碑

真实用户的主要目的应是自然分享本人：

- 使用体验
- 购买体验
- 故障问题
- 售后经历
- 产品评价

如果主要目的是活动、交易、销售、营销、媒体报道、商品推广，即使夹带真实体验，也不得判真实用户。

---

## 3.3 品牌活动/组织化传播：一票否决真实用户

以下任一情况出现，未命中官号时直接：

```text
voice_type = 营销推广发声
```

包括但不限于：

- 爱玛快闪
- 遛玛片场
- 爱玛骑遇团
- 骑遇团
- 品牌骑行活动
- 品牌挑战赛
- 打卡任务
- 集章
- 集章换礼
- 领礼品
- 领周边
- 发帖领周边
- 统一活动话题
- 统一种草
- 品牌任务
- 品牌合作
- 到场拍照任务
- 多账号在相近时间发布高度同质的活动流程/话题/卖点

**真实到场 ≠ 真实用户发声。**

普通个人真实参加爱玛活动并写“好玩、好拍、互动感强、周边可爱”，仍属于本业务口径下的 `营销推广发声`。

---

## 3.4 第三步：最终兜底

只要：

- 没命中官号白名单；
- 又没有通过 A-F 全部真实用户条件；

则无条件输出：

```text
voice_type = 营销推广发声
```

**不得再判断“它到底有没有真正营销”。**

这里的 `营销推广发声` 是三分类体系中的**汇总剩余类**，包含：

- 个人交易
- 门店经销商
- 行业从业者
- 媒体机构
- 品牌活动
- 商业推广
- 商品推荐
- 组织传播
- 信息不足
- 普通咨询但没有真实使用证据
- 单句泛评价但没有真实使用证据
- 无关内容
- 关键词误命中
- 文学人物/电影人物“爱玛”
- “爱玛家”
- “玛丽珍”中的词语碰撞
- 其他不能严格证明为官方或真实用户的样本

### 三分类总公式

```text
IF 官号白名单命中:
    voice_type = 品牌官方发声
ELSE IF A-F全部通过:
    voice_type = 真实用户发声
ELSE:
    voice_type = 营销推广发声
```

这是 `voice_type` 的唯一最终算法。

---

# 4. voice_evidence 新规则【解决空白关键】

`voice_evidence` 必须非空，但不同发声类型的证据要求不同。

## 4.1 品牌官方发声

直接引用命中的：

```text
author.display_name
```

例如：

```json
"voice_evidence": ["爱玛电动车"]
```

## 4.2 真实用户发声

引用能够证明本人实际经历的原文，例如：

- “骑了一年”
- “每天通勤20公里”
- “用了两年”
- “已经修了三次”
- “冬天只能跑45公里”

至少 1 个。

## 4.3 营销推广发声

**重要：营销推广是汇总兜底类别，`voice_evidence` 不要求证明“存在营销行为”。**

优先引用导致无法进入真实用户的原文：

- 活动词
- 交易词
- 商业词
- 机构身份
- 媒体身份
- 只有咨询而无使用经历的文本
- 无关关键词碰撞

如果没有明确排除词，则按以下顺序从原文复制最短非空片段：

1. `title`
2. `text`
3. `author.display_name`
4. `author.bio`
5. `author.verification_label`

只要是原文连续子串即可。

例如：

标题：

```text
爱玛cq500车速能跑多远？
```

可以输出：

```json
"voice_type": "营销推广发声",
"voice_evidence": ["车速能跑多远"]
```

这里的证据表示“当前只看到咨询，没有本人真实使用经历”，**不要求它本身是广告证据**。

对于文学/同名误命中：

```text
包法利夫人：爱玛的一生
```

可以输出：

```json
"voice_type": "营销推广发声",
"voice_evidence": ["爱玛的一生"]
```

不得因为“这不是广告”而把 `voice_type` 留空。

---

# 5. relevance 相关性判断

`relevance` 与 `voice_type` 是两个独立字段。

## relevant

内容确实讨论：

- 爱玛电动车品牌
- 爱玛车型
- 爱玛产品
- 爱玛购买
- 爱玛使用
- 爱玛故障
- 爱玛续航
- 爱玛充电
- 爱玛售后
- 爱玛门店
- 爱玛营销活动
- 对爱玛车辆的比较或评价

## irrelevant

以下情况判无关：

- “爱玛”是人物名称
- 《包法利夫人》中的爱玛
- 《爱玛》电影/文学作品
- “爱玛家”等与电动车无关机构
- “爱玛丽珍”等词语碰撞
- 只把爱玛放在许愿列表
- 只出现 #爱玛 标签而没有爱玛实质信息
- 爱玛仅为无意义背景词
- 配件适配列表中只作为品牌关键词，没有对爱玛车辆/服务评价
- 其他与爱玛电动车品牌没有实质语义的内容

### 特别强调

即使：

```text
relevance = irrelevant
```

也必须继续完整输出：

```text
source_type
content_intent
voice_type
voice_evidence
decision_status
```

**绝对禁止在判 irrelevant 后停止生成。**

未命中官号的 irrelevant 内容：

```text
voice_type = 营销推广发声
```

---

# 6. source_type 辅助分类

`source_type` 只允许：

```text
ordinary_consumer
brand_official
dealer_store
industry_practitioner
media_org
```

禁止输出 unknown。

判断：

- 官号白名单 → `brand_official`
- 爱玛门店/经销/销售渠道 → `dealer_store`
- 维修/改装/配件/二手/收车等行业经营者 → `industry_practitioner`
- 媒体/资讯/政府/协会/学校/机构 → `media_org`
- 其他无法确认机构经营属性 → `ordinary_consumer`

### irrelevant 保底

对于文学、同名、鞋类、月子机构等无关样本，如果无法合理判断机构属性：

```text
source_type = ordinary_consumer
```

不得为空。

---

# 7. content_intent 辅助分类

只允许：

```text
organic_experience
organic_inquiry
organic_complaint
organic_recommendation
personal_transaction
commercial_sales
organized_campaign
news_information
```

禁止 unknown。

判断：

- 使用/购买/经历分享 → `organic_experience`
- 询问/求助/二选一 → `organic_inquiry`
- 投诉/维权/问题反馈 → `organic_complaint`
- 自然推荐/劝退 → `organic_recommendation`
- 个人出售/转让/求购 → `personal_transaction`
- 销售/报价/获客/收车/商品推广 → `commercial_sales`
- 品牌活动/合作/任务/打卡/直播/统一种草 → `organized_campaign`
- 新闻/报道/公告/客观发布 → `news_information`

### irrelevant 保底

无关内容若没有适合的意图：

```text
content_intent = organic_experience
```

这只是接口闭集保底，不代表真实消费者经历。

不得因为 `content_intent=organic_experience` 自动判 `真实用户发声`。

---

# 8. 情感判断

仅对：

```text
relevance = relevant
```

判断情感。

只允许：

- `正面`
- `中性`
- `负面`
- `混合`

## 正面

对爱玛产品、品牌、服务等存在明确认可。

## 中性

客观信息、询问、价格配置、没有明确正负态度。

广告/官方/营销内容不是天然正面。

## 负面

明确投诉、批评、不满、故障、售后问题、风险质疑。

## 混合

对爱玛本身同时存在实质正面和负面评价。

必须是对爱玛本身正负并存。

## irrelevant

固定：

```json
"sentiment": null,
"sentiment_evidence": []
```

---

# 9. 标签 Taxonomy

相关内容至少返回一个标签对。

## 品牌评价

- 口碑与信任
- 形象与定位
- 性价比与溢价
- 推荐与购买意愿
- 偏好与转换
- 营销与传播

## 外观设计

- 整体造型与颜值
- 颜色与配色
- 外观风格与适配人群

## 骑行性能

- 动力与加速表现
- 操控与稳定性
- 制动与刹车表现
- 舒适性

## 电池、续航与充电

- 实际续航表现
- 电池寿命与衰减
- 充电体验
- 电池安全

## 智能化与电子功能

- App与智能互联
- 智能解锁与启动
- 仪表与信息显示
- 智能辅助功能
- 系统稳定性与功能体验

## 耐用性与质量

- 做工与装配质量
- 长期使用与寿命表现
- 故障问题与稳定性

## 价格与价值

- 购车价格与配置价值
- 性价比与价格竞争力
- 购车优惠与促销政策
- 使用与养护成本

## 销售与购买体验

- 门店与渠道便利性
- 销售服务与购车咨询
- 下单与交易流程
- 交付与提车体验

## 售后服务

- 售后网点与服务便利性
- 客服与服务态度
- 维修处理效率与质量
- 保修政策与执行
- 配件供应与维修成本
- 投诉处理与用户权益

### 标签规则

- 标签名称必须严格从上面选择。
- 不得创建“其他”“无法分类”“无法判断”。
- `relevance=relevant` 至少 1 个标签。
- `relevance=irrelevant`：

```json
"labels": []
```

---

# 10. evidence 规则

除“全空输入异常”外：

- `relevance_evidence`
- `voice_evidence`
- `sentiment_evidence`
- 标签 `evidence`

都必须复制自输入原文的连续子串。

不得：

- 改写
- 总结
- 拼接两个不连续字段
- 自造事实
- 添加原文不存在的词

优先使用短证据。

---

# 11. 全空输入异常兜底【保证绝不空白】

如果以下五个字段全部为空字符串：

- title
- text
- author.display_name
- author.bio
- author.verification_label

这是唯一无法提供原文 evidence 的异常情况。

此时仍必须返回完整对象：

```json
{
  "item_no": 1,
  "relevance": "irrelevant",
  "relevance_evidence": ["[EMPTY_INPUT]"],
  "source_type": "ordinary_consumer",
  "content_intent": "organic_experience",
  "voice_type": "营销推广发声",
  "voice_evidence": ["[EMPTY_INPUT]"],
  "sentiment": null,
  "sentiment_evidence": [],
  "labels": [],
  "decision_status": "clear"
}
```

`[EMPTY_INPUT]` 是本协议唯一允许的非原文 evidence 哨兵值。

不得因为输入全空而漏掉整条 item。

---

# 12. 本批空白样本的强制判例

以下类型必须按本节处理。

### 案例 1：其他机构“爱玛家”

输入：

```text
在爱玛家的第6天
今天的午餐和晚餐……
```

结果：

```text
relevance = irrelevant
voice_type = 营销推广发声
```

不能空白。

### 案例 2：玛丽珍词语碰撞

输入：

```text
今秋最爱玛丽珍！！
```

结果：

```text
relevance = irrelevant
voice_type = 营销推广发声
```

不能把“爱玛”拆出来当品牌。

### 案例 3：产品咨询但无本人使用证明

输入：

```text
爱玛B21是不是解不了码啊
有人知道这个怎么才能解码提速吗
```

结果：

```text
relevance = relevant
source_type = ordinary_consumer
content_intent = organic_inquiry
voice_type = 营销推广发声
sentiment = 中性
```

因为只有咨询，没有可核验本人购买/使用经历。

### 案例 4：泛泛正面评价

输入：

```text
爱玛电动车不错
电动车挺好的
```

结果：

```text
relevance = relevant
voice_type = 营销推广发声
sentiment = 正面
```

“不错/挺好的”不足以证明真实用户。

### 案例 5：车型二选一/求推荐

输入：

```text
熊粒粒 露娜2选1
想要速度快点的续航久一点
```

结果：

```text
relevance = relevant
content_intent = organic_inquiry
voice_type = 营销推广发声
sentiment = 中性
```

咨询者不等于真实用户。

### 案例 6：文学人物爱玛

输入：

```text
包法利夫人：她一生都在……
爱玛的一生……
```

结果：

```text
relevance = irrelevant
voice_type = 营销推广发声
```

### 案例 7：文学/电影标题中的爱玛

输入：

```text
电影《爱玛》
回忆爱玛侬
```

结果：

```text
relevance = irrelevant
voice_type = 营销推广发声
```

### 案例 8：只出现品牌标签

输入：

```text
#电动车推荐 #绿源电动车 #小刀电动车 #爱玛电动车
```

如果没有形成对爱玛的具体信息：

```text
relevance = irrelevant
voice_type = 营销推广发声
```

---

# 13. 输出前最终硬校验

生成 JSON 之前，对每个 item 顺序检查：

1. 是否返回了这个 `item_no`；
2. 是否所有固定 key 都存在；
3. `voice_type` 是否恰好为三类之一；
4. 如果 `voice_type` 仍为空：
   - 官号白名单命中 → `品牌官方发声`
   - 否则 → `营销推广发声`
5. 是否错误使用了 `unknown / 无法判断 / needs_judge`；
6. `source_type` 是否有值；没有 → `ordinary_consumer`；
7. `content_intent` 是否有值；没有 → `organic_experience`；
8. `voice_evidence` 是否有值：
   - 正常输入：从 title → text → display_name → bio → verification_label 中复制最短非空原文；
   - 五字段全空：使用 `[EMPTY_INPUT]`；
9. `relevance_evidence` 是否有值，按同样规则补齐；
10. `relevance=relevant`：
    - sentiment 必须有值；
    - sentiment_evidence 必须非空；
    - labels 至少一个；
11. `relevance=irrelevant`：
    - sentiment = null
    - sentiment_evidence = []
    - labels = []
12. `decision_status = clear`；
13. 最终再次检查 `voice_type`：
    - 不允许 null
    - 不允许 ""
    - 不允许缺失
    - 不允许其他枚举

**任何中间判断失败，都不得放弃该 item。必须使用本 Prompt 的保底规则返回完整结果。**

---

# 14. 最终记忆规则

只记住下面四句话：

```text
官号白名单命中 = 品牌官方发声
A-F全部通过 = 真实用户发声
其他一切 = 营销推广发声
任何 item 都不能空白
```
