# 舆情 AI 打标与统一分析契约

## 1. 定位

本设计负责全平台通用的**内容 AI 打标**能力，不属于临时 P1 私有逻辑，也不属于某个 Provider/平台 Mapper。

长期调用方向：

```text
TikHub / 官方 API / Apify / 文件导入 / 未来其他 Provider
→ 各自 Mapper
→ CanonicalContentV1
→ Provider-neutral 内容记录 / Query Read Model
→ Analysis Service
→ LLM Port
→ LLM Adapter
→ ContentLabelAnalysisV3
→ Analysis Repository / 统一 JSONL / Excel / 页面 / 报告
```

P1 的无数据库实现只是这套长期能力的第一个独立验证入口。以后正式系统从 PostgreSQL 读取内容后，仍调用同一 Analysis Service，不得按 TikHub、文件导入或不同平台分别维护标签逻辑。

当前 P1 只处理帖子/内容；未来如果增加评论打标，应复用本文同一个 Prompt Taxonomy、Validator 和重试语义，只增加“评论如何构造模型输入”的适配，不能复制第二套分类体系。

## 2. Canonical 不增加 AI 标签

`CanonicalContentV1` 只表示平台/Provider 实际观察到的事实。情感、一级标签和二级标签是**派生分析事实**，不能混入 Canonical `observed_fields`，也不能让 Mapper 伪装成 Provider 原始字段。

跨平台统一结构分两层：

```text
CanonicalContentV1
= 外部可观察事实

UnifiedContentRecordV1
= CanonicalContentV1 + 处理元数据 + 可空 Analysis
```

概念结构：

```json
{
  "schema_version": "content-record.v1",
  "content": {
    "schema_version": "content.v1"
  },
  "matched_keywords": ["爱玛"],
  "analysis": null
}
```

AI 成功后仍然写回同一条记录，只填：

```text
analysis: ContentLabelAnalysisV1 | ContentLabelAnalysisV2 | ContentLabelAnalysisV3
```

未来正式入库时：

```text
record.content
→ Content Owner

record.analysis
→ Analysis Owner
```

不得为了方便把整个 `UnifiedContentRecordV1` 直接当成 `contents` 表的一坨 JSONB。

## 3. Prompt Markdown 是具体标签体系的唯一事实源

正式运行时唯一标签/判断规则文件：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

具体的：

- 情感标签列表；
- 一级标签列表；
- 二级标签列表；
- 一级与二级父子关系；
- 每个标签覆盖内容；
- 典型表达；
- 边界规则；
- 多主题优先级；
- 正反例；

全部只维护在这个 Markdown 中。

Python/Pydantic **不得**再维护一份具体业务标签 `Enum`、`Literal[...]` 或 `PRIMARY_TO_SECONDARY` 常量。

因此以后业务 Owner 如果只是：

```text
增加标签
删除标签
标签改名
调整一级/二级父子关系
扩充判断标准
调整典型表达/边界示例
```

只修改 `content_labeling_v3.md`，无需同步修改 Python 标签枚举。

### 3.1 代码硬约束“结构和合法性”，不硬编码“标签内容”

代码固定强制：

```text
每条结果恰好 1 个 sentiment
每条结果至少 1 个 labels 标签对
每个标签对恰好 1 个 primary_label + 1 个 secondary_label
同一条结果不得出现重复标签对
sentiment 必须属于当前 Prompt Taxonomy
每个 primary_label 必须属于当前 Prompt Taxonomy
每个 secondary_label 必须属于同一标签对中的 primary_label
批量 item 必须一一对应
不得缺项、重复 item、多余 item 或未声明字段
```

一条内容可以同时命中同一一级下多个二级，也可以同时命中多个一级。程序保存完整标签对，不把一级数组和二级数组分离，因此父子关系不会丢失。“标签不硬编码”不等于“相信模型自由输出”；最终写入系统的值仍然只能来自当前 Markdown 中的闭集。

历史 `ContentLabelAnalysisV1/V2` 保留用于读取旧 JSONL/checkpoint；当前 Service 新生成的成功结果使用 `ContentLabelAnalysisV3`。V3 在**同一次 LLM 调用**中完成 `relevance + voice_type + sentiment + labels`：先做语义相关性复核，再做内容发声类型判断，只有 relevant 内容继续输出情感和标签。`voice_type` 是发声类型唯一业务事实，不再定义或暴露额外的二值用户发声字段。

### 3.2 V3 相关性、发声类型与离线删除语义

当前 V3 固定规则：

```text
关键词确定性粗筛
→ 去重
→ 单次 LLM：relevance + voice_type + sentiment + labels
→ 本地 Validator
→ relevant：写回 Analysis
→ irrelevant：从最终离线业务 JSONL 删除
```

`voice_type` 机器值固定为：`user_voice`、`creator_marketing`、`brand_official`、`dealer_promotion`、`media_information`、`other_organization`、`unknown`。判断的是当前内容发声属性，不声称认定账号真实法律身份。Prompt 必须综合标题、正文与作者展示名/公开简介/认证文案：标题和正文用于识别当前表达目的，作者信息作为主体证据；两者冲突时以当前内容主要表达目的为主，单一昵称、单一营销词或创作者身份不得机械决定类型，证据不足时使用 `unknown`。

离线流程中的“删除”指：AI 成功判定 `irrelevant` 后，该完整内容记录不再进入最终 `deduplicated/contents.jsonl`、最终 Excel 和报告。为了崩溃恢复与费用幂等，`analysis/checkpoints.jsonl` 可以保留不含正文的最小成功决策与稳定身份；它不是下游业务数据源，也不能被 Excel/报告消费。Provider Raw、来源账本和正式 PostgreSQL 审计历史继续按各自数据保留规则管理。

