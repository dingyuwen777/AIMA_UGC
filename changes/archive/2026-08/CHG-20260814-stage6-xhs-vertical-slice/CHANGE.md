---
schema: rvc-change/v1
id: "CHG-20260814-stage6-xhs-vertical-slice"
title: "Stage 6 小红书 TikHub App V2 端到端纵切"
level: L3
status: done
owner: "dingyuwen777"
branch: "feature/stage6-xhs-vertical-slice"
created: 2026-08-14
updated: 2026-08-14
depends_on:
  - "CHG-20260814-stage5d-provider-dispatch-recovery"
affected_areas:
  - "collection"
  - "provider"
  - "content"
  - "database"
  - "migration"
  - "testing"
  - "ci"
  - "blueprint"
affected_paths:
  - "backend/src/aima_ugc/adapters/providers/tikhub/"
  - "backend/src/aima_ugc/modules/collection/"
  - "backend/src/aima_ugc/modules/content/"
  - "backend/src/aima_ugc/adapters/persistence/postgres/"
  - "backend/src/aima_ugc/database_schema.py"
  - "migrations/versions/"
  - "tests/fixtures/providers/tikhub/xhs/"
  - "tests/unit/collection/"
  - "tests/unit/content/"
  - "tests/integration/content/"
  - "docs/blueprint/"
  - ".github/workflows/"
  - "scripts/quality/check_architecture.py"
contracts:
  - "CanonicalContentV1"
  - "CanonicalCommentV1"
  - "CanonicalSourceV1"
data_changes:
  - "collection_candidates"
  - "collection_candidate_ingestions"
  - "accounts"
  - "contents"
  - "content_versions"
  - "content_metric_observations"
  - "comments"
  - "comment_versions"
  - "comment_metric_observations"
  - "comment_coverage_observations"
  - "account_external_ids"
---

# 背景与现状

Stage 1–5D 已在 main 建立 Provider-neutral Job、Collection Run/Scope、Provider Request/Attempt、不可变 Raw Artifact、Dispatch/Fencing 与恢复链。本分支已建立首个小红书 TikHub App V2 Operation/Mapper、Candidate/Ingestion 与 Content/Comment 业务事实，但正式验收前发现 Candidate/Ingestion 尚未由数据库完整保护“只追加”和“成功结果必须关联目标”语义，因此本 Change 继续补齐约束、迁移、测试和文档。

用户于 2026-08-14 批准 Stage 6 首个平台采用“小红书 + TikHub App V2”。能力基线为：`search_notes`、`get_image_note_detail`、`get_video_note_detail`、`get_note_comments`、`get_note_sub_comments`。用户另行明确授权使用其凭据，以关键词“爱玛”执行最小真实兼容性测试；该授权只用于本轮受控 Probe，不表示允许把 Secret、真实响应或真实付费调用接入代码、CI 或生产链路。

# 目标

以小红书 TikHub App V2 完成首个平台端到端纵切：Operation/分页 → Raw 来源项 → Mapper → Canonical → Candidate/Ingestion → Current/Version/Metric PostgreSQL，并通过 Fake/Fixture 从正式 Job/Collection 边界验证可回放、可追溯、可幂等。

# 范围

- 建立 TikHub 小红书 App V2 Operation：搜索、图文/视频详情、一级/二级评论的请求构造和分页状态解析；不在 Operation 中访问数据库。
- 建立纯 Mapper：只从已确认 Raw/采集上下文映射 `CanonicalContentV1` / `CanonicalCommentV1`，不发 HTTP、不写数据库、不猜发布时间或评论父子关系。
- 以用户提供的 2026-08-05 TikHub App V2 `search_notes` 成功响应作为真实结构来源，提交最小脱敏 Fixture；去除 cache 签名、xsec_token、真实账号/昵称/正文/CDN URL 等可识别值。
- 新建 Content Owner 模块及 Stage 6 业务表：Candidate/Ingestion、Account、Content/Version/Metric、Comment/Version/Metric；保持关系化 Current + History。
- 建立 `ContentIngestionService` + PostgreSQL Repository，依据 `observed_fields` 稀疏更新；业务 A→B→A 生成三个版本；指标首次、变化、每日检查点留痕且允许下降。
- Candidate 必须能沿 `Attempt → Request → Scope → Run` 与 Raw Artifact 追溯；来源项位置使用稳定 locator，不用数组下标作为唯一身份。
- 增加 Stage 6 独立 CI，并验证 `base → head`、`20260814_0005 → head`、首条 Stage 6 Revision 和上一条 Stage 6 Revision 到 `head`。
- 同步受影响 Blueprint、Collection/Content README 和事实导航。

