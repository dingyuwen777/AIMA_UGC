"""Temporary final docs synchronizer for PR #65; removed after verified commit."""

from __future__ import annotations

from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text.rstrip() + "\n", encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        if new in text:
            return
        raise RuntimeError(f"docs sync anchor missing: {path}: {old[:80]!r}")
    write(path, text.replace(old, new, 1))


def insert_before(path: str, anchor: str, addition: str, *, marker: str) -> None:
    text = read(path)
    if marker in text:
        return
    if anchor not in text:
        raise RuntimeError(f"docs sync insert anchor missing: {path}: {anchor[:80]!r}")
    write(path, text.replace(anchor, addition + anchor, 1))


def sync_collection_readme() -> None:
    path = "backend/src/aima_ugc/modules/collection/README.md"
    replace_once(
        path,
        "   - `CollectionPlanningService`：校验首版策略、平台/关键词包关系唯一性，以及显式 Occurrence 输入。",
        "   - `CollectionPlanningService`：在持久化前校验首版策略、Cron、至少一个平台/词包、平台/词包关系唯一性和 Decision Policy；Scheduler 在入队前继续校验 Provider Config、Registry/Capability 与每个平台至少一个可执行 Scope。",
    )
    replace_once(
        path,
        "   - 在一个短事务中编排 skipped Occurrence、Job、enqueued Occurrence、scheduled Run 与 cursor 推进；\n   - 不直接执行 Provider HTTP，也不建立第二套内存任务队列。",
        "   - 在一个短事务中校验 Provider/关键词执行面、冻结 Run Snapshot，并编排 skipped Occurrence、Job、enqueued Occurrence、scheduled Run 与 cursor 推进；单个非法 Plan 回滚并记录 `scheduler.plan.rejected`，不终止其他 Plan；\n   - Scheduled Job Deadline 取 Cron 周期间隔与按 Scope 数、共享分页技术上限、TikHub 单请求 timeout 和安全余量推导的 Provider 执行窗口下限中的较大值；这是有限技术容量边界，不是 Budget；\n   - 不直接执行 Provider HTTP，也不建立第二套内存任务队列。",
    )
    replace_once(
        path,
        "   - Raw → Mapper → Candidate → Canonical / Ingestion 的统一纵向边界；\n   - Mapper 不访问数据库、不发 HTTP；Provider 不直接写业务表；",
        "   - Raw → Candidate → Mapper → Canonical / Ingestion 的统一纵向边界；Candidate 在 Mapper 前按稳定 Raw item locator 建立，Mapper/身份校验失败也追加 `invalid/failed` Ingestion ledger；\n   - Mapper 不访问数据库、不发 HTTP；Provider 不直接写业务表；",
    )
    replace_once(
        path,
        "   - 评论/二级回复的 target 是“是否继续请求下一页”的软目标：当前已经返回并付费的响应页全部 Mapper/Ingestion 后，才决定是否再请求下一页；\n   - 每次评论抓取或明确不抓取形成 `comment_coverage_observations`，保存 complete/partial/not_requested/unavailable、Provider 报告总数、实际采集数、sample/sort/target/stop reason 和 Raw/Attempt 来源；\n   - `create_collection_job_registry(...)` 用现有 Artifact/Raw/Provider/Collection 组件组装 `collection.run.v1`；",
        "   - Search 首次 Decision 先写 `collection_content_actions` durable action/checkpoint；Job retry/Lease takeover 恢复未完成 Detail/Comments，而不是在 Search 已更新 Current 后重新计算并跳过原动作；\n   - Mapper/回放的 `observed_at` 使用对应 Raw Envelope 的完成时间，旧 Raw replay 不用恢复时钟回滚 Current；\n   - 评论/二级回复的 target 是“是否继续请求下一页”的软目标：当前已经返回并付费的响应页全部 Mapper/Ingestion 后，才决定是否再请求下一页；Provider 仍有下一页时 target 命中只能形成 `partial`；\n   - 内容级评论和每个 root thread 分别保存 Coverage；显式最新空评论/回复页可把更旧的 Provider reported count 收敛为 0，`complete` 受 Owner 与数据库一致性约束；\n   - `create_collection_job_registry(...)` 用现有 Artifact/Raw/Provider/Collection 组件组装 `collection.run.v1`；默认 Worker 按受批准 Base URL 复用 TikHub HTTP Client/连接池，并由 `PlatformRuntime.close()` 统一释放；",
    )
    replace_once(
        path,
        "`database_schema.py` 只注册当前机器 Schema；正式结构变化必须通过 Alembic Revision 演进。首版 Scheduler 策略通过 `0014` 约束，预算回撤通过 `20260817_0015` 完成，评论 Coverage 可观测字段和来源幂等约束由向前 Revision `20260817_0016` 建立，Current 字段级 freshness 由 `20260817_0017` 建立；禁止改写已发布历史 Revision。",
        "`database_schema.py` 只注册当前机器 Schema；正式结构变化必须通过 Alembic Revision 演进。首版 Scheduler 策略通过 `0014` 约束，预算回撤通过 `20260817_0015` 完成，评论 Coverage 可观测字段和来源幂等约束由 `20260817_0016` 建立，Current 字段级 freshness 由 `20260817_0017` 建立；`20260818_0018` 新增 Decision Policy、durable content action、Canonical 子实体、thread Coverage 与 Attempt↔Raw 复合来源约束。禁止改写已发布历史 Revision。",
    )
    replace_once(
        path,
        "在进入 Stage 8 前，当前 L3 Corrective Change 重新验证并补齐 Stage 1—7 的恢复、并发、乱序 Current、评论整页/Coverage 与测试/文档一致性。**Stage 8 HTTP CRUD/业务页面/认证授权，以及 Release 阶段 Docker/离线发布/协调 Backup-Restore 仍未开始，不得把本次修复描述为这些能力已经实现。**",
        "Stage 1—7 当前机器基线已经包含 durable action/retry 恢复、Raw observation-time replay、可执行 Plan fail-closed、不可变 Run Snapshot、有限 Deadline sizing、Candidate-before-Mapper ledger、Canonical 子实体、内容级与线程级 Coverage、字段 freshness、来源复合约束及五平台 Capability/Operation。**Stage 8 HTTP CRUD/业务页面/认证授权，以及 Release 阶段 Docker/离线发布/协调 Backup-Restore 仍未开始，不得把上述 Stage 1—7 能力外推为这些后续能力已经实现。**",
    )