正式数据库默认列表、查询型 Analysis target 和查询型 Export 排除当前配置已判 `irrelevant` 的内容；显式 `relevance=irrelevant` 查询以及明确按内容 ID 读取详情仍可用于审计，不把审计读取重新解释为业务可见数据。

Excel 不展示“相关性”列，因为正常业务导出只消费 relevant 集合；发声类型在 Excel 中映射为中文，并且只展示这一份分类事实，不再增加第二个二值发声列。

## 4. 同一个 Markdown 中必须包含机器可读 Taxonomy JSON

程序不能通过模糊解析自然语言表格猜标签。正式 Prompt 必须同时包含一个机器可读 JSON 区块：

````markdown
<!-- AIMA_TAXONOMY_START -->
```json
{
  "schema_version": "aima-content-taxonomy.v1",
  "sentiments": ["正面", "中性", "负面", "混合"],
  "labels": {
    "品牌评价": [
      "口碑与信任",
      "形象与定位"
    ]
  }
}
```
<!-- AIMA_TAXONOMY_END -->

# 判断标准
...
````

运行时：

```text
读取完整 Markdown
→ 精确提取 AIMA_TAXONOMY_START / END 内 JSON
→ 标准库 json 解析
→ 校验 Taxonomy 自身结构
→ 规范化 JSON 并计算 taxonomy_sha256
→ 计算完整 Markdown 的 prompt_sha256
→ 以同一 Taxonomy 约束模型输出
→ 本地再次校验模型结果
```

首版不新增 YAML 解析依赖。

### 4.1 Prompt Taxonomy 本身也必须 fail closed

真实模型调用前至少验证：

- `sentiments` 为非空、去重字符串数组；
- `labels` 为非空对象；
- 一级标签名称非空且唯一；
- 每个一级至少一个非空二级；
- 同一一级下二级不重复；
- 首版要求二级在整个 taxonomy 中唯一，避免只返回二级名称时产生歧义；
- Taxonomy JSON 区块必须恰好一个；
- 缺失、重复、解析失败、空标签或结构非法时禁止调用真实模型。

Markdown 判断说明如果和机器 JSON 的标签名称冲突，机器 JSON 决定“什么值合法”，但文档 Review 必须修正语义冲突，不能长期放任两者不一致。

## 5. 当前首版 Taxonomy：严格完整包含业务截图

当前 Prompt 首版必须完整包含以下 **9 个一级标签、39 个二级标签**。这个数量只是当前 Prompt 内容事实，禁止写成 Python 常量；以后可以只改 Prompt。

### 5.1 完整父子关系

```text
品牌评价
├─ 口碑与信任
├─ 形象与定位
├─ 性价比与溢价
├─ 推荐与购买意愿
├─ 偏好与转换
└─ 营销与传播

外观设计
├─ 整体造型与颜值
├─ 颜色与配色
└─ 外观风格与适配人群

骑行性能
├─ 动力与加速表现
├─ 操控与稳定性
├─ 制动与刹车表现
└─ 舒适性

电池、续航与充电
├─ 实际续航表现
├─ 电池寿命与衰减
├─ 充电体验
└─ 电池安全

智能化与电子功能
├─ App与智能互联
├─ 智能解锁与启动
├─ 仪表与信息显示
├─ 智能辅助功能
└─ 系统稳定性与功能体验

耐用性与质量
├─ 做工与装配质量
├─ 长期使用与寿命表现
└─ 故障问题与稳定性

价格与价值
├─ 购车价格与配置价值
├─ 性价比与价格竞争力
├─ 购车优惠与促销政策
└─ 使用与养护成本

销售与购买体验
├─ 门店与渠道便利性
├─ 销售服务与购车咨询
├─ 下单与交易流程
└─ 交付与提车体验

售后服务
├─ 售后网点与服务便利性
├─ 客服与服务态度
├─ 维修处理效率与质量
├─ 保修政策与执行
├─ 配件供应与维修成本
└─ 投诉处理与用户权益
```

### 5.2 完整判断标准

