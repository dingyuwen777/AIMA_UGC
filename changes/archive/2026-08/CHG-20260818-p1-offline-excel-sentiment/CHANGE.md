---
id: CHG-20260818-p1-offline-excel-sentiment
title: 临时 P1 Excel 离线导入、去重与舆情 AI 打标
level: L3
status: done
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
  note: P1 已合并后如需回退，使用普通 Git revert 回退 P1 合并及相关提交；不得改写 Stage 1—7 已发布 Migration 历史。
---

# 临时 P1 Excel 离线导入、去重与舆情 AI 打标

## 1. 最终结果

P1 是 Stage 7 与 Stage 8 之间的一次临时优先插入，不改变正式 Stage 编号。首版无数据库业务主链已经完成、合并并通过合并后验证：

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

P1A—P1H 全部完成。临时 Blueprint 14 已删除，长期 Excel 与 Analysis 规则分别收口到 Blueprint 13/15，Stage 8 已恢复为下一正式阶段；本 Change 没有进入 Stage 8 开发。

## 2. 最终设计边界

### 2.1 File Provider / Excel

- `openpyxl` read-only + `iter_rows(values_only=True)` 顺序读取输入 Excel；
- 中间业务数据使用 JSONL，不把 Excel 作为处理链事实源；
- 关键词过滤与去重均为 Provider-neutral；
- 稳定身份优先平台 URL 原生 ID，再来源文章编号，再规范化 URL SHA-256 fallback；
- `UnifiedContentRecordV1 = content + matched_keywords + analysis`；
- Canonical 只承载 Provider/平台可观察事实，不增加 AI 标签；
- `UnifiedDataExcelV1` 是唯一数据 Excel Contract；
- `tikhub_test`、`imports_test` 与未来正式导出共用唯一 `backend/src/aima_ugc/platform/export/excel.py`；
- Workbook 固定 `内容` / `评论` 两 Sheet；raw/labeled 使用同一 Contract；
- raw Excel 只是可选人工审阅旁路，不进入默认 `run_all()`。

### 2.2 Analysis / Prompt / LLM

唯一具体标签事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

当前 Prompt 包含 4 种情感、9 个一级标签、39 个二级标签。程序只解析 `AIMA_TAXONOMY_START/END` 中的机器 JSON；Python 不复制具体业务标签 Enum/Literal 或父子映射。

模型业务输入只允许：

```text
title
text
author.display_name
```

模型每条固定返回：

```text
item_no
sentiment
primary_label
secondary_label
```

本地 Validator 强制 JSON、固定字段、item 配对、Taxonomy membership 与一级/二级父子关系；非法结果不猜值、不模糊匹配。Validation Retry 与 Transport Retry 分离。

成功 Analysis 先写 checkpoint，再原子回写同一个 `deduplicated/contents.jsonl`。checkpoint 只负责恢复、费用安全和审计，不成为第二业务事实源。

恢复身份绑定：

```text
platform + external_content_id
+ input_hash
+ prompt_sha256 + taxonomy_sha256
+ model_provider + model
```

### 2.3 TikHub 调试

用户确认保留 `调整tikhub_test目录结构` 的目标结构和抓取行为：

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

生产 Transport 显式兼容既有 `https://api.tikhub.io`，其他 Origin 在发送 Secret 前拒绝。调试 `.env.example` 使用 `.dev` 且保留 300 秒调试超时。

目录重组后发现 `core/config.py` 默认 `.env` 路径会错误指向 `tikhub_test/core/.env`，最终修复为 `tikhub_test/.env` 并建立回归测试；没有修改正式抓取 endpoint、分页、Mapper 或 Runner 业务语义。

## 3. 子阶段完成状态

- [x] P1A：设计与阶段导航
- [x] P1B：Excel imports + imports_test + convert
- [x] P1C：关键词过滤 + UnifiedContentRecordV1 去重
- [x] P1D：UnifiedDataExcelV1 + 唯一共享 Exporter + tikhub_test 迁移
- [x] P1E：PromptTaxonomyLoader + Prompt + Analysis Contract/Service/Port + Fake + Retry tests
- [x] P1F：真实 OpenAI-compatible LLM Adapter + 最小输入 + Validation Retry + checkpoint + JSONL 原子回写
- [x] P1G：run_all + 崩溃恢复 + 最终同源 JSONL 导出
- [x] P1H：90k 性能 + 真实模型小样 + Review/CI + 收口
- [x] PR #66 合并、post-merge 12/12 验证与 Change 归档

