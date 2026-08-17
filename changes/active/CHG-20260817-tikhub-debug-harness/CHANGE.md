---
id: CHG-20260817-tikhub-debug-harness
title: TikHub 五平台独立调试与评论增量一致性修复
level: L2
status: in_progress
owner: ChatGPT
branch: agent/tikhub-test-debug
created: 2026-08-17
updated: 2026-08-18
depends_on: []
affected_areas:
  - collection
  - provider
  - content
affected_paths:
  - backend/src/aima_ugc/adapters/providers/tikhub_test
  - backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py
  - backend/src/aima_ugc/bootstrap/collection_scope.py
  - backend/src/aima_ugc/modules/collection/decision.py
  - tests/unit/collection
  - tests/integration/collection
  - pyproject.toml
  - uv.lock
  - README.md
  - docs/测试与调试说明.md
  - docs/blueprint/08-采集策略与平台能力.md
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
  - docs/collection/README.md
  - docs/collection/xiaohongshu.md
contracts: []
data_changes: []
---

# TikHub 五平台独立调试与评论增量一致性修复

## 背景与当前事实

本 Change 最初负责建立五平台 TikHub 无数据库独立调试工具。实施过程中按用户要求继续核对整个系统设计与生产实现后，发现 Stage 7 已批准 Blueprint 与当前机器实现存在一个直接影响费用与调试真实性的缺口：

1. `docs/blueprint/08-采集策略与平台能力.md` 已明确规定：已有内容 `comment_count` 增加时优先增量抓取；有稳定“最新”排序的平台从最新第一页开始，遇到已知 `comment_id` 并达到安全边界后停止继续翻页，稳定 `stop_reason=known_comment_reached`。
2. 小红书当前生产 Operation `build_note_comments_request()` 已固定发送 `sort_strategy=latest_v2`；TikHub 官方接口说明将该值定义为按时间倒序/最新优先，并推荐用于稳定分页。
3. 但 `XHS_TIKHUB_CAPABILITY.comments.supports_incremental_comment_sort` 当前仍为 `False`，因此生产 `CollectionDecisionService` 会把 `comment_count` 增长降级成 `refresh_controlled`，不会发出 `fetch_incremental`。
4. 正式 `TikHubCollectionScopeExecutor._fetch_comments()` 当前也没有读取 PostgreSQL 已知一级评论 ID，因此即使收到 `fetch_incremental` 也不能实现 `known_comment_reached`。
5. PostgreSQL `comments` 已有 `(content_id, external_comment_id)` 唯一身份，不需要新表或 Migration；缺的是只读历史边界与执行停止逻辑。
6. `docs/collection/xiaohongshu.md` 仍包含“小红书是唯一已落地平台”“Stage 7 Budget”等过期描述，需要与当前 Stage 7/预算回撤事实同步。

因此该问题不是新增一套调试私有策略，而是修复“已批准 Blueprint → Capability → Decision → PostgreSQL previous state → 正式 Scope Executor → 调试入口”的一致性。

## 目标

1. 为小红书、抖音、微博、B站、快手提供可直接调用的 Python 调试入口，不依赖 PostgreSQL、API、Worker 或 Scheduler。
2. 调试入口复用生产 TikHub Operation、分页、Transport、Mapper、Capability 和 Collection Decision，不复制 endpoint、字段映射或业务规则。
3. 修复 XHS 已批准增量评论在生产主链未闭环的问题，使系统和调试工具都调用同一“已知评论边界”规则。
4. 保存 Raw、Canonical、`run_summary.json`、跨运行轻量 state 和原始数据 Excel；不写生产数据库。
5. 最终完成五平台受控真实 Provider 验证、PR Review、CI、合并后 main 复验和 Change 归档。

## 可观察成功标准

### A. 五平台独立调试