| 一级标签 | 二级标签 | 覆盖内容与优化后的判断标准 | 典型表达仅作辅助 |
| --- | --- | --- | --- |
| 品牌评价 | 口碑与信任 | 整体口碑、质量印象、可靠程度、信任度、企业承诺兑现及市场评价；核心是“品牌整体是否可信/靠谱”，而非某一具体故障。 | 靠谱、值得信赖、牌子大、质量有保障、不可信、口碑差 |
| 品牌评价 | 形象与定位 | 品牌气质、档次、风格、目标人群、场景、年轻化/家庭化/高端化等定位印象。 | 年轻、时尚、高端、传统、老气、适合女生、家用 |
| 品牌评价 | 性价比与溢价 | 从品牌层面评价品牌值不值、是否有溢价及整体价格感知；若针对具体车型价格/配置，优先“价格与价值”。 | 品牌溢价、值不值、这个牌子性价比 |
| 品牌评价 | 推荐与购买意愿 | 明确推荐、劝购/劝退、购买意愿、观望、复购意愿。 | 推荐、值得买、想买、不建议买、观望、劝退、回购 |
| 品牌评价 | 偏好与转换 | 品牌忠诚、继续购买、长期使用、品牌迁移、从其他品牌换到爱玛或从爱玛换走。 | 继续买、换品牌、换爱玛、用了很多年、以后不买了 |
| 品牌评价 | 营销与传播 | 广告、代言人、直播、达人测评、联名、话题活动、宣传内容与社交传播方式本身。 | 广告、代言人、直播间、联名、达人、宣传、营销 |
| 外观设计 | 整体造型与颜值 | 整车外观、比例、辨识度、设计完成度和第一视觉印象；单纯颜色偏好不归此项。 | 颜值高、好看、漂亮、耐看、顺眼、协调、高级、有设计感、丑 |
| 外观设计 | 颜色与配色 | 颜色、配色方案、颜色质感、选择丰富度及适配性。 | 颜色、配色、色系、亮眼、低调、耐看、耐脏、显脏、高级、掉色 |
| 外观设计 | 外观风格与适配人群 | 外观设计风格与年龄、性别、通勤、运动、商务等人群/场景匹配度。 | 年轻、时尚、复古、运动、可爱、商务、女性化、老气、适合女生/年轻人 |
| 骑行性能 | 动力与加速表现 | 起步、中段加速、最高速度、爬坡、载人/载物时动力及动力衰减；核心是“跑得快不快/有没有劲”。 | 起步、加速、提速、动力、最高时速、爬坡、有劲、没劲、推背感、满载 |
| 骑行性能 | 操控与稳定性 | 灵活性、转向、车身稳定、弯道、掉头、低速行驶、方向轻重、发飘等操控体验。 | 好骑、难骑、灵活、笨重、稳、不稳、车身晃、方向轻/重、转向、掉头 |
| 骑行性能 | 制动与刹车表现 | 刹车力度、制动距离、线性、前后刹配合及雨天/紧急制动；若核心是刹车部件损坏，可按主诉归故障。 | 刹车、制动、急刹、刹得住、刹车灵/软/硬、刹车距离、点头、ABS、湿滑路面 |
| 骑行性能 | 舒适性 | 减震、座椅、路感、颠簸过滤、长时间骑行及双人骑行舒适度。 | 舒服、舒适、减震、避震、颠、震、硬、软、弹、路感、过滤、腰疼、长途 |
| 电池、续航与充电 | 实际续航表现 | 实际可骑里程、官方续航与实际差异，以及季节、路况、速度、载人等条件对续航影响。 | 续航、能跑多远、实测续航、官方续航、虚标、缩水、里程、公里、冬季续航 |
| 电池、续航与充电 | 电池寿命与衰减 | 电池使用周期、长期续航衰减、充放电次数、老化和更换周期。 | 电池寿命、电池衰减、用了多久、半年/一年/两年、越骑越短、续航下降、电池老化 |
| 电池、续航与充电 | 充电体验 | 充电速度、时长、接口、便利性、费用及充电过程异常；若核心是设备故障则按主诉判断。 | 充电、充多久、充电速度、快充、慢充、充满、充电时间、充电口、充电器、充电方便/麻烦 |
| 电池、续航与充电 | 电池安全 | 电池起火、发热、鼓包、进水、涉水、高低温、长期停放等安全和存放风险。 | 电池安全、起火、爆炸、发热、烫、鼓包、漏液、短路、过充、充电着火 |
| 智能化与电子功能 | App与智能互联 | App、蓝牙、车辆绑定、远程控制、定位、电子围栏、行驶数据查看等联网功能。 | App、手机、蓝牙、连接、绑定、配对、远程控制、远程启动、车辆定位、电子围栏、行驶记录 |
| 智能化与电子功能 | 智能解锁与启动 | NFC、刷卡、手机解锁、指纹、密码、遥控器、无钥匙启动等方式及可靠性。 | NFC、刷卡、手机解锁、指纹、密码、钥匙、遥控器、无钥匙、感应、自动解锁、识别不了 |
| 智能化与电子功能 | 仪表与信息显示 | 仪表、屏幕、电量/续航/速度/里程/故障提示、胎压等显示准确性、可读性与交互。 | 仪表、屏幕、显示、电量、续航、速度、里程、胎压、故障码、提醒、亮度、清晰、反光、看不清、数据不准、黑屏 |
| 智能化与电子功能 | 智能辅助功能 | 定速巡航、倒车辅助、自动驻车、语音控制、灯光感应、USB、蓝牙音响、导航等电子辅助。 | 定速巡航、倒车、自动驻车、语音、感应灯、自动大灯、USB、充电口、音响、导航、辅助功能 |
| 智能化与电子功能 | 系统稳定性与功能体验 | 电子系统/智能功能流畅性、稳定性、易用性、更新升级、OTA、功能失效、死机、掉线、复杂度。 | 系统、卡顿、死机、重启、闪退、延迟、误报、更新、升级、OTA、功能少/多、操作复杂、好用、稳定、不稳定 |
| 耐用性与质量 | 做工与装配质量 | 车架、塑件、漆面、接缝、装配精度、扎实度和新车做工等制造质量。 | 做工、装配、工艺、接缝、毛刺、松动、异响、塑料件、漆面、掉漆、划痕、变形、扎实、粗糙、廉价感 |
| 耐用性与质量 | 长期使用与寿命表现 | 使用一段时间后的整体状态、寿命、性能保持和老化程度，强调长期耐久而非一次具体故障。 | 耐用、寿命、用了半年/一年/两年、累计里程、老化、性能下降、越用越差、用了多年 |
| 耐用性与质量 | 故障问题与稳定性 | 无法启动、突然断电、系统异常、部件失灵、频繁维修、反复故障等稳定性问题。 | 故障、坏了、出问题、无法启动、突然断电、失灵、漏水、异响、抖动、反复坏、频繁维修、质量问题 |
| 价格与价值 | 购车价格与配置价值 | 整车售价、不同配置价格、车型价格与产品配置是否匹配，核心是“这辆车按这个配置值不值”。 | 价格、售价、指导价、落地价、裸车价、贵、便宜、配置、同价位、值不值 |
| 价格与价值 | 性价比与价格竞争力 | 综合比较价格、性能、续航、智能化、质量等价值，以及与同价位车型/竞品的性价比。 | 性价比、划算、不划算、超值、同价位、对比、竞品、值得买、不值得、价格优势 |
| 价格与价值 | 购车优惠与促销政策 | 优惠力度、补贴、赠品、金融方案、置换政策、直播优惠及活动规则。 | 优惠、折扣、补贴、立减、优惠券、赠品、置换、金融、分期、免息、直播间、活动、套路、限时 |
| 价格与价值 | 使用与养护成本 | 购车后持续产生的电费、换电费、保险、维修、保养、配件、电池更换等成本。 | 使用成本、养车成本、电费、充电费、换电费、保险、维修费、保养费、配件费、电池更换、人工费、后期成本 |
| 销售与购买体验 | 门店与渠道便利性 | 门店数量、位置、覆盖范围、到店便利、线上商城/直播间/经销商等购买渠道是否易找到和触达。 | 门店、专卖店、经销商、附近、离家近、网点、覆盖、找不到店、店太少、线上买、直播间、官方商城、渠道 |
| 销售与购买体验 | 销售服务与购车咨询 | 销售人员态度、专业程度、产品讲解、车型推荐、试驾安排、报价说明和销售承诺。 | 销售、导购、服务态度、热情、冷淡、专业、不专业、讲解、推荐、报价、隐瞒、夸大、试驾、承诺、套路 |
| 销售与购买体验 | 下单与交易流程 | 订车、付款、合同、分期、保险、上牌、发票、订单变更、退订等交易环节。 | 下单、订车、定金、付款、分期、合同、发票、保险、上牌、退款、退订、改订单、手续、流程、等车 |
| 销售与购买体验 | 交付与提车体验 | 交车时间、车辆状态、交付检查、随车资料、赠品、交车仪式和提车等待。 | 提车、交车、交付、现车、等车、延期、库存车、验车、检查、生产日期、里程、划痕、随车资料、合格证、赠品 |
| 售后服务 | 售后网点与服务便利性 | 售后网点数量、覆盖范围、距离、营业时间、预约方式及服务渠道便利性。 | 售后、维修点、服务站、网点、离家近、太远、找不到、覆盖少、预约、排队、营业时间、线上客服 |
| 售后服务 | 客服与服务态度 | 品牌客服、门店人员、维修人员响应态度、沟通方式、服务意识和问题解释。 | 客服、售后、态度、热情、冷淡、推诿、不理人、敷衍、耐心、专业、回复、电话打不通、没人管 |
| 售后服务 | 维修处理效率与质量 | 故障检测、维修时长、维修过程、维修结果和问题是否复现，核心是“修得快不快/好不好”。 | 维修、检测、排查、修理、维修时间、修了几天、当天修好、返修、重复故障、修不好、效率、拖延 |
| 售后服务 | 保修政策与执行 | 整车、电池、电机、控制器等部件保修期限、范围、条件以及实际执行。 | 保修、质保、三包、电池质保、保修期、保修范围、免费维修、免费更换、不在保、拒保、厂家保修 |
| 售后服务 | 配件供应与维修成本 | 原厂配件、配件库存、等待时间、配件价格、人工费、检测费和整体维修成本。 | 配件、原厂件、缺货、等配件、配件贵、维修费、人工费、检测费、更换、电池、控制器、收费、乱收费 |
| 售后服务 | 投诉处理与用户权益 | 投诉渠道、厂家介入、问题升级、退换车、赔偿、补偿及最终处理结果。 | 投诉、维权、厂家、总部、客服热线、12315、处理结果、赔偿、补偿、退车、换车、退款、曝光、回应、解决 |

