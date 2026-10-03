---
schema: coding-change/v1
id: CHG-20261003-111428-wisersone-import
title: WisersOne 下载与统一导入接入
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feature/700-wisersone-import
created: 2026-10-03
updated: 2026-10-03
completion_gate: required
depends_on: []
affected_areas:
  - "backend"
  - "frontend"
  - "deployment"
  - "docs"
affected_paths:
  - "backend/src/aima_ugc"
  - "frontend/src"
  - "migrations"
  - "tests"
  - "Dockerfile"
  - "compose.yaml"
  - "compose.windows.yaml"
  - "scripts/deploy"
  - "docs"
contracts:
  - "WisersOne HTTP/Job"
  - "generated HTTP clients"
data_changes:
  - "WisersOne download lifecycle migration"
---

# 变更摘要

把已有独立 WisersOne 过去 24 小时下载能力接入系统，持久保存刷新登录态，并复用统一 Data Import Pipeline。上游要求见 #700。

# 背景、现状与问题

## 背景

用户要求本地及 Linux 无 UI 运行成功后直接合并。初始两份 JSON 随代码公开打包是用户获告知后的明确例外。

## 当前现状

根工程已有 Playwright 1.62.0；正式容器尚无浏览器。现有 server_path 默认 historical_fill_only，统一导入已有 Source 与 Canonical Artifact。

## 问题、根因或约束

独立脚本没有 PG 任务/租约/恢复/导入接线；刷新状态随代码替换会失效。慢网站导出不能占用一个无限 attempt。

## 不修改的后果

持续依赖人工拷贝文件，容器和升级后的登录态不可验证。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 独立脚本显式选择过去24小时并无限轮询网站任务 | 原脚本 download_wisersone_xlsx、_wait_download_task | 复用已验证行为，拆为有界任务阶段 |
| E2 | 既有 Campaign 有服务端目录、冻结过滤与不可变 Artifact | historical_import_http/worker、platform/storage/canonical.py | 不复制导入链路 |
| E3 | root uv 项目和非 root Docker 已建立 | pyproject.toml、Dockerfile、compose.yaml | 根构建 context 不变 |

## 推断与待确认

本轮 Windows 和 Linux 已免密码完成真实导出；网站未来可以撤销会话，需要人工更新认证目录。数据内容的业务正确性按用户决定不在验收范围。

# 目标、成功标准与非目标

## 目标

人工脚本可指定目录；系统可追踪下载、取消、恢复、导入和结果。

## 成功标准

以 #700 的 AC1–AC13 和用户追加的定时计划、共用弹窗、品牌过滤要求为完整完成定义，所有适用项必须取得直接证据。

## 范围

Provider/人工入口、auth、PG Job/下载事实、API/UI、Docker/Compose、七天清理和文档。

## 非目标

不检查数据内容业务正确性，不执行 Release/部署/生产迁移或导入。

## 必须保持不变

现有输入→Artifact→Canonical→过滤→Owner 链路，Job fencing/deadline，根 uv，既有用户数据库和原桌面文件。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 负责人 | Ingestion 持有下载事实，Provider 不写业务表 | #700 / AC6 | bootstrap 与 PG adapter |
| 认证 | bundle 仅首次播种，刷新使用 host bind | #700 / AC3、AC4 | 镜像升级不覆盖 |
| 长等待 | 有界阶段与 continuation，无30分钟总上限 | #700 / AC5 | 同一 Job Runtime |
| 数据 | 新导入 standard_observation，冻结文件重试 | #700 / AC6 | 现有 Campaign |
| 交付 | 用户授权 Agent 验证通过后直接交付；项目早期 PR 规则适用 | 用户当前指令、AGENTS.md | 不另等待重复授权 |

# 修改方案与决策依据

## 最小充分方案

1. 认证与 Provider → 正式与人工目录 → 过去24小时原子导出 → 本地单元和真实下载。
2. PG/API/Job → 下载生命周期、恢复与 Campaign 接线 → 隔离 PG 集成。
3. 计划和 UI → 采集策略共用新建计划弹窗、默认 WisersOne、名称/执行频率/品牌 → Scheduler 到时自动下载导入，任务状态可见 → 组件及跨组件验收。
4. Docker/Compose → 非 root 浏览器及 bind → 构建和真实 Linux 下载。
5. 文档/清理/交付 → 七天保留与 Canonical 不变 → 受影响检查、Review、CI 与 merge 收尾。

## 证据到决策

E1 要求提交/轮询/下载阶段拆分；E2 要求复用生产导入；E3 要求在正式镜像验证。

## 备选方案与取舍

