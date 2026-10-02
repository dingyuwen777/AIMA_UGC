---
schema: coding-change/v1
id: CHG-20261002-141617-workbench-ui-stability
title: 工作台与声音广场展示稳定性、自适应和全站滚动条整改
level: L3
status: ready_for_review
owner: codex
branch: fix/692-workbench-ui-stability
created: 2026-10-02T14:16:17+08:00
updated: 2026-10-02T16:45:00+08:00
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
  - "backend/src/aima_ugc/contracts/http.py"
  - "backend/src/aima_ugc/bootstrap/content_http.py"
  - "backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py"
  - "backend/src/aima_ugc/bootstrap/workbench_http.py"
  - "backend/src/aima_ugc/adapters/persistence/postgres/workbench.py"
  - "backend/src/aima_ugc/modules/workbench"
  - "frontend/src/features/workbench"
  - "frontend/src/features/voice-plaza"
  - "frontend/src/shared"
  - "frontend/src/app"
  - "frontend/tests"
  - "frontend/e2e"
  - "frontend/e2e-fullstack"
  - "tests/api/test_workbench.py"
  - "tests/integration/content/test_workbench_runtime.py"
  - "tests/unit/content"
  - "contracts"
  - "docs/product"
  - "docs/blueprint"
  - "docs/guides"
contracts:
  - "ContentFilterSnapshot"
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

