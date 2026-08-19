---
id: CHG-20260818-p1-offline-excel-sentiment
title: 临时 P1 Excel 离线导入、去重与舆情 AI 打标
level: L3
status: in_progress
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

## 1. 目标与最终边界

P1 是 Stage 7 与 Stage 8 之间的一次临时优先插入，不改变正式 Stage 编号。首版不接数据库，业务主链固定为：

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

不变量：

- `CanonicalContentV1` 只承载 Provider/平台可观察事实，不增加 AI 标签；
- `UnifiedContentRecordV1 = content + matched_keywords + analysis`；
- `analysis/checkpoints.jsonl` 只负责恢复、费用安全和审计，不成为第二业务事实源；
- `raw_data.xlsx` 只是可选人工审阅旁路，不进入默认 `run_all()`；
- 一个 `UnifiedDataExcelV1`、一个共享 Excel Exporter；
- 一个 Prompt/Taxonomy；
- 模型业务输入只允许 `title`、`text`、`author.display_name`；
- P1 不增加数据库 DDL/Migration，不升级依赖，不进入 Stage 8。

## 2. 已确认关键决策

### 2.1 Excel 与文件处理

- Excel 输入使用 `openpyxl` read-only + `iter_rows(values_only=True)`；没有性能失败证据，不新增 pandas；
- 中间业务产物使用 JSONL；写入使用临时文件 + flush/fsync + atomic replace；
- 稳定身份优先平台 URL 原生 ID，再来源文章编号，再规范化 URL SHA-256 fallback；
- 关键词过滤与去重均是 Provider-neutral 处理；
- `tikhub_test`、`imports_test` 和未来正式导出共用 `backend/src/aima_ugc/platform/export/excel.py`；
- Workbook 固定为 `内容` / `评论` 两个 Sheet，raw/labeled 使用同一 Contract。

### 2.2 Analysis / Prompt / Taxonomy

唯一具体标签事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

程序只精确读取 `AIMA_TAXONOMY_START/END` 中的机器 JSON；具体标签不复制到 Python Enum/Literal/父子映射。当前 Prompt 为 4 种情感、9 个一级标签、39 个二级标签。

每条模型业务输入只发送：

```text
title
text
author.display_name
```

模型每条只返回 `item_no/sentiment/primary_label/secondary_label`。本地 Validator 强制 JSON、固定字段、item 配对、闭集 membership 与一级/二级父子关系；非法输出不猜值、不模糊匹配。

`max_validation_retries >= 0` 表示首次请求失败后最多额外 Validation Retry 次数。Validation Retry 与 Transport Retry 分离；成功 item 不因同批其他 item 失败而重复付费。

checkpoint 恢复身份绑定：

```text
platform
external_content_id
input_hash
prompt_sha256
taxonomy_sha256
model_provider
model
```

### 2.3 TikHub 调试边界

保留 `调整tikhub_test目录结构` 的目标设计：

```text
tikhub_test/
├─ core/
├─ operations/
├─ test.py
├─ README.md
└─ .env.example
```

Search、Detail、评论、回复、分页、Mapper、Capability 与 Collection Decision 继续复用正式生产实现，不建立第二套采集器。

当前 TikHub 默认 Origin 为：

```text
https://api.tikhub.dev
```

生产 Transport 显式兼容既有 `https://api.tikhub.io`，其他第三方 Origin 在发送 Secret 前拒绝。调试 `.env.example` 使用 `.dev`，300 秒超时保留。

目录重组后发现默认 `.env` 路径仍指向 `tikhub_test/core/.env`，现已修复为 `tikhub_test/.env` 并建立回归测试。

## 3. 子阶段状态

- [x] P1A：设计与阶段导航
- [x] P1B：Excel imports + imports_test + convert
- [x] P1C：关键词过滤 + UnifiedContentRecordV1 去重
- [x] P1D：UnifiedDataExcelV1 + 唯一共享 Exporter + tikhub_test 迁移
- [x] P1E：PromptTaxonomyLoader + Prompt + Analysis Contract/Service/Port + Fake + Retry tests
- [x] P1F：真实 OpenAI-compatible LLM Adapter + 最小输入 + Validation Retry + checkpoint + JSONL 原子回写
- [x] P1G：run_all + 崩溃恢复 + 最终同源 JSONL 导出
- [x] P1H：90k 性能 + 真实模型小样 + Review/CI + 代码收口
- [ ] PR #66 合并后 post-merge 验证、Change 归档