典型表达只帮助模型理解，不是关键词命中规则。模型必须基于整条内容语义选主标签。

## 6. 多主题多标签选择

当前每条内容输出**一个整体情感 + 一个或多个一级/二级标签对**。标签选择遵循：

1. 只输出正文真实涉及且能被当前 Taxonomy 解释的标签，不为了“覆盖更多”凑标签；
2. 同一一级下可以命中多个二级，也可以同时命中多个一级；
3. 每个二级标签必须和其所属一级标签成对输出，不能把一级数组和二级数组拆开后丢失父子关系；
4. 同一 `(primary_label, secondary_label)` 标签对不得重复；
5. 具体产品/服务事实优先于泛品牌印象；
6. 明确故障优先“耐用性与质量 / 故障问题与稳定性”，但电池、智能功能、骑行性能有明确专属维度时优先专属标签；
7. 电池续航、衰减、充电、安全优先“电池、续航与充电”；App/NFC/仪表/电子功能优先“智能化与电子功能”；
8. 售后维修、保修、配件、投诉使用“售后服务”；购买前、下单、提车使用“销售与购买体验”；
9. 具体车型价格/配置、优惠、养护成本使用“价格与价值”；品牌层面的品牌溢价才使用“品牌评价 / 性价比与溢价”；
10. 广告、代言、直播、达人、联名等传播内容使用“品牌评价 / 营销与传播”。

模型可以返回多个合法标签对，但本地 Validator 仍是最终写入门禁；未知标签、错误父子关系、空标签和重复标签对一律拒绝。

## 7. 情感标签也由 Prompt 管理

当前 Prompt 基线：

```text
正面
中性
负面
混合
```

