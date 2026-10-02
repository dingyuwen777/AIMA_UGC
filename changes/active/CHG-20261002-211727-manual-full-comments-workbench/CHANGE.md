---
schema: coding-change/v1
id: CHG-20261002-211727-manual-full-comments-workbench
title: 主动采集默认全量评论与工作台交互修复
level: L3
status: ready_for_review
owner: codex
branch: codex/manual-full-comments-workbench
created: 2026-10-02
updated: 2026-10-02
completion_gate: required
depends_on: []
affected_areas:
  - collection
  - content
  - workbench
  - voice-plaza
  - contracts
  - docs
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - frontend/src/features/collection-supplement
  - frontend/src/features/import-batches
  - frontend/src/features/workbench
  - frontend/src/features/voice-plaza
  - tests/contracts
  - tests/integration/collection
  - frontend/tests
  - frontend/e2e
  - frontend/e2e-fullstack
  - contracts
  - frontend/src/generated
  - docs/product
  - docs/blueprint
contracts:
  - CollectionRunCreateRequest
  - CollectionSupplementPreviewRequest
data_changes: []
---

# 变更摘要

用户主动采集的二级回复默认关闭，一次性发现仍冻结 Adaptive。统一三个主动入口默认全量一级评论和二级回复，同时恢复工作台已应用筛选、雷达标签选择及无活动任务时的声音广场展示。

# 背景、现状与问题

## 背景

用户要求依次实施引用对话的两份方案。本 Change 只承担第一阶段；第二阶段按账号补采另建正式单元。

## 当前现状

main 77060d1c：HTTP 默认 include_sub_comments=false；手动 Run comment_policy=adaptive；工作台 filters 只在内存；雷达依赖图形事件及隐藏按钮；声音广场永久渲染活动任务区域。

## 问题、根因或约束

默认和快照策略分散，导致主动入口实际行为不一致。页面缺少可恢复的已应用筛选事实及可见标签交互。全量表示 Provider 当前可访问范围，必须保留分页安全上限及 partial。

## 不修改的后果

用户省略选项会漏采回复，主动发现会抽样；页面刷新丢失筛选，标签切换不可靠，无任务仍占用展示区域。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 默认二级回复 false | contracts/http.py；test_manual_comment_defaults.py 本轮 3 failed | 明确更改请求默认与三个页面入口 |
| E2 | 手动 Run 冻结 adaptive | bootstrap/collection_http.py:create_run | 同时冻结 policy.comment_mode=full |
| E3 | Full 引擎已存在 | run_policy.py；test_tikhub_plan_full_comments.py | 复用正式引擎，保留页上限 |
| E4 | filters 不持久化；几何已计算标签边界 | workbench/store.ts；radarGeometry.ts | sessionStorage 与已有几何复用 |
| E5 | 重复补采不生成新版本时，版本来源关联漏掉该次成功入库 | 单一 Full-stack Journey 失败；PG 两条重复来源回归 Red | 结果查询补充成功 Candidate Ingestion 关联，保持业务版本不变 |

## 推断与待确认

隔离 PostgreSQL 评论策略 109 项、声音广场及来源 15 项、197 项 Browser Mock 和单一五平台 Full-stack Journey 均已有通过证据。独立返修复核和当前 head/base CI 尚未完成。

# 目标、成功标准与非目标

## 目标

主动采集默认完整评论；刷新恢复工作台条件；每个一级心智标签可操作并显示对应详情；无活动任务隐藏 AI 区域。

## 成功标准

- [x] Issue #696 AC1–AC7 对应实现、测试与文档证据完整。
- [ ] 本地验证、独立 Review、当前 head/base CI 满足交付门禁。

## 范围

HTTP 默认与手动策略、三个主动入口、工作台筛选与雷达、声音广场活动任务区域、重复补采结果来源关联及直接相关测试、生成物和正式文档。来源关联修复来自必须验收的重复补采流程，不另造写入账本或业务版本。

## 非目标

账号补采另阶段；不修改周期计划默认，不增加 endpoint、依赖或 Schema，不部署生产，不改变安全页上限。

## 必须保持不变

历史快照、周期策略、Raw/Canonical/Owner 入库、Job 恢复/取消、Preview 指纹冲突、北京时区和生成 Client。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 根 Agent 唯一写入；独立只读 Review | #696 | collection/workbench/voice-plaza |
| 接口与契约 | 默认二级开启，显式 false 继续有效 | #696 / AC1 | 生成消费者同步 |
| 数据与迁移 | 不新增表列、不重写历史快照 | E2/E3 | 无 Migration |
| 错误与失败语义 | 保留 409、partial、安全页上限 | #696 / AC6 | 不承诺第三方不可访问数据 |
| 兼容性 | 周期 Adaptive/Full 按原选择 | #696 / AC2 | 仅新手动 Run 冻结 Full |
| 部署与回滚 | 用户仅要求合并 main | 用户指令 | 无生产部署；可回滚代码 |