# 非目标

- 不实现其余四个平台。
- 不实现关键词/词包、Plan/Occurrence/Scheduler；这些属于 Stage 7。
- 不建立最终 `provider_budget_accounts/provider_budget_reservations`；真实付费 Provider 仍不可达。
- 不在生产调用链或普通 CI 中调用 TikHub 真实付费端点，不创建或提交 API Key/Cookie/Token；本轮只执行用户已授权的最小只读 Probe。
- 不实现公开 HTTP API、前端页面、认证授权、AI/Monitoring/Reporting。
- 不升级或新增依赖，不改 Canonical V1 已冻结身份/字段语义，不为未来假设创建兼容层。

# 必须保持不变

- Provider 不写业务表；Mapper 不访问数据库、不发 HTTP；Router 不写 SQL；一个表只有一个写 Owner。
- 外部 ID 使用字符串，数据库时间使用 `timestamptz`，Canonical/API 时间带时区。
- Stage 5D 的一次发送、Job Fencing、Raw 不可变、Artifact `pending/stored/linked` 与恢复语义不改变。
- `ProviderRequestV1/ProviderAttemptV1/RawEnvelopeV1` 不改；Canonical Pydantic 仍是唯一手写 Contract 事实源。
- Secret 不进入代码、日志、Raw Fixture、Job Payload 或数据库明文。
- 已校验 Raw 可重放时不得再次调用 Provider。

# 成功标准

- [x] 真实脱敏 `search_notes` Fixture 可被正式 XHS Mapper 转成合法 `CanonicalContentV1`，且无真实 Token/签名/账号/正文/CDN URL 泄漏。
- [x] 搜索分页保存并推进 `page/search_id/search_session_id`；评论分页保存并推进 `cursor/index/pageArea`；空页、重复页和状态不推进可确定停止。
- [x] 图文/视频详情和一级/二级评论 Operation 使用批准的 App V2 endpoint，参数由 Operation 唯一定义。
- [x] Comment Mapper 只在来源明确时设置 `root_comment_id/parent_comment_id`；sub-comments 调用上下文只可确定 thread root，不能猜 direct parent。
- [x] Candidate/Ingestion 账本与 Content/Comment Current+Version+Metric 表由 Stage 6 Revision 建立，并有约束保护来源链、身份、只追加和成功结果完整性。
- [x] Ingestion 只更新 `observed_fields`；同一内容 A→B→A 产生三个业务版本；指标下降被记录；同一业务日最多一个无变化检查点。
- [x] 失败 Mapper/Ingestion 可从已存 Raw 重放，不产生第二次 Provider 调用；Fake Provider 端到端 Job 边界通过。
- [x] Stage 6 Unit/Contract/Integration、Migration 多升级路径、Ruff、mypy、架构/Table Owner/Secret/docs/Contract 门禁全绿。
- [x] PR 合并后 main 相关 CI 重新成功，Change 才允许 done/archive。

# 方案比较与关键决策

1. **方案 A（采用）**：保留已经执行过的 `0006`—`0008`，以增量 `0009` 同时增加数据库只追加 Trigger、成功结果 Check 和服务层关闭失败校验。优点是兼容已执行 Revision、约束覆盖直接 SQL 和生产入口，回滚边界明确；代价是多一条 Migration。
2. 方案 B：直接改写 `0006` 并把账本约束塞回首条 Stage 6 Revision。文件更少，但 `0006` 已被 CI 和分支历史执行，改写会破坏 Migration 可追溯性和已部署兼容，故拒绝。
3. 方案 C：只在 `CandidateIngestionService` 校验，不增加数据库约束。实现最小，但无法阻止直接 SQL UPDATE/DELETE 或写入无目标成功结果，不满足 Blueprint 的不可变账本机器事实，故拒绝。

用户已批准继续完成 Stage 6；实现按现有模块化单体、Owner Repository 和增量 Migration 路线执行，没有更换 Contract、目录、运行时或依赖。

# 实施步骤

[步骤 1：Red]
→ 修改范围：Stage 6 Change、专项 CI、XHS Operation/Mapper 单元测试、Content Ingestion 集成测试骨架。
→ 预期结果：测试准确因生产入口/表/行为不存在而失败。
→ 验证方式：Stage 6 GitHub Actions 读取 pytest 失败原因与退出状态。