**当前检查点：P1H 的代码与设计目标已经完成。P1 分支已同步并包含 Stage 1—7 最新共享基线；最终代码候选 `1fa1005e63d9bf1ab836e5ad48c0c35d921226dc` 的 11 个适用正式 workflow 全部 success。临时 Blueprint 14 已删除，长期规则已收口到 Blueprint 13/15，Stage 8 已恢复为下一正式阶段但本 Change 不进入 Stage 8。当前只剩文档收口后的新鲜 CI、PR #66 合并、post-merge 验证和 Change 归档。**

## 4. P1A—P1G 实现摘要

### P1B / P1C

- `imports/` File Provider 与 `convert()` 将 13 列输入 Profile 转换为 Canonical JSONL；
- 平台时间按 `Asia/Shanghai` 解释，外部 ID 保持字符串；
- `filter_keywords()` 与 `deduplicate()` 使用 Provider-neutral `UnifiedContentRecordV1`；
- 去重身份为 `(platform, external_content_id)`，冲突 fail closed。

### P1D

- 建立 `UnifiedDataExcelV1`；
- 建立唯一共享 Exporter；
- `tikhub_test`/`imports_test` 均迁到共享 Exporter；
- 删除 `tikhub_test/core/excel.py` 的平行 Workbook 实现；
- raw/labeled Excel 使用同一两 Sheet Contract。

### P1E / P1F

- 建立 `ContentLabelAnalysisV1`、`PromptTaxonomyLoader`、严格 Runtime Validator、`ContentLabelingService`、LLM Port/Fake；
- 建立真实 OpenAI-compatible Adapter；
- 成功 Analysis 先 checkpoint，再回写同一 `deduplicated/contents.jsonl`；
- 真实模型默认关闭，普通 CI 不发付费请求。

### P1G

`imports_test.run_all()` 固定串联：

```text
convert
→ filter_keywords
→ deduplicate
→ label_sentiment
→ export_labeled_excel
```

`export_raw_excel()` 保持可选旁路。最终 Excel 只读取已回写 Analysis 的同一 deduplicated JSONL。

跨进程恢复严格绑定输入、Prompt/Taxonomy、Provider/model；旧身份不匹配的 checkpoint 只保留审计，不当作当前成功结果。

## 5. Red → Green 证据

### 5.1 checkpoint 模型身份缺口

Red commit：

```text
d80a8fb674f8cd51fa4be8b33e6bd3bbd03e51aa
```

Stage 5A Run `32161890146` / Job `95792468933`：

```text
2 failed, 62 passed
exit 1
```

失败精确证明切换 `model_provider` 或 `model` 时仍会错误复用旧 checkpoint。

Green commits：

```text
f3e0981e8605a28becc8164d17308ed681498247
d636cedefe324fd8620b77dc560e9755b8c916bd
```

Stage 5A Run `32162296188` / Job `95793757795`：

```text
64 passed
exit 0
```

并通过 Ruff、mypy、Analysis/Export Contract、Secret/Docs；当时仍存在独立 Stage1–7 共享基线问题，未伪称整仓全绿。

### 5.2 P1H 性能入口

Red commit：

```text
5c7448d0b6d4dd4d925dc4287cd0938d134b2cfa
```

Stage 5A Run `32164502249`：性能入口尚不存在，pytest 收集阶段按预期失败，exit 2。

Green commit：

```text
155f0f76a7f67fc349ff2ea0522d74bb1cbee52c
```

后续 Windows 性能门禁发现 native process 退出码传播缺口，又通过：

```text
b04670233fcf8b9b8bf1ab7d63db5c04a564a8b8
```

修复 PowerShell 严格传播 `$LASTEXITCODE`，避免 Ruff 失败被后续成功命令掩盖。

### 5.3 与新 main 集成后的 Excel Contract 漂移

P1 与 Stage1–7 新 main 真正合并后，Stage5B 新鲜 Red：

```text
uv run pytest tests/unit/collection tests/contracts/test_provider_v1.py -q
→ 3 failed, 247 passed
→ exit 1
```