1. `backend/src/aima_ugc/adapters/providers/tikhub_test/` 提供五个平台独立 `run_*()` Python 函数，不新增 CLI。
2. 关键词在函数参数配置；同时支持 `keyword="爱玛"` 与 `keywords=("爱玛", "爱玛电动车")`。同一运行每个关键词独立执行 Search，但共享内容去重，重复帖子只拉一次 Detail/评论，并在 run summary/Excel 保留命中关键词。
3. `.env` 只保存 `TIKHUB_BASE_URL`、`TIKHUB_API_KEY`、超时等 Provider 连接配置；真实 `.env` 永不提交，仓库只保存 `.env.example`。
4. 每次运行的 Raw、Canonical、`run_summary.json` 和 XLSX 保存到 `tikhub_test/output/<platform>/runs/<run-id>/`；跨运行 `state.json` 保存轻量 current/去重状态，可删除后重置。
5. Excel 是“原始采集数据 Excel”，不是分析报告；字段来自统一 Canonical，完整 Provider Raw 仍单独保存。
6. Excel 使用锁定 `openpyxl==3.1.5`，保持 `内容与评论` 核心 Sheet、内容区块纵向合并、每条评论一行、comment/root/parent ID、文本 ID、超链接、浅色表头、防公式注入和命中关键词。
7. 未来正式系统级原始数据 Excel 导出落地后，必须删除 `tikhub_test/excel.py` 的平行实现并复用共享 Data Exporter；该门禁由 Blueprint 13 固化。

### B. 五平台生产评论增量闭环

8. XHS `get_note_comments` 继续固定使用生产 Operation 的 `sort_strategy=latest_v2`；不创建第二个评论 Client/endpoint。
9. XHS 与 B站 Capability 声明 `supports_incremental_comment_sort=True`；抖音、微博、快手基于当前官方/真实排序证据保持 `False`，不得为统一形式强行扩大能力。
10. `comment_count` 增加且 previous state 存在时，生产 Decision 返回 `fetch_incremental / comment_count_increased_incremental`。
11. PostgreSQL previous-state 读取一次取得目标内容已有一级评论 external ID 集合，不做逐评论 SQL，不改变表结构。
12. 增量页必须先完整保存 Raw，并对当前已付费页面全部执行 Mapper/Ingestion；不能因命中旧评论而裁掉本页已返回数据。
13. 对按最新排序的页面，若存在一个已知历史评论，且从第一个已知评论开始到该页末尾均为已知历史评论，则判定进入连续历史区；记录 `stop_reason=known_comment_reached` 并不再请求下一页。若“已知评论后又出现新评论”，不能提前停止。
14. `known_comment_reached` 规则由生产 Collection 代码拥有；正式 Scope Executor 和 `tikhub_test` 调用同一规则，测试目录不得复制一份判断。
15. 生产 PostgreSQL/Fake Transport 纵切证明：已有 XHS 内容 `comment_count: 1 → 2` 时只请求 Search + 第一页 Comments；第一页含“新评论 → 已知旧评论”且 Provider 仍声明有下一页时，不发送第二页评论请求，新评论入库，历史评论可正常更新，Coverage 记录 `known_comment_reached`。

### C. 文档与交付

16. `docs/blueprint/08`、`docs/collection/README.md`、`docs/collection/xiaohongshu.md`、模块 README/测试说明与机器实现一致；删除预算已回撤、平台状态已过期等相关错误描述。
17. GitHub-hosted Runner 使用受控 Secret 对 `https://api.tikhub.io`、关键词“爱玛”执行五平台真实 Search → Detail → 一级评论 → 二级评论/回复验证；不把 Secret/完整真实 Raw 上传到公开 Artifact。
18. PR 合并前完成需求符合性与代码质量两阶段 Review；合并后对 `main` 取得新鲜 CI 证据后再归档 Change。

## 范围

- `tikhub_test` 配置、运行、文件状态、Raw/Canonical、原始数据 Excel、五平台函数入口与文档。
- `openpyxl==3.1.5` 与 `types-openpyxl` 的锁定依赖。
- XHS Capability 增量声明修复。
- Collection Decision 的共享历史评论边界纯规则。
- PostgreSQL Content/Comment current state 的只读历史一级评论 ID 查询。
- 正式 TikHub Scope XHS 增量评论停止逻辑与 Coverage stop reason。
- `tikhub_test` 对同一生产规则的文件状态适配。
- 相关 Unit/Integration/Fixture 回归和文档同步。