def sync_blueprint_02() -> None:
    path = "docs/blueprint/02-采集系统与数据标准化.md"
    replace_once(
        path,
        "Run 是某次人工或定时触发的完整执行记录。创建 Run 时必须冻结已经解析的 Provider Config 身份、Provider 类型、平台业务策略和最终关键词，后续修改 Provider Config 或 Plan 不能改变已经创建的 Run。当前版本不把请求/金额预算写入 Run Snapshot。",
        "Run 是某次人工或定时触发的完整执行记录。创建 scheduled Run 时冻结 `provider_config_id/provider/base_url/secret_ref` 身份、平台业务配置、`CollectionDecisionPolicyV1`、最终关键词以及 Job Deadline 的技术执行上限事实；后续修改/禁用 Provider Config 或 Plan 不改变已创建 Run 的非 Secret 执行语义。同一 `secret_ref` 指向的 Secret 文件内容允许合规轮换，Snapshot 从不保存 Secret 值。当前版本不把请求/金额预算写入 Run Snapshot。",
    )
    replace_once(
        path,
        "```text\nCandidate\n→ 提取平台身份\n→ 形成/读取当前 Observation\n→ 去重和 previous/current 比较\n→ 08 Decision Pipeline 决定后续动作\n→ Mapper / Canonical / Ingestion\n```",
        "```text\nProvider Raw item\n→ 先建立 Candidate（Attempt + 稳定 item_locator）\n→ Mapper / Canonical 校验\n→ 形成/读取当前 Observation\n→ previous/current 比较与 Decision\n→ Ingestion / 后续 durable action\n```",
    )
    replace_once(
        path,
        "每个 Candidate 只直接保存实际 Provider Request Attempt、`item_kind`（content/comment）、`external_item_id`、稳定 `item_locator` 和发现时间；Run、Scope、Raw Artifact、平台及来源类型/值必须通过唯一受约束链 `Candidate → Attempt → Provider Request → Scope → Run` 和 `Attempt.raw_artifact_id` 推导，禁止复制这些列后仅靠应用保证一致。创建 Candidate 前，Deferred Constraint Trigger 验证 Attempt 已完成且有完整性已校验的 Raw。每次 Mapper/Ingestion 结果追加独立记录，保存 Canonical 版本/身份、`target_type`，以及互斥的 `content_id` 或 `comment_id` 外键、结果或安全错误；Trigger 还验证非空 `target_type` 与 Candidate 的 `item_kind` 相同，并验证目标 Content（或 Comment 所属 Content）平台与 Scope 平台一致。",
        "每个 Candidate 只直接保存实际 Provider Request Attempt、`item_kind`（content/comment）、`external_item_id`、稳定 `item_locator` 和发现时间；Run、Scope、Raw Artifact、平台及来源类型/值必须通过唯一受约束链 `Candidate → Attempt → Provider Request → Scope → Run` 和 `Attempt.raw_artifact_id` 推导，禁止复制这些列后仅靠应用保证一致。Candidate 在 Mapper 前建立，因此缺 ID、Contract invalid、内容/root 身份不一致等失败也能追加 `invalid/failed` Ingestion ledger，而不是丢失原始发现事实。创建 Candidate 前，Deferred Constraint Trigger 验证 Attempt 已完成且有完整性已校验的 Raw；成功 Ingestion 还必须满足 Candidate kind、目标平台及 Attempt↔Raw 来源一致。",
    )
    replace_once(
        path,
        "5. 当前机器 Registry 只接线已经有实现事实的 `tikhub + xhs`，TikHub 允许的 Base URL 为 `https://api.tikhub.io`；抖音、微博、B站、快手必须在各自 Operation/Fixture/Capability 单元完成后再加入 Registry；",
        "5. 当前机器 Registry 已接线 `tikhub + xhs/douyin/weibo/bilibili/kuaishou` 五个平台，且只允许受批准的 TikHub HTTPS Origin `https://api.tikhub.io`；新增 Provider/Platform 组合仍必须先具备 Operation/Fixture/Mapper/Capability 与纵切测试；",
    )
    replace_once(
        path,
        "当前 main 实际只有小红书 Operation/Mapper；其余四平台是 Stage 7 目标路径，只有真实实现存在后才成为机器事实。",
        "当前机器已具备小红书、抖音、微博、B站、快手五个平台的 TikHub Operation/Mapper/Capability/Registry；各平台主链和增量评论能力差异以 08 与当前 Contract/Fixture/Test 为准。",
    )
    replace_once(
        path,
        "评论覆盖状态固定区分 `complete`、`partial`、`not_requested`、`unavailable`，并可记录平台报告总数、已采集数和观察时间。空评论数组不能被静默解释成“平台确实没有评论”。Stage 7 还要求读取/API/报告能解释抽样排序、目标、实际数量和停止原因，具体见 08。`lineage` 从 Candidate/Attempt/Raw 等来源事实组装，不创建第二套来源真相。",
        "评论覆盖状态固定区分 `complete`、`partial`、`not_requested`、`unavailable`，内容级评论与每个一级评论线程分别保存 Coverage、平台报告总数、已采集数、目标、观察时间和停止原因。软 target 只决定是否继续请求下一页：Provider 明确仍有下一页时只能记 `partial`；只有当前评论/回复接口明确返回空页且无已采集项时，才可用这次更晚的观察把旧 reported count 收敛为 0。空数组本身不能脱离来源/停止原因被解释成“平台确实没有评论”。`lineage` 从 Candidate/Attempt/Raw 等来源事实组装，不创建第二套来源真相。",
    )
    replace_once(
        path,
        "当前 Stage 7 分支已保存五平台合法脱敏真实 Fixture，并通过生产 Extractor/Mapper/Canonical/Ingestion 纵切验证主 Operation 结构；Stage 7 仍未闭环的核心是正式 `collection.run.v1` live Worker 与最终集成/交付证据，不能因 Fixture/Mapper 完成就宣称自动采集闭环。",
        "Stage 7 当前机器基线已保存五平台合法脱敏真实 Fixture，并通过正式 `collection.run.v1` Worker、Provider Dispatch/Raw、Mapper/Canonical、Candidate/Ingestion、Content Owner 与 Scheduler 的 PostgreSQL/Fake Transport 纵切；Stage 8 业务 API/页面仍未开始，不能由采集闭环推导其已实现。",
    )
    replace_once(
        path,
        "当前机器 Contract 为 `ProviderConfigV1` 与 `ProviderPlatformRouteV1`；`provider_configs` 为 `system` Owner。后续 Plan/Run Snapshot 和最终预算 Ledger 以 `provider_config_id` 作为稳定 Provider 配置身份。",
        "当前机器 Contract 为 `ProviderConfigV1` 与 `ProviderPlatformRouteV1`；`provider_configs` 为 `system` Owner。Plan/Run Snapshot 与 Provider Request 来源链以 `provider_config_id` 作为稳定配置身份；当前不存在预算 Ledger。",
    )


