---
id: CHG-20260817-tikhub-debug-harness
title: TikHub 五平台独立测试调试工具
level: L2
status: in_progress
owner: ChatGPT
branch: agent/tikhub-test-debug
created: 2026-08-17
updated: 2026-08-17
depends_on: []
affected_areas:
  - collection
  - provider
affected_paths:
  - backend/src/aima_ugc/adapters/providers/tikhub_test
  - tests/unit/collection/test_tikhub_test_debug.py
  - .github/workflows/tikhub-test-real.yml
  - pyproject.toml
  - uv.lock
  - README.md
  - docs/测试与调试说明.md
contracts: []
data_changes: []
---

# TikHub 五平台独立测试调试工具

## 目标

在不依赖 PostgreSQL、API、Worker 或 Scheduler 的情况下，为小红书、抖音、微博、B站、快手提供可直接调用的 Python 调试入口。入口复用现有 TikHub 生产 Operation、分页、Transport、Mapper、Capability 和 Collection Decision 语义，保存真实 Raw、Canonical、跨运行轻量去重状态与人工审阅 Excel，用于开发和排障。

## 可观察成功标准

1. `backend/src/aima_ugc/adapters/providers/tikhub_test/` 提供五个平台独立 `run_*()` Python 函数，不新增 CLI。
2. 每个平台可设置现有 Capability 已支持的关键词、排序/筛选参数，以及搜索页数、最大帖子数、每帖评论目标、每根评论回复目标等调试边界；不得开放仓库当前主 Operation 不支持的业务参数。
3. 调试链严格复用 `adapters/providers/tikhub/operations/*`、生产分页状态、`TikHubHttpTransport`、生产 Mapper、Capability 和 `CollectionDecisionService`；不复制 endpoint、字段映射、自动 fallback 或隐藏重试。
4. 不写数据库。每次运行的 Raw、Canonical、manifest 和 XLSX 全部保存到 `tikhub_test/output/<platform>/runs/<run-id>/`；跨运行 `state.json` 只保存去重所需的内容 ID、已知评论 ID 和最近评论计数等轻量状态。
5. 内容唯一身份使用 `(platform, external_content_id)`；同次搜索和跨关键词/分页重复内容只执行一次后续详情/评论动作。评论按平台稳定 comment ID 去重；Provider 末页和目标达到后停止额外请求，已付费返回的整页 Raw 数据不裁剪。
6. `tikhub_test/.env` 是本地运行配置，加载 TikHub URL/密钥；真实 `.env` 永不提交。仓库只提交 `.env.example`，Secret 不进入代码、日志、Raw、Canonical、manifest 或 Excel。
7. Excel 沿用已批准的 Real Provider Probe 格式：核心 Sheet 名为 `内容与评论`；一条内容形成纵向区块，公共内容列跨评论行合并，每条评论一行，保留 comment/root/parent ID，URL 可点击，ID 以文本保存，浅色表头、白色主体、无粗黑边框。实现使用锁定的 `openpyxl==3.1.5`，优先保证可编辑性、样式、合并单元格和人工审阅质量。
8. 自动化测试覆盖 `.env` 加载与 Secret 隐藏、状态去重、Raw/Canonical 落盘、用 `openpyxl` 重新打开 XLSX 并验证布局/样式/超链接/文本 ID/防公式注入、五个平台公开入口及无数据库依赖。
9. GitHub-hosted Runner 使用受控 Secret 对 `https://api.tikhub.io` 以关键词“爱玛”执行五平台真实 Search → Detail → 一级评论 → 二级评论/回复验证；验证 Raw 与 Canonical 均可生成，且每个平台取得非空内容与评论样本。实时平台数据若某次检索没有可回复样本，必须扩大当前已批准搜索范围或明确报告证据，不能伪造通过。
10. PR 合并前完成需求符合性和代码质量两阶段复核；合并后对 `main` 再取得新鲜 CI 证据。

## 范围

