---
schema: coding-change/v1
id: CHG-20260913-001143-comment-thread-voice-plaza
title: 声音广场评论补采结果与父子关系展示
level: L3
status: ready_for_review
owner: dingyuwen777
branch: comment-thread-voice-plaza
created: 2026-09-13
updated: 2026-09-13
completion_gate: required
depends_on: []
affected_areas:
  - content
  - frontend
  - comments
  - docs
  - figma
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/bootstrap/api.py
  - frontend/src/features/voice-plaza/
  - tests/
  - docs/03_API接口说明.md
  - docs/blueprint/04_后端任务API与前端.md
  - docs/roadmap/04_五平台评论补采产品化实施方案.md
  - changes/active/CHG-20260913-001143-comment-thread-voice-plaza/CHANGE.md
contracts:
  - Content comments HTTP API
  - Voice Plaza comment thread UI
data_changes:
  - none
---

# 变更摘要

- **要解决的问题**：评论补采已经能把评论及 `root_comment_id`、`parent_comment_id` 写入 PostgreSQL，但内容详情 HTTP Contract 丢失层级字段、最多返回固定 100 条，声音广场又把评论藏在默认折叠区并按扁平列表展示。
- **拟议修改**：新增稳定分页的评论读取资源，保留根评论与直接父评论关系；声音广场提供清晰的评论区与“回复谁”提示；同步既有 Figma 详情抽屉。保持补采 Job、数据库 Schema 和已明确不需要的专用重试按钮/API 不变。
- **预期结果**：本地补采并入库后的评论可以从声音广场逐页查看全部结果，一级评论与二级回复的归属直观可辨。

# 背景、现状与问题

## 已确认事实

| 证据编号 | 已确认事实 | 来源 / 定位 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | `comments` 数据已保存 `root_comment_id` 和 `parent_comment_id` | `backend/src/aima_ugc/modules/content/tables.py`、Canonical Comment Contract | 不新增数据库列或历史迁移 |
| E2 | 内容详情响应不包含层级字段，查询固定 `limit=100` 且扁平排序 | `contracts/http.py`、`content_queries.py`、`content_http.py` | 需要独立分页读取资源，不能只改模板 |
| E3 | 声音广场评论位于默认折叠的“更多信息与评论”中并扁平渲染 | `ContentDetailDrawer.vue` | 评论入口需直接可见并按线程表达 |
| E4 | 正式产品方案明确不要专用“重试未完成项”API/按钮，评论从 PostgreSQL 读取 | `docs/roadmap/04_五平台评论补采产品化实施方案.md` | 本变更不扩展补采写入控制面 |
| E5 | 正式 Figma 声音广场页面为 `4627:7429`，详情设计为 `4627:8510`，公共详情 Body 组件为 `4861:31020` | 用户提供的 Figma 文件与本轮 metadata / component inspection | 在既有页面/组件上同步，不创建平行页面 |

## 推断与待确认

- 快手等 Provider 在只提供根级归属、没有直接父评论标识时，只显示“该一级评论下的回复”，不猜造“回复某条二级评论”。该降级语义将由测试固定。

# 目标、成功标准与非目标

## 成功标准

- [x] 评论 API 支持稳定分页，并能让调用方最终读取当前内容的全部已采集评论。
- [x] 每条评论保留根评论、直接父评论与可用的父评论作者信息；未知直接父级时不伪造。
- [x] 声音广场详情直接展示评论区，一级评论为主块、回复缩进，并以自然语言说明回复对象。
- [x] 加载、空、错误、继续加载状态均可理解，且区分数据库评论总数与当前已显示数量。
- [x] 生成 OpenAPI/TypeScript Client 与手写 Pydantic Contract 一致，既有内容详情调用保持兼容。
- [x] 后端、前端组件和跨层用户路径测试覆盖父子关系、分页及降级语义。
- [x] Figma 既有详情抽屉及其相关状态同步，并标记为 `SYNCHRONIZED_PENDING_HUMAN_REVIEW`。

## 范围

- Content Query/HTTP Contract、声音广场 Store/API/详情抽屉、生成客户端、测试与针对性长期文档。
- 使用本地已入库/补采数据做只读验收；必要时使用隔离测试数据库验证持久化查询。

## 非目标

- 不新增专用“重试未完成项”API 或按钮。
- 不修改 TikHub 端点选择、补采分页/费用策略或 Provider Mapper。
- 不新增头像、点赞交互、回复发布、评论审核或社交操作。
- 不发布 Release、不部署生产环境。

## 必须保持不变