# 修改方案与决策依据

## 最小充分方案

1. HTTP 默认与前端公共默认开启一级/二级；手动 Run 冻结一致 Full，生成 Contract。验证默认、关闭与 PG 快照。
2. 工作台参考目录加载后恢复 schema_version 筛选；复用归一化与 Taxonomy 清理，set/reset 持久化。验证 reload 首次请求与损坏/过期条件。
3. 按 radarGeometry 渲染可见 HTML 标签按钮，单一 selectedMind 驱动高亮与右侧详情。验证鼠标、键盘、指标和下钻。
4. 活动任务非空才显示区域；同步正式文档。验证终态消失和轮询不回归。
5. 本地分层验收、完成审计、独立两阶段 Review、CI、merge、原生 Archive/main-fresh/Closure。
6. 返修保留目录读取失败时的已存车型条件；将隐含跨用例前置状态合并为单一 Journey。该 Journey 复现的重复补采来源遗漏使用现有成功入库账本补齐，投影与回退共用关联，列表、计数和冻结目标同义。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1/E2/E3 | 同时闭合默认及正式执行策略，不另造采集引擎 |
| D2 | E4 | 持久已应用条件，复用参考目录与标签几何 |

## 备选方案与取舍

仅修改 UI 默认不能修复省略字段调用或主动发现 Adaptive；仅使用 ECharts 文本事件不能稳定提供键盘及选中态。选用已批准的 HTTP/快照/HTML 标签完整闭环。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 主动入口默认评论回复且可关闭 | #696 / AC1 | satisfied | V1/V2/V4/V7/V9/V10：HTTP 默认与非法组合、三个入口/重开/关闭；默认全量回复实际入库 |
| R2 | 新手动 Run Full，周期历史兼容 | #696 / AC2 | satisfied | V2/V3：手动发现四种请求选项冻结 Full 一致；原周期及历史配置回归 |
| R3 | 完整已应用筛选恢复与安全清理 | #696 / AC3 | satisfied | V4/V7/V10：三个首次请求直接恢复日期及条件，reset/损坏 storage/目录失效/目录读取失败 |
| R4 | 可见可操作标签与详情高亮联动 | #696 / AC4 | satisfied | V4/V7：按钮鼠标及键盘、aria-pressed、右侧标题指标/二级详情/下钻，refresh 及指标切换保留选择 |
| R5 | 无活动任务隐藏 AI 区域 | #696 / AC5 | satisfied | V4/V7：空与终态隐藏，活动进度、轮询及历史入口继续有效 |
| R6 | 本地各层证据与分页边界 | #696 / AC6 | satisfied | V2–V11：真实 PG Full 500/30/100 页与 partial，Browser/完整实链、重复来源及去重、构建及生成物；Fake 不冒充真实 Provider |
| R7 | 正式文档与无迁移依赖升级 | #696 / AC7 | satisfied | V5/V11：Product 02/Blueprint 08 与实现同步；check_docs PASS；锁文件与 Migration 无变更 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| contracts/http.py、collection_http.py、生成物 | 默认及冻结 Full | E1/E2 | R1/R2 |
| collection-supplement、TikHubSupplementDialog | 共用开启默认及关闭联动 | 三个入口一致 | R1 |
| workbench/store.ts | 已应用筛选持久与恢复 | E4 | R3 |
| BrandMindCard.vue | 可见按钮与动态详情标题 | E4 | R4 |
| VoicePlazaPage.vue | 活动区域条件渲染 | 当前永久区域 | R5 |
| content_queries.py、collection content runtime regression | 成功入库账本补齐重复采集来源 | E5，不伪造新版本 | R6 |
| 相关测试与正式文档 | 回归、验收及事实同步 | Requirement | R6/R7 |

