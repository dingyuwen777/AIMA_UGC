---
schema: coding-change/v1
id: CHG-20261009-143436-supplement-result-consistency
title: 补采一致性、小红书媒体与开发交付效率整改
level: L3
status: in_progress
owner: maintainer
branch: fix/supplement-result-consistency
created: 2026-10-09T14:34:36+08:00
updated: 2026-10-09T22:00:56+08:00
completion_gate: required
depends_on: []
affected_areas:
  - content
  - vehicles
  - collection
  - analysis
  - reporting
  - workbench
  - frontend
  - ci
  - developer-tooling
affected_paths:
  - backend/src/aima_ugc
  - migrations/versions
  - tests
  - frontend
  - scripts
  - .github/workflows
  - AGENTS.md
  - docs
contracts:
  - CanonicalContentV1
  - BrandVehicleCatalogSnapshot
  - analysis.content-label.v1
  - content.consistency-repair.v1
  - CanonicalMediaV1
  - ContentMediaResponse
  - Content playback prepare/stream
  - CI changed-scope outputs
data_changes:
  - content_versions.author_snapshot
  - analysis_content_version_reuses
  - voice_plaza_content_projection
  - content_consistency_repair_runs
  - content_consistency_repair_targets
  - content_media attribute observations and playback state
---

# 变更摘要

补采成功后，按合并后的完整 Current 原子维护当前版本品牌/车型 Evidence；通过生产输入 Hash 证明等价时引用真实历史 AI Result，保留有效人工审核。输入变化或历史协议不明时保持 stale，补采不创建 AI Run。补采阶段已在90013af0完成本地验证与独立复审；本轮按用户新增两份任务书扩展小红书图文/视频全链路及开发交付效率，统一上游需求为Issue #711。最新直接指令授权全部本地成果经验证和保护PR合并main及清理；不部署、不Release、不操作生产数据。用户人工验收不能由自动测试冒充。

# 背景、现状与问题

## 背景

上游是用户在本会话提供并批准的《Codex 开发任务书：补采后品牌车型识别与 AI 打标结果一致性修复》，包含 AC01–AC22。引用会话为 chatgpt-conversation://6ac87f50-c62c-83e8-a2b9-7a7343b6d0e8；补采阶段要求以用户粘贴正文为准；2026-10-09后续追加小红书20项AC和效率整改方案，55项统一验收见Issue #711。最新直接主分支交付指令覆盖两份粘贴方案的PR Ready终点。

## 当前现状

起点为 main caf06ae1be1d243545d21a71fcbfe72640d0bd5f。已 fetch origin/main，仍为同一提交，工作区起始无修改。新本地分支为 fix/supplement-result-consistency。

## 问题、根因或约束

补采创建路径返回空 filter_snapshot；Fenced Writer 仅在传入目录和 Resolution 时维护 Evidence，且前置拒绝 unmatched。版本作者快照直接采用稀疏 Observation；AI 查询主要只接受当前版本直接 Result，尚无正式等价复用关系。需要先由 PostgreSQL 回归确认失败。

## 不修改的后果

非 AI 输入字段补齐也可能使当前结果 stale；新 Content Version 的品牌/车型 Evidence 与当前完整正文不一致，人工纠正可能失效。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 补采 Run 未冻结目录 | backend/src/aima_ugc/bootstrap/collection_http.py / _build_scopes | 新补采必须冻结全量有效目录 |
| E2 | Evidence 写入前置 matched 且依赖可选参数 | backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py / ingest_content | 分开接受内容与分类命中 |
| E3 | 已有完整 Current 与人工审核统一解析入口 | backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle_classification.py | 复用生产 Resolver、锁序和 Evidence Owner |
| E4 | 已有生产输入 Hash | backend/src/aima_ugc/modules/analysis/content_labeling.py / content_labeling_input_hash | 不增加相似度机制或 LLM 请求 |
| E5 | 版本作者快照取稀疏 Observation | backend/src/aima_ugc/adapters/persistence/postgres/content.py / _append_content_version | 先保证不可变输入快照一致 |

## 推断与待确认

定向及广域数据库回归、投影/消费者、历史修复Runtime、真实浏览器和两轮独立Review已闭合。以上仅说明90013af0补采阶段的已完成边界；本轮新增媒体/CI范围尚在开发，整体不表示PR Ready或用户已验收。

# 目标、成功标准与非目标

## 目标

品牌/车型/竞品、有效 AI 结果、人工审核、列表/详情/筛选/导出/报告在补采和恢复后保持一致。

## 补采阶段成功标准（本轮扩展前）

- [x] AC01–AC22 均有直接证据，逐项定位于EVIDENCE。
- [x] Schema、Migration、Owner、Contract、文档及必要真实浏览器链验证闭环。
- [x] 两个独立Reviewer在最终返修checkpoint无unresolved blocking Finding，完成到本地待用户验收。

以上三项只对应90013af0补采阶段。扩展后的整体成功标准为Issue #711全部55项验收，当前媒体、CI与正式交付仍在进行；新增直接证据记录于同目录MEDIA_CI_EVIDENCE.md，不据旧checkbox宣称整体完成。

## 范围

Content 合并/版本作者快照、补采冻结目录及原子 Evidence、Analysis 等价关联及统一读取、人工审核、查询投影与消费者、有界恢复任务、相关测试和正式文档。

## 非目标

