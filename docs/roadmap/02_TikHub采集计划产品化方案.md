# TikHub 采集计划产品化方案

状态：2026-10-02 用户已批准，实施中；验收状态由 [Issue #694](https://github.com/dingyuwen777/AIMA_UGC/issues/694) 的 AC1–AC28 维护。

本文件完整保存用户指定会话《解释评论自适应采集》的最新 36 节方案，避免长任务丢失细节。原文中的“当前”是方案提出时的事实描述，实施前必须与当前代码核验；示例结构为已批准设计意图，不冒充已实现。

上游：会话 `6abf63eb-e0ec-83e8-ab11-7b70807898d7`，用户 2026-10-02 明确要求按方案实施、本地验证后合并远程 main。完整原文同时保留在 Issue 正文。

## 稳定验收索引

<a id="AC1"></a>AC1：采集策略仍含关键词包和采集计划；采集计划是多类型父概念，当前仅 TikHub；直接点击“新建 TikHub 采集计划”打开配置，UI 统一 TikHub，无类型选择中间层。

<a id="AC2"></a>AC2：collection_plans 增加非空 plan_type=tikhub 和 Check Constraint；全部既有 Plan 回填 tikhub，既有评论策略保持 adaptive；不重命名关联子表。

<a id="AC3"></a>AC3：领域/API 区分通用 Plan 事实与 TikHub 类型配置，类型成为一级事实，不从 provider 推断，不预造未来类型或堆 Optional 字段；当前专属关联受类型约束。

<a id="AC4"></a>AC4：Scheduler、手动计划运行及执行入口按 plan_type 分发；未知类型 fail closed，不创建或错误执行 TikHub Run/Scope/请求。

<a id="AC5"></a>AC5：新 Run 显式冻结 schema_version、plan_type、schedule_version、comment_policy 和一致执行策略；仅旧 collection-run-config.v2 缺类型时解释为 TikHub，不重写历史快照。

<a id="AC6"></a>AC6：comment_policy 和 decision_policy.comment_mode 支持 adaptive/full，默认 adaptive，创建/更新单向同步或校验一致，不能出现 full/adaptive 矛盾；编辑仅影响未来 Run，不能启动历史补采。

<a id="AC7"></a>AC7：新增可审计 fetch_full action 并通过正式 Migration 扩展 Check Constraint；Contract/OpenAPI/JSON Schema/TS Client 从事实源生成且无手工 generated 修改。

<a id="AC8"></a>AC8：Adaptive 回归：30一级目标30、500一级目标50、30回复目标5、评论数无变化通常跳过，未知数按现有 Probe/Detail 规则。

<a id="AC9"></a>AC9：Full 新内容正数或未知数持续分页；500一级不在50停止、30回复不在5停止、未知数不在第一页停止；零评论跳过并形成正确完整事实。

<a id="AC10"></a>AC10：Full 完整度由现有 root/thread coverage 聚合：根 complete 且全部必要回复线程 complete 才完整；根 partial 或任何必要线程 partial/缺失均不完整，不另造完整布尔表。

<a id="AC11"></a>AC11：Full 先前完整且评论数相同跳过；先前不完整即使数量相同也继续补齐，不能把 Adaptive 样本覆盖误作 Full 完整。

<a id="AC12"></a>AC12：小红书/B站先前全部完整且数量增加时可靠 newest 增量、整页摄取和稳定 known boundary；证明满足时保持 complete，证据不足时 partial，不丢同页新评论或尚未补齐回复。

<a id="AC13"></a>AC13：抖音/微博/快手数量变化时按能力受控全量刷新并 Stable ID 去重、直到 Provider exhausted；不能退回50条自适应。

<a id="AC14"></a>AC14：Full 二级线程 complete 且 reply_count 未变时跳过；数量改变/未知或线程partial时继续补齐；内容级和线程级均避免重复付费请求。

<a id="AC15"></a>AC15：Plan Full 与 batch/content/date Supplement 统一全量判定并共用正式 comments/sub_comments 分页、Mapper/Canonical/Ingestion/Coverage；保留补采既有语义、Raw恢复、Fencing/取消。

<a id="AC16"></a>AC16：保留根/回复各100页安全上限；page_limit、分页停滞或Provider无法继续时明确partial及stop_reason，不能误标complete；全量仅承诺可获取范围。

<a id="AC17"></a>AC17：创建/编辑复用同一个 TikHubPlanDialog 和 AimaModalContainer；详情继续Drawer；约960×820且受viewport-48约束，固定Header/Footer、Body滚动、低干扰滚动条，无Wizard或第三套Modal基础。

<a id="AC18"></a>AC18：Modal 基本信息、频率两列；关键词包/品牌两列；“采集渠道”改“目标平台”；五平台卡片大屏双列/窄屏单列，未选择平台不展开参数，保留真实Search能力选项、启用配置。

<a id="AC19"></a>AC19：评论策略两个Radio Card；Adaptive明确一级≤50尽量完整、>50默认50、回复默认5、无变化/可靠增量；Full说明一级+二级全部可获取、刷新/分页/部分与限制。

<a id="AC20"></a>AC20：Full清晰提示TikHub请求及费用显著增加、当前没有请求或金额预算上限；规则说明与冻结执行参数一致，不作虚假完整或零成本承诺。

<a id="AC21"></a>AC21：Modal Browser覆盖中央弹窗、Header/Footer/Body、取消/关闭/焦点、编辑回显/保存刷新、保存pending防重复及失败保留草稿。

<a id="AC22"></a>AC22：列表使用名称/类型/状态/采集范围/策略/调度与下次运行/操作；TikHub Badge与adaptive/full策略正确，不把平台作为通用顶层列。

<a id="AC23"></a>AC23：详情Drawer使用通用壳和TikHub专属配置，显示类型、策略、真实一级/回复/刷新规则、关键词包/品牌/平台/搜索参数；创建/编辑/复制/列表/详情完整round-trip。

<a id="AC24"></a>AC24：本地 Domain/Decision、Contract、PostgreSQL Migration旧数据/CRUD、Scheduler冻结、Collection执行/coverage/replies/安全上限及Adaptive回归均取得直接证据。

<a id="AC25"></a>AC25：Frontend Unit/Browser Mock、正式build和少量Real Full-stack Golden Path：浏览器创建计划→真实API→PG→Scheduler Run→冻结快照，覆盖full/adaptive接线；Mock不冒充真实链。

<a id="AC26"></a>AC26：同步受影响正式Product/Blueprint/Collection/模块文档与操作/回滚事实，完整保留36节原方案和逐AC追溯；Completion Audit重读上游且反向核对入口/实现/结果，两阶段独立Review无阻塞项。

<a id="AC27"></a>AC27：从最新main创建本地任务分支，Issue/Change/首个治理或失败测试提交/首次push/早期PR稳定关联；本地验证和current-head/current-base required CI满足后按用户授权guarded merge远程main，必要管理员权限仅按实际授权规则使用。

<a id="AC28"></a>AC28：合并后main-fresh和原生Change归档/同ID done得到确认，按直接Evidence回写Issue AC并重读关闭、安全清理任务资源；无Release/Deploy/生产Migration授权，未验证边界如实报告。

## 已批准方案原文

可以。结合前面所有决定，我建议把这次任务定义为一个完整的 **“TikHub 采集计划产品化改造”**，而不是单独改弹窗或评论开关。

核心目标有四个：

1. **“采集计划”成为未来多种采集计划的统一容器**；
2. 当前现有这一类明确命名为 **TikHub 采集计划**；
3. **新建/编辑 TikHub 采集计划改用弹窗，不再使用抽屉**；
4. 评论采集正式支持 **自适应采集 / 全量采集**，并把真实规则告诉用户。

---

# 一、最终产品形态

页面结构保持：

```text
采集策略
├─ 关键词包
└─ 采集计划
```

但“采集计划”从现在开始是一个**上层业务概念**：

```text
采集计划
│
├─ TikHub 采集计划       ← 本次完整实现
│
├─ 未来：其他 API 采集计划
├─ 未来：账号监测计划
├─ 未来：其他数据源采集计划
└─ ...
```

因此右上角当前按钮明确改成：

> **新建 TikHub 采集计划**

UI 文案统一使用官方风格 `TikHub`，不要在界面上写全大写 `TIKHUB`。

目前只有一种计划类型，所以：

```text
点击“新建 TikHub 采集计划”
→ 直接打开 TikHub 计划弹窗
```

**不要现在做一个“请选择采集计划类型”的中间弹窗。**

等第二种真实计划出现后，再把按钮升级为下拉菜单：

```text
+ 新建采集计划
   ├─ TikHub 采集计划
   └─ XXX 采集计划
```

---

# 二、新建/编辑：统一改成弹窗

当前 `PlanCreateDrawer.vue` 不再继续作为创建表单。

当前仓库已经有：

```text
frontend/src/shared/ui/AimaModalContainer.vue
```

它本身就适合复杂配置弹窗：

- 固定 Header；
- 固定 Footer；
- 中间 Body 独立滚动；
- 支持关闭禁用；
- 支持焦点恢复；
- 有统一遮罩；
- 有视口高度限制。

因此**不要再新建第三套 Modal 基础组件**。

建议：

```text
PlanCreateDrawer.vue
        ↓
TikHubPlanDialog.vue
```

使用：

```text
AimaModalContainer
```

而不是 `AimaDrawer`。

---

# 三、创建和编辑都用同一个 Modal

虽然你这次明确说的是“新建不要用抽屉”，但从当前代码来看，创建和编辑使用的是同一套表单字段。

因此最干净的做法是：

```text
新建 TikHub 采集计划
→ TikHubPlanDialog

编辑 TikHub 采集计划
→ 同一个 TikHubPlanDialog
```

通过：

```text
initialPlan == null
→ create

initialPlan != null
→ edit
```

区分。

这样避免以后出现：

```text
创建表单一套
编辑表单另一套
```

逐渐漂移。

而：

> **查看采集计划详情**

仍然保留 Drawer。

最终交互就是：

```text
创建 / 编辑
→ Modal

查看详情
→ Drawer
```

这个职责划分更合理。

---

# 四、TikHub Modal 的尺寸和布局

不建议做成很窄的小弹窗，因为当前配置已经包含：

- 计划名称；
- 关键词包；
- 品牌；
- 五个平台；
- 每个平台 Search 参数；
- 评论策略；
- 执行频率；
- 启用状态。

建议：

```text
width ≈ 960px
height ≈ 820px
```

实际继续由 `AimaModalContainer` 限制为：

```text
min(指定尺寸, viewport - 48px)
```

### 结构

```text
┌──────────────────────────────────────────┐
│ 新建 TikHub 采集计划                ×   │
│ 通过 TikHub 按关键词持续发现并采集内容   │
├──────────────────────────────────────────┤
│                                          │
│  1. 基本信息                             │
│                                          │
│  2. 搜索条件 · 关键词包                  │
│                                          │
│  3. 内容过滤 · 品牌                      │
│                                          │
│  4. 目标平台                             │
│                                          │
│  5. 评论采集策略                         │
│                                          │
│  6. 执行频率                             │
│                                          │
│  7. 创建后启用                           │
│                                          │
│  TikHub费用提示                          │
│                                          │
├──────────────────────────────────────────┤
│                         取消   保存计划  │
└──────────────────────────────────────────┘
```

Header/Footer 固定，中间内容自己滚动。

**不要做 Wizard / 上一步下一步。**

现在字段数量还没复杂到必须分步骤，Wizard 会增加用户修改配置时的操作成本。

---

# 五、Modal 内部布局不要照搬原 Drawer

510px Drawer 是纵向长表单。

改成 960px Modal 后应该利用空间。

## 1. 基本信息

两列：

```text
计划名称                         执行频率
[____________________]          [每6小时 ▼]
```

启用状态放这一组右侧或末尾。

---

## 2. 关键词包和品牌

可以两列布局：

```text
搜索条件 · 关键词包             内容过滤 · 品牌

☑ 品牌词包                     ○ 全部启用品牌
☑ 竞品词包                     ● 指定品牌
                               [爱玛] [雅迪] [...]
```

---

## 3. “采集渠道”改名为“目标平台”

这是前面已经发现的概念问题。

现在：

> 采集渠道 → 小红书 / 抖音 / 微博

这个名称不准确。

真正关系是：

```text
计划类型 / Provider
→ TikHub

目标平台
→ 小红书
→ 抖音
→ 微博
→ B站
→ 快手
```

所以 UI 改成：

> **目标平台**

平台卡片例如：

```text
┌ 小红书 ────────────────────────────────┐
│ ☑ 已启用                               │
│ 排序：[最新]  时间：[一天内] 类型：[全部] │
└────────────────────────────────────────┘
```

五个平台按 2 列排列，大屏两列，小屏退化单列。

未选择的平台不展开参数。

---

# 六、评论采集策略成为正式配置

增加：

## 5. 评论采集策略

使用两个 Radio Card，而不是 Select。

### 自适应采集（推荐）

文案明确告诉用户：

> 适合持续舆情监测，在数据完整度和 TikHub 调用量之间平衡。

并展示：

```text
一级评论：
评论数 ≤ 50 时尽量完整采集；
评论数 > 50 时默认最多采集 50 条。

二级回复：
每条一级评论默认最多采集 5 条。

后续刷新：
评论数没有变化时通常不会重复采集；
支持可靠增量的平台优先只采新增评论。
```

当前已确认：

```text
小红书
B站
```

支持可靠最新评论增量。

---

## 全量采集

文案：

> 尽量采集每个帖子下全部一级评论和二级回复。

说明：

```text
系统会持续翻页，
直到 TikHub / 平台明确返回结束。

已经完整采集且评论没有变化时，
不会每个周期重新全量采集。

出现新增评论后，
系统根据平台能力增量补齐或重新完整刷新。
```

同时展示 Warning：

> 全量采集可能产生显著更多 TikHub 请求和费用。当前系统没有请求次数或金额预算上限。

---

# 七、“全量”必须有准确语义

这里不能给用户错误承诺。

全量的定义应该是：

> **完整度目标 = 全部可获取的一级评论 + 全部可获取的二级回复。**

但受：

```text
TikHub 实际返回范围
平台权限
删除/隐藏评论
分页能力
技术安全上限
```

限制。

因此说明里明确：

> 若达到技术安全上限或 Provider 无法继续分页，系统会记录为“部分采集”，不会误标为完整。

当前：

```text
MAX_COMMENT_PAGES = 100
MAX_SUB_COMMENT_PAGES = 100
```

继续保留。

---

# 八、Plan Type 从现在正式进入领域模型

不能只改 UI 名称。

给：

```text
collection_plans
```

增加：

```text
plan_type
```

当前：

```text
plan_type = "tikhub"
```

即：

```python
CollectionPlanType = Literal["tikhub"]
```

所有现有 Plan Migration 后：

```text
plan_type = tikhub
```

行为不发生变化。

---

# 九、为什么 `plan_type` 不能通过 Provider 推断

以后完全可能出现：

```text
TikHub 关键词监测计划
TikHub 账号监测计划
```

它们 Provider 都可能是：

```text
tikhub
```

但业务计划不是一回事。

所以：

```text
plan_type
```

必须是业务一级事实，而：

```text
provider=tikhub
```

只是执行依赖。

不要写：

```text
if provider == tikhub:
    plan_type = ...
```

这种反推机制。

---

# 十、Collection Plan 成为父模型

最终建议：

```text
CollectionPlan
│
├─ id
├─ plan_type
├─ name
├─ enabled
├─ schedule
├─ schedule_version
├─ next_run_at
├─ created_at
└─ updated_at
       │
       └── type-specific configuration
```

当前：

```text
plan_type=tikhub
        │
        ├─ keyword packs
        ├─ brands
        ├─ platforms
        ├─ provider config
        ├─ search configs
        ├─ detail policy
        └─ comment policy
```

未来新的 plan type 拥有自己的配置。

---

# 十一、不要把所有未来配置塞进一个巨型 Contract

必须避免：

```text
CollectionPlanCreateRequest
├─ keyword_pack_ids?
├─ account_ids?
├─ urls?
├─ tikhub_config?
├─ other_provider_config?
├─ crawler_config?
...
```

最终 Optional 字段越来越多。

建议现在至少在领域/API 层明确：

```text
通用 Plan
+
TikHub Plan Config
```

例如语义上：

```text
CollectionPlanSummaryResponse
→ 通用列表字段

TikHubCollectionPlanResponse
→ TikHub 详细配置
```

详情未来可以自然升级为：

```text
CollectionPlanDetailResponse
= TikHubCollectionPlanResponse
| FutureCollectionPlanResponse
```

以：

```text
plan_type
```

作为 discriminator。

---

# 十二、现有数据库子表暂时不要重命名

当前已有：

```text
collection_plan_platforms
collection_plan_keyword_packs
collection_plan_brands
collection_plan_decision_policies
```

不要为了未来扩展，现在就大规模改名为：

```text
tikhub_collection_...
```

没有必要。

只需要建立约束：

> 当前这些关联配置只适用于 `plan_type=tikhub`。

以后其他 Plan 增加自己的专属表。

这比现在做大规模 Schema 重构更稳。

---

# 十三、Scheduler 必须按 Plan Type 分发

不能让 `plan_type` 只存在于页面。

当前 Scheduler 本质默认所有计划都走现有 TikHub Discovery Pipeline。

需要改成：

```text
Collection Plan
        ↓
plan_type
        ↓
dispatch

tikhub
→ 当前 TikHub Scheduler / Scope / Provider Pipeline

future
→ 对应自己的 executor
```

未知类型：

```text
fail closed
```

不能错误进入 TikHub。

---

# 十四、Run Snapshot 增加 Plan Type

现在 Snapshot 已经冻结：

```text
plan_id
plan_name
schedule_version
detail_policy
comment_policy
decision_policy
platforms
keywords
...
```

增加：

```text
plan_type = tikhub
```

新 Run 必须有：

```text
schema_version
plan_type
plan_id
schedule_version
comment_policy
...
```

---

# 十五、历史 Run 不重写

已经存在的旧：

```text
collection-run-config.v2
```

可能没有：

```text
plan_type
```

不要为了这次改造重写所有历史 JSON Snapshot。

兼容逻辑可以限定为：

```text
旧 v2 snapshot
+ plan_type 缺失
→ legacy interpretation = tikhub
```

仅为了历史兼容。

所有新 Run：

```text
plan_type
```

必须显式存在。

---

# 十六、评论策略 Contract

现状：

```python
comment_policy: Literal["adaptive"]
```

改为：

```python
Literal[
    "adaptive",
    "full",
]
```

默认：

```text
adaptive
```

已有 Plan 全部继续 adaptive。

因此升级不会突然造成大量 TikHub 调用。

---

# 十七、`decision_policy` 与 `comment_policy` 的关系

当前系统同时有：

```text
collection_plans.comment_policy
```

以及：

```text
collection_plan_decision_policies.policy.comment_mode
```

不要再增加第三份规则。

明确：

```text
comment_policy
→ 用户选择的高层业务策略

decision_policy
→ 该策略所使用的执行参数
```

其中必须保证：

```text
comment_policy == decision_policy.comment_mode
```

或者由创建逻辑单向生成。

不能允许它们独立修改后出现：

```text
Plan = full
Policy = adaptive
```

---

# 十八、Comment Action 增加 `fetch_full`

现在：

```text
fetch_adaptive
fetch_incremental
refresh_controlled
probe_first_page
...
```

增加：

```text
fetch_full
```

这样：

```text
Plan = full
→ Decision = fetch_full
```

数据库和排障都能清楚看到为什么进行了大量分页。

同步：

```text
collection_content_actions.comment_action
```

数据库 Check Constraint。

需要正式 Alembic Migration。

---

# 十九、全量采集必须同时考虑一级和二级 Coverage

这是此次不能遗漏的关键点。

“帖子全部评论”不是：

```text
一级评论 complete
```

就够了。

必须满足：

```text
一级评论 coverage = complete

AND

需要采集的二级回复线程全部 complete
```

因此 Full Mode 下一篇内容的完整状态应该由现有 Coverage 数据派生：

```text
FullCommentCaptureState
├─ root_coverage
├─ incomplete_reply_thread_count
└─ full_capture_complete
```

建议**优先从现有 root/thread coverage observation 聚合得到**。

不要一开始就新建一套“complete boolean”表。

只有实际查询性能证明有必要，再做 materialized summary。

---

# 二十、Full Mode 决策矩阵

## 新内容

```text
comment_count = 0
→ skip comments
→ complete
```

```text
comment_count > 0
→ fetch_full
```

---

## 评论数未知

Adaptive：

```text
probe_first_page
```

Full：

```text
fetch_full
→ 持续分页
```

不能第一页之后停止。

---

## 上一次全部完整 + 数量没变

```text
previous count = 300
current count = 300
full_capture_complete = true
```

结果：

```text
skip
```

这保证：

> 全量模式 ≠ 每 6 小时重新全抓。

---

## 上一次不完整 + 数量没变

```text
previous count = 300
current count = 300
full_capture_complete = false
```

结果：

```text
继续补齐
```

不能因为 count 没变化就 skip。

---

# 二十一、小红书 / B站：完整数据后的增量

当前两者：

```text
supports_incremental_comment_sort = true
```

如果：

```text
previous full_capture_complete = true
comment_count 300 → 315
```

可以：

```text
从最新开始
→ ingest 新评论
→ 遇到稳定 known comment boundary
→ 停止
```

这种情况下：

```text
旧 300 完整
+
新增部分完整
=
当前仍完整
```

所以 Full 模式不能像当前普通 incremental 一样一律写：

```text
coverage = partial
```

在满足完整增量证明条件时应该继续：

```text
coverage = complete
```

---

# 二十二、抖音 / 微博 / 快手

当前无法证明可靠 newest-first 增量。

Full Mode：

```text
之前 complete
+
comment_count 改变
        ↓
受控重新分页
        ↓
Stable ID 去重
        ↓
Provider exhausted
```

不能偷偷退回 Adaptive 的 50 条。

---

# 二十三、二级回复也要自适应刷新，不能每次重抓

还有一个容易造成大量费用的问题。

对于 Full Mode：

```text
某一级评论之前：
reply_count = 20
thread coverage = complete

本次：
reply_count = 20
```

即使因为平台不支持一级评论增量而重新遍历到了这条 root comment，也应该：

```text
skip 该 thread
```

不要重新抓 20 个回复。

如果：

```text
reply_count 20 → 24
```

或者：

```text
thread coverage = partial
```

才继续补齐。

所以 Full 模式的优化应该覆盖：

```text
内容级 comment_count
+
root coverage
+
每条 root 的 reply_count
+
thread coverage
```

这才能真正做到：

> **追求完整，但避免重复费用。**

---

# 二十四、复用 Supplement 的 Full Capture

当前代码已有：

```python
full_capture = mode in {
    "batch_supplement",
    "content_supplement",
    "date_supplement",
}
```

不要重新实现一套 Plan Full Loop。

统一为类似：

```text
requires_full_comment_capture(run)
```

判断：

```text
Batch Supplement
→ true

Content Supplement
→ true

Date Supplement
→ true

TikHub Plan + comment_policy=full
→ true

TikHub Plan + comment_policy=adaptive
→ false
```

然后所有模式继续复用：

```text
_fetch_comments
_fetch_sub_comments
advance_comments
advance_sub_comments
Mapper
Canonical
Ingestion
Coverage
```

---

# 二十五、编辑 Full/Adaptive 只影响未来 Run

例如：

```text
Plan 原来 adaptive
→ 用户编辑成 full
```

行为：

```text
未来新创建的 Run
→ full

历史 Run
→ 仍按原 Snapshot解释
```

**不能自动启动历史数据全量补采。**

历史数据补齐继续使用：

```text
声音广场 → 评论补采
日期补采
批次补采
```

这样避免用户只是改配置，却突然产生巨额 TikHub 请求。

---

# 二十六、采集计划列表同步改造

未来这里会放多种 Plan，所以表格不要再过度 TikHub-specific。

建议：

| 列 | 内容 |
|---|---|
| 计划名称 | 名称 + 简要范围 |
| 类型 | `TikHub` Badge |
| 状态 | 已启用 / 已停用 |
| 采集范围 | TikHub 当前显示关键词包、品牌、平台摘要 |
| 采集策略 | 自适应 / 全量 |
| 调度与下次运行 | 每6小时 / 时间 |
| 操作 | 详情 / 启停 |

不要继续把：

> “目标平台”

作为顶层通用列表列。

因为未来其他 Plan 可能根本没有“平台”。

---

# 二十七、计划详情仍然使用 Drawer

详情 Drawer 改成上层通用壳：

```text
PlanDetailDrawer
        │
        └─ plan_type=tikhub
              ↓
          TikHubPlanDetail
```

当前详情展示：

```text
计划类型        TikHub
状态            已启用
执行频率        每6小时
下次运行        ...
```

TikHub 专属：

```text
关键词包
品牌范围
目标平台
搜索参数
评论采集策略
```

---

# 二十八、Full / Adaptive 详情必须写真实行为

Adaptive：

```text
评论策略
自适应采集

一级评论
≤50 尽量完整
>50 默认最多 50 条

二级回复
每条一级评论默认最多 5 条
```

Full：

```text
评论策略
全量采集

一级评论
尽量全部

二级回复
尽量全部

刷新方式
完整且无变化不重复采集；
有新增时按平台能力增量或完整刷新
```

---

# 二十九、Migration

本次至少需要正式 Migration。

## `collection_plans`

新增：

```text
plan_type TEXT NOT NULL
```

迁移：

```text
既有 Plan
→ tikhub
```

然后加：

```text
CHECK plan_type IN ('tikhub')
```

未来新类型通过新 Migration 扩展。

---

## `collection_content_actions`

扩展：

```text
comment_action
```

允许：

```text
fetch_full
```

---

## Decision Policy

允许：

```text
comment_mode:
adaptive | full
```

旧 Plan：

```text
adaptive
```

不改变历史行为。

---

# 三十、前端具体修改范围

至少涉及：

```text
frontend/src/features/collection-strategy/
```

重点：

### `CollectionStrategyPage.vue`

改：

```text
新建采集计划
→ 新建 TikHub 采集计划
```

状态从：

```text
planDrawerOpen
```

改成类似：

```text
tikhubPlanDialogOpen
```

---

### 删除 / 替换

```text
PlanCreateDrawer.vue
```

替换为：

```text
TikHubPlanDialog.vue
```

内部使用：

```text
AimaModalContainer
```

---

### `PlanPanel.vue`

增加：

```text
计划类型
采集策略
```

调整“采集范围”表达。

---

### `PlanDetailDrawer.vue`

改成：

```text
通用 Plan detail shell
+
TikHub-specific detail
```

至少明确显示：

```text
plan_type
comment_policy
```

---

### `store.ts`

支持：

```text
plan_type
comment_policy
```

创建、编辑、复制、列表、详情全部 round-trip。

---

### generated client

必须：

```text
OpenAPI
→ regenerate TS client
```

不能手改 generated 文件。

---

# 三十一、后端主要修改范围

重点包括：

```text
backend/src/aima_ugc/contracts/http.py

backend/src/aima_ugc/contracts/collection/models.py

backend/src/aima_ugc/modules/collection/planning.py

backend/src/aima_ugc/modules/collection/decision.py

backend/src/aima_ugc/modules/collection/tables.py

backend/src/aima_ugc/modules/collection/corrective_tables.py

backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py

backend/src/aima_ugc/bootstrap/collection_strategy_http.py

backend/src/aima_ugc/bootstrap/scheduler.py

backend/src/aima_ugc/bootstrap/collection_scope.py
```

以及对应 Migration、tests 和 generated Contract。

---

# 三十二、不要做的东西

这次不要扩大到：

- 不真正新增第二个采集 Plan 类型；
- 不新增第二个 Provider；
- 不提前设计所有未来采集方式；
- 不重命名全部 Collection 数据表；
- 不创建万能 JSON 配置仓库；
- 不移除 100 页技术安全上限；
- 不修改 TikHub 当前 endpoint；
- 不增加 Budget Account / Cost Guard；
- 不让 Plan 编辑触发历史补采；
- 不复制已有 Supplement 分页逻辑；
- 不在普通 CI 真调用付费 TikHub。

---

# 三十三、Codex 必须覆盖的测试

## A. Plan Type

```text
旧 Plan migration → tikhub

新建 TikHub Plan
→ plan_type=tikhub

Plan List
→ TikHub

Plan Detail
→ TikHub

Run Snapshot
→ tikhub

未知 plan_type
→ fail closed
```

---

## B. Modal

必须 Browser 测：

```text
点击“新建 TikHub 采集计划”
→ 中央 Modal
→ 不再出现右侧 Drawer

Header 固定
Footer 固定
Body 可滚动

保存时不能重复提交
取消正常关闭
编辑正常回显
保存后列表刷新
```

Modal 内滚动继续使用项目统一的低干扰滚动条风格，不产生粗黑滚动条。

---

## C. Adaptive 回归

现有行为不能坏：

```text
30 comments
→ target=30

500 comments
→ target=50

30 replies
→ target=5

comment count unchanged
→ skip
```

---

## D. Full

```text
500 comments
→ 不在 50 停止

30 replies
→ 不在 5 停止

comment_count unknown
→ 不在第一页停止

Provider exhausted
→ complete
```

---

## E. Coverage

```text
root complete
+ all required reply threads complete
→ full_capture_complete=true

root partial
→ false

任意需要的 reply thread partial
→ false
```

---

## F. Refresh

```text
complete + count unchanged
→ skip

partial + count unchanged
→ continue

complete + count increased + XHS/Bilibili
→ safe incremental

complete + count increased + Douyin/Weibo/Kuaishou
→ controlled full refresh
```

---

## G. Page limit

```text
100 pages reached
→ partial
→ stop_reason=page_limit
```

绝不能标成 complete。

---

# 三十四、验证层次

Codex 最终至少应该取得：

```text
Domain / Decision Unit
→ adaptive/full/coverage/reply refresh

Contract
→ Pydantic
→ OpenAPI
→ generated TS client

PostgreSQL Integration
→ Migration
→ legacy backfill
→ create/read/update

Scheduler Integration
→ plan_type/comment_policy frozen into Run Snapshot

Collection Integration
→ full/adaptive execution decisions

Frontend Unit / Browser Mock
→ Modal
→ create/edit
→ type/comment strategy
→ list/detail

Real Full-stack Golden Path
→ Browser 创建 TikHub Plan
→ API
→ PostgreSQL
→ Scheduler Run
→ Snapshot 正确
```

不需要用真实 TikHub 作为普通 CI 证明。

---

# 三十五、建议 Codex 按这个顺序开发

```text
1. 建立 Requirement / Change
        ↓
2. plan_type Contract
        ↓
3. Migration + Repository
        ↓
4. TikHub Plan Domain
        ↓
5. comment_policy adaptive/full
        ↓
6. Coverage-aware Decision
        ↓
7. 统一 Full Capture
        ↓
8. Scheduler Dispatch + Snapshot
        ↓
9. OpenAPI / generated client
        ↓
10. TikHubPlanDialog Modal
        ↓
11. Plan List / Detail
        ↓
12. Browser + Backend + PostgreSQL 回归
        ↓
13. Full-stack Golden Path
        ↓
14. Docs / Review / PR Ready
```

---

# 三十六、最终完成定义

这次不能以：

> “创建页面已经改成弹窗了”

作为完成。

真正 Done 必须同时满足：

```text
“采集计划”已经成为多类型父概念
+
现有计划明确为 TikHub
+
旧 Plan 全部安全迁移
+
新 Run 明确冻结 plan_type
+
未知类型不会误走 TikHub
+
新建/编辑 TikHub 计划使用 Modal
+
详情仍使用 Drawer
+
UI 明确解释 Adaptive 真实规则
+
用户可选择 Full
+
Full 覆盖一级评论 + 二级回复
+
完整状态考虑 root + reply thread coverage
+
已完整且无变化不会周期性重复抓
+
Partial 即使 count 不变仍继续补齐
+
安全增量不会错误降为 partial
+
Supplement 与 Plan Full 共用生产分页实现
+
达到安全上限明确记录 partial
+
所有历史 Run 语义保持冻结
```

这套方案完成后，你后面再增加其他采集计划时，新增的是一个新的 **`plan_type + 类型专属配置 + executor + 创建 Modal`**；“采集策略 → 采集计划”这个上层结构不需要再次推翻。