- 新增 `tikhub_test` 调试包及平台入口。
- 新增无数据库文件状态、Raw/Canonical、manifest 与 XLSX 派生输出。
- 新增 `openpyxl==3.1.5` 作为正式锁定运行依赖，仅用于可编辑 XLSX 导出与验证。
- 新增单元测试与受控手动/本次验证用 GitHub Actions workflow。
- 更新根 README 与 `docs/测试与调试说明.md` 导航；`tikhub_test/README.md` 为具体使用入口。

## 非目标

- 不修改公共 HTTP API、Pydantic Contract、数据库 Schema、Migration、生产 Job/Scheduler 语义。
- 不恢复请求次数预算、金额预算、Budget Account、Reservation Ledger、发送前 Budget/Cost Guard。
- 不为调试工具增加自动网络重试、自动 Provider/API family fallback 或生产数据库写入。
- 不升级 Python、uv、前端依赖，也不引入 `pandas`、`xlsxwriter` 等第二套 Excel 技术路线；当前只增加 `openpyxl==3.1.5`。
- 不把调试输出提交到 Git 仓库。

## 必须保持不变

- 根目录仍是唯一 Python/uv 工程根；源码仍位于 `backend/src/aima_ugc/`。
- TikHub 出站 Origin 仍只允许生产 Transport 已批准的 `https://api.tikhub.io`。
- 五平台主 Operation、Capability、Canonical 字段语义和 Mapper 保持当前 `main` 实现。
- 真实 Provider Probe 不进入普通常规 CI；本 Change 的真实联网验证是用户明确授权的一次受控交付门禁，长期入口保持显式手动触发。
- Secret 不进入 Git 历史或用户可见日志。

## 已确认关键决策

1. 调试目录固定为 `backend/src/aima_ugc/adapters/providers/tikhub_test/`，平台代码可分文件组织。
2. 本地凭据文件固定为该目录下 `.env`；Git 只保存 `.env.example`。
3. 中间数据不用数据库，全部进入 `output/`；跨运行轻量 `state.json` 用于避免重复付费动作，可删除该文件重置调试状态。
4. Excel 复用 `CHG-20260814-stage7-real-provider-probe` 已批准的 `内容与评论` 纵向区块格式。
5. 费用节省通过去重、Provider 末页、显式页数/帖子/评论/回复边界和生产 Decision Service 的跳过语义实现，不建立生产预算域。
6. GitHub-hosted Runner 可使用仓库 Secret 做真实验证，密钥不得写入 workflow、代码或日志。
7. 2026-08-17 用户明确允许新增 Excel 库并要求优先生成“格式好看的 Excel”；本 Change 选择 `openpyxl==3.1.5`，原因是当前目标需要可编辑 `.xlsx`、合并单元格、样式、文本格式、超链接及重新打开验证，不需要再增加第二套 Excel 依赖。

## 现有生产复用点

- `backend/src/aima_ugc/adapters/providers/tikhub/runtime.py`
- `backend/src/aima_ugc/adapters/providers/tikhub/operations/{xiaohongshu,douyin,weibo,bilibili,kuaishou}.py`
- `backend/src/aima_ugc/adapters/providers/tikhub/mappers/*`
- `backend/src/aima_ugc/adapters/providers/tikhub/transport.py`
- `backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py`
- `backend/src/aima_ugc/modules/collection/decision.py`
- `backend/src/aima_ugc/contracts/canonical/*`
- 既有脱敏真实 Fixture 与 Stage 7 Real Probe 选择策略。

## 分步计划与验证

### 1. Red：固化调试包行为

→ 修改范围：`tests/unit/collection/test_tikhub_test_debug.py`  
→ 预期结果：测试表达配置、去重、输出、Excel 与五平台函数的目标行为；实现尚不存在时因目标模块缺失而失败。  
→ 验证方式：`uv run pytest tests/unit/collection/test_tikhub_test_debug.py -q`

### 2. Green：实现共用无数据库调试基础

