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
- [x] 无 Migration/数据库表/公开 HTTP API/前端/Scheduler/依赖/锁文件变化。
- [x] Collection README 同步机器入口、Probe 和已知限制；Secret 扫描成功，TikHub API Key 未进入仓库或 CI 输出。
- [ ] PR #33 正式 Review 后合并，合并后 main 相关 CI 成功，再归档 Change。

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
5. TikHub Secret 只允许经正式 Secret 边界进入显式 Real Probe。本轮使用用户授权凭据做最小只读请求尝试时，执行宿主在 TLS/HTTP 之前即 DNS 解析失败；凭据未写文件、未打印、未提交，因此没有新增真实接口兼容证据。

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

## 当前 Green

head：`66854ae040401bc428e65e036a31739426e9f409`

- `CI #270` / run `31830794703`：success；Stage 1、Stage 2、Stage 3A、Windows bootstrap 全部 success。
- `Stage 5A Provider Raw #34` / `31830794691`：success。
- `Stage 5B Collection Execution #32` / `31830794671`：success。
- `Stage 5C Provider Persistence #29` / `31830794670`：success。
- `Stage 5D Provider Dispatch #26` / `31830794686`：success。
- `Stage 6 XHS Vertical Slice #108` / `31830794685`：success；Unit、Quality、PostgreSQL 均 success。
- Stage 6 Quality 实际执行并通过 Ruff format/check、mypy、architecture、table owner、secret scan、docs、Contract generate/check/compatibility。
- Stage 6 PostgreSQL 实际通过 Collection/Stage 6 Integration 和既有 Migration 升级/round-trip 路径。

当前宿主没有本地 Git 工作树，因此没有伪造本地 `git status`/pytest 输出；上面全部来自本 PR GitHub Actions 新鲜证据。

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
- PR：#33（draft，待完成 Review 后转 ready）
- Red：已确认
- Green：当前 head 六条相关 workflow 全部 success
- 合并：未执行
- 归档：未执行