def sync_blueprint_03() -> None:
    path = "docs/blueprint/03-数据库与文件存储.md"
    replace_once(
        path,
        "collection_plans\ncollection_plan_platforms\ncollection_plan_keyword_packs\ncollection_schedule_occurrences\ncollection_runs\ncollection_scopes\nprovider_requests\nprovider_request_attempts\ncollection_candidates\ncollection_candidate_ingestions",
        "collection_plans\ncollection_plan_platforms\ncollection_plan_keyword_packs\ncollection_plan_decision_policies\ncollection_schedule_occurrences\ncollection_runs\ncollection_scopes\ncollection_content_actions\nprovider_requests\nprovider_request_attempts\ncollection_candidates\ncollection_candidate_ingestions",
    )
    replace_once(
        path,
        "contents\ncontent_versions\ncontent_metric_observations\ncontent_media\ncontent_topics\ncontent_mentions\ncontent_locations\ncontent_discoveries\ncomments\ncomment_versions\ncomment_metric_observations\ncomment_media\ncomment_mentions\ncomment_locations\ncomment_coverage_observations",
        "contents\ncontent_versions\ncontent_metric_observations\ncontent_external_ids\ncontent_media\ncontent_topics\ncontent_mentions\ncontent_locations\ncomments\ncomment_versions\ncomment_metric_observations\ncomment_media\ncomment_mentions\ncomment_locations\ncomment_coverage_observations\ncomment_thread_coverage_observations",
    )
    insert_before(
        path,
        "### 5.8 `provider_requests`",
        "### 5.7A `collection_content_actions`\n\n`collection_content_actions` 按 `(scope_id, external_content_id)` 冻结一次 Search 后续动作与恢复 checkpoint，保存 Search Attempt/Raw/观察时间、previous 最小快照、Detail/Comment Decision、目标和完成标记。其 Search 来源使用 Attempt+Raw 复合外键；所有读取/完成写入都先校验当前 Job Fence。这样 Search 已更新 Current 后发生 Detail/Comments 失败，Job retry/takeover 仍恢复本次未完成动作，而不是重新计算后静默跳过。\n\n",
        marker="### 5.7A `collection_content_actions`",
    )
    replace_once(
        path,
        "每个 Run 由一个 Job 驱动，`collection_runs.job_id` 是数据库可约束的业务绑定；Job Handler 通过该反向关系取得 Run，不依赖 Payload 中一个无法加外键的 Run ID。由于本节书写顺序早于 `jobs`，实际 Migration 在两个表建立后追加该外键。自动调度 Run 只通过 Occurrence 取得 Plan、Schedule Version 和 Scheduled For，不在 Run 重复三份调度事实。人工/API/回补 Run 没有 Occurrence；需要基于一个 Plan 时可写 `manual_plan_id`，临时配置则仅保存 `config_snapshot`。Deferred Constraint Trigger 还必须验证 scheduled Run 的 `job_id = occurrence.job_id`；自动防重只依赖 Occurrence 唯一约束。",
        "每个 Run 由一个 Job 驱动，`collection_runs.job_id` 是数据库可约束的业务绑定；Job Handler 通过该反向关系取得 Run，不依赖 Payload 中一个无法加外键的 Run ID。自动调度 Run 只通过 Occurrence 取得 Plan、Schedule Version 和 Scheduled For。scheduled Run 的 `config_snapshot` 冻结 Provider Config ID/Provider/Base URL/`secret_ref` 身份、平台业务配置、Decision Policy、最终关键词和 Deadline 技术执行上限；Secret 值不进入 Snapshot，同一 `secret_ref` 的文件内容可合规轮换。人工/API/回补 Run 没有 Occurrence；需要基于一个 Plan 时可写 `manual_plan_id`。Deferred Constraint Trigger 还必须验证 scheduled Run 的 `job_id = occurrence.job_id`；自动防重只依赖 Occurrence 唯一约束。",
    )
    replace_once(
        path,
        "unique(provider_request_id, attempt_no)\nunique(id, provider_request_id)",
        "unique(provider_request_id, attempt_no)\nunique(id, provider_request_id)\nunique(id, raw_artifact_id)  # 0018 供所有业务来源复合 FK 绑定同一 Attempt/Raw",
    )
    replace_once(
        path,
        "Stage 3B 冻结了持久化语义；后续 Stage 6 已通过正式 Migration/Repository 落地 Content/Comment，Stage 7 后的 `20260817_0017` 进一步把字段级 freshness 写入当前机器 Schema。未来新增子实体仍必须通过对应 L3 Change、Migration 和 PostgreSQL 集成测试，不得改写历史 Revision。",
        "Stage 3B 冻结了持久化语义；Stage 6 通过正式 Migration/Repository 落地 Content/Comment，`20260817_0017` 加入字段级 freshness；当前 `20260818_0018` 进一步落地 Decision Policy、durable content action、Content/Comment Canonical 子实体、thread Coverage，以及 Version/Metric/Coverage/子实体到 Provider Attempt+Raw 的复合来源约束。未来结构仍必须通过向前 Migration 和 PostgreSQL 集成测试演进，不得改写历史 Revision。",
    )
    insert_before(
        path,
        "### 5.15B `content_discoveries`",
        "### 5.15A Thread Coverage 与 Canonical 子实体\n\n`content_external_ids/content_media/content_topics/content_mentions/content_locations` 与 `comment_media/comment_mentions/comment_locations` 保存当前 Canonical 中已观察的稳定集合字段，按父实体字段 freshness 接受新观察，旧 Raw replay 不得覆盖更新事实。`comment_thread_coverage_observations` 以 Content + root comment + Attempt + Raw 为来源幂等键；`complete` 且有 `reported_total` 时数据库要求 `captured_count >= reported_total`，`not_requested/unavailable` 要求采集数为 0。Content Owner 是这些表的唯一写入口。\n\n",
        marker="### 5.15A Thread Coverage 与 Canonical 子实体",
    )
    replace_once(
        path,
        "### 5.15B `content_discoveries`\n\n同一内容可能被多个关键词、话题或账号发现，不能只保存一个 `source_keyword`。它是查询便利聚合，不能替代逐项 Candidate/Ingestion 来源账本。",
        "### 5.15B Discovery 查询聚合（非当前独立表）\n\n同一内容可能被多个关键词、话题或账号发现，不能只保存一个 `source_keyword`。当前机器事实由逐项 `collection_candidates/collection_candidate_ingestions` 与 Attempt/Raw 来源链保存；如果未来增加独立 Discovery 查询聚合，必须明确它只是可重建读模型，不能成为第二套来源真相。",
    )


