---
schema: coding-change/v1
id: CHG-20260920-175016-voice-plaza-read-model
title: 声音广场增量读模型与交互性能整改
level: L3
status: in_progress
owner: codex
branch: perf/voice-plaza-read-model
created: 2026-09-20
updated: 2026-09-20
completion_gate: required
depends_on: []
affected_areas: [content, analysis, vehicles, jobs, api, frontend, database, docs]
affected_paths: [backend/src/aima_ugc, frontend/src, migrations/versions, tests, docs]
contracts: [ContentFilterOptionsResponse, ContentListResponse, ContentDetailResponse, ContentCommentListResponse, content.voice-plaza-projection-backfill.v1]
data_changes: [voice_plaza_content_projection, voice_plaza_projection_state]
---

# 变更摘要

- **要解决的问题**：约 182 万条数据的生产日志中，声音广场列表约 9–10 秒、筛选目录约 34 秒、详情和评论约 11.5 秒；现有查询会在请求内重建全量 Analysis/Review 投影并重复计算来源和评论统计。
- **拟议修改**：建立由 PostgreSQL 维护的一行一内容增量读模型，既有数据由持久 Job 分块回填；列表和筛选切到小投影，详情复用列表摘要，评论改为集合统计，并增加安全阶段耗时日志。PostgreSQL 仍是唯一业务事实库。
- **预期结果**：首屏、平台筛选、加载更多、详情和评论不再把全量事实表计算放在用户请求主链；真实 182 万数据耗时在合并后的服务器环境用新增日志验收。

# 背景、现状与问题

## 背景

Issue #551 承载本次正式验收项。用户已明确要求按系统方案修改、同步文档并合并主分支，同时明确本地不要求完成真实 182 万量级查询计划/性能验证，由服务器部署后提供日志继续验收。

## 当前现状

- `GET /api/v1/contents` 会构造全局 `row_number()` Analysis、Analysis Run 与 Relevance Review 子查询，再补查标签、Brand、Vehicle 和可用性。
- `GET /api/v1/content-filter-options` 会扫描当前可见内容和动态分析值，最新日志约 34 秒并导致前端显示“筛选项暂不可用”。
- 详情复用同一重型基础投影；评论分页为每一行执行相关回复计数，随后再执行两个总数查询。
- 前端首屏已经先请求第一页，但详情抽屉仍等待详情接口才获得主体数据。

## 问题、根因或约束

根因不是单一索引缺失，而是请求成本仍随全库 Analysis/Review/来源链增长：排序分页之前先构造全量当前态，筛选目录每次重扫大表，详情重复执行列表重投影，评论把聚合放进逐行相关子查询。仅继续增加普通索引不能稳定切断这些增长路径。

## 不修改的后果

数据继续增长时，列表、筛选目录和详情请求仍会随着全表投影成本增加；用户即使只看 20 条内容，也要等待与全库规模相关的工作，超时后筛选能力被误报为不可用。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 最新日志中列表约 9–10 秒、筛选目录约 34 秒、详情和评论约 11.5 秒 | `E:/Desktop/logs/logs/api.log` | 必须切断全库请求时计算，不能只调前端加载顺序 |
| E2 | 列表基础查询包含三个全局窗口投影和四路来源可见性谓词 | `backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py`、`content_visibility.py` | 列表需要读取已维护的当前态投影 |
| E3 | 筛选目录每次扫描当前可见 Content、Analysis 与标签 | `PostgresContentQueryRepository.list_filter_values` | 筛选目录需要持久小投影 |
| E4 | 评论列表逐行相关统计回复数并另做两个 count | `PostgresContentQueryRepository._comment_statement`、`count_comments` | 回复数与总数需要集合聚合 |
| E5 | 当前首屏已经先获取最新第一页，辅助资源在后台加载 | `frontend/src/features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue` | 保留首屏调度，继续优化数据路径 |

## 推断与待确认