[步骤 2：Provider Operation 与 Mapper]
→ 修改范围：`adapters/providers/tikhub/operations/xiaohongshu.py`、`mappers/xiaohongshu.py`、脱敏 Fixture。
→ 预期结果：请求/分页由 Operation 唯一定义；Mapper 纯函数输出 Canonical。
→ 验证方式：Unit + Contract Schema + Secret 扫描。

[步骤 3：Content/Candidate 机器事实]
→ 修改范围：Content/Collection Table、`database_schema.py`、Stage 6 Alembic Revision 链。
→ 预期结果：最终来源链、Current/Version/Metric 关系表和约束存在。
→ 验证方式：PostgreSQL introspection、`base→head`、`0005→head`、downgrade/re-upgrade、`alembic check`。

[步骤 4：Ingestion]
→ 修改范围：Content Service、PostgreSQL Repository、Candidate Repository。
→ 预期结果：稀疏合并、A→B→A、指标变化/日检查点、失败结果/重放正确。
→ 验证方式：真实 PostgreSQL Integration。

[步骤 5：Job/Fake 纵切与文档]
→ 修改范围：最小 Collection Job Handler/组装、Fake Fixture、README/Blueprint、CI。
→ 预期结果：不产生真实费用即可从正式 Job/Collection 边界完成 Raw→Canonical→Ingestion，且失败可回放。
→ 验证方式：端到端 Fake Provider、全量相关回归和两阶段 Review。

# 测试计划

- Red/Unit：XHS Operation 请求构造、搜索分页、评论分页、Mapper、评论关系真实性。
- Contract：脱敏真实 Fixture → Mapper → Canonical Pydantic/JSON Schema。
- Integration：Candidate 来源约束、Content/Comment Ingestion、A→B→A、指标下降、daily checkpoint、事务回滚和 Raw replay。
- Migration：`base → head → base → head` 与 `20260814_0005 → head → 0005 → head`。
- 回归：Stage 4/5A/5B/5C/5D Collection/Job/Provider/Raw tests。
- 质量：Ruff format/check、mypy、Contract generate/compatibility、architecture/table owner/secret/docs。

# 已执行的受控 Provider Probe

- 2026-08-14 按 TikHub 官方 Swagger 与 Xiaohongshu App V2 `search_notes` 文档复核 `.io` Base URL、Bearer 认证、endpoint 和参数；未据此升级依赖或改变 Provider 方案。
- 第一次最小请求未携带常规 `User-Agent`，在业务响应前得到 HTTP 403；该结果不作为接口兼容或计费成功证据。
- 随后以关键词“爱玛”执行两次只读 `search_notes`：一次使用 `time_descending + 一天内`，一次使用默认综合排序。两次均返回 HTTP 200，确认当前顶层响应包装、`data`、分页会话字段和空页结构；两次 `items=[]`，因此只能验证当前空页兼容，不能替代已脱敏非空 Fixture 对 Mapper 的验证。
- 未执行详情或评论 Probe，未写生产库，未保存真实 Raw，未把 API Key、请求头或真实响应写入源码、文档、日志、Fixture、数据库或 Git。

# Red/Green 证据

- Red：`uv run pytest tests/unit/collection/test_candidate_ingestion.py -q`，退出码 1，`ingested`/`duplicate` 两个无目标成功结果均因未抛出 `ValueError` 而失败。
- Green：加入服务层关闭失败校验后运行同一命令，退出码 0，`2 passed`。
- PostgreSQL 行为测试已新增，但本地现有 Python 3.14.7 uv 环境缺少可加载的 libpq/psycopg binary wrapper，无法在本地建立数据库 Red/Green 证据；不得把该环境错误表述为业务测试失败。最终数据库约束、Migration 和回归以 PostgreSQL 18.4 Stage 6 CI 为准。
- 本地 Stage 6 Unit/Contract：`41 passed`；目标账本测试复跑：`2 passed`；Ruff、mypy（92 个源文件）、Contract 生成/兼容、架构、Table Owner、Secret 和文档门禁均为退出码 0。
- 本地全量 Unit/Contract/API：`71 passed, 1 failed`；唯一失败是 Windows 当前进程没有创建目录符号链接权限（WinError 1314），不是 Stage 6 行为失败。该测试不删除、不跳过，最终由 Linux CI 重新覆盖。