不改Prompt/标签体系、评论分页、既有Job Runtime机制或依赖；不伪造模型/人工历史，不全量计费或历史Content迁移，不缓存完整视频，不改其他四平台视频产品能力，不修改Agent_Skills受管资产，不Release/Deploy/生产操作或绕过保护。

## 必须保持不变

既有直接 Result/Run 顺序、历史 Run 冻结语义、人工锁及显式解锁、品牌先行 v2、竞品角色推导、表 Owner、Fencing、Source 账本和不在数据库事务内发 HTTP。声音广场不引入全局 active Prompt 失效；工作台保留其已测试的 active Scheme 范围。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 同一事务跨 Owner 编排，业务表仍由原 Repository 写入 | 用户任务书 §3、§7 | Content/Vehicles/Analysis |
| 接口与契约 | 尽量保持 HTTP 响应兼容，若增管理能力则正常生成 Contract | 用户任务书 §6、§8 | API/generated consumer |
| 数据与迁移 | 新 Migration 增加真实 Result 引用关系，不扫描全量 Content | 用户任务书 §4、§8 | Analysis Owner 与投影 |
| 错误与失败语义 | 不能证明等价就 stale；从未分析 pending；事务失败回滚 | 用户任务书 §4、§7 | Writer 与消费者 |
| 兼容性 | 新补采冻结全量目录；历史 Run 按原协议 | 用户任务书 §3.3 | Snapshot/Worker |
| 部署与回滚 | 先升级 DDL 再启动新 Worker；回滚前排空新协议任务 | 用户任务书 §11 | 本轮仅隔离本地验证 |

# 修改方案与决策依据

## 最小充分方案

1. PostgreSQL 回归复现补采缺 Evidence、稀疏作者快照与非输入变更 stale，建立 Red。
2. Content Owner 正确冻结合并作者输入；新补采冻结全量 Catalog，Fenced Writer 合并后重解析并原子维护 Evidence。
3. Analysis Owner 增加轻量等价关系；生产 Hash、可信历史协议、成功 Result、Content 锁共同保护复用。
4. 统一有效结果/人工来源选择，更新声音广场投影、查询、导出、报告、工作台和写资格。
5. 同一规则支持 Dry-run 与有界持久修复；测试 Retry/Fence/并发/回滚和一条真实 UI 补采刷新路径。
6. 同步正式文档，按 changed-scope 检查，重读上游逐 AC 审计与独立 Review。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1–E3 | 复用既有完整 Current 解析和人工锁语义，避免平行识别器 |
| D2 | E4–E5 | 输入先冻结一致，再用 Hash 证明等价，不能靠业务版本或相似度 |

## 备选方案与取舍

历史 Result 原地改版本或复制成新 Result 会污染模型执行历史，用户明确禁止。只在前端显示 completed 不能统一服务端消费者，用户明确禁止。采用用户推荐的独立关联表，最小表达目标版本到真实成功结果的引用和人工继承来源。


## 本轮新增范围与执行计划

Development Preflight：保留当前分支和四个本地提交，唯一上游Issue #711已canonical create校验、平台创建及live同检PASS。风险L3；实现与验证存在可独立调查价值，独立Review必需；共享checkout单一tracked Writer租约，Parent顺序集成。所有下游状态按新增范围重开，原补采证据仅在相关实现/Contract/环境未变化时复用。

1. CI正确性与生命周期 → classifier/validate_changed/check_docs、永久Workflow和对应测试 → PR merge-base真实范围、env风险、synchronize、Preflight fail-closed → 构造Git DAG/真实#710四文件、控制面目标回归；保持三个required identity。
2. Workflow成本 → Runtime/Tooling/Release真实消费者与Evidence Preservation Mapping → 模板-only执行配置/Compose渲染/正式打包，保留真实镜像与Runtime风险 → 对照#710真实Runner时间与本轮CI，避免重构整个DB体系。
3. 媒体根因 → Canonical/Mapper/Content Owner及所有scalar/batch/贡献账本路径 → 明确unknown、完整/部分/删除、属性新鲜度与追溯，封面合并和缓存 → 真PostgreSQL Red/Green、旧/新Raw与Replay兼容。
4. 播放准备与流 → 正式Collection父事实/Job/Attempt/Raw、Content窄更新与短期状态、Principal/可信CDN Transport/API → 并发去重、一次刷新、URL变更不改版本AI证据、Range/断开与SSRF防护 → 可控HTTP/真实DB故障恢复与有界真实TikHub/CDN。
5. 前端及Contract → Pydantic/OpenAPI/Orval、Drawer/Table/api、Nginx/CSP → 图片完整比例、视频标识封面/原生播放/一次恢复、稳定切帖 → 定向Unit/Browser及少量真实全栈。
6. 交付 → 受影响正式Docs/Completion/独立主审与盲审 → 全部55AC直接证据、当前head/base required CI → 保护PR合并、main-fresh、原生Change归档、Issue Closure与任务资源/分支清理。

真实Probe采用现有生产Operation/Transport/Mapper与价格限制器，最多6次物理请求、计划总费用0.06 USD，先核价；Secret/签名URL/Raw仅在安全内存或忽略审计边界，不入Git或输出。部署服务器出口不可用时保留明确验证边界，不把本机/Mock成功冒充该环境通过。

# 需求追溯

