---
id: CHG-20260818-p1-offline-excel-sentiment
title: 临时 P1 Excel 离线导入、去重与舆情 AI 打标
level: L3
status: ready_for_review
owner: AI coding agent
branch: feature/p1-offline-excel-sentiment
base_branch: main
created_at: 2026-08-18
updated_at: 2026-08-19
affected_paths:
  - docs/blueprint/
  - backend/src/aima_ugc/adapters/llm/
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/providers/imports_test/
  - backend/src/aima_ugc/adapters/providers/tikhub_test/
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/contracts/analysis/
  - backend/src/aima_ugc/contracts/export/
  - backend/src/aima_ugc/platform/export/
  - contracts/analysis/
  - contracts/export/
  - scripts/performance/
  - tests/unit/analysis/
  - tests/unit/collection/
  - tests/unit/platform/
  - .github/workflows/stage5a-provider-raw.yml
rollback:
  strategy: revert
  note: P1 未归档前统一回退本 Change 对应提交；不得修改数据库 Schema，不得覆盖其他 Active Change。
---

# 临时 P1 Excel 离线导入、去重与舆情 AI 打标

## 1. 结果与边界

P1 是 Stage 7 与 Stage 8 之间的一次临时优先插入，不改变正式 Stage 编号。首版无数据库业务主链已经实现并验证：

```text
source.xlsx
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl
→ AI 打标
→ 本地结构/Taxonomy 校验
→ Validation Retry
→ analysis/checkpoints.jsonl
→ 原子回写同一个 deduplicated/contents.jsonl
→ <source>_<run-id>_labeled_data.xlsx
```

固定不变量：

- Canonical 只承载 Provider/平台可观察事实，不增加 AI 标签；
- `UnifiedContentRecordV1 = content + matched_keywords + analysis`；
- checkpoint 只负责恢复、费用安全和审计，不成为第二业务事实源；
- raw Excel 是可选人工审阅旁路，不进入默认 `run_all()`；
- 一个 `UnifiedDataExcelV1`、一个共享 Excel Exporter；
- 一个 Prompt/Taxonomy；
- 模型业务输入仅 `title`、`text`、`author.display_name`；
- P1 不增加数据库 DDL/Migration、不升级依赖、不进入 Stage 8。

## 2. 已确认设计

### Excel / File Provider

- `openpyxl` read-only + `iter_rows(values_only=True)` 顺序读取；
- JSONL 中间业务文件使用临时文件 + flush/fsync + atomic replace；
- 稳定身份优先平台 URL 原生 ID，再来源文章编号，再规范化 URL SHA-256 fallback；
- 关键词过滤、去重与统一导出均为 Provider-neutral；
- `tikhub_test`、`imports_test` 和未来正式导出共用 `backend/src/aima_ugc/platform/export/excel.py`；
- Workbook 固定 `内容` / `评论` 两 Sheet，raw/labeled 使用同一 Contract。

### Analysis / LLM

唯一具体标签事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

当前 Prompt 为 4 种情感、9 个一级标签、39 个二级标签。程序只解析 `AIMA_TAXONOMY_START/END` 中的机器 JSON；Python 不复制具体业务 Enum/Literal/父子映射。

模型只返回：

```text
item_no
sentiment
primary_label
secondary_label
```

本地 Validator 强制 JSON、固定字段、item 配对、Taxonomy membership 与一级/二级父子关系；非法结果不猜值、不模糊匹配。Validation Retry 与 Transport Retry 分离。

checkpoint 恢复身份绑定：

```text
platform + external_content_id
+ input_hash
+ prompt_sha256 + taxonomy_sha256
+ model_provider + model
```

### TikHub 调试

保留 `调整tikhub_test目录结构` 的目标结构与抓取行为：

```text
tikhub_test/
├─ core/
├─ operations/
├─ test.py
├─ README.md
└─ .env.example
```

调试入口继续复用正式 Search/Detail/评论/回复/分页/Mapper/Capability/Collection Decision，不建立第二套采集器。

当前默认 TikHub Origin：

```text
https://api.tikhub.dev
```

生产 Transport 显式兼容既有 `https://api.tikhub.io`，其他 Origin 在发送 Secret 前拒绝。目录重组后发现的默认 `.env` 定位错误已修为 `tikhub_test/.env` 并有回归测试。

## 3. 子阶段

- [x] P1A：设计与阶段导航
- [x] P1B：Excel imports + imports_test + convert
- [x] P1C：关键词过滤 + UnifiedContentRecordV1 去重
- [x] P1D：UnifiedDataExcelV1 + 唯一共享 Exporter + tikhub_test 迁移
- [x] P1E：PromptTaxonomyLoader + Prompt + Analysis Contract/Service/Port + Fake + Retry tests
- [x] P1F：真实 OpenAI-compatible LLM Adapter + 最小输入 + Validation Retry + checkpoint + JSONL 原子回写
- [x] P1G：run_all + 崩溃恢复 + 最终同源 JSONL 导出
- [x] P1H：90k 性能 + 真实模型小样 + Review/CI + 收口
- [ ] PR #66 合并后的 post-merge 验证与 Change 归档

