---
schema: rvc-change/v1
id: "CHG-20260814-stage6-xhs-vertical-slice"
title: "Stage 6 小红书 TikHub App V2 端到端纵切"
level: L3
status: active
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
---

# 背景与现状

Stage 1–5D 已在 main 建立 Provider-neutral Job、Collection Run/Scope、Provider Request/Attempt、不可变 Raw Artifact、Dispatch/Fencing 与恢复链。当前没有具体平台 Operation、Mapper、Candidate/Ingestion 或 Content/Comment 业务表。

用户于 2026-08-14 批准 Stage 6 首个平台采用“小红书 + TikHub App V2”。能力基线为：`search_notes`、`get_image_note_detail`、`get_video_note_detail`、`get_note_comments`、`get_note_sub_comments`。真实付费 Provider Probe 不在本 Change 执行。

# 目标

以小红书 TikHub App V2 完成首个平台端到端纵切：Operation/分页 → Raw 来源项 → Mapper → Canonical → Candidate/Ingestion → Current/Version/Metric PostgreSQL，并通过 Fake/Fixture 从正式 Job/Collection 边界验证可回放、可追溯、可幂等。

# 范围

- 建立 TikHub 小红书 App V2 Operation：搜索、图文/视频详情、一级/二级评论的请求构造和分页状态解析；不在 Operation 中访问数据库。
- 建立纯 Mapper：只从已确认 Raw/采集上下文映射 `CanonicalContentV1` / `CanonicalCommentV1`，不发 HTTP、不写数据库、不猜发布时间或评论父子关系。
- 以用户提供的 2026-08-05 TikHub App V2 `search_notes` 成功响应作为真实结构来源，提交最小脱敏 Fixture；去除 cache 签名、xsec_token、真实账号/昵称/正文/CDN URL 等可识别值。
- 新建 Content Owner 模块及 Stage 6 业务表：Candidate/Ingestion、Account、Content/Version/Metric、Comment/Version/Metric；保持关系化 Current + History。
- 建立 `ContentIngestionService` + PostgreSQL Repository，依据 `observed_fields` 稀疏更新；业务 A→B→A 生成三个版本；指标首次、变化、每日检查点留痕且允许下降。
- Candidate 必须能沿 `Attempt → Request → Scope → Run` 与 Raw Artifact 追溯；来源项位置使用稳定 locator，不用数组下标作为唯一身份。
- 增加 Stage 6 独立 CI，并验证第六条 Alembic Revision 的 `base → head` 与 `20260814_0005 → head`。
- 同步受影响 Blueprint、Collection/Content README 和事实导航。

# 非目标

- 不实现其余四个平台。
- 不实现关键词/词包、Plan/Occurrence/Scheduler；这些属于 Stage 7。
- 不建立最终 `provider_budget_accounts/provider_budget_reservations`；真实付费 Provider 仍不可达。
- 不调用 TikHub 真实付费端点，不创建或提交 API Key/Cookie/Token。
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

- [ ] 真实脱敏 `search_notes` Fixture 可被正式 XHS Mapper 转成合法 `CanonicalContentV1`，且无真实 Token/签名/账号/正文/CDN URL 泄漏。
- [ ] 搜索分页保存并推进 `page/search_id/search_session_id`；评论分页保存并推进 `cursor/index/pageArea`；空页、重复页和状态不推进可确定停止。
- [ ] 图文/视频详情和一级/二级评论 Operation 使用批准的 App V2 endpoint，参数由 Operation 唯一定义。
- [ ] Comment Mapper 只在来源明确时设置 `root_comment_id/parent_comment_id`；sub-comments 调用上下文只可确定 thread root，不能猜 direct parent。
- [ ] Candidate/Ingestion 账本与 Content/Comment Current+Version+Metric 表由第六条 Revision 建立，并有约束保护来源链/身份。
- [ ] Ingestion 只更新 `observed_fields`；同一内容 A→B→A 产生三个业务版本；指标下降被记录；同一业务日最多一个无变化检查点。
- [ ] 失败 Mapper/Ingestion 可从已存 Raw 重放，不产生第二次 Provider 调用；Fake Provider 端到端 Job 边界通过。
- [ ] Stage 6 Unit/Contract/Integration、Migration 双升级路径、Ruff、mypy、架构/Table Owner/Secret/docs/Contract 门禁全绿。
- [ ] PR 合并后 main 相关 CI 重新成功，Change 才允许 done/archive。

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
→ 修改范围：Content/Collection Table、`database_schema.py`、第六条 Alembic Revision。
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

# 数据、部署与回滚

第六条 Revision 只新增 Stage 6 表/约束，不改写 0001–0005。合并本 Change 不启用真实付费采集；生产无自动外部调用。回滚前停止相关 Worker 并备份，降级至 `20260814_0005` 删除 Stage 6 新业务表；因此已写入 Stage 6 业务数据会丢失，生产正式启用前必须以迁移/备份策略另行验收。

# 风险

- 当前仅有真实 `search_notes` 响应 Fixture；详情/评论使用确定性 Fake/结构测试，不能宣称已通过真实 TikHub 详情/评论兼容验收。
- TikHub 属第三方 Provider；端点变化通过 Operation/Fixture 隔离，不向 Canonical/业务表泄漏 Provider 私有字段。
- 用户本地工作区不可见，本 Change 仅能证明 GitHub 远端分支与 Actions 状态。
