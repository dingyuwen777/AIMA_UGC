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
- `last_seen_at` 单调向前，`first_seen_at` 可以被更早的补录 Observation 向前扩展。
- `observed_at` 较旧的乱序 Observation 仍可留下历史指标/来源事实，但不得覆盖较新的 Current 业务字段、Current 指标、`updated_at` 或 `current_version`。
- 指标历史是稀疏事实：只有 `observed_fields` 明确观察到的指标才写值，未观察指标保存 `NULL`，不得从 Current 静默带入。
- 正常时间顺序下 A → B → A 仍然是三个有效观察事实；“防止旧 Observation 回滚 Current”不等于删除真实回变历史。

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
- 不因旧 Observation 到达较晚而回滚较新的 Current；
- 不把 `NULL`/未观察字段猜成 `0` 或沿用旧值写入历史。

正式架构、采集决策和 Schema 语义分别以 `docs/blueprint/01-总体架构与技术选型.md`、`02-采集系统与数据标准化.md`、`03-数据库与文件存储.md`、`08-采集策略与平台能力.md` 为长期事实源。