- [x] 调查当前实现和事实源
- [x] 建立任务路由和验证矩阵
- [x] 默认行为建立失败证据
- [x] 完成最小充分实现
- [x] 同步受影响长期文档
- [x] 取得当前版本验证证据
- [x] 完成追溯与完成审计；Final Ready 复核另绑定最终 head

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 评论 Full 引擎及前端 store/选项/标签/任务回归 |
| 接口 / 契约 | required | HTTP 默认、非法组合、生成 OpenAPI/Client |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL 手动 Run 冻结与历史兼容 |
| 用户 / 工作流验收 | required | 浏览器补采选项、reload、标签详情/下钻、活动任务 |
| 跨组件关键路径 | required | 正式 comment-supplement Full-stack |
| 外部依赖 / 供应方探测 | not_applicable | 无新 endpoint/Mapper；现有 Full 引擎回归证明本轮接线 |
| 构建 / 打包 / 运行 | required | lint、typecheck、build、generated checks |
| 文档 / 治理 / 其他 | required | 文档检查、Change 完成门禁、Review/CI |

## 验证计划

- pytest Contract、Full 评论运行及相关 collection HTTP 集成。
- Vitest collection-supplement/workbench/voice-plaza；Playwright workbench 和相关流程。
- 真实 PostgreSQL 与 comment-supplement Full-stack 使用隔离状态。
- python scripts/dev/validate_changed.py --base origin/main；python scripts/quality/check_change_completion.py --root . --require-active-ready。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 默认增加请求/费用/时长 | 页面明确范围，保留关闭与安全上限 |
| 兼容性 | 默认语义调整已获用户批准 | 显式选项、历史快照及周期策略保留 |
| 数据 / Migration | 不适用 | 不改变数据库 Schema 或存量数据 |
| 部署 / 运行 | 无本轮部署 | 用户要求本地验证并合并 main |
| 回滚 / 恢复 | 可回滚实现提交 | 无数据迁移；既有冻结 Run 继续执行原语义 |

# 文档、依赖、部署与发布影响

- **长期文档**：docs/product/02 与 docs/blueprint/08 按实现同步评论默认、筛选恢复与标签联动。
- **依赖 / Runtime**：不适用，无升级或新增。
- **配置 / Secret**：仅浏览器 sessionStorage 版本化筛选；不写 Secret。
- **部署 / Release**：不适用，本轮无生产部署授权要求。
- **兼容 / 消费方通知**：生成 Contract 与页面提示体现默认及调用量影响。

# 完成审计

- [x] upstream_re_read：2026-10-02 重新读取 live #696 与引用对话第一阶段完整方案（20 节）；主动入口默认/Full、首次请求恢复、雷达每标签/右侧/下钻、空活动任务四组要求分别重建。
- [x] change_coverage：AC1–AC7 与 R1–R7 全部对应实现、分层测试和正式文档，无遗漏及擅自延期；账号方案明确是后续独立单元，不以第一阶段代替整体交付。
- [x] reverse_audit：HTTP 默认→生成物→三个入口→冻结 Run→Job/Raw/入库/覆盖→结果/评论详情；恢复条件→三个首请求；雷达选择→详情与原声；活动任务→轮询/终态/历史。完整 Journey 的反向结果核对发现并修复重复补采来源遗漏。
- [x] unresolved_cleared：not_satisfied 清零，原 F-P1-01/F-P1-02 经独立 REPAIR_VERIFY 关闭。代码局部完成不冒充人工验收/远程 CI/merge，后者按交付状态持续留待取得真实证据。

