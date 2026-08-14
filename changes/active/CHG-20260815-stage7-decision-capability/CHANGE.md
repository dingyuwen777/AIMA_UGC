---
schema: rvc-change/v1
id: CHG-20260815-stage7-decision-capability
title: 建立 Stage 7 采集决策与 Provider Capability 基础
level: L3
status: in_progress
owner: dingyuwen777
branch: agent/stage7-decision-capability
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-collection-pipeline]
affected_areas: [collection, provider, contracts, testing, documentation]
affected_paths: [backend/src/aima_ugc/contracts/collection/, backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/providers/tikhub/, contracts/collection/, scripts/contracts/generate.py, tests/unit/collection/, tests/contracts/, backend/src/aima_ugc/modules/collection/README.md, docs/测试与调试说明.md]
contracts: [collection-decision.v1, provider-platform-capability.v1]
data_changes: []
---

# 目标

把 Blueprint 08 已批准的 Stage 7 通用采集决策和 Provider Capability 从文档事实落成第一批机器事实：由版本化 Pydantic Contract 表达当前/上次 Observation、业务策略、平台 Operation Capability 和可解释 Decision；由唯一生产 Decision Service 计算详情、评论和二级回复动作；TikHub 小红书 Capability 只声明当前 Stage 6 已实现且官方文档可确认的能力。后续抖音/微博/B站/快手复用同一 Contract/Decision，不复制业务规则。

# 成功标准

- [ ] 新增版本化 `collection-decision.v1` Pydantic Contract，能表达 previous/current comment_count、评论可用性、详情触发事实、评论策略、Capability 输入、Detail/Comment/Reply 动作和稳定 reason code。
- [ ] 新增版本化 `provider-platform-capability.v1` Contract；Capability 只表达业务语义，不包含 cursor/search_id/pageArea/Secret 等 Provider 技术状态。
- [ ] `CollectionDecisionService` 为纯生产逻辑，覆盖：新内容、零评论短路、评论关闭/不可用、重复内容评论数未变化、评论数增加、评论数减少、评论数未知、Deep/定时详情触发，以及一级线程 `reply_count=0/>0/unknown`。
- [ ] 评论数增加时，只有 Capability 明确支持稳定最新排序才返回增量评论动作，否则返回受控刷新；未知 comment_count 不得当成 0。
- [ ] XHS TikHub Capability 与当前 `search_notes/get_*_detail/get_note_comments/get_note_sub_comments` 实现及 TikHub 官方文档一致；不声明尚未实现的四平台 Capability 为当前机器事实。
- [ ] 固定生成 `contracts/collection/*.schema.json`，`scripts/contracts/generate.py --check` 能检查漂移。
- [ ] 建立独立 Business Decision 调试入口，输入显式 JSON/Fixture，调用正式 Decision Service，输出可解释 JSON；不复制生产决策逻辑、不访问生产数据库、不需要 Secret。
- [ ] Red 阶段测试先因 Contract/Decision/Capability 尚不存在而失败；Green 后目标测试、相关 Collection/Stage 6 回归、Contract 生成检查全部成功。
- [ ] 本 Change 不创建/修改 Migration、数据库表、公开 HTTP API、前端页面、Scheduler、依赖或锁文件。
- [ ] 文档同步当前机器入口与验证方式；不泄露 TikHub API Key。
- [ ] PR CI 成功，合并后 main 相关 CI 成功后再归档。

# 范围

- `contracts/collection`：Decision/Capability Pydantic 模型及生成 JSON Schema。
- `modules/collection/decision.py`：纯决策实现。
- `adapters/providers/tikhub/capabilities.py`：只登记当前已实现 XHS Capability。
- `scripts/dev/` 或现有适合位置：最小 Business Decision Probe，使用显式输入调用生产 Decision Service。
- Unit/Contract Test、Collection README、统一测试与调试说明的必要同步。

# 非目标

- 不实现抖音、微博、B站、快手 Operation/Mapper；这些在后续 Stage 7 PR 中分别建立真实 Fixture 后实现。
- 不实现真实 TikHub HTTP Transport、Provider Config 持久化或生产 Dispatcher 接线；真实付费 Dispatch 仍需最终 Budget Ledger。
- 不实现 Plan/Run Snapshot、预算 Migration、`run_comments` 数据库账户、评论 coverage 新列或 API/前端。
- 不实现/启用 Scheduler；`misfire_policy/max_catch_up_runs` 仍是明确 No-Go。
- 不把当前宿主无法完成的外部网络调用伪装成已验证。

# 必须保持不变

- Stage 1—6 公开 Contract、Migration、Provider Request/Attempt、Raw、Candidate/Ingestion、Content Owner 和 Job Runtime 行为保持兼容。
- Provider Operation 继续独占 endpoint/分页；Decision Service 不拼 URL、不解析 Provider Raw、不读写数据库。
- Mapper 继续只做 Raw→Canonical，不承担“是否继续抓详情/评论”的业务决策。
- Secret 不进入源码、Git、日志、Raw、Fixture、Contract、Probe 输出或测试快照。
- XHS 当前 `latest_v2` 评论排序和 App V2 endpoint 事实不被静默改变。

# 已确认关键决策