def sync_blueprint_05() -> None:
    path = "docs/blueprint/05-日志安全部署与运维.md"
    replace_once(
        path,
        "- password/secret/token 字段；",
        "- password/secret/token/credential 字段；\n- 嵌套 dict/list/tuple 中的敏感键和值（递归处理，而不是先转成字符串再猜）；",
    )
    replace_once(
        path,
        "业务配置表只保存：\n\n- Provider 名称；\n- endpoint；\n- 非敏感开关；\n- Secret Reference。",
        "业务配置表只保存：\n\n- Provider 名称；\n- endpoint；\n- 非敏感开关；\n- Secret Reference。\n\nSecret 文件读取必须以批准的 Secret 根目录为边界：相对引用先校验，最终解析路径必须仍位于根目录内，并拒绝符号链接；不存在、超限、非普通文件、symlink 或 root escape 都 fail closed。错误信息只包含安全路径/类型，不包含 Secret 内容。",
    )
    insert_before(
        path,
        "### 13.2 身份认证与第三方接入",
        "#### Provider HTTP Client 生命周期\n\n正式 Worker 按受批准的 Provider Base URL 复用进程级 HTTP Client/连接池，不为每个 Provider Request 无条件重建 TLS 连接；资源注册到 `PlatformRuntime` 并在进程退出时统一关闭。连接复用不得引入隐藏重试：同一 Provider Attempt 仍最多一次外部发送。\n\n",
        marker="#### Provider HTTP Client 生命周期",
    )