→ 修改范围：`backend/src/aima_ugc/adapters/providers/tikhub_test/{__init__,config,core,excel}.py`、`.env.example`、`output/.gitignore`、`pyproject.toml`、`uv.lock`  
→ 预期结果：配置安全加载；一次请求一次发送；Raw/Canonical/manifest/state/XLSX 可生成；内容和评论可跨运行去重；Excel 可由 `openpyxl` 重新打开并保留目标版式。  
→ 验证方式：目标测试 + `uv run ruff check ...` + `uv run mypy backend/src` + `uv lock --check`

### 3. Green：接入五个平台生产 Operation/Mapper

→ 修改范围：`tikhub_test/{runner,xiaohongshu,douyin,weibo,bilibili,kuaishou}.py`  
→ 预期结果：五个平台入口仅准备参数、调用生产 Runtime/Operation/分页/Mapper、保存输出，不复制 endpoint 或 Canonical 规则。  
→ 验证方式：目标测试及现有五平台 Operation/Mapper/真实 Fixture 回归测试。

### 4. 文档与人类使用入口

→ 修改范围：`tikhub_test/README.md`、根 `README.md`、`docs/测试与调试说明.md`  
→ 预期结果：说明 `.env`、函数调用示例、平台参数、目录结构、去重/重置逻辑、Excel 格式和真实调用风险，并能从根导航进入。  
→ 验证方式：`uv run python scripts/quality/check_docs.py` 与人工逐项核对链接。

### 5. 真实 GitHub Runner 验证

→ 修改范围：`.github/workflows/tikhub-test-real.yml`  
→ 预期结果：受控 Secret 只写入 Runner 临时 `.env`，五平台真实采集均产生非空内容、评论和可解析输出；不写生产数据库，不上传含真实内容/Secret 的公开 Artifact。  
→ 验证方式：读取本次 workflow job/steps/logs，只记录状态码、计数和验证结论，不输出密钥或完整 Raw。

### 6. 两阶段复核与集成

→ 修改范围：本 Change、完整 PR diff  
→ 预期结果：先按用户成功标准复核，再检查正确性、安全、兼容性、无关改动和重复实现；CI/Real Probe 通过后合并。  
→ 验证方式：目标测试、相关测试、完整 `CI`、Secret scan、PR changed files/patch review、合并后 `main` 新鲜 workflow。

## 文档影响

- `tikhub_test/README.md`：具体使用说明和输出格式唯一人类入口。
- 根 `README.md`：增加独立 TikHub 测试/调试导航。
- `docs/测试与调试说明.md`：把 Stage 7 一次性 Probe 与长期 `tikhub_test` 调试入口区分清楚。
- Blueprint 不新增第二套机器 Schema；若需要导航，只做最小链接，不复制字段定义。

## 验证证据

- 开发基线：`main@e64a9e5956caf08fbbe14321cc0f45b603b3b919` 的适用 push workflows 查询结果均为 `completed/success`。
- TDD Red：PR #63 head `19046103682de53a2eb87014053bfe2895409d80` 的 CI run `32041123976` 中，Python 3.14.7 环境、`ruff format --check`、`ruff check`、`mypy backend/src` 均先通过；随后 `uv run pytest tests/unit -q` 在收集 `test_tikhub_test_debug.py` 时明确失败为 `ModuleNotFoundError: No module named 'aima_ugc.adapters.providers.tikhub_test'`，这是目标实现尚不存在导致的正确失败原因。
- `openpyxl==3.1.5` 的 Python 3.14.7 实际兼容、Green、真实 Provider、PR 最终与合并后证据尚未完成，后续只记录本轮新鲜结果。

## Git 状态

- 分支：`agent/tikhub-test-debug`，从 `main@e64a9e5956caf08fbbe14321cc0f45b603b3b919` 创建。
- PR：#63，Draft / Open。
- 已完成 Red 测试提交与格式门禁修正；当前进入 Green。
- 合并：尚未执行。
- 发布/部署：不适用；本任务只交付仓库内调试能力。