## 4. 关键 Red → Green

### 4.1 checkpoint Provider/model 恢复身份

Red commit：`d80a8fb674f8cd51fa4be8b33e6bd3bbd03e51aa`。

Stage5A Run `32161890146` / Job `95792468933`：

```text
2 failed, 62 passed
exit 1
```

失败证明切换 Provider 或 model 时会错误复用旧 checkpoint。

Green commits：

```text
f3e0981e8605a28becc8164d17308ed681498247
d636cedefe324fd8620b77dc560e9755b8c916bd
```

后续专项验证：

```text
64 passed
exit 0
```

恢复身份增加当前 Provider/model 精确匹配，没有改变 checkpoint 文件格式。

### 4.2 P1H 性能入口

Red commit：`5c7448d0b6d4dd4d925dc4287cd0938d134b2cfa`，性能入口尚不存在，pytest 收集 exit 2。

Green commit：`155f0f76a7f67fc349ff2ea0522d74bb1cbee52c`。

随后 `b04670233fcf8b9b8bf1ab7d63db5c04a564a8b8` 修复 Windows PowerShell native process `$LASTEXITCODE` 传播，防止 Ruff 失败被后续成功命令掩盖。

### 4.3 与最新 main 集成后的 Excel Contract

P1 与 Stage1–7 新基线真正合并后，Stage5B 新鲜 Red：

```text
uv run pytest tests/unit/collection tests/contracts/test_provider_v1.py -q
3 failed, 247 passed
exit 1
```

三个失败均来自旧 TikHub 调试测试仍读取单 Sheet `内容与评论`，而公共 `UnifiedDataExcelV1` 已迁为 `内容` / `评论` 两 Sheet。修复只更新测试到当前公共 Contract，没有把生产 Exporter 改回旧布局。

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

主链合计：`148.919 s`，`604.35 rows/s`，峰值 RSS `234,762,240 B`。最终 Excel 导出是主要耗时，但没有正确性或 OOM 失败证据，因此没有引入 pandas。

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

5 条样本首次响应全部通过本地 Validator，Validation Retry=0。临时模型配置通过一次性 RSA-OAEP Runner 握手注入；明文 Secret 未提交到仓库、PR、日志或 Artifact，临时 workflow、私钥与解密配置均已清理。

```text
prompt_sha256   473af4b34e507ec086e9b8f4c177a2ffef8080319c619cb328599212438ca0e1
taxonomy_sha256 d5f118a1a8b002670439858b5dfb1d70f85ee324c1df360733f7caa33aa59c02
```

## 7. Stage 1—7 共享基线同步

P1 原基线为旧 `main@0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf`。Stage1–7 独立整改完成并归档后，共享基线为 `main@29a6f0882f2d87063a6bb64def78611c0b57136e`。

通过同步 PR #71 正常 merge 到 P1 分支：

```text
merge commit = 2028c0f2489c348a4bc1bf366aa8c873a4ea09a4
```

未 rebase、未 force push、未重写 P1 历史。同步后 `behind_by=0`，merge base 为当时最新 main。

共享文件语义合并同时保留：

- P1 Analysis/Export 门禁；
- `platform/storage` 当前真实路径；
- `provider-platform-capability.v1` / `provider-platform-route.v1` 固定公共 Contract；
- TikHub 共享 Exporter 迁移、`.dev` 默认 Origin 与 Canonical `platform` 语义。

## 8. PR #66 合并前最终验证

代码候选 `1fa1005e63d9bf1ab836e5ad48c0c35d921226dc`：11/11 适用 workflow success。

文档收口候选 `901f8a7d1178378a7b134be6ce78644a0f1a46a6`：11/11 适用 workflow success。

最终 `ready_for_review` head `fb741a13800324357cc9735e3417bd234646bbea`：11/11 适用 workflow success。

其中 Stage5A 新鲜证据包括：

```text
P1 pytest: 66 passed in 3.21s
Ruff format: 40 files already formatted
Ruff check: All checks passed
mypy: Success, 24 source files
Analysis/Export Contract: success
Architecture: success
Secret/Docs: success
Provider/Raw pytest: 24 passed in 0.69s
Provider/Collection Contract compatibility: success
全局 Ruff format: 307 files already formatted
全局 Ruff check: All checks passed
全局 mypy: Success, 168 source files
Table Ownership / Secret / Docs: success
```