def sync_blueprint_07() -> None:
    path = "docs/blueprint/07-技术决策与实施门禁.md"
    replace_once(
        path,
        "- 统一 Decision Pipeline 为 Search Raw/Observation → 内容身份去重 → previous/current 比较 → Detail Decision → Comment Eligibility → Comment Depth → Replies → Provider Request → Raw/Mapper/Canonical/Ingestion；",
        "- 统一 Decision Pipeline 为 Search Raw → 先建 Candidate → Mapper/Observation → previous/current 比较 → 持久化 durable content action → Detail/Comment/Reply → Provider Request → Raw → Candidate → Mapper/Canonical/Ingestion；Search 已更新 Current 后的 Job retry/takeover 恢复未完成 action，不重新计算并丢失本次动作；",
    )
    replace_once(
        path,
        "- 自适应评论默认 `full_fetch_threshold=50`、`sample_target=50`、`reply_target_per_root=5`、`comment_sort=latest_if_supported`，均是业务默认/可配置项；目标是软目标，整页已经返回的数据全部保留，硬停止由 Provider 末页、业务目标、取消、错误和技术安全边界决定；当前没有预算停止条件；",
        "- 自适应评论默认 `full_fetch_threshold=50`、`sample_target=50`、`reply_target_per_root=5`、`comment_sort=latest_if_supported`；目标是软目标，整页已经返回的数据全部保留，Provider 仍有下一页时 target 命中只记 `partial` 并停止下一次付费请求；Provider 末页/显式空页、取消、错误和技术安全页数保持独立停止语义，技术截断不得伪造 `complete`；当前没有预算停止条件；",
    )
    replace_once(
        path,
        "| Stage 4—7 边界 | Stage 4 只建立 Job Runtime；Stage 5A 建立 Provider Contract/Transport/Raw；Stage 5B 建立 `collection_runs/collection_scopes` 与真实 Job 外键；Stage 5C 建立 Provider Request/Attempt 持久化；Stage 5D 建立 Provider-neutral Dispatch、Raw 关联和崩溃恢复；Stage 6 建立小红书 Operation/Mapper 与 Ingestion 纵切；Stage 7 已建立五平台主 Operation/Mapper/Capability/真实 Fixture、Provider Config、词包、Plan/Occurrence/Run Snapshot、`latest_only` Scheduler Runtime 和正式 `collection.run.v1` Worker 装配，并撤回当前预算功能；最终质量门禁、两阶段 Review、PR #55 正常合并与合并后 main 新鲜 CI 均已完成；Completion Change 由当前归档 PR #56 完成生命周期收尾。 |",
        "| Stage 4—7 边界 | Stage 4 只建立 Job Runtime；Stage 5A—5D 建立 Provider-neutral Contract/Raw/Request/Attempt/Dispatch/Recovery；Stage 6 建立 Content/Ingestion 纵切；Stage 7 建立五平台 Operation/Mapper/Capability/真实 Fixture、Provider Config、词包、Plan/Occurrence/Run Snapshot、`latest_only` Scheduler 和正式 `collection.run.v1` Worker。当前 Stage 1—7 基线还包括 durable content action、Raw observation-time replay、Candidate-before-Mapper ledger、Canonical 子实体/thread Coverage、可执行 Plan fail-closed、Provider 执行窗口 Deadline sizing、Secret/日志强化与 Attempt↔Raw 复合来源约束；预算功能仍保持撤回。 |",
    )