# 数据、部署与回滚

`20260814_0006`—`20260814_0009` 只新增或补强 Stage 6 表、外键、Check 与 Trigger，不改写 0001–0005。`0009` 禁止 Candidate/Ingestion 账本 UPDATE/DELETE，并要求 `ingested/duplicate` 同时具备 Canonical 身份和业务目标。合并本 Change 不启用真实付费采集；生产无自动外部调用。回滚 `0009 → 0008` 会移除新增账本保护但保留数据；降级至 `20260814_0005` 会删除全部 Stage 6 业务表，因此回滚前必须停止相关 Worker 并备份，生产正式启用前仍需另行验收迁移/备份策略。

# 风险

- 当前仅有真实 `search_notes` 响应 Fixture；详情/评论使用确定性 Fake/结构测试，不能宣称已通过真实 TikHub 详情/评论兼容验收。
- TikHub 属第三方 Provider；端点变化通过 Operation/Fixture 隔离，不向 Canonical/业务表泄漏 Provider 私有字段。
- 当前真实 Probe 的两次成功响应均为空结果页，不能宣称已用当日实时非空数据验证字段映射；非空映射证据仍来自 2026-08-05 脱敏 Fixture。
- 本地 PostgreSQL 集成因 libpq wrapper 不可用而不能运行；该未验证项已由 PR 与合并后 main 的 GitHub Actions PostgreSQL 18.4 新鲜绿色证据覆盖。

# 最终验证证据

- 实现提交 `c9ff0043d95d7e8112899104855e87912c600417` 的 PR 工作流全部 completed/success：CI `31813222528`、Stage 4 `31813222545`、Stage 5A `31813222539`、Stage 5B `31813222553`、Stage 5C `31813222534`、Stage 5D `31813222581`、Stage 6 `31813222527`。
- Stage 6 PR run 的 Unit、Quality、PostgreSQL 三个 Job 全部成功；PostgreSQL 18.4 实际完成 Collection/Content Integration、`upgrade head`、`0005 → head`、`0006 → head`、`0008 → head`、`base → head` 往返和 `alembic check`。
- PR #27 最终 head 为 `c9ff0043d95d7e8112899104855e87912c600417`，非 Draft、mergeable、无 review thread/review/comment 阻塞，以 merge commit `c3fab0f2f46678bd576a70b80b221227bcaeb6aa` 合并到 `main`。
- 合并后 main push 工作流全部 completed/success：CI `31813934345`、Stage 4 `31813934277`、Stage 5A `31813934398`、Stage 5B `31813934281`、Stage 5C `31813934413`、Stage 5D `31813934369`、Stage 6 `31813934317`。
- 合并后本地 main 复验：Stage 6 Unit/Contract `41 passed`；Ruff format/check、mypy 92 个源文件、Architecture、Table Owner、Secret、Docs、Contract generate/compatibility 均退出码 0，工作区干净。
- 本地全量 Unit/Contract/API 的唯一失败仍是 Windows 当前进程缺少目录符号链接权限（WinError 1314）；测试未删除或跳过，Linux 通用 CI 已成功覆盖。

# 文档影响

- 根 README、Collection/Content README、Blueprint 导航/阶段/技术门禁、测试调试说明和 Fixture README 已同步 Stage 6 当前事实、真实 Probe 边界、Migration 和测试入口。
- 无公开 HTTP API、OpenAPI 字段或前端行为变化；固定 Contract 生成和兼容门禁证明生成物无漂移，因此 `docs/API接口说明.md` 与前端生成 Client 无需修改。

# 交付

- 基线 main：`5b18bbc2b73e55d3faa448abe4ae7dcdf8fc7130`。
- 实现分支：`feature/stage6-xhs-vertical-slice`；补强提交：`c9ff004`（`补强 Stage 6 Candidate 追加账本约束`）。
- 实现 PR：[PR #27](https://github.com/dingyuwen777/AIMA_UGC/pull/27)，merge commit `c3fab0f2f46678bd576a70b80b221227bcaeb6aa`。
- Change 收尾分支：`docs/archive-stage6-xhs-vertical-slice`。
- Change 状态：done，归档至 `changes/archive/2026-08/CHG-20260814-stage6-xhs-vertical-slice/`。
- 发布：本 Change 不启用真实 Provider Transport、付费预算、Scheduler、API 或前端，不执行生产部署。