同样不写死在 Python `Enum/Literal`。

- **正面**：对爱玛品牌、产品、服务、价格政策、渠道或使用体验有明确认可、满意、推荐、支持或表扬；
- **中性**：主要是客观信息、事实、新闻、配置、价格或政策说明，没有明确正负态度；信息不足也用中性；
- **负面**：存在明确投诉、批评、质疑、不满、失望、风险指控或负面体验；
- **混合**：对爱玛本身同时存在具有实质信息量的正面和负面评价，且任何一方不能忽略。对竞品负面 + 对爱玛正面不等于混合。

## 8. 模型只接收三个业务字段

每条内容业务输入只能包含：

```text
title
text
author.display_name
```

缺失必须填空字符串，不传 `null`。

不得发送平台内容 ID、URL、互动指标、粉丝数、Provider、命中关键词、源 Excel “全文情感”、Raw 定位或其他 Provider 私有字段。

批量请求为了配对可以增加临时 `item_no`；它不是业务字段，也不能使用平台 ID 代替。

## 9. 模型输出 Contract：结构固定，标签动态

当前新成功结果使用 `ContentLabelAnalysisV2`：

```text
sentiment: str
labels: tuple[ContentLabelPairV2, ...]   # 至少 1 个
```

每个 `ContentLabelPairV2`：

```text
primary_label: str
secondary_label: str
```

程序固定保存的运行事实继续包括：

```text
schema_version
sentiment
labels
prompt_version
prompt_sha256
taxonomy_sha256
model_provider
model
input_hash
analyzed_at
analysis_status
```

模型只返回业务判断：

```json
{
  "items": [
    {
      "item_no": 1,
      "sentiment": "混合",
      "labels": [
        {"primary_label": "骑行性能", "secondary_label": "舒适性"},
        {"primary_label": "售后服务", "secondary_label": "客服与服务态度"}
      ]
    }
  ]
}
```

模型不负责伪造 model、Hash、时间等运行事实。为兼容历史离线样本/旧模型响应，Validator 可以把合法 V1 单标签响应解释为只有一个标签对；当前 Prompt V2 本身只要求 `labels[]` 形状，新 Service 始终写 V2。

## 10. 大模型不能保证永远输出正确格式，代码校验是强制门禁

即使模型 Provider 支持 JSON mode、response schema 或 structured output，也不能把模型输出直接写入业务 JSONL。原因包括：

- 返回可能被截断或不是合法 JSON；
- 批量结果可能缺 item、重复 item、多 item；
- 模型可能输出 Prompt 中不存在的近义标签；
- 一级和二级分别合法但父子组合错误；
- 用户编辑 Prompt 后 Taxonomy 本身可能有错误；
- 结构合法也不等于业务分类语义一定正确。

固定验证链：

```text
PromptTaxonomyLoader
→ Taxonomy 自身校验
→ 如模型 Provider 支持，则动态生成 response schema / enum 约束
→ LLM
→ JSON 解析
→ 固定结构/Pydantic 校验
→ item_no 一一对应校验
→ Runtime Taxonomy membership 校验
→ 一级/二级父子校验
→ 全部通过后才允许写入 checkpoint / analysis
```

**本地 Validator 必须存在。**

未知标签不得模糊匹配，不得自动改成“最接近标签”，不得把失败结果伪装成功。

## 11. 校验失败后的可配置有界重试

用户已确认：如果模型返回的字段、格式或标签不符合要求，Analysis Service 应在配置上限内重新请求，直到通过本地校验或达到重试上限。

### 11.1 配置语义

生产 Service 接收显式配置：

```text
max_validation_retries: int >= 0
```

含义固定为**首次请求失败后最多额外重试多少次**：

```text
0 = 最多 1 次总请求
1 = 最多 2 次总请求
2 = 最多 3 次总请求
```

不得把具体数字散落硬编码在 LLM Adapter、Service 或 Prompt 中。

P1 `imports_test/test.py` 应暴露一个易修改配置，例如：

```python
MAX_VALIDATION_RETRIES = 2
```

`2` 只作为 README/人工调试推荐起始值，不是不可修改的长期业务常量；真实请求会产生额外调用和费用，用户可以根据模型效果调整。

未来正式 Job/API 应把该值纳入正式 Analysis 执行配置，并记录运行快照，不能依赖 `imports_test` 常量。

### 11.2 哪些失败进入 Validation Retry

以下模型响应问题允许触发重试：

- 非法 JSON / 无法解析；
- 缺少必须字段；
- 返回多余未声明字段且严格 Contract 不接受；
- item 缺失、重复、数量不一致或 `item_no` 无法配对；
- sentiment 不在 Prompt Taxonomy；
- 任一一级标签不在 Prompt Taxonomy；
- 任一二级标签不在同一标签对的一级下；
- labels 为空、标签对重复、标签字段为空或其他结构违反。

重试时可以把**上一次本地校验错误的简短错误代码/说明**追加为纠错指令，例如：

```text
previous_response_validation_errors:
- invalid_secondary_for_primary
- unknown_sentiment

请重新返回整个批次，只使用当前 Taxonomy 中的合法值，并严格遵守 JSON 输出格式。
```

不能把程序自动猜出来的替代标签告诉模型，也不能绕过当前 Prompt Taxonomy。

### 11.3 重试与网络/Provider 重试分开

Validation Retry 是 Analysis Service 在拿到一个明确响应后，因**响应不满足业务 Contract**而发起的新 LLM 请求。

它不同于底层 Transport 在同一次调用里隐藏网络重试。每次重新请求必须作为可观察的独立模型 attempt，至少记录：

