---
schema: coding-change/v1
id: CHG-20261002-141617-workbench-ui-stability
title: 工作台与声音广场展示稳定性、自适应和全站滚动条整改
level: L3
status: in_progress
owner: codex
branch: fix/692-workbench-ui-stability
created: 2026-10-02T14:16:17+08:00
updated: 2026-10-02T14:16:17+08:00
completion_gate: required
depends_on: []
affected_areas:
  - "workbench"
  - "voice-plaza"
  - "shared-ui"
  - "contracts"
  - "docs"
affected_paths:
  - "backend/src/aima_ugc/contracts/workbench.py"
  - "backend/src/aima_ugc/bootstrap/workbench_http.py"
  - "backend/src/aima_ugc/adapters/persistence/postgres/workbench.py"
  - "backend/src/aima_ugc/modules/workbench"
  - "frontend/src/features/workbench"
  - "frontend/src/features/voice-plaza"
  - "frontend/src/shared"
  - "frontend/src/app"
  - "frontend/tests"
  - "frontend/e2e"
  - "frontend/fullstack"
  - "tests/api/test_workbench.py"
  - "tests/integration/content/test_workbench_runtime.py"
  - "tests/unit/workbench"
  - "contracts"
  - "docs/product"
  - "docs/blueprint"
  - "docs/guides"
contracts:
  - "WorkbenchMindResponse"
  - "WorkbenchMindDimensionResponse"
  - "WorkbenchMindSecondaryResponse"
  - "WorkbenchLayoutModule"
  - "WorkbenchLayoutUpdateRequest"
data_changes:
  - "workbench_snapshots.response"
  - "workbench_layouts.layout"
---

# 变更摘要