上游AC01–AC09在机器来源绑定中规范为AC1–AC9；编号和语义对应不变，展示及Evidence继续使用用户任务书编号。

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 评论/回复/互动不破坏版本及分析 | #711 / AC1 | satisfied | V6/V7/V14/V22；EVIDENCE AC01 |
| R2 | URL/发布时间等非输入变更复用 AI | #711 / AC2 | satisfied | V14/V20/V22；EVIDENCE AC02 |
| R3 | 稀疏 Detail 保留正文并按完整 Current 分类 | #711 / AC3 | satisfied | V6/V14；EVIDENCE AC03 |
| R4 | 新品牌全部命中 | #711 / AC4 | satisfied | V24 title/text新增时序两参数；EVIDENCE AC04 |
| R5 | 删除旧品牌撤销自动命中 | #711 / AC5 | satisfied | V6/V24；EVIDENCE AC05 |
| R6 | 多品牌车型归属正确 | #711 / AC6 | satisfied | V20/V22，真实爱玛+雅迪及各自车型；EVIDENCE AC06 |
| R7 | 无品牌仍补采成功 | #711 / AC7 | satisfied | V6/V24/V25，Discovery过滤保留；EVIDENCE AC07 |
| R8 | 人工品牌车型锁继承 | #711 / AC8 | satisfied | V6/V25，分维来源、空锁和墓碑；EVIDENCE AC08 |
| R9 | 同输入跨版本零 LLM 复用 | #711 / AC9 | satisfied | V14/V20/V22；EVIDENCE AC09 |
| R10 | 任一输入字段不同保持 stale | #711 / AC10 | satisfied | V14，生产Hash与变化字段参数；EVIDENCE AC10 |
| R11 | 未知协议/失败结果不猜测继承 | #711 / AC11 | satisfied | V14/V25；EVIDENCE AC11 |
| R12 | 等价输入保留情感标签发声人工修正 | #711 / AC12 | satisfied | V14/V20/V22；EVIDENCE AC12 |
| R13 | 人工相关性及 inherit_ai 正确 | #711 / AC13 | satisfied | V14/V22；EVIDENCE AC13 |
| R14 | 主动新 Run 执行且直接 Result 优先 | #711 / AC14 | satisfied | V14，真实Planner/Shard调用与新Result断言；EVIDENCE AC14 |
| R15 | A→B→A 可引用原始结果 | #711 / AC15 | satisfied | V14，非相邻Result来源；EVIDENCE AC15 |
| R16 | 补采/AI/审核并发无错误覆盖 | #711 / AC16 | satisfied | V14实际双Session锁等待、V25现有Owner锁回归；EVIDENCE AC16 |
| R17 | 事务中途异常完整回滚 | #711 / AC17 | satisfied | V6/V14/V25；EVIDENCE AC17 |
| R18 | Retry/Fence/接管幂等 | #711 / AC18 | satisfied | V6/V14/V25，正式Job故障重试/接管/取消；EVIDENCE AC18 |
| R19 | List/Count/详情/筛选一致 | #711 / AC19 | satisfied | V14/V20/V22；EVIDENCE AC19 |
| R20 | 导出/工作台/报告/历史冻结一致 | #711 / AC20 | satisfied | V14/V22/V23及V30；F-B1/F-B2直接Red/Green、完整Analysis30及两个独立Reviewer在8a10f441限定复审resolved，见EVIDENCE整批审查记录 |
| R21 | 历史修复有界恢复且重复运行幂等 | #711 / AC21 | satisfied | V25，30项repair包含真实CLI/Worker/故障/二次运行；EVIDENCE AC21 |
| R22 | 批量投影无明显 N+1 或全表扫描 | #711 / AC22 | satisfied | V14/V26，有限UUID页与1/100固定SQL数；不宣称生产40M压测；EVIDENCE AC22 |