```text
item/batch identity
attempt_no
validation_error_codes
provider/model
prompt_sha256
taxonomy_sha256
started_at / finished_at
可获得时的 token/费用事实
```

不能无限重试。

逻辑 Validation Attempt 与物理 HTTP 请求必须分开审计。一次逻辑 attempt 可能因网络、429、
可恢复 5xx 或空 `content` 产生多个物理请求；`attempts.jsonl` 记录前者，
`llm_requests.jsonl` 逐次记录后者。费用汇总以物理请求为准，否则会漏掉已经返回 usage、但响应
内容无效后被重试的调用。

### 11.4 达到上限仍失败

如果所有允许尝试都未通过校验：

```text
analysis_status = failed
```

记录最终错误和 attempts 数；**不得**填入一个猜测标签。

该 item/batch 后续可以通过显式补跑继续处理。已经成功并 checkpoint 的 item 不得因为同批其他 item 失败而重新付费。

### 11.5 README 文档门禁

P1E/P1F 必须在：

```text
backend/src/aima_ugc/modules/analysis/README.md
```

说明平台通用的：

- Prompt/Taxonomy 唯一事实源；
- 本地 Validator；
- `max_validation_retries` 的精确定义；
- 哪些错误会重试；
- 达上限后的 failed 行为；
- 重试会增加模型调用/费用；
- Prompt/Taxonomy Hash；
- 如何调试非法模型返回。

P1 `imports_test/README.md` 还必须说明人工入口如何设置 `MAX_VALIDATION_RETRIES`、推荐起始示例和如何查看失败/checkpoint。

## 12. Prompt/Taxonomy Hash 与历史追溯

运行时计算：

```text
prompt_sha256
= 完整 Markdown 原文 SHA-256

taxonomy_sha256
= Taxonomy JSON 规范化后的 SHA-256
```

分析缓存/恢复 identity 至少绑定：

```text
内容 input_hash
prompt_sha256
taxonomy_sha256
model_provider
model
```

因此：

- 只改判断标准 → `prompt_sha256` 变化；
- 增删/重命名标签 → Taxonomy/Prompt Hash 变化；
- 改父子关系 → `taxonomy_sha256` 变化；
- 忘记手工改版本字符串也不会误复用旧结果。

版本字符串用于人工阅读，Hash 是精确运行事实。

## 13. JSONL 回写与恢复

### 13.1 当前离线单条并发执行

当前 `imports_test` 的真实模型执行采用：

```text
一条内容 = 一次独立 LLM 请求
最大在飞请求 = 250（运行配置）
```

250 只描述离线执行并发，不改变 `ContentLabelAnalysisV2`、Canonical 或标签 Taxonomy Contract。并发前先完整扫描输入 JSONL，校验结构、稳定身份、已有 Analysis 和可恢复 checkpoint；这只是**模型调用前的输入完整性与防重复预检**，不包含预算上限、费用阈值或 Token 预算停止逻辑。

当前执行使用有界滑动窗口，不一次性创建 90,000 个 Future；成功 checkpoint 由单一协调者追加并 durable，全部模型阶段结束后再按原 JSONL 行序原子回写，因此网络完成顺序不会改变业务数据顺序。Transport Retry 与 Validation Retry 分开：网络/429/可恢复 5xx 做有限退避重试，模型 HTTP 成功但标签结构不合法时只重试当前单条内容。

P1 `label_sentiment()` / 长期 `label_content()` 输入：

```text
deduplicated/contents.jsonl
```

每条只提取三个批准业务字段。

**只有通过全部本地校验的成功结果**才先 append + flush 到：

```text
analysis/checkpoints.jsonl
```

全部模型阶段结束后按原始 JSONL 行序：

```text
deduplicated/contents.jsonl
+ checkpoint
→ deduplicated/contents.jsonl.tmp
→ flush / fsync
→ atomic replace
→ deduplicated/contents.jsonl
```

最终业务 JSONL 自身 `analysis` 已填。checkpoint 只负责恢复、费用安全与审计，不是 Excel/数据库/页面的业务事实源。

### 13.2 全平台共享 LLM 计费事实（当前由离线入口装配）

价格、物理请求审计和费用复算由平台无关的 `adapters/llm` 持有，不属于 Excel、TikHub 或任一内容
平台。当前 `imports_test` 是第一个装配者：它在一次模型 run 开始时加载包内最小价格目录，并选择
本次 run 的审计文件路径；后续 Analysis Job 必须复用同一 Adapter 能力，不得按来源平台复制实现。

共享价格目录：

```text
backend/src/aima_ugc/adapters/llm/pricing.toml
```

价格按 `provider + model` 精确匹配，配置保存币种、实际使用的 token 单价、官方来源 URL 和
`effective_date`。供应商存在分时价格时，同一模型还保存 IANA 时区、一个全天默认价格时段和零个
或多个显式覆盖时段；时段区间按 `[start, end)` 解释并禁止重叠。该配置结构对所有 provider/model
通用，不把 DeepSeek 的时段或价格写死在 Adapter。缓存拆分价格字段固定为
`input_cache_hit_per_million_tokens`、
`input_cache_miss_per_million_tokens`、`output_per_million_tokens`，名称直接表达供应商官方的
输入（缓存命中）、输入（缓存未命中）、输出和“每百万 tokens”单位。`effective_date` 表示该价格项
在 AIMA 价格目录中的生效日期；它和人工价格版本都不参与公式。系统对规范化币种、单价和来源内容
计算 SHA-256，并按每个物理 HTTP 请求的 `started_at` 选择当时价格，在审计中冻结实际单价、来源
和快照身份。费用复算读取同一审计时间重新选择价格时段，不使用复算执行时间。