- **待确认**：真实 182 万数据下的最终 P50/P95 和查询计划只能在服务器部署后的实际 PostgreSQL 环境确认；这不阻塞实现和本地正确性门禁，但不得在合并时声称真实大库性能已验证。

# 目标、成功标准与非目标

## 目标

把声音广场高频读取从“每次请求重建全库当前态”改为“写入时维护、一次回填、请求按索引读小投影”，同时让首屏和详情优先呈现用户已经需要的数据。

## 成功标准

- [ ] Issue #551 AC1–AC8 全部有实现和当前证据，或有用户明确延期依据。
- [ ] 列表、筛选、详情和评论主链不再执行已识别的全量窗口/逐行聚合形态。
- [ ] 合并后服务器可从安全日志直接获得各阶段耗时和读模型状态。

## 范围

- PostgreSQL 读模型、迁移、自动增量刷新与持久分块回填 Job。
- 列表、筛选目录、详情和评论后端查询路径。
- 声音广场列表/详情的缓存、摘要先显、预取与迟到请求保护。
- Contract、generated client、测试、架构和运维文档。

## 非目标

- 本地构造或复制 182 万条生产规模数据做性能基准。
- 引入 Redis、Kafka、OpenSearch、第二套数据库或第二套任务系统。
- 改变声音广场的业务筛选定义、来源撤销语义或新增认证能力。

## 必须保持不变

- 默认无筛选时最新数据倒序、Cursor 稳定分页、默认排除业务有效不相关内容。
- 现有公共筛选、详情、评论和人工复核行为兼容；新增响应字段必须向后兼容。
- PostgreSQL 是唯一业务事实库，回填复用当前持久 Job Runtime。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Content Owner 维护声音广场派生投影，事实表 Owner 不变 | E2–E4、项目模块边界 | 不创建第二个业务写 Owner |
| 接口与契约 | 保持现有列表/详情结构，筛选目录只增加回填状态 | #551 / AC3、AC6 | 生成 OpenAPI Client 并验证兼容 |
| 数据与迁移 | Migration 只建表、函数、触发器和初始 pending 状态；历史数据由 Job 分块回填 | #551 / AC5 | 避免 182 万数据在 Alembic 单事务回填 |
| 错误与失败语义 | 回填未完成时列表保留兼容查询；筛选目录返回 active Taxonomy + 已投影目录并标识 building | #551 / AC3、AC5 | 不把回填过程误报为筛选不可用 |
| 兼容性 | Cursor、筛选和来源可见性语义保持 | #551 / AC6 | 查询路径改变而业务结果不变 |
| 部署与回滚 | Worker 自动认领一次性回填；读模型 ready 后切换；回滚先退应用再降迁移 | #551 / AC5、AC8 | 部署期间允许兼容慢路径但不能返回错误结果 |

# 修改方案与决策依据

## 最小充分方案

1. **建增量读模型与回填状态**
   → 修改 `modules/content` 表定义、Alembic Migration、数据库注册
   → 新内容及 Analysis、人工纠正、Brand/Vehicle 变化同步刷新；旧内容保持 pending
   → Schema/触发器集成测试、Migration upgrade/downgrade 检查。

2. **持久 Job 分块回填**
   → 新增 `content.voice-plaza-projection-backfill.v1`、Worker 装配与启动幂等入队
   → 按 UUID 游标分块提交，可中断续跑，完成后原子标记 ready
   → Handler 单元测试与 PostgreSQL 续跑/幂等集成测试。

3. **切换高频查询**
   → 列表/筛选从 ready 投影读取，详情只对一个 Content 做补充；评论用集合聚合
   → 默认最新、平台筛选、下一页成本与返回页大小相关，不包含全局窗口投影
   → SQL 形态回归、Contract、PostgreSQL 行为测试。

4. **改善前端感知速度**
   → 详情先复用列表摘要，详情附加项和评论独立加载；对查询页做短时缓存和下一页预取
   → 返回页面保留已应用筛选，切换平台不显示上一请求迟到结果
   → Browser Mock 用户路径与前端构建。