- PostgreSQL 是评论业务事实源；页面不读取 staging/JSONL。
- 数据库 Schema、Canonical 评论字段语义、Content Detail 既有字段与路由兼容。
- Vue 3 + TypeScript + Vite + Pinia、Pydantic/OpenAPI/Orval 生成链和现有依赖版本不变。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 接口与契约 | 新增只读分页评论资源，内容详情既有评论字段兼容保留 | E2、E4 | 不破坏既有调用方，页面改用可分页资源 |
| 数据与迁移 | 不改 Schema、不回填；读取既有层级列 | E1 | 无 Migration |
| 错误与失败语义 | 评论区独立呈现加载/空/错误，详情主体不因评论加载失败而不可用 | 用户可见闭环要求 | 前端 Store 分离状态 |
| 兼容性 | 旧详情 API 保持，生成 Client 只由 OpenAPI 更新 | 项目 Contract 规则 | 不手改生成目录 |
| 部署与回滚 | 普通前后端版本发布；回滚代码即可 | 无 Schema/依赖变化 | 不需数据回滚 |

# 修改方案与决策依据

1. 在 PostgreSQL Query 与 Pydantic HTTP Contract 增加按根评论稳定分页的线程读取，回复按时间稳定排序并带直接父评论显示信息。
2. 在 FastAPI 暴露内容评论只读资源，补契约/持久化测试并重新生成 OpenAPI Client。
3. 声音广场 Store 独立管理评论分页状态；详情抽屉直接显示评论区、根评论与缩进回复、“回复某人/该评论”的自然语言关系及继续加载。
4. 用组件测试、API/数据库测试和本地数据只读探测验证“补采入库 → API → 页面模型”的关键路径。
5. 将同一布局、状态和说明同步到用户指定 Figma 既有详情抽屉，并保留人工视觉评审门禁。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 本地补采后的全部评论可在声音广场逐页查看 | #473 / AC1 | satisfied | 正式补采评论/回复集成 7 passed；真实 PostgreSQL Query + HTTP Service 分别验证一级评论 Cursor、线程回复和总数 |
| R2 | 一级评论和二级回复关系直观，能看出回复对象 | #473 / AC2 | satisfied | `ContentCommentSection.vue` 以根卡片和缩进回复展示；组件测试与 Playwright 断言“回复 用户乙”和“原作者” |
| R3 | 页面自然易读，参考截图层级但不增加头像等无关元素 | #473 / AC3 | satisfied | 本轮浏览器实拍已目视核对，无头像/社交操作；页面使用“平台显示 / 已采集 / 当前显示”自然语言 |
| R4 | 页面改动同步到指定 Figma 原型 | #473 / AC4 | satisfied | 在公共详情 Body `4861:31020` 新增评论区 `5356:2`、根评论 `5356:33065`、缩进回复 `5357:2`、分页节点 `5357:33077`/`5357:33079`；在 `4627:10058` 新增状态说明 `5357:33089`；状态 `SYNCHRONIZED_PENDING_HUMAN_REVIEW` |
| R5 | 不新增专用重试 API/按钮，评论读取系统性适用于五平台已入库数据 | #473 / AC5 | satisfied | 新 API 只按 Content/Comment PostgreSQL 通用表读取，不按 Provider 分支；沿用已有辅助补采入口与持久 Collection Runtime；五平台本地响应 Mapper/分页 10 passed；未新增补采重试 Contract/UI |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 评论线程组装、直接父级降级、Vue 展示与交互 |
| 接口 / 契约 | required | Pydantic/OpenAPI/生成 TypeScript Client 与分页语义 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 层级查询、稳定分页、计数 |
| 用户 / 工作流验收 | required | 声音广场打开详情、看评论、继续加载、空/错状态 |
| 跨组件关键路径 | required | 已入库评论经 API/Store 到详情抽屉的组装链路 |
| 外部依赖 / 供应方探测 | not_applicable | 本变更读取既有已入库评论，不改变 TikHub 请求/Mapper；此前真实 Provider 结构证据继续作为输入事实 |
| 构建 / 打包 / 运行 | required | 后端目标测试、前端 test/typecheck/build |
| 文档 / 治理 / 其他 | required | Roadmap、Change、Figma 同步与人工评审状态 |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 分页切断线程、错误归因直接父评论、海量回复造成响应过大 | 以根评论为分页单位；未知直接父级降级；实测与边界测试约束单页规模 |
| 兼容性 | 保持既有详情 Contract 和合法页面路径 | 新增资源/字段而非删除；前端统一走生成 Client |
| 数据 / Migration | 不适用 | 复用既有列，不改 Schema、不回填 |
| 部署 / 运行 | 前后端需同版本发布 | 新页面依赖新增只读 API；无额外服务/配置 |
| 回滚 / 恢复 | 代码回滚即可 | 无不可逆数据写入或 Migration |

# 文档、依赖、部署与发布影响