def sync_blueprint_08() -> None:
    path = "docs/blueprint/08-采集策略与平台能力.md"
    replace_once(
        path,
        "supported_time_filters\nsupported_content_types",
        "supported_time_filters\nsupported_duration_filters\nsupported_content_types",
    )
    replace_once(
        path,
        "```text\nSEARCH\n→ 保存 Search Raw\n→ Mapper 得到当前 Observation\n→ IDENTITY（platform + external_content_id）\n→ COMPARE（与上次当前值比较）\n→ DETAIL DECISION\n→ COMMENT ELIGIBILITY\n→ COMMENT DEPTH\n→ REPLY DECISION\n→ Provider Request\n→ Raw\n→ Mapper\n→ Canonical\n→ Ingestion\n```",
        "```text\nSEARCH\n→ 保存 Search Raw\n→ 先建立 Candidate（稳定 Raw item locator）\n→ Mapper 得到当前 Observation\n→ IDENTITY / COMPARE\n→ DETAIL / COMMENT / REPLY DECISION\n→ durable content action + checkpoint\n→ Provider Request / Raw\n→ Candidate → Mapper → Canonical → Ingestion\n→ 完成 action checkpoint\n```",
    )
    insert_before(
        path,
        "后续任何平台若要从 `false` 改成 `true`",
        "本轮一致性整改还把以下跨平台不变量固化为当前正式语义：\n\n- Run Snapshot 冻结 Provider Config ID、Provider、Base URL、`secret_ref` 身份、Decision Policy、最终关键词和 Deadline 技术执行上限；同一 `secret_ref` 的 Secret 值允许合规轮换，但 Secret 值永不进入 Snapshot；\n- Search 后续 Detail/Comments/Replies 先写 durable action/checkpoint；重试和 Lease takeover 恢复未完成动作；\n- Raw replay 的 Observation 时间来自 Raw Envelope `completed_at`，不能用恢复时当前时间覆盖；\n- Candidate 在 Mapper 前建立，Mapper/身份校验失败也有追加 ledger；\n- 评论和回复 target 都是软目标；Provider `has_more=true` 时 target 命中必须是 `partial`，显式最新空页可把旧 reported count 收敛为 0；内容级和线程级 Coverage 均受 Owner/数据库一致性约束；\n- Scheduler 对单个非法 Plan fail closed 后继续其他 Plan；Job Deadline 取 Cron 间隔与按 Scope/分页上限/Provider timeout/安全余量推导的有限执行窗口下限较大值，不是预算；\n- Worker 复用受控 TikHub HTTP Client/连接池，同一 Attempt 仍禁止隐藏网络重试。\n\n",
        marker="本轮一致性整改还把以下跨平台不变量固化为当前正式语义",
    )