5. **补可观测性与文档**
   → API 输出安全的阶段耗时、projection 状态、页大小与筛选维度；同步产品、架构、运维说明
   → 服务器日志能区分列表选页、hydrate、筛选目录、详情和评论阶段
   → 日志单测、文档链接/路径检查。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：持久增量投影 | E1–E3 | 只有把当前态计算移出请求主链，成本才不随全库事实表线性增长 |
| D2：Job 回填而非 Migration 回填 | 182 万条现状、#551 / AC5 | 可分块提交、续跑和观测，避免长 Migration 事务 |
| D3：评论集合聚合 | E4 | 一次聚合替代每行子查询，页大小增长时不会形成 N 次相关统计 |
| D4：摘要先显与独立加载 | E5、#551 / AC4 | 用户已有列表数据，无需等待重型详情才能看到主体 |

## 备选方案与取舍

- **只加索引**：已执行过一次且提升有限；不能消除全局窗口和每次筛选目录重建，拒绝。
- **仅内存缓存**：多进程不一致、重启丢失且首个请求仍慢，不能作为根因方案。
- **Redis/OpenSearch**：当前需求不需要新基础设施，且会引入第二套一致性、部署和恢复边界，拒绝。
- **Alembic 单事务全量回填**：182 万条下锁持有和回滚成本不可接受，拒绝。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 首次自动加载最新倒序第一页，返回保留已应用筛选 | #551 / AC1 | not_satisfied | 待实现与验证 |
| R2 | 列表、平台筛选和加载更多只走增量投影，不再全量窗口 | #551 / AC2 | not_satisfied | 待实现与验证 |
| R3 | 筛选目录从小投影读取，回填期间仍可用 | #551 / AC3 | not_satisfied | 待实现与验证 |
| R4 | 详情摘要先显、详情与评论独立、评论无逐行计数 | #551 / AC4 | not_satisfied | 待实现与验证 |
| R5 | 持久 Job 分块回填且各类增量变化刷新投影 | #551 / AC5 | not_satisfied | 待实现与验证 |
| R6 | 保持既有业务语义且不引入新基础设施 | #551 / AC6 | not_satisfied | 待实现与验证 |
| R7 | 增加安全阶段耗时与投影状态日志 | #551 / AC7 | not_satisfied | 待实现与验证 |
| R8 | 完成本地正确性门禁；真实大库性能由合并后服务器日志验收 | #551 / AC8 | not_satisfied | 用户明确验收边界；待完成本地门禁 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `backend/src/aima_ugc/modules/content/` | 定义读模型、状态与 Job Contract | 建立唯一派生模型和回填语义 | R2、R3、R5 |
| `backend/src/aima_ugc/adapters/persistence/postgres/` | 投影查询、回填和高频读取 | 切断全量窗口与逐行聚合 | R2–R5、R7 |
| `backend/src/aima_ugc/bootstrap/`、`entrypoints/` | Worker 装配、幂等入队、HTTP timing | 自动回填与排障 | R5、R7 |
| `migrations/versions/` | Schema/函数/触发器/索引 | 支持增量维护与索引读取 | R2、R3、R5 |
| `frontend/src/features/voice-plaza/` | 摘要先显、缓存、预取、状态文案 | 改善用户感知速度 | R1、R3、R4 |
| `tests/`、`frontend/src/**/*.test.ts` | Contract、SQL 形态、集成、用户路径回归 | 防止再次退回慢查询形态 | R1–R8 |
| `docs/`、模块 README | 架构、部署回填、验收与限制 | 让服务器操作和日志验收可执行 | R5、R7、R8 |

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [ ] 行为变化建立失败证据
- [ ] 完成最小实现，不静默扩大范围
- [ ] 同步受影响的长期文档
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 投影状态/Job 续跑、SQL 形态、前端 Store 摘要与缓存行为 |
| 接口 / 契约 | required | Pydantic/OpenAPI/generated client 漂移和兼容 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 触发器、回填、查询结果、Migration |
| 用户 / 工作流验收 | required | 首屏、平台切换、返回筛选、详情摘要、评论独立失败、加载更多 |
| 跨组件关键路径 | required | API + PostgreSQL + generated client 的关键列表/详情路径 |
| 外部依赖 / 供应方探测 | not_applicable | 本次不修改 TikHub 或其它外部 Provider Contract，也不需要付费 Probe |
| 构建 / 打包 / 运行 | required | Python 检查、前端 typecheck/test/build、应用 Schema/Migration 导入 |
| 文档 / 治理 / 其他 | required | Change Ready、文档链接、PR/CI、合并后主分支新鲜验证 |