- **长期文档**：定向同步评论产品化方案中的实际 Contract、页面入口与状态。
- **依赖 / Runtime**：不新增或升级依赖。
- **配置 / Secret**：不变，不记录或输出 TikHub Secret。
- **部署 / Release**：无 Migration；需要前后端同版本发布，但本轮不部署。
- **兼容 / 消费方通知**：新增生成 Client 方法；旧内容详情调用保持可用。

# 完成审计

- [x] upstream_re_read：完成前重新读取用户要求、Roadmap 4.5、Contract、辅助补采 Runtime、页面与 Figma 目标节点；本地 `origin/main`/HEAD 均为 `a000855cef3d0d3ffa7747a901a4e014ad1e3bf8`。
- [x] change_coverage：逐条核对 R1—R5；本轮完成的是“已正确入库评论的正式查看链路”，不把路线中尚未落地的全部 Provider 身份解析写成已完成。
- [x] reverse_audit：“正式辅助补采 → Collection Scope 评论/回复 Runtime → Canonical Mapper/Ingestion → PostgreSQL comments → Content HTTP → 生成 Client → Store → 详情评论区”接线存在；反向从每个页面加载动作追到新增只读 Contract 和 PostgreSQL 查询，无 staging/JSONL 读取。
- [x] unresolved_cleared：R1—R5 已有实现与新鲜证据；Figma 已同步并按要求保留人工视觉评审状态，最终复截图因连接随后失去文件编辑权限而列为未验证项，不伪装已复核。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 本地工作树 / Python 3.14 | `pytest tests/api/test_stage8d_contents.py tests/contracts/test_openapi.py tests/unit/content/test_content_cursor.py -q` | 16 passed | 路由、Contract 与 Cursor 既有回归 |
| V2 | 隔离 PostgreSQL 18.4 | 评论 Query + 正式 HTTP Service 定向集成测试 | 1 passed | 一级/回复稳定分页、直接父作者与计数读取真实 PostgreSQL |
| V3 | 隔离 PostgreSQL 18.4 | 正式辅助补采评论、回复、资格集成测试 | 7 passed | 现有网页补采后端链路经 Collection Runtime 写入评论/回复 |
| V3a | 五平台脱敏本地响应 | TikHub 评论 Mapper 与分页 Runtime 定向测试 | 10 passed | 五平台统一进入 Canonical 评论语义；不代表真实 Provider 当前在线 |
| V4 | Frontend / Vitest | 评论组件、声音广场 Store、补采状态测试 | 3 files / 29 passed | 页面层级、降级文案、分页请求与状态 |
| V5 | Chromium / Playwright | `voice-plaza.spec.ts` | 11 passed；截图场景另跑 1 passed | 详情直接展示、展开回复、“回复谁”、原作者及实际布局 |
| V6 | Frontend build | `npm run lint`、`npm run build` | exit 0 | 零 Lint 告警；TypeScript/Vue 类型检查及 Vite 生产构建通过 |
| V7 | Contract / Python static | compatibility checker、Ruff、Mypy | exit 0 | OpenAPI 兼容检查与变更代码静态检查通过 |
| V8 | Figma | 既有 Body/Dev Spec 节点增量写入 | `SYNCHRONIZED_PENDING_HUMAN_REVIEW` | 原型具有根评论、缩进回复、分页与状态说明；等待用户人工视觉确认 |

## 未验证内容与剩余风险

- 当前 Compose 业务数据库的只读检查结果为 4 条 Content、0 条 Comment，因此不能声称用户现有业务库已经有可在页面展示的评论；本轮以隔离 PostgreSQL 的生产 Mapper/Ingestion/Query/HTTP Service 链路证明结构和读取行为。
- Playwright 使用可控 HTTP Mock 验证浏览器交互，不等同于真实 TikHub 在线调用；本变更没有调用付费 Provider，也不证明路线中微博 `ttarticle` 等身份解析已全部完成。
- Figma 节点写入完成后，连接开始返回该文件无编辑权限，故最后一次布局修正后的 Figma 截图未能重新获取；状态保持 `SYNCHRONIZED_PENDING_HUMAN_REVIEW`，不写成视觉终验完成。

## 交付状态

- 需求来源：GitHub Issue #473 已创建，待合并后依据新鲜主分支证据关闭。
- 提交：用户已授权合并，待创建。
- 拉取请求：用户已授权合并，待创建。
- CI：未触发远程 CI；本地完成目标测试、真实 PostgreSQL 集成、浏览器测试、静态检查与生产构建。
- 合并：用户已授权，待 Required Checks 与 Review 门禁通过后执行。
- Change 归档：未归档，当前为 Active。
- 发布 / 部署：不在本次授权范围，未执行。