已按当前生成 Contract、backend/frontend/正式 docs 调查：心智字段由 Workbench generated client 消费，仓库内已同步。仓库外消费者无可访问事实，不能声称不存在；按已批准 content 命名决定同版本前后端集成，分离旧 snapshot 身份。Chrome/Edge 几何、九标签及滚动条已有本轮 Browser 证据；Firefox 提供兼容 CSS，未执行其浏览器实机。

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
| Contract兼容 | 已批准 content 字段 rename，仓库内消费者与生成链同步；旧snapshot独立身份 | #692 / AC40 | 后端/生成Client/缓存 |
| 数据与迁移 | 无Schema迁移，旧布局读时归一化 | #692 / AC33, AC36 | 不改用户现存布局事实 |
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
| R1 | 三个 Workbench Card 均可自由排序和 Resize | #692 / AC1 | satisfied | WorkbenchPage 编辑草稿/CAS 保存；Browser 排序、取消/保存与拖动回归 |
| R2 | 尺寸范围 `6–12列 × 48–160行` | #692 / AC2 | satisfied | WorkbenchLayoutModule 新写 6–12/48–160；Contract/API 与 Browser 六尺寸矩阵 |
| R3 | Workbench 默认品牌为爱玛，可多选其他品牌 | #692 / AC3 | satisfied | Workbench store 首次由共享目录 code/display_name/alias 解析；Unit/Browser 初始请求断言 |
| R4 | 默认日期为北京时间昨天结束的最近完整7天 | #692 / AC4 | satisfied | 北京时间 yesterdayRange(7)；Unit 冻结日期及 Browser 三模块请求 |
| R5 | 品牌变化自动清理失效车型 | #692 / AC5 | satisfied | Workbench/Voice 显式品牌提交按 knownVehicles 清理；目录与 picker Unit |
| R6 | Sound Filter 顺序严格按已确认顺序 | #692 / AC6 | satisfied | WorkbenchFilters 日期→品牌→车型→平台→情感→发声→一级→二级→重置；Browser 控件顺序 |
| R7 | Sound Filter 允许水平滚动 | #692 / AC7 | satisfied | WorkbenchFilters aima-scroll-x；Browser 真实 scrollWidth 与交互 |
| R8 | Scrollbar 使用细、浅、AIMA 色系样式 | #692 / AC8 | satisfied | shared/styles/tokens.css + scrollbars.css；Chrome/Edge 像素、颜色、圆角与截图 |
| R9 | 三张 Workbench Card 右上日期一致 | #692 / AC9 | satisfied | WorkbenchDateLabel 三卡复用；Browser 日期相等并位于 header 右上 |
| R10 | Brand Mind 改为 content-based 心智占比 | #692 / AC10 | satisfied | Postgres Workbench distinct content_id；test_workbench_runtime.py SQL/API 聚合和 Full-stack 两帖 100% |
| R11 | 多标签帖子可进入多个一级维度 | #692 / AC11 | satisfied | 一级/二级 distinct content_id 独立统计；PostgreSQL 同一级去重、多一级分母独立回归 |
| R12 | 9 个一级标签在最小尺寸下完整易读、单行优先 | #692 / AC12 | satisfied | radarGeometry measureText/ResizeObserver；九标签 Browser 实际 SVG 字号>=11、单行、无重叠/裁切 |
| R13 | Brand Mind 在所有合法尺寸始终左右布局 | #692 / AC13 | satisfied | BrandMindCard cqw/clamp 左右布局；Browser 六尺寸矩阵和 1100px 窄窗口真实拖动 |
| R14 | UGC Trend 在所有合法尺寸始终左右布局 | #692 / AC14 | satisfied | UgcTrendCard 左右结构/密度；Browser 六尺寸矩阵与最窄模块无溢出 |
| R15 | Radar 中心正确反映单品牌/多品牌/全部品牌 | #692 / AC15 | satisfied | BrandMindCard 中心消费 reactive knownBrands；Workbench Unit 单/多/全部与目录版本回归 |
| R16 | Brand Mind / Trend 默认正常状态没有可见内部 Scrollbar | #692 / AC16 | satisfied | Mind/Trend body overflow/布局；Browser 正常九标签与真实二级明细六矩阵无内部滚动 |
| R17 | Workbench 自动后台刷新为 6 小时 | #692 / AC17 | satisfied | WorkbenchPage 6h ordinary timer；Browser fake clock 六小时及 visible 过期回归 |
| R18 | 首次加载、用户筛选、重试、AI完成仍及时刷新 | #692 / AC18 | satisfied | 独立 pending 3/6/12/15s 有界跟进、显式动作与已有 Analysis fingerprint；Unit/Browser 初始、重试、终态 |
| R19 | Workbench Background Refresh 不清空现有内容 | #692 / AC19 | satisfied | Workbench retainSnapshot 保留同 Scheme 成功响应；Browser 请求延迟中 SVG/主体 bbox 不变 |
| R20 | Workbench Background Refresh 不插入造成布局变化的提示行 | #692 / AC20 | satisfied | Workbench 状态在固定 header/overlay；Browser before/mid/failure 图表、中心和明细 bbox 相等 |
| R21 | Workbench refresh 失败保留最近成功数据 | #692 / AC21 | satisfied | Workbench store warm failure 不清响应；Unit/Browser 503 SVG 保留且可重试 |
| R22 | Voice Plaza Filter Options Background Refresh 保留现有情感/发声/标签 | #692 / AC22 | satisfied | Voice store options SWR；Unit/Browser delayed building 与失败目录仍可操作 |
| R23 | Voice Plaza 动态筛选刷新期间不 disabled、不切“加载中” | #692 / AC23 | satisfied | VoicePlazaFilters warm 有值分支；Browser picker 打开、勾选、情感 select enabled |
| R24 | Voice Plaza Filter Options 失败保留最近成功目录 | #692 / AC24 | satisfied | Voice refreshFilterOptions 失败保留最近响应；Unit 与 Browser 503 |
| R25 | Taxonomy 后台刷新失败不清空最近成功 Taxonomy | #692 / AC25 | satisfied | Voice refreshTaxonomy 相同响应保留引用、失败保留；Unit 目录/草稿断言 |
| R26 | 品牌/车型目录使用共享 SWR Owner，不因页面刷新显示 fallback 文案 | #692 / AC26 | satisfied | shared/domain/vehicleCatalog.ts 唯一 Pinia Owner、分页原子提交、scope 去重；vehicle-catalog Unit |
| R27 | 品牌后台 refresh 时“爱玛”文字全程稳定 | #692 / AC27 | satisfied | knownBrands 合并时比较 catalog_version/entity version；Workbench reactive refs；目录异步/旧 scope 回归 |
| R28 | 一级/二级 Picker 在刷新过程中保持打开和当前 draft | #692 / AC28 | satisfied | picker draft 与 server options 分离；Browser 延迟/503 中 dialog 和已勾 checkbox 保留 |
| R29 | Voice Plaza 列表后台刷新保留当前窗口，不整表闪白 | #692 / AC29 | satisfied | Voice replaceWindow 按 content_id 原位提交；Unit 窗口身份、旧查询 fence 与 Browser 列表 |
| R30 | 后台 Refresh 不重置页面/筛选器滚动位置 | #692 / AC30 | satisfied | VoicePage 普通刷新不滚页；同 ID 详情/评论窗口保留；Browser 详情草稿、scrollTop 和 bbox 回归 |
| R31 | 用户主动 Query Change 不展示旧 Query 数据，但容器几何保持稳定 | #692 / AC31 | satisfied | Voice applyFilters 真变化立即清旧项；VoicePlazaTable 记录上次 body/header 高度；Browser 延迟/503 列表 bbox 相等 |
| R32 | Cold Loading / Background Refresh / Query Change 三类状态有独立回归 | #692 / AC32 | satisfied | 既有 cold/error Browser、warm options/detail、真实 query change 三类独立场景；193 Browser 全绿 |
| R33 | 历史 `<6列` 布局安全归一化 | #692 / AC33 | satisfied | workbench_http 旧 read clamp 至6、保持 revision/order；API/PG old JSONB regression |
| R34 | OpenAPI / Generated Client / Docs 同步 | #692 / AC34 | satisfied | Pydantic→scripts/contracts/generate.py→Orval；generate --check 与 compatibility、Docs 两检查通过 |
| R35 | Build、targeted Unit、Browser、Backend Integration 当前 Head 全部有新鲜证据 | #692 / AC35 | satisfied | 最终本地版本：1966 Backend+12 subtests、295 Frontend、193 Browser、14 PG、1 Real Full-stack；lint/ruff/mypy/build；远程 current-head CI 作为后续 merge 必需门禁 |
| R36 | 声音流作为唯一 Workbench 全局筛选入口始终可见；前后端拒绝隐藏，旧隐藏布局读取时安全恢复，同时保留排序。 | #692 / AC36 | satisfied | LayoutUpdate validator 拒绝 sound_stream hidden；UI 无隐藏操作；旧读恢复；Contract/API/Browser |
| R37 | 初次进入必须先取得目录和布局、解析爱玛业务身份及完整7天，再对同一筛选快照并发查询三模块一次；目录重验证不得覆盖用户主动品牌选择。 | #692 / AC37 | satisfied | Workbench bootstrap await references/layout 后 resolve default 再并发三模块；Unit/Browser 首次请求唯一同条件 |
| R38 | Workbench Reset恢复爱玛+最近完整7天+其余全部；Voice Plaza Reset维持页面自身语义，两个页面只共享目录。 | #692 / AC38 | satisfied | Workbench reset AIMA/7天，Voice reset 页面空条件；store Unit、Browser session/reset |
| R39 | Workbench→Voice Plaza完整deep-link携带已选维度/day/content_id，覆盖旧Session隐含条件，不出现隐藏筛选。 | #692 / AC39 | satisfied | voicePlazaQuery 保留所有数组、day/content_id；Voice route 先清旧 Session；Browser plural 深链及 secondary 钻取 |
| R40 | 心智分母为当前筛选active Scheme relevant distinct content_id，无作者ID和同作者多帖均按帖子计；Contract消费者和旧snapshot payload兼容必须调查并验证。 | #692 / AC40 | satisfied | PG 缺作者/同作者多帖/active Scheme，旧 snapshot hash 隔离；仓库消费者只有 Workbench generated client；旧 Cursor/Analysis 幂等 Unit；同版本发布前后端 |
| R41 | Workbench普通6h刷新保留声音流当前游标和遍历状态；休眠恢复仅过期补查，AI任务结果事件仍及时刷新。 | #692 / AC41 | satisfied | ordinary refreshAggregates 不读 stream；visible 仅过期补查；Browser 游标/频率/AI 终态 |
| R42 | 全站页面、Workbench、声音广场、Table、Drawer、Dialog、Dropdown、Chart/长文本滚动区域使用统一scrollbar Design Token与复用scroll utilities；默认3–6px，透明/极浅轨道、浅粉灰thumb、999px圆角，hover/active轻微增强且不变粗。 | #692 / AC42 | satisfied | main.ts 全局 import scrollbar Owner；3/4/5px utilities，透明轨道、999 圆角、色态；Browser Chrome/Edge 主要页面 |
| R43 | Chrome/Edge滚动条尺寸和颜色实际生效，同时提供Firefox thin/color兼容；禁止粗黑轨道、8px+滚动条和全局强制隐藏。 | #692 / AC43 | satisfied | Chrome 与本机 Edge 各3主要页面测试通过；Firefox CSS thin/color 分支由浏览器兼容样式提供，未宣称 Firefox 实机验收 |
| R44 | 滚动条颜色来自现有AIMA token，禁止页面私自硬编码；声音筛选横向3–4px、卡内更淡、Drawer/Dialog约5px、Table约4px。 | #692 / AC44 | satisfied | Token 单一颜色 Owner；全仓 scrollbar 专项审计与 Chrome/Edge computed width；无页面颜色副本 |
| R45 | 固定尺寸卡片、图表关联容器和Table按真实布局使用stable gutter，滚动条出现/消失不改变Mind/Trend/Radar宽度；不得无脑全局加gutter。 | #692 / AC45 | satisfied | 仅真实 picker overflow stable gutter；去除无必要全局 Drawer gutter；完整正式 responsive 几何测试及 warm Radar/body bbox |
| R46 | 主要页面Workbench/Voice Plaza/Admin/配置的normal/hover/active滚动条和layout shift取得Browser视觉与几何证据。 | #692 / AC46 | satisfied | Workbench 横向、Voice detail、Admin catalog 与 scheme editor normal/hover/active 真实截图；Chrome/Edge bbox/clientWidth/width 不变 |
| R47 | 对frontend/src自动刷新/polling可见路径完成有界审计；本范围已有成功值不得刷新闪烁，其他同类路径有实际问题时修复，不做无关重构或重型Refresh框架。 | #692 / AC47 | satisfied | 有界审计 TaskCenter、CollectionRuntime、DataImport、Provider capacity、Report polling；固定提示层、detail generation/unmount fence；相关 Unit/Browser 保持原轮询频率 |
| R48 | 用户草稿/search/open/scroll与server目录隔离；失效候选可标记或提交时清理，后台目录刷新不得突然删除用户勾选。 | #692 / AC48 | satisfied | server directory/known names 与 picker draft 分离；不在 warm options 刷新清用户值；显式提交才清失效项；Unit/Browser 草稿/搜索/打开/scroll |
| R49 | 合法Resize矩阵6×48/6×80/8×48/8×80/12×48/12×160全验证；当前9正式标签可读、实际measureText计算，异常超长在最低可读字号后可省略且tooltip/详情完整。 | #692 / AC49 | satisfied | 6×48/6×80/8×48/8×80/12×48/12×160 Browser；九正式标签完整，异常长标签最低字号后省略且 detail title/tooltip 全名 |
| R50 | 源会话完整文字方案、修订优先级、实施进展持久可追溯；旧事实按当前代码复核，图片未读取不冒充视觉事实。 | #692 / AC50 | satisfied | 用户源会话完整文字与修订顺序持久保存于 #692 附录及本任务 source-plan.md/source-conversation.json；长期 goal active；原截图像素缺失如实披露 |
| R51 | 本地分层验证、Completion Audit、独立Review、当前Head/Base相关CI全部收敛后合并远程main；管理员仅在已满足质量门禁且有效授权成立时必要使用。 | #692 / AC51 | not_applicable | 本行是交付阶段门禁，不是 Implementation Ready 已发生的结果。依 #692/AC51 与原生 PR 生命周期，独立最终 Review、当前 Head/Base CI、权限复核及 expected SHA merge 必须在此 Change Ready 后执行；Issue AC51 保持未勾选直至真实合并，不延期、不降门禁 |
| R52 | 合并后核验main-fresh CI、repository-native Change Archive、逐AC Closure Audit、Issue状态回写与安全cleanup；没有直接证据不得声明已交付。 | #692 / AC52 | not_applicable | 本行只对 pre-merge Implementation Ready 不适用：#692/AC52 明确要求合并后的 main-fresh、原生归档、Closure/cleanup；原生 automation 必须接收 active/ready_for_review 后才能生成 archive/done。Issue AC52 与长期 goal 保持未完成直至下游直接证据齐全，不把其冒充当前已交付 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| backend Workbench Contract/HTTP/Repository/snapshot | 内容统计、布局旧读新写、缓存身份 | E1/E2/E3 | R2/R10/R33/R36/R40 |
| frontend Workbench/Voice Plaza/shared/app | 默认值、SWR、布局/图表、统一scrollbar | 用户决定 | R1–R50 |
| contracts/generated/tests/docs | 生成一致性、风险匹配回归、当前事实 | 公共边界 | R34/R35/R51/R52 |