按 [Issue #692](https://github.com/dingyuwen777/AIMA_UGC/issues/692) 的最终用户决定统一整改工作台、声音广场及共享滚动区域。完整原始文字及修订顺序由上游 Issue 附录持有；本 Change 保存施工映射与证据，不能作为需求全集。

# 背景、现状与问题

## 背景

用户明确要求完整实施引用方案、持久长期目标、本地验证后合并远程 main，必要时管理员。后续修订优先：单行横向筛选、6小时普通聚合刷新、全站弱存在感 scrollbar。

## 当前现状

基线为 `0a8f6b4c0acf92a2d5e227cc0c79130cffb4c0dd`。Contract 接受4–12列，Mind SQL仍以作者去重，Workbench默认30日且全品牌，品牌车型在多个消费方加载。现有 AI fingerprint watch 和持久快照 Job 已存在。

## 问题、根因或约束

作者ID口径使缺作者帖子不能正常计占比；refresh-note插入/删除和 options loading 状态映射改变现有可见UI。持久JSONB旧snapshot不能直接按新Contract读取；普通刷新6h必须保留独立pending快照跟进，避免 preparing/refreshing 长期不更新。

## 不修改的后果

当前用户报告的占比、布局和后台刷新视觉偏差持续存在；仅减少周期频率不能切断闪烁机制。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Mind SQL使用distinct author_account_id | backend/src/aima_ugc/adapters/persistence/postgres/workbench.py | 转为content统计并同步Contract |
| E2 | 布局允许4列、默认6×48 | backend/src/aima_ugc/contracts/workbench.py；bootstrap/workbench_http.py | 新写约束和旧读归一化分离 |
| E3 | 已有持久JSONB snapshot及AI刷新watch | backend/src/aima_ugc/bootstrap/workbench_http.py；frontend/src/features/workbench/pages/WorkbenchPage.vue | 缓存身份升级、pending跟进，复用既有事件 |
| E4 | 初始工作区干净，远程main已fetch同基线 | git status；git fetch origin main；git worktree add | 独立checkout保留原工作区 |

## 推断与待确认

仓库外消费者尚不能仅由全仓搜索证明不存在；在Contract变更前调查正式文档/调用方/部署事实。几何与滚动条仍需真实Browser测量。所有尚未执行验证保持未满足。

# 目标、成功标准与非目标

## 目标

正确内容心智、稳定刷新和交互、统一默认筛选与自由布局、全站符合AIMA视觉的滚动条。

## 成功标准

唯一完成标准为上游 [Issue #692](https://github.com/dingyuwen777/AIMA_UGC/issues/692) 的AC1–AC52，逐项直接证据见需求追溯；不得由本Change生成第二套成功标准。

## 范围

工作台后端统计/布局/快照兼容、三卡/store、声音广场/store/filter/taxonomy/list、共享品牌车型目录/picker、全站scrollbar与相关refresh审计；对应生成链/测试/文档及PR交付。

## 非目标

不升级依赖，不改AI语义或生产数据，不执行Release/Deploy，不无关重构，不创建重型Refresh框架。

## 必须保持不变

模块Owner/持久Job/Secret与权限；AI/Export/building实时轮询；Voice Plaza独立reset及完整deep-link；原用户工作区/在用数据库/服务。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 业务行为 | 最终用户方案统一实施 | #692 / AC1–AC52 | 见逐项追溯 |
| 统一目录Owner | 共享SWR store，消费方不重复HTTP | #692 / AC26 | frontend/shared |
| Contract兼容 | 调查消费者后rename或deprecated迁移；旧snapshot独立身份 | #692 / AC40 | 后端/生成Client/缓存 |
| 数据与迁移 | 计划无Schema迁移，旧布局读时归一化 | #692 / AC33, AC36 | 不改用户现存布局事实 |
| 部署与回滚 | 同版本前后端集成，新缓存身份；回滚代码与旧缓存不混读 | E2/E3 | 仅合并，未授权部署 |

# 修改方案与决策依据

## 最小充分方案

1. 后端统计/layout与snapshot身份 → content统计和严格新写、兼容旧读 → API/PostgreSQL/Contract Red→Green及生成漂移。
2. Shared catalog/SWR和Workbench默认/fencing → 先reference后同查询bootstrap、品牌车型联动、固定几何refresh → Store/Component延迟、失败、race。
3. 三卡日期/合法resize/radar文本测量/6h周期+pending跟进 → 同结构自适应和及时更新 → Browser几何/9标签/六尺寸矩阵。
4. Voice Plaza options/taxonomy/list/picker → 已有值保留和交互不丢失 → Browser请求中间状态/scroll/deep-link。
5. 全站scrollbar token/utility与有界polling审计 → 弱存在感，适当gutter → Workbench/Voice/Admin/配置Browser视觉/geometry。
6. 同步正式文档 → Completion Audit/独立Review/changed-scope CI → 当前Head/Base合并、main-fresh、原生Archive、逐AC Closure及cleanup。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1 | 不依赖作者ID才能满足帖子心智 |
| D2 | E3 | 状态语义和固定几何切断刷新闪烁，6h仅是周期策略 |
| D3 | E2 | 不为用户布局偏好引入Schema迁移 |

## 备选方案与取舍

局部修改spinner/频率不能满足目录、Query fencing与缓存兼容，弃用。重型全局Refresh框架增加迁移和维护成本，用户明确不需要。采用现有Feature Store保留成功值、共享目录唯一Owner及局部稳定状态，是当前完整要求下机制较少的方案。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 三个 Workbench Card 均可自由排序和 Resize | #692 / AC1 | not_satisfied | 开发中，未取得当前实现证据 |
| R2 | 尺寸范围 `6–12列 × 48–160行` | #692 / AC2 | not_satisfied | 开发中，未取得当前实现证据 |
| R3 | Workbench 默认品牌为爱玛，可多选其他品牌 | #692 / AC3 | not_satisfied | 开发中，未取得当前实现证据 |
| R4 | 默认日期为北京时间昨天结束的最近完整7天 | #692 / AC4 | not_satisfied | 开发中，未取得当前实现证据 |
| R5 | 品牌变化自动清理失效车型 | #692 / AC5 | not_satisfied | 开发中，未取得当前实现证据 |
| R6 | Sound Filter 顺序严格按已确认顺序 | #692 / AC6 | not_satisfied | 开发中，未取得当前实现证据 |
| R7 | Sound Filter 允许水平滚动 | #692 / AC7 | not_satisfied | 开发中，未取得当前实现证据 |
| R8 | Scrollbar 使用细、浅、AIMA 色系样式 | #692 / AC8 | not_satisfied | 开发中，未取得当前实现证据 |
| R9 | 三张 Workbench Card 右上日期一致 | #692 / AC9 | not_satisfied | 开发中，未取得当前实现证据 |
| R10 | Brand Mind 改为 content-based 心智占比 | #692 / AC10 | not_satisfied | 开发中，未取得当前实现证据 |
| R11 | 多标签帖子可进入多个一级维度 | #692 / AC11 | not_satisfied | 开发中，未取得当前实现证据 |
| R12 | 9 个一级标签在最小尺寸下完整易读、单行优先 | #692 / AC12 | not_satisfied | 开发中，未取得当前实现证据 |
| R13 | Brand Mind 在所有合法尺寸始终左右布局 | #692 / AC13 | not_satisfied | 开发中，未取得当前实现证据 |
| R14 | UGC Trend 在所有合法尺寸始终左右布局 | #692 / AC14 | not_satisfied | 开发中，未取得当前实现证据 |
| R15 | Radar 中心正确反映单品牌/多品牌/全部品牌 | #692 / AC15 | not_satisfied | 开发中，未取得当前实现证据 |
| R16 | Brand Mind / Trend 默认正常状态没有可见内部 Scrollbar | #692 / AC16 | not_satisfied | 开发中，未取得当前实现证据 |
| R17 | Workbench 自动后台刷新为 6 小时 | #692 / AC17 | not_satisfied | 开发中，未取得当前实现证据 |
| R18 | 首次加载、用户筛选、重试、AI完成仍及时刷新 | #692 / AC18 | not_satisfied | 开发中，未取得当前实现证据 |
| R19 | Workbench Background Refresh 不清空现有内容 | #692 / AC19 | not_satisfied | 开发中，未取得当前实现证据 |
| R20 | Workbench Background Refresh 不插入造成布局变化的提示行 | #692 / AC20 | not_satisfied | 开发中，未取得当前实现证据 |
| R21 | Workbench refresh 失败保留最近成功数据 | #692 / AC21 | not_satisfied | 开发中，未取得当前实现证据 |
| R22 | Voice Plaza Filter Options Background Refresh 保留现有情感/发声/标签 | #692 / AC22 | not_satisfied | 开发中，未取得当前实现证据 |
| R23 | Voice Plaza 动态筛选刷新期间不 disabled、不切“加载中” | #692 / AC23 | not_satisfied | 开发中，未取得当前实现证据 |
| R24 | Voice Plaza Filter Options 失败保留最近成功目录 | #692 / AC24 | not_satisfied | 开发中，未取得当前实现证据 |
| R25 | Taxonomy 后台刷新失败不清空最近成功 Taxonomy | #692 / AC25 | not_satisfied | 开发中，未取得当前实现证据 |
| R26 | 品牌/车型目录使用共享 SWR Owner，不因页面刷新显示 fallback 文案 | #692 / AC26 | not_satisfied | 开发中，未取得当前实现证据 |
| R27 | 品牌后台 refresh 时“爱玛”文字全程稳定 | #692 / AC27 | not_satisfied | 开发中，未取得当前实现证据 |
| R28 | 一级/二级 Picker 在刷新过程中保持打开和当前 draft | #692 / AC28 | not_satisfied | 开发中，未取得当前实现证据 |
| R29 | Voice Plaza 列表后台刷新保留当前窗口，不整表闪白 | #692 / AC29 | not_satisfied | 开发中，未取得当前实现证据 |
| R30 | 后台 Refresh 不重置页面/筛选器滚动位置 | #692 / AC30 | not_satisfied | 开发中，未取得当前实现证据 |
| R31 | 用户主动 Query Change 不展示旧 Query 数据，但容器几何保持稳定 | #692 / AC31 | not_satisfied | 开发中，未取得当前实现证据 |
| R32 | Cold Loading / Background Refresh / Query Change 三类状态有独立回归 | #692 / AC32 | not_satisfied | 开发中，未取得当前实现证据 |
| R33 | 历史 `<6列` 布局安全归一化 | #692 / AC33 | not_satisfied | 开发中，未取得当前实现证据 |
| R34 | OpenAPI / Generated Client / Docs 同步 | #692 / AC34 | not_satisfied | 开发中，未取得当前实现证据 |
| R35 | Build、targeted Unit、Browser、Backend Integration 当前 Head 全部有新鲜证据 | #692 / AC35 | not_satisfied | 开发中，未取得当前实现证据 |
| R36 | 声音流作为唯一 Workbench 全局筛选入口始终可见；前后端拒绝隐藏，旧隐藏布局读取时安全恢复，同时保留排序。 | #692 / AC36 | not_satisfied | 开发中，未取得当前实现证据 |
| R37 | 初次进入必须先取得目录和布局、解析爱玛业务身份及完整7天，再对同一筛选快照并发查询三模块一次；目录重验证不得覆盖用户主动品牌选择。 | #692 / AC37 | not_satisfied | 开发中，未取得当前实现证据 |
| R38 | Workbench Reset恢复爱玛+最近完整7天+其余全部；Voice Plaza Reset维持页面自身语义，两个页面只共享目录。 | #692 / AC38 | not_satisfied | 开发中，未取得当前实现证据 |
| R39 | Workbench→Voice Plaza完整deep-link携带已选维度/day/content_id，覆盖旧Session隐含条件，不出现隐藏筛选。 | #692 / AC39 | not_satisfied | 开发中，未取得当前实现证据 |
| R40 | 心智分母为当前筛选active Scheme relevant distinct content_id，无作者ID和同作者多帖均按帖子计；Contract消费者和旧snapshot payload兼容必须调查并验证。 | #692 / AC40 | not_satisfied | 开发中，未取得当前实现证据 |
| R41 | Workbench普通6h刷新保留声音流当前游标和遍历状态；休眠恢复仅过期补查，AI任务结果事件仍及时刷新。 | #692 / AC41 | not_satisfied | 开发中，未取得当前实现证据 |
| R42 | 全站页面、Workbench、声音广场、Table、Drawer、Dialog、Dropdown、Chart/长文本滚动区域使用统一scrollbar Design Token与复用scroll utilities；默认3–6px，透明/极浅轨道、浅粉灰thumb、999px圆角，hover/active轻微增强且不变粗。 | #692 / AC42 | not_satisfied | 开发中，未取得当前实现证据 |
| R43 | Chrome/Edge滚动条尺寸和颜色实际生效，同时提供Firefox thin/color兼容；禁止粗黑轨道、8px+滚动条和全局强制隐藏。 | #692 / AC43 | not_satisfied | 开发中，未取得当前实现证据 |
| R44 | 滚动条颜色来自现有AIMA token，禁止页面私自硬编码；声音筛选横向3–4px、卡内更淡、Drawer/Dialog约5px、Table约4px。 | #692 / AC44 | not_satisfied | 开发中，未取得当前实现证据 |
| R45 | 固定尺寸卡片、图表关联容器和Table按真实布局使用stable gutter，滚动条出现/消失不改变Mind/Trend/Radar宽度；不得无脑全局加gutter。 | #692 / AC45 | not_satisfied | 开发中，未取得当前实现证据 |
| R46 | 主要页面Workbench/Voice Plaza/Admin/配置的normal/hover/active滚动条和layout shift取得Browser视觉与几何证据。 | #692 / AC46 | not_satisfied | 开发中，未取得当前实现证据 |
| R47 | 对frontend/src自动刷新/polling可见路径完成有界审计；本范围已有成功值不得刷新闪烁，其他同类路径有实际问题时修复，不做无关重构或重型Refresh框架。 | #692 / AC47 | not_satisfied | 开发中，未取得当前实现证据 |
| R48 | 用户草稿/search/open/scroll与server目录隔离；失效候选可标记或提交时清理，后台目录刷新不得突然删除用户勾选。 | #692 / AC48 | not_satisfied | 开发中，未取得当前实现证据 |
| R49 | 合法Resize矩阵6×48/6×80/8×48/8×80/12×48/12×160全验证；当前9正式标签可读、实际measureText计算，异常超长在最低可读字号后可省略且tooltip/详情完整。 | #692 / AC49 | not_satisfied | 开发中，未取得当前实现证据 |
| R50 | 源会话完整文字方案、修订优先级、实施进展持久可追溯；旧事实按当前代码复核，图片未读取不冒充视觉事实。 | #692 / AC50 | not_satisfied | 开发中，未取得当前实现证据 |
| R51 | 本地分层验证、Completion Audit、独立Review、当前Head/Base相关CI全部收敛后合并远程main；管理员仅在已满足质量门禁且有效授权成立时必要使用。 | #692 / AC51 | not_satisfied | 开发中，未取得当前实现证据 |
| R52 | 合并后核验main-fresh CI、repository-native Change Archive、逐AC Closure Audit、Issue状态回写与安全cleanup；没有直接证据不得声明已交付。 | #692 / AC52 | not_satisfied | 开发中，未取得当前实现证据 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| backend Workbench Contract/HTTP/Repository/snapshot | 内容统计、布局旧读新写、缓存身份 | E1/E2/E3 | R2/R10/R33/R36/R40 |
| frontend Workbench/Voice Plaza/shared/app | 默认值、SWR、布局/图表、统一scrollbar | 用户决定 | R1–R50 |
| contracts/generated/tests/docs | 生成一致性、风险匹配回归、当前事实 | 公共边界 | R34/R35/R51/R52 |

- [x] 调查当前实现和事实源。
- [x] 建立任务路由与上游AC追溯。
- [ ] 行为变化建立失败证据。
- [ ] 完成实现与受影响文档。
- [ ] 取得验证、Completion Audit和独立Review。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Workbench/Voice/shared目录默认值、SWR、race/picker及后端统计/layout |
| 接口 / 契约 | required | Pydantic/OpenAPI/Orval与真实消费方兼容、旧缓存payload |
| 集成 / 持久化 / 运行依赖 | required | 隔离PostgreSQL：作者缺失/重复、多标签、active Scheme、快照Job/历史布局 |
| 用户 / 工作流验收 | required | Mock Browser请求前中后、失败、picker/scroll、全站scrollbar和几何矩阵 |
| 跨组件关键路径 | required | 少量Browser→真实API/PostgreSQL/Worker Workbench关键路径 |
| 外部依赖 / 供应方探测 | not_applicable | 本轮为内部查询/UI，不依赖TikHub或付费模型当前事实 |
| 构建 / 打包 / 运行 | required | 当前锁定工具链lint/typecheck/build |
| 文档 / 治理 / 其他 | required | Product/Blueprint/设计受影响事实、架构/Owner/Secret/Docs/Completion |

## 验证计划

先目标Red→Green，再模块回归；`python scripts/dev/validate_changed.py --base origin/main`复用唯一CI classifier。正式Ready必须本地风险匹配层、`python scripts/quality/check_change_completion.py --root . --require-active-ready`、独立Review及当前Head/Base CI。真实数据库与Browser端口均隔离。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | old snapshot、query race、Picker draft、ECharts可读几何 | 直接回归覆盖，不用截图最终状态代替中间状态 |
| 兼容性 | 内容字段同步生成客户端；外部消费者调查决定rename边界 | #692 / AC40 |
| 数据 / Migration | 计划无Schema迁移 | JSONB旧布局读归一化，新snapshot身份 |
| 部署 / 运行 | 同版本后端与前端，快照继续走既有Job | 本次不部署 |
| 回滚 / 恢复 | 回滚实现commit，缓存身份隔离可重建 | 不破坏Content/Analysis数据 |

# 文档、依赖、部署与发布影响

长期文档：Product用户行为、相关Blueprint查询/刷新/布局、shared styles README与设计工作流；以机器事实同步。依赖/Runtime不变。配置/Secret不变。没有Release/Deploy授权。Contract与仓库内消费者同步生成；仓库外消费者尚待事实调查。

# 完成审计

- [ ] upstream_re_read：重新读取live #692及完整最终方案。
- [ ] change_coverage：独立确认所有适用AC进入当前施工范围。
- [ ] reverse_audit：前后端、snapshot/Job、UI动作和验证层反向审计。
- [ ] unresolved_cleared：所有not_satisfied清零且处置有正式依据。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | baseline 0a8f6b4c；Windows | git status/fetch/worktree；live Issue create validation | 工作区干净，Issue校验PASS | 已建立真实上游需求和隔离本地分支 |

## 未验证内容与剩余风险

实施、测试、Review和CI尚未完成，本Change不Ready，禁止合并。

## 交付状态

本地分支 `fix/692-workbench-ui-stability` 已建立，首个提交/远程跟踪分支/早期PR尚待建立。合并、main-fresh、原生Change Archive、Issue Closure与cleanup未执行。Release/Deploy不在授权范围。

## 备注

主代理唯一Writer，独立只读preflight reviewer已发现旧缓存和pending快照风险。任务长期目标active；完整源方案作为#692末尾59,827字符正文保存，另有本会话持久原始JSON/Markdown。缺少图片像素明确未验证。