## 验证计划

- 目标测试：投影表/SQL 形态、回填 Job、Filter Options、评论聚合、Store 缓存与详情摘要。
- 相关回归：现有 Content API/Contract、品牌车型、撤销可见性、声音广场 Browser Mock。
- 静态检查或构建：Ruff/Mypy（项目正式入口）、OpenAPI Client drift、前端 typecheck/test/build。
- 专项真实边界：本地可用的 PostgreSQL Integration；不把小数据结果冒充 182 万性能结论。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 投影刷新遗漏导致列表与事实表不一致 | 覆盖 Content/Analysis/Review/Manual/Brand/Vehicle 写入触发器，回填和增量一致性测试 |
| 兼容性 | 保持现有列表、筛选、详情、评论和 Cursor 语义 | Contract 回归和新旧结果对照 |
| 数据 / Migration | 新增派生表与状态；不改变业务事实表 | Migration 只建结构，Job 分块回填，可重建投影 |
| 部署 / 运行 | Migration 后 Worker 自动回填；ready 前列表使用兼容路径 | 日志输出状态和进度，运维文档给出检查方法 |
| 回滚 / 恢复 | 先回滚应用到旧查询，再执行 downgrade；投影可丢弃重建 | 派生投影不是业务事实，不需要回写业务表 |

# 文档、依赖、部署与发布影响

- **长期文档**：targeted 更新产品行为、后端/前端架构、数据库投影和部署/回填验收说明。
- **依赖 / Runtime**：不新增依赖、不升级 Python/Node/PostgreSQL 或锁文件。
- **配置 / Secret**：不新增 Secret；回填复用现有 Worker 与数据库配置。
- **部署 / Release**：需先运行 Migration，再启动 Worker 自动回填；ready 前保留兼容读取；不执行生产部署或生产 Migration。
- **兼容 / 消费方通知**：generated client 同步；现有消费者字段保留，筛选目录新增状态字段。

# 完成审计

- [ ] upstream_re_read：已重新读取 Issue #551、用户最新验收边界和正式项目文档，并独立重建完成定义。
- [ ] change_coverage：已确认当前变更覆盖 AC1–AC8，没有把 Change 自身当作需求全集。
- [ ] reverse_audit：已执行前端入口→API→投影→事实表、写入→触发器→投影→查询、Migration→Worker→ready 的反向审计。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；真实大库性能未验证按用户明确边界记录为 post-merge 服务器验收，不伪装成本地完成。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | 待实现 HEAD | 待执行 | 待执行 | 待补 |

## 未验证内容与剩余风险

- 真实 182 万数据的查询计划、P50/P95 和用户感知耗时不在本地验证；合并后由用户在服务器执行，随后基于安全阶段日志继续分析。

## 交付状态

- 提交：尚未创建。
- 拉取请求：尚未创建。
- CI：尚未运行。
- 合并：尚未执行。
- Change 归档：尚未执行。
- 发布 / 部署：不在本次授权范围；仅合并主分支，不执行服务器部署或生产 Migration。

## 备注

Issue #551 的真实大库性能验收已按用户最新决定调整到合并后服务器环境；本地仍必须证明查询路径已切换、业务语义正确且可回滚。