单一无限长 Job 会破坏 attempt deadline；复制 imports_test 会复制业务规则；刷新写回源码会导致升级丢失。采用分阶段 Job 与 host auth。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 正式 Provider 和人工入口 | #700 / AC1 | satisfied | providers/wisersone 与 sibling wisersone_test；实际 Windows/Linux 模块命令、正式 wheel 人工入口解析 |
| R2 | 过去24小时、五平台和原子 Excel | #700 / AC2 | satisfied | 原生产选择器与字段配置、Windows/Linux 实际导出 JSON 证据、ZIP CRC 与表头解析 |
| R3 | 两份初始 JSON 正式打包 | #700 / AC3 | satisfied | 两个精确 Secret 例外路径；当前 wheel/sdist 与正式镜像均解析到两份 JSON；不输出值 |
| R4 | host auth 首次播种、刷新与升级 | #700 / AC4 | satisfied | auth 单元/跨进程锁/崩溃释放/原子失败保护；候选镜像实测同一宿主状态未被覆盖 |
| R5 | 无总等待上限、持久恢复与取消 | #700 / AC5 | satisfied | 65 次正常 continuation、未知发送回执、取消持久传播/终态竞争、预检/监控/Chunk 恢复与耗尽重试边界；实际 Linux 导出跨30分钟 |
| R6 | 受管文件接入标准统一导入 | #700 / AC6 | satisfied | 正式 server_path Campaign/Source/Canonical/Reader/Mapper/Owner；PG 工作流与真实 full-stack 自动入库 |
| R7 | 现有页面入口与完整结果 | #700 / AC7 | satisfied | 采集运行中心 WisersOne 任务弹窗、取消/恢复/结果；3 项浏览器状态测试与19项正式 full-stack 回归 |
| R8 | 正式非 root Docker 与 Compose | #700 / AC8 | satisfied | 根 Dockerfile此前e5baa正式候选构建、uid10001 Chromium实际启动及installed包21项PG测试；当前454源码wheel已验证，最终LinuxCI按R14硬门禁执行；Compose/Windows bind接线和既有构建源检查 |
| R9 | 七天原文件清理、Canonical 保留 | #700 / AC9 | satisfied | 45项Windows PG PASS，持久目录消费者准入、发现/Source复制复核保护、清理先认领原子409、根递归及大小写等价、终态满七天释放、Canonical保留；独立复审机制闭合，当前Linux PG证据按R14正式CI取得 |
| R10 | Windows 实际免密码下载 | #700 / AC10 | satisfied | changes/active/CHG-20261003-111428-wisersone-import/evidence/windows-download.json |
| R11 | 正式 Linux 实际下载和隔离导入 | #700 / AC11 | satisfied | 同目录 linux-download.json/linux-final.json；此前e5baa正式候选 installed 包21项PG与认证保留smoke；Provider/Auth后续未改变 |
| R12 | 文档、本地自动测试、生成消费者、静态检查、Completion和独立代码Review | #700 / AC12 | satisfied | 最终Windows45项PG/2066项后端及Unicode3项控制、当前wheel454源码、306前端/205浏览器通过；WIS-DR-01至04 resolved，有限代码复审NO_FINDINGS_WITHIN_SCOPE；当前Linux重依赖CI明确由R14提供，不以本地旧镜像替代 |
| R14 | 当前head Linux PG/full-stack/正式Compose构建及其它适用PR CI、guarded merge | #700 / AC12 | explicitly_deferred | 原生preflight与canonical Coding ref23规定的正式CI阶段：载体ready_for_review后转换PR触发全套CI，包含六份Wise PG、空库迁移、完整full-stack、Compose及Release只读dry-run。全部current-head/current-base证据是merge前硬门禁，当前未运行，不能post-merge延期、跳过或称PASS |
| R15 | 合并后main-fresh、自动归档、Closure、cleanup | #700 / AC12 | explicitly_deferred | live Issue AC12、canonical Coding ref23与项目AGENTS明确属于merge后正式阶段，保留在同一任务scope；依赖R14真实merge，AC12和整体交付保持pending，不能以载体Ready视为任务完成 |
| R13 | 共用计划弹窗、名称/频率/品牌及自动下载导入 | #700 / AC13 | satisfied | 前端10项计划测试；PG Scheduler唯一Occurrence、冻结快照、CRUD复制启停归档；正式浏览器→API→Scheduler→Worker→入库→结果工作流 |

| R16 | 不再等待本机磁盘恢复后重复整套Linux/full-stack验收，复用先前本轮证据 | #700 / AC12 | explicitly_deferred | 用户明确允许不重复本地验收；最终代码的当前Linux执行由R14远端CI补齐，保留旧镜像revision与失败日志事实。该本地重复项不再是依赖磁盘恢复的交付前置条件，不豁免CI/Review，也不新增磁盘修复范围 |

# 计划改动