Stage5D、Stage6 和总 CI 同时证明 PostgreSQL integration、Architecture/Ownership、Contract 和 Migration round-trip 全部 success。

## 9. PR 合并与 post-merge 验证

PR #66 已正常 merge 到 `main`，未 squash/rebase P1 历史：

```text
PR #66 merge commit = 089c7a24a63d8fe7206ad204e8474d8da790634c
```

GitHub App 当前不能直接列出 `push` 事件 run，因此 post-merge 验证使用从该 merge commit 建立的归档分支，仅临时增加 3 个无业务语义 `.txt` marker 触发全部正式 Stage workflow；marker 在归档前全部删除，不进入 main。

post-merge 验证 head：

```text
d68e0c95dcaed4ad84659a1d64b7074f5edf69d2
```

全部 **12/12 success**：

- CI — Run `32208096064`；
- Stage 1-7 Audit Correctness — `32208096107`；
- Stage 4 Job Runtime — `32208096151`；
- Stage 5A Provider Raw — `32208096002`；
- Stage 5B Collection Execution — `32208096050`；
- Stage 5C Provider Persistence — `32208096056`；
- Stage 5D Provider Dispatch — `32208096023`；
- Stage 6 XHS Vertical Slice — `32208096008`；
- Stage 7 Keyword Packs — `32208096001`；
- Stage 7 Plan Occurrence Run Snapshot — `32208096041`；
- Stage 7 Provider Config Routing — `32208096026`；
- Stage 7 Scheduler Runtime — `32208096042`。

该轮 Stage5A 再次完整通过 P1 专项、lint/type、Analysis/Export Contract、Architecture、Secret/Docs、Provider/Raw、Provider Contract 与全局 quality；Stage4/5/6 的 PostgreSQL 与 Migration 门禁也全部 success。

## 10. 两阶段 Review

### 需求符合性

已确认：Excel→JSONL→关键词→去重→AI→checkpoint→同 JSONL 回写→Excel 主链、raw 旁路、唯一 Prompt/Taxonomy、唯一 Exporter、最小模型输入、严格 Validator、有界 Validation Retry、checkpoint 恢复、90k、真实模型、TikHub 调试目录重组与 `.dev` 默认 Origin均符合已确认要求。

### 代码质量

已确认：

- P1 已与当时最新 Stage1–7 main 同步并正常合并；
- 无第二套 Workbook、Prompt/Taxonomy 或 TikHub 抓取实现；
- 旧 Excel 单 Sheet 测试已迁到公共两 Sheet Contract；
- `tikhub_test` 默认 `.env` 路径有回归保护；
- Secret/Origin 校验、原子文件写和 checkpoint fail-closed 边界保持；
- 无依赖升级、P1 DDL/Migration 或无关架构重构；
- 合并后完整 12/12 正式 workflow 再验证成功。

## 11. 文档与阶段导航

- Blueprint 13 永久维护统一 Excel Contract、同源 JSONL 和共享 Exporter；
- Blueprint 15 永久维护平台通用 Analysis/Prompt/Taxonomy；
- 临时 Blueprint 14 已删除；
- Blueprint README 已删除临时 P1 导航，Stage 8 恢复为下一正式阶段；
- P1 收口没有开始 Stage 8 实现。

## 12. 依赖、Migration、部署与回滚

- 依赖：无新增、升级或降级；
- 数据库：P1 无 DDL/Migration；
- 部署：未执行生产部署；
- 真实 LLM：普通 CI 默认关闭；
- 回滚：使用普通 Git revert；不得改写 Stage1–7 已发布 Migration；
- 90k/真实模型验证不涉及生产数据迁移。

## 13. Git / PR 最终状态

```text
P1 branch = feature/p1-offline-excel-sentiment
P1 PR = #66
P1 merge commit = 089c7a24a63d8fe7206ad204e8474d8da790634c
post-merge verification = 12/12 success
archive PR = #72
status = done
```

完成归档后，下一正式开发单元为 Stage 8；必须在新的任务中重新从届时 `main`、AGENTS.md、RVC Skill 与 Stage 8 相关 Blueprint 恢复事实，不得把本 Change 当作 Stage 8 当前实现依据。