1. 采用 Blueprint 08 的统一 Decision Pipeline 和默认 `new_or_comment_changed`、adaptive 50/50/5 语义。
2. 这轮先建立跨平台共同 Decision/Capability 基础；四平台具体 Capability 只有对应 Operation/Fixture 实现时才加入机器 registry。
3. Decision Service 接受规范化事实，不依赖 TikHub 私有 JSON，也不直接查询 PostgreSQL；生产编排负责从 Mapper/数据库准备 previous/current facts。
4. Capability 以 `Provider + Platform + Business Operation` 表达，可被后续 HTTP Contract/前端生成链消费；这轮不提前暴露公开 Route。
5. 真实 TikHub API Key 只允许通过正式 Secret 边界用于显式 Real Probe，任何工具/日志/提交都不得回显。当前宿主直连 `api.tikhub.io` DNS 失败，因此外部实调不是本 Change 完成条件；后续具备网络边界时复用正式 Provider Probe，不写第二套请求逻辑。

# 方案比较

## 方案 A：先做 Decision + Capability 共同基础（采用）

先把五平台共享的“什么时候继续花钱”和“这个 Provider/Operation 能配置什么”落成稳定机器 Contract，再让每个平台 Operation/Mapper 接入。

优点：四个平台不会各自复制判断；零评论、重复评论数不变、增量资格和 Capability 约束只有一份生产逻辑；无需 Migration 即可独立 Red→Green；与 Blueprint 08 顺序一致。缺点：本 PR 本身不增加第二个平台真实数据。

## 方案 B：先直接实现抖音纵切（不采用）

可以较快增加平台数量，但在共同 Decision/Capability 尚无机器事实时容易把抖音私有条件写进业务 Service，后续微博/B站/快手再复制/重构，返工面更大。

## 方案 C：一次同时实现 Decision、Capability、预算、四平台 Operation/Mapper（不采用）

表面上 Stage 7 推进快，但跨 Contract、Migration、Provider 真实 Fixture 和多平台字段验证，无法形成小而完整的 Red→Green 单元，CI/Review 根因难定位，并且真实 Fixture 尚未齐全。

# 实施步骤

[步骤 1：建立失败测试]
→ 修改范围：`tests/unit/collection/`、`tests/contracts/`
→ 预期结果：测试准确表达 Blueprint 08 的 Decision/Capability 行为，因目标模块/Contract 尚不存在而失败。
→ 验证方式：PR/CI Red 证据或可执行目标 pytest 输出。

[步骤 2：建立版本化 Contract 与 Decision Service]
→ 修改范围：`backend/src/aima_ugc/contracts/collection/`、`backend/src/aima_ugc/modules/collection/decision.py`、`modules/collection/__init__.py`
→ 预期结果：纯输入→纯输出，稳定 reason code，严格区分 null/0 和增减变化。
→ 验证方式：目标 Unit/Contract Test。

[步骤 3：建立当前 XHS Capability]
→ 修改范围：`backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py`、对应测试
→ 预期结果：只声明当前 XHS 已实现 Operation 和官方文档证明的业务能力；技术分页状态不泄漏 Capability。
→ 验证方式：Capability 单测 + 现有 XHS Operation 测试。

[步骤 4：固定生成物与独立调试入口]
→ 修改范围：`scripts/contracts/generate.py`、`contracts/collection/`、Business Decision Probe、测试说明
→ 预期结果：Contract 可检测漂移；维护者可用显式 JSON 验证同一生产 Decision Service。
→ 验证方式：`uv run python scripts/contracts/generate.py --check` + Probe 测试/示例。

[步骤 5：回归、Review、PR]
→ 修改范围：本 Change 直接相关 diff
→ 预期结果：Stage 1—6 相关行为不漂移；无 Secret/无无关改动。
→ 验证方式：目标 pytest、Collection/Stage 6 回归、Ruff/mypy/Contract check、GitHub Actions。

# 验证计划

目标命令：

```text
uv run pytest tests/unit/collection/test_stage7_decision.py tests/unit/collection/test_tikhub_capabilities.py tests/contracts/test_collection_stage7.py -q
uv run pytest tests/unit/collection tests/unit/content tests/contracts/test_provider_v1.py -q
uv run python scripts/contracts/generate.py --check
uv run ruff check backend/src/aima_ugc/contracts/collection backend/src/aima_ugc/modules/collection backend/src/aima_ugc/adapters/providers/tikhub tests/unit/collection tests/contracts scripts/contracts scripts/dev
uv run mypy backend/src/aima_ugc
```

本宿主没有本地 Git 工作树/可用项目终端，因此 Red/Green 与完整命令由远端 PR GitHub Actions 提供新鲜证据；若 CI 没有覆盖某个目标命令，必须通过临时/正式工作流或其他可审计执行入口补足，不能只推断。

# 兼容、Migration、部署和回滚

- 公共 HTTP API：无变化。
- Canonical/Provider V1：无破坏性变化；新增独立 Collection V1 Contract。
- 数据库/Migration：无变化。
- 依赖/Lock：无变化。
- 部署：无新增运行进程或生产配置。
- 回滚：回滚本 PR 即可；无数据回填/数据库回滚。
- 安全：Capability/Decision/Probe 输入输出禁止 Secret；真实 API Key 不进入本 Change 文件。

# Git

- 基线 main：`d0c1dc0b64bbda0c93d49aff1cc83677a0c17c29`
- 分支：`agent/stage7-decision-capability`
- Change：`in_progress`
- Red：待执行
- Green：未执行
- PR：未创建
- CI：未运行
- 合并：未执行
- 归档：未执行