| R23 | 小红书明确normal/video与未知；未知不默认图片。 | #711 / AC23 | satisfied | MEDIA_CI_EVIDENCE媒体基础层；真实normal/video/unknown Fixture与生产Mapper Unit；未知不默认image |
| R24 | 已知视频选视频详情；未知先图文确认后至多一次视频详情。 | #711 / AC24 | satisfied | 同文件媒体基础层60PG/610Unit与可选视频失败Red22；已知视频及同ID未知至多一次补充 |
| R25 | URL/封面/毫秒时长/尺寸来自真实验证字段，不用cache_url。 | #711 / AC25 | satisfied | 同文件TikHub直接6请求与脱敏Fixture；真实h264/封面/尺寸/毫秒，不用cache_url；本机实际解码 |
| R26 | 无播放URL仍保留视频类型封面。 | #711 / AC26 | satisfied | 同文件媒体基础层及真实首次cover-only入库；无URL保留video和封面 |
| R27 | 重复补采、部分属性、完整替换、删除、迟到并发正确合并媒体。 | #711 / AC27 | satisfied | 同文件60PG与三项返修10PG/48相邻PG；partial/full/delete/late/batch/并发和来源撤销 |
| R28 | 横竖长图及多图窄屏完整无裁切拉伸。 | #711 / AC28 | satisfied | 同文件真实Chrome横1200×600/竖600×1200/长400×2400及390px详情；contain、558×440稳定 |
| R29 | 标题附近及详情有真实视频标识，不恢复类型筛选或列。 | #711 / AC29 | satisfied | 同文件前端FE-R4永久Red/Green及真实列表和详情视频标识截图；不增加类型筛选/列 |
| R30 | 受支持合法源站内播放，真实CDN证据与Mock区别。 | #711 / AC30 | satisfied | 同文件正式Nginx/API/Worker/Chrome/真实CDN；720×1280/17.833s/readyState4，exit0 |
| R31 | 真实Range/206/416与进度拖动遵循上游能力。 | #711 / AC31 | satisfied | 同文件实际206/1024bytes及416空正文；原生seek到10秒完成解码；53代理Unit |
| R32 | 视频不落盘、不入Artifact或长期缓存，Nginx禁视频临时缓冲。 | #711 / AC32 | satisfied | 同文件14组业务/Artifact审计video MIME0，真实Nginx仅pid无proxy_temp，遥测保存视频字节0 |
| R33 | 每次明确播放意图最多一次受控URL刷新，失败冷却无循环。 | #711 / AC33 | satisfied | 同文件BR-R3及完整受控恢复Chrome；首次{}+一次failed_revision、固定Job只读观察、90s截止，无循环 |
| R34 | CDN403/404/410/429/5xx/超时及不支持格式正确分类降级。 | #711 / AC34 | satisfied | 同文件53代理Unit及播放Service/HTTP；403/404/410/429/5xx/超时/格式/终态分类，失败保留封面 |
| R35 | 同视频并发准备去重，正式Job/Attempt/Raw/Fence与费用可审计。 | #711 / AC35 | satisfied | 同文件104PG及三项返修/BR-R3；正式collection Job/Attempt/Raw/Fence去重、重放、未知费用和冷却 |
| R36 | 纯URL刷新不改Content Version、AI、Evidence或评论。 | #711 / AC36 | satisfied | 同文件首次缺URL到正式发布及实际恢复/播放/关闭14组摘要全等，V5/评论3/非空AI人工Evidence；零LLM增加 |
| R37 | 正文真实变化仍按已有版本、品牌和AI输入规则收敛。 | #711 / AC37 | satisfied | 原EVIDENCE AC03–AC18 + 新媒体60PG/相邻57PG；正文变化走原Content Owner与生产hash/Evidence |
| R38 | 兼容历史图片/多图/仅封面/旧note unknown/人工确认与旧Run，不全量重新计费。 | #711 / AC38 | satisfied | 同文件五种90013af0真实旧wire/20比较/25Scope、旧v1与v2账本、带数据0085/86往返；无全量计费 |
| R39 | Principal/可信HTTPS CDN/逐跳DNS与IP/SSRF/Range/连接带宽保护、断开释放有效。 | #711 / AC39 | satisfied | 同文件53安全代理Unit、真实PG/API Principal绑定及26条Nginx别名；公网IP固定/TLS/SSRF/Range/配额/退出连接0 |
| R40 | 后台刷新不清正文评论封面，关闭切换终止播放器轮询，无明显闪烁。 | #711 / AC40 | satisfied | 同文件FE-R1–R5、BR-R3独立复审及19Vitest/2Chrome Mock/真实关闭；轮询停止、节点稳定、late epoch拒绝 |
| R41 | 其他四平台与评论补采不回归。 | #711 / AC41 | satisfied | 同文件宽层2245通过与4项限定20全绿、610Unit/60PG及原补采回归；五平台原正式入口保持 |
| R42 | OpenAPI/generated client/Migration/Docs与实现一致。 | #711 / AC42 | satisfied | 同文件0085/86空库及带数据往返、当前Pydantic/OpenAPI/Client同步、generate --check和11Docs限定独立复核 |
| R43 | #710及base前进PR范围仅分支实际4文件，merge-base异常诊断且fail-closed。 | #711 / AC43 | satisfied | 同文件真实#710新4/旧14、唯一merge-base；166控制面回归覆盖base前进/缺对象/多基线fail-closed |
| R44 | 新增删除重命名及staged/unstaged/untracked与本地CI同源选择正确。 | #711 / AC44 | satisfied | 同文件166回归：本地与CI唯一classifier，staged/unstaged/untracked/新增删除改名及删除测试Owner suite |
| R45 | CI自身/Migration仍full fail-closed；其他真实边界精准选择并解释。 | #711 / AC45 | satisfied | 同文件高风险反例及当前171文件full计划；CI自身/Migration/未知路径不自免验证 |
| R46 | env注释/值/结构/敏感配置有独立分类和语法重复键、真实Settings/Connector/Secret/Compose/打包证据。 | #711 / AC46 | satisfied | 同文件env实际Settings/Connector/Secret/引号插值/重复键、两次真实Compose config和Release模板保留回归 |
| R47 | 未暂存文档非法引用本地失败，忽略目录不误报。 | #711 / AC47 | satisfied | 同文件未暂存新增文档坏引用真Red及忽略目录回归、check_docs本地静态PASS |
| R48 | 轻量Preflight失败不执行重型Job且required checks明确失败；成功后重型并行。 | #711 / AC48 | satisfied | 同文件CI-R1–R6独立闭合；Preflight needs图、显式required失败、成功后重层并行永久回归 |
| R49 | opened/synchronize/Ready/修复push/base更新最新HEAD有可靠自动检查入口，取消旧运行。 | #711 / AC49 | satisfied | 同文件synchronize/Ready/base edited、merge ref/head guard/metadata lane身份与cancel-in-progress控制面回归 |
| R50 | main Evidence reuse、Change Archive、正式Release与三个strict required identity不回归。 | #711 / AC50 | satisfied | 同文件main tree reuse/archive/release/3 strict identity永久回归；实时保护在合并前再次读取，不能用本地替代远程事实 |
| R51 | 项目自有规则默认本地两步验收，USER_WAIVED如实记录，不改managed资产。 | #711 / AC51 | satisfied | AGENTS自有区/USAGE/Blueprint06本地两步流程；managed区无改动；人工验收当前PENDING，不冒充通过 |
| R52 | Workflow责任审计/Evidence保留映射后消除确认重复Setup/Install/Build，保持必要Runtime/Release验证。 | #711 / AC52 | satisfied | Blueprint06 Workflow责任与Evidence Preservation Mapping；#710配置风险避免无关Runtime/镜像/DB/Browser，真实部署风险保留 |
| R53 | 定向验证优先、充分旧证据复用、Review整批收敛；DB热点有真实基线而不无界重构。 | #711 / AC53 | satisfied | 同文件定向Red/Green、冻结hash证据复用/整批修复限定复审；真实PG suite耗时/固定1与100查询数，无共享DB并行或timeout放宽 |
| R54 | 用#710及本轮真实CI执行次数/时长/关键路径证明优化，不能仅宣称YAML减少。 | #711 / AC54 | explicitly_deferred | explicitly_deferred仅指已批准PRA→PRB顺序中的post-merge真实模板Runner采样；MEDIA_CI_EVIDENCE已有#710真实旧时长/4文件反例，新Workflow自身须full；Issue AC54保持未勾选，采样后回写，不免除该验收 |
| R55 | 三项本地成果经独立Review、current-head/base required CI及受保护PR合并main，取得implementation main-fresh、原生归档及archive governance fresh；全部AC闭合后完成Closure和关单，再清理本次已合并未使用的任务分支和临时资源；不Release/Deploy/生产操作。 | #711 / AC55 与生命周期附录 | explicitly_deferred | explicitly_deferred仅指授权的post-merge main-fresh/原生归档/Closure及清理阶段；独立Review已闭合，人工Gate仍PENDING，正式current-head/base CI及保护须在merge前实际满足；Issue AC55保持未勾选，禁止据此先关单 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Content/Collection/Vehicles Repository 与 bootstrap | 合并、冻结及 Evidence 原子收敛 | 当前 Writer 缺口 | R1–R8、E1–E5 |
| Analysis tables/Repository 与 Migration | 正式复用、有效结果/人工来源 | 保留真实历史 | R9–R18 |
| Content projection/query、Reporting/Workbench | 消费统一有效结果 | 端到端一致 | R19–R20 |
| 既有 Job/管理接线、tests、frontend/e2e-fullstack | 历史修复与回归 | 有界恢复和真实接线 | R21–R22 |
| 小红书 Operation/Mapper、Content 媒体 Owner、缓存与来源撤销 | 真实类型、媒体完整性、属性新鲜度及视频封面 | 重复补采不丢有效事实，保持生产单一写入口 | R23–R27、R36–R38 |
| Content Playback Service/Repository、Collection media_refresh、流式 Provider 与 HTTP | 正式持久准备任务、短期会话、一次收费预算及受控转发 | 站内播放和失败恢复；稳定事实与可失效来源分离 | R30–R39 |
| Content Contract、生成 OpenAPI/Client、0085/0086 | 媒体观测元数据、播放状态与公共能力 | 兼容历史数据并明确部署/回滚边界 | R38–R42 |
| 声音广场 Gallery/Player/Drawer/Table、采集中心及任务中心消费者、Nginx | 完整图片、真实视频标识、原生播放状态和安全代理配置 | 用户路径和服务端实际能力闭环 | R28–R41 |
| 唯一 CI classifier、validate_changed、模板/文档检查、四 Workflow 与项目自有规则 | 正确变更范围、配置风险分层、同步触发、Preflight及证明责任 | 提速保留 required checks、安全和正式发布责任 | R43–R54 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Hash、解析、作者合并和持久任务规则 |
| 接口 / 契约 | required | Schema/Migration、生成物及管理入口兼容 |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL：事务、约束、并发、Fencing、人工与消费者 |
| 用户 / 工作流验收 | required | 原补采刷新证据可复用；新增图片/视频/准备恢复与切帖Browser验收；人工验收状态如实单列 |
| 跨组件关键路径 | required | 真实 Vue/API/DB/Worker，外部 Provider 用受控 Fake |
| 外部依赖 / 供应方探测 | required | 新增媒体范围要求有界真实TikHub字段与CDN证据；已完成6次TikHub Probe，不追加付费请求；部署出口边界单列 |
| 构建 / 打包 / 运行 | required | 前端 Build、隔离 Migration/服务启动 |
| 文档 / 治理 / 其他 | required | changed-scope、Owner、架构、Secret、文档与完成检查 |