- [x] 调查当前实现和事实源。
- [x] 建立任务路由与上游AC追溯。
- [x] 行为变化建立失败证据：后端 content/layout 与前端默认日期、warm SWR 先 Red 后 Green；旧 Cursor 与独立 Review Findings 也取得失败/修复回归。
- [x] 完成实现与受影响文档。
- [x] 本地验证与 Completion Audit 已取得；独立最终 Review/远程 CI/merge 另设不可跳过的 Delivery Gate。

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
| 兼容性 | 内容字段同步生成客户端；仓库内 Workbench 消费者同步；仓库外调用方需采用同版本 Contract | #692 / AC40 |
| 数据 / Migration | 无Schema迁移 | JSONB旧布局读归一化，新snapshot身份 |
| 部署 / 运行 | 同版本后端与前端，快照继续走既有Job | 本次不部署 |
| 回滚 / 恢复 | 回滚实现commit，缓存身份隔离可重建 | 不破坏Content/Analysis数据 |

# 文档、依赖、部署与发布影响

长期文档：Product用户行为、相关Blueprint查询/刷新/布局、shared styles README与设计工作流；以机器事实同步。依赖/Runtime不变。配置/Secret不变。没有Release/Deploy授权。Contract与仓库内消费者同步生成；当前可访问仓库消费者已同步，仓库外调用方没有可访问清单，不声称已验证；部署时同版本升级前后端，回滚同版本代码。