当前 P1 已满足 PR Review 条件；Change 在合并前保持 `ready_for_review`，不能提前标记 `done`。

## 4. 关键 Red → Green

### checkpoint 模型身份

Red：`d80a8fb674f8cd51fa4be8b33e6bd3bbd03e51aa`，Stage5A Run `32161890146`：

```text
2 failed, 62 passed
exit 1
```

证明切换 Provider/model 时会错误恢复旧 checkpoint。

Green：`f3e0981e8605a28becc8164d17308ed681498247` + `d636cedefe324fd8620b77dc560e9755b8c916bd`：

```text
64 passed
exit 0
```

恢复身份增加当前 Provider/model 精确匹配，没有改变 checkpoint 文件结构。

### P1H 性能入口

Red：`5c7448d0b6d4dd4d925dc4287cd0938d134b2cfa`，性能入口尚不存在，pytest 收集 exit 2。

Green：`155f0f76a7f67fc349ff2ea0522d74bb1cbee52c`。随后 `b04670233fcf8b9b8bf1ab7d63db5c04a564a8b8` 修复 Windows PowerShell native process `$LASTEXITCODE` 传播，避免 Ruff 失败被后续命令掩盖。

### 与新 main 集成后的 Excel Contract

Stage5B 新鲜 Red：

```text
uv run pytest tests/unit/collection tests/contracts/test_provider_v1.py -q
3 failed, 247 passed
exit 1
```

三个失败都是旧 TikHub 调试测试仍读取 `内容与评论`，而公共 `UnifiedDataExcelV1` 已迁为 `内容` / `评论` 两 Sheet。修复只更新测试到当前公共 Contract，不把生产 Exporter 改回旧布局。

### `tikhub_test` 默认 `.env`

目录移动后 `core/config.py` 曾错误查找 `tikhub_test/core/.env`。新增回归测试后改为父目录 `tikhub_test/.env`；正式抓取 endpoint、分页、Mapper 和 Runner 业务语义未改变。

## 5. 90,000 × 13 Windows 性能

Run `32165652105` / Job `95804494417`，Windows Server 2025 / Python 3.14.7：

```text
ruff format --check → exit 0
ruff check          → exit 0
pytest smoke        → exit 0, 1 passed in 1.66s
90k benchmark       → exit 0
```

| 阶段 | 用时 | rows/s | 峰值 RSS |
| --- | ---: | ---: | ---: |
| convert | 22.480 s | 4,003.59 | 53,231,616 B |
| filter_keywords | 4.131 s | 21,787.50 | 53,231,616 B |
| deduplicate | 8.010 s | 11,236.49 | 85,499,904 B |
| analysis_writeback（无网络 Fake） | 13.182 s | 6,827.34 | 220,123,136 B |
| export_labeled_excel | 101.117 s | 890.06 | 234,762,240 B |

主链合计 `148.919 s`、`604.35 rows/s`，进程峰值 RSS `234,762,240 B`。最终 Excel 导出是主要耗时，但当前没有正确性、OOM 或依赖层面的失败证据，因此没有引入 pandas。

## 6. 真实模型小样

Run `32199031852` / Job `95908742768`：success。

```text
provider = deepseek
model = deepseek-v4-pro
sample_count = 5
rows_succeeded = 5
rows_failed = 0
llm_http_attempts = 1
initial_valid_rate = 100%
retried_item_count = 0
final_failure_rate = 0%
average_attempts_per_item = 1.0
input_tokens = 4535
output_tokens = 2368
cost_amount = null
```

5 条样本首次响应全部通过本地 Validator，Validation Retry=0。临时模型配置使用一次性 RSA-OAEP Runner 握手；明文 Secret 未提交到仓库、PR、日志或 Artifact，临时 workflow/私钥/解密配置已清理。

```text
prompt_sha256   473af4b34e507ec086e9b8f4c177a2ffef8080319c619cb328599212438ca0e1
taxonomy_sha256 d5f118a1a8b002670439858b5dfb1d70f85ee324c1df360733f7caa33aa59c02
```

## 7. Stage 1—7 基线同步

P1 原基线为旧 `main@0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`。独立 Stage1–7 整改完成并归档后，共享基线为：

```text
main = 29a6f0882f2d87063a6bb64def78611c0b57136e
```

通过同步 PR #71 正常 merge 到 P1 分支：

