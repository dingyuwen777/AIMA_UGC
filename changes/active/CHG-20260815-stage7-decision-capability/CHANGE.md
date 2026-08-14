---
schema: rvc-change/v1
id: CHG-20260815-stage7-decision-capability
title: 建立 Stage 7 采集决策与 Provider Capability 基础
level: L3
status: ready_for_review
owner: dingyuwen777
branch: agent/stage7-decision-capability
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-collection-pipeline]
affected_areas: [collection, provider, contracts, testing, documentation]
affected_paths: [backend/src/aima_ugc/contracts/collection/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py, contracts/collection/, scripts/contracts/, scripts/dev/probe_collection_decision.py, tests/unit/collection/, tests/contracts/test_collection_stage7.py, backend/src/aima_ugc/modules/collection/README.md]
contracts: [collection-decision.v1, provider-platform-capability.v1]
data_changes: []
---

# 目标

把 Blueprint 08 已批准的 Stage 7 通用采集 Decision/Capability 从文档事实落成第一批机器事实：版本化 Pydantic Contract 表达 previous/current Observation、业务策略、Provider/Platform Capability 和可解释 Decision；唯一生产 `CollectionDecisionService` 负责详情、一级评论和二级回复动作；当前机器 Capability 只登记已有 Stage 6 Operation/Mapper 的小红书 TikHub。

# 成功标准

- [x] 建立 `collection-decision-request.v1` / `collection-decision.v1` Pydantic Contract，稳定表达 current/previous comment_count、评论可用性、详情触发事实、策略、Capability、动作和 reason code。
- [x] 建立 `provider-platform-capability.v1`；只表达业务能力，不暴露 cursor/search_id/pageArea/Secret 等技术状态。
- [x] `CollectionDecisionService` 为纯生产逻辑，覆盖新内容、零评论、评论不可用、重复评论数不变、增/减/未知、Deep/定时详情触发，以及 reply_count=0/>0/unknown。
- [x] 评论数增加只有 Capability 明确声明 `supports_incremental_comment_sort=true` 才返回增量动作，否则受控刷新；`null` 与 `0` 严格区分。
- [x] `XHS_TIKHUB_CAPABILITY` 与当前 XHS `search_notes/get_*_detail/get_note_comments/get_note_sub_comments` 机器实现一致；没有把其余四平台设计目标注册成当前能力。
- [x] `contracts/collection/*.schema.json` 由 Pydantic 确定性生成，生成/漂移门禁已经接入现有 Contract 脚本。
- [x] `scripts/dev/probe_collection_decision.py` 用显式 JSON 调用正式 Decision Service；测试通过真实子进程执行脚本，不复制业务逻辑、不改 `sys.path`。
- [x] Red 先因目标模块尚不存在失败；Green 后 Stage 5A—5D、Stage 6、主 CI 全部成功。
- [x] 两阶段 Review 已完成并修复两个问题：Capability 不超报当前评论排序；无二级评论能力时不产生回复目标假信号。
- [x] 无 Migration/数据库表/公开 HTTP API/前端/Scheduler/依赖/锁文件变化。
- [x] Collection README 同步机器入口、Probe 和已知限制；Secret 扫描成功，TikHub API Key 未进入仓库或 CI 输出。
- [ ] PR #33 最终元数据 head CI 成功后转 ready、合并；合并后 main 相关 CI 成功，再归档 Change。

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
2. 本单元先建立跨平台公共 Decision/Capability；四平台 Capability 在各自真实 Operation/Fixture 单元中增加。
3. Decision Service 只接受规范化事实，生产编排以后负责从 Mapper/PostgreSQL 准备 previous/current state。
4. 当前 XHS 评论 Capability **不声明**稳定增量停止：TikHub 官方文档说明 `latest_v2` 是最新评论排序，但仓库尚无合法脱敏非空评论 Fixture/Real Probe 证明“遇到已知 comment_id 即可安全停止”，因此评论数增加先 `refresh_controlled`。
5. 当前 XHS 评论 Operation 虽然 TikHub 官方支持多种排序，但仓库 Stage 6 builder 固定 `sort_strategy=latest_v2`；因此当前机器 Capability 只暴露规范化 `latest`，不能把 Provider 支持但代码尚未参数化的排序冒充已实现业务能力。
6. TikHub Secret 只允许经正式 Secret 边界进入显式 Real Probe。本轮使用用户授权凭据做最小只读请求尝试时，执行宿主在 TLS/HTTP 之前即 DNS 解析失败；凭据未写文件、未打印、未提交，因此没有新增真实接口兼容证据。

# 方案比较

采用“先 Decision + Capability 公共基础”：先冻结五平台共享的后续请求决策和可配置能力，再实现各平台 Operation/Mapper。相比先做单一抖音纵切，可避免四平台复制业务判断；相比一次做完 Decision+预算+四平台，可保持 Red→Green 单元小而完整。