三个失败都来自旧测试仍读取 `内容与评论` Sheet，而 P1 已批准并实现 `UnifiedDataExcelV1` 的 `内容` / `评论` 两 Sheet。

修复仅更新既有 TikHub 调试回归测试到当前公共 Excel Contract，不把生产 Exporter 改回旧布局；后续最终 Stage5B workflow 全绿。

### 5.4 `tikhub_test` 目录重组后的默认 `.env` 路径

Review 发现 `core/config.py` 移动后仍使用当前文件同目录查找 `.env`，会错误查找 `tikhub_test/core/.env`。新增回归测试锁定 `tikhub_test/.env`，实现改为父目录定位；不修改正式抓取 endpoint、分页、Mapper 或 Runner 业务语义。

## 6. 90,000 × 13 Windows 性能证据

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

主链合计：

```text
148.919 s
604.35 rows/s
peak RSS = 234,762,240 B
```

最终 Excel 导出是主要耗时，但当前没有正确性、OOM 或依赖层面的失败证据，因此没有引入 pandas。90k Analysis 使用由当前 PromptTaxonomy 动态取得合法标签的无网络 Fake，不代表真实模型网络延迟或吞吐。

## 7. 真实模型小样

真实模型 Run `32199031852` / Job `95908742768`：success。

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

5 条样本均第一次通过 JSON、固定字段、item 映射、Taxonomy membership 与一级/二级父子关系校验，因此 Validation Retry=0。

临时模型配置通过一次性 RSA-OAEP Runner 握手注入；明文 Secret 未提交到仓库、PR、日志或 Artifact。临时 workflow、私钥和解密配置均已清理。该结果只证明本次真实链路可运行，不外推为长期模型质量或稳定性承诺。

当前 Hash：

```text
prompt_sha256   473af4b34e507ec086e9b8f4c177a2ffef8080319c619cb328599212438ca0e1
taxonomy_sha256 d5f118a1a8b002670439858b5dfb1d70f85ee324c1df360733f7caa33aa59c02
```

## 8. Stage 1—7 共享基线同步

P1 最初基于旧 `main@0dc666192f83fa9e55d5cbfffb19c09d31c5ecaf` 开发。独立 Stage1–7 整改完成并归档后，当前共享基线为：

```text
main = 29a6f0882f2d87063a6bb64def78611c0b57136e
```

为保留 P1 历史且不 rebase/force push，先把 5 个真实冲突文件临时恢复到共同祖先，再通过同步 PR #71 将 `main` 正常 merge 到 P1 分支：

```text
PR #71
merge commit = 2028c0f2489c348a4bc1bf366aa8c873a4ea09a4
```

随后重放 5 个语义合并版本：

- Stage5A：保留 P1 Analysis/Export 门禁，并继承 `platform/storage` 当前真实路径；
- Contract generator/checker：保留 P1 Analysis/Export，同时继承 `provider-platform-capability/route` 固定公共 Contract；
- TikHub README：保留共享 Exporter 迁移与 `.dev` 默认 Origin；
- TikHub debug test：保留 P1 迁移，同时使用 Canonical `platform` 语义。

同步后比较结果为：

```text
behind_by = 0
merge_base = main@29a6f0882f2d87063a6bb64def78611c0b57136e
```

没有修改 Stage1–7 Migration/数据库语义，也没有把 Stage1–7 整改重新塞进 P1。

## 9. 最终代码候选 CI

最终代码候选：

```text
1fa1005e63d9bf1ab836e5ad48c0c35d921226dc
```

该 head 触发的 11 个适用正式 workflow 全部 `success`：

- CI — Run `32207144998`；
- Stage 1-7 Audit Correctness — `32207144985`；
- Stage 5A Provider Raw — `32207144989`；
- Stage 5B Collection Execution — `32207144995`；
- Stage 5C Provider Persistence — `32207145020`；
- Stage 5D Provider Dispatch — `32207145004`；
- Stage 6 XHS Vertical Slice — `32207144994`；
- Stage 7 Keyword Packs — `32207145065`；
- Stage 7 Plan Occurrence Run Snapshot — `32207145125`；
- Stage 7 Provider Config Routing — `32207144981`；
- Stage 7 Scheduler Runtime — `32207144992`。