# 完成审计

- [x] upstream_re_read：2026-10-02 16:41 重新读取 live #692、完整附录与最终修订；独立重建 AC1–AC52，与 source-plan.md 对照。
- [x] change_coverage：AC1–AC50 已有逐项实现/验收映射；AC51/AC52 按其明确时间关系作为不可跳过的 pre-merge/post-merge Delivery Gate，不由 Change 反推需求，不作为延期。
- [x] reverse_audit：Content/Mind Contract→SQL/缓存/HTTP→生成 Client→三卡/深链/筛选消费者；UI排序/Resize→后端CAS/旧读新写；快照请求→Job→Worker→fresh结果；AI结果→页面事件→心智→声音广场通过真实 Full-stack 验收。所有五个多选消费者使用同一快照；Schema/依赖/Provider/生产环境未改变。
- [x] unresolved_cleared：Implementation Ready 无 not_satisfied；两项交付状态仅对当前施工阶段 not_applicable，仍在 Issue/goal 中保留未完成。独立审查 R1–R5 均修复并回归，等待独立最终核验；Ready 不表示已合并。

# 完成证据与状态

## 新鲜证据

所有命令在隔离任务 checkout、锁定 Python 3.14.7/Node 24.19.0 上执行，生产文件和生成 Contract 为本次最终实现。日志由本任务 `.runtime/692` 持有，交付后保存到任务 Evidence 目录。CI 将绑定正式提交 SHA；代码变化会使受影响证据重新验证。

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | baseline 0a8f6b4c；Windows | git status/fetch/worktree；live Issue canonical validation | PASS | 独立施工分支和正式上游需求 |
| V2 | 最终后端实现；Windows | uv run pytest tests/unit tests/contracts tests/api -q -p no:cacheprovider --basetemp 临时短路径 | 1966 passed、16 skipped、12 subtests passed | 后端/API/Contract 与治理全回归；skip 保持项目既有要求 |
| V3 | 最终后端实现 | uv run ruff format --check / ruff check changed Python；uv run mypy backend/src | PASS；435 files | 格式、静态检查与类型 |
| V4 | 最终生成物/文档 | scripts/contracts/generate.py --check；check_compatibility.py；check_docs.py；check_docs_facts.py | 全 PASS | Pydantic→OpenAPI/Client 一致，文档导航与机器事实一致 |
| V5 | 最终前端实现；Chrome | npm run lint；npm run test -- --run；npm run build | 295 Unit；lint、双 typecheck、生产 build PASS | 前端完整回归与产物 |
| V6 | 最终前端实现；Chrome | npx playwright test --workers=3 | 193 passed | 全页面 Browser，六 Resize 尺寸、九标签、延迟/503/草稿/scroll/bbox/deep-link 与其他轮询路径 |
| V7 | 最终样式；本机 Microsoft Edge | 三个相同 scrollbar Browser 场景，channel=msedge | 3 passed | Workbench/Voice/Admin/配置三状态实际样式、视觉与几何；原测试源码复用 |
| V8 | 隔离 PostgreSQL 18.4 | test_workbench_runtime.py + test_workbench_scheme_bootstrap.py；test_stage8d_voice_plaza_runtime.py | 5+9 passed | 缺作者/多帖/多标签/active Scheme、历史布局/旧 snapshot、plural 投影与回退查询 |
| V9 | 最终 API 重新启动；隔离 PG/真实 Worker/本机 Fake LLM | npm run test:e2e:fullstack -- e2e-fullstack/analysis-streaming.spec.ts | 1 passed | 同作者两帖 AI→持久结果→心智2/2=100%→声音广场钻取真实闭环 |
| V10 | 唯一 CI classifier | scripts/dev/validate_changed.py --base origin/main --json | profile=full | 全 Backend/Frontend、PG、Full-stack、Runtime/Package 等远程 current-head CI 必需；Windows npm.cmd 适配下逐条执行同源本地命令，无第二套映射 |