# Red → Green 证据

## Red

PR #33 初始只提交失败测试。`Stage 6 XHS Unit` job `94861873862` 在测试收集阶段以退出码 2 失败，核心错误：

```text
ModuleNotFoundError: No module named 'aima_ugc.adapters.providers.tikhub.capabilities'
```

失败来自目标模块尚不存在，不是依赖、数据库或旧实现故障。

## Green 过程中发现并修复

1. 首轮 Quality 指出 `models.py` Ruff format 漂移；只按 Ruff 格式修正，无行为变化。
2. Unit 指出测试把 `scripts/` 当包导入；改为子进程真实执行 `scripts/dev/probe_collection_decision.py`，未加入 `PYTHONPATH/sys.path` 特例。
3. Quality/主 CI 指出 3 个 Collection Schema 与 Pydantic 生成物仅有 description 漂移；按 `scripts/contracts/generate.py` 实际生成 diff 同步，最终生成检查通过。
4. 第一阶段需求 Review 发现 XHS Capability 曾把 TikHub 支持的 `most_liked` 暴露为当前可配置排序，但 Stage 6 builder 实际固定 `latest_v2`；已收紧为 `comment_sort_modes=("latest",)` 并测试 builder 参数。
5. 第二阶段质量 Review 发现 `reply_target_per_root` 在未来不支持二级回复的平台仍可能给出 5；已改为只有 comments Capability 明确支持且存在 `sub_comments` Operation 时才给出目标，并补负例测试。
6. Review 修正后一次 Stage 5A 只因测试注释 101 字符触发 Ruff E501；Provider/Raw 17 个测试与 Contract 检查此前均已成功。已只拆分注释，不改行为或断言。

## Review 后最终 Green

行为/测试 head：`8596c9e7417b86c11498e59b6c4bbb9b98cebd9f`

- `CI #276` / run `31831424969`：success；Stage 1、Stage 2、Stage 3A、Windows bootstrap 全部 success。
- `Stage 5A Provider Raw #40` / `31831424950`：success。
- `Stage 5B Collection Execution #38` / `31831424995`：success。
- `Stage 5C Provider Persistence #35` / `31831424961`：success。
- `Stage 5D Provider Dispatch #32` / `31831425020`：success。
- `Stage 6 XHS Vertical Slice #114` / `31831424967`：success；Unit、Quality、PostgreSQL 均 success。
- Stage 5A 的 Provider/Raw 17 tests、Provider/Collection Contract 生成与漂移检查、Ruff/mypy/architecture/owner/secret/docs 门禁均成功。
- Stage 6 PostgreSQL 实际通过 Collection/Stage 6 Integration 和 Stage 5D/Stage 6/base Migration round-trip 路径。

本次 Change 审计文件更新发生在上述代码/测试 head 之后，不改变生产或测试逻辑；PR 最终 head 仍需重新通过 GitHub Actions 后才允许合并。

当前宿主没有本地 Git 工作树，因此没有伪造本地 `git status`/pytest 输出；以上均来自 PR GitHub Actions 新鲜证据。

# 两阶段 Review

## 第一阶段：需求符合性

- 目标 Decision/Capability 已落机器 Contract；XHS 只登记当前实现能力；其余四平台未提前实现/注册。
- 零评论、评论不变、增减/未知、Deep/定时详情和二级回复规则均有测试。
- Scheduler、Migration、Plan 持久化、预算、HTTP API、前端均未越界。
- 发现并修复“Provider 支持排序 ≠ 当前仓库已实现可配置排序”的 Capability 超报。

## 第二阶段：代码质量

- Decision Service 为纯逻辑，无 HTTP/DB/Raw 解析；Probe 复用生产 Service。
- Capability 不包含 Secret/技术分页字段；Secret 扫描通过。
- 无 sub-comments Capability 时不会产出虚假 reply target。
- Contract 由 Pydantic 唯一生成源维护，固定 Schema 有 drift 门禁。
- 未新增依赖、临时抽象、Migration 或跨模块 SQL。

# 文档、兼容、Migration、部署、回滚

- 文档：只更新 Collection 模块 README；Blueprint 08 业务语义未改变，因此不重复修改 Blueprint。
- 公共 HTTP API：无变化。
- Canonical/Provider V1：无破坏性变化；新增独立 Collection V1 Contract。
- DB/Migration：无变化。
- 依赖/Lock：无变化。
- 部署：无新增进程/配置。
- 回滚：回滚本 PR 即可，无数据回填或数据库回滚。

# Git

- 基线 main：`d0c1dc0b64bbda0c93d49aff1cc83677a0c17c29`
- 分支：`agent/stage7-decision-capability`
- Change：`ready_for_review`
- PR：#33（draft；最终 head CI 成功后转 ready）
- Red：已确认
- Green：Review 后代码/测试 head 六条相关 workflow 全部 success
- 合并：未执行
- 归档：未执行