Stage 4 没有被 P1 当前 changed paths 命中，不属于本次 PR 的适用 workflow。

关键门禁事实：

- Stage5A：P1 专项 pytest、Ruff、mypy、Analysis/Export Contract、Architecture、Secret/Docs、Provider/Raw、Provider Contract、Stage5A 全局 quality 全部 success；
- Stage5B：Collection tests、PostgreSQL integration、quality、Migration round-trip 全部 success；
- Stage5D：Unit/Provider、4xx takeover、Coverage/detail re-decision、Raw replay、PostgreSQL/Artifact、Ruff、mypy、Architecture/Ownership、Secret/Docs、Contract、Migration round-trip 全部 success；
- Stage6：Unit、Quality、PostgreSQL integration 与全部 Migration round-trip 全部 success；
- 总 CI：Stage1、Stage2 Platform、Stage3A Database、Windows bootstrap 等全部 success。

## 10. 两阶段 Review

### 需求符合性

已逐项确认：

- Excel → JSONL → 关键词 → 去重 → AI → checkpoint → 同 JSONL 回写 → Excel 主链存在；
- raw Excel 不进入默认主链；
- Canonical 不承载 AI 标签；
- 唯一 Prompt/Taxonomy 与唯一共享 Excel Exporter 均成立；
- 模型最小输入、严格 Validator、有界 Validation Retry 与失败不猜标签均成立；
- checkpoint 恢复绑定 input/Prompt/Taxonomy/Provider/model；
- 90k Windows 与 5 条真实模型小样均有新鲜证据；
- TikHub 目录重组与抓取生产复用保留；
- `.dev` 默认 Origin 保留，`.io` 仅兼容；
- P1 不新增数据库 Migration、不升级依赖、不进入 Stage8。

### 代码质量

已检查：

- P1 与 Stage1–7 main 同步后不存在 behind 分叉；
- 旧 Excel 单 Sheet 测试已迁到公共两 Sheet Contract；
- `tikhub_test` 重组后的 `.env` 默认路径已补回归；
- 无第二套 Workbook、第二套 Prompt/Taxonomy、第二套 TikHub 抓取逻辑；
- Secret 边界、Provider Origin 校验、文件原子写与 checkpoint 恢复保持 fail closed；
- 没有依赖升级、DDL/Migration 或无关架构重构。

未发现阻止 P1 进入最终 PR Review 的严重/重要问题。

## 11. 文档与阶段导航

P1 长期事实已收口：

- Blueprint 13 永久维护统一 Excel Contract、同源 JSONL 与共享 Exporter；
- Blueprint 15 永久维护平台通用 Analysis/Prompt/Taxonomy；
- 临时 Blueprint 14 已删除；
- Blueprint README 已删除临时 P1 导航并恢复 Stage 8 为下一正式阶段；
- Stage 8 本次不开始实现，下一次必须重新从合并后的 `main` 创建/认领独立 Change。

本节文档修改完成后仍需以新的最终 head 再执行适用 CI；通过后才能把本 Change 改为 `ready_for_review` 并合并 PR #66。

## 12. 依赖、Migration、部署与回滚

- 依赖：无新增、升级或降级；
- 数据库：无 DDL/Migration；
- 部署：无生产部署动作；
- 真实 LLM：普通 CI 默认关闭，真实 Probe 不常驻普通 workflow；
- 回滚：PR 合并前可 revert P1 对应提交；合并后按普通 Git revert 回退 P1，不改写 Stage1–7 历史 Migration；
- 90k/真实模型验证均无生产数据迁移回滚要求。

## 13. Git / PR 当前状态

```text
branch = feature/p1-offline-excel-sentiment
base = main@29a6f0882f2d87063a6bb64def78611c0b57136e
PR = #66
PR state = Open / Draft / 未合并
```

同步 PR #71 已完成并合入 P1 分支。旧同步 PR #70 已关闭且未合并。

当前仍不直接推 `main`、不 force push、不 rebase 历史。待本轮文档收口新鲜 CI 全绿后：

```text
Change → ready_for_review
PR #66 → Ready
正常 merge 到 main
→ post-merge 验证
→ Change status=done 并归档
```