## 非目标

- 不新增/修改公共 HTTP API、Pydantic Contract Schema、数据库 Schema 或 Migration。
- 不恢复请求次数预算、金额预算、Budget Account、Reservation Ledger 或发送前 Budget/Cost Guard。
- 不为 TikHub 增加自动网络重试或自动 App/Web/API family fallback。
- 不把当前没有安全最新评论边界证据的抖音/微博/快手强行声明为增量评论能力。
- 不把 Provider Raw JSON 变成公共业务结构；原始数据 Excel 仍以 Canonical/Aggregate 语义为列来源。
- 不实现分析报告或 Report Renderer。

## 必须保持不变

- 根目录是唯一 Python/uv 工程根；源码在 `backend/src/aima_ugc/`。
- TikHub 出站 Origin 仍只允许生产 Transport 已批准的 `https://api.tikhub.io`。
- 五平台现有主 Operation、Mapper、Canonical 字段语义保持；本轮纠正已批准评论增量设计在生产执行层的缺口，并按真实证据更新 XHS/B站 Capability；不改变五个平台主 Operation/Mapper/Canonical 语义。
- 每个 Provider Attempt 最多一次真实发送；Raw 先保存，Mapper/Ingestion 后执行。
- 已付费返回的整页 Raw/Canonical 不因软目标或历史边界被本地裁剪。
- 真实 Provider Probe 不进入普通 CI；Secret 不进入 Git、日志、Raw、Canonical、run summary 或 Excel。

## 已确认关键决策

1. 调试目录固定为 `backend/src/aima_ugc/adapters/providers/tikhub_test/`。
2. 本地 Provider 凭据固定从该目录 `.env` 加载；Git 只保存 `.env.example`。
3. 关键词属于运行参数，不属于 Secret `.env`；单关键词和多关键词都支持。
4. 中间数据不用数据库，全部进入 `output/`；`state.json` 用于跨运行 current/去重，可删除重置。
5. 原始数据 Excel 复用已批准的 `内容与评论` 纵向区块格式；不是舆情报告。
6. `openpyxl==3.1.5` 用于当前阶段性 Excel；未来系统共享原始数据导出完成后按 Blueprint 13 删除调试目录平行实现。
7. 当前没有生产预算域；省钱依赖身份去重、Decision、Provider 末页、业务/技术停止条件和增量历史边界。
8. XHS `latest_v2` 与 B站 `mode=2 + next_offset=0` 都取得当前真实多评论顺序证据，因此两者开启生产增量；抖音无最新评论排序参数，微博/快手真实顺序不满足安全边界，保持关闭。
9. 历史边界采用“当前整页处理完成后再决定是否继续下一页”，且只有从首个已知评论到页尾均为已知历史评论才停止，降低页面内置顶/混排造成误停的风险。

## 生产复用点

- `backend/src/aima_ugc/adapters/providers/tikhub/runtime.py`
- `backend/src/aima_ugc/adapters/providers/tikhub/operations/*`
- `backend/src/aima_ugc/adapters/providers/tikhub/mappers/*`
- `backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py`
- `backend/src/aima_ugc/bootstrap/collection_scope.py`
- `backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py`
- `backend/src/aima_ugc/modules/collection/decision.py`
- `backend/src/aima_ugc/contracts/canonical/*`
- `backend/src/aima_ugc/modules/content/tables.py`

## TDD / 验证计划

### 1. 已完成：调试包 Red → Green

- 初始 Red：目标模块不存在时 pytest 正确失败。
- Green：Python 3.14.7 上 Ruff、mypy、目标测试、Secret scan 通过。
- 多关键词 Red：`run_xiaohongshu()` 不接受 `keywords` 时仅新增用例失败。
- 多关键词 Green：Runner 验证 `ruff + mypy + 8 个调试目标测试` 成功后提交。

### 2. 当前：XHS 增量评论生产 Red

新增/调整测试先证明以下当前缺口：