Provider/wisersone 与 wisersone_test、Ingestion 下载模型与 Contract、PG repository/schema/migration、bootstrap API/worker、frontend import 页面/生成 client、Dockerfile/Compose/host preparation、tests、相关正式文档和安全例外。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 当前2066项后端PASS、16既有skip、12subtests；306项前端单元与205项浏览器PASS；4个取消/恢复/清理反例先Red后Green |
| 接口 / 契约 | required | OpenAPI/client正式生成、drift/兼容PASS；旧TikHub默认及必填语义回归 |
| 集成 / 持久化 / 运行依赖 | required | Windows隔离PG 13+独立8项PASS；正式Linux installed包21项PASS；空库全迁移至0082及alembic check无漂移 |
| 用户 / 工作流验收 | required | 19项正式full-stack PASS，Wise默认创建/频率/品牌/自动下载导入/结果与既有Excel入口；Agent本地验证后直接交付是用户明确授权，不冒充用户本人已验收 |
| 跨组件关键路径 | required | 同一真实API/持久Worker/PG/前端与生产Reader/Mapper/Owner；只替代网站边界，保留正式30秒continuation |
| 外部依赖 / 供应方探测 | required | Windows与Linux免密码真实下载；只验证文件结构，不审核业务内容 |
| 构建 / 打包 / 运行 | required | fresh wheel/sdist解析、JSON2份和人工入口；正式backend非root镜像构建/Chromium启动/源hash比对 |
| 文档 / 治理 / 其他 | required | 正式产品/架构/运行/导入文档与Secret窄例外已同步；本地Completion和有限代码Review闭合；当前head远端CI按R14、post-merge按R15执行 |

## 验证计划

按 scripts/dev/validate_changed.py --base origin/main 的唯一 scope classifier 执行。真实 Provider 验证不进入普通 CI、不写生产库。独立审查和 Completion 后同步 main 并获得 current head CI。

# 风险、兼容性、迁移与回滚

网站会话仍可失效，需要人工重新登录。HTTP增加WisersOne任务与可选plan_type（旧TikHub默认不变），Job增加默认observe/可选cancel，同一持久Runtime。迁移0080新增下载生命周期，0081新增计划/Occurrence关联与一致性约束，0082新增cancelling。已有Wise事实或取消传播未结清时downgrade明确拒绝，不能用删除历史任务作为常规回滚。失败时停用Wise计划、结清活动任务，保留host auth、输入与数据库备份；既有Canonical用于历史重筛。

# 文档、依赖、部署与发布影响

同步采集、存储、运行、统一导入和模块 README。依赖版本不升级。新增浏览器构建内容、host mount、auth 配置。只批准初始两份 JSON 例外，其余 Secret 规则不变。Release/部署未授权。

# 完成审计

- [x] upstream_re_read：重新读取本轮全部用户决定、live Issue #700 AC1–AC13及项目正式采集/统一导入事实，未把本Change当上游全集。
- [x] change_coverage：逐AC映射R1–R16；自动下载/计划/品牌未漏项；远端和合并后义务仍属完整范围。
- [x] reverse_audit：计划创建/编辑/复制启停归档→类型化Contract/Scheduler；后端任务→运行中心取消恢复/导入详情/声音广场；Job→真实终态/取消/监控/预检恢复；源码→wheel/正式installed镜像；TTL→Canonical保留。
- [x] unresolved_cleared：当前本地施工未满足项清零，WIS-DR-01至04已resolved。R14为下一正式CI/merge前阶段、R15为merge后阶段；R16依据用户明确决定不重复本地验收。整体Issue AC12及最终交付仍pending，不以本载体Ready宣称完成。

# 完成证据与状态

## 新鲜证据

最终产品实现冻结于 18eec1e025eb1309dd39ba80b0bf69d3d422f234，base为3e13cccf63a75b05eec12e302d557c3cf99dcaac。完整分层验证见同一任务的 evidence/validation.md 与 candidate.json，真实导出见windows-download.json/linux-download.json/linux-final.json。证据不含认证内容。后续仅Change/非敏感Evidence变动不失效产品检查；若产品改变必须补受影响验证。

## 未验证内容与剩余风险

Windows最终45项PG与2066项后端及Unicode3项控制已通过，前端205/306项PASS。独立有限代码复审闭合，WIS-DR-01至04 resolved。用户允许复用本轮既有Linux成功证据，不再等待本机D盘恢复后重跑整套本地验收；最终当前head的Linux PG/full-stack/正式Compose构建与其它适用检查仍须由远端CI通过，当前pending。不以既有Linux镜像冒充最新构建成功。本机Docker只读导致的缓存清理限制按R15继续核实。外部网站可能使登录态过期；只能保证本轮免密码成功，不能承诺永久会话有效。数据业务真伪按用户决定不审核。既有Pydantic/Starlette弃用和前端bundle体积提示未升级依赖处理。

## 交付状态

Issue #700，feature/700-wisersone-import，早期Draft PR #701已建立。本地载体ready_for_review用于触发当前PR全套CI；最终PR merge clearance仍pending、未merge。R14当前CI通过后才guarded merge，再按R15执行main-fresh/native archive/Closure/cleanup。Release/Deploy不适用：用户只授权验证后合并，未授权正式发布、部署或生产数据操作。

## 备注

清理仅限本任务 scratch、测试容器、镜像和可证明归属的构建缓存。
