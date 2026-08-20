# Content 模块

`content` 是 Canonical Content/Comment 业务状态、版本历史、指标历史、评论 Coverage 和账号身份的唯一写 Owner。Collection 只能通过 Content Service/Repository 写入，Provider/Mapper 不得直接写这些业务表。

## 当前职责

- 维护 `accounts` / `account_external_ids`；
- 维护 `contents` / `content_versions` / `content_metric_observations`；
- 维护 `comments` / `comment_versions` / `comment_metric_observations`；
- 维护 `comment_coverage_observations`；
- 按 `platform + external_content_id`、`content_id + external_comment_id` 和账号平台身份做 PostgreSQL 幂等收敛；
- 保存 Canonical 的当前值与稀疏历史事实，不把未观察字段伪造成当前或历史值；
- 通过 `provider_attempt_id + raw_artifact_id` 保持来源链。

Stage 8D 新增 Provider-neutral 只读边界：

```text
PostgreSQL Content Current / Version / Metric / Comment / Coverage / Source
→ PostgresContentQueryRepository
→ Content HTTP Service
→ Pydantic / OpenAPI / Orval
→ Vue 声音广场
```

查询支持标题、正文、作者、外部 ID、平台、内容类型、发布时间、来源 Batch/Run、AI 状态、情感和
一级/二级标签过滤，以及绑定查询条件的 HMAC Cursor。Repository 只读 Content/Analysis/Collection
Owner 的事实；不会成为第二个写 Owner。当前 AI 投影必须同时匹配 Content Version 和进程选定的
Prompt/Taxonomy/Provider/Model 身份；其他成功历史保留，但页面状态为 `stale`，不能冒充当前结果。

## 当前五平台边界

Stage 7 已接通 TikHub 的小红书、抖音、微博、B站、快手正式 Operation/Mapper。五个平台最终都进入同一 Canonical V1 和本 Content Owner；平台差异停留在 Provider Operation/Mapper，不在 Content Repository 建第二套平台表或平台专用摄取路径。

当前正式主链：

```text
Provider Adapter
→ Raw Artifact
→ Mapper
→ Canonical Content / Comment
→ Collection Candidate / Ingestion Ledger
→ ContentIngestionService
→ PostgresContentRepository
→ PostgreSQL Current / History
```

## Current 与 History 语义

- `contents` / `comments` / `accounts` 保存当前业务视图；历史事实保存在版本表和指标 Observation 表。
- 同一业务身份首次并发发现时，由 PostgreSQL UNIQUE + `ON CONFLICT` 收敛为同一记录，不能依赖“先查再插”避免竞争。
- `last_seen_at` 是实体级“最近一次看见”时间并单调向前；`first_seen_at` 可以被更早的补录 Observation 向前扩展。
- Current 的稀疏字段不能只用整行 `last_seen_at` 判断新旧。`accounts`、`contents`、`comments` 使用内部 `field_observed_at` JSONB 记录**每个已观察字段**的 freshness；同一字段只接受 `observed_at >=` 该字段已有 freshness 的 Observation。
- 因此，较旧 Observation 可以补充更晚 Observation **从未观察过**的字段；如果更晚 Observation 已经明确观察过某字段，即使值是合法 `NULL`，较旧 Observation 也不得把它回滚成旧值。
- `field_observed_at` 只保存字段路径和带时区时间，不保存第二份业务值；稳定业务字段仍使用关系列，指标历史仍使用 Metric Observation。
- Content/Comment 业务字段在字段级合并后发生变化时才推进 `current_version` 并追加 Version；旧 Observation 补入此前未知字段也属于新的 Current 业务事实，因此可以形成新版本。
- 指标历史是稀疏事实：只有 `observed_fields` 明确观察到的指标才写值，未观察指标保存 `NULL`，不得从 Current 静默带入。
- 正常时间顺序下 A → B → A 仍然是三个有效观察事实；“防止旧 Observation 回滚某字段”不等于删除真实回变历史。

## 账号稳定身份

- `accounts.external_account_id` 是平台主稳定身份；`account_external_ids` 保存已确认的备用稳定 ID。
- 同一 `account_id + id_type` 重复出现相同值是幂等。
- 如果同一 `account_id + id_type` 出现不同值，当前语义为 **fail-closed**：抛出稳定身份冲突，不静默覆盖旧值，也不根据 Observation 到达顺序猜哪个 ID 正确。
- 如果未来真实 Provider 证据证明某类 alternate ID 实际是可变属性，应通过新的身份语义 Change 重新设计，而不是放宽当前稳定 ID 约束。

## 评论 Coverage

每次正式评论采集/明确不采集都应形成可审计 Coverage 事实。当前 Schema 记录：

- `coverage`: `complete | partial | not_requested | unavailable`；
- `reported_total`；
- `collected_count`；
- `sample_mode`；
- `sort_mode`；
- `target_count`；
- `stop_reason`；
- `observed_at`；
- `provider_attempt_id` / `raw_artifact_id`。

同一 `content_id + provider_attempt_id + raw_artifact_id` 来源幂等。Stage 7 的 50/50/5 是请求深度软目标：已经由 Provider 返回并付费的当前页必须全部 Mapper/Ingestion，达到 target 只控制是否继续请求下一页。

## 不能做的事

- 不在 Content Repository 调 Provider HTTP；
- 不在 Mapper 内访问数据库；
- 不让 Collection/Router 绕过 Content Owner 直接写 Content/Comment 表；
- 不把平台原始 JSON 作为 Current 业务模型；
- 不用实体级 `last_seen_at` 替代字段级 freshness；
- 不因旧 Observation 到达较晚而回滚已经被更新 Observation 明确观察过的 Current 字段；
- 不把 `NULL`/未观察字段猜成 `0` 或沿用旧值写入历史；
- 不静默覆盖已经建立的稳定 alternate ID。

正式架构、采集决策和 Schema 语义分别以 `docs/blueprint/01-总体架构与技术选型.md`、`02-采集系统与数据标准化.md`、`03-数据库与文件存储.md`、`08-采集策略与平台能力.md` 为长期事实源。