## 验证计划

目标命令在隔离 PostgreSQL 环境执行 pytest 新回归及相关 content/collection/vehicles/analysis 集成套件；使用 python scripts/dev/validate_changed.py --base origin/main 取得 CI 同源范围，执行所需本地静态、Contract、前端和真实 Full-stack 验证。完成前运行 python scripts/quality/check_change_completion.py --root . --require-active-ready。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 作者快照、人工来源和投影跨层一致性 | 锁保护、统一选择与 PostgreSQL 回归 |
| 兼容性 | 历史 Run/Result/Prompt 不变 | 只新增引用事实，直接结果优先 |
| 数据 / Migration | 新 DDL，无自动全量回填 | 历史修复独立有界 Job |
| 部署 / 运行 | 仅隔离本地与受保护 Git 交付 | 不迁移用户在用库；已授权的六次真实 TikHub Probe 已完成，不追加付费请求；部署出口验证未完成 |
| 回滚 / 恢复 | 先排空新协议任务再按兼容版本回退 | 新 v2 Media Delta、新 v6 Run 不能由不支持它们的旧业务 Worker 继续处理；DDL往返不代表任意旧软件可安全回滚 |

# 文档、依赖、部署与发布影响

同步 Product、Blueprint、Operations、开发指南及 Analysis/Content/Collection/Provider 模块 README。依赖和 Runtime 保持锁定版本；真实 Probe 凭据不入 Git、日志或报告，未添加公共 CDN 签名地址。新增 Playback Contract 通过生产生成器同步 OpenAPI 和 TypeScript Client；0085/0086 仅升级隔离测试库。本轮不发布、不部署、不操作生产数据。