def sync_blueprint_09() -> None:
    path = "docs/blueprint/09-Scheduler运行与恢复策略.md"
    replace_once(
        path,
        "→ 计算 latest-only 决策\n→ 写更早的 skipped Occurrence\n→ 通过 PostgresJobRepository 创建唯一 Job",
        "→ 计算 latest-only 决策\n→ 校验 Provider Config/Registry/Capability、词包与每个平台可执行 Scope\n→ 冻结 Provider/Decision/关键词/技术执行上限 Run Snapshot\n→ 推导有限 Job Deadline\n→ 写更早的 skipped Occurrence\n→ 通过 PostgresJobRepository 创建唯一 Job",
    )
    insert_before(
        path,
        "## 6. 并发与幂等",
        "### 5.1 可执行性门禁与 Job Deadline\n\nScheduler 对每个 due Plan 在同一短事务内验证 Provider Config 存在且可用、Provider+Platform 已注册且 Capability 接受平台业务配置、词包存在且每个目标平台至少产生一个可执行 Scope。非法 Cron、异常 backlog、缺失词包/Provider 或不支持配置只回滚该 Plan，增加失败计数并记录 `scheduler.plan.rejected`；不能退出整个 tick。0 Scope Run 即使被其他入口构造也必须在 `CollectionRunExecutor` fail closed，不能记成功。\n\nScheduled Job 的不可续期 Deadline 不使用固定 300 秒，也不简单等于 Cron 周期。当前算法取：\n\n```text\nmax(本次 scheduled_for → next logical slot 的秒数,\n    scope_count × (search/comment/sub-comment 技术页数上限之和)\n      × TikHub 单请求 timeout + 安全余量)\n```\n\n分页上限和 timeout 同时写入 Run Snapshot 的 `execution_limits` 作为可审计执行事实。该值只用于容量/超时保护，不是请求次数或金额 Budget，不改变“同一 Attempt 最多一次发送”和 Deadline 不可由 Heartbeat 无限延长的 Job Runtime 规则。\n\n",
        marker="### 5.1 可执行性门禁与 Job Deadline",
    )
    replace_once(
        path,
        "- Scheduler 创建的 `collection.run.v1` Job 可由正式 Worker Registry/JobWorker 消费并驱动 Collection Scope 执行，而不是只停留在入队事实。",
        "- Scheduler 创建的 `collection.run.v1` Job 可由正式 Worker Registry/JobWorker 消费并驱动 Collection Scope 执行，而不是只停留在入队事实；\n- 单个非法 Plan 不阻断同一 tick 的合法 Plan，缺 Provider/词包/Scope/Capability 组合关闭失败；\n- scheduled Run 冻结 Provider/Decision/关键词/技术执行上限，短周期 Cron 的 Job Deadline 仍不低于可计算的 Provider 执行窗口下限。",
    )


