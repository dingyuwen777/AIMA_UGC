---
schema: rvc-change/v1
id: CHG-20260815-stage7-decision-capability
title: 建立 Stage 7 采集决策与 Provider Capability 基础
level: L3
status: done
owner: dingyuwen777
branch: agent/stage7-decision-capability
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-collection-pipeline]
affected_areas: [collection, provider, contracts, testing, documentation]
affected_paths: [backend/src/aima_ugc/contracts/collection/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py, contracts/collection/, scripts/contracts/, scripts/dev/probe_collection_decision.py, tests/unit/collection/, tests/contracts/test_collection_stage7.py, backend/src/aima_ugc/modules/collection/README.md]
contracts: [collection-decision.v1, provider-operations-capability.v1]
data_changes: []
---

# 目标与结果

把 Blueprint 08 已批准的 Stage 7 通用采集 Decision/Capability 落成第一批机器事实：版本化 Pydantic Contract 表达 previous/current Observation、业务策略、Provider/Platform Capability 和可解释 Decision；唯一生产 `CollectionDecisionService` 负责详情、一级评论和二级回复动作；当前机器 Capability 只登记已有 Stage 6 Operation/Mapper 的小红书 TikHub。

本 Change 已完成并通过 PR、合并后 main CI 与两阶段 Review。

# 成功标准

- [x] 建立 `collection-decision-request.v1` / `collection-decision.v1` Pydantic Contract，稳定表达 current/previous comment_count、评论可用性、详情触发事实、策略、Capability、动作和 reason code。
- [x] 建立 `provider-platform-capability.v1`；只表达业务能力，不暴露 cursor/search_id/pageArea/Secret 等技术状态。
- [x] `CollectionDecisionService` 为纯生产逻辑，覆盖新内容、零评论、评论不可用、重复评论数不变、增/减/未知、Deep/定时详情触发，以及 reply_count=0/>0/unknown。
- [x] 评论数增加只有 Capability 明确声明 `supports_incremental_comment_sort=true` 才返回增量动作，否则受控刷新；`null` 与 `0` 严格区分。
- [x] `XHS_TIKHUB_CAPABILITY` 与当前 XHS `search_notes/get_*_detail/get_note_comments/get_note_sub_comments` 机器实现一致；没有把其余四平台设计目标注册成当前能力。
- [x] `contracts/collection/*.schema.json` 由 Pydantic 确定性生成，生成/漂移门禁接入现有 Contract 脚本。
- [x] `scripts/dev/probe_collection_decision.py` 用显式 JSON 调用正式 Decision Service；测试通过真实子进程执行脚本，不复制业务逻辑、不改 `sys.path`。
- [x] Red 先因目标模块尚不存在失败；Green 后 Stage 5A—5D、Stage 6、主 CI 全部成功。
- [x] 两阶段 Review 完成并修复 Capability 超报与无二级评论能力时的回复目标假信号。
- [x] 无 Migration/数据库表/公开 HTTP API/前端/Scheduler/依赖/锁文件变化。
- [x] Collection README 同步机器入口、Probe 和已知限制；Secret 扫描成功，TikHub API Key 未进入仓库或 CI 输出。
- [x] PR #33 合并，合并后 main 六条相关 workflow 全部 success。

# 范围与非目标

范围：Collection Decision/Capability Contract、纯 Decision Service、当前 XHS TikHub Capability、固定 JSON Schema、Business Decision Probe、Unit/Contract Test、Collection README。

明确非目标：抖音/微博/B站/快手 Operation/Mapper；Plan/Run Snapshot；最终 Budget Ledger/Migration；公开 API/前端；Scheduler；生产真实 TikHub Transport/Dispatcher 接线。

# 必须保持不变

- Stage 1—6 Contract/Migration/Provider Request/Attempt/Raw/Candidate/Ingestion/Content Owner/Job Runtime 兼容。
- Provider Operation 独占 endpoint/分页；Decision 不拼 URL、不解析 Raw、不访问 DB。
- Mapper 继续只负责 Raw→Canonical，不决定是否继续花钱抓详情/评论。
- Secret 不进入源码、Git、日志、Raw、Fixture、Contract、Probe 输出或测试快照。
- XHS 当前 App V2 endpoint 和 `latest_v2` Operation 行为不被静默改变。

# 已确认关键决策

1. 使用 Blueprint 08 的 `new_or_comment_changed`、adaptive 50/50/5 默认语义。
2. 本单元只建立跨平台公共 Decision/Capability；四平台 Capability 在各自真实 Operation/Fixture 单元中增加。
3. Decision Service 只接受规范化事实，生产编排后续负责从 Mapper/PostgreSQL 准备 previous/current state。
4. 当前 XHS 评论 Capability 不声明稳定增量停止：虽然 `latest_v2` 是最新评论排序，但仓库尚无合法脱敏非空评论 Fixture/Real Probe 证明“遇到已知 comment_id 即可安全停止”，因此评论数增加先 `refresh_controlled`。
5. TikHub 官方支持多个评论排序，但当前 Stage 6 builder 固定 `sort_strategy=latest_v2`；当前机器 Capability 只暴露规范化 `latest`，不能把 Provider 支持但代码尚未参数化的排序冒充已实现业务能力。
6. TikHub Secret 只允许经正式 Secret 边界进入显式 Real Probe。本轮使用用户授权凭据做最小只读请求尝试时，执行宿主在 TLS/HTTP 之前即 DNS 解析失败；凭据未写文件、未打印、未提交，因此没有新增真实接口兼容证据。