# 完成审计

- [x] upstream_re_read：已live重读Issue #711，55AC及生命周期附录与canonical已澄清正文逐字一致；重新对照三份用户任务书与最新合并清理授权，逐55AC重建本地完成定义。
- [x] change_coverage：R1–R53直接证据已逐项映射，受影响旧路径经相邻PG/真实浏览器复验；R54/R55仅按上游既定交付顺序保留post-merge阶段，未提前勾选Issue，pre-merge门禁不豁免。
- [x] reverse_audit：逐层反查正常补采/Replay到媒体Owner、prepare到正式Job/Attempt/Raw和只读观察、stream到Principal/安全CDN/取消、前端到生成Contract、selector到CI/Runtime/Tooling/Release及三个required identity；main收尾仍按授权后续阶段执行。
- [x] unresolved_cleared：补采、媒体基础/代理/Service、CI、前端及Docs的整批material Findings均经独立限定复审closed；BR-R3与真实Chrome/CDN最后路径通过。人工Gate、远程required CI及post-merge事实仍如实单列，未冒充已取得。

# 完成证据与状态

## 补采阶段已取得证据（90013af0完成边界）

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V0 | caf06ae1 / Windows | git fetch origin main、git status --short、git switch -c fix/supplement-result-consistency origin/main | 成功；起始工作区干净 | 本地开发基线 |
| V1 | 4f84afc8 / decision_epoch=1 | Parent 与独立 Reviewer 对照用户任务书执行 Development Preflight | PASS；不代表实现完成 | 需求、范围、验证与本地交付边界可进入实现 |
| V2 | 隔离 localhost:25439 / PostgreSQL 18.4 | .venv/Scripts/python.exe -m alembic upgrade head | exit 0 | 正式 Migration 在本任务空测试库可执行 |
| V3 | 本地 Change | .venv/Scripts/python.exe scripts/quality/check_change_completion.py --root D:/test/AIMA_UGC | PASS | in_progress Change 元数据与项目 carrier 合法，尚未执行 Ready 门禁 |
| V4 | 仅治理 diff | .venv/Scripts/python.exe scripts/dev/validate_changed.py --base origin/main --json | governance_only | 初始治理 checkpoint 的 CI 范围；实现完成后重新计算 |
| V5 | caf06ae1 原实现 / 隔离 PostgreSQL | 新作者快照参数回归、补采空匹配和新 Run 快照回归 | 作者四参数 4 failed；空补采 1 failed/Discovery 1 passed；目录快照 1 failed | 修复前直接失败证据 |
| V6 | Content/Brand 切片工作树 / 4f84afc8 | pytest：test_supplement_author_snapshots、test_collection_content_runtime、test_collection_content_supplement、test_collection_date_supplement、test_excel_follower_count_voice_plaza | 23 passed / 16.40s | 稀疏快照、完整 Current、空匹配、人工锁、错误身份及事务回滚 |
| V7 | 同切片 | pytest：test_content_current_concurrency、test_content_audit_regressions、test_brand_replay_owner_baseline、test_collection_scope_runtime、test_collection_scope_decision_bridge | 25 passed / 7.58s | Content、来源审计、Replay、Scope 和桥接相邻回归 |
| V8 | 同切片最后类型修复后 | 作者快照四参数 pytest；mypy 五个生产文件；ruff check/format 九文件；git diff --check | 4 passed；类型/格式/diff PASS | 最后局部变量及行尾修正后的新鲜证据 |
| V9 | Analysis C/D 工作树 / 专用隔离库 | test_analysis_version_reuse：正式 Excel → Analysis Planner/Shard → 只修改发布时间再导入 | 旧实现 stale 真 Red；新实现 completed Green，Result/Run 数未增加 | 非模型输入跨版本复用的首条直接回归；尚非完整 C/D 验收 |
| V10 | 前端现有实现 / Windows + Chrome | D:/node/npm.ps1 --prefix frontend run test -- --run | 38 文件 / 306 tests passed | 完整前端单元回归，不作为真实服务端接线证据 |
| V11 | 同前端 revision | D:/node/npm.ps1 --prefix frontend run test:e2e -- --workers=3 | 206 passed / 3.4m | 完整 Browser Mock 回归；真实 Full-stack 仍单独执行 |
| V12 | 同前端 revision | D:/node/npm.ps1 --prefix frontend run build | TypeScript Native、Vue 类型检查及 Vite Build PASS | 当前前端生产构建；既有大 chunk 提示不阻塞构建 |
| V13 | 既有 frontend/package-lock.json | D:/node/npm.ps1 --prefix frontend audit --audit-level=high | found 0 vulnerabilities | 当前锁定前端依赖只读审计；没有升级依赖 |
| V14 | Analysis C/D 与作者解绑修复最终工作树 / 隔离 PostgreSQL | pytest test_analysis_version_reuse、test_supplement_author_snapshots、test_content_current_concurrency、test_excel_follower_count_voice_plaza，-q --tb=short --show-capture=no | 36 passed / 36.69s | 22 Analysis、8作者快照、6相邻回归；包含真实锁等待、关联写入后整体回滚及100目标固定查询数 |
| V15 | 同 C/D 工作树 | pytest：stage8d_voice_plaza、stage12_analysis_runs、manual/bidirectional relevance、workbench、database_reports、u1_u5、schema_runtime_invariants、collection_content_runtime | 39 passed / 10 report guard skipped / 24.93s | 相邻消费者；报告跳过将由固定专用隔离库补跑 |
| V16 | 0083 / 专用隔离库 | alembic downgrade 20261003_0082 → upgrade head → check → current；mypy 20生产文件；ruff check/format 29文件；git diff --check | 全部 PASS；head=20261009_0083；No new upgrade operations detected | 新结构往返、Schema 与当前切片静态质量 |
| V17 | Parent Full-stack/Docs 切片 | npm --prefix frontend run lint；ruff check/format 三个 fullstack fixture；check_docs.py；check_docs_facts.py | 全部 PASS | 新增真实浏览器回归静态接线、定向文档链接和当前机器事实；尚未运行 Full-stack |
| V18 | 本地完整后端 / 本任务隔离配置 | pytest tests/unit tests/contracts tests/api -q --tb=short --show-capture=no；移除本进程 AIMA_EXTERNAL_SECRET_DIR 后 pytest tests/api 同参数 | 首轮 2094 passed / 16 skipped / 12 subtests，1 项 API 因测试 Secret 路径环境覆盖失败；清理覆盖后 API 全套 106 passed | Unit/Contract 与 API 全量通过；跳过是既有 Windows/POSIX、符号链接及 Linux Noto 字体条件，不作为通过计数；未修改测试或生产 Secret |
| V19 | 当前内部表和公开 Contract | check_agent_governance.py、scan_secrets.py、check_architecture.py、check_table_ownership.py、scripts/contracts/generate.py --check、check_compatibility.py | 全部 PASS | 新 Owner 接线、架构、Secret、生成 Contract 和 HTTP 兼容性未漂移；不代表 repair 运行已验收 |
| V20 | browser 专用库 / head 20261009_0084 / 真 API、PostgreSQL、Worker，Fake Provider/LLM | npm --prefix frontend run test:e2e:fullstack -- comment-supplement.spec.ts -g 补采形成等价 | 1 passed / 25.9s；首轮 spec 误用 POST 已改为正式 PUT | 页面导入→补采→AI→三项人工纠正→非输入补采；版本+1、原 Result 时间/Model/人工锁有效、多品牌车型归属和 mixed、Run/LLM 请求不增加；详情不导航/不手刷自动显示新发布时间；成功截图保存在本任务 runtime |
| V21 | 同专用真实全栈 | scripts/dev/check_local_stack.py --require-ready | PASS | 8090 API readiness、5173 Vite 与代理，以及 PostgreSQL 联调；尚不代表全量 Full-stack 通过 |
| V22 | 同真实 API/DB/Worker/Chrome 隔离环境 | npm --prefix frontend run test:e2e:fullstack；修正后 npm --prefix frontend run lint | 20 passed / 4.6m；lint PASS | 全部 Full-stack 回归及新增补采链实际通过；测试拥有的5个进程树按PID/启动时间清理，8090/8091/4174/5173均释放 |
| V23 | 独立 Tester / report专用空库55437 / 0083、0084内容哈希稳定 | alembic upgrade/current/check；verify_migration_compatibility.py；pytest tests/integration/reporting；显式REPORT_BROWSER_ACCEPTANCE单跑浏览器项 | 14个历史checkpoint（含base）升级/降级/Schema无漂移；9 passed + browser 1 passed | 全10项报告实际执行；Chrome→Vue→正式API/Worker→DOCX下载；无数据库guard残余skip；55439/55440自有资源清理完毕 |
| V24 | 最终Content测试 / 25439专用库 | pytest tests/integration/collection/test_collection_content_runtime.py -q --tb=short --show-capture=no | 14 passed / 6.82s | 新增title/text后来出现新品牌的真实补采时序两参数；版本+1、旧/新全部品牌、实际匹配字段/文本/目录版本 |
| V25 | 最终repair与两Owner batch / 专用库 | pytest test_content_consistency_repair + test_content_reclassification_postgres + test_brand_first_frozen_cleanup + test_collection_content_runtime -q；canonical_replay_worker -k人工锁 | 47 passed / 59.05s（30repair+17相邻）；Replay 2 passed / 6.32s；0084→0083→0084/check PASS | 只读预检、显式有限目标、冻结目录、空锁/墓碑、独立人工来源、正式Runtime重试/接管/取消、业务+checkpoint原子回滚、二次修复不重复 |
| V26 | 同最终repair / 真实SQLAlchemy执行事件 | pytest repair -k query_count或owner_batch_queries --junitxml=.runtime/supplement-consistency/repair-performance.xml | 3 passed / 8.67s；1/100：预检11/11、自动apply54/54、人工carry10/10 | 原人工carry Red 14/1004，集合化Green固定查询数；无单Content N+1或全库目标扫描；局部量级证据 |
| V27 | Writer释放后最终后端 | pytest tests/unit tests/contracts tests/api -q -rs --tb=short --show-capture=no，移除测试外部Secret覆盖 | 2095 passed / 16既有平台skip / 12subtests / 162.15s；全461源mypy PASS；956文件ruffformat与lint PASS | 最终Owner修改后的完整单元/Contract/API与静态质量 |
| V28 | 最终文档/Contract/Package | 文档/事实/治理/Secret/架构/Owner全部项目检查；正式generate.py + npm generate:api + check/compat；uv离线build、按uv.lock导出依赖同步全新Wheel环境、-I安装包导入 | 全PASS；生成物语义无变化；导入来自Wheel独立site-packages，包含新模块及Prompt资源 | 正式文档与代码一致；无公共API变化；唯一根工程打包可用、无依赖升级 |
| V29 | 最终相邻测试修正 / 25439专用库 | pytest test_collection_worker_runtime.py + test_xiaohongshu_incremental_comments_runtime.py -q --tb=short --show-capture=no | 2 passed / 4.18s | 新Job注册完整集合断言同步；小红书历史种子由正式Content Owner和真实来源夹具创建Current+Version，原评论分页断言不变 |
| V30 | 整批Review返修 / 25439专用库 | 新6报告依据+2带数据降级Red/Green；Replay两参数；完整test_analysis_version_reuse.py | Red3 failed/5 pass；定向Green10 passed/17.17s；完整Analysis30 passed/69.38s | 报告缺键/null不算人工，真实/继承/解锁对象保留基线；降级只定向收敛引用Content，直接结果和无关Content不变；Replay集合读取与总SQL/撤销全部通过 |
| V31 | 同返修最终源 | report_runs mypy；全956文件ruff format/check；离线重建并重装独立Wheel，python -I核最终实现 | 全PASS | 两项生产修复静态/构建新鲜证据；其他稳定生产源未变化 |
| V32 | 8a10f441 / 两个独立Reviewer | 主审baseline challenge与漏审恢复；blind限定repair re-review；直接Git/hash绑定 | F-B1/F-B2均resolved；无新增blocking Finding | 首轮整批审查→最小返修→限定复审闭环，静态通过不替代剩余独立运行结果 |
| V33 | 8a10f441 / 独立Tester / 55437专用库 | 完整Replay42、报告9+真实browser1、正式14历史Migration checkpoint、新8项回归、upgrade/current/check | 全PASS；42/127.23s，9/28.44s，1/8.12s，8/14.53s；head0084/无metadata漂移；起止hash一致 | 两项修复的独立运行证据与全部广域回归闭合；测试DB/进程lease已释放 |
| V34 | 最终本地Completion / 8a10f441同生产源 | check_change_completion.py --require-active-ready --json；治理/Secret/架构/表Owner/Docs/DocsFacts；容器完整ID/标签/端口核对后清理 | 全PASS；ok=true/strict163/errors空；两个自有测试容器和匿名volume已移除，全部测试端口释放 | 本地技术完成、逐需求审计与资源清理；后续提交仅Evidence/Change，不改变已审查生产源 |