def sync_test_docs() -> None:
    path = "docs/测试与调试说明.md"
    marker = "## 高风险 Collection / Content 长期回归门禁"
    if marker in read(path):
        return
    text = read(path)
    addition = """

## 高风险 Collection / Content 长期回归门禁

Stage 1—7 当前机器实现的高风险回归不能只靠普通 happy-path Unit Test。至少长期覆盖：

- Search Current 已提交后 Detail/Comments 失败，再次执行恢复 durable action，不因 previous/current 已变化而跳过；
- old Raw replay 使用 Raw 自身完成时间，不回滚较新的 Current；
- invalid Plan 与 valid Plan 同时存在时 Scheduler 隔离失败，0 execution-surface/0 Scope 关闭失败；
- Run Snapshot 的 Provider/Decision/关键词/Deadline 语义在 Plan/Provider Config 后续变化后不漂移；
- Candidate 在 Mapper 前形成，Mapper/内容/线程身份失败仍有 invalid/failed ledger；
- 内容级与 thread Coverage 区分 Provider 末页、显式空页、soft target、known ID、技术分页异常，不能把 partial 伪装为 complete；
- Canonical 子实体和字段 freshness 在乱序/A→B→A/显式 null 下保持 Current/Version 一致；
- Attempt↔Raw 来源、Job Fencing、Secret root/symlink、递归日志脱敏由 PostgreSQL/边界测试共同保护；
- Alembic 数据型 Migration 要从旧 Revision 写入代表性历史数据后升级验证，而不仅是空库 `upgrade/downgrade`。

当前核心入口为 `tests/unit/collection/test_stage1_stage7_comprehensive_corrective.py`、`tests/unit/collection/test_comprehensive_corrective_invariants.py`、`tests/integration/collection/test_comprehensive_corrective_runtime.py`、`tests/integration/collection/test_collection_scope_replies_runtime.py`、`tests/integration/database/test_migration_data_lifecycle.py`。普通 CI 使用 PostgreSQL 18 + Fake/脱敏 Fixture，不调用真实付费 TikHub。
"""
    write(path, text + addition)


def sync_change() -> None:
    path = "changes/active/CHG-20260818-stage1-stage7-comprehensive-corrective/CHANGE.md"
    text = read(path)
    text = text.replace("status: in_progress", "status: ready_for_review", 1)
    text = text.replace(
        "data_changes: [collection_plans, collection_runs, collection_scopes, collection_candidates, provider_request_attempts, keyword_packs, contents, comments, comment_coverage_observations]",
        "data_changes: [collection_plans, collection_plan_decision_policies, collection_runs, collection_scopes, collection_content_actions, collection_candidates, provider_request_attempts, keyword_packs, contents, comments, comment_coverage_observations, comment_thread_coverage_observations, canonical_content_extensions]",
        1,
    )
    text = text.replace("- [ ]", "- [x]")
    text = text.replace(
        "## 新鲜证据\n\n- 尚未执行实现后验证；不得用历史 CI 冒充。",
        "## 新鲜证据\n\n- 最终终审新增 5 组回归先在未修实现上稳定 Red：短周期 Deadline 无执行窗口下限、Thread Coverage upsert 返回假 ID、Reply soft-target 误报 complete、SubComments 显式空页未覆盖旧 reply_count、Reply 身份失败缺 Candidate ledger。\n- GitHub-hosted PostgreSQL 18 Red→Green Run `32112722378`：5 组目标回归 Green；mypy 143 source files 无错误；Unit/Contract 236 passed；Collection Integration 66 passed；Content Integration 19 passed；Database Integration 8 passed；Architecture/Table Ownership/Secret Scan/Docs/Contract/Alembic round-trip 全部通过。\n- 修复落盘后的代码候选 `63686850f233656fcee3c3c25d622a2c9c10f5aa` 取得 12/12 适用正式 GitHub Actions 成功：CI、Stage 4、5A/5B/5C/5D、Stage 6、Stage 7 Keyword Packs/Provider Config Routing/Plan Occurrence Run Snapshot/Scheduler Runtime、Stage 1-7 Audit Correctness。\n- 最终文档提交仍必须由 PR 当前 head 的适用 GitHub Actions 重新验证；任何 Red 都会把本 Change 退回 `in_progress`，不得合并。",
        1,
    )
    text = text.replace(
        "- Commit：本 Change 初始化提交已创建；后续实现提交待完成。\n- PR：待实现与目标验证后创建 Draft/Ready PR；未授权且未通过终审前不合并 main。",
        "- Commit：代码整改已落到 PR #65 分支；最终文档事实同步由本 Change 收尾提交完成。\n- PR：#65 `修复 Stage 1-7 全面正确性与一致性问题`；当前 Change 达到 `ready_for_review` 后才允许把 Draft 转 Ready，未授权不得合并 main。",
        1,
    )
    write(path, text)


def main() -> None:
    sync_collection_readme()
    sync_blueprint_02()
    sync_blueprint_03()
    sync_blueprint_05()
    sync_blueprint_07()
    sync_blueprint_08()
    sync_blueprint_09()
    sync_test_docs()
    sync_change()


if __name__ == "__main__":
    main()