```text
merge commit = 2028c0f2489c348a4bc1bf366aa8c873a4ea09a4
```

未 rebase、未 force push、未重写 P1 既有历史。同步后：

```text
behind_by = 0
merge_base = main@29a6f0882f2d87063a6bb64def78611c0b57136e
```

5 个共享文件采用语义合并：P1 Analysis/Export 与 Stage1–7 `platform/storage`、`provider-platform-*` 固定 Contract 同时保留。

## 8. 最终验证

### 代码候选

`1fa1005e63d9bf1ab836e5ad48c0c35d921226dc` 的 11 个适用正式 workflow 全部 success。

### 文档收口候选

`901f8a7d1178378a7b134be6ce78644a0f1a46a6` 在删除临时 Blueprint 14、恢复 Stage8 导航、更新 Blueprint13 和本 Change 后，再次取得 **11/11 success**：

- CI — Run `32207662590`；
- Stage 1-7 Audit Correctness — `32207662641`；
- Stage 5A Provider Raw — `32207662598`；
- Stage 5B Collection Execution — `32207662569`；
- Stage 5C Provider Persistence — `32207662642`；
- Stage 5D Provider Dispatch — `32207662582`；
- Stage 6 XHS Vertical Slice — `32207662587`；
- Stage 7 Keyword Packs — `32207662643`；
- Stage 7 Plan Occurrence Run Snapshot — `32207662654`；
- Stage 7 Provider Config Routing — `32207662581`；
- Stage 7 Scheduler Runtime — `32207662572`。

Stage4 未被 P1 changed paths 命中，不是本 PR 的适用 workflow。

Stage5A Job `95933920511` 的新鲜关键输出：

```text
P1 目标/回归 pytest: 66 passed in 3.21s
Ruff format: 40 files already formatted
Ruff check: All checks passed
mypy: Success, 24 source files
Analysis/Export Contract: exit 0
Architecture: Stage 1–7 架构骨架与硬边界检查通过
Secret: 通过
Docs: 文档入口与本地链接检查通过
Provider/Raw pytest: 24 passed in 0.69s
Provider/Collection Contract compatibility: 通过
全局 Ruff format: 307 files already formatted
全局 Ruff check: All checks passed
全局 mypy: Success, 168 source files
Table ownership / Secret / Docs: 通过
```

Stage5D、Stage6、总 CI 同时证明 PostgreSQL integration、Architecture/Ownership、Contract 和 Migration round-trip 全部 success。

## 9. 两阶段 Review

### 需求符合性

已确认：Excel→JSONL→关键词→去重→AI→checkpoint→同 JSONL 回写→Excel 主链、raw 旁路、唯一 Prompt/Taxonomy、唯一 Exporter、最小模型输入、严格 Validator、有界 Retry、checkpoint 恢复、90k、真实模型、TikHub 调试目录重组和 `.dev` 默认 Origin均符合已确认要求。

### 代码质量

已确认：

- P1 与最新 main `behind=0`；
- 无第二套 Workbook、Prompt/Taxonomy 或 TikHub 抓取实现；
- 旧 Excel 单 Sheet 测试已迁到公共两 Sheet Contract；
- `tikhub_test` 默认 `.env` 路径有回归保护；
- Secret/Origin 校验、原子文件写、checkpoint fail-closed 边界保持；
- 无依赖升级、DDL/Migration 或无关架构重构；
- 未发现阻止 PR 合并的严重/重要问题。

## 10. 文档与阶段导航

- Blueprint 13 永久维护统一 Excel Contract、同源 JSONL 和共享 Exporter；
- Blueprint 15 永久维护平台通用 Analysis/Prompt/Taxonomy；
- 临时 Blueprint 14 已删除；
- Blueprint README 已删除临时 P1 导航，Stage 8 恢复为下一正式阶段；
- 本次不开始 Stage 8 实现。

## 11. 依赖、Migration、部署与回滚

- 依赖：无新增/升级/降级；
- 数据库：无 P1 DDL/Migration；
- 部署：未执行生产部署；
- 真实 LLM：普通 CI 默认关闭；
- 回滚：PR 合并前可 revert P1 提交；合并后按普通 Git revert 回退，不改写已发布 Stage1–7 Migration。

## 12. Git / PR

```text
branch = feature/p1-offline-excel-sentiment
base = main@29a6f0882f2d87063a6bb64def78611c0b57136e
PR = #66
status = ready_for_review
```

同步 PR #71 已完成；旧 #70 已关闭未合并。下一步只允许：

```text
验证本次 status-only Change 提交的适用 CI
→ PR #66 Ready
→ 正常 merge 到 main
→ post-merge 验证
→ Change status=done 并归档
```

禁止直接推 main、force push、rebase 历史或进入 Stage8。