## Review Repair Package

| Finding | 原问题 | 修复 | 新鲜验证 |
| --- | --- | --- | --- |
| R1 | plural 默认字段改变旧 Cursor/Analysis 幂等身份 | 规范化兼容空默认、集合顺序和单值/数组并集，stored snapshot 恢复后比较 query identity | 9 targeted Unit；1966 全 Backend |
| R2 | warm detail error 插入正文导致几何位移 | 固定 header error overlay，保持成功详情与草稿 | Browser 延迟/503：正文 bbox、scrollTop、正面纠正草稿全保持 |
| R3 | 一级心智钻取丢 secondary filter | 深链总是携带 applied secondary 数组 | Browser primary 钻取 secondary 仍存在；Product 文档同步 |
| R4 | Workbench 独立目录副本滞后/旧scope覆盖已知新名 | reactive active catalog + version-aware known catalog 合并 | vehicle-catalog 与 Workbench Unit；共享 Owner 不重复请求 |
| R5 | <=1180px CSS 固定430px盖掉合法高度 Resize | 删除无依据的高度覆盖，实际 row_units 控制高度 | 1100px Browser pointer 48→80 行后实际384→640且保存正确 |

## 未验证内容与剩余风险

原引用图片没有像素，不能声明逐像素还原；Firefox 提供标准 thin/color 兼容，但未执行 Firefox 实机。仓库外消费者没有可访问清单，Mind 字段 rename 需要前后端同版本发布/回滚。无依赖升级、Schema Migration 或生产变更。Vite 保留既有大 chunk 警告，Backend 保留既有 deprecation warnings；未提高预算或降低断言。真实付费 Provider Probe 不适用且未调用。