## 未验证内容与剩余风险

原补采阶段技术证据见上表及EVIDENCE.md，Windows/POSIX skip和无40M生产容量/生产Migration/生产修复结论仍保持。新增媒体与CI的本地技术证据和独立复审已闭合；人工Gate、远程CI及后续交付事实尚未取得。真实CDN部署出口、费用实际账单与Mock/本地证据需分别报告，不作无依据强结论。

## 交付状态

- Requirement Source：#711，canonical create与live同检PASS；55AC为当前完整完成定义。
- 分支：fix/supplement-result-consistency，保留4f84afc8/9ddc6513/8a10f441/90013af0四个本地提交。
- 整体：in_progress，新增范围重新执行适用Completion与独立Review。
- 用户人工验收：未发生，不冒充通过；主分支交付及任务清理已获明确授权。
- PR/远程CI/merge/main-fresh/archive/Closure/清理：尚未执行。
- Release/Deploy/生产数据：非目标。

## 备注

Parent管理唯一Change、集成及资源清理。所有Agent共享checkout；CI切片已冻结后，后端Writer独占Backend/Contract/Generated与PostgreSQL 25449，前端Writer仅负责声音广场、视频准备任务消费者、相关前端测试和Nginx，公共播放Contract已冻结且生成物由后端单独维护。Parent仅维护Change/定向文档与隔离浏览器PostgreSQL 25450，避免路径和运行环境交叉写入。独立Reviewer只读，测试仅操作已验证属于任务的隔离环境。既有EVIDENCE保留补采阶段历史，新增证据单独记入本Change的MEDIA_CI_EVIDENCE.md。