旧 TOML 字段只在加载边界兼容并显式告警；新的价格 Model、配置示例和成本计算引用只使用正式字段。
已经发布的 `llm-http-request.v1` 审计 JSON 字段保持不变，避免配置术语调整破坏历史复算。

当前支持：

```text
普通文本模型：input + output
缓存拆分文本模型：cache-hit input + cache-miss input + output
```

每个物理请求只记录安全计费事实，不记录 Prompt、标题、正文、作者或 Provider 响应正文。模型价格
未配置、usage 分类不足或响应在网络中丢失时必须写明费用不可计算，不得套用默认价格。汇总金额是
按 Provider usage 与配置的官方单价计算出的可复算值，不声明为供应商最终账单，也不参与预算停止
或调度决策。

价格变化后的复算生成独立派生报告，不覆盖原 `llm_requests.jsonl`、checkpoint、Analysis 或运行时
单价快照。使用新价格复算旧 token 只能解释为模拟重估；缺少缓存拆分等必要历史 token 时不能补造
精确金额。

## 14. Excel 只读取回写后的统一 JSONL

最终：

```text
deduplicated/contents.jsonl（analysis 已填）
→ 唯一共享 Excel Exporter
→ labeled_data.xlsx
```

不 join 第二份业务 Analysis JSONL，也不从 Excel 回读进入 AI。

可选 raw Excel 读取同一 JSONL，但 `include_analysis=False`。

## 15. 正式 Analysis PostgreSQL 持久化（Stage 8D 已实现）

Stage 8D 已建立 `analysis_content_results`、`analysis_content_label_pairs`、
`analysis_content_requests` 与 `analysis_content_request_items`，并接入 Pydantic HTTP、
`analysis.content-label.v1` durable Job、正式 Worker 和声音广场 current Analysis Query。离线
`imports_test`/`tikhub_test` 的文件模式保持不变，不因数据库产品化而自动写库或自动触发付费模型。

长期目标已经确认：**只要运行进入正式数据库模式，AI 结果通过本地 Validator 后，也必须作为独立 Analysis 业务事实写入 PostgreSQL。** 不能形成“Excel 有情感/一级/二级标签，而数据库只有 Content”的长期分叉。

### 15.1 固定写入链路

```text
Canonical / UnifiedContentRecordV1.content
→ ContentIngestionService
→ Content Owner Repository
→ PostgreSQL Content
→ 得到稳定 content_id

同一内容
→ Analysis Service
→ LLM
→ Runtime Taxonomy Validator
→ ContentLabelAnalysisV2（成功）
   ├→ 回写 deduplicated/contents.jsonl
   ├→ Shared Excel Exporter → labeled_data.xlsx
   └→ Analysis Owner Repository → PostgreSQL Analysis
```

固定规则：

1. Content 与 Analysis 分 Owner；不得把 AI 标签加进 `contents` 表方便查询。
2. JSONL、Excel 与 PostgreSQL Analysis 必须消费**同一份已经 Validator 接受的结构化 Analysis**；禁止从 Excel 反向解析标签再入库，也禁止数据库路径重新调用一次模型。
3. AI 失败不得写猜测标签；失败执行事实/错误由 Job/Run/Audit 记录，Analysis Result 只保存合法成功结果。
4. Content 已成功、Analysis 持久化失败时必须显式暴露 Analysis/DB 阶段失败或 partial 状态，并允许幂等重试；不能把“Content 已入库”冒充“AI 数据已完整入库”。
5. file-only 调试模式仍可以只保留 JSONL/Excel；“正式数据库模式必须写 Analysis”只在后续 Analysis Persistence 机器能力落地后成为运行时行为，不能靠 Blueprint 假装当前已经实现。

### 15.2 逻辑数据模型

推荐逻辑结构保持“结果父事实 + 标签对子事实”，避免把多标签压成字符串：

```text
Content Analysis Result
- id
- content_id                      FK → Content
- content_input_hash
- sentiment
- prompt_version
- prompt_sha256
- taxonomy_sha256
- model_provider
- model
- analyzed_at
- analysis_run/job identity

Content Analysis Label Pair
- analysis_result_id              FK → Content Analysis Result
- ordinal                         标签重要性/模型合法顺序
- primary_label
- secondary_label
```

同一结果内 `(analysis_result_id, primary_label, secondary_label)` 必须唯一，`ordinal` 保留 Validator 接受后的标签对顺序。

实际表名、字段、外键、索引和约束以 Migration `20260821_0021` 与 SQLAlchemy Table 为机器事实。
Result 唯一身份固定为 Content ID/Version、Input Hash、Prompt Hash、Taxonomy Hash、Provider 与 Model；
Request Item 冻结目标版本并关联成功 Result。结果/标签写入与 Request Item 状态推进在验证当前 Job
Fencing Token 的同一短事务中完成。

未来评论打标进入正式范围时，优先使用独立 Comment Analysis Result/Label Pair 与真实 `comment_id` 外键，不使用 `subject_type + subject_id` 这类无法由 PostgreSQL 正常外键约束的万能多态表，除非后续有新的明确证据改变该决策。

### 15.3 幂等、历史与 Current Analysis

Analysis identity 至少绑定：

```text
content_id
content_input_hash
prompt_sha256
taxonomy_sha256
model_provider
model
```

因此：