## 交付状态与不可跳过的剩余门禁

当前 Change 达到 Implementation Ready，PR 仍 Draft。正式最终 Review 必须独立核验当前 head/base、R1–R5 Repair 与本表完成定义；随后 PR Ready/current-head CI、live Requirement/权限/保护规则复核、expected SHA REST merge。此后才执行 implementation main-fresh、repository-native Archive、archive governance fresh、逐 AC Closure/Issue 重读与安全 cleanup。Issue AC51/AC52 与长期 goal 保持未完成，不把 pre-merge N/A 当作整任务完成，也不代替用户批准延期。

合并、main-fresh、归档、Issue closure、分支与隔离服务清理在其真实平台 Evidence 取得前均未完成。本轮不执行 Release/Deploy。

## 备注

主代理唯一 Writer。独立只读 Reviewer 负责最终修复复核。任务长期目标 active；完整方案及修订顺序由上游 #692 附录和本任务持久 source-plan.md/source-conversation.json 持有。Validation Asset Redundancy Gate：新增测试分别覆盖 SQL/Contract、目录并发身份、幂等兼容、用户中间状态、几何、跨组件实际接线；没有增加平行业务实现或重复 Setup/永久 CI Job。唯一 classifier 仅补充 Workbench→现有 analysis-streaming Golden Path 的真实影响映射，未知路径仍 full/fail-closed。