验证资产冗余检查：clean。分页 500/30/100 复用既有生产 Full 引擎；新增 Contract 和手动 Run 测试证明接线，前端与 PG 分别承担各自边界；两个隐含依赖的 Full-stack 用例合并为一个自主建立前置状态的 Journey，没有复制 Provider 实现。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | main 77060d1c + 新测试；本地 Python | pytest tests/contracts/test_manual_comment_defaults.py -q | 3 failed，断言 include_sub_comments True | 已复现默认关闭 |
| V2 | 本地实现 / Python 3.14.7 | pytest tests/unit tests/contracts tests/api -q | 2014 passed、16 skipped、12 subtests passed | 后端及 Contract 回归 |
| V3 | 本地实现 / 隔离 PostgreSQL 18.4 / head 20261002_0079 | collection HTTP/date/selected/comment coverage 四个 integration 文件 | 109 passed | 默认 Full 快照、原 Full 500/30/100 页边界 |
| V4 | 本地实现 / Node 24.19.0 | npm --prefix frontend run test -- --run；lint；build | 304 passed；lint/typecheck/build PASS | store、默认选项、AI 活动状态与构建 |
| V5 | 本地实现 | generate.py --check；check_compatibility.py；mypy backend/src；ruff；check_docs.py | PASS | 生成物、兼容性、类型与文档 |
| V6 | 本地实现 / 全新隔离 DB + API + Fake Worker | comment-supplement.spec.ts 首个五平台日期用例 | PASS，18.3s | 浏览器默认回复到 Raw/Job/业务库和评论详情 |
| V7 | d5cffdfe / Browser Mock / workers=2 | npm --prefix frontend run test:e2e -- --workers=2 | 197 passed | 包含首次恢复请求、可见雷达、默认选项及活动任务流程 |
| V8 | 返修工作树 / 真 PostgreSQL 18.4 | test_collection_content_runtime.py -k repeated_unchanged：先 Red 后 Green；同文件及 test_stage8d_voice_plaza_runtime.py | Red 2 failed；Green 15 passed | 内容不变仍关联两次 Run，未入库 Run 不关联；投影/回退、列表/计数/目标冻结一致，业务版本仍只有 1 个 |
| V9 | 返修工作树 / 全新 aima_comments_source_fixed + API + Fake Worker + Browser | comment-supplement.spec.ts 单一完整 Journey | 1 passed，26.4s | 五平台导入→日期补采→勾选补采→重复补采，无跨用例依赖，结果来源及评论回复不重复 |
| V10 | 返修工作树 / 本地锁定工具链 | pytest tests/unit tests/contracts tests/api -q；mypy backend/src；frontend test/lint/typecheck | 2014 passed、16 skipped、12 subtests；437 source files PASS；305 passed；lint/typecheck PASS | 来源查询与目录加载失败返修未破坏其他行为 |
| V11 | e42b39c6 / 隔离 PostgreSQL 18.4 / 锁定本地工具链 | import_campaign_revocation_postgres.py；frontend build；generate.py --check；check_compatibility.py；ruff format --check/check；check_docs.py；validate_changed.py --base origin/main | 6 passed；构建/生成/兼容/静态/文档 PASS；classifier 输出 27 个 changed paths 与 contract profile | 当前来源修复未绕过撤销可见性；生成物/类型/构建及正式文档一致，复用 CI 唯一范围分类 |
| V12 | reviewed head e42b39c61750cf4004d73064b4f2ed9a38a34dd8 / base 77060d1c49303ebf95542c2bb049159f2d7f4be5 | 独立 phase1_acceptance_review：First Assembly → REPAIR_VERIFY | NO_FINDINGS_WITHIN_SCOPE；F-P1-01/F-P1-02 CLOSED | 原阻塞问题及新增成功入库来源关联均已按实际代码/消费者/证据复核，无本轮阻塞 Finding |
| V13 | reviewed head 139752e3446bc3172c4a40a3e4effeb695a01795 / base 77060d1c49303ebf95542c2bb049159f2d7f4be5 | 独立 phase1_acceptance_review：Final Ready 增量审查 | NO_FINDINGS_WITHIN_SCOPE | 相对返修版本仅有 Change 完成审计与元数据修正，原验证保持代表性；CI 和人工验收不由审查结论替代 |

## 未验证内容与剩余风险

第一阶段人工本地验收等待按用户 2026-10-02 最新指示“第一阶段做完了就提交远程分析啊”及“你自己测试功能没问题之后直接合并到远程主分支就行”记为 USER_WAIVED：用户明确要求自行测试后直接提交和合并，因此不再以尚未人工操作页面阻塞第一阶段实现推送；该覆盖不冒充 PASSED，不跳过技术验证、独立 Review 或 current-head/current-base CI。独立 REPAIR_VERIFY 及 139752e3 的 Final Ready 增量审查已通过；本次只更新交付事实，远程 CI 仍待推送后取得。第一阶段功能验证的 TikHub 请求使用 Fake，不冒充真实 Provider 结构探测。新增来源条件未做生产大规模性能实测，不据既有索引宣称容量已验证。现有 Pydantic/Starlette deprecated 与构建 chunk size 警告保留，无本轮升级或断言放宽。

## 交付状态

- 提交：治理/Red 6ea6481；实现 checkpoint d5cffdfe；返修 checkpoint e42b39c6；完成审计 139752e3；本次交付事实更新后推送。
- 拉取请求：#697，本次按用户新指示推送第一阶段实现并更新 PR；进入 Ready 前继续核对最终 head 的增量审查与必要门禁。
- CI：既有远程结果只对应早期治理/Red head，不代表当前实现；推送后取得本次 head/base 的新鲜 CI。
- 合并：尚未合并。
- Change 归档：合并后由原生 Workflow 完成。
- 发布 / 部署：不适用，本轮仅要求 merge main。

## 备注

Requirement Source：https://github.com/dingyuwen777/AIMA_UGC/issues/696。用户已授权必要管理员合并；该权限不替代质量门禁。