- 完全相同 identity 的成功结果重复提交必须幂等收敛，不产生重复标签对；
- Content 输入变化、Prompt/Taxonomy 变化或模型身份变化时，形成新的 Analysis 历史结果，不覆盖旧事实；
- 历史结果用于审计、复算、对比和问题追踪；
- Query 层提供确定性的 `current_analysis` 投影：选择匹配当前 Content Version、Prompt Version/Hash、
  Taxonomy Hash、Provider 与 Model 的最新成功结果。没有当前配置匹配结果但存在历史结果时返回 `stale`；
  从未有结果时返回 `pending`。列表、详情、标签过滤和正式 Excel 导出共用该选择语义。

声音广场只在用户显式确认选择项或当前查询后创建 Job；Import/Collection 默认不自动调用付费 Provider。
如果未来需要随采集自动分析，必须以新的 L3 Change 明确费用、调度、失败/partial 和级联事务边界。

Prompt/Taxonomy 只是标签合法性事实源；数据库不使用 PostgreSQL ENUM 固化具体标签集合，因此后续只改 Prompt 标签体系不需要数据库 ENUM Migration。

### 15.4 事务与恢复原则

- Content 需要先合法入库/收敛出稳定 `content_id`，Analysis Result 才能建立真实外键；
- 不要求把外部 LLM HTTP 调用放进数据库事务；LLM 调用完成并通过 Validator 后，再用短事务写 Analysis Result + Label Pairs；
- Analysis Result 与其 Label Pairs 必须在同一数据库事务提交；
- 重试必须依赖数据库唯一约束/幂等身份，而不是“先查有没有再插入”的进程内约定；
- 后续正式 Analysis Job 必须继续复用现有 LLM Request Audit/费用快照，不按 Excel/TikHub 来源复制第二套计费实现。

### 15.5 与报告的关系

Analysis 持久化落地后：

```text
离线单批报告
→ 本次 labeled_data.xlsx
→ Excel Report Source

正式系统报告 / Dashboard / 跨批次趋势
→ PostgreSQL Content + current Analysis + Comment Read Model
→ Report Read Model
```

两条路径都必须转换成同一个 Provider-neutral Report Dataset/Context，复用同一统计、Renderer 和 `platform/reporting/report_template.md`。不能因为 PostgreSQL 恰好可访问就让同一个离线 `run_all()` 自动改读数据库；报告数据源必须由业务场景显式决定。完整规则见 Blueprint 13/17。

## 16. P1E 必须落地的生产能力

P1E 至少建立：

```text
modules/analysis/prompts/content_labeling_v2.md
PromptTaxonomyLoader
ContentLabelAnalysisV2（一个情感 + N 个标签对，不硬编码业务标签枚举；V1 保留兼容）
ContentLabelingService
LLM Port
Fake Classifier
Runtime Taxonomy Validator
modules/analysis/README.md
```

自动测试至少证明：

1. 当前 Prompt 能解析出 **9 个一级、39 个二级**，名称逐项与本文基线一致；
2. Python 中没有第二份完整标签枚举/父子映射；
3. 修改 Prompt JSON 增加临时标签后，不改生产 Python 即可被 Loader/Validator 接受；
4. 删除/重命名 Prompt 标签后旧标签立即被 Validator 拒绝；
5. 合法一级 + 非所属二级被拒绝；
6. 重复标签、空标签、非法 Taxonomy JSON 在调用模型前失败；
7. title/text/author 缺失时填 `""`；
8. 模型 payload 不包含 ID、URL、指标、Provider、matched_keywords、源情感；
9. Prompt 文本变化改变 `prompt_sha256`，Taxonomy 变化改变 `taxonomy_sha256`；
10. Fake 可以制造非法 JSON、未知标签、父子错配、缺 item，验证可配置 Validation Retry；
11. `max_validation_retries=0/1/2` 对应总请求次数 1/2/3，达到上限后 failed；
12. 已成功 item 不因同批其他 item 重试而被重复请求。

## 17. P1F 真实模型验证

真实模型 Probe 默认关闭，不进入普通 CI。

人工确认样本至少覆盖：

- 当前 4 种情感；
- 当前 9 个一级标签；
- 39 个二级都有离线/Fake 合法性 Fixture；
- 易混淆边界，例如品牌溢价 vs 车型价格、长期寿命 vs 单次故障、电池安全 vs 一般故障、销售咨询 vs 售后客服、门店渠道便利 vs 售后网点便利、操控稳定 vs 系统稳定。

真实 Probe 记录：

```text
结构化首次成功率
经过 Validation Retry 后成功率
平均/最大尝试次数
最终失败率
人工标签差异
延迟
token/费用（Provider 可提供时）
失败原因
```

一次 Probe 不能承诺长期模型稳定性。

## 18. 长期维护规则

### 只改判断标准/示例

只修改：

```text
content_labeling_v2.md
```

代码不变，`prompt_sha256` 自动变化。

### 增删/重命名标签或改父子关系

仍然只修改同一个 Markdown 的 Taxonomy JSON 和对应判断说明。代码不改，`taxonomy_sha256` 自动变化。

### 修改验证重试次数

这是运行配置变化，不修改标签 Prompt；P1 人工入口改 `MAX_VALIDATION_RETRIES`，未来正式系统改对应 Analysis 执行配置。

### 什么时候才需要改代码/Contract

只有例如：

- 改变当前 `labels[]` 标签对结构或标签顺序语义；
- 增加三级标签；
- 增加必须返回的置信度、理由、实体等字段；
- 改模型业务输入字段；
- 改 JSONL/数据库 Analysis 结构；
- 改失败/重试/历史语义本身。

“只是标签列表、父子关系和判断标准变化”不再触发 Python 标签枚举修改。