# 方案比较

采用“先 Decision + Capability 公共基础”：先冻结五平台共享的后续请求决策和可配置能力，再实现各平台 Operation/Mapper。相比先做单一抖音纵切，可避免四平台复制业务判断；相比一次做完 Decision+预算+四平台，可保持 Red→Green 单元小而完整。

# Red → Green 与修复证据

## Red

PR #33 初始只提交失败测试。`Stage 6 XHS Unit` job `94861873862` 在测试收集阶段以退出码 2 失败：

```text
ModuleNotFoundError: No module named 'aima_ugc.adapters.providers.tikhub.capabilities'
```

失败来自目标模块尚不存在，不是依赖、数据库或旧实现故障。

## Green 过程中处理的问题

1. Ruff format 指出 `models.py` 格式漂移，只做格式修正。
2. Unit 指出测试把 `scripts/` 当包导入，改为子进程真实执行 `scripts/dev/probe_collection_decision.py`，没有加入 `PYTHONPATH/sys.path` 特例。
3. Contract 生成门禁指出三个 Collection Schema description 漂移，按 `scripts/contracts/generate.py` 实际生成结果同步。
4. 需求 Review 发现 XHS Capability 超报未参数化的评论排序，收紧为 `comment_sort_modes=("latest",)` 并测试 builder 的 `latest_v2`。
5. 质量 Review 发现未来不支持二级回复的平台仍可能得到 `reply_target_per_root=5`，改为只有 Capability 支持且存在 `sub_comments` Operation 时才给出目标，并补负例测试。
6. Review 后 Stage 5A 曾仅因测试注释 101 字符触发 Ruff E501；拆分注释后全绿，没有改行为或测试标准。

# PR 最终验证

PR #33 最终 head：`e1730b3bc2a048cbf4367e12ca71c562afb18685`。

- `CI #277` / `31831598964`：success。
- `Stage 5A Provider Raw #41` / `31831599060`：success。
- `Stage 5B Collection Execution #39` / `31831599026`：success。
- `Stage 5C Provider Persistence #36` / `31831598997`：success。
- `Stage 5D Provider Dispatch #33` / `31831599092`：success。
- `Stage 6 XHS Vertical Slice #115` / `31831598983`：success。

PR 无 review thread、无 review submission、无讨论评论阻塞；转 ready 后以正常 merge commit 合并。

# 合并与 main 验证

PR #33 merge commit：`80cc4c76faed97ab3e54204ac35a2a8bbe343bd4`。

合并后 main：

- `CI #278` / `31831751075`：success；Stage 1/2/3A/Windows 全部 success。
- `Stage 5A Provider Raw #42` / `31831751147`：success。
- `Stage 5B Collection Execution #40` / `31831751085`：success。
- `Stage 5C Provider Persistence #37` / `31831751071`：success。
- `Stage 5D Provider Dispatch #34` / `31831751095`：success。
- `Stage 6 XHS Vertical Slice #116` / `31831751079`：success；Unit/Quality/PostgreSQL 全部 success，既有 Migration round-trip 继续通过。

当前执行宿主没有本地 Git 工作树，因此没有伪造本地 `git status`/pytest 输出；完成证据来自 PR/main GitHub Actions。

# 两阶段 Review

## 第一阶段：需求符合性

- Decision/Capability 已落机器 Contract；XHS 只登记当前实现能力；其余四平台未提前实现/注册。
- 零评论、评论不变、增减/未知、Deep/定时详情和二级回复规则均有测试。
- Scheduler、Migration、Plan 持久化、预算、HTTP API、前端均未越界。
- 修复“Provider 支持排序 ≠ 当前仓库已实现可配置排序”的 Capability 超报。

## 第二阶段：代码质量

- Decision Service 为纯逻辑，无 HTTP/DB/Raw 解析；Probe 复用生产 Service。
- Capability 不包含 Secret/技术分页字段；Secret 扫描通过。
- 无 sub-comments Capability 时不会产出虚假 reply target。
- Contract 由 Pydantic 唯一生成源维护，固定 Schema 有 drift 门禁。
- 未新增依赖、临时抽象、Migration 或跨模块 SQL。

# 兼容、Migration、部署和回滚

- 公共 HTTP API：无变化。
- Canonical/Provider V1：无破坏性变化；新增独立 Collection V1 Contract。
- DB/Migration：无变化。
- 依赖/Lock：无变化。
- 部署：无新增进程/配置。
- 回滚：回滚 PR #33 即可，无数据回填或数据库回滚。

# Git

- 基线 main：`d0c1dc0b64bbda0c93d49aff1cc83677a0c17c29`
- 开发分支：`agent/stage7-decision-capability`
- PR：#33，已合并
- merge commit：`80cc4c76faed97ab3e54204ac35a2a8bbe343bd4`
- Change：`done`，归档中
- 生产部署：未执行