- Capability 应声明 XHS incremental；
- Decision 应得到 `fetch_incremental`；
- PostgreSQL state reader 应返回历史一级评论 ID；
- 正式 Scope 第一页命中安全历史边界后不应请求下一页，并写 `known_comment_reached`；
- `tikhub_test` 应调用同一生产边界规则。

在生产修复前必须实际观察这些测试按正确原因失败。

### 3. Green / Refactor

最小修改 Capability、Decision helper、state reader、Scope Executor 和调试 state 适配；不增加 Schema/Migration/新 endpoint。

### 4. 回归

至少执行：

```text
uv lock --check
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit/collection tests/unit/content tests/contracts/test_provider_v1.py -q
uv run pytest tests/integration/collection tests/integration/content -q   # PostgreSQL 18
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
```

并读取 Stage 6 XHS Vertical Slice、完整 CI 和受影响 Stage 7 workflows 的新鲜结果。

### 5. 真实 Provider / Review / 集成

完成五平台真实 Runner 验证；两阶段 Review；PR #63 由 Draft 转正式并正常合并；main 新鲜 CI 后归档 Change。

## 已有验证证据

- 开发基线：`main@e64a9e5956caf08fbbe14321cc0f45b603b3b919` 的适用 push workflows 均成功。
- 初始 TDD Red：PR #63 head `19046103682de53a2eb87014053bfe2895409d80`，pytest 因 `aima_ugc.adapters.providers.tikhub_test` 不存在而失败，前置 Ruff/mypy 已通过。
- 调试 Green：`dd34563f1cba09eb70b9c3a570e98b2ec61dee9c` 的只读目标门禁中 Python 3.14.7、`openpyxl==3.1.5`、`types-openpyxl`、Ruff、mypy 137 个源文件、30 个目标/回归测试、Secret scan 全部通过。
- 多关键词 Red：`af0127c81f59fc5121e8302477f7b4096f90a072` 的目标门禁中仅多关键词用例因 `unexpected keyword argument 'keywords'` 失败。
- 多关键词 Green：一次性受控 Runner 在 Python 3.14.7 上通过 Ruff、mypy 137 源文件与 8 个调试目标测试后生成提交 `64db854e5469f882f9fe6ba7466b31ffa3243727`；一次性补丁 workflow 随后已删除。
- 系统一致性调查：Blueprint 08 已有 `known_comment_reached`/增量评论设计；XHS Operation 已固定 `latest_v2`；Capability 仍为 false；正式 Scope 缺历史 comment ID；PostgreSQL `comments` 现有唯一身份足以实现，无需 Migration。

## Git 状态

- 分支：`agent/tikhub-test-debug`。
- PR：#63，Draft / Open。
- 当前 head 在本次 Change 更新前为 `528b0c67f482d93c26bc61a1dce1ceb7898d81d2`。
- 合并：尚未执行。
- 发布/部署：不适用；本 Change 不改变生产部署形态。

### 五平台真实排序与兼容证据（GitHub-hosted Runner）

- `32045460636`：五平台首轮真实验证。XHS `latest_v2` 获得唯一一级评论且时间严格非增；快手获得 94 条唯一一级评论但时间顺序非严格非增。
- `32047972292`：抖音 post-fix 真实兼容验证，生产 extractor 从 8 个混合业务卡片中过滤并映射 7 个稳定 `aweme_id`，Detail/Comments 主链可继续；抖音评论 Operation 仍无已批准最新评论排序参数。
- `32048374466`：微博真实 shape 验证，Search/Detail 可映射；21 个评论候选中 20 个为有效稳定 ID，`sort_type=1` 的 20 个评论时间顺序 `time_nonincreasing=false`，因此不启用增量。
- `32049910092`：B站最终定向验证，生产 `mode=2 + next_offset=0` 在 Provider 报告 105 条评论的样本上返回 20 条，20/20 comment ID 唯一、20 个时间戳严格非增；结合官方 `mode=2=time`，启用 B站增量。
- 所有真实调用使用一次性 RSA-3072 OAEP-SHA256 凭据交接，Runner 接收后立即清理 PR 密文占位和临时密钥材料；明文 TikHub Key 未写入 Git、PR、日志或 Artifact。
